import base64
import time

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.types import DetectedProduct

# Verified live against the installed `openai` SDK and the real API before
# writing this (see README): confirmed via `client.models.list()` that this
# model exists on this account, and via public documentation that it
# supports image input and strict structured JSON output. Chosen over
# other cheap, vision-capable candidates specifically for cost:
# gpt-4o-mini is priced at $0.15 / $0.60 per million input/output tokens,
# below every other model confirmed to reliably support both vision and
# structured outputs (e.g. gpt-5.6-luna at $0.20 / $1.20/M) -- a cheaper
# option on paper existed (gpt-4.1-nano, $0.10 / $0.40/M) but its
# structured-output support is inconsistently documented, and this
# pipeline depends entirely on structured output actually working, so it
# was not worth the risk for a fractional-cent-per-image saving. gpt-4o-mini
# is also not a "reasoning" model, so it never spends tokens on hidden
# reasoning output -- a real, material cost driver observed with reasoning
# models -- keeping per-image cost small and predictable.
DEFAULT_MODEL_NAME = "gpt-4o-mini"

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5
# Generous enough for a busy multi-item shelf (~15-20 items) without
# leaving cost unbounded on a pathological response.
_MAX_OUTPUT_TOKENS = 2000

INSTRUCTIONS = """\
You digitize inventory photos for Wehbi Nuts, a nuts/coffee/sweets/snacks/\
dried-food roastery shop, into product DRAFTS for an e-commerce catalog. \
Identify SELLABLE INVENTORY UNITS -- complete physical items a shop would \
sell as one unit -- not every visually distinct object.

One sellable unit, by presentation:
- packaged (bag/box/pouch): the WHOLE package is one item; its label/logo/\
artwork is not a separate item.
- jar/other container: the WHOLE container is one item; its lid, cap, or \
sticker is not a separate item.
- bottle: the WHOLE bottle (body+neck+cap) is one item.
- bulk_tray: the ENTIRE tray/bin of one product is one item; individual \
pieces inside it are NOT separate items.
- bulk_loose: a close-up filling the frame with one loose product and no \
packaging is ONE item, not one per piece.
- Multiple distinguishable products on a shelf: one item each. Multiple \
separate physical units of the same product may each be their own item.

Ignore entirely: shelves, dividers, shelf edges, background, non-product \
price tags, logos/labels as separate objects, individual pieces inside a \
bulk tray or loose pile, decorations.

Identification: many items are loose/bulk with no visible text at all -- \
you may infer the likely product visually, but never present a visual \
guess as if it were read from text. Set identification_basis to "visual", \
"text", or "visual_and_text" accurately. Use a low confidence rather than \
inventing a confident identity; a generic category name (e.g. "Mixed \
Nuts") is fine when a specific one isn't visually justified. Put any \
actually visible/readable text in visible_text verbatim, else null.

bbox is [ymin, xmin, ymax, xmax], integers 0-1000, normalized to the full \
image (0,0 = top-left, 1000,1000 = bottom-right), enclosing the COMPLETE \
physical unit -- never shrunk to just a label or visible content.

Be concise. Return only the structured item list, no extra commentary. If \
there is no sellable product, return an empty list.
"""

USER_PROMPT = "Return the sellable inventory units in this shop photo."


class _DigitizationResponse(BaseModel):
    items: list[DetectedProduct]


