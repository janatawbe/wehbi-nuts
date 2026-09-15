"""DEVELOPMENT-ONLY: clear local catalog/order/digitizer data and reseed a
clean 18-product demo catalog for the customer storefront.

*** THIS SCRIPT DELETES DATA. NEVER RUN IT AGAINST A PRODUCTION DATABASE. ***

What this does NOT touch:
  - The `categories` table itself -- every existing Category row (the seven
    official storefront categories plus any dev-only leftovers) is kept
    exactly as-is. Nothing is created, renamed, or deleted here; see
    app.scripts.align_storefront_categories for that.
  - The database schema / Alembic migration history -- no DDL, no new
    migration, no `alembic downgrade`.

What this DOES clear (in FK-safe order, real dev/demo data only):
  1. digitized_product_duplicate_matches
  2. digitized_products
  3. digitization_jobs
  4. order_items
  5. orders
  6. products
Then it seeds exactly 18 demo Products (3 each for Coffee, Dried Fruits,
Nuts, Snacks & Sweets, Seeds, Spice & Herbs -- deliberately none for Gifts
yet), linked to the existing Category rows by slug.

Safety:
  - Running with no flags (or --dry-run) NEVER touches the database -- it
    only prints the exact plan (current row counts to be cleared/preserved,
    and the 18 products that would be seeded).
  - The actual destructive clear + seed only runs with the explicit --yes
    flag, and only from a deliberate manual invocation -- nothing in the
    app imports or calls this at startup or from any request handler.
  - Seeding is idempotent: matched by `sku` (unique at the DB level), so
    running --yes again after the clear step already ran is a safe no-op
    for any demo product that already exists (it does NOT touch orders/
    digitizer data again since those deletes are unconditional -- only run
    --yes when you actually intend to clear them).

Usage (from `server/`, venv activated, DATABASE_URL configured):
    python -m app.scripts.reset_dev_catalog              # prints the plan only
    python -m app.scripts.reset_dev_catalog --yes         # actually clears + seeds
"""
import argparse
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.models.digitized_product_duplicate_match import DigitizedProductDuplicateMatch
from app.models.enums import StockStatus
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product

# Tables cleared, in FK-safe dependency order. Categories are deliberately
# absent from this list -- see module docstring.
_CLEAR_ORDER: list[type] = [
    DigitizedProductDuplicateMatch,
    DigitizedProduct,
    DigitizationJob,
    OrderItem,
    Order,
    Product,
]

