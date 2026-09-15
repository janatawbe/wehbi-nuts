"""DEVELOPMENT-ONLY: generate an AI catalog image for one seeded
`WN-DEMO-*` demo product (see app.scripts.reset_dev_catalog) using
text-to-image generation -- these products have no real source photo, so
the normal Digitizer workflow (real shop photo -> detection/crop -> AI
refinement -> review) does not apply to them and is completely untouched
by this script.

*** THIS CALLS A PAID OPENROUTER MODEL. EACH RUN WITH --yes COSTS MONEY. ***

Safety:
  - Only ever targets a product whose SKU starts with "WN-DEMO-" -- never
    a real catalog product.
  - Generates for exactly ONE product per invocation, by --sku. There is
    no --all/bulk mode; generating the remaining demo products means
    running this again, once per SKU, by deliberate choice each time.
  - Running with no flags (or --dry-run, the default) makes ZERO network
    calls -- it only prints the exact plan: model, whether the product
    already has an image, the final prompt, and where the result would be
    stored. Only --yes performs the one real API call, saves the image,
    and updates that Product's `image` field.
  - If the product already has an `image` set, this refuses to
    regenerate (and re-bill) unless --force is also passed.
  - Never touches name/price/category/description/SKU/selling_mode/or any
    other field -- only `Product.image` is ever written.
  - Nothing in the app imports or calls this at startup, during database
    seeding, during tests, or from any request handler.

Usage (from `server/`, venv activated, DATABASE_URL and
OPENROUTER_API_KEY configured):
    python -m app.scripts.generate_demo_product_images --sku WN-DEMO-COFFEE-01
    python -m app.scripts.generate_demo_product_images --sku WN-DEMO-COFFEE-01 --yes
    python -m app.scripts.generate_demo_product_images --sku WN-DEMO-COFFEE-01 --yes --force
"""
import argparse
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.product import Product
from app.services.ai.demo_catalog_image_generator import AIDemoCatalogImageGenerator
from app.services.ai.demo_catalog_image_prompt import DemoProductImageContext, build_prompt_text
from app.services.storage import get_job_refined_dir, get_upload_root, save_refined_image

# Only products with this SKU prefix may ever be targeted -- see
# app.scripts.reset_dev_catalog.DEMO_PRODUCTS. A real catalog product
# (created via the Digitizer or catalog import) never has this prefix, so
# this is a hard guard against ever generating/overwriting a real
# product's image.
DEMO_SKU_PREFIX = "WN-DEMO-"

# NOT a real DigitizationJob -- there is no job row with this id anywhere
# in the database, and none is ever created here (see module docstring:
# "Do NOT modify database schema"). This fixed, constant UUID is reused
# purely as a shared folder name and media-serving namespace: it lets
# every generated demo image reuse the exact same on-disk layout
# (storage.get_job_refined_dir/save_refined_image) and the exact same
# existing, already-safe media route (GET /api/digitizer/jobs/{job_id}/
# media/{kind}/{filename}, see api.digitizer.get_job_media) that the real
# Digitizer already uses to serve refined images -- that route resolves
# purely from the filesystem and never queries the digitization_jobs
# table, so reusing it here needs no new API route and no schema change.
DEMO_MEDIA_NAMESPACE_ID = uuid.UUID("00000000-0000-0000-0000-00000000dee0")


class DemoProductNotEligibleError(Exception):
    """Raised when --sku does not resolve to an eligible WN-DEMO-* product
    (not found, not a demo SKU, or already has an image without --force)."""


def _build_context(product: Product) -> DemoProductImageContext:
    return DemoProductImageContext(
        name_en=product.name_en,
        category=product.category.name_en if product.category else None,
        # Product.unit holds the selling_mode string ("weight"/"unit") --
        # see app.services.storefront_service._to_storefront_product for
        # the same, pre-existing mapping.
        selling_mode=product.unit,
        description_en=product.description_en,
    )


def load_demo_product(db: Session, sku: str, *, force: bool) -> Product:
    if not sku.startswith(DEMO_SKU_PREFIX):
        raise DemoProductNotEligibleError(
            f"Refusing to generate an image for '{sku}': only {DEMO_SKU_PREFIX}* demo products are eligible."
        )

    product = db.query(Product).filter(Product.sku == sku).first()
    if product is None:
        raise DemoProductNotEligibleError(f"No product found with SKU '{sku}'.")

    if product.image and not force:
        raise DemoProductNotEligibleError(
            f"Product '{sku}' already has an image ({product.image}). "
            "Pass --force to regenerate (this makes another paid API call)."
        )

    return product


def _print_plan(product: Product, model_name: str) -> None:
    context = _build_context(product)
    prompt = build_prompt_text(context)

    print("=== DEVELOPMENT demo image generation plan (no API call made yet) ===\n")
    print(f"SKU: {product.sku}")
    print(f"Product: {product.name_en}")
    print(f"Category: {context.category}")
    print(f"Selling mode: {context.selling_mode}")
    print(f"Current image field: {product.image or '(empty)'}")
    print(f"\nModel: {model_name}")
    print("Mode: text-to-image (no input_references sent -- no source photo exists)")
    print("Expected API calls: exactly 1")
    print(
        f"\nWould store at: uploads/digitizer/{DEMO_MEDIA_NAMESPACE_ID}/products/refined/<generated-uuid>.jpg"
    )
    print(f"Would update: Product.image (only) for SKU {product.sku}")
    print("\n--- Final prompt to be sent ---\n")
    print(prompt)
    print("\n--- End of prompt ---")
    print("\nNo API call was made. Re-run with --yes to actually generate and save.")


def generate_and_save(db: Session, product: Product, model_name: str, api_key: str) -> str:
    """Makes exactly one OpenRouter call, saves the resulting image under
    the shared demo-media namespace, and updates ONLY Product.image.
    Returns the saved image's public media URL."""
    generator = AIDemoCatalogImageGenerator(api_key=api_key, model_name=model_name)
    context = _build_context(product)
    image_bytes = generator.generate(context)

    upload_root = get_upload_root()
    refined_dir = get_job_refined_dir(upload_root, DEMO_MEDIA_NAMESPACE_ID)
    filename = save_refined_image(refined_dir, image_bytes)

    product.image = f"/api/digitizer/jobs/{DEMO_MEDIA_NAMESPACE_ID}/media/refined/{filename}"
    db.add(product)
    db.commit()

    return product.image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sku", required=True, help="The WN-DEMO-* product SKU to generate an image for.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually make the OpenRouter API call, save the image, and update the product. "
        "Without this flag, only prints the plan.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow regenerating an image for a product that already has one (makes another paid call).",
    )
    args = parser.parse_args()

    settings = get_settings()
    db = SessionLocal()
    try:
        product = load_demo_product(db, args.sku, force=args.force)

        if not args.yes:
            _print_plan(product, settings.openrouter_image_refinement_model)
            return

        if not settings.openrouter_api_key:
            raise DemoProductNotEligibleError(
                "OPENROUTER_API_KEY is not configured -- cannot generate an image."
            )

        image_url = generate_and_save(
            db, product, settings.openrouter_image_refinement_model, settings.openrouter_api_key
        )
        print(f"Generated and saved 1 image for '{product.sku}' ({product.name_en}).")
        print(f"Product.image -> {image_url}")
    except DemoProductNotEligibleError as exc:
        print(f"Not generating: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
