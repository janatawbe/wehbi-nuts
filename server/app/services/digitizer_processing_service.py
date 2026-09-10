import uuid
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.models.enums import DigitizationJobStatus, IdentificationBasis, PresentationType, ReviewStatus
from app.services.ai.errors import AIAnalysisError
from app.services.ai.types import AIProductAnalyzer, DetectedProduct
from app.services.storage import (
    cleanup_job_products,
    get_job_products_dir,
    get_job_source_dir,
    list_job_source_images,
    save_crop,
)

_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


class ProcessingError(Exception):
    """A client-safe error raised before/without mutating job state.

    Used only for request-level problems (unknown job, no source images) --
    once processing actually starts, failures are handled by marking the
    job FAILED instead of raising, so a client always gets a 200 with a
    job body rather than a bare error for a problem partway through.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class _PendingProduct:
    source_image: str
    crop_bytes: bytes
    detected: DetectedProduct
    bbox_px: tuple[int, int, int, int]  # x, y, width, height


def _bbox_to_pixels(
    bbox: list[int], image_width: int, image_height: int
) -> tuple[int, int, int, int] | None:
    """Convert a normalized [ymin, xmin, ymax, xmax] (0-1000) box to a
    clamped pixel-space (x, y, width, height) box, or None if it collapses
    to zero area after clamping/rounding (a malformed or degenerate box
    should be dropped, not turned into an invalid crop)."""
    ymin, xmin, ymax, xmax = bbox
    x1 = max(0, min(round(xmin / 1000 * image_width), image_width))
    y1 = max(0, min(round(ymin / 1000 * image_height), image_height))
    x2 = max(0, min(round(xmax / 1000 * image_width), image_width))
    y2 = max(0, min(round(ymax / 1000 * image_height), image_height))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2 - x1, y2 - y1


def _encode_crop(image: Image.Image, box_px: tuple[int, int, int, int]) -> bytes | None:
    """Crop `image` to `box_px` (x, y, width, height) and encode it as a
    JPEG, preserving the original aspect ratio and resolution (no
    stretching, no resampling, no upscaling -- a crop is just a pixel
    subset of the source). Returns None if the crop is degenerate or the
    encoded result does not actually decode back (defense in depth: never
    persist a DigitizedProduct pointing at an unrenderable crop).
    """
    x, y, width, height = box_px
    if width <= 0 or height <= 0:
        return None

    cropped = image.crop((x, y, x + width, y + height))
    if cropped.mode not in ("RGB", "L"):
        cropped = cropped.convert("RGB")

    buffer = BytesIO()
    try:
        cropped.save(buffer, format="JPEG", quality=95)
    except Exception:
        return None
    crop_bytes = buffer.getvalue()

    try:
        with Image.open(BytesIO(crop_bytes)) as probe:
            probe.verify()
    except Exception:
        return None
    return crop_bytes


def _detect_products_for_image(
    image_path: Path, analyzer: AIProductAnalyzer
) -> list[_PendingProduct]:
    """Run one Gemini call for `image_path` and return crop-ready pending
    products. Raises AIAnalysisError only for a failure that affects the
    *whole* image (the API call itself failing, or the response overall
    not parsing) -- callers treat that as this one source image failing,
    not the whole job. An individual detected item with an invalid/
    degenerate bbox, or a crop that fails to encode, is silently skipped
    rather than failing the entire image (see README).
    """
    mime_type = _MIME_TYPES.get(image_path.suffix.lower())
    if mime_type is None:
        raise AIAnalysisError(f"Unsupported source image extension: {image_path.suffix}")

    detections = analyzer.analyze_image(image_path.read_bytes(), mime_type)
    if not detections:
        return []

    with Image.open(image_path) as image:
        image.load()
        width, height = image.size

        pending: list[_PendingProduct] = []
        for detection in detections:
            box_px = _bbox_to_pixels(detection.bbox, width, height)
            if box_px is None:
                continue
            crop_bytes = _encode_crop(image, box_px)
            if crop_bytes is None:
                continue
            pending.append(
                _PendingProduct(
                    source_image=image_path.name,
                    crop_bytes=crop_bytes,
                    detected=detection,
                    bbox_px=box_px,
                )
            )
        return pending


def process_digitization_job(
    db: Session, upload_root: Path, job_id: uuid.UUID, analyzer: AIProductAnalyzer
) -> DigitizationJob:
    """Run Gemini-based product digitization for every source image in a job.

    One Gemini request per source image (never per detected product).
    Rerunning is safe: previous candidates and crop files for this job are
    replaced, never accumulated. If digitization for every image fails,
    the job is marked FAILED; if some (or all) images succeed -- including
    an image that genuinely has zero sellable products -- it is marked
    COMPLETED, with a note in `error_message` if any images failed.
    """
    job = db.get(DigitizationJob, job_id)
    if job is None:
        raise ProcessingError("Digitization job not found.", status_code=404)

    source_filenames = list_job_source_images(upload_root, job.id)
    if not source_filenames:
        raise ProcessingError("This job has no source images to process.", status_code=400)

    job.status = DigitizationJobStatus.PROCESSING
    job.error_message = None
    db.add(job)
    db.commit()

    source_dir = get_job_source_dir(upload_root, job.id)

    pending: list[_PendingProduct] = []
    failed_count = 0
    for source_filename in source_filenames:
        try:
            pending.extend(_detect_products_for_image(source_dir / source_filename, analyzer))
        except Exception:
            failed_count += 1

    processed_count = len(source_filenames) - failed_count

    try:
        db.query(DigitizedProduct).filter(DigitizedProduct.job_id == job.id).delete()
        cleanup_job_products(upload_root, job.id)
        products_dir = get_job_products_dir(upload_root, job.id)

        for candidate in pending:
            crop_filename = save_crop(products_dir, candidate.crop_bytes)
            detected = candidate.detected
            x, y, width, height = candidate.bbox_px
            db.add(
                DigitizedProduct(
                    job_id=job.id,
                    source_image=candidate.source_image,
                    crop_image=crop_filename,
                    name_en=detected.name_en,
                    name_ar=detected.name_ar,
                    category_suggestion=detected.category,
                    presentation=PresentationType(detected.presentation),
                    identification_basis=IdentificationBasis(detected.identification_basis),
                    visible_text=detected.visible_text,
                    notes=detected.notes,
                    bbox_x=x,
                    bbox_y=y,
                    bbox_width=width,
                    bbox_height=height,
                    ai_confidence=Decimal(str(round(detected.confidence, 2))),
                    ai_raw_result=detected.model_dump(),
                    needs_review=True,
                    review_status=ReviewStatus.DRAFT,
                )
            )

        job.processed_items = processed_count
        job.failed_items = failed_count
        if failed_count > 0 and processed_count == 0:
            job.status = DigitizationJobStatus.FAILED
            job.error_message = "Digitization failed for all source images."
        elif failed_count > 0:
            job.status = DigitizationJobStatus.COMPLETED
            job.error_message = (
                f"Digitization completed, but {failed_count} of "
                f"{len(source_filenames)} source image(s) could not be processed."
            )
        else:
            job.status = DigitizationJobStatus.COMPLETED
            job.error_message = None

        db.add(job)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_job_products(upload_root, job.id)
        job.status = DigitizationJobStatus.FAILED
        job.error_message = "Could not save digitization results."
        job.processed_items = 0
        job.failed_items = len(source_filenames)
        db.add(job)
        db.commit()

    db.refresh(job)
    return job
