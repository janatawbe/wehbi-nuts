"""Milestone 10 customer checkout request/response shapes.

Deliberately SEPARATE from app.schemas.order/order_item (the Milestone 2
admin-facing schemas, which accept a client-submitted subtotal/total/
unit_price/line_total directly) -- CheckoutRequest carries no price field
of any kind. There is nothing for app.services.checkout_service to
"remember not to trust": the shape of this request makes it impossible
for a browser to submit a price, subtotal, or total in the first place.
Every price fact in CheckoutResult is instead computed server-side from
the live Product rows -- see checkout_service.create_order_from_checkout.
"""
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import OrderStatus

# Milestone 10 originally restricted a weight-mode order to six fixed
# presets (100-1000 g). The shop now allows ANY practical positive
# weight, including multiple kilograms -- deliberately NO business-rule
# maximum. `_MAX_WEIGHT_GRAMS` below is NOT that kind of cap: it only
# guards against a value too large to fit `order_items.quantity`
# (Numeric(10, 3), i.e. a ceiling of 9,999,999.999 kilograms) -- a
# technical DB-column-overflow safety bound a real customer will never
# come close to, not a restriction on how much someone can order.
_MAX_WEIGHT_GRAMS = 9_999_999_000

# A generous but finite per-line cap for a unit-mode item -- purely a
# sanity/abuse guard (e.g. against a typo'd or malicious six-digit
# quantity), not a real inventory limit (this app has no per-product
# stock count to check against).
MAX_UNIT_QUANTITY = 20

_NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CheckoutItemRequest(BaseModel):
    """One requested cart line. Carries only what's needed to identify the
    product and the customer's requested quantity/weight -- no name, no
    price. Exactly one of `weight_grams`/`quantity` is set, matching
    `selling_mode`; see `_validate_mode_fields`."""

    product_id: uuid.UUID
    selling_mode: Literal['weight', 'unit']
    # Strictly positive -- zero/negative are rejected here at the field
    # level (gt=0); the upper bound is only the DB-column-overflow safety
    # net described above, never a real business maximum.
    weight_grams: int | None = Field(default=None, gt=0, le=_MAX_WEIGHT_GRAMS)
    quantity: int | None = Field(default=None)

    @model_validator(mode='after')
    def _validate_mode_fields(self) -> 'CheckoutItemRequest':
        if self.selling_mode == 'weight':
            if self.weight_grams is None or self.quantity is not None:
                raise ValueError('A weight-mode item must set weight_grams only (not quantity).')
        else:
            if self.quantity is None or self.weight_grams is not None:
                raise ValueError('A unit-mode item must set quantity only (not weight_grams).')
            if not (1 <= self.quantity <= MAX_UNIT_QUANTITY):
                raise ValueError(f'quantity must be between 1 and {MAX_UNIT_QUANTITY}.')
        return self


class CheckoutRequest(BaseModel):
    """The full Cash-on-Delivery checkout submission. `delivery_area` is
    required (mirrors Order.delivery_area, itself a required column) --
    a separate field from `delivery_address` for the neighborhood/district,
    shown to the customer as "Area / Neighborhood" / "المنطقة / الحي"."""

    customer_name: _NonBlankStr = Field(max_length=255)
    customer_phone: _NonBlankStr = Field(max_length=32)
    delivery_address: _NonBlankStr
    delivery_area: _NonBlankStr = Field(max_length=255)
    notes: str | None = Field(default=None)
    items: list[CheckoutItemRequest] = Field(min_length=1)

    @model_validator(mode='after')
    def _normalize_notes(self) -> 'CheckoutRequest':
        if self.notes is not None:
            stripped = self.notes.strip()
            self.notes = stripped or None
        return self

    @model_validator(mode='after')
    def _reject_duplicate_products(self) -> 'CheckoutRequest':
        seen: set[uuid.UUID] = set()
        for item in self.items:
            if item.product_id in seen:
                raise ValueError(f'Duplicate product in checkout request: {item.product_id}')
            seen.add(item.product_id)
        return self


class CheckoutItemResult(BaseModel):
    """One confirmed, server-priced order line -- returned so the
    frontend's order-success page never needs to have trusted its own
    locally-computed cart numbers."""

    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID | None
    product_name: str
    product_name_ar: str | None
    selling_mode: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    package_weight: Decimal | None


class CheckoutResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    status: OrderStatus
    subtotal: Decimal
    total: Decimal
    items: list[CheckoutItemResult]
