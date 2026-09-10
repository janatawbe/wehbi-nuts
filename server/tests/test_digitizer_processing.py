import re
import uuid
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api.digitizer import get_ai_analyzer
from app.main import app
from app.models.digitized_product import DigitizedProduct
from app.services.ai.errors import AIInvalidResponseError, AIServiceUnavailableError
from app.services.ai.types import DetectedProduct
from app.services.digitizer_processing_service import _bbox_to_pixels, _encode_crop

SAFE_FILENAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


def make_image_bytes(width: int = 400, height: int = 300, fmt: str = "JPEG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(120, 60, 10)).save(buffer, format=fmt)
    return buffer.getvalue()


def make_detected_product(**overrides) -> DetectedProduct:
    defaults = dict(
        name_en="Almonds",
        name_ar="لوز",
        category="Nuts",
        presentation="packaged",
        bbox=[100, 100, 800, 800],
        confidence=0.9,
        visible_text="ALMONDS 500G",
        identification_basis="visual_and_text",
        notes=None,
    )
    defaults.update(overrides)
    return DetectedProduct(**defaults)


class FakeAnalyzer:
    """A scripted AIProductAnalyzer: pops one entry per `analyze_image`
    call, in call order. An entry that is an Exception instance is raised
    instead of returned, simulating a per-image AI failure."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[tuple[int, str]] = []

    def analyze_image(self, image_bytes: bytes, mime_type: str) -> list[DetectedProduct]:
        self.calls.append((len(image_bytes), mime_type))
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def use_fake_analyzer(script: list) -> FakeAnalyzer:
    fake = FakeAnalyzer(script)
    app.dependency_overrides[get_ai_analyzer] = lambda: fake
    return fake


def upload_job(client: TestClient, *jpeg_bytes: bytes) -> dict:
    files = [("files", (f"shelf{i}.jpg", data, "image/jpeg")) for i, data in enumerate(jpeg_bytes)]
    response = client.post("/api/digitizer/jobs", files=files)
    assert response.status_code == 201
    return response.json()


# --- bbox / crop unit tests --------------------------------------------


def test_bbox_normalized_to_pixel_conversion():
    # Full-image normalized box on a 400x300 image.
    assert _bbox_to_pixels([0, 0, 1000, 1000], 400, 300) == (0, 0, 400, 300)


def test_bbox_conversion_scales_proportionally():
    # [ymin=250, xmin=250, ymax=750, xmax=750] is the centered half of the
    # image on both axes.
    x, y, w, h = _bbox_to_pixels([250, 250, 750, 750], 400, 300)
    assert x == 100 and w == 200
    assert y == 75 and h == 150


def test_bbox_conversion_clamps_out_of_range_coordinates():
    # A pydantic-valid DetectedProduct always keeps bbox within [0, 1000],
    # but pixel rounding could in principle push a value 1 past an edge;
    # clamping must still hold the box inside the image.
    result = _bbox_to_pixels([0, 0, 1000, 1000], 1, 1)
    assert result == (0, 0, 1, 1)


def test_bbox_conversion_rejects_degenerate_box():
    # A box thinner than one pixel on a small image collapses after
    # rounding -- must be reported as invalid (None), not a 0-area crop.
    assert _bbox_to_pixels([500, 500, 501, 501], 10, 10) is None


def test_encode_crop_produces_decodable_jpeg_matching_bbox_size():
    image = Image.new("RGB", (400, 300), color=(10, 20, 30))
    crop_bytes = _encode_crop(image, (50, 50, 100, 80))

    assert crop_bytes is not None
    with Image.open(BytesIO(crop_bytes)) as decoded:
        decoded.load()
        assert decoded.size == (100, 80)


def test_encode_crop_rejects_degenerate_box():
    image = Image.new("RGB", (400, 300), color=(10, 20, 30))
    assert _encode_crop(image, (50, 50, 0, 80)) is None


def test_encode_crop_never_upscales_or_distorts_aspect_ratio():
    image = Image.new("RGB", (400, 300), color=(10, 20, 30))
    crop_bytes = _encode_crop(image, (0, 0, 200, 150))

    with Image.open(BytesIO(crop_bytes)) as decoded:
        decoded.load()
        # Exactly the requested pixel region -- same aspect ratio (4:3),
        # no resampling to a different size.
        assert decoded.size == (200, 150)


# --- Processing: successful cases -------------------------------------


def test_process_job_with_single_product(client: TestClient):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product()]])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["processed_items"] == 1
    assert body["failed_items"] == 0
    assert len(body["candidates"]) == 1
    candidate = body["candidates"][0]
    assert candidate["name_en"] == "Almonds"
    assert candidate["name_ar"] == "لوز"
    assert candidate["presentation"] == "packaged"
    assert candidate["identification_basis"] == "visual_and_text"
    assert candidate["visible_text"] == "ALMONDS 500G"
    assert candidate["category_suggestion"] == "Nuts"
    assert candidate["review_status"] == "draft"
    assert candidate["needs_review"] is True
    assert candidate["product_id"] is None
    assert float(candidate["ai_confidence"]) == 0.9


def test_process_job_with_multiple_products(client: TestClient):
    job = upload_job(client, make_image_bytes())
    products = [
        make_detected_product(name_en="Almonds", bbox=[0, 0, 400, 400]),
        make_detected_product(name_en="Coffee", bbox=[500, 500, 900, 900]),
    ]
    use_fake_analyzer([products])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    assert response.status_code == 200
    names = sorted(c["name_en"] for c in response.json()["candidates"])
    assert names == ["Almonds", "Coffee"]


def test_bulk_tray_scene_is_one_candidate(client: TestClient):
    """A bulk tray must surface as exactly one DigitizedProduct draft, not
    one per piece inside it -- the AI provider is trusted to have already applied
    that judgment (see the system instruction); this test locks in that
    the processing pipeline does not somehow split or duplicate it."""
    job = upload_job(client, make_image_bytes())
    tray = make_detected_product(
        name_en="Mixed Roasted Nuts",
        presentation="bulk_tray",
        identification_basis="visual",
        visible_text=None,
        bbox=[0, 0, 1000, 1000],
    )
    use_fake_analyzer([[tray]])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    candidates = response.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["presentation"] == "bulk_tray"


def test_zero_item_result_completes_the_job_without_error(client: TestClient):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[]])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert body["status"] == "completed"
    assert body["processed_items"] == 1
    assert body["failed_items"] == 0
    assert body["error_message"] is None
    assert body["candidates"] == []


def test_multi_image_job_combines_candidates_from_all_images(client: TestClient):
    job = upload_job(client, make_image_bytes(), make_image_bytes(width=300, height=300))
    use_fake_analyzer(
        [
            [make_detected_product(name_en="Almonds")],
            [make_detected_product(name_en="Coffee"), make_detected_product(name_en="Dates")],
        ]
    )

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert body["status"] == "completed"
    assert body["processed_items"] == 2
    assert body["failed_items"] == 0
    assert len(body["candidates"]) == 3


def test_crop_files_created_and_bbox_matches_persisted_size(client: TestClient, tmp_path: Path):
    job = upload_job(client, make_image_bytes(width=400, height=300))
    use_fake_analyzer([[make_detected_product(bbox=[0, 0, 500, 500])]])  # top-left quarter

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")
    candidate = response.json()["candidates"][0]

    assert candidate["bbox_x"] == 0 and candidate["bbox_y"] == 0
    assert candidate["bbox_width"] == 200 and candidate["bbox_height"] == 150

    products_dir = tmp_path / "uploads" / "digitizer" / job["id"] / "products"
    crop_files = list(products_dir.iterdir())
    assert len(crop_files) == 1
    assert SAFE_FILENAME.match(crop_files[0].name)

    with Image.open(crop_files[0]) as decoded:
        decoded.load()
        assert decoded.size == (200, 150)


def test_source_image_unchanged_after_processing(client: TestClient, tmp_path: Path):
    original_bytes = make_image_bytes()
    job = upload_job(client, original_bytes)
    use_fake_analyzer([[make_detected_product()]])

    source_dir = tmp_path / "uploads" / "digitizer" / job["id"] / "source"
    source_file = next(source_dir.iterdir())
    before = source_file.read_bytes()

    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    assert source_file.read_bytes() == before


# --- Processing: failure handling --------------------------------------


def test_one_image_failing_is_recorded_without_failing_the_whole_job(client: TestClient):
    job = upload_job(client, make_image_bytes(), make_image_bytes())
    use_fake_analyzer(
        [
            AIServiceUnavailableError("OpenAI was unavailable."),
            [make_detected_product(name_en="Coffee")],
        ]
    )

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert body["status"] == "completed"
    assert body["processed_items"] == 1
    assert body["failed_items"] == 1
    assert body["error_message"] is not None
    assert "OpenAI was unavailable." in body["error_message"]
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["name_en"] == "Coffee"


def test_all_images_failing_marks_job_failed(client: TestClient):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([AIServiceUnavailableError("OpenAI was unavailable.")])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "failed"
    assert body["processed_items"] == 0
    assert body["failed_items"] == 1
    assert body["error_message"] is not None
    assert body["candidates"] == []


def test_rate_limit_failure_surfaces_the_real_reason_not_a_generic_message(client: TestClient):
    """Regression test for a production incident: an OpenAI rate-limit
    was swallowed into the generic "Digitization failed for all source
    images." with no indication of the actual cause. The job's
    error_message must now include the specific, client-safe reason the
    AI service raised."""
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer(
        [
            AIServiceUnavailableError(
                "OpenAI's rate limit was exceeded for this image after 3 attempts. "
                "Wait a while before retrying, or process fewer images at once."
            )
        ]
    )

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert body["status"] == "failed"
    assert "rate limit" in body["error_message"].lower()
    assert body["error_message"] != "Digitization failed for all source images."


def test_unexpected_non_ai_error_gets_a_generic_safe_message(client: TestClient, tmp_path: Path):
    """An error that is NOT a known, client-safe AIAnalysisError (e.g. a
    corrupt/unreadable source image on disk) must still fail that image
    cleanly, but must never leak an internal detail such as a filesystem
    path into the job's error_message."""
    job = upload_job(client, make_image_bytes())
    source_dir = tmp_path / "uploads" / "digitizer" / job["id"] / "source"
    source_file = next(source_dir.iterdir())
    source_file.write_bytes(b"not actually an image anymore")
    use_fake_analyzer([[make_detected_product()]])  # never reached: the image can't even be read

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert body["status"] == "failed"
    assert str(source_dir) not in body["error_message"]
    assert str(tmp_path) not in body["error_message"]


def test_malformed_ai_response_is_treated_as_a_failed_image(client: TestClient):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([AIInvalidResponseError("OpenAI's response did not match the schema.")])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    body = response.json()
    assert body["status"] == "failed"
    assert body["failed_items"] == 1


def test_process_unknown_job_returns_404(client: TestClient):
    use_fake_analyzer([[]])
    response = client.post(f"/api/digitizer/jobs/{uuid.uuid4()}/process")

    assert response.status_code == 404


def test_process_job_with_no_source_images_is_rejected(client: TestClient, tmp_path: Path):
    job = upload_job(client, make_image_bytes())
    source_dir = tmp_path / "uploads" / "digitizer" / job["id"] / "source"
    for f in source_dir.iterdir():
        f.unlink()
    use_fake_analyzer([[]])

    response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    assert response.status_code == 400


def test_ai_service_not_configured_returns_503_without_leaking_details(client: TestClient):
    # No override of get_ai_analyzer -- exercises the real dependency,
    # which requires a configured API key.
    from app.core.config import Settings, get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(openai_api_key=None)
    try:
        job = upload_job(client, make_image_bytes())
        response = client.post(f"/api/digitizer/jobs/{job['id']}/process")
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 503
    assert "key" not in response.json()["detail"].lower()


# --- Rerun behavior ------------------------------------------------------


def test_rerun_does_not_accumulate_duplicate_candidates(
    client: TestClient, db_session, tmp_path: Path
):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product()]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    use_fake_analyzer([[make_detected_product()]])
    second_response = client.post(f"/api/digitizer/jobs/{job['id']}/process")

    assert len(second_response.json()["candidates"]) == 1
    candidates = (
        db_session.query(DigitizedProduct)
        .filter(DigitizedProduct.job_id == uuid.UUID(job["id"]))
        .all()
    )
    assert len(candidates) == 1  # not 2

    products_dir = tmp_path / "uploads" / "digitizer" / job["id"] / "products"
    assert len(list(products_dir.iterdir())) == 1  # not 2


