"""Integration tests for Milestone 6's LOCAL (Tier1+rembg) image
refinement path, exercised through the real API/DB/storage stack. The
real rembg model is NEVER invoked -- `get_product_image_refiner` is
always overridden with a LocalBackgroundRefiner wrapping a scripted fake
BackgroundRemover. See test_ai_image_refiner.py and
test_digitizer_ai_refinement.py for the AI (OpenRouter Images API) path,
which is mocked separately and never makes a real network call either."""
import uuid
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.api.digitizer import get_product_image_refiner
from app.main import app
from app.models.digitized_product import DigitizedProduct
from app.services.image_refinement_service import LocalBackgroundRefiner
from tests.test_digitizer_processing import make_detected_product, make_image_bytes, upload_job, use_fake_analyzer


class FakeBackgroundRemover:
    """Retains the entire subject unchanged (fully opaque) -- simulates a
    clean, successful isolation that easily clears the retained-area
    safety check."""

    def __init__(self) -> None:
        self.calls = 0

    def remove(self, image_bytes: bytes) -> bytes:
        self.calls += 1
        with Image.open(BytesIO(image_bytes)) as source:
            rgba = source.convert("RGBA")
        buffer = BytesIO()
        rgba.save(buffer, format="PNG")
        return buffer.getvalue()


class DestructiveBackgroundRemover:
    """Simulates a segmentation pass that erased almost all of the real
    product -- correct dimensions, but only a tiny opaque speck survives.
    Used to prove the safety net rejects this and falls back safely."""

    def __init__(self) -> None:
        self.calls = 0

    def remove(self, image_bytes: bytes) -> bytes:
        self.calls += 1
        with Image.open(BytesIO(image_bytes)) as source:
            width, height = source.size
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        speck_side = max(1, min(width, height) // 20)
        speck = Image.new("RGBA", (speck_side, speck_side), (120, 60, 10, 255))
        canvas.paste(speck, (0, 0))
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()


def use_fake_background_remover() -> FakeBackgroundRemover:
    fake = FakeBackgroundRemover()
    app.dependency_overrides[get_product_image_refiner] = lambda: LocalBackgroundRefiner(fake)
    return fake


def use_destructive_background_remover() -> DestructiveBackgroundRemover:
    fake = DestructiveBackgroundRemover()
    app.dependency_overrides[get_product_image_refiner] = lambda: LocalBackgroundRefiner(fake)
    return fake


def create_processed_product(client: TestClient, **detected_overrides) -> dict:
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(**detected_overrides)]])
    processed = client.post(f"/api/digitizer/jobs/{job['id']}/process").json()
    return processed["candidates"][0]


def _crop_path(tmp_path: Path, candidate: dict) -> Path:
    return tmp_path / "uploads" / "digitizer" / candidate["job_id"] / "products" / candidate["crop_image"]


def _source_path(tmp_path: Path, candidate: dict) -> Path:
    return tmp_path / "uploads" / "digitizer" / candidate["job_id"] / "source" / candidate["source_image"]


def _refined_dir(tmp_path: Path, candidate: dict) -> Path:
    return tmp_path / "uploads" / "digitizer" / candidate["job_id"] / "products" / "refined"


# --- Successful single-item refinement, originals preserved --------------


def test_refine_produces_a_distinct_file_without_touching_the_crop(client: TestClient, tmp_path: Path):
    use_fake_background_remover()
    candidate = create_processed_product(client, presentation="packaged")
    crop_path = _crop_path(tmp_path, candidate)
    original_crop_bytes = crop_path.read_bytes()

    response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert response.status_code == 200
    body = response.json()
    assert body["image_refinement_status"] == "refined"
    assert body["refined_image"] is not None
    assert body["refined_image"] != body["crop_image"]
    assert crop_path.read_bytes() == original_crop_bytes

    refined_path = _refined_dir(tmp_path, candidate) / body["refined_image"]
    assert refined_path.is_file()
    with Image.open(refined_path) as refined:
        assert refined.size == (1200, 1200)


def test_source_image_is_never_touched_by_refinement(client: TestClient, tmp_path: Path):
    use_fake_background_remover()
    candidate = create_processed_product(client, presentation="bulk_tray")
    source_path = _source_path(tmp_path, candidate)
    original_source_bytes = source_path.read_bytes()

    client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert source_path.read_bytes() == original_source_bytes


# --- Background isolation now covers every suitable presentation --------


