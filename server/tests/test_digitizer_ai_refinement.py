"""Integration tests for Milestone 6's AI (OpenRouter Images API) image
refinement path, exercised through the real API/DB/storage stack. NO real
network call is made anywhere here -- `get_product_image_refiner` is
overridden with a scripted fake ProductImageRefiner, never the real
AIProductImageRefiner class. See test_ai_image_refiner.py for
AIProductImageRefiner's own unit tests (mocked via httpx.MockTransport)."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.api.digitizer import get_product_image_refiner
from app.core.config import Settings
from app.main import app
from app.models.enums import BackgroundIsolationStatus
from app.services.image_refinement_service import (
    LocalBackgroundRefiner,
    RefinementRequest,
    RefinementResult,
)
from tests.test_digitizer_processing import make_detected_product, make_image_bytes, upload_job, use_fake_analyzer


def _make_refined_jpeg(color=(250, 250, 250)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1200, 1200), color).save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


class FakeAIRefiner:
    """Scripted ProductImageRefiner standing in for the real
    AIProductImageRefiner -- pops one outcome per `refine()` call, in call
    order. An outcome that is an Exception instance is raised instead of
    returned, mirroring FakeAnalyzer/FakeEnricher in this test suite."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[RefinementRequest] = []

    def refine(self, request: RefinementRequest) -> RefinementResult:
        self.calls.append(request)
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def use_fake_ai_refiner(script: list) -> FakeAIRefiner:
    fake = FakeAIRefiner(script)
    app.dependency_overrides[get_product_image_refiner] = lambda: fake
    return fake


def create_processed_product(client: TestClient, **detected_overrides) -> dict:
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(**detected_overrides)]])
    processed = client.post(f"/api/digitizer/jobs/{job['id']}/process").json()
    return processed["candidates"][0]


def _crop_path(tmp_path: Path, candidate: dict) -> Path:
    return tmp_path / "uploads" / "digitizer" / candidate["job_id"] / "products" / candidate["crop_image"]


def _refined_dir(tmp_path: Path, candidate: dict) -> Path:
    return tmp_path / "uploads" / "digitizer" / candidate["job_id"] / "products" / "refined"


def _applied(image_bytes: bytes) -> RefinementResult:
    return RefinementResult(image_bytes=image_bytes, background_isolation_status=BackgroundIsolationStatus.APPLIED)


# --- Successful AI refinement -----------------------------------------------


def test_successful_ai_refinement_is_stored_separately_from_the_crop(client: TestClient, tmp_path: Path):
    use_fake_ai_refiner([_applied(_make_refined_jpeg())])
    candidate = create_processed_product(client, presentation="bulk_tray")
    crop_path = _crop_path(tmp_path, candidate)
    original_crop_bytes = crop_path.read_bytes()

    response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert response.status_code == 200
    body = response.json()
    assert body["image_refinement_status"] == "refined"
    assert body["background_isolation_status"] == "applied"
    assert body["refined_image"] is not None
    assert body["refined_image"] != body["crop_image"]
    assert crop_path.read_bytes() == original_crop_bytes  # untouched

    refined_path = _refined_dir(tmp_path, candidate) / body["refined_image"]
    assert refined_path.is_file()
    with Image.open(refined_path) as refined:
        assert refined.size == (1200, 1200)


def test_ai_refiner_receives_the_real_crop_and_product_context(client: TestClient, tmp_path: Path):
    fake = use_fake_ai_refiner([_applied(_make_refined_jpeg())])
    candidate = create_processed_product(client, presentation="bulk_tray", name_en="Mixed Nuts")
    crop_path = _crop_path(tmp_path, candidate)

    client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request.crop_bytes == crop_path.read_bytes()
    assert request.context.name_en == "Mixed Nuts"
    assert isinstance(request.reference_images, list)


# --- Failure handling: originals and previous results are protected --------


def test_ai_refinement_failure_preserves_the_original_crop_and_marks_failed(
    client: TestClient, tmp_path: Path
):
    use_fake_ai_refiner([RuntimeError("simulated AI failure")])
    candidate = create_processed_product(client, presentation="bulk_tray")
    crop_path = _crop_path(tmp_path, candidate)
    original_crop_bytes = crop_path.read_bytes()

    response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert response.status_code == 502
    assert crop_path.read_bytes() == original_crop_bytes

    unchanged = client.get(f"/api/digitizer/jobs/{candidate['job_id']}").json()
    product_after = unchanged["candidates"][0]
    assert product_after["image_refinement_status"] == "failed"
    assert product_after["refined_image"] is None


def test_ai_refinement_failure_preserves_a_previous_valid_refined_image(
    client: TestClient, tmp_path: Path
):
    use_fake_ai_refiner([_applied(_make_refined_jpeg())])
    candidate = create_processed_product(client, presentation="bulk_tray")
    first = client.post(f"/api/digitizer/products/{candidate['id']}/refine").json()
    first_refined_filename = first["refined_image"]
    refined_dir = _refined_dir(tmp_path, candidate)
    first_refined_bytes = (refined_dir / first_refined_filename).read_bytes()

    use_fake_ai_refiner([RuntimeError("simulated AI failure on re-refine")])
    second = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert second.status_code == 502
    # The previous refined file on disk is completely untouched...
    assert (refined_dir / first_refined_filename).read_bytes() == first_refined_bytes
    # ...and the DB row still points at it -- only the status flips to
    # failed, so the failed attempt is visible without losing the last
    # good result.
    unchanged = client.get(f"/api/digitizer/jobs/{candidate['job_id']}").json()
    product_after = unchanged["candidates"][0]
    assert product_after["refined_image"] == first_refined_filename
    assert product_after["image_refinement_status"] == "failed"


def test_only_one_ai_attempt_is_made_per_manual_refine_click(client: TestClient, tmp_path: Path):
    fake = use_fake_ai_refiner([RuntimeError("simulated AI failure")])
    candidate = create_processed_product(client, presentation="bulk_tray")

    client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert len(fake.calls) == 1


# --- Provider selection: AI when configured, local otherwise --------------
# (direct unit-style calls -- no HTTP round trip needed for this)


def test_get_product_image_refiner_selects_ai_when_api_key_configured():
    from app.services.ai.image_editing_refiner import AIProductImageRefiner

    refiner = get_product_image_refiner(settings=Settings(openrouter_api_key="fake-key-not-real"))

    assert isinstance(refiner, AIProductImageRefiner)


def test_get_product_image_refiner_selects_local_when_no_api_key_configured():
    refiner = get_product_image_refiner(settings=Settings(openrouter_api_key=None))

    assert isinstance(refiner, LocalBackgroundRefiner)
