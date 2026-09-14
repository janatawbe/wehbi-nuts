import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import (
    BackgroundIsolationStatus,
    DuplicateResolution,
    DuplicateStatus,
    EnrichmentStatus,
    IdentificationBasis,
    ImageRefinementStatus,
    PresentationType,
    ReviewStatus,
    SellingMode,
    StockStatus,
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
        CheckConstraint(
            "price IS NULL OR price >= 0", name="ck_digitized_products_price_non_negative"
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
        default=ReviewStatus.PENDING_REVIEW,
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

    # Milestone 6: catalog-ready image derived from `crop_image` (Tier 1
    # canvas/padding/resize, plus attempted Tier 2 background isolation for
    # every "suitable" presentation, including bulk/loose) -- see
    # app.services.image_refinement_service. `crop_image` above is never
    # overwritten; this is always a separate file.
    refined_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_refinement_status: Mapped[ImageRefinementStatus] = mapped_column(
        SAEnum(
            ImageRefinementStatus,
            name="image_refinement_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ImageRefinementStatus.PENDING,
    )
    # Whether Tier 2 background isolation was attempted and its outcome --
    # distinct from image_refinement_status (the overall pipeline, which
    # still succeeds via Tier-1-only fallback even when isolation itself
    # is rejected). Lets a human reviewer see when isolation was tried and
    # rejected as unsafe, e.g. for a hard-to-segment bulk/loose product.
    background_isolation_status: Mapped[BackgroundIsolationStatus] = mapped_column(
        SAEnum(
            BackgroundIsolationStatus,
            name="background_isolation_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=BackgroundIsolationStatus.NOT_ATTEMPTED,
    )

    # Milestone 6: deterministic, within-job duplicate flagging -- see
    # app.services.duplicate_detection_service. Never auto-merges/deletes;
    # a human resolves flagged groups in Milestone 7.
    duplicate_status: Mapped[DuplicateStatus] = mapped_column(
        SAEnum(
            DuplicateStatus,
            name="duplicate_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=DuplicateStatus.NOT_CHECKED,
    )
    # Shared by every product transitively matched together (union-find
    # over qualifying pairwise matches) -- NULL until at least one match is
    # found. Not a foreign key: it is a synthetic group label, not a row.
    duplicate_group_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    # Milestone 7: a single terminal fact about THIS product itself, not a
    # per-relationship resolution -- only ever meaningfully MERGED (set
    # alongside review_status=MERGED when this record is merged away).
    # "Keep separate" does NOT set this field: whether a *specific*
    # relationship (e.g. with one other candidate) is resolved lives on
    # DigitizedProductDuplicateMatch.resolution instead, since a product
    # can have one resolved and one still-unresolved duplicate relationship
    # at the same time -- a single product-level flag cannot represent that.
    # See DigitizedProduct.has_unresolved_duplicates for the actual source
    # of truth used by the review UI/bulk-approve gating.
    duplicate_resolution: Mapped[DuplicateResolution] = mapped_column(
        SAEnum(
            DuplicateResolution,
            name="duplicate_resolution",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=DuplicateResolution.UNRESOLVED,
    )

    # --- Milestone 7: human review & approval ------------------------------
    #
    # AI never sets price -- see app.services.digitizer_review_service.
    # Meaning depends on selling_mode: for WEIGHT products this is the
    # price per KILOGRAM; for UNIT products this is the fixed price for
    # one unit/package. One field, not two competing ones, mirroring how
    # Product.price already works (a single price column whose meaning is
    # likewise carried by context, not a separate column per mode).
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    stock_status: Mapped[StockStatus] = mapped_column(
        SAEnum(
            StockStatus,
            name="stock_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=StockStatus.IN_STOCK,
    )
    # Set whenever a human saves ANY review action on this product's own
    # content (field edits, draft save, approve, reject) -- NOT set by
    # duplicate keep-separate/merge actions, which are about the duplicate
    # GROUP rather than this product's own information. Also used to guard
    # against a manual "Re-enrich" silently overwriting reviewed edits --
    # see digitizer_enrichment_service.enrich_digitized_product.
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Self-referential traceability link for a merged-away record (see
    # DuplicateResolution.MERGED) -- points at the surviving canonical
    # DigitizedProduct. NULL for every record that was never merged away,
    # including the canonical survivor itself. ondelete=SET NULL rather
    # than CASCADE: deleting the canonical must never cascade-delete the
    # merged-away evidence records.
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("digitized_products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    job: Mapped["DigitizationJob"] = relationship(  # noqa: F821
        "DigitizationJob", back_populates="digitized_products"
    )
    product: Mapped["Product | None"] = relationship(  # noqa: F821
        "Product", back_populates="digitized_products"
    )
    category: Mapped["Category | None"] = relationship("Category")  # noqa: F821
    merged_into: Mapped["DigitizedProduct | None"] = relationship(
        "DigitizedProduct", remote_side="DigitizedProduct.id", foreign_keys=[merged_into_id]
    )
    duplicate_matches: Mapped[list["DigitizedProductDuplicateMatch"]] = relationship(  # noqa: F821
        "DigitizedProductDuplicateMatch",
        foreign_keys="DigitizedProductDuplicateMatch.product_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(DigitizedProductDuplicateMatch.score)",
    )

    @property
    def has_unresolved_duplicates(self) -> bool:
        """The single source of truth for "does this product currently
        require a duplicate-resolution decision" -- used by the review
        list/badges/filter and by bulk-approve's gating check alike, so
        none of them can drift out of sync with each other. True only when
        at least one of this product's pairwise match rows still has
        `resolution == UNRESOLVED` (see DigitizedProductDuplicateMatch's
        docstring) -- NOT merely whether a match row exists at all, which
        is what the pre-Milestone-7-audit logic incorrectly used. Since
        `duplicate_matches` is stored bidirectionally (a row from this
        product to every product it's matched with), this single-direction
        list is already complete -- no second query needed.
        """
        return any(
            match.resolution == DuplicateResolution.UNRESOLVED for match in self.duplicate_matches
        )
