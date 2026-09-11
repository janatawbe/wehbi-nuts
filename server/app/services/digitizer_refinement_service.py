import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.digitized_product import DigitizedProduct
from app.models.enums import ImageRefinementStatus
from app.services.image_refinement_service import (
    ProductImageRefiner,
    RefinementProductContext,
    RefinementRequest,
)
from app.services.reference_images import select_reference_images
from app.services.storage import (
    delete_refined_image,
    get_job_products_dir,
    get_job_refined_dir,
    save_refined_image,
)


class RefinementError(Exception):
    """A client-safe error raised before any image processing is attempted
    (unknown product, no crop image to refine from) -- mirrors
    EnrichmentError in digitizer_enrichment_service.py. A failure that
    happens DURING processing (the crop itself can't be decoded) is
    instead recorded as image_refinement_status=FAILED and raised
    separately below, since -- unlike an upstream AI failure -- it is this
    module's own job to record that outcome before re-raising."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def refine_digitized_product(
    db: Session,
    upload_root: Path,
    product_id: uuid.UUID,
    refiner: ProductImageRefiner,
) -> DigitizedProduct:
    """Refine exactly one DigitizedProduct's catalog image from its saved
    crop, via `refiner` (the AI image-editing model when configured,
    otherwise the free local Tier1+rembg refiner -- see
    api/digitizer.get_product_image_refiner). Independent of job state and
    of every other product in the job -- this is what makes single-item
    retry ("Re-refine") possible, and is always allowed regardless of
    `image_refinement_status` (unlike the job-level endpoint, which skips
    already-refined products for its own bulk pass -- see
    api/digitizer.refine_job).

    Exactly ONE call to `refiner.refine()` per invocation -- no retry loop
    here or in either ProductImageRefiner implementation, so a manual
    "Refine" click costs at most one paid AI attempt.

    Never touches `crop_image` -- the refined image is always a distinct,
    newly-saved file (see storage.save_refined_image). A prior refined
    image, if this is a re-refine, is deleted only AFTER the new one is
    safely saved and committed -- and is left completely untouched (both
    the file on disk and `product.refined_image`) if this attempt fails,
    so a previous valid refined image always remains available.
    """
    product = db.get(DigitizedProduct, product_id)
    if product is None:
        raise RefinementError("Digitized product not found.", status_code=404)
    if not product.crop_image:
        raise RefinementError("This product has no crop image to refine.", status_code=400)

    crop_path = get_job_products_dir(upload_root, product.job_id) / product.crop_image
    if not crop_path.is_file():
        raise RefinementError("The crop image for this product could not be found.", status_code=404)

    refined_dir = get_job_refined_dir(upload_root, product.job_id)
    previous_refined_filename = product.refined_image

    context = RefinementProductContext(
        name_en=product.name_en,
        name_ar=product.name_ar,
        category=product.category_suggestion,
        selling_mode=product.selling_mode.value if product.selling_mode else None,
        brand=product.brand,
        flavor_variant=product.flavor_variant,
    )
    reference_images = [path.read_bytes() for path in select_reference_images(product.presentation)]
    request = RefinementRequest(
        crop_bytes=crop_path.read_bytes(),
        presentation=product.presentation,
        context=context,
        reference_images=reference_images,
    )

    try:
        result = refiner.refine(request)
    except Exception as exc:
        # Covers both: the crop itself couldn't be decoded (local path),
        # and the AI request/response failing or returning nothing usable
        # (AI path) -- either way, this attempt failed. `product.
        # refined_image` is left completely untouched, so a previous valid
        # refined image (if any) stays exactly as it was; only the status
        # flips to FAILED so this attempt is visibly flagged for
        # review/retry. Never silently substitutes a different (e.g.
        # local rembg) result for a failed AI attempt -- see
        # LocalBackgroundRefiner's docstring.
        product.image_refinement_status = ImageRefinementStatus.FAILED
        db.add(product)
        db.commit()
        raise RefinementError("Could not refine this product's image.", status_code=502) from exc

    new_filename = save_refined_image(refined_dir, result.image_bytes)
    product.refined_image = new_filename
    product.image_refinement_status = ImageRefinementStatus.REFINED
    product.background_isolation_status = result.background_isolation_status
    db.add(product)
    db.commit()
    db.refresh(product)

    if previous_refined_filename and previous_refined_filename != new_filename:
        # Best-effort: the DB row (already correctly updated above) is the
        # source of truth, so a cleanup failure here must never surface as
        # a request failure.
        delete_refined_image(refined_dir, previous_refined_filename)

    return product
