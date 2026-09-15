"""Milestone 9 dev alignment: bring the existing `Category` rows in line
with the seven OFFICIAL storefront categories the manager specified,
without deleting or orphaning anything.

Why this exists: `seed_categories.py` (Milestone 7) seeded a practical
starting set of ten categories for local development, before the final
storefront category list was decided. Auditing that set against the
seven official categories (Coffee, Dried Fruits, Nuts, Snacks & Sweets,
Seeds, Spice & Herbs, Gifts) found:
  - Five seeds already match one official category outright (Coffee,
    Dried Fruits, Nuts, Seeds, and -- after a wording fix -- Spice &
    Herbs, seeded as "Spices & Herbs").
  - Two seeds ("Snacks" and "Sweets & Chocolate") both belong under the
    single official "Snacks & Sweets" bucket and must become one row.
  - "Gifts" has no dev-seed equivalent at all and needs creating.
  - Three dev-only seeds ("Other", "Spreads", "Syrups & Molasses") have
    no place in the official list. None of them were referenced by any
    Product as of this audit.

This script NEVER deletes a Category or a Product. A category with no
official equivalent is simply left in the database, unreferenced by the
storefront's 7-category navigation -- a future admin category-management
UI can repurpose, rename, or remove it. Merging two seeds into one
official category reassigns the affected Products' `category_id` to the
surviving row; the now-empty duplicate is left in place, not deleted, so
this operation is never destructive or hard to reason about afterward.

Idempotent: safe to run again on a database that's already aligned --
each step matches by slug and only acts on rows that still need it.

Usage (same convention as seed_categories.py):
    python -m app.scripts.align_storefront_categories
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.product import Product

# (current_slug, new_name_en, new_name_ar, new_slug) -- a dev seed that
# already means the same thing as an official category, just needs its
# wording/slug corrected in place. Category.id (and therefore every
# existing Product relationship) is untouched.
RENAMES: list[tuple[str, str, str, str]] = [
    ("spices-herbs", "Spice & Herbs", "بهارات وأعشاب", "spice-herbs"),
]

# (surviving_slug, new_name_en, new_name_ar, new_slug, slug_to_merge_away)
# -- two dev seeds that both belong under one official category. The
# surviving row is renamed in place; every Product pointed at the
# merged-away row is reassigned to the survivor; the merged-away row
# itself is left in the database, simply unused.
MERGES: list[tuple[str, str, str, str, str]] = [
    ("sweets-chocolate", "Snacks & Sweets", "وجبات خفيفة وحلويات", "snacks-sweets", "snacks"),
]

# (name_en, name_ar, slug) -- an official category with no dev-seed
# equivalent at all. Created only if no category with this slug exists.
NEW_CATEGORIES: list[tuple[str, str, str]] = [
    ("Gifts", "هدايا", "gifts"),
]

# The seven official storefront categories' final slugs, in the order
# "Shop by Category" should present them. Exported so the frontend/tests
# have one shared source of truth to check the database against.
OFFICIAL_CATEGORY_SLUGS: list[str] = [
    "coffee",
    "dried-fruits",
    "nuts",
    "snacks-sweets",
    "seeds",
    "spice-herbs",
    "gifts",
]


def align_storefront_categories(db: Session) -> list[str]:
    """Applies every rename/merge/create step above. Returns a list of
    human-readable change descriptions (empty if the database already
    matched the seven official categories)."""
    changes: list[str] = []
    by_slug = {category.slug: category for category in db.scalars(select(Category)).all()}

    for current_slug, name_en, name_ar, new_slug in RENAMES:
        category = by_slug.get(current_slug) or by_slug.get(new_slug)
        if category is None:
            continue  # no matching seed -- leave for NEW_CATEGORIES/manual setup
        if category.name_en == name_en and category.slug == new_slug:
            continue  # already aligned
        changes.append(f"Renamed category '{category.name_en}' ({category.slug}) -> '{name_en}' ({new_slug})")
        category.name_en = name_en
        category.name_ar = name_ar
        category.slug = new_slug
        db.add(category)
        by_slug.pop(current_slug, None)
        by_slug[new_slug] = category

    for surviving_slug, name_en, name_ar, new_slug, merge_away_slug in MERGES:
        survivor = by_slug.get(surviving_slug) or by_slug.get(new_slug)
        if survivor is None:
            continue
        if survivor.name_en != name_en or survivor.slug != new_slug:
            changes.append(f"Renamed category '{survivor.name_en}' ({survivor.slug}) -> '{name_en}' ({new_slug})")
            survivor.name_en = name_en
            survivor.name_ar = name_ar
            survivor.slug = new_slug
            db.add(survivor)
            by_slug.pop(surviving_slug, None)
            by_slug[new_slug] = survivor

        merged_away = by_slug.get(merge_away_slug)
        if merged_away is not None and merged_away.id != survivor.id:
            moved = list(db.scalars(select(Product).where(Product.category_id == merged_away.id)).all())
            if moved:
                for product in moved:
                    product.category_id = survivor.id
                    db.add(product)
                changes.append(
                    f"Reassigned {len(moved)} product(s) from '{merged_away.name_en}' ({merged_away.slug}) "
                    f"to '{survivor.name_en}' ({survivor.slug}); '{merged_away.name_en}' left in place, now unused"
                )

    for name_en, name_ar, slug in NEW_CATEGORIES:
        if slug in by_slug:
            continue
        category = Category(name_en=name_en, name_ar=name_ar, slug=slug)
        db.add(category)
        by_slug[slug] = category
        changes.append(f"Created category '{name_en}' ({slug})")

    if changes:
        db.commit()
    return changes


def main() -> None:
    db = SessionLocal()
    try:
        changes = align_storefront_categories(db)
    finally:
        db.close()

    if changes:
        print(f"Aligned {len(changes)} change(s):")
        for change in changes:
            print(f"  - {change}")
    else:
        print("Already aligned with the seven official storefront categories.")
    print(f"\nOfficial storefront categories (by slug): {', '.join(OFFICIAL_CATEGORY_SLUGS)}")


if __name__ == "__main__":
    main()
