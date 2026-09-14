import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.models.enums import EnrichmentStatus, ImageRefinementStatus, ReviewStatus
from app.schemas.digitization_job import DigitizationJobRead
from app.schemas.digitized_product import DigitizedProductRead
from app.schemas.digitizer import DigitizerJobRead, DuplicateDetectionSummaryRead
from app.services.ai.enrichment_service import OpenRouterProductEnricher
from app.services.ai.errors import AIAnalysisError
from app.services.ai.image_editing_refiner import AIProductImageRefiner
from app.services.ai.openrouter_vision_digitizer import OpenRouterVisionDigitizer
from app.services.ai.types import AIProductAnalyzer
from app.services.digitizer_enrichment_service import EnrichmentError, enrich_digitized_product
from app.services.digitizer_processing_service import ProcessingError, process_digitization_job
from app.services.digitizer_refinement_service import RefinementError, refine_digitized_product
from app.services.digitizer_service import DigitizerUploadError, create_digitization_job
from app.services.duplicate_detection_service import detect_duplicates_for_job, summarize_duplicate_detection
from app.services.image_refinement_service import LocalBackgroundRefiner, ProductImageRefiner, RembgBackgroundRemover
from app.services.storage import MediaKind, get_upload_root, list_job_source_images, resolve_media_path

router = APIRouter()

_MEDIA_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def get_ai_analyzer(settings: Settings = Depends(get_settings)) -> AIProductAnalyzer:
    """FastAPI dependency constructing the AI product analyzer.

    Tests override this with a fake analyzer so the test suite never makes
    a live OpenRouter call. Depending on the narrow `AIProductAnalyzer`
    protocol (not the concrete `OpenRouterVisionDigitizer` class) everywhere
    else in the app is what would let a different provider/gateway be
    swapped in later without touching the processing pipeline or the API
    layer.
    """
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503, detail="The AI digitization service is not configured."
        )
    return OpenRouterVisionDigitizer(
        api_key=settings.openrouter_api_key, model_name=settings.openrouter_model
    )


def get_ai_enricher(settings: Settings = Depends(get_settings)) -> OpenRouterProductEnricher:
    """FastAPI dependency constructing the Milestone 5 enrichment client.
    Mirrors get_ai_analyzer above; tests override this the same way."""
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503, detail="The AI digitization service is not configured."
        )
    return OpenRouterProductEnricher(
        api_key=settings.openrouter_api_key, model_name=settings.openrouter_model
    )


@lru_cache
def _rembg_background_remover() -> RembgBackgroundRemover:
    # Cached process-wide: loading the ONNX session is comparatively
    # expensive and rembg's model itself is immutable, so there is no
    # reason to reconstruct it per-request.
    return RembgBackgroundRemover(model_name="u2netp")


def get_product_image_refiner(settings: Settings = Depends(get_settings)) -> ProductImageRefiner:
    """FastAPI dependency constructing the Milestone 6 image refiner.

    Uses the approved AI image-editing model (google/gemini-2.5-flash-image
    via OpenRouter's Images API, see app/services/ai/image_editing_refiner.py)
    whenever `openrouter_api_key` is configured -- the SAME key already
    used for Milestone 4/5's text analysis; this is a different
    endpoint/model on the same OpenRouter account, not a different
    provider or credential. Falls back to the free, local Tier1+rembg
    refiner only when no key is configured at all (e.g. local dev without
    one) -- a CONFIGURATION fallback, not a runtime one: once AI is
    configured, a failed AI call is reported as a failed refinement, never
    silently downgraded to this local result (see
    digitizer_refinement_service and LocalBackgroundRefiner's docstring).

    Tests override this dependency with a fake ProductImageRefiner the
    same way get_ai_analyzer/get_ai_enricher are overridden, so the test
    suite never makes a real network call to either OpenRouter surface.
    """
    if settings.openrouter_api_key:
        return AIProductImageRefiner(
            api_key=settings.openrouter_api_key,
            model_name=settings.openrouter_image_refinement_model,
        )
    return LocalBackgroundRefiner(_rembg_background_remover())


# Small helper shared by every route below: bolts the filesystem-derived
# `source_images` and the persisted `digitized_products` onto the
# DB-backed DigitizationJobRead schema.


