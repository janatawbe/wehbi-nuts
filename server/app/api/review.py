import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.category import Category
from app.models.digitized_product import DigitizedProduct
from app.schemas.category import CategoryRead
from app.schemas.digitized_product import (
    BulkApproveFailure,
    BulkApproveRequest,
    BulkApproveResponse,
    DigitizedProductApproveRequest,
    DigitizedProductRead,
    DigitizedProductRejectRequest,
    DigitizedProductReviewUpdate,
    DuplicateKeepSeparateRequest,
    DuplicateMergeRequest,
    DuplicateMergeResponse,
)
from app.services.digitizer_review_service import (
    ReviewError,
    approve_digitized_product,
    bulk_approve,
    merge_duplicates,
    reject_digitized_product,
    resolve_duplicate_keep_separate,
    update_review_fields,
)

router = APIRouter()


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryRead]:
    """Read-only category listing for the review edit form's category
    picker (a human-editable field, per Milestone 7). No create/update/
    delete here -- category management itself is out of this milestone's
    scope.
    """
    stmt = select(Category).order_by(Category.name_en.asc())
    return list(db.scalars(stmt).all())


@router.get("/products", response_model=list[DigitizedProductRead])
def list_all_products(db: Session = Depends(get_db)) -> list[DigitizedProductRead]:
    """Cross-job listing for the Milestone 7 review admin UI. Bounded
    (limit 200) with client-side tab filtering (All/Needs Review/Draft/
    Approved/Rejected/Duplicates) -- a deliberately simple approach at this
    milestone's scale rather than a server-side filter query API; see
    README for this documented limitation.
    """
    stmt = select(DigitizedProduct).order_by(DigitizedProduct.created_at.desc()).limit(200)
    return list(db.scalars(stmt).all())


@router.patch("/products/{product_id}/review", response_model=DigitizedProductRead)
def update_product_review(
    product_id: uuid.UUID,
    payload: DigitizedProductReviewUpdate,
    db: Session = Depends(get_db),
) -> DigitizedProductRead:
    try:
        product = update_review_fields(db, product_id, payload)
    except ReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DigitizedProductRead.model_validate(product)


@router.post("/products/{product_id}/approve", response_model=DigitizedProductRead)
def approve_product(
    product_id: uuid.UUID,
    _payload: DigitizedProductApproveRequest | None = None,
    db: Session = Depends(get_db),
) -> DigitizedProductRead:
    try:
        product = approve_digitized_product(db, product_id)
    except ReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DigitizedProductRead.model_validate(product)


@router.post("/products/{product_id}/reject", response_model=DigitizedProductRead)
def reject_product(
    product_id: uuid.UUID,
    payload: DigitizedProductRejectRequest | None = None,
    db: Session = Depends(get_db),
) -> DigitizedProductRead:
    reason = payload.reason if payload is not None else None
    try:
        product = reject_digitized_product(db, product_id, reason)
    except ReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DigitizedProductRead.model_validate(product)


@router.post("/products/duplicates/keep-separate", response_model=list[DigitizedProductRead])
def keep_separate(
    payload: DuplicateKeepSeparateRequest,
    db: Session = Depends(get_db),
) -> list[DigitizedProductRead]:
    try:
        products = resolve_duplicate_keep_separate(db, payload.product_ids)
    except ReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return [DigitizedProductRead.model_validate(product) for product in products]


@router.post("/products/duplicates/merge", response_model=DuplicateMergeResponse)
def merge_products(
    payload: DuplicateMergeRequest,
    db: Session = Depends(get_db),
) -> DuplicateMergeResponse:
    try:
        canonical, merged = merge_duplicates(db, payload.canonical_id, payload.merge_ids)
    except ReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DuplicateMergeResponse(
        canonical=DigitizedProductRead.model_validate(canonical),
        merged=[DigitizedProductRead.model_validate(product) for product in merged],
    )


@router.post("/products/bulk-approve", response_model=BulkApproveResponse)
def bulk_approve_products(
    payload: BulkApproveRequest,
    db: Session = Depends(get_db),
) -> BulkApproveResponse:
    approved, failed = bulk_approve(db, payload.product_ids)
    return BulkApproveResponse(
        approved=[DigitizedProductRead.model_validate(product) for product in approved],
        failed=[
            BulkApproveFailure(product_id=product_id, reasons=reasons)
            for product_id, reasons in failed
        ],
    )
