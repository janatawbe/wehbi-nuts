"""Unit tests for GeminiVisionDigitizer. No live Gemini API calls are ever
made here -- the SDK client is replaced with a fake that returns
pre-scripted responses, exercising only this project's own parsing,
validation, and retry logic."""
import json

import pytest
from google.genai import errors as genai_errors

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.gemini_vision_digitizer import GeminiVisionDigitizer


class _FakeResponse:
    def __init__(self, text: str | None) -> None:
        self.text = text


class _FakeModels:
    """Replaces `client.models`: returns each entry in `responses` in
    order, or raises it if it's an Exception instance."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, responses: list) -> None:
        self.models = _FakeModels(responses)


def _make_digitizer(responses: list, max_attempts: int = 3) -> GeminiVisionDigitizer:
    digitizer = GeminiVisionDigitizer(
        api_key="fake-key-not-real", max_attempts=max_attempts, retry_backoff_seconds=0
    )
    digitizer._client = _FakeClient(responses)  # bypass the real SDK client
    return digitizer


def _valid_payload(items: list[dict]) -> str:
    return json.dumps({"items": items})


ONE_ITEM = {
    "name_en": "Almonds",
    "name_ar": "لوز",
    "category": "Nuts",
    "presentation": "packaged",
    "bbox": [100, 100, 500, 500],
    "confidence": 0.9,
    "visible_text": "ALMONDS 500G",
    "identification_basis": "visual_and_text",
    "notes": None,
}


# --- Valid responses ---------------------------------------------------


def test_valid_single_item_response_is_parsed():
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([ONE_ITEM]))])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert results[0].name_en == "Almonds"
    assert results[0].name_ar == "لوز"
    assert results[0].identification_basis == "visual_and_text"


def test_multiple_items_are_parsed():
    second = {**ONE_ITEM, "name_en": "Coffee", "bbox": [0, 0, 100, 100]}
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([ONE_ITEM, second]))])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert [item.name_en for item in results] == ["Almonds", "Coffee"]


def test_bulk_tray_single_item_response():
    tray_item = {**ONE_ITEM, "presentation": "bulk_tray", "identification_basis": "visual"}
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([tray_item]))])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert results[0].presentation == "bulk_tray"


def test_zero_item_response_is_valid():
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([]))])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert results == []


def test_one_request_is_made_per_call():
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([ONE_ITEM]))])

    digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.models.calls) == 1


# --- Malformed / invalid responses -----------------------------------------


def test_non_json_response_raises_invalid_response_error():
    digitizer = _make_digitizer([_FakeResponse("not json at all")])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_empty_response_text_raises_invalid_response_error():
    digitizer = _make_digitizer([_FakeResponse(None)])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_missing_required_field_raises_invalid_response_error():
    broken_item = {k: v for k, v in ONE_ITEM.items() if k != "name_en"}
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([broken_item]))])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


@pytest.mark.parametrize(
    "bad_bbox",
    [
        [100, 100, 100, 500],  # ymin == ymax
        [100, 500, 500, 100],  # xmin > xmax
        [-1, 100, 500, 500],  # out of [0, 1000]
        [100, 100, 500, 1001],  # out of [0, 1000]
        [100, 100, 500],  # wrong length
    ],
)
def test_invalid_bbox_raises_invalid_response_error(bad_bbox):
    item = {**ONE_ITEM, "bbox": bad_bbox}
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([item]))])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


def test_invalid_presentation_value_raises_invalid_response_error():
    item = {**ONE_ITEM, "presentation": "shelf"}  # not one of the allowed values
    digitizer = _make_digitizer([_FakeResponse(_valid_payload([item]))])

    with pytest.raises(AIInvalidResponseError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")


# --- Retry / failure behavior -----------------------------------------------


def test_transient_server_error_is_retried_then_succeeds():
    server_error = genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    digitizer = _make_digitizer([server_error, _FakeResponse(_valid_payload([ONE_ITEM]))])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.models.calls) == 2


def test_server_error_exhausts_retries_and_raises_service_unavailable():
    server_error = genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    digitizer = _make_digitizer([server_error, server_error, server_error], max_attempts=3)

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.models.calls) == 3


def test_client_error_is_not_retried():
    client_error = genai_errors.ClientError(400, {"error": {"message": "bad request"}})
    digitizer = _make_digitizer([client_error, _FakeResponse(_valid_payload([ONE_ITEM]))])

    with pytest.raises(AIServiceUnavailableError):
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.models.calls) == 1  # never attempted the second, scripted response


def _rate_limit_error() -> genai_errors.ClientError:
    """A 429 shaped like Gemini's real free-tier quota response (root
    cause of a production incident: every image reliably failed instantly,
    with no retry and no useful error, because a 429 was previously
    treated exactly like a generic 4xx client error)."""
    return genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": "You exceeded your current quota, please check your plan and billing details.",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )


def test_rate_limit_error_is_retried_then_succeeds():
    digitizer = _make_digitizer([_rate_limit_error(), _FakeResponse(_valid_payload([ONE_ITEM]))])

    results = digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(results) == 1
    assert len(digitizer._client.models.calls) == 2


def test_rate_limit_error_exhausts_retries_with_a_clear_message():
    digitizer = _make_digitizer(
        [_rate_limit_error(), _rate_limit_error(), _rate_limit_error()], max_attempts=3
    )

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.models.calls) == 3
    # The whole point of this fix: the message must say *why* (rate
    # limit/free tier), not just "failed" -- this is what the frontend
    # surfaces to the user instead of a generic message.
    assert "rate limit" in str(exc_info.value).lower()


def test_non_rate_limit_client_error_is_still_not_retried():
    """A genuine bad-request/auth-style 4xx (not 429) must remain
    non-retryable -- only rate-limit/quota errors get the retry
    treatment."""
    client_error = genai_errors.ClientError(403, {"error": {"message": "permission denied"}})
    digitizer = _make_digitizer([client_error, _FakeResponse(_valid_payload([ONE_ITEM]))])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert len(digitizer._client.models.calls) == 1
    assert "rate limit" not in str(exc_info.value).lower()


def test_error_messages_never_contain_the_api_key():
    server_error = genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    digitizer = GeminiVisionDigitizer(
        api_key="THIS-IS-THE-SECRET-KEY", max_attempts=1, retry_backoff_seconds=0
    )
    digitizer._client = _FakeClient([server_error])

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        digitizer.analyze_image(b"fake-bytes", "image/jpeg")

    assert "THIS-IS-THE-SECRET-KEY" not in str(exc_info.value)