class OpenAIVisionDigitizer:
    """AIProductAnalyzer implementation backed by the OpenAI Responses API.

    One request per image (never per detected product). Uses
    `client.responses.parse` with a Pydantic `text_format` for native
    structured-output support (never parses free-form prose). The parsed
    result is still independently re-validated with Pydantic (see
    `_parse_and_validate`) rather than trusted as-is: OpenAI's strict JSON
    schema mode guarantees field *shape*, not this project's own
    cross-field business rules (e.g. bbox ymin < ymax), which are plain
    Python validators the schema itself cannot express.

    Retries a rate-limit (`429`) or a transient server-side error
    (timeout, connection failure, `5xx`) up to `max_attempts` times with a
    short backoff; any other client error (bad request, invalid key,
    unknown model, permission/billing rejection other than a plain rate
    limit) is never retried, since it will not resolve itself. A
    rate-limit error is retried the same as a server error because it is
    often transient, but an exhausted *quota* cannot be fixed by retrying
    quickly -- so the attempt bound stays the same either way, and the
    final message names the real cause (quota vs. plain rate limit)
    instead of a generic one.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_MODEL_NAME,
        max_attempts: int = _MAX_ATTEMPTS,
        retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model_name = model_name
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> list[DetectedProduct]:
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.responses.parse(
                    model=self._model_name,
                    instructions=INSTRUCTIONS,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": USER_PROMPT},
                                # "auto" (not "low"): a fixed low-resolution
                                # pass is cheaper but would materially hurt
                                # bounding-box precision and visible_text
                                # reading, which this pipeline depends on.
                                {"type": "input_image", "image_url": data_url, "detail": "auto"},
                            ],
                        }
                    ],
                    text_format=_DigitizationResponse,
                    max_output_tokens=_MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                )
            except ValidationError as exc:
                # A response that matches OpenAI's strict JSON schema (field
                # *shape*) can still fail this project's own cross-field
                # business rules (e.g. bbox ymin < ymax), which the schema
                # itself cannot express -- the SDK raises this synchronously
                # from inside `.parse()` while building the Pydantic object.
                # Not retried: the model produced a complete, schema-valid,
                # but business-invalid answer, which is a content problem,
                # not a transient one.
                raise AIInvalidResponseError(
                    "OpenAI's response did not match the expected item schema."
                ) from exc
            except RateLimitError as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    time.sleep(self._retry_backoff_seconds * attempt)
                    continue
                if _is_quota_exhausted(exc):
                    raise AIServiceUnavailableError(
                        "OpenAI's quota/billing limit was exhausted after "
                        f"{attempt} attempts. Check your plan and billing details."
                    ) from exc
                raise AIServiceUnavailableError(
                    f"OpenAI's rate limit was exceeded after {attempt} attempts. "
                    "Wait a while before retrying, or process fewer images at once."
                ) from exc
            except (InternalServerError, APITimeoutError, APIConnectionError) as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    time.sleep(self._retry_backoff_seconds * attempt)
                    continue
                raise AIServiceUnavailableError(
                    f"OpenAI was unavailable after {attempt} attempts."
                ) from exc
            except (AuthenticationError, PermissionDeniedError, NotFoundError, BadRequestError) as exc:
                # Never retried: a bad request/auth/unknown-model error will
                # not fix itself, and never include the raw exception (may
                # echo request details) in what bubbles up to the API layer.
                raise AIServiceUnavailableError(
                    "OpenAI rejected the request (client error)."
                ) from exc
            except OpenAIError as exc:  # noqa: BLE001 -- any other SDK error, not retried
                raise AIServiceUnavailableError("Could not reach OpenAI.") from exc
            except Exception as exc:  # noqa: BLE001 -- network/unexpected errors, not retried
                raise AIServiceUnavailableError("Could not reach OpenAI.") from exc

            return _parse_and_validate(response)

        # Unreachable in practice (the loop above always returns or raises),
        # but keeps type-checkers happy and fails safely if it ever isn't.
        raise AIServiceUnavailableError(f"OpenAI call failed: {last_error}")


def _is_quota_exhausted(exc: RateLimitError) -> bool:
    """A 429 covers two genuinely different situations that need different
    messages: a short-lived rate limit (retrying shortly plausibly helps)
    versus a fully exhausted quota/billing balance (retrying, at any
    speed, cannot help). Verified directly against a real account with no
    credits: the exact fields used to signal this are NOT consistent --
    that response had `type: "insufficient_quota"` but
    `code: "credit_balance_exhausted"`, not `code: "insufficient_quota"`
    as OpenAI's own older documentation examples show -- so this checks
    both fields, and checks for the family of related terms rather than
    one exact string, on the assumption the exact code/type OpenAI sends
    is not perfectly stable across accounts or over time.
    """
    haystack = f"{getattr(exc, 'code', '') or ''} {getattr(exc, 'type', '') or ''}".lower()
    return any(term in haystack for term in ("insufficient_quota", "credit_balance", "billing"))


def _parse_and_validate(response: object) -> list[DetectedProduct]:
    status = getattr(response, "status", None)
    if status is not None and status != "completed":
        raise AIInvalidResponseError(f"OpenAI did not complete the request (status: {status}).")

    output_parsed = getattr(response, "output_parsed", None)
    if output_parsed is None:
        raise AIInvalidResponseError("OpenAI's response did not match the expected item schema.")

    try:
        # output_parsed is already a `_DigitizationResponse` instance built
        # by the SDK; re-validating from its own data re-runs this
        # project's cross-field validators (e.g. bbox ymin < ymax) rather
        # than trusting the SDK's parse succeeded on those too.
        return _DigitizationResponse.model_validate(output_parsed.model_dump()).items
    except ValidationError as exc:
        raise AIInvalidResponseError(
            "OpenAI's response did not match the expected item schema."
        ) from exc
