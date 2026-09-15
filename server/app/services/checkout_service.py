"""Milestone 10: turns a customer's cart into a real Order + OrderItems.

Every price/subtotal/total fact here is computed from the CURRENT
database state -- never from anything the browser submitted (see
app.schemas.checkout.CheckoutRequest, which has no price field to trust
or distrust in the first place). This is the one and only place a
customer order is ever created.
"""
import random
import string
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import OrderStatus, SellingMode, StockStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.checkout import CheckoutItemRequest, CheckoutRequest

GRAMS_PER_KG = Decimal('1000')
_ORDER_NUMBER_ALPHABET = string.ascii_uppercase + string.digits
_ORDER_NUMBER_LENGTH = 8
# The random 8-char alphanumeric space is ~2.8e12 -- a collision on any
# single attempt is already vanishingly unlikely; this bounds the retry
# loop rather than looping forever if something is persistently wrong.
_MAX_ORDER_NUMBER_ATTEMPTS = 5


class CheckoutError(Exception):
    """Raised for any checkout request that fails validation against the
    live database (an unknown/hidden/out-of-stock product, a
    selling-mode mismatch, an order-number collision that never resolves,
    etc). Carries a customer-safe message; the API layer turns this into
    an HTTP 422."""


def _generate_order_number() -> str:
    suffix = ''.join(random.choices(_ORDER_NUMBER_ALPHABET, k=_ORDER_NUMBER_LENGTH))
    return f'WN{suffix}'


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class _PricedLine:
    product_id: object
    product_name: str
    product_name_ar: str | None
    selling_mode: SellingMode
    quantity: Decimal  # kilograms for a weight line, item-count for a unit line
    unit_price: Decimal
    line_total: Decimal
    package_weight: Decimal | None


def _price_item(db: Session, item: CheckoutItemRequest) -> _PricedLine:
    """Reloads the product fresh from the database and re-derives every
    price fact from ITS current state -- `item` supplies only an identity
    (product_id) and a requested quantity/weight, nothing priced."""
    product = db.get(Product, item.product_id)
    if product is None or product.needs_review:
        raise CheckoutError('One of the products in your cart is no longer available.')
    if product.stock_status == StockStatus.OUT_OF_STOCK:
        raise CheckoutError(f"'{product.name_en}' is currently out of stock.")

    # Product.unit holds the SAME "weight"/"unit" string as
    # item.selling_mode -- see app.services.storefront_service for this
    # pre-existing, already-established naming. A mismatch means the
    # cart is stale (e.g. an admin changed the product's selling mode
    # after it was added to the cart) -- never silently reinterpreted.
    if product.unit != item.selling_mode:
        raise CheckoutError(f"'{product.name_en}' is no longer sold that way. Please refresh your cart.")

    if item.selling_mode == 'weight':
        # Belt-and-suspenders: CheckoutItemRequest's own Field(gt=0)
        # already rejects zero/negative, but the service never assumes a
        # validator upstream was the only possible caller. No upper bound
        # here either -- any positive weight is a legitimate order.
        if item.weight_grams is None or item.weight_grams <= 0:
            raise CheckoutError('Invalid weight selection.')
        quantity_kg = Decimal(item.weight_grams) / GRAMS_PER_KG
        return _PricedLine(
            product_id=product.id,
            product_name=product.name_en,
            product_name_ar=product.name_ar,
            selling_mode=SellingMode.WEIGHT,
            quantity=quantity_kg,
            unit_price=product.price,
            line_total=_round_money(product.price * quantity_kg),
            package_weight=None,
        )

    quantity = Decimal(item.quantity)
    return _PricedLine(
        product_id=product.id,
        product_name=product.name_en,
        product_name_ar=product.name_ar,
        selling_mode=SellingMode.UNIT,
        quantity=quantity,
        unit_price=product.price,
        line_total=_round_money(product.price * quantity),
        package_weight=product.weight,
    )


def _build_order_items(priced_lines: list[_PricedLine]) -> list[OrderItem]:
    return [
        OrderItem(
            product_id=line.product_id,
            product_name=line.product_name,
            product_name_ar=line.product_name_ar,
            selling_mode=line.selling_mode,
            quantity=line.quantity,
            unit_price=line.unit_price,
            line_total=line.line_total,
            package_weight=line.package_weight,
        )
        for line in priced_lines
    ]


def create_order_from_checkout(db: Session, request: CheckoutRequest) -> Order:
    """The one transactional entry point for placing a Cash-on-Delivery
    order. Prices every line from the current database, then creates the
    Order + OrderItems together -- either both are committed or neither
    is (a failed attempt, e.g. an order_number collision, rolls back
    completely and retries with a fresh number rather than leaving a
    partial order behind)."""
    priced_lines = [_price_item(db, item) for item in request.items]

    subtotal = _round_money(sum((line.line_total for line in priced_lines), Decimal('0')))
    total = subtotal  # No delivery fee or discount concept in Milestone 10.

    last_error: Exception | None = None
    for _attempt in range(_MAX_ORDER_NUMBER_ATTEMPTS):
        order = Order(
            order_number=_generate_order_number(),
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            delivery_address=request.delivery_address,
            delivery_area=request.delivery_area,
            notes=request.notes,
            status=OrderStatus.PENDING,
            subtotal=subtotal,
            total=total,
            items=_build_order_items(priced_lines),
        )
        db.add(order)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            continue
        db.refresh(order)
        return order

    raise CheckoutError('Could not create the order. Please try again.') from last_error
