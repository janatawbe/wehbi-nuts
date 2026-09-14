"""Milestone 7 dev convenience: seed a practical starting set of
`Category` rows for Wehbi Nuts.

Why this exists: Milestone 7 approval requires a real `category_id` (see
app.services.digitizer_review_service.validate_for_approval), but nothing
before this milestone ever created a Category row, so a fresh database has
none to pick from and approval could never be completed end-to-end. The
fix is real, admin-manageable `Category` database rows -- NOT a hardcoded
list in the frontend and NOT a closed code enum -- since categories are
meant to become editable by an admin in a later milestone (see README).
This script only guarantees a workable starting point for local
development and manual Milestone 7 testing.

Usage (from `server/`, with the virtual environment activated and
DATABASE_URL configured via `.env` or the environment -- the same
convention as running `alembic upgrade head`):

    python -m app.scripts.seed_categories

Idempotent: matched by `slug` (already unique at the database level).
Running this again -- on a database that already has some or all of these
categories -- creates nothing new for the ones that already exist and
never modifies or deletes an existing category, even one an admin has
since renamed.
"""
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.category import Category

# (name_en, name_ar, slug) -- a practical starting category set for a
# nuts/seeds/dried-fruit/coffee/spices/sweets/snacks roastery shop. Not
# exhaustive and not a closed enum: an admin can add, rename, or remove
# categories later through the Category table directly (or a future admin
# UI) -- this script never re-runs itself automatically and never touches
# a category it didn't itself just create.
INITIAL_CATEGORIES: list[tuple[str, str, str]] = [
    ("Nuts", "مكسرات", "nuts"),
    ("Seeds", "بذور", "seeds"),
    ("Dried Fruits", "فواكه مجففة", "dried-fruits"),
    ("Coffee", "قهوة", "coffee"),
    ("Spices & Herbs", "بهارات وأعشاب", "spices-herbs"),
    ("Sweets & Chocolate", "حلويات وشوكولاتة", "sweets-chocolate"),
    ("Spreads", "دهانات", "spreads"),
    ("Syrups & Molasses", "شراب ودبس", "syrups-molasses"),
    ("Snacks", "وجبات خفيفة", "snacks"),
    ("Other", "أخرى", "other"),
]


def seed_categories(db: Session) -> tuple[list[Category], list[str]]:
    """Create whichever of INITIAL_CATEGORIES don't already exist (matched
    by `slug`). Returns (created, already_present_slugs). Never updates or
    deletes an existing category -- a slug that already exists (from a
    previous run of this script, or created independently, e.g. by an
    admin) is left completely untouched, even if its name_en/name_ar
    differs from the seed list above.
    """
    existing_slugs = {row[0] for row in db.query(Category.slug).all()}
    created: list[Category] = []
    already_present: list[str] = []

    for name_en, name_ar, slug in INITIAL_CATEGORIES:
        if slug in existing_slugs:
            already_present.append(slug)
            continue
        category = Category(name_en=name_en, name_ar=name_ar, slug=slug)
        db.add(category)
        created.append(category)

    if created:
        db.commit()
        for category in created:
            db.refresh(category)

    return created, already_present


def main() -> None:
    db = SessionLocal()
    try:
        created, already_present = seed_categories(db)
    finally:
        db.close()

    if created:
        label = "category" if len(created) == 1 else "categories"
        print(f"Created {len(created)} {label}:")
        for category in created:
            print(f"  - {category.name_en} ({category.slug})")
    if already_present:
        print(f"Already present, skipped ({len(already_present)}): {', '.join(already_present)}")
    if not created and not already_present:
        print("Nothing to seed.")  # unreachable given INITIAL_CATEGORIES is non-empty


if __name__ == "__main__":
    main()