def _to_job_read(db: Session, job: DigitizationJob, upload_root: Path) -> DigitizerJobRead:
    data = DigitizationJobRead.model_validate(job).model_dump()
    data["source_images"] = list_job_source_images(upload_root, job.id)
    stmt = (
        select(DigitizedProduct)
        .where(DigitizedProduct.job_id == job.id)
        .order_by(DigitizedProduct.created_at.asc())
    )
    candidates = list(db.scalars(stmt).all())
    data["candidates"] = candidates
    summary = summarize_duplicate_detection(candidates)
    data["duplicate_summary"] = DuplicateDetectionSummaryRead(
        total_candidates=summary.total_candidates,
        eligible_candidates=summary.eligible_candidates,
        skipped_not_enriched=summary.skipped_not_enriched,
        likely_count=summary.likely_count,
        possible_count=summary.possible_count,
        none_count=summary.none_count,
    )
    return DigitizerJobRead(**data)


@router.post("/jobs", response_model=DigitizerJobRead, status_code=201)
async def create_job(
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
    settings: Settings = Depends(get_settings),
) -> DigitizerJobRead:
    try:
        job, _saved_filenames = await create_digitization_job(
            db=db,
            upload_root=upload_root,
            files=files or [],
            max_images=settings.digitizer_max_images_per_job,
            max_file_size_bytes=settings.digitizer_max_file_size_bytes,
            max_image_dimension=settings.digitizer_max_image_dimension,
        )
    except DigitizerUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return _to_job_read(db, job, upload_root)


@router.get("/jobs", response_model=list[DigitizerJobRead])
def list_jobs(
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
) -> list[DigitizerJobRead]:
    stmt = select(DigitizationJob).order_by(DigitizationJob.created_at.desc()).limit(100)
    jobs = db.scalars(stmt).all()
    return [_to_job_read(db, job, upload_root) for job in jobs]


@router.get("/jobs/{job_id}", response_model=DigitizerJobRead)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
) -> DigitizerJobRead:
    job = db.get(DigitizationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Digitization job not found.")

    return _to_job_read(db, job, upload_root)


@router.post("/jobs/{job_id}/process", response_model=DigitizerJobRead)
def process_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
    analyzer: AIProductAnalyzer = Depends(get_ai_analyzer),
) -> DigitizerJobRead:
    """Run AI digitization for every source image in this job.

    A separate endpoint from upload rather than an automatic step of it:
    an AI call per image is slow (seconds) and can fail independently of
    upload validation, so keeping upload fast/synchronous and processing
    as an explicit, separately-retriable action avoids either blocking the
    upload response on the AI provider or conflating the two very different
    failure modes. No background worker is introduced -- this runs
    synchronously within the request, which is sufficient at this
    milestone's scale (see README).
    """
    try:
        job = process_digitization_job(db, upload_root, job_id, analyzer)
    except ProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except AIAnalysisError as exc:
        # Should not normally surface here (per-image AI failures are
        # caught inside process_digitization_job and recorded on the job
        # instead), but never leak a raw provider/SDK exception if one does.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _to_job_read(db, job, upload_root)


@router.post("/products/{product_id}/enrich", response_model=DigitizedProductRead)
def enrich_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
    enricher: OpenRouterProductEnricher = Depends(get_ai_enricher),
) -> DigitizedProductRead:
    """Enrich exactly one DigitizedProduct with a single AI call (brand,
    weight/unit, barcode, both descriptions, and a resolved category).
    Independent of job state and of every other product in the job -- can
    always be retried on its own without re-running detection.
    """
    try:
        product = enrich_digitized_product(db, upload_root, product_id, enricher)
    except EnrichmentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except AIAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return DigitizedProductRead.model_validate(product)


