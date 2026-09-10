"""Unit tests for OpenAIVisionDigitizer. No live OpenAI API calls are ever
made here -- the SDK client's `responses.parse` is replaced with a fake
that returns pre-scripted responses, exercising only this project's own
parsing, validation, and retry logic."""
import httpx2
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.openai_vision_digitizer import OpenAIVisionDigitizer, _DigitizationResponse
from app.services.ai.types import DetectedProduct


class _FakeParsedResponse:
    def __init__(self, items: list[DetectedProduct], status: str = "completed") -> None:
        self.status = status
        self.output_parsed = _DigitizationResponse(items=items) if items is not None else None


class _FakeResponses:
    """Replaces `client.responses`: returns each entry in `outcomes` in
    order, or raises it if it's an Exception instance."""

    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes: list) -> None:
        self.responses = _FakeResponses(outcomes)


def _make_digitizer(outcomes: list, max_attempts: int = 3) -> OpenAIVisionDigitizer:
    digitizer = OpenAIVisionDigitizer(
        api_key="fake-key-not-real", max_attempts=max_attempts, retry_backoff_seconds=0
    )
    digitizer._client = _FakeClient(outcomes)  # bypass the real SDK client
    return digitizer


def _api_error(cls, code: str | None = None, status_code: int = 400, type_: str = "api_error"):
    """Build a real OpenAI SDK exception instance the way the SDK itself
    would, using a minimal fake httpx response. `body` is the *inner*
    error object (APIError.__init__ reads `code`/`param`/`type` directly
    off it) -- not the raw `{"error": {...}}` HTTP response envelope."""
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    body = {"message": "err", "code": code, "type": type_}
    response = httpx2.Response(status_code, request=request, json={"error": body})
    return cls(message="err", response=response, body=body)


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
    digitizer = _make_digitizer([_FakeParsedResponse([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert results[0].name_en == "Almonds"
    assert results[0].name_ar == "لوز"


def test_multiple_items_are_parsed():
    second = ONE_ITEM.model_copy(update={"name_en": "Coffee", "bbox": [0, 0, 100, 100]})
    digitizer = _make_digitizer([_FakeParsedResponse([ONE_ITEM, second])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert [item.name_en for item in results] == ["Almonds", "Coffee"]


def test_bulk_tray_item_response():
    tray_item = ONE_ITEM.model_copy(update={"presentation": "bulk_tray", "identification_basis": "visual"})
    digitizer = _make_digitizer([_FakeParsedResponse([tray_item])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert results[0].presentation == "bulk_tray"


def test_zero_item_response_is_valid():
    digitizer = _make_digitizer([_FakeParsedResponse([])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert results == []


def test_one_request_is_made_per_call():
    digitizer = _make_digitizer([_FakeParsedResponse([ONE_ITEM])])

    digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 1


def test_request_specifies_model_instructions_schema_and_output_cap():
    digitizer = _make_digitizer([_FakeParsedResponse([ONE_ITEM])])

    digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    call = digitizer._client.responses.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["text_format"] is _DigitizationResponse
    assert isinstance(call["max_output_tokens"], int) and call["max_output_tokens"] > 0
    assert "instructions" in call and len(call["instructions"]) > 0


# --- Malformed / invalid responses -----------------------------------------


def test_missing_output_parsed_raises_invalid_response_error():
    digitizer = _make_digitizer([_FakeParsedResponse(None)])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_incomplete_status_raises_invalid_response_error():
    digitizer = _make_digitizer([_FakeParsedResponse([ONE_ITEM], status="incomplete")])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_schema_valid_but_business_invalid_bbox_raises_invalid_response_error():
    """A response can satisfy OpenAI's strict JSON schema (correct field
    shapes) while still failing this project's own cross-field business
    rule (ymin < ymax) -- the schema alone cannot express that."""
    from pydantic import ValidationError

    digitizer = _make_digitizer([ValidationError.from_exception_data("DetectedProduct", [])])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


# --- Retry / failure behavior -----------------------------------------------


def test_transient_server_error_is_retried_then_succeeds():
    server_error = _api_error(InternalServerError, status_code=500)
    digitizer = _make_digitizer([server_error, _FakeParsedResponse([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.responses.calls) == 2


def test_server_error_exhausts_retries_and_raises_service_unavailable():
    server_error = _api_error(InternalServerError, status_code=500)
    digitizer = _make_digitizer([server_error, server_error, server_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 3


def test_rate_limit_error_is_retried_then_succeeds():
    rate_limit_error = _api_error(RateLimitError, code="rate_limit_exceeded", status_code=429)
    digitizer = _make_digitizer([rate_limit_error, _FakeParsedResponse([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.responses.calls) == 2


def test_quota_exhausted_error_exhausts_retries_with_a_clear_message():
    quota_error = _api_error(RateLimitError, code="insufficient_quota", status_code=429)
    digitizer = _make_digitizer([quota_error, quota_error, quota_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 3
    assert "quota" in str(exc_info.value).lower()


def test_real_world_credit_balance_exhausted_error_names_quota_not_generic_rate_limit():
    """Regression test using the EXACT error shape observed from a real
    account with no credits (captured during this project's one permitted
    manual validation call): `type: "insufficient_quota"` but
    `code: "credit_balance_exhausted"` -- not `code: "insufficient_quota"`
    as OpenAI's own older documented examples show. A naive check of only
    `code == "insufficient_quota"` misses this and would wrongly tell the
    user to "wait a while before retrying", which cannot help an empty
    balance."""
    real_shape_error = _api_error(
        RateLimitError, code="credit_balance_exhausted", type_="insufficient_quota", status_code=429
    )
    digitizer = _make_digitizer([real_shape_error, real_shape_error, real_shape_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    message = str(exc_info.value).lower()
    assert "quota" in message or "billing" in message
    assert "wait a while" not in message


def test_plain_rate_limit_exhausted_names_rate_limit_not_quota():
    rate_limit_error = _api_error(RateLimitError, code="rate_limit_exceeded", status_code=429)
    digitizer = _make_digitizer([rate_limit_error, rate_limit_error, rate_limit_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert "rate limit" in str(exc_info.value).lower()


def test_authentication_error_is_not_retried():
    auth_error = _api_error(AuthenticationError, status_code=401)
    digitizer = _make_digitizer([auth_error, _FakeParsedResponse([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 1  # never attempted the second, scripted response


def test_bad_request_error_is_not_retried():
    bad_request = _api_error(BadRequestError, status_code=400)
    digitizer = _make_digitizer([bad_request, _FakeParsedResponse([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 1


def test_not_found_error_is_not_retried():
    """Covers an invalid/unknown configured model name."""
    not_found = _api_error(NotFoundError, status_code=404)
    digitizer = _make_digitizer([not_found, _FakeParsedResponse([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 1


def test_permission_denied_error_is_not_retried():
    denied = _api_error(PermissionDeniedError, status_code=403)
    digitizer = _make_digitizer([denied, _FakeParsedResponse([ONE_ITEM])])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.responses.calls) == 1


def test_timeout_error_is_retried_then_succeeds():
    timeout_error = APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))
    digitizer = _make_digitizer([timeout_error, _FakeParsedResponse([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.responses.calls) == 2


def test_connection_error_is_retried_then_succeeds():
    connection_error = APIConnectionError(request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))
    digitizer = _make_digitizer([connection_error, _FakeParsedResponse([ONE_ITEM])])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.responses.calls) == 2


def test_error_messages_never_contain_the_api_key():
    server_error = _api_error(InternalServerError, status_code=500)
    digitizer = OpenAIVisionDigitizer(
        api_key="THIS-IS-THE-SECRET-KEY", max_attempts=1, retry_backoff_seconds=0
    )
    digitizer._client = _FakeClient([server_error])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert "THIS-IS-THE-SECRET-KEY" not in str(exc_info.value)
