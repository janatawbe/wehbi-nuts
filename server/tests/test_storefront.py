"""Tests for the Milestone 9 customer storefront API.

Never touches any AI-dependent endpoint -- every Product/Category here is
created directly via the ORM, so this whole suite makes zero AI calls and
needs no OpenRouter dependency override.
"""
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.models.enums import ReviewStatus, SellingMode, StockStatus
from app.models.product import Product
from app.scripts.align_storefront_categories import OFFICIAL_CATEGORY_SLUGS


def make_category(db_session: Session, **overrides) -> Category:
    defaults = dict(name_en="Nuts", name_ar="مكسرات", slug="nuts")
    defaults.update(overrides)
    category = Category(**defaults)
    db_session.add(category)
    db_session.commit()
    return category


def make_product(db_session: Session, **overrides) -> Product:
    defaults = dict(
        sku=f"SKU-{uuid.uuid4().hex[:8]}",
        name_en="Roasted Almonds",
        name_ar="لوز محمص",
        price=Decimal("18.00"),
        unit="weight",
        needs_review=False,
    )
    defaults.update(overrides)
    product = Product(**defaults)
    db_session.add(product)
    db_session.commit()
    return product


# --- Categories --------------------------------------------------------


def test_categories_returns_only_the_seven_official_categories_in_order(client: TestClient, db_session: Session):
    for slug in OFFICIAL_CATEGORY_SLUGS:
        db_session.add(Category(name_en=slug, name_ar=slug, slug=slug))
    # A dormant, non-official category that must never appear here.
    db_session.add(Category(name_en="Spreads", name_ar="دهانات", slug="spreads"))
    db_session.commit()

    response = client.get("/api/storefront/categories")

    assert response.status_code == 200
    body = response.json()
    assert [c["slug"] for c in body] == OFFICIAL_CATEGORY_SLUGS
    assert "spreads" not in [c["slug"] for c in body]


def test_categories_skips_an_official_slug_that_does_not_exist_yet(client: TestClient, db_session: Session):
    db_session.add(Category(name_en="Nuts", name_ar="مكسرات", slug="nuts"))
    db_session.commit()

    response = client.get("/api/storefront/categories")

    assert response.status_code == 200
    assert [c["slug"] for c in response.json()] == ["nuts"]


# --- Product listing -----------------------------------------------------


def test_list_products_returns_customer_safe_fields_only(client: TestClient, db_session: Session):
    category = make_category(db_session)
    make_product(
        db_session,
        name_en="Roasted Almonds",
        name_ar="لوز محمص",
        category_id=category.id,
        brand="Wehbi",
        price=Decimal("20.00"),
        unit="weight",
        stock_status=StockStatus.IN_STOCK,
        image="/api/digitizer/jobs/abc/media/refined/x.jpg",
    )

    response = client.get("/api/storefront/products")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    product = body[0]
    assert product["name_en"] == "Roasted Almonds"
    assert product["name_ar"] == "لوز محمص"
    assert product["price"] == "20.00"
    assert product["selling_mode"] == "weight"
    assert product["category"]["slug"] == "nuts"
    assert product["image"] == "/api/digitizer/jobs/abc/media/refined/x.jpg"
    # Never exposed to customers.
    for internal_field in ("sku", "barcode", "ai_confidence", "ai_raw_result", "needs_review", "source_image"):
        assert internal_field not in product


def test_list_products_excludes_products_that_need_review(client: TestClient, db_session: Session):
    make_product(db_session, name_en="Visible", needs_review=False)
    make_product(db_session, name_en="Hidden", needs_review=True)

    response = client.get("/api/storefront/products")

    names = [p["name_en"] for p in response.json()]
    assert names == ["Visible"]


def test_list_products_includes_out_of_stock_products_marked_unavailable_not_hidden(
    client: TestClient, db_session: Session
):
    make_product(db_session, name_en="Sold Out Item", stock_status=StockStatus.OUT_OF_STOCK)

    response = client.get("/api/storefront/products")

    body = response.json()
    assert len(body) == 1
    assert body[0]["stock_status"] == "out_of_stock"


