"""Unit tests for AIProductImageRefiner (OpenRouter Images API image
editing). NO real network call is EVER made here -- every test intercepts
the request via httpx.MockTransport, never a live httpx.Client."""
import base64
import dataclasses
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.models.enums import BackgroundIsolationStatus, PresentationType
from app.services.ai.image_editing_refiner import (
    IMAGES_ENDPOINT,
    MAX_TOTAL_IMAGES,
    AIImageRefinementError,
    AIProductImageRefiner,
)
from app.services.image_refinement_service import RefinementProductContext, RefinementRequest


def make_crop_bytes(width: int = 400, height: int = 400) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (120, 60, 10)).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def make_valid_response_b64(width: int = 512, height: int = 512) -> str:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (240, 240, 240)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def make_refiner(handler, model_name: str = "google/gemini-2.5-flash-image") -> AIProductImageRefiner:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return AIProductImageRefiner(api_key="fake-key-not-real", model_name=model_name, http_client=client)


def make_request(**overrides) -> RefinementRequest:
    defaults = dict(
        crop_bytes=make_crop_bytes(),
        presentation=PresentationType.BULK_TRAY,
        context=RefinementProductContext(
            name_en="Mixed Nuts",
            name_ar="مكسرات مشكلة",
            category="Nuts",
            selling_mode="weight",
            brand=None,
            flavor_variant=None,
        ),
        reference_images=[make_crop_bytes(200, 200), make_crop_bytes(200, 300)],
    )
    defaults.update(overrides)
    return RefinementRequest(**defaults)


def success_handler(captured_requests: list):
    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [{"b64_json": make_valid_response_b64(), "media_type": "image/png"}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 1290,
                    "total_tokens": 1390,
                    "cost": 0.0387,
                },
            },
        )

    return handler


# --- Request construction --------------------------------------------------


def test_payload_uses_the_configured_model_name():
    refiner = make_refiner(success_handler([]), model_name="google/gemini-2.5-flash-image")
    payload = refiner.build_request_payload(make_request())
    assert payload["model"] == "google/gemini-2.5-flash-image"


def test_source_crop_is_always_the_first_image():
    crop = make_crop_bytes(111, 111)
    request = make_request(crop_bytes=crop, reference_images=[make_crop_bytes(50, 50)])
    refiner = make_refiner(success_handler([]))

    payload = refiner.build_request_payload(request)

    first_url = payload["input_references"][0]["image_url"]["url"]
    assert base64.b64encode(crop).decode("ascii") in first_url


def test_total_images_never_exceed_three():
    request = make_request(reference_images=[make_crop_bytes(10, 10) for _ in range(5)])
    refiner = make_refiner(success_handler([]))

    payload = refiner.build_request_payload(request)

    assert len(payload["input_references"]) == MAX_TOTAL_IMAGES == 3


def test_prompt_explicitly_distinguishes_source_from_references():
    refiner = make_refiner(success_handler([]))
    payload = refiner.build_request_payload(make_request())

    prompt = payload["prompt"]
    assert "SOURCE PRODUCT IMAGE" in prompt
    assert "THIS IS THE PRODUCT TO PRESERVE AND EDIT" in prompt
    assert "STYLE/PRESENTATION REFERENCE ONLY" in prompt
    assert "DO NOT COPY THE PRODUCT" in prompt


def test_prompt_includes_the_full_system_prompt():
    refiner = make_refiner(success_handler([]))
    payload = refiner.build_request_payload(make_request())

    prompt = payload["prompt"]
    assert "PRODUCT PRESERVATION" in prompt
    assert "TRUTHFULNESS PRIORITY" in prompt
    assert "STRICTLY FORBIDDEN" in prompt


