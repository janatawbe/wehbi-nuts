import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus


class OrderBase(BaseModel):
    order_number: str = Field(min_length=1, max_length=32)
    customer_name: str = Field(min_length=1, max_length=255)
    customer_phone: str = Field(min_length=1, max_length=32)
    delivery_address: str = Field(min_length=1)
    delivery_area: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    status: OrderStatus = OrderStatus.PENDING
    subtotal: Decimal = Field(ge=0)
    total: Decimal = Field(ge=0)


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_phone: str | None = Field(default=None, min_length=1, max_length=32)
    delivery_address: str | None = Field(default=None, min_length=1)
    delivery_area: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    status: OrderStatus | None = None
    subtotal: Decimal | None = Field(default=None, ge=0)
    total: Decimal | None = Field(default=None, ge=0)


class OrderRead(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
