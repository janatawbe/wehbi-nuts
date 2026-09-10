import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StockStatus


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    name_en: str = Field(min_length=1, max_length=255)
    name_ar: str = Field(min_length=1, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    category_id: uuid.UUID | None = None
    brand: str | None = Field(default=None, max_length=255)
    weight: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    price: Decimal = Field(ge=0)
    discount_price: Decimal | None = Field(default=None, ge=0)
    stock_status: StockStatus = StockStatus.IN_STOCK
    image: str | None = Field(default=None, max_length=512)
    source_image: str | None = Field(default=None, max_length=512)
    ai_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    needs_review: bool = False
    ai_raw_result: dict[str, Any] | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    name_ar: str | None = Field(default=None, min_length=1, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    category_id: uuid.UUID | None = None
    brand: str | None = Field(default=None, max_length=255)
    weight: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    price: Decimal | None = Field(default=None, ge=0)
    discount_price: Decimal | None = Field(default=None, ge=0)
    stock_status: StockStatus | None = None
    image: str | None = Field(default=None, max_length=512)
    source_image: str | None = Field(default=None, max_length=512)
    ai_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    needs_review: bool | None = None
    ai_raw_result: dict[str, Any] | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