def test_packaged_jar_bottle_bulk_tray_bulk_loose_all_attempt_background_isolation(
    client: TestClient, tmp_path: Path
):
    """The core corrected behavior: bulk/loose products are no longer
    excluded from Tier 2 -- every suitable presentation attempts it."""
    for presentation in ("packaged", "jar", "bottle", "bulk_tray", "bulk_loose"):
        fake = use_fake_background_remover()
        candidate = create_processed_product(client, presentation=presentation)

        response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

        assert fake.calls == 1
        body = response.json()
        assert body["image_refinement_status"] == "refined"
        assert body["background_isolation_status"] == "applied"


def test_uncertain_presentation_never_attempts_background_isolation(client: TestClient, tmp_path: Path):
    for presentation in ("other",):
        fake = use_fake_background_remover()
        candidate = create_processed_product(client, presentation=presentation)

        response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

        assert fake.calls == 0
        body = response.json()
        assert body["image_refinement_status"] == "refined"
        assert body["background_isolation_status"] == "not_attempted"


def test_destructive_isolation_on_a_bulk_product_falls_back_safely(
    client: TestClient, db_session: Session, tmp_path: Path
):
    """Background removal on loose/bulk products is harder -- a result
    that erased too much of the real pile must be rejected, not trusted.
    The original crop stays intact, no candidate is deleted, and the
    overall refinement still succeeds via the Tier-1-only fallback."""
    use_destructive_background_remover()
    candidate = create_processed_product(client, presentation="bulk_tray")
    crop_path = _crop_path(tmp_path, candidate)
    original_crop_bytes = crop_path.read_bytes()

    response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert response.status_code == 200
    body = response.json()
    assert body["image_refinement_status"] == "refined"  # still usable overall
    assert body["background_isolation_status"] == "rejected"  # flagged for later review
    assert body["refined_image"] is not None
    assert crop_path.read_bytes() == original_crop_bytes  # original crop untouched

    with Image.open(_refined_dir(tmp_path, candidate) / body["refined_image"]) as refined:
        assert refined.size == (1200, 1200)

    remaining = db_session.query(DigitizedProduct).filter(DigitizedProduct.id == uuid.UUID(candidate["id"])).count()
    assert remaining == 1  # never deleted


def test_destructive_isolation_on_bulk_loose_also_falls_back_safely(client: TestClient, tmp_path: Path):
    use_destructive_background_remover()
    candidate = create_processed_product(client, presentation="bulk_loose")

    response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert response.status_code == 200
    body = response.json()
    assert body["image_refinement_status"] == "refined"
    assert body["background_isolation_status"] == "rejected"


# --- Failure safety ----------------------------------------------------------


def test_unreadable_crop_leaves_the_product_usable_and_returns_502(client: TestClient, tmp_path: Path):
    use_fake_background_remover()
    candidate = create_processed_product(client, presentation="packaged")
    crop_path = _crop_path(tmp_path, candidate)
    crop_path.write_bytes(b"not-a-real-image")  # simulate on-disk corruption

    response = client.post(f"/api/digitizer/products/{candidate['id']}/refine")

    assert response.status_code == 502
    unchanged = client.get(f"/api/digitizer/jobs/{candidate['job_id']}").json()
    product_after = unchanged["candidates"][0]
    assert product_after["image_refinement_status"] == "failed"
    assert product_after["refined_image"] is None


# --- Individual retry / Re-refine -----------------------------------------


def test_explicit_re_refine_replaces_the_refined_image_and_cleans_up_the_old_file(
    client: TestClient, tmp_path: Path
):
    use_fake_background_remover()
    candidate = create_processed_product(client, presentation="packaged")
    refined_dir = _refined_dir(tmp_path, candidate)

    first = client.post(f"/api/digitizer/products/{candidate['id']}/refine").json()
    first_filename = first["refined_image"]
    assert (refined_dir / first_filename).is_file()

    second = client.post(f"/api/digitizer/products/{candidate['id']}/refine").json()
    second_filename = second["refined_image"]

    assert second_filename != first_filename
    assert (refined_dir / second_filename).is_file()
    assert not (refined_dir / first_filename).exists()


