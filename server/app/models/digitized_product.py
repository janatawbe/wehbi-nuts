import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import IdentificationBasis, PresentationType, ReviewStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DigitizedProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digitized_products"
    __table_args__ = (
        CheckConstraint(
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)",
            name="ck_digitized_products_ai_confidence_range",
        ),
        CheckConstraint(
            "bbox_x IS NULL OR bbox_x >= 0", name="ck_digitized_products_bbox_x_non_negative"
        ),
        CheckConstraint(
            "bbox_y IS NULL OR bbox_y >= 0", name="ck_digitized_products_bbox_y_non_negative"
        ),
        CheckConstraint(
            "bbox_width IS NULL OR bbox_width > 0", name="ck_digitized_products_bbox_width_positive"
        ),
        CheckConstraint(
            "bbox_height IS NULL OR bbox_height > 0",
            name="ck_digitized_products_bbox_height_positive",
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("digitization_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    crop_image: Mapped[str | None] = mapped_column(String(512), nullable=True)

    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_raw_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(
            ReviewStatus,
            name="review_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ReviewStatus.DRAFT,
    )

    # AI vision-digitizer fields (Milestone 4). `category_suggestion` is
    # the AI's raw, unvalidated category text -- distinct from `category_id`,
    # which stays NULL until a human links this draft to a real `Category`.
    category_suggestion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    presentation: Mapped[PresentationType | None] = mapped_column(
        SAEnum(
            PresentationType,
            name="presentation_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    identification_basis: Mapped[IdentificationBasis | None] = mapped_column(
        SAEnum(
            IdentificationBasis,
            name="identification_basis",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    visible_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pixel-space bounding box within `source_image`, derived from the AI's
    # normalized [0, 1000] coordinates -- kept in pixel space so displaying
    # or re-cropping never needs the original image dimensions again.
    bbox_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    job: Mapped["DigitizationJob"] = relationship(  # noqa: F821
        "DigitizationJob", back_populates="digitized_products"
    )
    product: Mapped["Product | None"] = relationship(  # noqa: F821
        "Product", back_populates="digitized_products"
    )
    category: Mapped["Category | None"] = relationship("Category")  # noqa: F821
