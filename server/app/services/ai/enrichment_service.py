import base64
import time
from decimal import Decimal

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    OpenAI,
    OpenAIError,
)
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.openrouter_vision_digitizer import DEFAULT_MODEL_NAME, OPENROUTER_BASE_URL
from app.services.ai.types import SellingModeValue

# Milestone 5's enrichment step: a SEPARATE AI call from Milestone 4's
# detection (OpenRouterVisionDigitizer), deliberately not a modification of
# it. It takes ONE already-detected DigitizedProduct's saved crop image
# (plus its already-known name/category guess as context) and fills in the
# fields M4 never populates. Keeping this as its own single-item call
# (rather than folding enrichment into detection, or batching many
# products into one request) is what makes single-item retry possible:
# re-enriching one row never requires re-running detection -- or
# enrichment -- on anything else in the job. Mirrors
# OpenRouterVisionDigitizer's request/retry/error-handling shape rather
# than introducing a new approach; that class and its tests are untouched.

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5
# A single item's enrichment is a much smaller output than a whole shelf's
# detections -- generous enough for two full-sentence bilingual
# descriptions plus the other fields, without leaving cost unbounded.
_MAX_OUTPUT_TOKENS = 800
_EXTRA_BODY = {"reasoning": {"effort": "none"}}
_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

_FIELD_REVIEW_KEYS = (
    "brand",
    "flavor_variant",
    "selling_mode",
    "package_weight",
    "barcode",
    "description_en",
    "description_ar",
    "category",
)

INSTRUCTIONS = """\
You enrich ONE already-identified product draft for Wehbi Nuts, a nuts/\
coffee/sweets/snacks/dried-food roastery shop, with e-commerce catalog \
fields. You are given a single cropped photo of exactly one sellable unit, \
plus its name and category guess from an earlier identification pass. Do \
not re-identify or rename the product -- only fill in the fields below \
from what is visible in the image.

brand: the manufacturer/brand name, only if actually printed or visible \
on packaging or labeling. If there is no visible packaging or brand text \
(e.g. a bulk/loose good sold from a tray or bin), leave this null -- \
never invent or guess a brand.

flavor_variant: the specific flavor, type, or variant if identifiable \
(e.g. "Salted", "Roasted", "Hazelnut", "Caramel", "Dark Chocolate", \
"Original") -- only from what is actually printed/visible or unambiguous \
from the product itself. Null if not identifiable. Never invent one.

selling_mode: how this item is SOLD to a customer -- exactly one of:
- "weight": a genuinely loose/bulk good with NO fixed package, sold by \
weight at checkout (nuts, dried fruit, seeds, or coffee beans sold from a \
tray, bin, or scoop display).
- "unit": a countable item sold as one fixed-price piece -- EVERY \
packaged, boxed, bagged, jarred, or bottled product is "unit", even if it \
has a printed net weight on its label. A packaged 500g bag is still sold \
as ONE UNIT, not by weight -- the customer buys the whole bag, not a \
chosen weight of it. Do not confuse "this item HAS a weight printed on \
it" with "this item is SOLD by weight"; those are unrelated questions. \
Only a genuinely loose/bulk good with no package at all is "weight".

package_weight: the item's printed net WEIGHT in KILOGRAMS (never a \
volume like liters/mL -- a bottle's "1L" is not a weight and must be left \
null), ONLY when it is actually visible/legible on packaging (e.g. \
"500g" -> 0.5, "1kg" -> 1, "100g" -> 0.1). Null whenever no weight is \
printed or legible -- this includes essentially all "weight" selling_mode \
items (a bulk tray has no package to print a weight on) and many "unit" \
items too (e.g. a bottle labeled only by volume, or a box with no printed \
weight). Never invent or guess a value that isn't actually legible. \
IMPORTANT: package_weight is a physical label fact, independent of \
selling_mode -- it must never be used as a reason to answer "weight" for \
selling_mode.

barcode: only if an actual barcode number is visible and legible in the \
photo. Never invent or guess one -- null otherwise. Most bulk goods, and \
many packaged products in a shelf photo, will genuinely have no visible \
barcode; that is a correct, non-uncertain null.

description_en / description_ar: two SHORT (1-2 sentence), natural, \
independently-written product descriptions suitable for an online shop \
listing -- one in English, one in Arabic. Each must read as natural, \
fluent text in its own language; neither may be a literal transliteration \
or word-for-word translation of the other, and neither may simply repeat \
visible packaging text verbatim. Never mention or imply a price.

category: choose the single best-fitting category from the numbered list \
given to you by copying its name EXACTLY, or return null if none of them \
genuinely fit this product.

field_review: for EACH of brand, flavor_variant, selling_mode, \
package_weight, barcode, description_en, description_ar, category, report \
whether a human should double check it (needs_review: true) or not \
(false), with an optional short reason. A field that is legitimately \
null/absent (no visible brand, no visible barcode, no legible package \
weight, no identifiable flavor) is NOT uncertain -- mark needs_review \
false for it. Only mark needs_review true when the value is genuinely \
ambiguous, hard to read/see, or a low-confidence guess -- including a \
selling_mode call you are not confident about.

Never invent or guess a price under any field -- no field here represents \
a price, and none should ever be interpreted as one.

Be concise. Return only the structured fields, no extra commentary.
"""

