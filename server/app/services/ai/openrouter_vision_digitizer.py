import base64
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    OpenAI,
    OpenAIError,
)
from pydantic import BaseModel, ValidationError

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.types import DetectedProduct

# OpenRouter is a gateway in front of many providers' models, reached
# through the OpenAI-compatible Chat Completions endpoint (the older,
# more universally-supported API shape -- not OpenAI's newer, OpenAI-
# hosted-specific Responses API, which OpenRouter does not implement).
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Verified live via `GET /api/v1/models` (a free, unbilled metadata
# endpoint) before writing this: an established Google model already
# proven, in earlier iterations of this exact project, to handle this
# task well (vision, structured output, English/Arabic bilingual naming,
# and the "one tray vs. many pieces" business judgment) -- not a tiny or
# obscure model chosen purely for being the lowest number on a price
# list. That listing confirmed:
#   - `structured_outputs` in `supported_parameters` (strict JSON schema
#     support, not just a generic "give me JSON" instruction).
#   - image in `input_modalities`.
#   - `reasoning.mandatory: false`, meaning reasoning (a real, billed
#     cost driver -- see `_EXTRA_BODY` below) can be fully turned off,
#     not merely hidden from the response.
#   - Pricing at verification time: $0.10 / $0.40 per million input/
#     output tokens (plus a small flat per-image charge).
# Cheaper models existed on the same listing (several 3-4B-parameter open
# models around $0.03-0.05/M, and OpenRouter's ":free" tier at $0), but
# were judged too small/unproven for reliable bilingual product
# identification and nuanced business-rule judgment to be "suitable" at
# any price -- and free-tier models on OpenRouter carry materially
# stricter rate limits, a real risk for a business pipeline (see the
# rate-limit incident documented in this project's README). OpenRouter's
# "auto"/"auto-beta" automatic routing was deliberately not used, since
# it could silently route to a more expensive model.
DEFAULT_MODEL_NAME = "google/gemini-2.5-flash-lite"

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5
# Generous enough for a busy multi-item shelf (~15-20 items) without
# leaving cost unbounded on a pathological response.
_MAX_OUTPUT_TOKENS = 2000
# OpenRouter's own extension (not a standard OpenAI field, so it must go
# through `extra_body`) for fully disabling reasoning-token generation --
# "effort": "none" stops the model from spending (billed) tokens on
# hidden reasoning at all, which merely excluding it from the response
# would not: https://openrouter.ai/docs/use-cases/reasoning-tokens
_EXTRA_BODY = {"reasoning": {"effort": "none"}}

# Status codes retried the same way a network-level failure is: OpenRouter
# documents 429 as rate-limited, 502/503 as the model/provider being
# temporarily down or overloaded, and 408 as a request timeout -- all
# plausibly transient. 402 (insufficient credits) and every other 4xx are
# not retried, since none of them resolve by trying again quickly.
_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

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


class OpenRouterVisionDigitizer:
    """AIProductAnalyzer implementation backed by OpenRouter, a gateway
    that proxies many providers' vision models behind one OpenAI-
    compatible API. Uses `client.beta.chat.completions.parse` with a
    Pydantic `response_format` for native structured-output support
    (never parses free-form prose). One request per image (never per
    detected product).

    The parsed result is still independently re-validated with Pydantic
    (see `_parse_and_validate`) rather than trusted as-is: strict JSON
    schema mode guarantees field *shape*, not this project's own
    cross-field business rules (e.g. bbox ymin < ymax), which are plain
    Python validators no schema can express.

    Retries a rate-limit (`429`), a request timeout (`408`), or a
    transient provider-side error (`5xx`, including OpenRouter's own
    502/503 for a down/overloaded model) up to `max_attempts` times with a
    short backoff. Insufficient credits (`402`, OpenRouter-specific) and
    every other client error (bad request, invalid key, unknown model,
    permission/content-policy rejection) are never retried, since none of
    them resolve by trying again quickly.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_MODEL_NAME,
        max_attempts: int = _MAX_ATTEMPTS,
        retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)
        self._model_name = model_name
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> list[DetectedProduct]:
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                completion = self._client.beta.chat.completions.parse(
                    model=self._model_name,
                    messages=[
                        {"role": "system", "content": INSTRUCTIONS},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": USER_PROMPT},
                                # "auto" (not "low"): a fixed low-resolution
                                # pass is cheaper but would materially hurt
                                # bounding-box precision and visible_text
                                # reading, which this pipeline depends on.
                                {"type": "image_url", "image_url": {"url": data_url, "detail": "auto"}},
                            ],
                        },
                    ],
                    response_format=_DigitizationResponse,
                    max_tokens=_MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                    extra_body=_EXTRA_BODY,
                )
            except (ValidationError, LengthFinishReasonError, ContentFilterFinishReasonError) as exc:
                # A response that matches the strict JSON schema (field
                # *shape*) can still fail this project's own cross-field
                # business rules (e.g. bbox ymin < ymax), which the schema
                # itself cannot express -- the SDK raises ValidationError
                # synchronously from inside `.parse()` while building the
                # Pydantic object. A response cut off by the output-token
                # cap (LengthFinishReasonError) or blocked by content
                # moderation (ContentFilterFinishReasonError) is the same
                # kind of problem: a complete, well-formed answer just
                # wasn't produced. None of these are retried -- retrying
                # the identical request is unlikely to fix a content
                # problem the same way it can fix a transient one.
                raise AIInvalidResponseError(
                    "OpenRouter's response did not match the expected item schema."
                ) from exc
            except (APIConnectionError, APITimeoutError) as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    time.sleep(self._retry_backoff_seconds * attempt)
                    continue
                raise AIServiceUnavailableError(
                    f"OpenRouter was unavailable after {attempt} attempts."
                ) from exc
            except APIStatusError as exc:
                if exc.status_code == 402:
                    # Not retried: an empty credit balance cannot be fixed
                    # by trying again, quickly or otherwise.
                    raise AIServiceUnavailableError(
                        "OpenRouter reported insufficient credits. Check your account balance."
                    ) from exc
                if exc.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = exc
                    if attempt < self._max_attempts:
                        time.sleep(self._retry_backoff_seconds * attempt)
                        continue
                    if exc.status_code == 429:
                        raise AIServiceUnavailableError(
                            f"OpenRouter's rate limit was exceeded after {attempt} attempts. "
                            "Wait a while before retrying, or process fewer images at once."
                        ) from exc
                    raise AIServiceUnavailableError(
                        f"OpenRouter was unavailable after {attempt} attempts."
                    ) from exc
                # Any other client error (bad request, invalid key, unknown
                # model, content-policy rejection) will not resolve itself
                # -- never retried, and never include the raw exception
                # (may echo request details) in what bubbles up.
                raise AIServiceUnavailableError(
                    "OpenRouter rejected the request (client error)."
                ) from exc
            except OpenAIError as exc:  # noqa: BLE001 -- any other SDK error, not retried
                raise AIServiceUnavailableError("Could not reach OpenRouter.") from exc
            except Exception as exc:  # noqa: BLE001 -- network/unexpected errors, not retried
                raise AIServiceUnavailableError("Could not reach OpenRouter.") from exc

            return _parse_and_validate(completion)

        # Unreachable in practice (the loop above always returns or raises),
        # but keeps type-checkers happy and fails safely if it ever isn't.
        raise AIServiceUnavailableError(f"OpenRouter call failed: {last_error}")


def _parse_and_validate(completion: object) -> list[DetectedProduct]:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise AIInvalidResponseError("OpenRouter returned no response choices.")

    output_parsed = getattr(choices[0].message, "parsed", None)
    if output_parsed is None:
        raise AIInvalidResponseError("OpenRouter's response did not match the expected item schema.")

    try:
        # output_parsed is already a `_DigitizationResponse` instance built
        # by the SDK; re-validating from its own data re-runs this
        # project's cross-field validators (e.g. bbox ymin < ymax) rather
        # than trusting the SDK's parse succeeded on those too.
        return _DigitizationResponse.model_validate(output_parsed.model_dump()).items
    except ValidationError as exc:
        raise AIInvalidResponseError(
            "OpenRouter's response did not match the expected item schema."
        ) from exc