def test_list_products_filters_by_category_slug(client: TestClient, db_session: Session):
    nuts = make_category(db_session, name_en="Nuts", name_ar="مكسرات", slug="nuts")
    coffee = make_category(db_session, name_en="Coffee", name_ar="قهوة", slug="coffee")
    make_product(db_session, name_en="Almonds", category_id=nuts.id)
    make_product(db_session, name_en="Beans", category_id=coffee.id)

    response = client.get("/api/storefront/products", params={"category": "coffee"})

    names = [p["name_en"] for p in response.json()]
    assert names == ["Beans"]


def test_list_products_search_matches_english_name(client: TestClient, db_session: Session):
    make_product(db_session, name_en="Roasted Almonds")
    make_product(db_session, name_en="Turkish Coffee")

    response = client.get("/api/storefront/products", params={"search": "almond"})

    names = [p["name_en"] for p in response.json()]
    assert names == ["Roasted Almonds"]


def test_list_products_search_matches_arabic_name(client: TestClient, db_session: Session):
    make_product(db_session, name_en="Roasted Almonds", name_ar="لوز محمص")
    make_product(db_session, name_en="Turkish Coffee", name_ar="قهوة تركية")

    response = client.get("/api/storefront/products", params={"search": "لوز"})

    names = [p["name_en"] for p in response.json()]
    assert names == ["Roasted Almonds"]


def test_list_products_search_is_case_insensitive(client: TestClient, db_session: Session):
    make_product(db_session, name_en="Roasted Almonds")

    response = client.get("/api/storefront/products", params={"search": "ALMOND"})

    assert len(response.json()) == 1


def test_list_products_respects_limit_for_a_curated_featured_subset(client: TestClient, db_session: Session):
    for i in range(5):
        make_product(db_session, name_en=f"Product {i}")

    response = client.get("/api/storefront/products", params={"limit": 2})

    assert len(response.json()) == 2


def test_list_products_on_an_empty_catalog_returns_an_empty_list(client: TestClient):
    response = client.get("/api/storefront/products")

    assert response.status_code == 200
    assert response.json() == []


# --- Product detail --------------------------------------------------------


def test_get_product_returns_full_customer_safe_detail(client: TestClient, db_session: Session):
    category = make_category(db_session)
    product = make_product(
        db_session,
        name_en="Roasted Almonds",
        description_en="Freshly roasted daily.",
        category_id=category.id,
        unit="weight",
        price=Decimal("20.00"),
    )

    response = client.get(f"/api/storefront/products/{product.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(product.id)
    assert body["description_en"] == "Freshly roasted daily."
    assert body["category"]["name_en"] == "Nuts"


def test_get_product_shows_package_weight_for_unit_mode(client: TestClient, db_session: Session):
    product = make_product(db_session, unit="unit", weight=Decimal("0.500"), price=Decimal("5.00"))

    response = client.get(f"/api/storefront/products/{product.id}")

    body = response.json()
    assert body["selling_mode"] == "unit"
    assert body["package_weight"] == "0.500"


def test_get_product_unknown_id_returns_404(client: TestClient):
    response = client.get(f"/api/storefront/products/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_product_that_needs_review_returns_404(client: TestClient, db_session: Session):
    product = make_product(db_session, needs_review=True)

    response = client.get(f"/api/storefront/products/{product.id}")

    assert response.status_code == 404


# --- Storefront never reads from DigitizedProduct ---------------------------


def test_a_rejected_digitized_product_never_appears_in_the_storefront(client: TestClient, db_session: Session):
    """A rejected/pending DigitizedProduct never gets a linked Product row
    at all (Milestone 7), so it can never reach the storefront -- this
    confirms the storefront reads Product, never DigitizedProduct."""
    job = DigitizationJob()
    db_session.add(job)
    db_session.commit()
    rejected = DigitizedProduct(
        job_id=job.id,
        name_en="Rejected Candidate",
        name_ar="مرفوض",
        selling_mode=SellingMode.UNIT,
        price=Decimal("5.00"),
        review_status=ReviewStatus.REJECTED,
    )
    db_session.add(rejected)
    db_session.commit()

    response = client.get("/api/storefront/products")

    names = [p["name_en"] for p in response.json()]
    assert "Rejected Candidate" not in names
