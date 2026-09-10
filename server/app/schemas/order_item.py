import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemBase(BaseModel):
    order_id: uuid.UUID
    product_id: uuid.UUID | None = None
    product_name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemRead(OrderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
