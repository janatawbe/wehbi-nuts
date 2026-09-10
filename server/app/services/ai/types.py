from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

# --- Structured detection result -------------------------------------------
#
# bbox coordinate convention: [ymin, xmin, ymax, xmax], each an integer in
# [0, 1000], normalized to the full source image regardless of its actual
# pixel dimensions (0,0 = top-left corner, 1000,1000 = bottom-right corner).
# This is the convention validated in the Gemini proof-of-concept and is
# provider-agnostic by construction -- any future AIProductAnalyzer
# implementation must normalize its own output to this same range.

PresentationValue = Literal["packaged", "jar", "bottle", "bulk_tray", "bulk_loose", "other"]
IdentificationBasisValue = Literal["visual", "text", "visual_and_text"]


class DetectedProduct(BaseModel):
    """One sellable inventory unit detected in a source image by an
    AIProductAnalyzer. This is a draft, never a guaranteed truth -- see
    `identification_basis` and `confidence`."""

    name_en: str
    name_ar: str
    category: str
    presentation: PresentationValue
    bbox: list[int] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)
    visible_text: str | None = None
    identification_basis: IdentificationBasisValue
    notes: str | None = None

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, value: list[int]) -> list[int]:
        for coordinate in value:
            if not (0 <= coordinate <= 1000):
                raise ValueError(f"bbox coordinate {coordinate} outside documented [0, 1000] range")
        ymin, xmin, ymax, xmax = value
        if ymin >= ymax or xmin >= xmax:
            raise ValueError(f"degenerate bbox {value}: min must be strictly less than max")
        return value


class AIProductAnalyzer(Protocol):
    """Interface every AI vision product analyzer must implement.

    Keeping this interface narrow (image bytes in, validated detections
    out) is what lets the analyzer be swapped or supplemented later (e.g.
    an OpenAI-based implementation) without touching the processing
    pipeline, the API, or the database layer.
    """

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> list[DetectedProduct]: ...
