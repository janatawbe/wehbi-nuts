import json
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.types import DetectedProduct

# Verified live against the installed google-genai SDK during the
# proof-of-concept (do not assume a model name without checking -- an
# earlier guess, "gemini-1.5-flash", is no longer offered to new users at
# all, and even "gemini-2.5-flash" returned a 404 telling callers to move
# to "gemini-3.6-flash"). Confirmed available via client.models.get() with
# image input + generateContent support.
DEFAULT_MODEL_NAME = "gemini-3.6-flash"

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5

SYSTEM_INSTRUCTION = """\
You are analyzing a photo for Wehbi Nuts, a nuts / coffee / sweets / \
snacks / dried-food and related roastery-shop inventory digitization \
system. The output will become product DRAFTS for an e-commerce catalog, \
so identify SELLABLE INVENTORY UNITS -- complete physical items a shop \
would sell as one unit -- not every visually distinct object in the \
photo.

Definition of one sellable unit, by physical presentation:
- Packaged product (bag/box/pouch/wrapped package): the WHOLE package is \
one item. Its label, logo, or printed panel is NOT a separate item.
- Jar or other container: the WHOLE jar/container is one item. Its lid, \
cap, sticker, or handwritten label is NOT a separate item.
- Bottle: the WHOLE bottle (body + neck + cap) is one item.
- Bulk product displayed in a tray/bin/container: the ENTIRE tray/bin of \
that product is one item. Individual nuts/snacks/pieces inside it are \
NOT separate items.
- Loose bulk product filling most/all of the photo with no visible \
packaging or container: return ONE item for the whole pile, not one \
item per nut/seed/bean/piece.
- A shelf/display with multiple different products: return each \
distinguishable complete sellable unit as its own item.
- Multiple separately visible physical units of the same product (e.g. \
two identical bags side by side): each physically separate unit may be \
returned as its own item.

Ignore entirely -- do not return any of these as items: shelves, shelf \
dividers, shelf edges, background, price tags that are not themselves a \
product, logos as separate objects, labels as separate objects, \
stickers, caps, decorations, individual contents visible inside a \
package, individual pieces inside a bulk tray.

Product identification:
Many Wehbi Nuts products are sold loose/bulk with no barcode, no visible \
product name, no packaging, and no readable text at all. You may \
visually infer the likely product (from color, shape, texture) when \
there is no text to read. However:
- Never present a visually-inferred guess as if it had been read from \
text.
- Set "identification_basis" accurately: "visual" if inferred purely \
from appearance, "text" if read from visible printed/handwritten text, \
"visual_and_text" if both contributed.
- If not confident, give a low "confidence" score rather than inventing \
a confident-sounding identity. A generic category-level name (e.g. \
"Mixed Nuts") is fine when a more specific one is not visually \
justified.
- Put any actually visible/readable text (brand, product name, weight, \
etc.) in "visible_text", verbatim, in whatever language it is written. \
Set it to null if no legible text is visible on that item.
- "name_en" and "name_ar" are the product name in English and Arabic \
regardless of what script the visible text (if any) uses.

Bounding boxes:
Return "bbox" as [ymin, xmin, ymax, xmax], each an integer from 0 to \
1000, normalized to the full image regardless of its actual pixel \
dimensions (0,0 is the top-left corner, 1000,1000 is the bottom-right \
corner). The box must enclose the COMPLETE physical unit (e.g. the whole \
jar, not just its sticker) -- do not shrink it to just a label, logo, or \
visible content when the complete object is larger than that.

Only return items that are genuinely sellable inventory units by the \
definitions above. If the image contains no sellable product, return an \
empty items list.
"""

USER_PROMPT = "Analyze this shop photo and return the sellable inventory units as instructed."


class _DigitizationResponse(BaseModel):
    """Wrapper object requested from Gemini's structured-output mode --
    proven in the proof-of-concept to work with `response_schema` even
    though `DetectedProduct` carries a cross-field bbox validator (Gemini's
    schema builder only inspects field types, not validator functions)."""

    items: list[DetectedProduct]


class GeminiVisionDigitizer:
    """AIProductAnalyzer implementation backed by the Gemini API.

    One request per image (never per detected product -- see README/
    project instructions on free-tier usage). Retries a transient server
    error, or a 429 rate-limit/quota error, up to `max_attempts` times with
    a short backoff; any other client error (bad request, invalid key,
    unknown model, etc.) is not retried, since it will not resolve itself.
    The raw model response is always re-validated locally with Pydantic
    before being trusted -- "structured output" mode is a strong hint to
    the model, not a guarantee.

    Root-caused in production (see README): the Gemini free tier enforces
    a low per-model request quota (as observed, 20 requests/day for
    gemini-3.6-flash) and responds with HTTP 429, which the SDK classifies
    as a `ClientError` -- the same class used for a genuinely bad request.
    Treating every `ClientError` as non-retryable meant a rate-limited
    image failed immediately (no retry at all) with a generic "digitization
    failed" message that gave no indication *why*. 429 is now retried like
    a server error, and if retries are exhausted, the message explicitly
    says the free-tier rate limit was hit rather than a generic failure.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_MODEL_NAME,
        max_attempts: int = _MAX_ATTEMPTS,
        retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> list[DetectedProduct]:
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        USER_PROMPT,
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=_DigitizationResponse,
                        temperature=0.2,
                    ),
                )
            except genai_errors.ServerError as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    time.sleep(self._retry_backoff_seconds * attempt)
                    continue
                raise AIServiceUnavailableError(
                    f"Gemini was unavailable after {attempt} attempts."
                ) from exc
            except genai_errors.ClientError as exc:
                if exc.code == 429:
                    # Rate limit / quota exceeded -- transient in principle
                    # (the API itself suggests a retry delay), so retried
                    # the same as a server error rather than failing
                    # instantly with no indication of the real cause.
                    last_error = exc
                    if attempt < self._max_attempts:
                        time.sleep(self._retry_backoff_seconds * attempt)
                        continue
                    raise AIServiceUnavailableError(
                        "Gemini's free-tier rate limit was exceeded for this image "
                        f"after {attempt} attempts. Wait a while before retrying, or "
                        "process fewer images at once."
                    ) from exc
                # Any other client error (bad request, invalid key, unknown
                # model, etc.) will not resolve itself -- never retried, and
                # never include the raw exception (may echo request
                # details) in what bubbles up to the API layer.
                raise AIServiceUnavailableError(
                    "Gemini rejected the request (client error)."
                ) from exc
            except Exception as exc:  # noqa: BLE001 -- network/SDK errors, not retried
                raise AIServiceUnavailableError("Could not reach Gemini.") from exc

            return _parse_and_validate(response.text)

        # Unreachable in practice (the loop above always returns or raises),
        # but keeps type-checkers happy and fails safely if it ever isn't.
        raise AIServiceUnavailableError(f"Gemini call failed: {last_error}")


def _parse_and_validate(raw_text: str | None) -> list[DetectedProduct]:
    if not raw_text:
        raise AIInvalidResponseError("Gemini returned an empty response.")

    try:
        raw_json = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AIInvalidResponseError("Gemini's response was not valid JSON.") from exc

    try:
        return _DigitizationResponse.model_validate(raw_json).items
    except ValidationError as exc:
        raise AIInvalidResponseError(
            "Gemini's response did not match the expected item schema."
        ) from exc
