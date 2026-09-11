"""Unit tests for OpenRouterProductEnricher. No live OpenRouter API calls
are ever made here -- the SDK client's `beta.chat.completions.parse` is
replaced with a fake that returns pre-scripted responses, exercising only
this project's own parsing, validation, and retry logic. Mirrors
test_openrouter_vision_digitizer.py's mocking style."""
import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from app.services.ai.enrichment_service import (
    OpenRouterProductEnricher,
    _EnrichmentResponse,
)
from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError


class _FakeMessage:
    def __init__(self, parsed) -> None:
        self.parsed = parsed


class _FakeChoice:
    def __init__(self, parsed) -> None:
        self.finish_reason = "stop"
        self.message = _FakeMessage(parsed)


class _FakeCompletion:
    def __init__(self, response: _EnrichmentResponse | None) -> None:
        self.choices = [_FakeChoice(response)]


class _FakeCompletionsAPI:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeBeta:
    def __init__(self, outcomes: list) -> None:
        self.chat = type("_Chat", (), {})()
        self.chat.completions = _FakeCompletionsAPI(outcomes)


class _FakeClient:
    def __init__(self, outcomes: list) -> None:
        self.beta = _FakeBeta(outcomes)


def _make_enricher(outcomes: list, max_attempts: int = 3) -> OpenRouterProductEnricher:
    enricher = OpenRouterProductEnricher(
        api_key="fake-key-not-real", max_attempts=max_attempts, retry_backoff_seconds=0
    )
    enricher._client = _FakeClient(outcomes)  # bypass the real SDK client
    return enricher


def _api_status_error(status_code: int, code: str | None = None, type_: str = "api_error"):
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    body = {"message": "err", "code": code, "type": type_}
    response = httpx.Response(status_code, request=request, json={"error": body})
    return APIStatusError(message="err", response=response, body=body)


_NO_REVIEW = {"needs_review": False, "reason": None}
_ALL_FIELDS_CLEAN = {
    "brand": _NO_REVIEW,
    "flavor_variant": _NO_REVIEW,
    "selling_mode": _NO_REVIEW,
    "package_weight": _NO_REVIEW,
    "barcode": _NO_REVIEW,
    "description_en": _NO_REVIEW,
    "description_ar": _NO_REVIEW,
    "category": _NO_REVIEW,
}


def _make_response(**overrides) -> _EnrichmentResponse:
    defaults = dict(
        brand="Wehbi Roastery",
        flavor_variant="Salted",
        selling_mode="unit",
        package_weight="0.500",
        barcode=None,
        description_en="Premium roasted almonds, lightly salted.",
        description_ar="لوز محمص فاخر، مملح قليلاً.",
        category="Nuts",
        field_review=dict(_ALL_FIELDS_CLEAN),
    )
    defaults.update(overrides)
    return _EnrichmentResponse(**defaults)


def _call_enrich(enricher: OpenRouterProductEnricher, presentation: str | None = "packaged"):
    return enricher.enrich_product(
        image_bytes=b"fake-crop-bytes",
        mime_type="image/jpeg",
        name_en="Almonds",
        name_ar="لوز",
        category_suggestion="Nuts",
        category_names=["Nuts", "Dried Fruit"],
        presentation=presentation,
    )


# --- Valid responses ---------------------------------------------------


def test_valid_response_is_parsed():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    result = _call_enrich(enricher)

    assert result.brand == "Wehbi Roastery"
    assert result.flavor_variant == "Salted"
    assert result.selling_mode == "unit"
    assert float(result.package_weight) == 0.5
    assert result.category == "Nuts"


def test_bulk_item_with_no_brand_barcode_or_package_weight_is_not_flagged_for_review():
    """A bulk/loose item genuinely has no brand, barcode, or package weight
    (it isn't packaged at all) -- that is a correct null, not uncertainty,
    and must not be marked needs_review."""
    response = _make_response(
        brand=None,
        flavor_variant=None,
        selling_mode="weight",
        package_weight=None,
        barcode=None,
        category=None,
        field_review={
            **_ALL_FIELDS_CLEAN,
            "category": {"needs_review": False, "reason": None},
        },
    )
    enricher = _make_enricher([_FakeCompletion(response)])

    result = _call_enrich(enricher, presentation="bulk_tray")

    assert result.brand is None
    assert result.flavor_variant is None
    assert result.barcode is None
    assert result.package_weight is None
    assert result.selling_mode == "weight"
    assert result.field_review["brand"].needs_review is False
    assert result.field_review["barcode"].needs_review is False
    assert result.field_review["package_weight"].needs_review is False
    assert result.field_review["flavor_variant"].needs_review is False


