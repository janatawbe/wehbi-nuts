from pydantic import BaseModel

from app.schemas.digitization_job import DigitizationJobRead
from app.schemas.digitized_product import DigitizedProductRead


class DuplicateDetectionSummaryRead(BaseModel):
    """Mirrors app.services.duplicate_detection_service.DuplicateDetectionSummary
    -- an explainable count of how many of a job's candidates were actually
    compared for duplicates versus skipped for not being enriched yet, so
    the frontend can tell the two apart instead of an unqualified "no
    duplicates found". Computed fresh on every job read, not stored."""

    total_candidates: int
    eligible_candidates: int
    skipped_not_enriched: int
    likely_count: int
    possible_count: int
    none_count: int


class DigitizerJobRead(DigitizationJobRead):
    """A DigitizationJob plus the safe filenames stored for it and the
    product drafts the AI has produced so far (empty before processing).

    `source_images` are server-generated filenames only (no directory
    components), never absolute filesystem paths. Each `candidates` entry
    carries its own `source_image`/`crop_image` filenames -- combined with
    the safe media endpoint, that is enough for the frontend to build a
    displayable URL for both without exposing any filesystem path.
    """

    source_images: list[str] = []
    candidates: list[DigitizedProductRead] = []
    duplicate_summary: DuplicateDetectionSummaryRead | None = None
