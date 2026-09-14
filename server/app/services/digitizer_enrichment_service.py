import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.digitized_product import DigitizedProduct
from app.models.enums import EnrichmentStatus, SellingMode
from app.services.ai.enrichment_service import OpenRouterProductEnricher
from app.services.storage import get_job_products_dir

_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

# `presentation` values (Milestone 4, see app.models.enums.PresentationType)
# that strongly imply a given selling_mode -- used only to flag a
# conflicting AI answer for human review, never to silently override it.
# "other" is deliberately absent: it carries no reliable implication.
_BULK_PRESENTATIONS = {"bulk_tray", "bulk_loose"}
_PACKAGED_PRESENTATIONS = {"packaged", "jar", "bottle"}


def _expected_selling_mode(presentation: str | None) -> str | None:
    if presentation in _BULK_PRESENTATIONS:
        return "weight"
    if presentation in _PACKAGED_PRESENTATIONS:
        return "unit"
    return None


class EnrichmentError(Exception):
    """A client-safe error raised before any AI call is made (unknown
    product, no crop image to enrich from) -- mirrors ProcessingError in
    digitizer_processing_service.py. Once the AI call is made, its own
    AIAnalysisError subclasses are left to propagate, since a single-item
    enrichment call is expected to fail visibly and be retried directly,
    unlike whole-job processing, which absorbs per-image AI failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def enrich_digitized_product(
    db: Session,
    upload_root: Path,
    product_id: uuid.UUID,
    enricher: OpenRouterProductEnricher,
) -> DigitizedProduct:
    """Enrich exactly one DigitizedProduct: one AI call using its saved
    crop image and already-known name/category as context, filling in the
    fields Milestone 4 never populates. Independent of job state and of
    every other product in the job -- this is what makes single-item
    retry possible.
    """
    product = db.get(DigitizedProduct, product_id)
    if product is None:
        raise EnrichmentError("Digitized product not found.", status_code=404)
    if product.reviewed_at is not None:
        # Milestone 7: human edits are authoritative. This product has
        # already been touched by a reviewer (field edit, draft save,
        # approve, or reject) -- re-running enrichment would silently
        # overwrite that with a fresh AI guess. Refuse outright rather than
        # merge/skip individual fields, so the failure is obvious instead
        # of a confusing partial overwrite.
        raise EnrichmentError(
            "This product has already been reviewed by a human; re-enrichment is disabled to avoid "
            "overwriting reviewed changes.",
            status_code=409,
        )
    if not product.crop_image:
        raise EnrichmentError("This product has no crop image to enrich from.", status_code=400)

    crop_path = get_job_products_dir(upload_root, product.job_id) / product.crop_image
    if not crop_path.is_file():
        raise EnrichmentError("The crop image for this product could not be found.", status_code=404)

    mime_type = _MIME_TYPES.get(crop_path.suffix.lower(), "image/jpeg")
    categories = list(db.scalars(select(Category).order_by(Category.name_en.asc())).all())
    category_names = [category.name_en for category in categories]
    presentation = product.presentation.value if product.presentation else None

    result = enricher.enrich_product(
        image_bytes=crop_path.read_bytes(),
        mime_type=mime_type,
        name_en=product.name_en,
        name_ar=product.name_ar,
        category_suggestion=product.category_suggestion,
        category_names=category_names,
        presentation=presentation,
    )

    field_review = {key: entry.model_dump() for key, entry in result.field_review.items()}

    matched_category: Category | None = None
    if result.category is not None:
        chosen = result.category.strip().lower()
        matched_category = next(
            (category for category in categories if category.name_en.strip().lower() == chosen),
            None,
        )
        if matched_category is None:
            # The model was given an explicit, closed list of names and
            # still returned something outside it -- treat the resolution
            # itself as unreliable regardless of what it self-reported.
            field_review["category"]["needs_review"] = True

    expected_selling_mode = _expected_selling_mode(presentation)
    if expected_selling_mode is not None and expected_selling_mode != result.selling_mode:
        # M4's own presentation classification strongly disagrees with this
        # pass's selling_mode -- never silently trust one AI call's
        # judgment over another's on a distinction this consequential for
        # future pricing; always surface it for a human instead.
        field_review["selling_mode"]["needs_review"] = True
        conflict_note = (
            f"AI selling_mode ({result.selling_mode}) conflicts with presentation "
            f"({presentation}, normally {expected_selling_mode})."
        )
        existing_reason = field_review["selling_mode"].get("reason")
        field_review["selling_mode"]["reason"] = (
            f"{existing_reason} {conflict_note}" if existing_reason else conflict_note
        )

    product.brand = result.brand
    product.flavor_variant = result.flavor_variant
    product.selling_mode = SellingMode(result.selling_mode)
    product.package_weight = result.package_weight
    product.barcode = result.barcode
    product.description_en = result.description_en
    product.description_ar = result.description_ar
    product.field_review = field_review
    product.enrichment_status = EnrichmentStatus.ENRICHED

    if matched_category is not None:
        product.category_id = matched_category.id
        product.category_suggestion = matched_category.name_en
    elif result.category is not None:
        # No confident match: never invent a new Category row -- leave
        # category_id NULL and preserve the AI's raw text for a human to
        # resolve later (Milestone 7).
        product.category_id = None
        product.category_suggestion = result.category
    # else: the AI returned null (no category fit) -- leave category_id
    # and category_suggestion exactly as Milestone 4 left them.

    db.add(product)
    db.commit()
    db.refresh(product)
    return product
