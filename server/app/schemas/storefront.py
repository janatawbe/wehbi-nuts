import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import StockStatus

# Milestone 9: customer-safe read models for the public storefront API.
# Deliberately narrower than ProductRead/CategoryRead (app/schemas/
# product.py, category.py) -- those are the full internal shapes used by
# admin tooling. Nothing here ever exposes sku, barcode, database
# timestamps, ai_confidence/ai_raw_result, needs_review, or source_image;
# see app/services/storefront_service.py for the one place that maps a
# Product to this shape.


class StorefrontCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ar: str
    slug: str


class StorefrontProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ar: str
    description_en: str | None
    description_ar: str | None
    brand: str | None
    category: StorefrontCategoryRead | None
    # "weight" (priced per kilogram) or "unit" (fixed price per package) --
    # mirrors DigitizedProduct.selling_mode's naming (Milestone 5), read
    # from Product's own pre-existing (Milestone 2) `unit` column, which
    # has held exactly these two string values since Milestone 7 approval
    # started writing it (see digitizer_review_service._upsert_catalog_product).
    selling_mode: str | None
    package_weight: Decimal | None
    price: Decimal
    stock_status: StockStatus
    image: str | None
