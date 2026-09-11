"""Unit tests for OpenRouterVisionDigitizer. No live OpenRouter API calls
are ever made here -- the SDK client's `beta.chat.completions.parse` is
replaced with a fake that returns pre-scripted responses, exercising only
this project's own parsing, validation, and retry logic."""
import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.openrouter_vision_digitizer import (
    OpenRouterVisionDigitizer,
    _DigitizationResponse,
)
from app.services.ai.types import DetectedProduct


class _FakeMessage:
    def __init__(self, parsed) -> None:
        self.parsed = parsed


class _FakeChoice:
    def __init__(self, parsed) -> None:
        self.finish_reason = "stop"
        self.message = _FakeMessage(parsed)


class _FakeCompletion:
    def __init__(self, items: list[DetectedProduct] | None) -> None:
        parsed = _DigitizationResponse(items=items) if items is not None else None
        self.choices = [_FakeChoice(parsed)]


class _FakeCompletionsAPI:
    """Replaces `client.beta.chat.completions`: returns each entry in
    `outcomes` in order, or raises it if it's an Exception instance."""

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


def _make_digitizer(outcomes: list, max_attempts: int = 3) -> OpenRouterVisionDigitizer:
    digitizer = OpenRouterVisionDigitizer(
        api_key="fake-key-not-real", max_attempts=max_attempts, retry_backoff_seconds=0
    )
    digitizer._client = _FakeClient(outcomes)  # bypass the real SDK client
    return digitizer


def _api_status_error(status_code: int, code: str | None = None, type_: str = "api_error"):
    """Build a real OpenAI SDK exception the way the SDK itself would,
    using a minimal fake httpx response."""
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    body = {"message": "err", "code": code, "type": type_}
    response = httpx.Response(status_code, request=request, json={"error": body})
    return APIStatusError(message="err", response=response, body=body)


ONE_ITEM = DetectedProduct(
    name_en="Almonds",
    name_ar="لوز",
    category="Nuts",
    presentation="packaged",
    bbox=[100, 100, 500, 500],
    confidence=0.9,
    visible_text="ALMONDS 500G",
    identification_basis="visual_and_text",
    notes=None,
)


# --- Valid responses ---------------------------------------------------


def test_valid_single_item_response_is_parsed():
    digitizer = _make_digitizer([_FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert results[0].name_en == "Almonds"
    assert results[0].name_ar == "لوز"


def test_multiple_items_are_parsed():
    second = ONE_ITEM.model_copy(update={"name_en": "Coffee", "bbox": [0, 0, 100, 100]})
    digitizer = _make_digitizer([_FakeCompletion([ONE_ITEM, second])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert [item.name_en for item in results] == ["Almonds", "Coffee"]


def test_bulk_tray_item_response():
    tray_item = ONE_ITEM.model_copy(update={"presentation": "bulk_tray", "identification_basis": "visual"})
    digitizer = _make_digitizer([_FakeCompletion([tray_item])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert results[0].presentation == "bulk_tray"


def test_zero_item_response_is_valid():
    digitizer = _make_digitizer([_FakeCompletion([])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert results == []


def test_one_request_is_made_per_call():
    digitizer = _make_digitizer([_FakeCompletion([ONE_ITEM])])

    digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.beta.chat.completions.calls) == 1


def test_request_specifies_model_schema_output_cap_and_disables_reasoning():
    digitizer = _make_digitizer([_FakeCompletion([ONE_ITEM])])

    digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    call = digitizer._client.beta.chat.completions.calls[0]
    assert call["model"] == "google/gemini-2.5-flash-lite"
    assert call["response_format"] is _DigitizationResponse
    assert isinstance(call["max_tokens"], int) and call["max_tokens"] > 0
    assert call["extra_body"]["reasoning"]["effort"] == "none"


# --- Malformed / invalid responses -----------------------------------------


def test_missing_output_parsed_raises_invalid_response_error():
    digitizer = _make_digitizer([_FakeCompletion(None)])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_no_choices_raises_invalid_response_error():
    completion = _FakeCompletion([ONE_ITEM])
    completion.choices = []
    digitizer = _make_digitizer([completion])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_schema_valid_but_business_invalid_bbox_raises_invalid_response_error():
    """A response can satisfy the strict JSON schema (correct field
    shapes) while still failing this project's own cross-field business
    rule (ymin < ymax) -- the schema alone cannot express that."""
    from pydantic import ValidationError

    digitizer = _make_digitizer([ValidationError.from_exception_data("DetectedProduct", [])])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


# --- Retry / failure behavior -----------------------------------------------


def test_transient_server_error_is_retried_then_succeeds():
    server_error = _api_status_error(500)
    digitizer = _make_digitizer([server_error, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_provider_down_502_is_retried_then_succeeds():
    provider_down = _api_status_error(502, type_="provider_unavailable")
    digitizer = _make_digitizer([provider_down, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_provider_overloaded_503_is_retried_then_succeeds():
    overloaded = _api_status_error(503, type_="provider_overloaded")
    digitizer = _make_digitizer([overloaded, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_timeout_408_is_retried_then_succeeds():
    timeout_status = _api_status_error(408, type_="timeout")
    digitizer = _make_digitizer([timeout_status, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_server_error_exhausts_retries_and_raises_service_unavailable():
    server_error = _api_status_error(500)
    digitizer = _make_digitizer([server_error, server_error, server_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.beta.chat.completions.calls) == 3


def test_rate_limit_429_is_retried_then_succeeds():
    rate_limit = _api_status_error(429, type_="rate_limit_exceeded")
    digitizer = _make_digitizer([rate_limit, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_rate_limit_exhausted_names_rate_limit():
    rate_limit = _api_status_error(429, type_="rate_limit_exceeded")
    digitizer = _make_digitizer([rate_limit, rate_limit, rate_limit], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert "rate limit" in str(exc_info.value).lower()


def test_insufficient_credits_402_is_not_retried_and_names_credits():
    payment_required = _api_status_error(402, type_="payment_required")
    digitizer = _make_digitizer([payment_required, _FakeCompletion([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.beta.chat.completions.calls) == 1  # never attempted the second, scripted response
    assert "credit" in str(exc_info.value).lower()


def test_authentication_error_401_is_not_retried():
    auth_error = _api_status_error(401, type_="authentication")
    digitizer = _make_digitizer([auth_error, _FakeCompletion([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.beta.chat.completions.calls) == 1


def test_bad_request_400_is_not_retried():
    bad_request = _api_status_error(400, type_="invalid_request")
    digitizer = _make_digitizer([bad_request, _FakeCompletion([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.beta.chat.completions.calls) == 1


def test_permission_denied_403_is_not_retried():
    denied = _api_status_error(403, type_="permission_denied")
    digitizer = _make_digitizer([denied, _FakeCompletion([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.beta.chat.completions.calls) == 1


def test_timeout_exception_is_retried_then_succeeds():
    timeout_error = APITimeoutError(request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))
    digitizer = _make_digitizer([timeout_error, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_connection_error_is_retried_then_succeeds():
    connection_error = APIConnectionError(
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )
    digitizer = _make_digitizer([connection_error, _FakeCompletion([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.beta.chat.completions.calls) == 2


def test_error_messages_never_contain_the_api_key():
    server_error = _api_status_error(500)
    digitizer = OpenRouterVisionDigitizer(
        api_key="THIS-IS-THE-SECRET-KEY", max_attempts=1, retry_backoff_seconds=0
    )
    digitizer._client = _FakeClient([server_error])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert "THIS-IS-THE-SECRET-KEY" not in str(exc_info.value)
