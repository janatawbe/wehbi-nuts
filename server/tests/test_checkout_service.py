"""Tests for app.services.checkout_service -- the server-side pricing and
transactional order-creation logic. Every case here confirms the service
NEVER trusts a price/subtotal/total from its input; it only ever reads
Product rows directly from `db_session`."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.enums import StockStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.checkout import CheckoutItemRequest, CheckoutRequest
from app.services.checkout_service import CheckoutError, create_order_from_checkout


def make_product(db_session: Session, **overrides) -> Product:
    defaults = dict(
        sku=f'SKU-{uuid.uuid4().hex[:8]}',
        name_en='Roasted Almonds',
        name_ar='لوز محمص',
        price=Decimal('20.00'),
        unit='weight',
        needs_review=False,
        stock_status=StockStatus.IN_STOCK,
    )
    defaults.update(overrides)
    product = Product(**defaults)
    db_session.add(product)
    db_session.commit()
    return product


def make_request(items: list[CheckoutItemRequest], **overrides) -> CheckoutRequest:
    defaults = dict(
        customer_name='Jana Tawbe',
        customer_phone='+96170000000',
        delivery_address='Building 4, Hamra Street',
        delivery_area='Hamra',
        notes=None,
    )
    defaults.update(overrides)
    # bypass CheckoutItemRequest's own validators when a test deliberately
    # wants an item that shouldn't even be constructible normally -- see
    # test_defensively_rejects_a_weight_not_in_the_allowed_set below.
    return CheckoutRequest.model_construct(items=items, **defaults)


def weight_item(product_id, grams=300) -> CheckoutItemRequest:
    return CheckoutItemRequest(product_id=product_id, selling_mode='weight', weight_grams=grams)


def unit_item(product_id, quantity=2) -> CheckoutItemRequest:
    return CheckoutItemRequest(product_id=product_id, selling_mode='unit', quantity=quantity)


# --- Happy paths -------------------------------------------------------


def test_creates_an_order_for_a_weight_product(db_session: Session):
    product = make_product(db_session, unit='weight', price=Decimal('20.00'))

    order = create_order_from_checkout(db_session, make_request([weight_item(product.id, grams=300)]))

    assert order.id is not None
    assert order.order_number.startswith('WN')
    assert len(order.order_number) == 10
    assert order.subtotal == Decimal('6.00')  # 20.00/kg * 0.3 kg
    assert order.total == Decimal('6.00')
    assert len(order.items) == 1
    item = order.items[0]
    assert item.selling_mode == 'weight'
    assert item.quantity == Decimal('0.300')
    assert item.unit_price == Decimal('20.00')
    assert item.line_total == Decimal('6.00')
    assert item.package_weight is None


def test_creates_an_order_for_a_unit_product_with_package_weight(db_session: Session):
    product = make_product(db_session, unit='unit', price=Decimal('5.00'), weight=Decimal('0.250'))

    order = create_order_from_checkout(db_session, make_request([unit_item(product.id, quantity=3)]))

    item = order.items[0]
    assert item.selling_mode == 'unit'
    assert item.quantity == Decimal('3')
    assert item.line_total == Decimal('15.00')
    assert item.package_weight == Decimal('0.250')


def test_computes_subtotal_across_mixed_weight_and_unit_lines(db_session: Session):
    coffee = make_product(db_session, name_en='Coffee', unit='weight', price=Decimal('20.00'))
    candy = make_product(db_session, name_en='Candy', unit='unit', price=Decimal('5.00'))

    order = create_order_from_checkout(
        db_session, make_request([weight_item(coffee.id, grams=500), unit_item(candy.id, quantity=2)])
    )

    assert order.subtotal == Decimal('20.00')  # (20*0.5) + (5*2) = 10 + 10
    assert order.total == order.subtotal


def test_rounds_a_tricky_weight_price_to_the_nearest_cent(db_session: Session):
    product = make_product(db_session, unit='weight', price=Decimal('7.33'))

    order = create_order_from_checkout(db_session, make_request([weight_item(product.id, grams=300)]))

    # 7.33 * 0.3 = 2.199 -> rounds half-up to 2.20
    assert order.items[0].line_total == Decimal('2.20')
    assert order.subtotal == Decimal('2.20')


def test_persists_order_and_items_to_the_database(db_session: Session):
    product = make_product(db_session)
    order = create_order_from_checkout(db_session, make_request([weight_item(product.id)]))

    reloaded = db_session.get(Order, order.id)
    assert reloaded is not None
    assert db_session.query(OrderItem).filter_by(order_id=order.id).count() == 1


# --- Availability / correctness guards -----------------------------------


def test_rejects_an_unknown_product(db_session: Session):
    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([weight_item(uuid.uuid4())]))


def test_rejects_a_product_that_needs_review(db_session: Session):
    product = make_product(db_session, needs_review=True)
    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([weight_item(product.id)]))


def test_rejects_an_out_of_stock_product(db_session: Session):
    product = make_product(db_session, stock_status=StockStatus.OUT_OF_STOCK)
    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([weight_item(product.id)]))


def test_allows_a_low_stock_product(db_session: Session):
    product = make_product(db_session, stock_status=StockStatus.LOW_STOCK)
    order = create_order_from_checkout(db_session, make_request([weight_item(product.id)]))
    assert order is not None


def test_rejects_a_selling_mode_mismatch(db_session: Session):
    product = make_product(db_session, unit='unit')  # actually sold per-unit now
    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([weight_item(product.id)]))  # cart still says weight


def test_nothing_is_persisted_when_one_line_in_a_multi_item_cart_is_invalid(db_session: Session):
    good = make_product(db_session, name_en='Good')
    bad = make_product(db_session, name_en='Bad', stock_status=StockStatus.OUT_OF_STOCK)

    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([weight_item(good.id), weight_item(bad.id)]))

    assert db_session.query(Order).count() == 0
    assert db_session.query(OrderItem).count() == 0


def test_defensively_rejects_a_zero_weight(db_session: Session):
    """CheckoutItemRequest's own Field(gt=0) already blocks this, but the
    service must never assume it was the only path that could construct
    one -- model_construct bypasses validation entirely to prove it."""
    product = make_product(db_session, unit='weight')
    sneaky_item = CheckoutItemRequest.model_construct(
        product_id=product.id, selling_mode='weight', weight_grams=0, quantity=None
    )

    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([sneaky_item]))


def test_defensively_rejects_a_negative_weight(db_session: Session):
    product = make_product(db_session, unit='weight')
    sneaky_item = CheckoutItemRequest.model_construct(
        product_id=product.id, selling_mode='weight', weight_grams=-500, quantity=None
    )

    with pytest.raises(CheckoutError):
        create_order_from_checkout(db_session, make_request([sneaky_item]))


def test_creates_an_order_for_more_than_one_kilogram(db_session: Session):
    product = make_product(db_session, unit='weight', price=Decimal('20.00'))

    order = create_order_from_checkout(db_session, make_request([weight_item(product.id, grams=1500)]))

    item = order.items[0]
    assert item.quantity == Decimal('1.500')
    assert item.line_total == Decimal('30.00')  # 20.00/kg * 1.5 kg


def test_creates_an_order_for_multiple_kilograms(db_session: Session):
    product = make_product(db_session, unit='weight', price=Decimal('15.00'))

    order = create_order_from_checkout(db_session, make_request([weight_item(product.id, grams=5000)]))

    item = order.items[0]
    assert item.quantity == Decimal('5.000')
    assert item.line_total == Decimal('75.00')  # 15.00/kg * 5 kg
    assert order.subtotal == Decimal('75.00')


def test_no_upper_bound_on_a_large_but_realistic_bulk_order(db_session: Session):
    """No arbitrary maximum -- a large bulk order (e.g. 25 kg) must price
    exactly, not be rejected."""
    product = make_product(db_session, unit='weight', price=Decimal('12.50'))

    order = create_order_from_checkout(db_session, make_request([weight_item(product.id, grams=25_000)]))

    item = order.items[0]
    assert item.quantity == Decimal('25.000')
    assert item.line_total == Decimal('312.50')  # 12.50/kg * 25 kg


def test_ignores_a_price_the_request_object_is_forced_to_carry(db_session: Session, monkeypatch):
    """Even if something upstream were coerced into carrying a price
    (impossible via the real schema, but simulated here defensively), the
    service must still price strictly from the database."""
    product = make_product(db_session, price=Decimal('20.00'))
    order = create_order_from_checkout(db_session, make_request([weight_item(product.id, grams=1000)]))
    assert order.subtotal == Decimal('20.00')  # full kg at the DB price, not anything else


# --- Order number generation ---------------------------------------------


def test_retries_on_an_order_number_collision(db_session: Session, monkeypatch):
    import app.services.checkout_service as checkout_service

    calls = {'count': 0}

    def colliding_then_unique() -> str:
        calls['count'] += 1
        return 'WNCOLLIDE' if calls['count'] == 1 else 'WNUNIQUE1'

    # Pre-seed a real Order occupying the "colliding" number so the first
    # attempt's INSERT genuinely violates the unique constraint.
    existing = Order(
        order_number='WNCOLLIDE',
        customer_name='Existing',
        customer_phone='000',
        delivery_address='x',
        delivery_area='x',
        subtotal=Decimal('1.00'),
        total=Decimal('1.00'),
    )
    db_session.add(existing)
    db_session.commit()

    monkeypatch.setattr(checkout_service, '_generate_order_number', colliding_then_unique)

    product = make_product(db_session)
    order = create_order_from_checkout(db_session, make_request([weight_item(product.id)]))

    assert order.order_number == 'WNUNIQUE1'
    assert db_session.query(Order).count() == 2  # the pre-seeded one + this new one
