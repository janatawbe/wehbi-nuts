"""Unit tests for AIDemoCatalogImageGenerator (OpenRouter Images API,
TEXT-TO-IMAGE mode for demo products with no source photo). NO real
network call is EVER made here -- every test intercepts the request via
httpx.MockTransport, never a live httpx.Client."""
import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.services.ai.demo_catalog_image_generator import (
    IMAGES_ENDPOINT,
    AIDemoCatalogImageGenerator,
    AIDemoImageGenerationError,
)
from app.services.ai.demo_catalog_image_prompt import DemoProductImageContext


def make_valid_response_b64(width: int = 512, height: int = 512) -> str:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (240, 240, 240)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def make_generator(handler, model_name: str = "google/gemini-2.5-flash-image") -> AIDemoCatalogImageGenerator:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return AIDemoCatalogImageGenerator(api_key="fake-key-not-real", model_name=model_name, http_client=client)


def make_context(**overrides) -> DemoProductImageContext:
    defaults = dict(
        name_en="Lebanese Coffee",
        category="Coffee",
        selling_mode="unit",
        description_en="Traditional Lebanese coffee, finely ground and roasted with cardamom.",
    )
    defaults.update(overrides)
    return DemoProductImageContext(**defaults)


def success_handler(captured_requests: list):
    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [{"b64_json": make_valid_response_b64(), "media_type": "image/png"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 1290, "total_tokens": 1340, "cost": 0.04},
            },
        )

    return handler


# --- Request construction --------------------------------------------------


def test_payload_uses_the_configured_model_name():
    generator = make_generator(success_handler([]), model_name="google/gemini-2.5-flash-image")
    payload = generator.build_request_payload(make_context())
    assert payload["model"] == "google/gemini-2.5-flash-image"


def test_payload_has_no_input_references_key():
    """This is pure text-to-image generation -- there is no source photo,
    so `input_references` must never be sent at all (distinct from
    AIProductImageRefiner, which always includes it)."""
    generator = make_generator(success_handler([]))
    payload = generator.build_request_payload(make_context())
    assert "input_references" not in payload


def test_payload_requests_square_aspect_ratio():
    generator = make_generator(success_handler([]))
    payload = generator.build_request_payload(make_context())
    assert payload["aspect_ratio"] == "1:1"


def test_prompt_includes_product_metadata():
    generator = make_generator(success_handler([]))
    payload = generator.build_request_payload(
        make_context(name_en="Roasted Pistachios", category="Nuts", selling_mode="weight", description_en=None)
    )
    prompt = payload["prompt"]
    assert "Roasted Pistachios" in prompt
    assert "Nuts" in prompt
    assert "weight" in prompt


def test_prompt_forbids_invented_packaging_and_branding():
    generator = make_generator(success_handler([]))
    payload = generator.build_request_payload(make_context())
    prompt = payload["prompt"]
    assert "invented brand name, logo" in prompt
    assert "Do not depict this product inside any packaging" in prompt


def test_prompt_never_mentions_price():
    generator = make_generator(success_handler([]))
    payload = generator.build_request_payload(make_context())
    assert "price" in payload["prompt"].lower()  # forbidding it is fine, inventing one is not
    assert "$" not in payload["prompt"]


def test_request_is_sent_to_the_dedicated_images_endpoint():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": [{"b64_json": make_valid_response_b64()}]})

    generator = AIDemoCatalogImageGenerator(
        api_key="fake-key-not-real",
        model_name="google/gemini-2.5-flash-image",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    generator.generate(make_context())

    assert captured["url"] == IMAGES_ENDPOINT


def test_request_carries_the_bearer_authorization_header():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"b64_json": make_valid_response_b64()}]})

    generator = AIDemoCatalogImageGenerator(
        api_key="fake-key-not-real",
        model_name="google/gemini-2.5-flash-image",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    generator.generate(make_context())

    assert captured["auth"] == "Bearer fake-key-not-real"


# --- Successful response handling ------------------------------------------


def test_valid_response_is_decoded_and_normalized_to_1200x1200():
    generator = make_generator(success_handler([]))
    image_bytes = generator.generate(make_context())

    out = Image.open(BytesIO(image_bytes))
    assert out.size == (1200, 1200)
    assert out.format == "JPEG"


def test_only_one_request_is_made_per_generate_call():
    calls: list = []
    generator = make_generator(success_handler(calls))

    generator.generate(make_context())

    assert len(calls) == 1


# --- Failure handling: exactly ONE attempt, never retried ------------------


def test_http_error_response_raises_without_retrying():
    calls: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={"error": {"message": "server error"}})

    generator = make_generator(handler)

    with pytest.raises(AIDemoImageGenerationError):
        generator.generate(make_context())

    assert len(calls) == 1


def test_connection_error_raises_without_retrying():
    calls: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("simulated network failure", request=request)

    generator = make_generator(handler)

    with pytest.raises(AIDemoImageGenerationError):
        generator.generate(make_context())

    assert len(calls) == 1


def test_missing_data_field_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"usage": {"cost": 0.01}})

    generator = make_generator(handler)

    with pytest.raises(AIDemoImageGenerationError):
        generator.generate(make_context())


def test_empty_data_array_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    generator = make_generator(handler)

    with pytest.raises(AIDemoImageGenerationError):
        generator.generate(make_context())


def test_malformed_base64_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": "not-valid-base64!!!"}]})

    generator = make_generator(handler)

    with pytest.raises(AIDemoImageGenerationError):
        generator.generate(make_context())


def test_valid_base64_but_not_an_image_is_rejected():
    not_an_image_b64 = base64.b64encode(b"just some random bytes, not a real image").decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": not_an_image_b64}]})

    generator = make_generator(handler)

    with pytest.raises(AIDemoImageGenerationError):
        generator.generate(make_context())


def test_error_does_not_expose_the_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    generator = AIDemoCatalogImageGenerator(
        api_key="THIS-IS-THE-SECRET-KEY",
        model_name="google/gemini-2.5-flash-image",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AIDemoImageGenerationError) as exc_info:
        generator.generate(make_context())

    assert "THIS-IS-THE-SECRET-KEY" not in str(exc_info.value)
