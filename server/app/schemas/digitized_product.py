import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    BackgroundIsolationStatus,
    DuplicateStatus,
    EnrichmentStatus,
    IdentificationBasis,
    ImageRefinementStatus,
    PresentationType,
    ReviewStatus,
    SellingMode,
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
    review_status: ReviewStatus = ReviewStatus.DRAFT
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


class DigitizedProductCreate(DigitizedProductBase):
    pass


class DuplicateMatchRead(BaseModel):
    """One directed pairwise duplicate match, evidence-only -- see
    DigitizedProductDuplicateMatch. Never implies anything was merged."""

    model_config = ConfigDict(from_attributes=True)

    matched_product_id: uuid.UUID
    matched_name_en: str | None = None
    score: Decimal
    reasons: list[str]


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


class DigitizedProductRead(DigitizedProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    duplicate_matches: list[DuplicateMatchRead] = []
