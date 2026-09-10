import uuid
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.main import app
from app.models.digitization_job import DigitizationJob


def make_image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (20, 20)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(120, 60, 10)).save(buffer, format=fmt)
    return buffer.getvalue()


def upload_files(client: TestClient, files: list[tuple[str, bytes, str]]):
    payload = [("files", (name, data, content_type)) for name, data, content_type in files]
    return client.post("/api/digitizer/jobs", files=payload)


# --- Successful uploads ----------------------------------------------------


def test_upload_single_valid_image_creates_job(client: TestClient, tmp_path: Path):
    response = upload_files(
        client, [("nuts.jpg", make_image_bytes("JPEG"), "image/jpeg")]
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_items"] == 1
    assert len(body["source_images"]) == 1
    assert body["source_images"][0].endswith(".jpg")

    job_dir = tmp_path / "uploads" / "digitizer" / body["id"] / "source"
    assert job_dir.is_dir()
    assert len(list(job_dir.iterdir())) == 1


def test_upload_multiple_valid_images_creates_one_job(client: TestClient):
    response = upload_files(
        client,
        [
            ("a.jpg", make_image_bytes("JPEG"), "image/jpeg"),
            ("b.png", make_image_bytes("PNG"), "image/png"),
            ("c.webp", make_image_bytes("WEBP"), "image/webp"),
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["total_items"] == 3
    assert len(body["source_images"]) == 3
    extensions = sorted(Path(name).suffix for name in body["source_images"])
    assert extensions == [".jpg", ".png", ".webp"]


# --- Validation failures ----------------------------------------------------


def test_zero_file_request_is_rejected(client: TestClient, db_session):
    response = client.post("/api/digitizer/jobs")

    assert response.status_code in (400, 422)
    assert db_session.query(DigitizationJob).count() == 0


def test_unsupported_image_format_is_rejected(client: TestClient, db_session):
    # GIF is a real, valid image that Pillow can decode, but it is not one
    # of this project's supported formats.
    response = upload_files(
        client, [("shelf.gif", make_image_bytes("GIF"), "image/gif")]
    )

    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()
    assert db_session.query(DigitizationJob).count() == 0


def test_fake_image_content_with_image_filename_is_rejected(
    client: TestClient, db_session
):
    fake_bytes = b"this is definitely not image data, just plain text padding"
    response = upload_files(client, [("nuts.jpg", fake_bytes, "image/jpeg")])

    assert response.status_code == 400
    assert db_session.query(DigitizationJob).count() == 0


def test_corrupt_image_is_rejected(client: TestClient, db_session):
    valid = make_image_bytes("PNG", size=(50, 50))
    truncated = valid[:20]  # sever the file well before any valid PNG data ends

    response = upload_files(client, [("broken.png", truncated, "image/png")])

    assert response.status_code == 400
    assert db_session.query(DigitizationJob).count() == 0


def test_oversized_file_is_rejected(client: TestClient, db_session):
    settings = get_settings()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"digitizer_max_file_size_bytes": 100}
    )
    try:
        response = upload_files(
            client, [("nuts.jpg", make_image_bytes("JPEG", size=(200, 200)), "image/jpeg")]
        )
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 400
    assert db_session.query(DigitizationJob).count() == 0


def test_maximum_image_count_is_enforced(client: TestClient, db_session):
    settings = get_settings()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"digitizer_max_images_per_job": 2}
    )
    try:
        response = upload_files(
            client,
            [
                ("a.jpg", make_image_bytes("JPEG"), "image/jpeg"),
                ("b.jpg", make_image_bytes("JPEG"), "image/jpeg"),
                ("c.jpg", make_image_bytes("JPEG"), "image/jpeg"),
            ],
        )
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 400
    assert "at most 2" in response.json()["detail"]
    assert db_session.query(DigitizationJob).count() == 0


def test_one_invalid_file_fails_the_whole_batch(
    client: TestClient, db_session, tmp_path: Path
):
    """Multi-file uploads behave as a single job: one bad file rejects all."""
    response = upload_files(
        client,
        [
            ("a.jpg", make_image_bytes("JPEG"), "image/jpeg"),
            ("bad.jpg", b"not an image", "image/jpeg"),
        ],
    )

    assert response.status_code == 400
    assert db_session.query(DigitizationJob).count() == 0
    # No orphaned job directories left behind after the failed batch.
    digitizer_root = tmp_path / "uploads" / "digitizer"
    assert not digitizer_root.exists() or list(digitizer_root.iterdir()) == []


# --- Safe filenames / path traversal ---------------------------------------


def test_generated_filenames_are_safe_and_ignore_client_filename(
    client: TestClient, tmp_path: Path
):
    response = upload_files(
        client, [("../../evil.jpg", make_image_bytes("JPEG"), "image/jpeg")]
    )

    assert response.status_code == 201
    body = response.json()
    stored_name = body["source_images"][0]

    assert ".." not in stored_name
    assert "/" not in stored_name and "\\" not in stored_name
    assert stored_name != "evil.jpg"

    job_dir = tmp_path / "uploads" / "digitizer" / body["id"] / "source"
    assert (job_dir / stored_name).is_file()
    # Nothing was written outside the job's own directory.
    uploads_root = tmp_path / "uploads"
    all_files = [p for p in uploads_root.rglob("*") if p.is_file()]
    assert all(p.parent == job_dir for p in all_files)


# --- Job retrieval -----------------------------------------------------------


def test_list_jobs_returns_newest_first(client: TestClient):
    first = upload_files(client, [("a.jpg", make_image_bytes("JPEG"), "image/jpeg")])
    second = upload_files(client, [("b.jpg", make_image_bytes("JPEG"), "image/jpeg")])

    response = client.get("/api/digitizer/jobs")

    assert response.status_code == 200
    jobs = response.json()
    ids = [job["id"] for job in jobs]
    assert ids.index(second.json()["id"]) < ids.index(first.json()["id"])


def test_get_job_detail_returns_source_images(client: TestClient):
    created = upload_files(
        client,
        [
            ("a.jpg", make_image_bytes("JPEG"), "image/jpeg"),
            ("b.png", make_image_bytes("PNG"), "image/png"),
        ],
    )
    job_id = created.json()["id"]

    response = client.get(f"/api/digitizer/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job_id
    assert len(body["source_images"]) == 2


def test_get_unknown_job_returns_404(client: TestClient):
    response = client.get(f"/api/digitizer/jobs/{uuid.uuid4()}")

    assert response.status_code == 404


# --- Existing endpoints unaffected ------------------------------------------


def test_health_endpoint_still_works(client: TestClient):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
