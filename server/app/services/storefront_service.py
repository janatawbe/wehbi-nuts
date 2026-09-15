"""Milestone 9 customer storefront reads.

Reads ONLY from `Product` -- the real, live catalog entity (see
Milestone 7's digitizer_review_service._upsert_catalog_product and
Milestone 8's catalog_import_export_service) -- never from
`DigitizedProduct`, which is the internal ingestion/review record. A
rejected or still-pending DigitizedProduct never has a linked Product row
at all, so it can never appear here by construction.

Visibility rule (see also the Milestone 9 README section this pairs
with): a Product is storefront-visible when `needs_review` is False.
That flag is the one existing column that means "not yet fit to show a
customer" -- every Product created by M7 approval or M8 import already
sets it False, so today this excludes nothing, but it's the correct,
already-existing gate rather than inventing a second one. Stock level
(`stock_status`) is NOT a visibility gate: an out-of-stock product still
appears, just marked unavailable, matching ordinary storefront behavior
(hiding it outright would make a small catalog look emptier than it is).
"""
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.product import Product
from app.schemas.storefront import StorefrontCategoryRead, StorefrontProductRead
from app.scripts.align_storefront_categories import OFFICIAL_CATEGORY_SLUGS


def _to_storefront_product(product: Product) -> StorefrontProductRead:
    return StorefrontProductRead(
        id=product.id,
        name_en=product.name_en,
        name_ar=product.name_ar,
        description_en=product.description_en,
        description_ar=product.description_ar,
        brand=product.brand,
        category=StorefrontCategoryRead.model_validate(product.category) if product.category else None,
        selling_mode=product.unit,
        package_weight=product.weight,
        price=product.price,
        stock_status=product.stock_status,
        image=product.image,
    )


def list_storefront_categories(db: Session) -> list[StorefrontCategoryRead]:
    """The seven official storefront categories only, in their canonical
    display order -- a dormant dev-only category (see
    app.scripts.align_storefront_categories) is never returned here, even
    though the row still exists in the database."""
    stmt = select(Category).where(Category.slug.in_(OFFICIAL_CATEGORY_SLUGS))
    by_slug = {category.slug: category for category in db.scalars(stmt).all()}
    ordered = [by_slug[slug] for slug in OFFICIAL_CATEGORY_SLUGS if slug in by_slug]
    return [StorefrontCategoryRead.model_validate(category) for category in ordered]


def list_storefront_products(
    db: Session,
    *,
    category_slug: str | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[StorefrontProductRead]:
    stmt = (
        select(Product)
        .options(joinedload(Product.category))
        .where(Product.needs_review.is_(False))
        .order_by(Product.created_at.desc())
    )

    if category_slug:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(Category.slug == category_slug)

    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.name_en.ilike(term), Product.name_ar.ilike(term)))

    if limit is not None:
        stmt = stmt.limit(limit)

    return [_to_storefront_product(product) for product in db.scalars(stmt).all()]


def get_storefront_product(db: Session, product_id: uuid.UUID) -> StorefrontProductRead | None:
    stmt = (
        select(Product)
        .options(joinedload(Product.category))
        .where(Product.id == product_id, Product.needs_review.is_(False))
    )
    product = db.scalars(stmt).first()
    return _to_storefront_product(product) if product else None