_PRESENTATION_HINTS = {
    "bulk_tray": "an entire tray/bin of loose product (no individual package)",
    "bulk_loose": "a loose/bulk product filling the frame (no individual package)",
    "packaged": "a packaged/bagged/boxed item",
    "jar": "a jar or other container",
    "bottle": "a bottle",
    "other": "presentation not clearly one of the above",
}


def _build_user_prompt(
    name_en: str | None,
    name_ar: str | None,
    category_suggestion: str | None,
    category_names: list[str],
    presentation: str | None,
) -> str:
    lines = [f"Product name (from an earlier pass): {name_en or '(unknown)'} / {name_ar or '(unknown)'}"]
    if presentation:
        hint = _PRESENTATION_HINTS.get(presentation, presentation)
        lines.append(
            f"Earlier presentation classification (from detection, unverified): "
            f"{presentation} -- {hint}. Use this as a strong signal for selling_mode, "
            "but judge from the actual photo, not this label alone."
        )
    if category_suggestion:
        lines.append(f"Earlier category guess (unverified): {category_suggestion}")
    if category_names:
        options = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(category_names))
        lines.append(f"Choose the category from this list, or null if none fit:\n{options}")
    else:
        lines.append("No categories exist yet in the catalog -- return null for category.")
    lines.append("Enrich this single product from the attached photo.")
    return "\n\n".join(lines)


class _FieldReview(BaseModel):
    needs_review: bool
    reason: str | None = None


class _EnrichmentResponse(BaseModel):
    brand: str | None = None
    flavor_variant: str | None = None
    selling_mode: SellingModeValue
    package_weight: Decimal | None = Field(default=None, ge=0)
    barcode: str | None = None
    description_en: str
    description_ar: str
    category: str | None = None
    field_review: dict[str, _FieldReview]

    @field_validator("field_review")
    @classmethod
    def _validate_field_review_keys(cls, value: dict[str, _FieldReview]) -> dict[str, _FieldReview]:
        missing = set(_FIELD_REVIEW_KEYS) - set(value)
        if missing:
            raise ValueError(f"field_review missing keys: {sorted(missing)}")
        extra = set(value) - set(_FIELD_REVIEW_KEYS)
        if extra:
            raise ValueError(f"field_review has unknown keys: {sorted(extra)}")
        return value

    @model_validator(mode="after")
    def _validate_package_weight_matches_selling_mode(self) -> "_EnrichmentResponse":
        # A genuinely loose/bulk good (selling_mode="weight") has no
        # package to print a weight on -- package_weight is only ever
        # meaningful for a "unit"-sold item, and even then only when a
        # weight was actually visible (it stays null far more often than
        # not). This is the same "field can't outrun its own precondition"
        # pattern as the old weight/unit validator, applied to the
        # corrected, orthogonal selling_mode/package_weight fields.
        if self.selling_mode != "unit" and self.package_weight is not None:
            raise ValueError('package_weight must be null unless selling_mode is "unit"')
        return self


class OpenRouterProductEnricher:
    """Milestone 5's AIProductAnalyzer-adjacent enrichment step: one
    OpenRouter request per already-detected DigitizedProduct, filling in
    the fields Milestone 4 never populates (brand, flavor_variant,
    selling_mode, package_weight, barcode, both descriptions, and a
    category chosen from the real category list).

    Deliberately a separate class from OpenRouterVisionDigitizer, not a
    mode/parameter on it -- see the module docstring above. Retry/error
    handling mirrors that class exactly.
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

    def enrich_product(
        self,
        image_bytes: bytes,
        mime_type: str,
        name_en: str | None,
        name_ar: str | None,
        category_suggestion: str | None,
        category_names: list[str],
        presentation: str | None = None,
    ) -> _EnrichmentResponse:
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        user_prompt = _build_user_prompt(name_en, name_ar, category_suggestion, category_names, presentation)
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
                                {"type": "text", "text": user_prompt},
                                {"type": "image_url", "image_url": {"url": data_url, "detail": "auto"}},
                            ],
                        },
                    ],
                    response_format=_EnrichmentResponse,
                    max_tokens=_MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                    extra_body=_EXTRA_BODY,
                )
            except (ValidationError, LengthFinishReasonError, ContentFilterFinishReasonError) as exc:
                raise AIInvalidResponseError(
                    "OpenRouter's response did not match the expected enrichment schema."
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
                            "Wait a while before retrying, or process fewer items at once."
                        ) from exc
                    raise AIServiceUnavailableError(
                        f"OpenRouter was unavailable after {attempt} attempts."
                    ) from exc
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


def _parse_and_validate(completion: object) -> _EnrichmentResponse:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise AIInvalidResponseError("OpenRouter returned no response choices.")

    output_parsed = getattr(choices[0].message, "parsed", None)
    if output_parsed is None:
        raise AIInvalidResponseError(
            "OpenRouter's response did not match the expected enrichment schema."
        )

    try:
        return _EnrichmentResponse.model_validate(output_parsed.model_dump())
    except ValidationError as exc:
        raise AIInvalidResponseError(
            "OpenRouter's response did not match the expected enrichment schema."
        ) from exc