def test_prompt_includes_available_product_metadata():
    context = RefinementProductContext(
        name_en="Roasted Almonds",
        name_ar="لوز محمص",
        category="Nuts",
        selling_mode="unit",
        brand="Wehbi Roastery",
        flavor_variant="Salted",
    )
    refiner = make_refiner(success_handler([]))

    payload = refiner.build_request_payload(
        make_request(context=context, presentation=PresentationType.PACKAGED)
    )

    prompt = payload["prompt"]
    assert "Roasted Almonds" in prompt
    assert "Nuts" in prompt
    assert "Wehbi Roastery" in prompt
    assert "Salted" in prompt
    assert "packaged" in prompt


def test_bulk_presentation_gets_bulk_specific_emphasis():
    refiner = make_refiner(success_handler([]))
    payload = refiner.build_request_payload(make_request(presentation=PresentationType.BULK_LOOSE))

    prompt = payload["prompt"]
    assert "natural standalone pile" in prompt
    assert "do not keep the rectangular shape" in prompt


def test_packaged_presentation_gets_packaging_preservation_emphasis():
    refiner = make_refiner(success_handler([]))
    payload = refiner.build_request_payload(make_request(presentation=PresentationType.PACKAGED))

    prompt = payload["prompt"]
    assert "Preserve the exact real package" in prompt
    assert "Do not redesign the packaging" in prompt


def test_context_never_carries_a_price_field():
    field_names = {f.name for f in dataclasses.fields(RefinementProductContext)}
    assert not any("price" in name.lower() for name in field_names)


def test_request_is_sent_to_the_dedicated_images_endpoint():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200, json={"data": [{"b64_json": make_valid_response_b64(), "media_type": "image/png"}]}
        )

    refiner = AIProductImageRefiner(
        api_key="fake-key-not-real",
        model_name="google/gemini-2.5-flash-image",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    refiner.refine(make_request())

    assert captured["url"] == IMAGES_ENDPOINT


# --- Successful response handling ------------------------------------------


def test_valid_response_is_decoded_and_normalized_to_1200x1200():
    refiner = make_refiner(success_handler([]))

    result = refiner.refine(make_request())

    out = Image.open(BytesIO(result.image_bytes))
    assert out.size == (1200, 1200)
    assert out.format == "JPEG"
    assert result.background_isolation_status == BackgroundIsolationStatus.APPLIED


def test_only_one_request_is_made_per_refine_call():
    calls: list = []
    refiner = make_refiner(success_handler(calls))

    refiner.refine(make_request())

    assert len(calls) == 1


# --- Failure handling: exactly ONE attempt, never retried ------------------


def test_http_error_response_raises_without_retrying():
    calls: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={"error": {"message": "server error"}})

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())

    assert len(calls) == 1


def test_connection_error_raises_without_retrying():
    calls: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("simulated network failure", request=request)

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())

    assert len(calls) == 1


def test_missing_data_field_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"usage": {"cost": 0.01}})

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())


def test_empty_data_array_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())


def test_malformed_base64_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"b64_json": "not-valid-base64!!!", "media_type": "image/png"}]}
        )

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())


def test_valid_base64_but_not_an_image_is_rejected():
    not_an_image_b64 = base64.b64encode(b"just some random bytes, not a real image").decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"b64_json": not_an_image_b64, "media_type": "image/png"}]}
        )

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())


def test_empty_base64_string_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": "", "media_type": "image/png"}]})

    refiner = make_refiner(handler)

    with pytest.raises(AIImageRefinementError):
        refiner.refine(make_request())


# --- Secrets are never leaked ------------------------------------------------


def test_error_does_not_expose_the_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    refiner = AIProductImageRefiner(
        api_key="THIS-IS-THE-SECRET-KEY",
        model_name="google/gemini-2.5-flash-image",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AIImageRefinementError) as exc_info:
        refiner.refine(make_request())

    assert "THIS-IS-THE-SECRET-KEY" not in str(exc_info.value)


def test_request_carries_the_bearer_authorization_header():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200, json={"data": [{"b64_json": make_valid_response_b64(), "media_type": "image/png"}]}
        )

    refiner = AIProductImageRefiner(
        api_key="fake-key-not-real",
        model_name="google/gemini-2.5-flash-image",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    refiner.refine(make_request())

    assert captured["auth"] == "Bearer fake-key-not-real"