def test_packaged_item_can_have_package_weight_while_selling_mode_is_unit():
    """A packaged 500g bag is still sold as ONE UNIT -- package_weight and
    selling_mode="unit" coexisting is the normal, expected case."""
    response = _make_response(selling_mode="unit", package_weight="0.500")
    enricher = _make_enricher([_FakeCompletion(response)])

    result = _call_enrich(enricher, presentation="packaged")

    assert result.selling_mode == "unit"
    assert float(result.package_weight) == 0.5


def test_mixed_confidence_field_review_shape():
    response = _make_response(
        field_review={
            **_ALL_FIELDS_CLEAN,
            "package_weight": {"needs_review": True, "reason": "Printed weight is partially obscured"},
        }
    )
    enricher = _make_enricher([_FakeCompletion(response)])

    result = _call_enrich(enricher)

    assert result.field_review["package_weight"].needs_review is True
    assert "obscured" in result.field_review["package_weight"].reason
    assert result.field_review["brand"].needs_review is False


def test_one_request_is_made_per_call():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    _call_enrich(enricher)

    assert len(enricher._client.beta.chat.completions.calls) == 1


def test_request_specifies_model_schema_output_cap_and_disables_reasoning():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    _call_enrich(enricher)

    call = enricher._client.beta.chat.completions.calls[0]
    assert call["model"] == "google/gemini-2.5-flash-lite"
    assert call["response_format"] is _EnrichmentResponse
    assert isinstance(call["max_tokens"], int) and call["max_tokens"] > 0
    assert call["extra_body"]["reasoning"]["effort"] == "none"


def test_category_options_are_included_in_the_prompt():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    _call_enrich(enricher)

    call = enricher._client.beta.chat.completions.calls[0]
    user_text = call["messages"][1]["content"][0]["text"]
    assert "Nuts" in user_text
    assert "Dried Fruit" in user_text


def test_no_categories_available_is_communicated_in_the_prompt():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    enricher.enrich_product(
        image_bytes=b"fake-crop-bytes",
        mime_type="image/jpeg",
        name_en="Almonds",
        name_ar="لوز",
        category_suggestion=None,
        category_names=[],
        presentation="packaged",
    )

    call = enricher._client.beta.chat.completions.calls[0]
    user_text = call["messages"][1]["content"][0]["text"]
    assert "No categories exist yet" in user_text


def test_presentation_is_included_in_the_prompt_as_a_selling_mode_signal():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    _call_enrich(enricher, presentation="bulk_tray")

    call = enricher._client.beta.chat.completions.calls[0]
    user_text = call["messages"][1]["content"][0]["text"]
    assert "bulk_tray" in user_text


def test_missing_presentation_omits_the_presentation_line_from_the_prompt():
    enricher = _make_enricher([_FakeCompletion(_make_response())])

    _call_enrich(enricher, presentation=None)

    call = enricher._client.beta.chat.completions.calls[0]
    user_text = call["messages"][1]["content"][0]["text"]
    assert "presentation classification" not in user_text


# --- Business-rule validation -------------------------------------------


def test_package_weight_without_unit_selling_mode_is_rejected():
    with pytest.raises(ValidationError):
        _make_response(selling_mode="weight", package_weight="0.500")


def test_field_review_missing_a_key_is_rejected():
    incomplete = dict(_ALL_FIELDS_CLEAN)
    del incomplete["barcode"]
    with pytest.raises(ValidationError):
        _make_response(field_review=incomplete)


def test_field_review_with_unknown_key_is_rejected():
    with_extra = {**_ALL_FIELDS_CLEAN, "made_up_field": _NO_REVIEW}
    with pytest.raises(ValidationError):
        _make_response(field_review=with_extra)


