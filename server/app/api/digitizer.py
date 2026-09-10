import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.schemas.digitization_job import DigitizationJobRead
from app.schemas.digitizer import DigitizerJobRead
from app.services.ai.errors import AIAnalysisError
from app.services.ai.openai_vision_digitizer import OpenAIVisionDigitizer
from app.services.ai.types import AIProductAnalyzer
from app.services.digitizer_processing_service import ProcessingError, process_digitization_job
from app.services.digitizer_service import DigitizerUploadError, create_digitization_job
from app.services.storage import MediaKind, get_upload_root, list_job_source_images, resolve_media_path

router = APIRouter()

_MEDIA_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def get_ai_analyzer(settings: Settings = Depends(get_settings)) -> AIProductAnalyzer:
    """FastAPI dependency constructing the AI product analyzer.

    Tests override this with a fake analyzer so the test suite never makes
    a live OpenAI call. Depending on the narrow `AIProductAnalyzer`
    protocol (not the concrete `OpenAIVisionDigitizer` class) everywhere
    else in the app is what would let a different provider be swapped in
    later without touching the processing pipeline or the API layer.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503, detail="The AI digitization service is not configured."
        )
    return OpenAIVisionDigitizer(api_key=settings.openai_api_key, model_name=settings.openai_model)


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
    data["candidates"] = list(db.scalars(stmt).all())
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
    upload response on OpenAI or conflating the two very different
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
