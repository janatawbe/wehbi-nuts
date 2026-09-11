import enum


class StockStatus(str, enum.Enum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"


class DigitizationJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


class PresentationType(str, enum.Enum):
    """How a detected sellable unit is physically presented on the shelf."""

    PACKAGED = "packaged"
    JAR = "jar"
    BOTTLE = "bottle"
    BULK_TRAY = "bulk_tray"
    BULK_LOOSE = "bulk_loose"
    OTHER = "other"


class IdentificationBasis(str, enum.Enum):
    """How an AI vision analyzer arrived at a detected item's identity --
    kept distinct from the identity itself so a visual guess is never
    silently presented as if it had been read from text."""

    VISUAL = "visual"
    TEXT = "text"
    VISUAL_AND_TEXT = "visual_and_text"


class SellingMode(str, enum.Enum):
    """How a digitized product is SOLD (Milestone 5 enrichment) -- entirely
    independent of whether it happens to have a printed package weight.
    A packaged 500g bag is still sold PER UNIT (one fixed-price item); only
    a genuinely loose/bulk good with no fixed package (a tray, bin, or
    scoop display) is sold BY WEIGHT. `DigitizedProduct.package_weight` is
    the separate, orthogonal field for a printed net weight -- see its own
    docstring. Having a package_weight does NOT imply WEIGHT selling."""

    WEIGHT = "weight"
    UNIT = "unit"


class EnrichmentStatus(str, enum.Enum):
    """Whether Milestone 5 AI enrichment has successfully completed for a
    DigitizedProduct. Deliberately separate from `review_status` (human
    approval state, Milestone 7) -- this only tracks whether the
    AI-enrichment step itself has run, so job-level enrichment can skip
    products that are already enriched (cost control) without that being
    confused with, or gated by, human review/approval."""

    PENDING = "pending"
    ENRICHED = "enriched"


class ImageRefinementStatus(str, enum.Enum):
    """Whether Milestone 6 image refinement (Tier 1 canvas/padding/resize +
    optional Tier 2 background isolation) has completed for a
    DigitizedProduct. Deliberately its own field, separate from both
    `enrichment_status` (Milestone 5) and `review_status` (Milestone 7) --
    refinement is a third, independent pipeline stage with its own success/
    failure outcome."""

    PENDING = "pending"
    REFINED = "refined"
    FAILED = "failed"
    # No crop image was available to refine from -- distinct from FAILED
    # (an attempt that ran and didn't succeed): nothing was attempted, and
    # retrying later without a crop would fail identically, so job-level
    # bulk refinement marks this instead of retrying it every time.
    SKIPPED = "skipped"


class BackgroundIsolationStatus(str, enum.Enum):
    """Whether Milestone 6 Tier 2 background isolation was attempted for a
    DigitizedProduct's refinement, and its outcome -- independent of
    `image_refinement_status`, which tracks the overall (always-runs-Tier-1)
    pipeline outcome. Isolation is attempted for every presentation type
    now (including bulk/loose), but loose/bulk products are materially
    harder to segment safely than a single packaged item, so a rejected
    attempt is recorded distinctly here rather than silently folded into a
    plain success -- letting a human reviewer later see "isolation was
    tried and rejected as unsafe" instead of it looking identical to
    "isolation succeeded cleanly" or "isolation was never attempted"."""

    NOT_ATTEMPTED = "not_attempted"
    APPLIED = "applied"
    # Attempted, but rejected by this module's own safety check (retained
    # too little of the original product) or failed outright (an
    # exception, or output Pillow couldn't decode) -- either way, the
    # refined image falls back to Tier-1-only, never a fabricated result.
    REJECTED = "rejected"


class DuplicateStatus(str, enum.Enum):
    """Milestone 6's duplicate-detection outcome for a DigitizedProduct,
    scoped to comparisons within its own job (see
    app.services.duplicate_detection_service). This only FLAGS a possible
    relationship -- it never merges or deletes anything; that decision is
    Milestone 7's."""

    NOT_CHECKED = "not_checked"
    NONE = "none"
    POSSIBLE = "possible"
    LIKELY = "likely"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
