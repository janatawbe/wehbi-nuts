"""Tests for the DEVELOPMENT-ONLY generate_demo_product_images script. NO
real network call is EVER made here -- AIDemoCatalogImageGenerator is
always monkeypatched to a stub."""
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import app.scripts.generate_demo_product_images as script
from app.models.category import Category
from app.models.product import Product


def make_category(db: Session, slug: str = "coffee") -> Category:
    category = Category(name_en="Coffee", name_ar="قهوة", slug=slug)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def make_demo_product(db: Session, **overrides) -> Product:
    category = overrides.pop("category", None) or make_category(db)
    defaults = dict(
        sku="WN-DEMO-COFFEE-01",
        name_en="Lebanese Coffee",
        name_ar="قهوة لبنانية",
        description_en="Traditional Lebanese coffee.",
        description_ar="قهوة لبنانية تقليدية.",
        category_id=category.id,
        unit="unit",
        weight=Decimal("0.250"),
        price=Decimal("9.00"),
        needs_review=False,
    )
    defaults.update(overrides)
    product = Product(**defaults)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


class StubGenerator:
    """Stands in for AIDemoCatalogImageGenerator -- records the context it
    was called with and returns a tiny valid JPEG, never touching the
    network."""

    instances: list["StubGenerator"] = []

    def __init__(self, api_key: str, model_name: str) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.calls: list = []
        StubGenerator.instances.append(self)

    def generate(self, context) -> bytes:
        self.calls.append(context)
        from io import BytesIO

        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (100, 100), (255, 255, 255)).save(buffer, format="JPEG")
        return buffer.getvalue()


@pytest.fixture(autouse=True)
def _reset_stub_instances():
    StubGenerator.instances = []
    yield
    StubGenerator.instances = []


@pytest.fixture()
def patched_generator(monkeypatch):
    monkeypatch.setattr(script, "AIDemoCatalogImageGenerator", StubGenerator)
    return StubGenerator


# --- SKU eligibility guards --------------------------------------------------


def test_refuses_a_sku_without_the_demo_prefix(db_session):
    with pytest.raises(script.DemoProductNotEligibleError, match="only WN-DEMO-"):
        script.load_demo_product(db_session, "REAL-PRODUCT-01", force=False)


def test_refuses_an_unknown_sku(db_session):
    with pytest.raises(script.DemoProductNotEligibleError, match="No product found"):
        script.load_demo_product(db_session, "WN-DEMO-DOES-NOT-EXIST", force=False)


def test_refuses_a_product_that_already_has_an_image_without_force(db_session):
    make_demo_product(db_session, image="/api/digitizer/jobs/x/media/refined/already.jpg")

    with pytest.raises(script.DemoProductNotEligibleError, match="already has an image"):
        script.load_demo_product(db_session, "WN-DEMO-COFFEE-01", force=False)


def test_force_allows_a_product_that_already_has_an_image(db_session):
    make_demo_product(db_session, image="/api/digitizer/jobs/x/media/refined/already.jpg")

    product = script.load_demo_product(db_session, "WN-DEMO-COFFEE-01", force=True)

    assert product.sku == "WN-DEMO-COFFEE-01"


def test_loads_an_eligible_demo_product_with_no_image(db_session):
    make_demo_product(db_session)

    product = script.load_demo_product(db_session, "WN-DEMO-COFFEE-01", force=False)

    assert product.name_en == "Lebanese Coffee"


# --- generate_and_save: exactly one call, only `image` is written -----------


def test_generate_and_save_makes_exactly_one_call(db_session, tmp_path, monkeypatch, patched_generator):
    monkeypatch.setattr(script, "get_upload_root", lambda: tmp_path / "uploads" / "digitizer")
    product = make_demo_product(db_session)

    script.generate_and_save(db_session, product, "google/gemini-2.5-flash-image", "fake-key")

    assert len(StubGenerator.instances) == 1
    assert len(StubGenerator.instances[0].calls) == 1


def test_generate_and_save_only_updates_the_image_field(db_session, tmp_path, monkeypatch, patched_generator):
    monkeypatch.setattr(script, "get_upload_root", lambda: tmp_path / "uploads" / "digitizer")
    product = make_demo_product(db_session)
    original_name, original_price, original_sku, original_desc = (
        product.name_en,
        product.price,
        product.sku,
        product.description_en,
    )

    script.generate_and_save(db_session, product, "google/gemini-2.5-flash-image", "fake-key")

    assert product.name_en == original_name
    assert product.price == original_price
    assert product.sku == original_sku
    assert product.description_en == original_desc
    assert product.image is not None


def test_generate_and_save_stores_under_the_shared_demo_namespace(
    db_session, tmp_path, monkeypatch, patched_generator
):
    upload_root = tmp_path / "uploads" / "digitizer"
    monkeypatch.setattr(script, "get_upload_root", lambda: upload_root)
    product = make_demo_product(db_session)

    image_url = script.generate_and_save(db_session, product, "google/gemini-2.5-flash-image", "fake-key")

    assert image_url.startswith(f"/api/digitizer/jobs/{script.DEMO_MEDIA_NAMESPACE_ID}/media/refined/")
    saved_files = list((upload_root / str(script.DEMO_MEDIA_NAMESPACE_ID) / "products" / "refined").iterdir())
    assert len(saved_files) == 1


def test_generate_and_save_passes_product_context_to_the_generator(
    db_session, tmp_path, monkeypatch, patched_generator
):
    monkeypatch.setattr(script, "get_upload_root", lambda: tmp_path / "uploads" / "digitizer")
    product = make_demo_product(db_session)

    script.generate_and_save(db_session, product, "google/gemini-2.5-flash-image", "fake-key")

    context = StubGenerator.instances[0].calls[0]
    assert context.name_en == "Lebanese Coffee"
    assert context.category == "Coffee"
    assert context.selling_mode == "unit"


# --- dry-run (default, no --yes): never touches the network -----------------


def test_dry_run_plan_never_instantiates_the_generator(db_session, patched_generator, capsys):
    product = make_demo_product(db_session)

    script._print_plan(product, "google/gemini-2.5-flash-image")

    assert StubGenerator.instances == []
    output = capsys.readouterr().out
    assert "No API call was made" in output
    assert "exactly 1" in output
    assert "Lebanese Coffee" in output


def test_dry_run_plan_prints_the_final_prompt(db_session, capsys):
    product = make_demo_product(db_session)

    script._print_plan(product, "google/gemini-2.5-flash-image")

    output = capsys.readouterr().out
    assert "STYLE (must match the rest of the catalog)" in output
    assert "Final prompt to be sent" in output
