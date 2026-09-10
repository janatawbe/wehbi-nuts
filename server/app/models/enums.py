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


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