def test_field_review_with_legacy_unit_key_is_rejected():
    """The pre-audit `unit`/`weight` keys must not silently resurface --
    field_review is a closed, exact key set."""
    legacy = {**_ALL_FIELDS_CLEAN, "unit": _NO_REVIEW}
    del legacy["selling_mode"]
    with pytest.raises(ValidationError):
        _make_response(field_review=legacy)


def test_response_has_no_price_field():
    """The AI is never asked for, and cannot return, a price -- pricing is
    out of scope for Milestone 5 and must never be AI-generated."""
    response = _make_response()
    assert not hasattr(response, "price")
    assert "price" not in _EnrichmentResponse.model_fields


def test_schema_valid_but_business_invalid_response_raises_invalid_response_error():
    enricher = _make_enricher([ValidationError.from_exception_data("_EnrichmentResponse", [])])

    with pytest.raises(AIInvalidResponseError):
        _call_enrich(enricher)


def test_missing_output_parsed_raises_invalid_response_error():
    enricher = _make_enricher([_FakeCompletion(None)])

    with pytest.raises(AIInvalidResponseError):
        _call_enrich(enricher)


def test_no_choices_raises_invalid_response_error():
    completion = _FakeCompletion(_make_response())
    completion.choices = []
    enricher = _make_enricher([completion])

    with pytest.raises(AIInvalidResponseError):
        _call_enrich(enricher)


# --- Retry / failure behavior, mirroring the digitizer's own coverage --


def test_transient_server_error_is_retried_then_succeeds():
    server_error = _api_status_error(500)
    enricher = _make_enricher([server_error, _FakeCompletion(_make_response())])

    result = _call_enrich(enricher)

    assert result.brand == "Wehbi Roastery"
    assert len(enricher._client.beta.chat.completions.calls) == 2


def test_server_error_exhausts_retries_and_raises_service_unavailable():
    server_error = _api_status_error(500)
    enricher = _make_enricher([server_error, server_error, server_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError):
        _call_enrich(enricher)

    assert len(enricher._client.beta.chat.completions.calls) == 3


def test_rate_limit_429_is_retried_then_succeeds():
    rate_limit = _api_status_error(429, type_="rate_limit_exceeded")
    enricher = _make_enricher([rate_limit, _FakeCompletion(_make_response())])

    result = _call_enrich(enricher)

    assert result.brand == "Wehbi Roastery"
    assert len(enricher._client.beta.chat.completions.calls) == 2


def test_insufficient_credits_402_is_not_retried_and_names_credits():
    payment_required = _api_status_error(402, type_="payment_required")
    enricher = _make_enricher([payment_required, _FakeCompletion(_make_response())])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        _call_enrich(enricher)

    assert len(enricher._client.beta.chat.completions.calls) == 1
    assert "credit" in str(exc_info.value).lower()


def test_bad_request_400_is_not_retried():
    bad_request = _api_status_error(400, type_="invalid_request")
    enricher = _make_enricher([bad_request, _FakeCompletion(_make_response())])

    with pytest.raises(AIServiceUnavailableError):
        _call_enrich(enricher)

    assert len(enricher._client.beta.chat.completions.calls) == 1


def test_timeout_exception_is_retried_then_succeeds():
    timeout_error = APITimeoutError(request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))
    enricher = _make_enricher([timeout_error, _FakeCompletion(_make_response())])

    result = _call_enrich(enricher)

    assert result.brand == "Wehbi Roastery"
    assert len(enricher._client.beta.chat.completions.calls) == 2


def test_connection_error_is_retried_then_succeeds():
    connection_error = APIConnectionError(
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )
    enricher = _make_enricher([connection_error, _FakeCompletion(_make_response())])

    result = _call_enrich(enricher)

    assert result.brand == "Wehbi Roastery"
    assert len(enricher._client.beta.chat.completions.calls) == 2


def test_error_messages_never_contain_the_api_key():
    server_error = _api_status_error(500)
    enricher = OpenRouterProductEnricher(
        api_key="THIS-IS-THE-SECRET-KEY", max_attempts=1, retry_backoff_seconds=0
    )
    enricher._client = _FakeClient([server_error])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        _call_enrich(enricher)

    assert "THIS-IS-THE-SECRET-KEY" not in str(exc_info.value)
