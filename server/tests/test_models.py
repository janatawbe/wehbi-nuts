import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models import Category, DigitizationJob, DigitizedProduct, Order, OrderItem, Product
from app.models.enums import (
    DigitizationJobStatus,
    OrderStatus,
    ReviewStatus,
    StockStatus,
)
from app.schemas.order_item import OrderItemCreate
from app.schemas.product import ProductCreate


def make_product(db_session, **overrides):
    defaults = dict(
        sku="SKU-DEFAULT",
        name_en="Mixed Nuts",
        name_ar="test-ar",
        price=Decimal("5.00"),
    )
    defaults.update(overrides)
    product = Product(**defaults)
    db_session.add(product)
    db_session.commit()
    return product


def make_order(db_session, **overrides):
    defaults = dict(
        order_number="ORD-DEFAULT",
        customer_name="Jana",
        customer_phone="+96170000000",
        delivery_address="Beirut",
        delivery_area="Hamra",
        subtotal=Decimal("10.00"),
        total=Decimal("10.00"),
    )
    defaults.update(overrides)
    order = Order(**defaults)
    db_session.add(order)
    db_session.commit()
    return order


# --- Model creation ---------------------------------------------------


def test_create_category(db_session):
    category = Category(name_en="Nuts", name_ar="test-ar", slug="nuts")
    db_session.add(category)
    db_session.commit()

    assert isinstance(category.id, uuid.UUID)
    assert category.parent_id is None
    assert category.created_at is not None
    assert category.updated_at is not None


def test_create_product(db_session):
    product = make_product(db_session, sku="CREATE-1")

    assert isinstance(product.id, uuid.UUID)
    assert product.stock_status == StockStatus.IN_STOCK
    assert product.needs_review is False


# --- Category parent / subcategory relationship ------------------------


def test_category_parent_child_relationship(db_session):
    parent = Category(name_en="Nuts", name_ar="test-ar", slug="nuts")
    db_session.add(parent)
    db_session.commit()

    child = Category(
        name_en="Almonds", name_ar="test-ar-2", slug="almonds", parent_id=parent.id
    )
    db_session.add(child)
    db_session.commit()

    assert child.parent is parent
    assert child in parent.children


def test_category_products_relationship(db_session):
    category = Category(name_en="Nuts", name_ar="test-ar", slug="nuts")
    db_session.add(category)
    db_session.commit()

    product = make_product(db_session, sku="CAT-1", category_id=category.id)

    assert product.category is category
    assert product in category.products


def test_deleting_category_nulls_product_category_id(db_session):
    category = Category(name_en="Nuts", name_ar="test-ar", slug="nuts")
    db_session.add(category)
    db_session.commit()

    product = make_product(db_session, sku="CAT-2", category_id=category.id)

    _ = category.products  # load the collection so the ORM can null the FK
    db_session.delete(category)
    db_session.commit()
    db_session.refresh(product)

    assert product.category_id is None


# --- Unique SKU / barcode -----------------------------------------------