# (sku, name_en, name_ar, description_en, description_ar, category_slug,
#  selling_mode, price, package_weight_kg)
#
# selling_mode/package_weight are NOT their own Product columns -- the
# storefront reads them from Product's pre-existing `unit` and `weight`
# columns respectively (see app.schemas.storefront.StorefrontProductRead
# and app.services.storefront_service._to_storefront_product):
#   - `unit`   holds the string "weight" or "unit" (the selling mode)
#   - `weight` holds the package weight in kilograms, ONLY for unit-mode
#     products; always None for weight-mode (loose/bulk) products.
# "weight" mode: `price` is per kilogram. "unit" mode: `price` is the fixed
# price for one package.
DEMO_PRODUCTS: list[tuple[str, str, str, str, str, str, str, Decimal, Decimal | None]] = [
    # -- Coffee (packaged bags, sold per unit) --
    (
        "WN-DEMO-COFFEE-01", "Lebanese Coffee", "قهوة لبنانية",
        "Traditional Lebanese coffee, finely ground and roasted with cardamom for an aromatic, rich cup.",
        "قهوة لبنانية تقليدية، مطحونة ناعمة ومحمصة مع الهيل لكوب غني وعطري.",
        "coffee", "unit", Decimal("9.00"), Decimal("0.250"),
    ),
    (
        "WN-DEMO-COFFEE-02", "Brazilian Coffee", "قهوة برازيلية",
        "Smooth, medium-roast Brazilian coffee beans with notes of chocolate and caramel.",
        "حبوب قهوة برازيلية محمصة بدرجة متوسطة، ناعمة المذاق مع لمسات من الشوكولاتة والكراميل.",
        "coffee", "unit", Decimal("8.50"), Decimal("0.250"),
    ),
    (
        "WN-DEMO-COFFEE-03", "Espresso Blend", "مزيج إسبريسو",
        "A bold, dark-roast espresso blend crafted for a rich crema and full-bodied flavor.",
        "مزيج إسبريسو غامق التحميص بنكهة قوية ورغوة كريمية غنية.",
        "coffee", "unit", Decimal("10.50"), Decimal("0.250"),
    ),
    # -- Dried Fruits (loose bulk, sold per kg) --
    (
        "WN-DEMO-DRIEDFRUIT-01", "Dried Apricots", "مشمش مجفف",
        "Naturally sweet, sun-dried apricots -- soft, chewy, and free of added sugar.",
        "مشمش مجفف طبيعي تحت الشمس، طري وحلو المذاق بدون سكر مضاف.",
        "dried-fruits", "weight", Decimal("9.00"), None,
    ),
    (
        "WN-DEMO-DRIEDFRUIT-02", "Raisins", "زبيب",
        "Sun-dried golden raisins with a naturally sweet, chewy bite.",
        "زبيب ذهبي مجفف تحت الشمس، حلو المذاق وطري القوام.",
        "dried-fruits", "weight", Decimal("7.50"), None,
    ),
    (
        "WN-DEMO-DRIEDFRUIT-03", "Dried Cranberries", "توت بري مجفف",
        "Tangy-sweet dried cranberries, perfect for snacking or baking.",
        "توت بري مجفف بمذاق حلو ومنعش، مثالي للتسلية أو الخبز.",
        "dried-fruits", "weight", Decimal("10.00"), None,
    ),
    # -- Nuts (loose bulk, sold per kg) --
    (
        "WN-DEMO-NUTS-01", "Roasted Pistachios", "فستق محمص",
        "Lightly salted, freshly roasted pistachios with a satisfying crunch.",
        "فستق محمص طازج ومملح بخفة، بقرمشة لذيذة.",
        "nuts", "weight", Decimal("18.00"), None,
    ),
    (
        "WN-DEMO-NUTS-02", "Roasted Cashews", "كاجو محمص",
        "Whole roasted cashews, buttery and lightly salted.",
        "كاجو محمص كامل الحبة، بطعم زبدي ومملح بخفة.",
        "nuts", "weight", Decimal("16.00"), None,
    ),
    (
        "WN-DEMO-NUTS-03", "Roasted Almonds", "لوز محمص",
        "Crunchy roasted almonds, lightly salted for a classic everyday snack.",
        "لوز محمص ومقرمش، مملح بخفة لوجبة خفيفة يومية.",
        "nuts", "weight", Decimal("14.00"), None,
    ),
    # -- Snacks & Sweets (packaged, sold per unit) --
    (
        "WN-DEMO-SNACKS-01", "Fruit Jelly Candies", "حلوى جيلي بالفواكه",
        "Soft and colorful fruit-flavored jelly candies with a sweet, chewy texture.",
        "حلوى جيلي طرية وملونة بنكهات الفواكه وقوام حلو ومطاطي.",
        "snacks-sweets", "weight", Decimal("8.00"), None,
    ),
    (
        "WN-DEMO-SNACKS-02", "Chocolate Coated Almonds", "لوز مغطى بالشوكولاتة",
        "Roasted almonds enrobed in smooth milk chocolate.",
        "لوز محمص مغطى بطبقة ناعمة من شوكولاتة الحليب.",
        "snacks-sweets", "unit", Decimal("7.00"), Decimal("0.200"),
    ),
    (
        "WN-DEMO-SNACKS-03", "Pistachio Chocolate Bites", "قطع فستق بالشوكولاتة",
        "Bite-sized pistachio pieces dipped in rich dark chocolate.",
        "قطع صغيرة من الفستق مغموسة بشوكولاتة داكنة غنية.",
        "snacks-sweets", "unit", Decimal("8.50"), Decimal("0.200"),
    ),
    # -- Seeds (loose bulk, sold per kg) --
    (
        "WN-DEMO-SEEDS-01", "Sunflower Seeds", "بذور دوار الشمس",
        "Roasted sunflower seeds in the shell, lightly salted.",
        "بذور دوار الشمس المحمصة بقشرها، مملحة بخفة.",
        "seeds", "weight", Decimal("6.00"), None,
    ),
    (
        "WN-DEMO-SEEDS-02", "Pumpkin Seeds", "بذور اليقطين",
        "Roasted pumpkin seeds, a crunchy and wholesome snack.",
        "بذور يقطين محمصة، وجبة خفيفة مقرمشة وصحية.",
        "seeds", "weight", Decimal("9.50"), None,
    ),
    (
        "WN-DEMO-SEEDS-03", "Mixed Seeds", "خلطة بذور",
        "A wholesome mix of roasted sunflower and pumpkin seeds.",
        "خلطة صحية من بذور دوار الشمس واليقطين المحمصة.",
        "seeds", "weight", Decimal("8.00"), None,
    ),
    # -- Spice & Herbs (loose bulk, sold per kg) --
    (
        "WN-DEMO-SPICE-01", "Ground Cinnamon", "قرفة مطحونة",
        "Warm, fragrant ground cinnamon, freshly milled.",
        "قرفة مطحونة طازجة بنكهة دافئة وعطرية.",
        "spice-herbs", "weight", Decimal("12.00"), None,
    ),
    (
        "WN-DEMO-SPICE-02", "Paprika", "بابريكا",
        "Vibrant, mildly sweet paprika for everyday cooking.",
        "بابريكا حمراء زاهية بنكهة معتدلة الحلاوة للاستخدام اليومي.",
        "spice-herbs", "weight", Decimal("11.00"), None,
    ),
    (
        "WN-DEMO-SPICE-03", "Seven Spice", "بهارات مشكلة (سبعة بهارات)",
        "Wehbi Nuts' own seven-spice blend, a Lebanese kitchen essential.",
        "خلطة السبعة بهارات الخاصة بوهبي نتس، عنصر أساسي في المطبخ اللبناني.",
        "spice-herbs", "weight", Decimal("13.00"), None,
    ),
]


