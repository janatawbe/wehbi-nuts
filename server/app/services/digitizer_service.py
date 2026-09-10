import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.digitization_job import DigitizationJob
from app.models.enums import DigitizationJobStatus
from app.services.storage import (
    InvalidImageError,
    allocate_job_directory,
    cleanup_job_directory,
    detect_image_extension,
    save_image,
)


class DigitizerUploadError(Exception):
    """A client-safe error raised while creating a digitization job.

    `message` is safe to return directly to the frontend: it never
    includes filesystem paths or internal stack traces.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def create_digitization_job(
    db: Session,
    upload_root: Path,
    files: list[UploadFile],
    max_images: int,
    max_file_size_bytes: int,
    max_image_dimension: int,
) -> tuple[DigitizationJob, list[str]]:
    """Validate and store uploaded images, then create their DigitizationJob.

    The database row is only created after every file has been validated
    and saved, so a partially invalid upload never leaves behind either a
    job row or orphaned files.
    """
    if not files:
        raise DigitizerUploadError("At least one image is required.")
    if len(files) > max_images:
        raise DigitizerUploadError(f"A job may include at most {max_images} images.")

    job_id = uuid.uuid4()
    try:
        job_dir = allocate_job_directory(upload_root, job_id)
    except FileExistsError as exc:
        raise DigitizerUploadError(
            "Could not allocate a storage location for this job.", status_code=500
        ) from exc

    saved_filenames: list[str] = []
    try:
        for upload in files:
            content = await upload.read()
            if not content:
                raise InvalidImageError("An uploaded file was empty.")
            if len(content) > max_file_size_bytes:
                raise InvalidImageError(
                    "An uploaded file exceeds the maximum allowed size."
                )
            extension = detect_image_extension(content, max_image_dimension)
            saved_filenames.append(save_image(job_dir, content, extension))
    except InvalidImageError as exc:
        cleanup_job_directory(upload_root, job_id)
        raise DigitizerUploadError(str(exc)) from exc
    except Exception as exc:
        cleanup_job_directory(upload_root, job_id)
        raise DigitizerUploadError(
            "Upload failed unexpectedly.", status_code=500
        ) from exc

    job = DigitizationJob(
        id=job_id,
        status=DigitizationJobStatus.PENDING,
        total_items=len(saved_filenames),
    )
    try:
        db.add(job)
        db.commit()
    except Exception as exc:
        db.rollback()
        cleanup_job_directory(upload_root, job_id)
        raise DigitizerUploadError(
            "Could not create digitization job.", status_code=500
        ) from exc

    db.refresh(job)
    return job, saved_filenames