def test_product_sku_unique_constraint(db_session):
    db_session.add(Product(sku="DUP-SKU", name_en="A", name_ar="a", price=Decimal("1")))
    db_session.commit()

    db_session.add(Product(sku="DUP-SKU", name_en="B", name_ar="b", price=Decimal("2")))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_product_barcode_unique_when_present(db_session):
    db_session.add(
        Product(sku="BC-1", name_en="A", name_ar="a", price=Decimal("1"), barcode="12345")
    )
    db_session.commit()

    db_session.add(
        Product(sku="BC-2", name_en="B", name_ar="b", price=Decimal("1"), barcode="12345")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_product_barcode_null_allows_multiple_products(db_session):
    p1 = Product(sku="BC-3", name_en="A", name_ar="a", price=Decimal("1"))
    p2 = Product(sku="BC-4", name_en="B", name_ar="b", price=Decimal("1"))
    db_session.add_all([p1, p2])
    db_session.commit()  # must not raise

    assert p1.barcode is None
    assert p2.barcode is None


# --- Decimal price handling / negative price validation -----------------


def test_product_price_is_decimal(db_session):
    product = make_product(db_session, sku="DEC-1", price=Decimal("19.99"))

    assert isinstance(product.price, Decimal)
    assert product.price == Decimal("19.99")


def test_product_negative_price_rejected_by_db(db_session):
    db_session.add(Product(sku="NEG-1", name_en="A", name_ar="a", price=Decimal("-1.00")))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_product_negative_discount_price_rejected_by_db(db_session):
    db_session.add(
        Product(
            sku="NEG-2",
            name_en="A",
            name_ar="a",
            price=Decimal("5.00"),
            discount_price=Decimal("-1.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_product_negative_price_rejected_by_schema():
    with pytest.raises(ValidationError):
        ProductCreate(sku="NEG-3", name_en="A", name_ar="a", price=Decimal("-1.00"))


# --- AI confidence bounds ------------------------------------------------


def test_ai_confidence_bounds_schema():
    with pytest.raises(ValidationError):
        ProductCreate(
            sku="CONF-1", name_en="A", name_ar="a", price=Decimal("1"),
            ai_confidence=Decimal("1.5"),
        )
    with pytest.raises(ValidationError):
        ProductCreate(
            sku="CONF-2", name_en="A", name_ar="a", price=Decimal("1"),
            ai_confidence=Decimal("-0.1"),
        )

    valid = ProductCreate(
        sku="CONF-3", name_en="A", name_ar="a", price=Decimal("1"),
        ai_confidence=Decimal("0.75"),
    )
    assert valid.ai_confidence == Decimal("0.75")


def test_ai_confidence_bounds_db(db_session):
    db_session.add(
        Product(
            sku="CONF-4",
            name_en="A",
            name_ar="a",
            price=Decimal("1"),
            ai_confidence=Decimal("1.50"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- DigitizationJob relationships ---------------------------------------


def test_digitization_job_digitized_products_relationship(db_session):
    job = DigitizationJob(total_items=2)
    db_session.add(job)
    db_session.commit()

    dp1 = DigitizedProduct(job_id=job.id, name_en="Item 1")
    dp2 = DigitizedProduct(job_id=job.id, name_en="Item 2")
    db_session.add_all([dp1, dp2])
    db_session.commit()

    assert len(job.digitized_products) == 2
    assert dp1.job is job


def test_digitization_job_cascade_deletes_digitized_products(db_session):
    job = DigitizationJob(total_items=1)
    db_session.add(job)
    db_session.commit()

    dp = DigitizedProduct(job_id=job.id, name_en="Item")
    db_session.add(dp)
    db_session.commit()
    dp_id = dp.id

    db_session.delete(job)
    db_session.commit()

    assert db_session.get(DigitizedProduct, dp_id) is None


def test_digitization_job_status_enum_default(db_session):
    job = DigitizationJob()
    db_session.add(job)
    db_session.commit()

    assert job.status == DigitizationJobStatus.PENDING


# --- DigitizedProduct review status / separation from Product -----------


def test_digitized_product_default_review_status(db_session):
    job = DigitizationJob()
    db_session.add(job)
    db_session.commit()

    dp = DigitizedProduct(job_id=job.id, name_en="Item")
    db_session.add(dp)
    db_session.commit()

    assert dp.review_status == ReviewStatus.DRAFT
    assert dp.needs_review is True
    assert dp.product_id is None
    assert dp.product is None


def test_digitized_product_review_status_transitions(db_session):
    job = DigitizationJob()
    db_session.add(job)
    db_session.commit()

    dp = DigitizedProduct(
        job_id=job.id, name_en="Item", review_status=ReviewStatus.APPROVED
    )
    db_session.add(dp)
    db_session.commit()

    assert dp.review_status == ReviewStatus.APPROVED


def test_digitized_product_can_link_to_approved_product(db_session):
    job = DigitizationJob()
    db_session.add(job)
    db_session.commit()

    product = make_product(db_session, sku="APPROVED-1")

    dp = DigitizedProduct(
        job_id=job.id,
        name_en="Item",
        review_status=ReviewStatus.APPROVED,
        product_id=product.id,
    )
    db_session.add(dp)
    db_session.commit()

    assert dp.product is product
    assert product.digitized_products == [dp]


# --- Order / OrderItem relationships and constraints ---------------------


def test_order_order_items_relationship(db_session):
    order = make_order(db_session, order_number="ORD-1")

    item = OrderItem(
        order_id=order.id,
        product_name="Almonds 500g",
        quantity=2,
        unit_price=Decimal("5.00"),
        line_total=Decimal("10.00"),
    )
    db_session.add(item)
    db_session.commit()

    assert order.items == [item]
    assert item.order is order


def test_order_number_unique(db_session):
    make_order(db_session, order_number="ORD-DUP")

    db_session.add(
        Order(
            order_number="ORD-DUP",
            customer_name="B",
            customer_phone="2",
            delivery_address="x",
            delivery_area="y",
            subtotal=Decimal("1"),
            total=Decimal("1"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_order_item_quantity_must_be_positive_db(db_session):
    order = make_order(db_session, order_number="ORD-Q1")

    db_session.add(
        OrderItem(
            order_id=order.id,
            product_name="X",
            quantity=0,
            unit_price=Decimal("1"),
            line_total=Decimal("0"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_order_item_quantity_schema_validation():
    with pytest.raises(ValidationError):
        OrderItemCreate(
            order_id=uuid.uuid4(),
            product_name="X",
            quantity=0,
            unit_price=Decimal("1"),
            line_total=Decimal("0"),
        )
    with pytest.raises(ValidationError):
        OrderItemCreate(
            order_id=uuid.uuid4(),
            product_name="X",
            quantity=-1,
            unit_price=Decimal("1"),
            line_total=Decimal("0"),
        )


def test_order_item_snapshot_survives_product_changes(db_session):
    product = make_product(db_session, sku="SNAP-1", name_en="Almonds", price=Decimal("5.00"))
    order = make_order(db_session, order_number="SNAP-ORD-1")

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name=product.name_en,
        quantity=1,
        unit_price=product.price,
        line_total=product.price,
    )
    db_session.add(item)
    db_session.commit()

    product.name_en = "Roasted Almonds"
    product.price = Decimal("8.00")
    db_session.commit()

    assert item.product_name == "Almonds"
    assert item.unit_price == Decimal("5.00")


def test_order_item_survives_product_deletion(db_session):
    product = make_product(db_session, sku="SNAP-2")
    original_name = product.name_en
    original_price = product.price
    order = make_order(db_session, order_number="SNAP-ORD-2")

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name=product.name_en,
        quantity=1,
        unit_price=product.price,
        line_total=product.price,
    )
    db_session.add(item)
    db_session.commit()

    _ = product.order_items  # load so the ORM can null the FK on delete
    db_session.delete(product)
    db_session.commit()
    db_session.refresh(item)

    assert item.product_id is None
    assert item.product_name == original_name
    assert item.unit_price == original_price


# --- Enum values -----------------------------------------------------------


def test_enum_values():
    assert StockStatus.IN_STOCK.value == "in_stock"
    assert StockStatus.LOW_STOCK.value == "low_stock"
    assert StockStatus.OUT_OF_STOCK.value == "out_of_stock"

    assert {s.value for s in DigitizationJobStatus} == {
        "pending", "processing", "completed", "failed",
    }
    assert {s.value for s in ReviewStatus} == {
        "draft", "approved", "rejected", "merged",
    }
    assert {s.value for s in OrderStatus} == {
        "pending", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled",
    }


# --- Timestamps --------------------------------------------------------


def test_timestamps_are_timezone_aware(db_session):
    product = make_product(db_session, sku="TS-1")

    assert product.created_at.tzinfo is not None
    assert product.updated_at.tzinfo is not None


def test_updated_at_changes_on_update(db_session):
    product = make_product(db_session, sku="TS-2")
    original_updated_at = product.updated_at

    product.price = Decimal("6.00")
    db_session.commit()

    assert product.updated_at >= original_updated_at


def test_order_item_has_created_at_but_no_updated_at(db_session):
    order = make_order(db_session, order_number="TS-ORD")
    item = OrderItem(
        order_id=order.id,
        product_name="X",
        quantity=1,
        unit_price=Decimal("1"),
        line_total=Decimal("1"),
    )
    db_session.add(item)
    db_session.commit()

    assert item.created_at is not None
    assert item.created_at.tzinfo is not None
    assert not hasattr(item, "updated_at")