def test_re_refine_works_even_after_a_prior_failure(client: TestClient, tmp_path: Path):
    use_fake_background_remover()
    candidate = create_processed_product(client, presentation="packaged")
    crop_path = _crop_path(tmp_path, candidate)
    crop_path.write_bytes(b"not-a-real-image")
    failed = client.post(f"/api/digitizer/products/{candidate['id']}/refine")
    assert failed.status_code == 502

    # restore a valid crop, as if the underlying M4 crop were fine again
    valid_jpeg = BytesIO()
    Image.new("RGB", (200, 200), (10, 20, 30)).save(valid_jpeg, format="JPEG")
    crop_path.write_bytes(valid_jpeg.getvalue())

    retried = client.post(f"/api/digitizer/products/{candidate['id']}/refine")
    assert retried.status_code == 200
    assert retried.json()["image_refinement_status"] == "refined"


# --- Error handling ------------------------------------------------------


def test_refine_unknown_product_returns_404(client: TestClient):
    use_fake_background_remover()
    response = client.post(f"/api/digitizer/products/{uuid.uuid4()}/refine")
    assert response.status_code == 404


# --- Job-level convenience endpoint ---------------------------------------


def test_job_level_refine_refines_every_candidate(client: TestClient, tmp_path: Path):
    fake = use_fake_background_remover()
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer(
        [
            [
                make_detected_product(name_en="Almonds", presentation="packaged"),
                make_detected_product(name_en="Loose Cashews", bbox=[500, 500, 900, 900], presentation="bulk_tray"),
            ]
        ]
    )
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    response = client.post(f"/api/digitizer/jobs/{job['id']}/refine")

    assert response.status_code == 200
    statuses = {c["image_refinement_status"] for c in response.json()["candidates"]}
    assert statuses == {"refined"}
    # both the packaged item AND the bulk_tray item now attempt isolation
    assert fake.calls == 2
    isolation_statuses = {c["background_isolation_status"] for c in response.json()["candidates"]}
    assert isolation_statuses == {"applied"}


def test_job_level_refine_skips_products_already_refined(client: TestClient, tmp_path: Path):
    fake = use_fake_background_remover()
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(name_en="Almonds", presentation="packaged")]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    first = client.post(f"/api/digitizer/jobs/{job['id']}/refine")
    assert first.json()["candidates"][0]["image_refinement_status"] == "refined"
    assert fake.calls == 1

    second = client.post(f"/api/digitizer/jobs/{job['id']}/refine")
    assert fake.calls == 1  # not invoked again
    assert second.json()["candidates"][0]["image_refinement_status"] == "refined"


def test_job_level_refine_retries_a_product_whose_earlier_attempt_failed(
    client: TestClient, tmp_path: Path
):
    use_fake_background_remover()
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(name_en="Almonds", presentation="packaged")]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    processed = client.get(f"/api/digitizer/jobs/{job['id']}").json()
    candidate = processed["candidates"][0]
    crop_path = _crop_path(tmp_path, candidate)
    crop_path.write_bytes(b"not-a-real-image")

    first = client.post(f"/api/digitizer/jobs/{job['id']}/refine")
    assert first.json()["candidates"][0]["image_refinement_status"] == "failed"

    valid_jpeg = BytesIO()
    Image.new("RGB", (200, 200), (10, 20, 30)).save(valid_jpeg, format="JPEG")
    crop_path.write_bytes(valid_jpeg.getvalue())

    second = client.post(f"/api/digitizer/jobs/{job['id']}/refine")
    assert second.json()["candidates"][0]["image_refinement_status"] == "refined"


def test_job_level_refine_marks_a_missing_crop_as_skipped(
    client: TestClient, db_session: Session, tmp_path: Path
):
    use_fake_background_remover()
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(name_en="Almonds")]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")
    processed = client.get(f"/api/digitizer/jobs/{job['id']}").json()
    product_id = processed["candidates"][0]["id"]

    product = db_session.get(DigitizedProduct, uuid.UUID(product_id))
    product.crop_image = None
    db_session.add(product)
    db_session.commit()

    response = client.post(f"/api/digitizer/jobs/{job['id']}/refine")

    updated = next(c for c in response.json()["candidates"] if c["id"] == product_id)
    assert updated["image_refinement_status"] == "skipped"

    # A repeat call must not keep re-attempting a candidate that can never
    # succeed -- still skipped, not re-marked/re-touched.
    response2 = client.post(f"/api/digitizer/jobs/{job['id']}/refine")
    updated2 = next(c for c in response2.json()["candidates"] if c["id"] == product_id)
    assert updated2["image_refinement_status"] == "skipped"


def test_refine_job_unknown_job_returns_404(client: TestClient):
    use_fake_background_remover()
    response = client.post(f"/api/digitizer/jobs/{uuid.uuid4()}/refine")
    assert response.status_code == 404
