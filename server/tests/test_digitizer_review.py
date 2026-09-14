"""Tests for Milestone 7 human review & approval.

Deliberately never touches the AI-dependent endpoints (enrich/refine/
process) -- every candidate here is created directly via the ORM, so this
whole suite makes zero AI calls and needs no OpenRouter dependency
override at all.
"""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.digitization_job import DigitizationJob
from app.models.digitized_product import DigitizedProduct
from app.models.digitized_product_duplicate_match import DigitizedProductDuplicateMatch
from app.models.enums import DuplicateResolution, DuplicateStatus, ReviewStatus, SellingMode, StockStatus
from app.models.product import Product


def make_job(db_session: Session, **overrides) -> DigitizationJob:
    job = DigitizationJob(**overrides)
    db_session.add(job)
    db_session.commit()
    return job


def make_category(db_session: Session, **overrides) -> Category:
    defaults = dict(name_en="Nuts", name_ar="مكسرات", slug=f"cat-{uuid.uuid4().hex[:8]}")
    defaults.update(overrides)
    category = Category(**defaults)
    db_session.add(category)
    db_session.commit()
    return category


def make_candidate(db_session: Session, job: DigitizationJob, category: Category | None = None, **overrides) -> DigitizedProduct:
    defaults = dict(
        job_id=job.id,
        name_en="Roasted Almonds",
        name_ar="لوز",
        crop_image=f"{uuid.uuid4().hex}.jpg",
        selling_mode=SellingMode.UNIT,
        price=Decimal("5.00"),
        category_id=category.id if category is not None else None,
    )
    defaults.update(overrides)
    candidate = DigitizedProduct(**defaults)
    db_session.add(candidate)
    db_session.commit()
    return candidate


def make_match(
    db_session: Session,
    a: DigitizedProduct,
    b: DigitizedProduct,
    *,
    score: Decimal = Decimal("0.75"),
    reasons: list[str] | None = None,
    status: DuplicateStatus = DuplicateStatus.POSSIBLE,
    resolution: DuplicateResolution = DuplicateResolution.UNRESOLVED,
) -> None:
    """Creates a real, bidirectional duplicate-match relationship between
    two candidates -- what app.services.duplicate_detection_service would
    actually produce -- rather than only setting the aggregate
    `duplicate_status` field on each product in isolation. This matters
    because Milestone 7's unresolved-duplicate logic is keyed off the
    pairwise DigitizedProductDuplicateMatch rows, not the per-product
    aggregate alone (see DigitizedProduct.has_unresolved_duplicates)."""
    reasons = reasons or ["name_similarity:0.90"]
    db_session.add(
        DigitizedProductDuplicateMatch(
            product_id=a.id, matched_product_id=b.id, score=score, reasons=list(reasons), resolution=resolution
        )
    )
    db_session.add(
        DigitizedProductDuplicateMatch(
            product_id=b.id, matched_product_id=a.id, score=score, reasons=list(reasons), resolution=resolution
        )
    )
    a.duplicate_status = status
    b.duplicate_status = status
    db_session.add_all([a, b])
    db_session.commit()


# --- Review status lifecycle -------------------------------------------


def test_new_candidate_defaults_to_pending_review(db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)

    assert candidate.review_status == ReviewStatus.PENDING_REVIEW
    assert candidate.reviewed_at is None
    assert candidate.approved_at is None


