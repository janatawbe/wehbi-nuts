"""Tests for the Milestone 9 dev category-alignment script."""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.scripts.align_storefront_categories import (
    OFFICIAL_CATEGORY_SLUGS,
    align_storefront_categories,
)
from app.scripts.seed_categories import seed_categories


def make_product(db_session: Session, **overrides) -> Product:
    defaults = dict(sku=f"SKU-{overrides.get('name_en', 'x')}", name_en="Item", name_ar="عنصر", price=Decimal("1.00"))
    defaults.update(overrides)
    product = Product(**defaults)
    db_session.add(product)
    db_session.commit()
    return product


def test_aligns_a_freshly_seeded_database_to_the_seven_official_categories(db_session: Session):
    seed_categories(db_session)

    changes = align_storefront_categories(db_session)

    assert changes  # something needed fixing on the fresh dev seed
    slugs = {c.slug for c in db_session.query(Category).all()}
    for official_slug in OFFICIAL_CATEGORY_SLUGS:
        assert official_slug in slugs


def test_is_idempotent(db_session: Session):
    seed_categories(db_session)
    first = align_storefront_categories(db_session)
    assert first

    second = align_storefront_categories(db_session)

    assert second == []


def test_never_deletes_a_category_row(db_session: Session):
    seed_categories(db_session)
    before_count = db_session.query(Category).count()

    align_storefront_categories(db_session)

    after_count = db_session.query(Category).count()
    # Only "Gifts" is newly created; nothing pre-existing was removed.
    assert after_count == before_count + 1


def test_renames_spices_and_herbs_in_place_preserving_its_id(db_session: Session):
    original = Category(name_en="Spices & Herbs", name_ar="بهارات وأعشاب", slug="spices-herbs")
    db_session.add(original)
    db_session.commit()
    original_id = original.id

    align_storefront_categories(db_session)

    refreshed = db_session.get(Category, original_id)
    assert refreshed.name_en == "Spice & Herbs"
    assert refreshed.slug == "spice-herbs"


def test_merges_snacks_into_sweets_and_chocolate_and_reassigns_its_products(db_session: Session):
    sweets = Category(name_en="Sweets & Chocolate", name_ar="حلويات وشوكولاتة", slug="sweets-chocolate")
    snacks = Category(name_en="Snacks", name_ar="وجبات خفيفة", slug="snacks")
    db_session.add_all([sweets, snacks])
    db_session.commit()
    product = make_product(db_session, name_en="Mixed Snacks", category_id=snacks.id)

    changes = align_storefront_categories(db_session)

    db_session.refresh(sweets)
    db_session.refresh(snacks)
    db_session.refresh(product)
    assert sweets.name_en == "Snacks & Sweets"
    assert sweets.slug == "snacks-sweets"
    assert product.category_id == sweets.id
    # The merged-away row is left in place, not deleted.
    assert db_session.get(Category, snacks.id) is not None
    assert any("Reassigned 1 product" in change for change in changes)


def test_never_deletes_a_dev_only_category_with_no_official_equivalent(db_session: Session):
    other = Category(name_en="Other", name_ar="أخرى", slug="other")
    spreads = Category(name_en="Spreads", name_ar="دهانات", slug="spreads")
    db_session.add_all([other, spreads])
    db_session.commit()

    align_storefront_categories(db_session)

    assert db_session.get(Category, other.id) is not None
    assert db_session.get(Category, spreads.id) is not None
    assert db_session.get(Category, other.id).name_en == "Other"


def test_creates_gifts_when_missing(db_session: Session):
    align_storefront_categories(db_session)

    gifts = db_session.query(Category).filter_by(slug="gifts").one()
    assert gifts.name_en == "Gifts"


def test_does_not_create_gifts_twice(db_session: Session):
    align_storefront_categories(db_session)
    first_count = db_session.query(Category).filter_by(slug="gifts").count()

    align_storefront_categories(db_session)

    assert db_session.query(Category).filter_by(slug="gifts").count() == first_count == 1


def test_never_touches_a_product_in_an_unrelated_category(db_session: Session):
    nuts = Category(name_en="Nuts", name_ar="مكسرات", slug="nuts")
    db_session.add(nuts)
    db_session.commit()
    product = make_product(db_session, name_en="Almonds", category_id=nuts.id)

    align_storefront_categories(db_session)

    db_session.refresh(product)
    assert product.category_id == nuts.id