# --- GET job returns digitized products -------------------------------


def test_get_job_returns_persisted_candidates(client: TestClient):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product()]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    response = client.get(f"/api/digitizer/jobs/{job['id']}")

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["crop_image"] is not None
    assert candidates[0]["source_image"] is not None


def test_new_job_has_no_candidates_before_processing(client: TestClient):
    job = upload_job(client, make_image_bytes())

    response = client.get(f"/api/digitizer/jobs/{job['id']}")

    assert response.json()["candidates"] == []


# --- Media endpoint --------------------------------------------------------


def test_media_endpoint_serves_crop_image(client: TestClient):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product()]])
    processed = client.post(f"/api/digitizer/jobs/{job['id']}/process").json()
    crop_filename = processed["candidates"][0]["crop_image"]

    response = client.get(f"/api/digitizer/jobs/{job['id']}/media/products/{crop_filename}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0


def test_media_endpoint_serves_source_image(client: TestClient):
    job = upload_job(client, make_image_bytes())
    source_filename = job["source_images"][0]

    response = client.get(f"/api/digitizer/jobs/{job['id']}/media/source/{source_filename}")

    assert response.status_code == 200
    with Image.open(BytesIO(response.content)) as decoded:
        decoded.load()


def test_media_endpoint_rejects_path_traversal_filename(client: TestClient):
    job = upload_job(client, make_image_bytes())

    response = client.get(
        f"/api/digitizer/jobs/{job['id']}/media/source/..%2F..%2F..%2Fetc%2Fpasswd"
    )

    assert response.status_code == 404


def test_media_endpoint_rejects_unknown_kind(client: TestClient):
    job = upload_job(client, make_image_bytes())
    source_filename = job["source_images"][0]

    response = client.get(f"/api/digitizer/jobs/{job['id']}/media/other/{source_filename}")

    assert response.status_code == 422  # not one of the "source" | "products" literal values


def test_media_endpoint_rejects_unknown_job(client: TestClient):
    response = client.get(f"/api/digitizer/jobs/{uuid.uuid4()}/media/source/{'a' * 32}.jpg")

    assert response.status_code == 404


# --- API key never exposed --------------------------------------------


def test_api_key_never_appears_in_any_job_response(client: TestClient):
    from app.core.config import Settings, get_settings

    fake_key = "SECRET-OPENAI-KEY-FOR-TEST"
    app.dependency_overrides[get_settings] = lambda: Settings(openai_api_key=fake_key)
    try:
        job = upload_job(client, make_image_bytes())
        use_fake_analyzer([[make_detected_product()]])
        process_response = client.post(f"/api/digitizer/jobs/{job['id']}/process")
        get_response = client.get(f"/api/digitizer/jobs/{job['id']}")
    finally:
        del app.dependency_overrides[get_settings]

    assert fake_key not in process_response.text
    assert fake_key not in get_response.text