def test_review_update_can_save_as_draft_even_when_incomplete(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job, name_en=None, name_ar=None, category_id=None, price=None)

    response = client.patch(
        f"/api/digitizer/products/{candidate.id}/review",
        json={"name_en": "Partial Name", "review_status": "draft"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "draft"
    assert body["name_en"] == "Partial Name"
    assert body["reviewed_at"] is not None
    # Still missing name_ar/category/price -- draft must allow this.
    assert body["name_ar"] is None
    assert body["category_id"] is None
    assert body["price"] is None


def test_plain_review_edit_without_review_status_does_not_change_status(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)
    assert candidate.review_status == ReviewStatus.PENDING_REVIEW

    response = client.patch(
        f"/api/digitizer/products/{candidate.id}/review", json={"brand": "Acme"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "pending_review"
    assert body["brand"] == "Acme"
    assert body["reviewed_at"] is not None


def test_review_edit_stamps_reviewed_at_marking_human_authority(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)

    response = client.patch(
        f"/api/digitizer/products/{candidate.id}/review", json={"name_en": "Human Edited"}
    )

    assert response.status_code == 200
    assert response.json()["reviewed_at"] is not None


def test_review_edit_rejects_negative_price(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)

    response = client.patch(
        f"/api/digitizer/products/{candidate.id}/review", json={"price": "-1.00"}
    )

    assert response.status_code == 422


def test_review_edit_unknown_product_returns_404(client: TestClient, db_session: Session):
    response = client.patch(
        f"/api/digitizer/products/{uuid.uuid4()}/review", json={"brand": "X"}
    )
    assert response.status_code == 404


# --- Approval validation -------------------------------------------------


def test_approval_fails_with_clear_reasons_when_incomplete(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(
        db_session, job, name_en=None, name_ar=None, category_id=None, price=None, crop_image=None
    )

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "English name" in detail
    assert "Arabic name" in detail
    assert "Category" in detail
    assert "price" in detail
    assert "image" in detail


def test_approval_fails_specifically_when_category_is_missing(client: TestClient, db_session: Session):
    """Every OTHER required field is present -- isolates the category
    requirement specifically, so this fails for exactly one reason."""
    job = make_job(db_session)
    candidate = make_candidate(db_session, job, category_id=None)

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 422
    assert response.json()["detail"] == "Category is required."


def test_approval_succeeds_with_a_valid_category(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category)

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 200
    assert response.json()["category_id"] == str(category.id)


def test_approval_does_not_require_barcode_brand_or_flavor(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(
        db_session, job, category=category, barcode=None, brand=None, flavor_variant=None
    )

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 200


def test_approval_requires_positive_price(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category, price=Decimal("0.00"))

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 422
    assert "price" in response.json()["detail"]


def test_weight_mode_product_with_package_weight_fails_approval(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(
        db_session,
        job,
        category=category,
        selling_mode=SellingMode.WEIGHT,
        package_weight=Decimal("0.500"),
        price=Decimal("8.00"),
    )

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 422
    assert "package weight" in response.json()["detail"]


def test_weight_mode_product_without_package_weight_can_be_approved(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(
        db_session,
        job,
        category=category,
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        price=Decimal("8.00"),
    )

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 200


def test_unit_mode_product_with_package_weight_can_be_approved(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(
        db_session,
        job,
        category=category,
        selling_mode=SellingMode.UNIT,
        package_weight=Decimal("0.500"),
        price=Decimal("3.50"),
    )

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 200


# --- Successful approval / Product creation -------------------------------


def test_successful_approval_creates_linked_product(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category, price=Decimal("9.99"))

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "approved"
    assert body["approved_at"] is not None
    assert body["product_id"] is not None

    catalog = db_session.get(Product, uuid.UUID(body["product_id"]))
    assert catalog is not None
    assert catalog.name_en == candidate.name_en
    assert catalog.price == Decimal("9.99")
    assert catalog.needs_review is False


def test_approval_is_idempotent_no_duplicate_product_rows(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category, price=Decimal("4.25"))

    first = client.post(f"/api/digitizer/products/{candidate.id}/approve")
    second = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["product_id"] == second.json()["product_id"]

    count = db_session.query(Product).count()
    assert count == 1


def test_reapproval_after_edit_updates_the_same_product_row(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category, price=Decimal("4.25"))

    first = client.post(f"/api/digitizer/products/{candidate.id}/approve")
    assert first.status_code == 200
    product_id = first.json()["product_id"]

    client.patch(f"/api/digitizer/products/{candidate.id}/review", json={"price": "6.00"})
    second = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert second.status_code == 200
    assert second.json()["product_id"] == product_id
    catalog = db_session.get(Product, uuid.UUID(product_id))
    assert catalog.price == Decimal("6.00")
    assert db_session.query(Product).count() == 1


def test_editing_an_approved_product_and_saving_syncs_the_linked_product(client: TestClient, db_session: Session):
    """Save Changes (PATCH .../review) on an already-approved product --
    the frontend's replacement for the old separate "Update Listing"
    action -- must keep the linked catalog Product in sync by reusing the
    same create-or-update mapping approval itself uses, without requiring
    a separate re-approve call and without ever inserting a second Product."""
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category, price=Decimal("4.25"))

    approve_response = client.post(f"/api/digitizer/products/{candidate.id}/approve")
    assert approve_response.status_code == 200
    product_id = approve_response.json()["product_id"]

    save_response = client.patch(
        f"/api/digitizer/products/{candidate.id}/review", json={"price": "7.50", "brand": "Acme"}
    )

    assert save_response.status_code == 200
    body = save_response.json()
    assert body["review_status"] == "approved"
    assert body["product_id"] == product_id

    catalog = db_session.get(Product, uuid.UUID(product_id))
    assert catalog.price == Decimal("7.50")
    assert catalog.brand == "Acme"
    assert db_session.query(Product).count() == 1


def test_editing_a_not_yet_approved_product_does_not_create_a_product(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category, price=Decimal("4.25"))

    response = client.patch(f"/api/digitizer/products/{candidate.id}/review", json={"price": "7.50"})

    assert response.status_code == 200
    assert response.json()["product_id"] is None
    assert db_session.query(Product).count() == 0


def test_approval_with_barcode_clash_is_rejected(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    db_session.add(Product(sku="EXISTING-1", name_en="X", name_ar="x", price=Decimal("1"), barcode="1234567890"))
    db_session.commit()

    candidate = make_candidate(db_session, job, category=category, barcode="1234567890")

    response = client.post(f"/api/digitizer/products/{candidate.id}/approve")

    assert response.status_code == 409
    assert db_session.query(Product).count() == 1


def test_approve_unknown_product_returns_404(client: TestClient, db_session: Session):
    response = client.post(f"/api/digitizer/products/{uuid.uuid4()}/approve")
    assert response.status_code == 404


# --- Rejection -------------------------------------------------------------


def test_rejection_does_not_require_catalog_completeness(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(
        db_session, job, name_en=None, name_ar=None, category_id=None, price=None, crop_image=None
    )

    response = client.post(f"/api/digitizer/products/{candidate.id}/reject", json={"reason": "Not sellable"})

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "rejected"
    assert body["product_id"] is None


def test_rejection_creates_no_product(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    candidate = make_candidate(db_session, job, category=category)

    response = client.post(f"/api/digitizer/products/{candidate.id}/reject")

    assert response.status_code == 200
    assert db_session.query(Product).count() == 0


# --- Merged-away records cannot be independently approved -----------------


def test_merged_away_candidate_cannot_be_approved(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    canonical = make_candidate(db_session, job, category=category, name_en="Canonical")
    duplicate = make_candidate(db_session, job, category=category, name_en="Duplicate")

    merge_response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(canonical.id), "merge_ids": [str(duplicate.id)]},
    )
    assert merge_response.status_code == 200

    approve_response = client.post(f"/api/digitizer/products/{duplicate.id}/approve")

    assert approve_response.status_code == 422
    assert "merged" in approve_response.json()["detail"].lower()


def test_merged_away_candidate_cannot_be_edited(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    canonical = make_candidate(db_session, job, category=category)
    duplicate = make_candidate(db_session, job, category=category)

    client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(canonical.id), "merge_ids": [str(duplicate.id)]},
    )

    response = client.patch(
        f"/api/digitizer/products/{duplicate.id}/review", json={"brand": "New"}
    )
    assert response.status_code == 409


# --- Duplicate merge behavior -----------------------------------------------


def test_merge_marks_candidates_merged_and_preserves_canonical(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    canonical = make_candidate(db_session, job, category=category, name_en="Canonical")
    dup1 = make_candidate(db_session, job, category=category, name_en="Dup 1")
    dup2 = make_candidate(db_session, job, category=category, name_en="Dup 2")
    make_match(db_session, canonical, dup1)
    make_match(db_session, canonical, dup2)

    response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(canonical.id), "merge_ids": [str(dup1.id), str(dup2.id)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["canonical"]["id"] == str(canonical.id)
    assert body["canonical"]["review_status"] == "pending_review"  # untouched by the merge itself
    assert body["canonical"]["has_unresolved_duplicates"] is False
    merged_ids = {m["id"] for m in body["merged"]}
    assert merged_ids == {str(dup1.id), str(dup2.id)}
    for merged in body["merged"]:
        assert merged["review_status"] == "merged"
        assert merged["merged_into_id"] == str(canonical.id)
        assert merged["duplicate_resolution"] == "merged"

    # Neither merged-away record was deleted -- both remain in the DB with
    # their original content, for traceability.
    db_session.expire_all()
    still_there = db_session.get(DigitizedProduct, dup1.id)
    assert still_there is not None
    assert still_there.name_en == "Dup 1"


def test_merge_clears_the_canonical_duplicate_warning_caused_only_by_the_merged_relationship(
    client: TestClient, db_session: Session
):
    """Core scenario from the Milestone 7 duplicate-resolution audit: A/B
    unresolved -> merge B into A -> A must no longer show a duplicate
    warning once that was its only unresolved relationship."""
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    make_match(db_session, a, b)

    before = client.get("/api/digitizer/products").json()
    assert next(p for p in before if p["id"] == str(a.id))["has_unresolved_duplicates"] is True

    merge_response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )
    assert merge_response.status_code == 200
    assert merge_response.json()["canonical"]["has_unresolved_duplicates"] is False

    after = client.get("/api/digitizer/products").json()
    assert next(p for p in after if p["id"] == str(a.id))["has_unresolved_duplicates"] is False


def test_merge_does_not_silence_an_unrelated_still_unresolved_relationship(
    client: TestClient, db_session: Session
):
    """A/B resolved via merge, but A/C is still unresolved -> A must still
    show a duplicate warning because C still requires a decision. This is
    exactly the case the old product-level `duplicate_resolution` flag
    could not represent correctly."""
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    c = make_candidate(db_session, job, category=category, name_en="C")
    make_match(db_session, a, b)
    make_match(db_session, a, c)

    merge_response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )
    assert merge_response.status_code == 200
    assert merge_response.json()["canonical"]["has_unresolved_duplicates"] is True

    products = {p["id"]: p for p in client.get("/api/digitizer/products").json()}
    a_matches = {m["matched_product_id"]: m["resolution"] for m in products[str(a.id)]["duplicate_matches"]}
    assert a_matches[str(b.id)] == "merged"
    assert a_matches[str(c.id)] == "unresolved"


def test_canonical_can_be_approved_normally_after_merge_resolves_its_only_duplicate(
    client: TestClient, db_session: Session
):
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    make_match(db_session, a, b)

    merge_response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )
    assert merge_response.status_code == 200

    # Remains editable and can be saved as draft...
    draft_response = client.patch(
        f"/api/digitizer/products/{a.id}/review", json={"review_status": "draft"}
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["review_status"] == "draft"

    # ...and approved normally.
    approve_response = client.post(f"/api/digitizer/products/{a.id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["review_status"] == "approved"


def test_merge_preserves_the_underlying_match_evidence(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category)
    b = make_candidate(db_session, job, category=category)
    make_match(db_session, a, b, score=Decimal("0.95"), reasons=["barcode_match"])

    client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )

    rows = db_session.query(DigitizedProductDuplicateMatch).filter(
        DigitizedProductDuplicateMatch.product_id.in_([a.id, b.id])
    ).all()
    assert len(rows) == 2  # both directions still present, nothing deleted
    for row in rows:
        assert row.resolution == DuplicateResolution.MERGED
        assert row.score == Decimal("0.95")
        assert row.reasons == ["barcode_match"]


def test_merge_rejects_canonical_listed_as_its_own_merge_target(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)

    response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(candidate.id), "merge_ids": [str(candidate.id)]},
    )

    assert response.status_code == 400


def test_merge_refuses_to_merge_away_an_already_approved_candidate(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    canonical = make_candidate(db_session, job, category=category)
    already_approved = make_candidate(db_session, job, category=category)
    approve_resp = client.post(f"/api/digitizer/products/{already_approved.id}/approve")
    assert approve_resp.status_code == 200

    response = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(canonical.id), "merge_ids": [str(already_approved.id)]},
    )

    assert response.status_code == 409
    assert db_session.query(Product).count() == 1  # unchanged


# --- Keep separate -----------------------------------------------------------


def test_keep_separate_resolves_the_specific_relationship(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    p1 = make_candidate(db_session, job, category=category)
    p2 = make_candidate(db_session, job, category=category)
    make_match(db_session, p1, p2, score=Decimal("0.65"), reasons=["name_similarity:0.80"])

    response = client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(p1.id), str(p2.id)]},
    )

    assert response.status_code == 200
    body = response.json()
    for entry in body:
        # keep-separate is not a "reviewed" action on the product's own content
        assert entry["review_status"] == "pending_review"
        assert entry["has_unresolved_duplicates"] is False

    # duplicate_status (the AI's own historical evidence) is untouched --
    # only the human resolution changed.
    db_session.expire_all()
    assert db_session.get(DigitizedProduct, p1.id).duplicate_status == DuplicateStatus.POSSIBLE

    # The underlying match evidence is preserved, both directions, with its
    # original score/reasons -- only `resolution` changed.
    rows = db_session.query(DigitizedProductDuplicateMatch).filter(
        DigitizedProductDuplicateMatch.product_id.in_([p1.id, p2.id])
    ).all()
    assert len(rows) == 2
    for row in rows:
        assert row.resolution == DuplicateResolution.KEPT_SEPARATE
        assert row.score == Decimal("0.65")
        assert row.reasons == ["name_similarity:0.80"]


def test_keep_separate_does_not_affect_an_unrelated_unresolved_relationship(
    client: TestClient, db_session: Session
):
    """A/B resolved as keep-separate, but A/C is still unresolved -> A must
    still show a duplicate warning for C."""
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    c = make_candidate(db_session, job, category=category, name_en="C")
    make_match(db_session, a, b)
    make_match(db_session, a, c)

    response = client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(a.id), str(b.id)]},
    )

    assert response.status_code == 200
    entries = {p["id"]: p for p in response.json()}
    assert entries[str(a.id)]["has_unresolved_duplicates"] is True  # C still pending
    assert entries[str(b.id)]["has_unresolved_duplicates"] is False  # B's only relation is now resolved

    products = {p["id"]: p for p in client.get("/api/digitizer/products").json()}
    a_matches = {m["matched_product_id"]: m["resolution"] for m in products[str(a.id)]["duplicate_matches"]}
    assert a_matches[str(b.id)] == "kept_separate"
    assert a_matches[str(c.id)] == "unresolved"


def test_keep_separate_leaves_both_products_independently_approvable(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    p1 = make_candidate(db_session, job, category=category)
    p2 = make_candidate(db_session, job, category=category)
    make_match(db_session, p1, p2)

    client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(p1.id), str(p2.id)]},
    )

    r1 = client.post(f"/api/digitizer/products/{p1.id}/approve")
    r2 = client.post(f"/api/digitizer/products/{p2.id}/approve")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert db_session.query(Product).count() == 2


