import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.digitizer import get_ai_enricher
from app.main import app
from app.models.category import Category
from app.services.ai.enrichment_service import _EnrichmentResponse
from app.services.ai.errors import AIServiceUnavailableError
from tests.test_digitizer_processing import make_detected_product, make_image_bytes, upload_job, use_fake_analyzer


class FakeEnricher:
    """A scripted enrichment client: pops one entry per `enrich_product`
    call, in call order. An entry that is an Exception instance is raised
    instead of returned, mirroring FakeAnalyzer in
    test_digitizer_processing.py."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def enrich_product(
        self, image_bytes, mime_type, name_en, name_ar, category_suggestion, category_names, presentation=None
    ):
        self.calls.append(
            dict(
                image_bytes=image_bytes,
                mime_type=mime_type,
                name_en=name_en,
                name_ar=name_ar,
                category_suggestion=category_suggestion,
                category_names=list(category_names),
                presentation=presentation,
            )
        )
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def use_fake_enricher(script: list) -> FakeEnricher:
    fake = FakeEnricher(script)
    app.dependency_overrides[get_ai_enricher] = lambda: fake
    return fake


_NO_REVIEW = {"needs_review": False, "reason": None}
_ALL_FIELDS_CLEAN = {
    "brand": _NO_REVIEW,
    "flavor_variant": _NO_REVIEW,
    "selling_mode": _NO_REVIEW,
    "package_weight": _NO_REVIEW,
    "barcode": _NO_REVIEW,
    "description_en": _NO_REVIEW,
    "description_ar": _NO_REVIEW,
    "category": _NO_REVIEW,
}


def make_enrichment_response(**overrides) -> _EnrichmentResponse:
    defaults = dict(
        brand="Wehbi Roastery",
        flavor_variant="Salted",
        selling_mode="unit",
        package_weight="0.500",
        barcode=None,
        description_en="Premium roasted almonds, lightly salted.",
        description_ar="لوز محمص فاخر، مملح قليلاً.",
        category="Nuts",
        field_review=dict(_ALL_FIELDS_CLEAN),
    )
    defaults.update(overrides)
    return _EnrichmentResponse(**defaults)


def create_processed_product(client: TestClient, **detected_overrides) -> dict:
    """Uploads a job, processes it with a single detected product (via M4's
    fake analyzer), and returns the resulting candidate dict -- enrichment
    always operates on a product that already went through detection."""
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(**detected_overrides)]])
    processed = client.post(f"/api/digitizer/jobs/{job['id']}/process").json()
    return processed["candidates"][0]


def add_category(db_session: Session, name_en: str, name_ar: str = "فئة") -> Category:
    category = Category(name_en=name_en, name_ar=name_ar, slug=name_en.lower().replace(" ", "-"))
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


# --- Successful single-item enrichment ---------------------------------


def test_enrich_populates_all_fields_and_resolves_category(client: TestClient, db_session: Session):
    category = add_category(db_session, "Nuts")
    candidate = create_processed_product(client, presentation="packaged")
    use_fake_enricher([make_enrichment_response(category="Nuts")])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert response.status_code == 200
    body = response.json()
    assert body["brand"] == "Wehbi Roastery"
    assert body["flavor_variant"] == "Salted"
    assert body["selling_mode"] == "unit"
    assert float(body["package_weight"]) == 0.5
    assert body["description_en"] == "Premium roasted almonds, lightly salted."
    assert body["description_ar"] == "لوز محمص فاخر، مملح قليلاً."
    assert body["category_id"] == str(category.id)
    assert body["enrichment_status"] == "enriched"
    assert body["field_review"]["brand"]["needs_review"] is False


def test_enrich_bulk_item_leaves_brand_barcode_and_package_weight_null_without_review(
    client: TestClient, db_session: Session
):
    candidate = create_processed_product(client, presentation="bulk_tray", identification_basis="visual")
    use_fake_enricher(
        [
            make_enrichment_response(
                brand=None,
                flavor_variant=None,
                selling_mode="weight",
                package_weight=None,
                barcode=None,
                category=None,
                field_review={**_ALL_FIELDS_CLEAN},
            )
        ]
    )

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["brand"] is None
    assert body["barcode"] is None
    assert body["package_weight"] is None
    assert body["selling_mode"] == "weight"
    assert body["field_review"]["brand"]["needs_review"] is False
    assert body["field_review"]["barcode"]["needs_review"] is False
    assert body["field_review"]["package_weight"]["needs_review"] is False
    assert body["field_review"]["flavor_variant"]["needs_review"] is False


def test_packaged_item_keeps_package_weight_with_unit_selling_mode(client: TestClient, db_session: Session):
    """A packaged 500g bag is still sold PER UNIT -- package_weight and
    selling_mode="unit" must coexist without being treated as a conflict."""
    candidate = create_processed_product(client, presentation="packaged")
    use_fake_enricher([make_enrichment_response(selling_mode="unit", package_weight="0.500")])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["selling_mode"] == "unit"
    assert float(body["package_weight"]) == 0.5
    assert body["field_review"]["selling_mode"]["needs_review"] is False


def test_bottle_resolves_to_unit_selling_mode_without_package_weight(client: TestClient, db_session: Session):
    candidate = create_processed_product(client, presentation="bottle")
    use_fake_enricher(
        [make_enrichment_response(selling_mode="unit", package_weight=None, flavor_variant="Original")]
    )

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["selling_mode"] == "unit"
    assert body["package_weight"] is None
    assert body["field_review"]["selling_mode"]["needs_review"] is False


def test_loose_coffee_resolves_to_weight_selling_mode(client: TestClient, db_session: Session):
    candidate = create_processed_product(client, presentation="bulk_loose", name_en="Coffee")
    use_fake_enricher(
        [
            make_enrichment_response(
                brand=None,
                flavor_variant=None,
                selling_mode="weight",
                package_weight=None,
                description_en="Loose roasted coffee beans sold by weight.",
                description_ar="حبوب قهوة محمصة تباع بالوزن.",
            )
        ]
    )

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["selling_mode"] == "weight"
    assert body["package_weight"] is None
    assert body["field_review"]["selling_mode"]["needs_review"] is False


def test_uncertain_flavor_variant_can_be_flagged_for_review(client: TestClient, db_session: Session):
    candidate = create_processed_product(client, presentation="packaged")
    use_fake_enricher(
        [
            make_enrichment_response(
                flavor_variant="Possibly Hazelnut",
                field_review={
                    **_ALL_FIELDS_CLEAN,
                    "flavor_variant": {"needs_review": True, "reason": "Label partially obscured."},
                },
            )
        ]
    )

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["flavor_variant"] == "Possibly Hazelnut"
    assert body["field_review"]["flavor_variant"]["needs_review"] is True


def test_flavor_variant_null_when_not_identifiable(client: TestClient, db_session: Session):
    candidate = create_processed_product(client, presentation="bulk_tray")
    use_fake_enricher([make_enrichment_response(flavor_variant=None, selling_mode="weight", package_weight=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert response.json()["flavor_variant"] is None


# --- presentation vs. selling_mode conflict -----------------------------


def test_selling_mode_conflicting_with_bulk_presentation_is_flagged_for_review(
    client: TestClient, db_session: Session
):
    """presentation=bulk_tray strongly implies selling_mode=weight; an AI
    answer of "unit" must be flagged, never silently trusted."""
    candidate = create_processed_product(client, presentation="bulk_tray")
    use_fake_enricher([make_enrichment_response(selling_mode="unit", package_weight=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["selling_mode"] == "unit"
    assert body["field_review"]["selling_mode"]["needs_review"] is True
    assert "bulk_tray" in body["field_review"]["selling_mode"]["reason"]


def test_selling_mode_conflicting_with_packaged_presentation_is_flagged_for_review(
    client: TestClient, db_session: Session
):
    candidate = create_processed_product(client, presentation="packaged")
    use_fake_enricher([make_enrichment_response(selling_mode="weight", package_weight=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["selling_mode"] == "weight"
    assert body["field_review"]["selling_mode"]["needs_review"] is True


def test_selling_mode_matching_presentation_is_not_flagged(client: TestClient, db_session: Session):
    candidate = create_processed_product(client, presentation="bulk_tray")
    use_fake_enricher([make_enrichment_response(selling_mode="weight", package_weight=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["field_review"]["selling_mode"]["needs_review"] is False


def test_other_presentation_has_no_selling_mode_expectation(client: TestClient, db_session: Session):
    """presentation="other" carries no reliable implication -- whatever the
    AI reports for selling_mode should not be force-flagged just because
    presentation didn't clearly indicate one mode or the other."""
    candidate = create_processed_product(client, presentation="other")
    use_fake_enricher([make_enrichment_response(selling_mode="unit", package_weight=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["field_review"]["selling_mode"]["needs_review"] is False


def test_presentation_is_passed_to_the_enricher(client: TestClient, db_session: Session):
    candidate = create_processed_product(client, presentation="bulk_tray")
    fake = use_fake_enricher([make_enrichment_response(selling_mode="weight", package_weight=None)])

    client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert fake.calls[0]["presentation"] == "bulk_tray"


# --- Category handling (preserved from before the audit) ---------------


def test_category_stays_null_and_suggestion_preserved_when_ai_finds_no_fit(
    client: TestClient, db_session: Session
):
    add_category(db_session, "Dried Fruit")  # exists, but genuinely doesn't fit
    candidate = create_processed_product(client)  # category_suggestion == "Nuts" from M4
    assert candidate["category_suggestion"] == "Nuts"
    use_fake_enricher([make_enrichment_response(category=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["category_id"] is None
    assert body["category_suggestion"] == "Nuts"


def test_category_returned_outside_given_options_is_flagged_for_review(
    client: TestClient, db_session: Session
):
    add_category(db_session, "Nuts")
    candidate = create_processed_product(client)
    use_fake_enricher([make_enrichment_response(category="Some Made Up Category")])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    body = response.json()
    assert body["category_id"] is None
    assert body["category_suggestion"] == "Some Made Up Category"
    assert body["field_review"]["category"]["needs_review"] is True


def test_category_match_is_case_insensitive(client: TestClient, db_session: Session):
    category = add_category(db_session, "Nuts")
    candidate = create_processed_product(client)
    use_fake_enricher([make_enrichment_response(category="nuts")])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert response.json()["category_id"] == str(category.id)


def test_no_categories_in_catalog_still_succeeds_with_null_category(
    client: TestClient, db_session: Session
):
    candidate = create_processed_product(client)
    use_fake_enricher([make_enrichment_response(category=None)])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert response.status_code == 200
    assert response.json()["category_id"] is None


def test_enricher_receives_the_products_context(client: TestClient, db_session: Session):
    add_category(db_session, "Nuts")
    add_category(db_session, "Coffee")
    candidate = create_processed_product(client, name_en="Almonds", name_ar="لوز")
    fake = use_fake_enricher([make_enrichment_response()])

    client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert fake.calls[0]["name_en"] == "Almonds"
    assert fake.calls[0]["name_ar"] == "لوز"
    assert fake.calls[0]["category_suggestion"] == "Nuts"
    assert set(fake.calls[0]["category_names"]) == {"Nuts", "Coffee"}


# --- Price safety ---------------------------------------------------------


def test_enrichment_response_never_contains_a_price(client: TestClient, db_session: Session):
    """`price` exists on the response (Milestone 7) but AI enrichment must
    never populate it -- only a human review edit/approval does."""
    candidate = create_processed_product(client)
    use_fake_enricher([make_enrichment_response()])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert response.json()["price"] is None


# --- Single-item retry, independent of job/other products --------------


def test_enrich_can_be_retried_on_the_same_product(client: TestClient, db_session: Session):
    candidate = create_processed_product(client)
    use_fake_enricher([AIServiceUnavailableError("OpenRouter was unavailable.")])

    first = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")
    assert first.status_code == 502

    use_fake_enricher([make_enrichment_response(brand="Second Try Brand")])
    second = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert second.status_code == 200
    assert second.json()["brand"] == "Second Try Brand"


def test_explicit_re_enrich_works_even_after_successful_enrichment(client: TestClient, db_session: Session):
    """The single-item endpoint is an explicit user action and must always
    be retriable, regardless of enrichment_status -- unlike the job-level
    endpoint, it never skips an already-enriched product."""
    candidate = create_processed_product(client)
    use_fake_enricher([make_enrichment_response(brand="First Brand")])
    first = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")
    assert first.json()["enrichment_status"] == "enriched"

    use_fake_enricher([make_enrichment_response(brand="Re-enriched Brand")])
    second = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert second.status_code == 200
    assert second.json()["brand"] == "Re-enriched Brand"


def test_enriching_one_product_does_not_touch_a_sibling_product(
    client: TestClient, db_session: Session
):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer(
        [[make_detected_product(name_en="Almonds"), make_detected_product(name_en="Coffee", bbox=[500, 500, 900, 900])]]
    )
    processed = client.post(f"/api/digitizer/jobs/{job['id']}/process").json()
    almonds, coffee = processed["candidates"]

    use_fake_enricher([make_enrichment_response(brand="Almond Brand")])
    client.post(f"/api/digitizer/products/{almonds['id']}/enrich")

    unchanged = client.get(f"/api/digitizer/jobs/{job['id']}").json()
    coffee_after = next(c for c in unchanged["candidates"] if c["id"] == coffee["id"])
    assert coffee_after["brand"] is None
    assert coffee_after["field_review"] is None
    assert coffee_after["enrichment_status"] == "pending"


# --- Error handling ------------------------------------------------------


def test_enrich_unknown_product_returns_404(client: TestClient):
    use_fake_enricher([make_enrichment_response()])
    response = client.post(f"/api/digitizer/products/{uuid.uuid4()}/enrich")

    assert response.status_code == 404


def test_enrich_ai_service_not_configured_returns_503(client: TestClient):
    from app.core.config import Settings, get_settings

    candidate = create_processed_product(client)
    app.dependency_overrides[get_settings] = lambda: Settings(openrouter_api_key=None)
    try:
        response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 503


def test_enrich_ai_failure_surfaces_as_502_without_mutating_the_product(
    client: TestClient, db_session: Session
):
    candidate = create_processed_product(client)
    use_fake_enricher([AIServiceUnavailableError("OpenRouter was unavailable.")])

    response = client.post(f"/api/digitizer/products/{candidate['id']}/enrich")

    assert response.status_code == 502
    unchanged = client.get(f"/api/digitizer/jobs/{candidate['job_id']}").json()
    assert unchanged["candidates"][0]["brand"] is None
    assert unchanged["candidates"][0]["enrichment_status"] == "pending"


# --- Job-level convenience endpoint -------------------------------------


def test_enrich_job_loops_over_every_draft_product(client: TestClient, db_session: Session):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer(
        [[make_detected_product(name_en="Almonds"), make_detected_product(name_en="Coffee", bbox=[500, 500, 900, 900])]]
    )
    client.post(f"/api/digitizer/jobs/{job['id']}/process")
    use_fake_enricher(
        [
            make_enrichment_response(brand="Almond Brand"),
            make_enrichment_response(brand="Coffee Brand"),
        ]
    )

    response = client.post(f"/api/digitizer/jobs/{job['id']}/enrich")

    assert response.status_code == 200
    brands = sorted(c["brand"] for c in response.json()["candidates"])
    assert brands == ["Almond Brand", "Coffee Brand"]


def test_enrich_job_continues_past_one_products_failure(client: TestClient, db_session: Session):
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer(
        [[make_detected_product(name_en="Almonds"), make_detected_product(name_en="Coffee", bbox=[500, 500, 900, 900])]]
    )
    client.post(f"/api/digitizer/jobs/{job['id']}/process")
    use_fake_enricher(
        [
            AIServiceUnavailableError("OpenRouter was unavailable."),
            make_enrichment_response(brand="Coffee Brand"),
        ]
    )

    response = client.post(f"/api/digitizer/jobs/{job['id']}/enrich")

    assert response.status_code == 200
    brands = sorted(c["brand"] for c in response.json()["candidates"] if c["brand"])
    assert brands == ["Coffee Brand"]


def test_enrich_job_unknown_job_returns_404(client: TestClient):
    use_fake_enricher([])
    response = client.post(f"/api/digitizer/jobs/{uuid.uuid4()}/enrich")

    assert response.status_code == 404


# --- Job-level re-enrichment cost leak fix -------------------------------


def test_calling_job_enrichment_twice_does_not_re_enrich_already_enriched_products(
    client: TestClient, db_session: Session
):
    """The core cost-control fix: a product that already has
    enrichment_status="enriched" must be SKIPPED (no AI call) on a second
    call to the job-level endpoint, even though review_status is still
    DRAFT (human review is a separate, untouched concern)."""
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(name_en="Almonds")]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    fake_first = use_fake_enricher([make_enrichment_response(brand="Almond Brand")])
    first = client.post(f"/api/digitizer/jobs/{job['id']}/enrich")
    assert first.json()["candidates"][0]["enrichment_status"] == "enriched"
    assert len(fake_first.calls) == 1

    fake_second = use_fake_enricher([])  # any pop() here means an unwanted extra AI call
    second = client.post(f"/api/digitizer/jobs/{job['id']}/enrich")

    assert second.status_code == 200
    assert len(fake_second.calls) == 0
    assert second.json()["candidates"][0]["brand"] == "Almond Brand"  # unchanged, untouched


def test_job_enrichment_still_enriches_a_product_added_after_the_first_pass(
    client: TestClient, db_session: Session
):
    """A DRAFT product that has never been enriched (enrichment_status
    still "pending") must still be picked up, even if a sibling in the
    same job was already enriched."""
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer(
        [[make_detected_product(name_en="Almonds"), make_detected_product(name_en="Coffee", bbox=[500, 500, 900, 900])]]
    )
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    use_fake_enricher([make_enrichment_response(brand="Almond Brand")])
    processed = client.get(f"/api/digitizer/jobs/{job['id']}").json()
    almonds = next(c for c in processed["candidates"] if c["name_en"] == "Almonds")
    client.post(f"/api/digitizer/products/{almonds['id']}/enrich")

    fake = use_fake_enricher([make_enrichment_response(brand="Coffee Brand")])
    response = client.post(f"/api/digitizer/jobs/{job['id']}/enrich")

    assert len(fake.calls) == 1  # only the still-pending "Coffee" product
    brands = sorted(c["brand"] for c in response.json()["candidates"])
    assert brands == ["Almond Brand", "Coffee Brand"]


def test_job_enrichment_retries_a_product_whose_earlier_enrichment_attempt_failed(
    client: TestClient, db_session: Session
):
    """A failed enrichment attempt leaves enrichment_status="pending" (it
    is only ever set to "enriched" on success) -- a later job-level call
    must still pick that product back up, not skip it as if it succeeded."""
    job = upload_job(client, make_image_bytes())
    use_fake_analyzer([[make_detected_product(name_en="Almonds")]])
    client.post(f"/api/digitizer/jobs/{job['id']}/process")

    use_fake_enricher([AIServiceUnavailableError("OpenRouter was unavailable.")])
    client.post(f"/api/digitizer/jobs/{job['id']}/enrich")
    after_failure = client.get(f"/api/digitizer/jobs/{job['id']}").json()
    assert after_failure["candidates"][0]["enrichment_status"] == "pending"

    fake_retry = use_fake_enricher([make_enrichment_response(brand="Almond Brand")])
    response = client.post(f"/api/digitizer/jobs/{job['id']}/enrich")

    assert len(fake_retry.calls) == 1
    assert response.json()["candidates"][0]["brand"] == "Almond Brand"
