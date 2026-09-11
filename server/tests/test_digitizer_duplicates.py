"""Integration tests for Milestone 6 duplicate detection, exercised
through the real API/DB stack. Fully local/deterministic -- no AI call
exists on this path at all, so nothing here needs mocking beyond the
already-established fake analyzer/enricher for getting candidates into a
comparable, enriched state first."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.digitized_product import DigitizedProduct
from app.models.digitized_product_duplicate_match import DigitizedProductDuplicateMatch
from tests.test_digitizer_enrichment import make_enrichment_response, use_fake_enricher
from tests.test_digitizer_processing import make_detected_product, make_image_bytes, upload_job, use_fake_analyzer


def _make_job(client: TestClient, detections: list[dict]) -> dict:
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(**d) for d in detections]])
    return client.post(f"/api/digitizer/jobs/{job['id']}/process").json()


def _enrich_all(client: TestClient, candidates: list[dict], responses: list) -> None:
    use_fake_enricher(list(responses))
    for candidate in candidates:
        response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")
        assert response.status_code == 200


def _packaged(name_en: str, bbox: list[int]) -> dict:
    return dict(name_en=name_en, bbox=bbox, presentation="packaged")


# --- Grouping: repeated identical packages ---------------------------------


def test_five_identical_packages_form_one_duplicate_group(client: TestClient, db_session: Session):
    detections = [
        _packaged("Choco Bar", [10 * i, 10 * i, 100 + 10 * i, 100 + 10 * i]) for i in range(5)
    ]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    candidates = processed["candidates"]
    _enrich_all(
        client,
        candidates,
        [
            make_enrichment_response(
                brand="ChocoCo", flavor_variant="Milk", selling_mode="unit", package_weight="0.100"
            )
            for _ in candidates
        ],
    )

    response = client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    assert response.status_code == 200
    body = response.json()["candidates"]
    group_ids = {c["duplicate_group_id"] for c in body}
    assert len(group_ids) == 1  # exactly one group id shared by all five
    for candidate in body:
        assert candidate["duplicate_group_id"] is not None
        assert candidate["duplicate_status"] in ("possible", "likely")
        assert len(candidate["duplicate_matches"]) == 4  # every other sibling


def test_reasons_and_scores_are_persisted_on_pairwise_matches(client: TestClient, db_session: Session):
    detections = [_packaged("Choco Bar", [0, 0, 100, 100]), _packaged("Choco Bar", [200, 200, 300, 300])]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    _enrich_all(
        client,
        processed["candidates"],
        [make_enrichment_response(brand="ChocoCo") for _ in processed["candidates"]],
    )

    response = client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    candidate = response.json()["candidates"][0]
    assert len(candidate["duplicate_matches"]) == 1
    match = candidate["duplicate_matches"][0]
    assert 0 <= float(match["score"]) <= 1
    assert isinstance(match["reasons"], list) and len(match["reasons"]) > 0
    assert match["matched_name_en"] == "Choco Bar"

    rows = db_session.query(DigitizedProductDuplicateMatch).all()
    assert len(rows) == 2  # stored in both directions
    for row in rows:
        assert 0 <= float(row.score) <= 1
        assert isinstance(row.reasons, list) and len(row.reasons) > 0


# --- Business-rule respect (spot checks; full matrix is unit-tested in
# test_duplicate_detection_service.py) --------------------------------


def test_different_flavor_is_not_flagged_as_duplicate(client: TestClient, db_session: Session):
    detections = [_packaged("Choco Bar", [0, 0, 100, 100]), _packaged("Choco Bar", [200, 200, 300, 300])]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    _enrich_all(
        client,
        processed["candidates"],
        [
            make_enrichment_response(brand="ChocoCo", flavor_variant="Milk"),
            make_enrichment_response(brand="ChocoCo", flavor_variant="Dark"),
        ],
    )

    response = client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    for candidate in response.json()["candidates"]:
        assert candidate["duplicate_status"] == "none"
        assert candidate["duplicate_matches"] == []


def test_un_enriched_products_are_never_flagged_as_duplicates(client: TestClient, db_session: Session):
    """selling_mode is still null before enrichment -- missing metadata
    must not manufacture a false-positive duplicate flag. They are also
    NOT downgraded to "none" (which would look identical to "compared,
    found nothing") -- they stay "not_checked", since they were never
    actually eligible for comparison at all."""
    detections = [_packaged("Choco Bar", [0, 0, 100, 100]), _packaged("Choco Bar", [200, 200, 300, 300])]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    # deliberately skip enrichment

    response = client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    for candidate in response.json()["candidates"]:
        assert candidate["duplicate_status"] == "not_checked"
        assert candidate["duplicate_group_id"] is None

    summary = response.json()["duplicate_summary"]
    assert summary["total_candidates"] == 2
    assert summary["eligible_candidates"] == 0
    assert summary["skipped_not_enriched"] == 2


def test_incomplete_enrichment_only_compares_the_enriched_candidates(
    client: TestClient, db_session: Session
):
    """A job with a mix of enriched and not-yet-enriched candidates must
    compare only the enriched ones -- an un-enriched candidate stays
    "not_checked" and is never matched against anything, even if its raw
    M4 name/category would otherwise look identical to an enriched
    sibling."""
    detections = [
        _packaged("Choco Bar", [0, 0, 100, 100]),
        _packaged("Choco Bar", [200, 200, 300, 300]),
        _packaged("Choco Bar", [400, 400, 500, 500]),
    ]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    candidates = processed["candidates"]
    # Only enrich the first two -- the third is deliberately left PENDING.
    _enrich_all(
        client,
        candidates[:2],
        [make_enrichment_response(brand="ChocoCo") for _ in candidates[:2]],
    )

    response = client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    body = {c["id"]: c for c in response.json()["candidates"]}
    enriched_ids = {c["id"] for c in candidates[:2]}
    pending_id = candidates[2]["id"]

    for candidate_id in enriched_ids:
        assert body[candidate_id]["duplicate_status"] in ("possible", "likely")
        assert body[candidate_id]["duplicate_group_id"] is not None
    assert body[pending_id]["duplicate_status"] == "not_checked"
    assert body[pending_id]["duplicate_group_id"] is None
    # The un-enriched candidate must never appear as anyone else's match.
    for candidate_id in enriched_ids:
        matched_ids = {m["matched_product_id"] for m in body[candidate_id]["duplicate_matches"]}
        assert pending_id not in matched_ids

    summary = response.json()["duplicate_summary"]
    assert summary["total_candidates"] == 3
    assert summary["eligible_candidates"] == 2
    assert summary["skipped_not_enriched"] == 1


def test_duplicate_summary_is_accurate_on_a_plain_job_read_too(
    client: TestClient, db_session: Session
):
    """duplicate_summary is computed fresh from current candidate state,
    not only returned right after detect-duplicates -- a later GET must
    reflect it just as accurately."""
    detections = [_packaged("Choco Bar", [0, 0, 100, 100]), _packaged("Choco Bar", [200, 200, 300, 300])]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    _enrich_all(
        client, processed["candidates"], [make_enrichment_response(brand="ChocoCo") for _ in processed["candidates"]]
    )
    client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    later_read = client.get(f"/api/digitizer/jobs/{job_id}").json()

    summary = later_read["duplicate_summary"]
    assert summary["total_candidates"] == 2
    assert summary["eligible_candidates"] == 2
    assert summary["skipped_not_enriched"] == 0
    assert summary["possible_count"] + summary["likely_count"] == 2


# --- Scope: within-job only ------------------------------------------------


def test_duplicate_detection_is_scoped_to_a_single_job(client: TestClient, db_session: Session):
    detections = [_packaged("Choco Bar", [0, 0, 100, 100])]
    job_a = _make_job(client, detections)
    _enrich_all(client, job_a["candidates"], [make_enrichment_response(brand="ChocoCo")])
    job_b = _make_job(client, detections)
    _enrich_all(client, job_b["candidates"], [make_enrichment_response(brand="ChocoCo")])

    response = client.post(f"/api/digitizer/jobs/{job_a['id']}/detect-duplicates")

    # job_a has only one candidate -- nothing in job_b, even though
    # identical, is ever compared against it.
    candidate = response.json()["candidates"][0]
    assert candidate["duplicate_status"] == "none"


# --- Safety: never deletes, always idempotent ------------------------------


def test_duplicate_detection_never_deletes_candidates(client: TestClient, db_session: Session):
    detections = [_packaged("Choco Bar", [0, 0, 100, 100]), _packaged("Choco Bar", [200, 200, 300, 300])]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    _enrich_all(
        client, processed["candidates"], [make_enrichment_response(brand="ChocoCo") for _ in processed["candidates"]]
    )

    before = db_session.query(DigitizedProduct).filter(DigitizedProduct.job_id == uuid.UUID(job_id)).count()
    client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")
    after = db_session.query(DigitizedProduct).filter(DigitizedProduct.job_id == uuid.UUID(job_id)).count()

    assert before == after == 2


def test_repeated_detection_is_idempotent_and_does_not_accumulate_rows(
    client: TestClient, db_session: Session
):
    detections = [_packaged("Choco Bar", [0, 0, 100, 100]), _packaged("Choco Bar", [200, 200, 300, 300])]
    processed = _make_job(client, detections)
    job_id = processed["id"]
    _enrich_all(
        client, processed["candidates"], [make_enrichment_response(brand="ChocoCo") for _ in processed["candidates"]]
    )

    client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")
    first_count = db_session.query(DigitizedProductDuplicateMatch).count()

    client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")
    second_count = db_session.query(DigitizedProductDuplicateMatch).count()
    third_response = client.post(f"/api/digitizer/jobs/{job_id}/detect-duplicates")

    assert first_count == second_count == 2
    for candidate in third_response.json()["candidates"]:
        assert candidate["duplicate_status"] in ("possible", "likely")


# --- Error handling ----------------------------------------------------------


def test_detect_duplicates_unknown_job_returns_404(client: TestClient):
    response = client.post(f"/api/digitizer/jobs/{uuid.uuid4()}/detect-duplicates")
    assert response.status_code == 404