def test_keep_separate_unknown_product_returns_404(client: TestClient, db_session: Session):
    job = make_job(db_session)
    p1 = make_candidate(db_session, job)

    response = client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(p1.id), str(uuid.uuid4())]},
    )
    assert response.status_code == 404


def test_keep_separate_with_no_relationship_between_products_is_rejected(
    client: TestClient, db_session: Session
):
    job = make_job(db_session)
    p1 = make_candidate(db_session, job)
    p2 = make_candidate(db_session, job)  # never matched with p1

    response = client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(p1.id), str(p2.id)]},
    )

    assert response.status_code == 400


# --- Bulk approval -----------------------------------------------------------


def test_bulk_approve_only_approves_products_that_individually_pass(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    good = make_candidate(db_session, job, category=category, name_en="Good")
    bad = make_candidate(db_session, job, category=category, name_en=None)

    response = client.post(
        "/api/digitizer/products/bulk-approve",
        json={"product_ids": [str(good.id), str(bad.id)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["approved"]) == 1
    assert body["approved"][0]["id"] == str(good.id)
    assert len(body["failed"]) == 1
    assert body["failed"][0]["product_id"] == str(bad.id)
    assert any("English name" in reason for reason in body["failed"][0]["reasons"])

    db_session.expire_all()
    untouched = db_session.get(DigitizedProduct, bad.id)
    assert untouched.review_status == ReviewStatus.PENDING_REVIEW  # left unchanged


def test_bulk_approve_does_not_bypass_validation(client: TestClient, db_session: Session):
    job = make_job(db_session)
    incomplete = make_candidate(db_session, job, name_en=None, category_id=None, price=None)

    response = client.post(
        "/api/digitizer/products/bulk-approve", json={"product_ids": [str(incomplete.id)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved"] == []
    assert len(body["failed"]) == 1
    assert db_session.query(Product).count() == 0


def test_bulk_approve_refuses_unresolved_likely_duplicate(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    flagged = make_candidate(db_session, job, category=category)
    other = make_candidate(db_session, job, category=category)
    make_match(db_session, flagged, other, status=DuplicateStatus.LIKELY)

    response = client.post(
        "/api/digitizer/products/bulk-approve", json={"product_ids": [str(flagged.id)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved"] == []
    assert len(body["failed"]) == 1
    assert any("duplicate" in reason.lower() for reason in body["failed"][0]["reasons"])
    assert db_session.query(Product).count() == 0


def test_single_approve_allows_a_deliberately_reviewed_likely_duplicate(client: TestClient, db_session: Session):
    """Unlike bulk-approve, a single explicit approve is a deliberate,
    already-inspected decision -- it is not blocked by an unresolved
    duplicate flag."""
    job = make_job(db_session)
    category = make_category(db_session)
    flagged = make_candidate(db_session, job, category=category)
    other = make_candidate(db_session, job, category=category)
    make_match(db_session, flagged, other, status=DuplicateStatus.LIKELY)

    response = client.post(f"/api/digitizer/products/{flagged.id}/approve")

    assert response.status_code == 200


def test_bulk_approve_with_kept_separate_duplicate_succeeds(client: TestClient, db_session: Session):
    """A resolved (kept-separate) duplicate relationship must NOT block
    bulk approval -- only a genuinely unresolved one should."""
    job = make_job(db_session)
    category = make_category(db_session)
    resolved = make_candidate(db_session, job, category=category)
    other = make_candidate(db_session, job, category=category)
    make_match(db_session, resolved, other, status=DuplicateStatus.LIKELY)
    keep_separate_resp = client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(resolved.id), str(other.id)]},
    )
    assert keep_separate_resp.status_code == 200

    response = client.post(
        "/api/digitizer/products/bulk-approve", json={"product_ids": [str(resolved.id)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["approved"]) == 1
    assert body["failed"] == []


def test_bulk_approve_does_not_block_a_canonical_merely_for_a_historically_merged_duplicate(
    client: TestClient, db_session: Session
):
    """A canonical product that had a duplicate which was already merged
    away must NOT be blocked from bulk approval -- that relationship is
    resolved, not outstanding."""
    job = make_job(db_session)
    category = make_category(db_session)
    canonical = make_candidate(db_session, job, category=category)
    duplicate = make_candidate(db_session, job, category=category)
    make_match(db_session, canonical, duplicate, status=DuplicateStatus.LIKELY)
    merge_resp = client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(canonical.id), "merge_ids": [str(duplicate.id)]},
    )
    assert merge_resp.status_code == 200

    response = client.post(
        "/api/digitizer/products/bulk-approve", json={"product_ids": [str(canonical.id)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["approved"]) == 1
    assert body["failed"] == []


def test_bulk_approve_never_approves_a_merged_away_record(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    canonical = make_candidate(db_session, job, category=category)
    duplicate = make_candidate(db_session, job, category=category)
    make_match(db_session, canonical, duplicate)
    client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(canonical.id), "merge_ids": [str(duplicate.id)]},
    )

    response = client.post(
        "/api/digitizer/products/bulk-approve", json={"product_ids": [str(duplicate.id)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved"] == []
    assert len(body["failed"]) == 1
    assert any("merged" in reason.lower() for reason in body["failed"][0]["reasons"])


def test_bulk_approve_partial_failure_does_not_roll_back_successes(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    ok1 = make_candidate(db_session, job, category=category, name_en="OK 1")
    ok2 = make_candidate(db_session, job, category=category, name_en="OK 2")
    bad = make_candidate(db_session, job, category=category, price=None)

    response = client.post(
        "/api/digitizer/products/bulk-approve",
        json={"product_ids": [str(ok1.id), str(bad.id), str(ok2.id)]},
    )

    body = response.json()
    approved_ids = {p["id"] for p in body["approved"]}
    assert approved_ids == {str(ok1.id), str(ok2.id)}
    assert db_session.query(Product).count() == 2


def test_bulk_approve_unknown_product_reported_as_failed(client: TestClient, db_session: Session):
    missing_id = uuid.uuid4()
    response = client.post(
        "/api/digitizer/products/bulk-approve", json={"product_ids": [str(missing_id)]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["approved"] == []
    assert body["failed"][0]["product_id"] == str(missing_id)


# --- Re-enrichment guard: human edits are authoritative ---------------------


def test_reviewed_product_cannot_be_re_enriched(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)
    client.patch(f"/api/digitizer/products/{candidate.id}/review", json={"brand": "Human Brand"})

    response = client.post(f"/api/digitizer/products/{candidate.id}/enrich")

    assert response.status_code == 409


# --- Category picker ---------------------------------------------------------


def test_list_categories_for_review_picker(client: TestClient, db_session: Session):
    make_category(db_session, name_en="Nuts", slug="nuts-cat")
    make_category(db_session, name_en="Coffee", slug="coffee-cat")

    response = client.get("/api/digitizer/categories")

    assert response.status_code == 200
    names = {c["name_en"] for c in response.json()}
    assert names == {"Nuts", "Coffee"}


# --- Cross-job listing -------------------------------------------------------


def test_list_all_products_returns_candidates_across_jobs(client: TestClient, db_session: Session):
    job1 = make_job(db_session)
    job2 = make_job(db_session)
    make_candidate(db_session, job1)
    make_candidate(db_session, job2)

    response = client.get("/api/digitizer/products")

    assert response.status_code == 200
    assert len(response.json()) == 2


# --- Unresolved-duplicate source of truth (Milestone 7 audit) ---------------
#
# `has_unresolved_duplicates` (computed from DigitizedProductDuplicateMatch.
# resolution, never from the historical existence of a match or the
# product-level duplicate_resolution field) is meant to be the ONE place
# this is decided -- the review list, badges, filters, and bulk-approve
# gating all read it rather than recomputing their own version.


def test_a_b_unresolved_produces_a_duplicate_warning_for_both(client: TestClient, db_session: Session):
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    make_match(db_session, a, b)

    products = {p["id"]: p for p in client.get("/api/digitizer/products").json()}

    assert products[str(a.id)]["has_unresolved_duplicates"] is True
    assert products[str(b.id)]["has_unresolved_duplicates"] is True
    assert products[str(a.id)]["duplicate_matches"][0]["resolution"] == "unresolved"


def test_a_product_with_no_matches_has_no_unresolved_duplicates(client: TestClient, db_session: Session):
    job = make_job(db_session)
    candidate = make_candidate(db_session, job)

    products = {p["id"]: p for p in client.get("/api/digitizer/products").json()}

    assert products[str(candidate.id)]["has_unresolved_duplicates"] is False
    assert products[str(candidate.id)]["duplicate_matches"] == []


def test_merged_away_product_is_never_shown_as_an_unresolved_duplicate_even_with_an_unrelated_match(
    client: TestClient, db_session: Session
):
    """B is merged into A, but B separately also matched D (never resolved
    from B's side). B is locked/terminal -- it must never be presented as
    something still requiring duplicate-resolution action, even though its
    raw `has_unresolved_duplicates` bit could technically still be true."""
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    d = make_candidate(db_session, job, category=category, name_en="D")
    make_match(db_session, a, b)
    make_match(db_session, b, d)

    client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )

    products = {p["id"]: p for p in client.get("/api/digitizer/products").json()}
    merged_b = products[str(b.id)]
    assert merged_b["review_status"] == "merged"
    # The UI's "needs a duplicate decision" surface must gate on
    # review_status != MERGED as well as has_unresolved_duplicates -- a
    # merged-away record is never actionable regardless of this bit.
    assert merged_b["has_unresolved_duplicates"] is True  # B/D was never resolved from B's side
    # but it is unreachable for independent action either way:
    assert merged_b["merged_into_id"] == str(a.id)


# --- Historical evidence survives resolution ---------------------------------


def test_historical_duplicate_evidence_remains_after_both_merge_and_keep_separate(
    client: TestClient, db_session: Session
):
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category)
    b = make_candidate(db_session, job, category=category)
    c = make_candidate(db_session, job, category=category)
    make_match(db_session, a, b, score=Decimal("0.70"), reasons=["brand_match"])
    make_match(db_session, a, c, score=Decimal("0.65"), reasons=["name_similarity:0.80"])

    client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )
    client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(a.id), str(c.id)]},
    )

    all_rows = db_session.query(DigitizedProductDuplicateMatch).filter(
        DigitizedProductDuplicateMatch.product_id.in_([a.id, b.id, c.id])
    ).all()
    # a<->b (2 rows) + a<->c (2 rows) -- none deleted by either resolution.
    assert len(all_rows) == 4
    by_pair = {(row.product_id, row.matched_product_id): row for row in all_rows}
    assert by_pair[(a.id, b.id)].resolution == DuplicateResolution.MERGED
    assert by_pair[(b.id, a.id)].resolution == DuplicateResolution.MERGED
    assert by_pair[(a.id, c.id)].resolution == DuplicateResolution.KEPT_SEPARATE
    assert by_pair[(c.id, a.id)].resolution == DuplicateResolution.KEPT_SEPARATE
    assert by_pair[(a.id, b.id)].score == Decimal("0.70")
    assert by_pair[(a.id, c.id)].reasons == ["name_similarity:0.80"]


# --- Duplicates filter (actionable-unresolved-only) --------------------------
#
# The frontend "Duplicates" tab and this backend's has_unresolved_duplicates
# are meant to agree exactly -- these tests exercise the same scenarios the
# frontend filter relies on, through the API response it actually reads.


def test_duplicates_filter_scenario_resolved_products_return_to_normal_state(
    client: TestClient, db_session: Session
):
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category)
    b = make_candidate(db_session, job, category=category)
    make_match(db_session, a, b)

    client.post(
        "/api/digitizer/products/duplicates/keep-separate",
        json={"product_ids": [str(a.id), str(b.id)]},
    )

    products = client.get("/api/digitizer/products").json()
    actionable = [p for p in products if p["review_status"] != "merged" and p["has_unresolved_duplicates"]]
    assert actionable == []


def test_duplicates_filter_scenario_only_the_still_unresolved_product_is_actionable(
    client: TestClient, db_session: Session
):
    job = make_job(db_session)
    category = make_category(db_session)
    a = make_candidate(db_session, job, category=category, name_en="A")
    b = make_candidate(db_session, job, category=category, name_en="B")
    c = make_candidate(db_session, job, category=category, name_en="C")
    make_match(db_session, a, b)
    make_match(db_session, a, c)

    client.post(
        "/api/digitizer/products/duplicates/merge",
        json={"canonical_id": str(a.id), "merge_ids": [str(b.id)]},
    )

    products = client.get("/api/digitizer/products").json()
    actionable_ids = {
        p["id"] for p in products if p["review_status"] != "merged" and p["has_unresolved_duplicates"]
    }
    # A still needs action (C is unresolved); B is merged-away (excluded);
    # C itself still needs action too.
    assert actionable_ids == {str(a.id), str(c.id)}
