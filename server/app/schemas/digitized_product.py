import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class DigitizedProductBase(BaseModel):
    job_id: uuid.UUID
    product_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    source_image: str | None = Field(default=None, max_length=512)
    crop_image: str | None = Field(default=None, max_length=512)
    name_en: str | None = Field(default=None, max_length=255)
    name_ar: str | None = Field(default=None, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    brand: str | None = Field(default=None, max_length=255)
    flavor_variant: str | None = Field(default=None, max_length=255)
    selling_mode: SellingMode | None = None
    package_weight: Decimal | None = None
    barcode: str | None = Field(default=None, max_length=64)
    ai_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    needs_review: bool = True
    ai_raw_result: dict[str, Any] | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    enrichment_status: EnrichmentStatus = EnrichmentStatus.PENDING

    # AI vision-digitizer fields (Milestone 4).
    category_suggestion: str | None = Field(default=None, max_length=255)
    presentation: PresentationType | None = None
    identification_basis: IdentificationBasis | None = None
    visible_text: str | None = None
    notes: str | None = None
    bbox_x: int | None = Field(default=None, ge=0)
    bbox_y: int | None = Field(default=None, ge=0)
    bbox_width: int | None = Field(default=None, gt=0)
    bbox_height: int | None = Field(default=None, gt=0)

    # Field-level review flags from Milestone 5 enrichment (see
    # DigitizedProduct.field_review).
    field_review: dict[str, Any] | None = None

    # Milestone 6 image refinement.
    refined_image: str | None = Field(default=None, max_length=512)
    image_refinement_status: ImageRefinementStatus = ImageRefinementStatus.PENDING
    background_isolation_status: BackgroundIsolationStatus = BackgroundIsolationStatus.NOT_ATTEMPTED

    # Milestone 6 duplicate detection -- flags only, never a merge/delete.
    duplicate_status: DuplicateStatus = DuplicateStatus.NOT_CHECKED
    duplicate_group_id: uuid.UUID | None = None

    # Milestone 7 human review & approval. `price` is NEVER set by AI --
    # see app.services.digitizer_review_service. Meaning depends on
    # selling_mode: per-kilogram for WEIGHT products, fixed per-unit for
    # UNIT products.
    price: Decimal | None = Field(default=None, ge=0)
    stock_status: StockStatus = StockStatus.IN_STOCK
    # A terminal fact about this product itself (only ever meaningfully
    # MERGED) -- NOT per-relationship resolution. See
    # has_unresolved_duplicates (on DigitizedProductRead) for the actual
    # "does this product need a duplicate decision" signal.
    duplicate_resolution: DuplicateResolution = DuplicateResolution.UNRESOLVED
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    merged_into_id: uuid.UUID | None = None


class DigitizedProductCreate(DigitizedProductBase):
    pass


class DuplicateMatchRead(BaseModel):
    """One directed pairwise duplicate match, evidence-only -- see
    DigitizedProductDuplicateMatch. Never implies anything was merged.
    `resolution` is the human decision about THIS specific relationship
    (unresolved/kept_separate/merged) -- the frontend uses it to stop
    showing an already-resolved match as if it still needed action, while
    still displaying it as historical evidence."""

    model_config = ConfigDict(from_attributes=True)

    matched_product_id: uuid.UUID
    matched_name_en: str | None = None
    score: Decimal
    reasons: list[str]
    resolution: DuplicateResolution


class DigitizedProductUpdate(BaseModel):
    product_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    crop_image: str | None = Field(default=None, max_length=512)
    name_en: str | None = Field(default=None, max_length=255)
    name_ar: str | None = Field(default=None, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    brand: str | None = Field(default=None, max_length=255)
    flavor_variant: str | None = Field(default=None, max_length=255)
    selling_mode: SellingMode | None = None
    package_weight: Decimal | None = None
    barcode: str | None = Field(default=None, max_length=64)
    ai_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    needs_review: bool | None = None
    ai_raw_result: dict[str, Any] | None = None
    field_review: dict[str, Any] | None = None
    review_status: ReviewStatus | None = None
    enrichment_status: EnrichmentStatus | None = None
    refined_image: str | None = Field(default=None, max_length=512)
    image_refinement_status: ImageRefinementStatus | None = None
    background_isolation_status: BackgroundIsolationStatus | None = None
    duplicate_status: DuplicateStatus | None = None
    duplicate_group_id: uuid.UUID | None = None

    price: Decimal | None = Field(default=None, ge=0)
    stock_status: StockStatus | None = None
    duplicate_resolution: DuplicateResolution | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    merged_into_id: uuid.UUID | None = None


class DigitizedProductRead(DigitizedProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    duplicate_matches: list[DuplicateMatchRead] = []
    # Computed from duplicate_matches (see DigitizedProduct.
    # has_unresolved_duplicates) -- the single source of truth for whether
    # this product currently needs a duplicate-resolution decision. Prefer
    # this over inspecting duplicate_status/duplicate_matches directly.
    has_unresolved_duplicates: bool


class DigitizedProductReviewUpdate(BaseModel):
    """Milestone 7 human review edit -- deliberately scoped to only the
    fields a reviewer is allowed to change by hand (never bbox/AI-confidence/
    raw-result/status-machine fields; those are AI- or service-owned).
    Saving through this schema always counts as a human touch: the service
    stamps `reviewed_at` and, since human edits are authoritative, this is
    also what protects the record from being silently overwritten by a
    later re-enrichment run."""

    name_en: str | None = Field(default=None, max_length=255)
    name_ar: str | None = Field(default=None, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    category_id: uuid.UUID | None = None
    brand: str | None = Field(default=None, max_length=255)
    flavor_variant: str | None = Field(default=None, max_length=255)
    selling_mode: SellingMode | None = None
    package_weight: Decimal | None = None
    barcode: str | None = Field(default=None, max_length=64)
    price: Decimal | None = Field(default=None, ge=0)
    stock_status: StockStatus | None = None
    # A reviewer may only use this endpoint to explicitly save as DRAFT
    # (deliberately incomplete). Approval/rejection/merge go through their
    # own dedicated endpoints, which apply their own stricter rules.
    review_status: Literal[ReviewStatus.DRAFT] | None = None


class DigitizedProductApproveRequest(BaseModel):
    """Empty today -- present so the approval endpoint has a well-defined
    request body to extend later without a breaking API change."""

    pass


class DigitizedProductRejectRequest(BaseModel):
    reason: str | None = None


class DuplicateKeepSeparateRequest(BaseModel):
    """Resolves the duplicate relationship(s) BETWEEN the listed products
    as kept-separate -- per pairwise relationship, not a blanket flag on
    each product (a product may still have a separate, unresolved
    relationship with a product NOT in this list; that one is untouched).
    Does not require the products to share a duplicate_group_id -- a
    reviewer may resolve any set they judge distinct after inspecting the
    evidence."""

    product_ids: list[uuid.UUID] = Field(min_length=2)


class DuplicateMergeRequest(BaseModel):
    """Merge one or more candidates into a single human-chosen canonical
    survivor. The canonical record itself is edited normally afterward
    (through DigitizedProductReviewUpdate) -- this endpoint only performs
    the merge itself, never a field-by-field combination."""

    canonical_id: uuid.UUID
    merge_ids: list[uuid.UUID] = Field(min_length=1)


class BulkApproveRequest(BaseModel):
    product_ids: list[uuid.UUID] = Field(min_length=1)


class BulkApproveFailure(BaseModel):
    product_id: uuid.UUID
    reasons: list[str]


class BulkApproveResponse(BaseModel):
    approved: list[DigitizedProductRead]
    failed: list[BulkApproveFailure]


class DuplicateMergeResponse(BaseModel):
    canonical: DigitizedProductRead
    merged: list[DigitizedProductRead]
