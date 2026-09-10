import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.digitization_job import DigitizationJob
from app.schemas.digitization_job import DigitizationJobRead
from app.schemas.digitizer import DigitizerJobRead
from app.services.digitizer_service import DigitizerUploadError, create_digitization_job
from app.services.storage import get_upload_root, list_job_source_images

router = APIRouter()

# Small helper shared by every route below: bolts the filesystem-derived
# `source_images` list onto the DB-backed DigitizationJobRead schema.


def _to_job_read(job: DigitizationJob, upload_root: Path) -> DigitizerJobRead:
    data = DigitizationJobRead.model_validate(job).model_dump()
    data["source_images"] = list_job_source_images(upload_root, job.id)
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

    return _to_job_read(job, upload_root)


@router.get("/jobs", response_model=list[DigitizerJobRead])
def list_jobs(
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
) -> list[DigitizerJobRead]:
    stmt = select(DigitizationJob).order_by(DigitizationJob.created_at.desc()).limit(100)
    jobs = db.scalars(stmt).all()
    return [_to_job_read(job, upload_root) for job in jobs]


@router.get("/jobs/{job_id}", response_model=DigitizerJobRead)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    upload_root: Path = Depends(get_upload_root),
) -> DigitizerJobRead:
    job = db.get(DigitizationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Digitization job not found.")

    return _to_job_read(job, upload_root)
