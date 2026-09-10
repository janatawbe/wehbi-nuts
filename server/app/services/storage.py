import shutil
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import get_settings

# server/app/services/storage.py -> parents[2] == server/
BASE_DIR = Path(__file__).resolve().parents[2]

# Maps the image format Pillow detects to the safe extension we store it
# under. Only these formats are accepted, regardless of the client-supplied
# filename or Content-Type header.
SUPPORTED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class InvalidImageError(ValueError):
    """Raised when uploaded content fails server-side image validation."""


def get_upload_root() -> Path:
    """FastAPI dependency returning the base directory for digitizer uploads.

    Tests override this dependency to point at a temporary directory so
    they never touch a developer's real upload folder.
    """
    settings = get_settings()
    upload_dir = Path(settings.digitizer_upload_dir)
    if not upload_dir.is_absolute():
        upload_dir = BASE_DIR / upload_dir
    return upload_dir


def detect_image_extension(data: bytes, max_dimension: int) -> str:
    """Validate that `data` is a genuine, supported image.

    Uses Pillow to actually decode the content rather than trusting the
    client-supplied filename or Content-Type. Returns the safe file
    extension to store the image under, or raises InvalidImageError.
    """
    try:
        with Image.open(BytesIO(data)) as probe:
            probe.verify()
    except Exception as exc:
        raise InvalidImageError("The uploaded file is not a valid image.") from exc

    # verify() leaves the Image object unusable for further access, so
    # re-open a fresh copy to inspect its format and dimensions.
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
    except Exception as exc:
        raise InvalidImageError("The uploaded file is not a valid image.") from exc

    extension = SUPPORTED_IMAGE_FORMATS.get(image_format or "")
    if extension is None:
        raise InvalidImageError(
            f"Unsupported image format: {image_format or 'unknown'}."
        )

    if width <= 0 or height <= 0 or width > max_dimension or height > max_dimension:
        raise InvalidImageError("Image dimensions are not within the allowed range.")

    return extension


def allocate_job_directory(upload_root: Path, job_id: uuid.UUID) -> Path:
    """Create and return the unique source-image directory for a job."""
    job_dir = upload_root / str(job_id) / "source"
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def save_image(job_dir: Path, data: bytes, extension: str) -> str:
    """Persist validated image bytes under a freshly generated safe filename.

    The stored filename is always server-generated (never derived from the
    client-supplied name), which eliminates path traversal and filename
    collisions by construction.
    """
    filename = f"{uuid.uuid4().hex}{extension}"
    file_path = job_dir / filename
    if file_path.resolve().parent != job_dir.resolve():
        # Defense in depth: should be unreachable since `filename` is always
        # a generated hex string, but never write outside the job directory.
        raise InvalidImageError("Invalid upload target.")
    file_path.write_bytes(data)
    return filename


def cleanup_job_directory(upload_root: Path, job_id: uuid.UUID) -> None:
    """Remove a job's entire upload directory, e.g. after a failed request."""
    shutil.rmtree(upload_root / str(job_id), ignore_errors=True)


def list_job_source_images(upload_root: Path, job_id: uuid.UUID) -> list[str]:
    """Return the safe filenames stored for a job, without exposing paths."""
    source_dir = upload_root / str(job_id) / "source"
    if not source_dir.is_dir():
        return []
    return sorted(p.name for p in source_dir.iterdir() if p.is_file())