@router.post("/jobs/{job_id}/enrich", response_model=DigitizerJobRead)
def enrich_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
    enricher: OpenRouterProductEnricher = Depends(get_ai_enricher),
) -> DigitizerJobRead:
    """Convenience endpoint: enrich every DRAFT, not-yet-enriched product in
    a job. A thin loop over the single-item logic above (not separate
    enrichment code), so per-item behavior -- including per-item retry --
    stays identical whether triggered here or one product at a time. One
    product's enrichment failing does not stop the rest.

    Only targets `enrichment_status == PENDING`: calling this endpoint
    again (e.g. after adding more source images or re-running detection)
    must not re-bill an AI call for a product that already succeeded --
    that would be paying for the same enrichment twice for no benefit. A
    user who deliberately wants to redo one product's enrichment can still
    do so explicitly via `POST /products/{id}/enrich`, which has no such
    filter.

    Only targets products still in PENDING_REVIEW or DRAFT (i.e. not yet
    approved/rejected/merged -- see ReviewStatus and
    digitizer_enrichment_service's reviewed_at guard): a human-reviewed
    product must never have its content silently regenerated by a bulk job
    action.
    """
    job = db.get(DigitizationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Digitization job not found.")

    stmt = select(DigitizedProduct.id).where(
        DigitizedProduct.job_id == job_id,
        DigitizedProduct.review_status.in_([ReviewStatus.PENDING_REVIEW, ReviewStatus.DRAFT]),
        DigitizedProduct.enrichment_status == EnrichmentStatus.PENDING,
    )
    product_ids = list(db.scalars(stmt).all())
    for product_id in product_ids:
        try:
            enrich_digitized_product(db, upload_root, product_id, enricher)
        except (EnrichmentError, AIAnalysisError):
            continue

    return _to_job_read(db, job, upload_root)


@router.post("/products/{product_id}/refine", response_model=DigitizedProductRead)
def refine_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
    refiner: ProductImageRefiner = Depends(get_product_image_refiner),
) -> DigitizedProductRead:
    """Refine exactly one DigitizedProduct's catalog image (Milestone 6)
    via the AI image-editing model (when configured) or the local
    Tier1+rembg refiner otherwise. Independent of job state and of every
    other product in the job -- always retriable as an explicit
    "Re-refine", regardless of `image_refinement_status`. At most one
    paid AI attempt per call -- see digitizer_refinement_service.
    """
    try:
        product = refine_digitized_product(db, upload_root, product_id, refiner)
    except RefinementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return DigitizedProductRead.model_validate(product)


@router.post("/jobs/{job_id}/refine", response_model=DigitizerJobRead)
def refine_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
    refiner: ProductImageRefiner = Depends(get_product_image_refiner),
) -> DigitizerJobRead:
    """Convenience endpoint: refine every not-yet-successfully-refined
    product in a job. Skips `image_refinement_status == REFINED` so a
    repeat call never redoes work that already succeeded (and, when AI is
    configured, never re-bills for a product that's already refined); a
    product whose refinement previously FAILED is retried (its status
    isn't REFINED), and a product with no crop image to refine from is
    marked SKIPPED so it isn't retried on every future bulk call either.
    """
    job = db.get(DigitizationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Digitization job not found.")

    stmt = select(DigitizedProduct.id).where(
        DigitizedProduct.job_id == job_id,
        DigitizedProduct.image_refinement_status != ImageRefinementStatus.REFINED,
    )
    product_ids = list(db.scalars(stmt).all())
    for product_id in product_ids:
        try:
            refine_digitized_product(db, upload_root, product_id, refiner)
        except RefinementError as exc:
            if exc.status_code == 400:
                # Nothing to refine from (no crop image) -- not a
                # processing failure, and retrying later can't change
                # that, so mark it distinctly rather than retrying forever.
                product = db.get(DigitizedProduct, product_id)
                if product is not None:
                    product.image_refinement_status = ImageRefinementStatus.SKIPPED
                    db.add(product)
                    db.commit()
            continue

    return _to_job_read(db, job, upload_root)


@router.post("/jobs/{job_id}/detect-duplicates", response_model=DigitizerJobRead)
def detect_duplicates(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
) -> DigitizerJobRead:
    """Recompute Milestone 6 duplicate flags for every candidate in this
    job (scoped to this job only -- see duplicate_detection_service).
    Fully local/deterministic, no AI call and no external dependency to
    mock in tests. Safe to call repeatedly: always recomputes from
    scratch, never accumulates stale pairwise rows, and never deletes or
    merges a DigitizedProduct -- it only flags.
    """
    job = db.get(DigitizationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Digitization job not found.")

    detect_duplicates_for_job(db, upload_root, job_id)

    return _to_job_read(db, job, upload_root)


@router.get("/jobs/{job_id}/media/{kind}/{filename}")
def get_job_media(
    job_id: uuid.UUID,
    kind: MediaKind,
    filename: str,
    upload_root: Path = Depends(get_upload_root),
) -> FileResponse:
    """Serve one source or crop image for a job without ever exposing the
    filesystem: `filename` must exactly match the safe, server-generated
    pattern this app itself writes (see storage.resolve_media_path), and
    the resolved path is re-checked to stay inside the expected
    directory. Neither condition holding is indistinguishable from "not
    found" in the response.
    """
    path = resolve_media_path(upload_root, job_id, kind, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Media not found.")

    content_type = _MEDIA_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=content_type, headers={"Cache-Control": "no-store"})
