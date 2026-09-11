import re
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image

from app.core.config import get_settings

# server/app/services/storage.py -> parents[2] == server/
BASE_DIR = Path(__file__).resolve().parents[2]

# Maps the image format Pillow detects to the safe extension we store it
# under. Only these formats are accepted, regardless of the client-supplied
# filename or Content-Type header.
SUPPORTED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

# Every filename this module ever writes is `<32-hex-uuid><.jpg|.png|.webp>`
# (see save_image/save_crop) -- this is also the only shape the media
# endpoint will ever serve, which is what makes path-traversal impossible
# by construction rather than by escaping/blocklisting client input.
_SAFE_FILENAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

MediaKind = Literal["source", "products", "refined"]

# Maps a MediaKind to the on-disk subpath it actually lives under, relative
# to a job's directory. "refined" is nested under products/ so a full
# reprocess (which wipes the whole products/ tree via cleanup_job_products)
# naturally also clears any refined images derived from the crops it's
# replacing -- no separate cleanup call is needed for that case.
_KIND_SUBPATH: dict[str, str] = {
    "source": "source",
    "products": "products",
    "refined": "products/refined",
}


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


def get_job_source_dir(upload_root: Path, job_id: uuid.UUID) -> Path:
    """The directory holding a job's original uploaded images. Never
    created here -- it is created by `allocate_job_directory` at upload
    time; callers that expect it to already exist (processing) should
    treat a missing directory as "no source images", not create one."""
    return upload_root / str(job_id) / "source"


def get_job_products_dir(upload_root: Path, job_id: uuid.UUID) -> Path:
    """The directory holding a job's cropped product images, creating it
    on first use. Kept as a sibling of `source/` (never inside it) so
    reprocessing a job's crops can never touch its original uploads."""
    products_dir = upload_root / str(job_id) / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    return products_dir


def save_crop(products_dir: Path, jpeg_bytes: bytes) -> str:
    """Persist an already-encoded JPEG crop under a freshly generated safe
    filename, mirroring `save_image`'s naming/containment guarantees."""
    filename = f"{uuid.uuid4().hex}.jpg"
    file_path = products_dir / filename
    if file_path.resolve().parent != products_dir.resolve():
        raise InvalidImageError("Invalid crop target.")  # unreachable in practice
    file_path.write_bytes(jpeg_bytes)
    return filename


def cleanup_job_products(upload_root: Path, job_id: uuid.UUID) -> None:
    """Remove all previously-generated crops for a job (e.g. before a
    rerun), without touching its source images. Also removes any Milestone
    6 refined images, since they are nested under products/ and derived
    from the crops this call is about to invalidate."""
    shutil.rmtree(upload_root / str(job_id) / "products", ignore_errors=True)


def get_job_refined_dir(upload_root: Path, job_id: uuid.UUID) -> Path:
    """The directory holding a job's Milestone 6 refined catalog images,
    creating it on first use. Nested under products/ (see MediaKind's
    _KIND_SUBPATH) -- never touches source/ or the crops in products/
    itself."""
    refined_dir = upload_root / str(job_id) / "products" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    return refined_dir


def save_refined_image(refined_dir: Path, jpeg_bytes: bytes) -> str:
    """Persist an already-encoded JPEG refined image under a freshly
    generated safe filename, mirroring `save_crop`. Always a NEW filename
    -- the crop this was derived from, and any previous refined image, are
    never overwritten by this call; a caller replacing a prior refinement
    is responsible for removing the old file separately (see
    delete_refined_image)."""
    filename = f"{uuid.uuid4().hex}.jpg"
    file_path = refined_dir / filename
    if file_path.resolve().parent != refined_dir.resolve():
        raise InvalidImageError("Invalid refined image target.")  # unreachable in practice
    file_path.write_bytes(jpeg_bytes)
    return filename


def delete_refined_image(refined_dir: Path, filename: str) -> None:
    """Best-effort removal of one previously-saved refined image (e.g. the
    prior file when a product is re-refined) -- never raises, since the
    database row is always the source of truth and a leftover orphaned
    file is a cosmetic disk-space issue, not a correctness one."""
    if not _SAFE_FILENAME.match(filename):
        return
    candidate = refined_dir / filename
    if candidate.resolve().parent != refined_dir.resolve():
        return
    candidate.unlink(missing_ok=True)


def resolve_media_path(
    upload_root: Path, job_id: uuid.UUID, kind: MediaKind, filename: str
) -> Path | None:
    """Resolve a job's source/crop filename to an on-disk path, or None if
    the request is invalid/the file doesn't exist -- callers should treat
    None as a 404, never distinguishing "bad filename" from "not found" in
    the response (both are just "not available").

    Safety is by construction, not by sanitizing `filename`: only a
    filename that exactly matches the pattern this module itself generates
    (32 hex chars + a supported extension) is even looked up, and the
    resolved path is double-checked to still be inside the expected
    directory before being returned.
    """
    if not _SAFE_FILENAME.match(filename):
        return None

    subpath = _KIND_SUBPATH.get(kind)
    if subpath is None:
        return None

    directory = upload_root / str(job_id) / subpath
    candidate = directory / filename
    if candidate.resolve().parent != directory.resolve():
        return None
    if not candidate.is_file():
        return None
    return candidate