def plan(db: Session) -> dict[str, object]:
    """Read-only: never modifies the database. Returns the exact counts
    that would be cleared/preserved and which demo products would be
    newly created vs. already present, for display before any --yes run."""
    to_clear = {model.__tablename__: db.query(model).count() for model in _CLEAR_ORDER}

    categories = db.scalars(select(Category).order_by(Category.slug)).all()
    preserved_categories = [(c.slug, c.name_en) for c in categories]

    existing_skus = {row[0] for row in db.query(Product.sku).all()}
    to_create = [row[0] for row in DEMO_PRODUCTS if row[0] not in existing_skus]
    already_present = [row[0] for row in DEMO_PRODUCTS if row[0] in existing_skus]

    return {
        "to_clear": to_clear,
        "preserved_categories": preserved_categories,
        "demo_products_to_create": to_create,
        "demo_products_already_present": already_present,
    }


def clear_dev_data(db: Session) -> dict[str, int]:
    """Deletes all rows from every table in _CLEAR_ORDER, in that order.
    Never touches `categories`. Commits once at the end."""
    deleted: dict[str, int] = {}
    for model in _CLEAR_ORDER:
        count = db.query(model).delete(synchronize_session=False)
        deleted[model.__tablename__] = count
    db.commit()
    return deleted


def seed_demo_products(db: Session) -> tuple[list[Product], list[str]]:
    """Creates whichever DEMO_PRODUCTS don't already exist (matched by
    `sku`). Returns (created, already_present_skus). Never updates or
    deletes an existing product with a matching SKU."""
    categories_by_slug = {c.slug: c for c in db.scalars(select(Category)).all()}
    existing_skus = {row[0] for row in db.query(Product.sku).all()}

    created: list[Product] = []
    already_present: list[str] = []

    for (
        sku, name_en, name_ar, description_en, description_ar,
        category_slug, selling_mode, price, package_weight,
    ) in DEMO_PRODUCTS:
        if sku in existing_skus:
            already_present.append(sku)
            continue

        category = categories_by_slug.get(category_slug)
        if category is None:
            raise RuntimeError(
                f"Cannot seed '{name_en}' ({sku}): no category with slug '{category_slug}' exists. "
                "Run `python -m app.scripts.align_storefront_categories` first."
            )

        product = Product(
            sku=sku,
            name_en=name_en,
            name_ar=name_ar,
            description_en=description_en,
            description_ar=description_ar,
            category_id=category.id,
            unit=selling_mode,
            weight=package_weight,
            price=price,
            stock_status=StockStatus.IN_STOCK,
            needs_review=False,
        )
        db.add(product)
        created.append(product)

    if created:
        db.commit()
        for product in created:
            db.refresh(product)

    return created, already_present


def _print_plan(result: dict[str, object]) -> None:
    print("=== DEVELOPMENT reset plan for Wehbi Nuts (no changes made yet) ===\n")

    print("Will CLEAR (dev/demo data only):")
    for table, count in result["to_clear"].items():  # type: ignore[union-attr]
        print(f"  - {table}: {count} row(s)")

    print("\nWill PRESERVE (untouched):")
    print(f"  - categories: {len(result['preserved_categories'])} row(s), including all 7 official categories")
    for slug, name in result["preserved_categories"]:  # type: ignore[union-attr]
        print(f"      · {name} ({slug})")

    print(f"\nWill CREATE {len(result['demo_products_to_create'])} demo product(s):")
    for sku, name_en, *_ in DEMO_PRODUCTS:
        if sku in result["demo_products_to_create"]:  # type: ignore[operator]
            print(f"  - {sku}: {name_en}")

    if result["demo_products_already_present"]:
        print(f"\nAlready present, would be skipped ({len(result['demo_products_already_present'])}):")
        for sku in result["demo_products_already_present"]:  # type: ignore[union-attr]
            print(f"  - {sku}")

    print("\nNo destructive action was taken. Re-run with --yes to actually clear and seed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually clear dev data and seed the demo catalog. Without this flag, only prints the plan.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.yes:
            _print_plan(plan(db))
            return

        deleted = clear_dev_data(db)
        created, already_present = seed_demo_products(db)

        print("=== Cleared ===")
        for table, count in deleted.items():
            print(f"  - {table}: {count} row(s) deleted")

        print(f"\n=== Seeded {len(created)} demo product(s) ===")
        for product in created:
            print(f"  - {product.sku}: {product.name_en}")

        if already_present:
            print(f"\nAlready present, skipped ({len(already_present)}): {', '.join(already_present)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
