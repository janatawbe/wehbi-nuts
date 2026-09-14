"""Tests for the Milestone 7 dev-convenience category seed script."""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.models.enums import SellingMode
from app.scripts.seed_categories import INITIAL_CATEGORIES, seed_categories


def test_seed_categories_creates_the_full_initial_set_on_an_empty_database(db_session: Session):
    created, already_present = seed_categories(db_session)

    assert len(created) == len(INITIAL_CATEGORIES)
    assert already_present == []
    assert db_session.query(Category).count() == len(INITIAL_CATEGORIES)

    slugs = {c.slug for c in created}
    assert slugs == {slug for _, _, slug in INITIAL_CATEGORIES}
    for category in created:
        assert category.name_en
        assert category.name_ar


def test_seed_categories_is_idempotent(db_session: Session):
    first_created, first_already_present = seed_categories(db_session)
    assert len(first_created) == len(INITIAL_CATEGORIES)
    assert first_already_present == []

    second_created, second_already_present = seed_categories(db_session)

    assert second_created == []
    assert set(second_already_present) == {slug for _, _, slug in INITIAL_CATEGORIES}
    # No duplicates were created -- still exactly one row per category.
    assert db_session.query(Category).count() == len(INITIAL_CATEGORIES)


def test_seed_categories_never_touches_a_pre_existing_category_with_the_same_slug(
    db_session: Session,
):
    custom = Category(name_en="My Custom Nuts Label", name_ar="مخصص", slug="nuts")
    db_session.add(custom)
    db_session.commit()

    created, already_present = seed_categories(db_session)

    assert "nuts" not in {c.slug for c in created}
    assert "nuts" in already_present
    db_session.refresh(custom)
    assert custom.name_en == "My Custom Nuts Label"  # untouched, not overwritten

    # Every OTHER initial category was still created normally.
    assert len(created) == len(INITIAL_CATEGORIES) - 1
    assert db_session.query(Category).count() == len(INITIAL_CATEGORIES)


def test_seed_categories_partial_seed_only_fills_the_gap(db_session: Session):
    db_session.add(Category(name_en="Coffee", name_ar="قهوة", slug="coffee"))
    db_session.commit()

    created, already_present = seed_categories(db_session)

    assert already_present == ["coffee"]
    assert len(created) == len(INITIAL_CATEGORIES) - 1
    assert db_session.query(Category).count() == len(INITIAL_CATEGORIES)


def test_a_seeded_category_unblocks_end_to_end_approval(client: TestClient, db_session: Session):
    """The original problem this script fixes: on a fresh database with no
    categories, a product could never be approved (Category is required).
    Seeding, then picking a seeded category, must actually unblock it."""
    created, _ = seed_categories(db_session)
    nuts_category = next(c for c in created if c.slug == "nuts")

    job = DigitizationJob()
    db_session.add(job)
    db_session.commit()
    candidate = DigitizedProduct(
        job_id=job.id,
        name_en="Roasted Almonds",
        name_ar="لوز",
        crop_image="abc123.jpg",
        selling_mode=SellingMode.UNIT,
        price=Decimal("5.00"),
        category_id=nuts_category.id,
    )
    db_session.add(candidate)
    db_session.commit()

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 200
    assert response.json()["category_id"] == str(nuts_category.id)
