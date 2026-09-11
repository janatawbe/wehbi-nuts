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


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
