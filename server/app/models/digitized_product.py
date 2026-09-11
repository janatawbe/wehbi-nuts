import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import (
    EnrichmentStatus,
    IdentificationBasis,
    PresentationType,
    ReviewStatus,
    SellingMode,
)
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
        CheckConstraint(
            "package_weight IS NULL OR package_weight >= 0",
            name="ck_digitized_products_package_weight_non_negative",
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
    # Flavor/type/variant (e.g. "Salted", "Hazelnut", "Dark Chocolate"),
    # Milestone 5 enrichment -- null when not visible/identifiable, never
    # invented.
    flavor_variant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # How this product is SOLD (Milestone 5 enrichment) -- see SellingMode's
    # own docstring. Independent of `package_weight` below: a packaged
    # 500g bag is UNIT with package_weight=0.500; a bulk tray is WEIGHT
    # with package_weight=NULL.
    selling_mode: Mapped[SellingMode | None] = mapped_column(
        SAEnum(
            SellingMode,
            name="selling_mode",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    # Kilograms. Only a genuinely printed/visible package net WEIGHT (never
    # a volume, e.g. a bottle's "1L") -- populated regardless of
    # selling_mode being knowable, but in practice only ever set for
    # selling_mode == UNIT (a bulk/loose good has no package to print a
    # weight on). See enrichment_service._EnrichmentResponse for the
    # validator enforcing this.
    package_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
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
    # Whether Milestone 5 enrichment has completed for this row -- distinct
    # from review_status above (human approval). Lets job-level enrichment
    # skip already-enriched products without touching review state.
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        SAEnum(
            EnrichmentStatus,
            name="enrichment_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EnrichmentStatus.PENDING,
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

    # Field-level review flags from Milestone 5 enrichment, e.g.
    # {"brand": {"needs_review": false, "reason": null}, ...} -- lets a
    # future reviewer see exactly which enriched fields are uncertain
    # instead of relying on the single overall `ai_confidence`/
    # `needs_review` pair above. A field being null (no visible brand on a
    # bulk item, no visible barcode) is a legitimate answer, not itself a
    # reason for needs_review=true.
    field_review: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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
