import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.digitized_product import DigitizedProduct
from app.models.digitized_product_duplicate_match import DigitizedProductDuplicateMatch
from app.models.enums import DuplicateResolution, ReviewStatus, SellingMode
from app.models.mixins import utcnow
from app.models.product import Product
from app.schemas.digitized_product import DigitizedProductReviewUpdate


class ReviewError(Exception):
    """A client-safe error raised by the Milestone 7 review workflow (not
    found, invalid state transition, failed approval validation) -- mirrors
    EnrichmentError/RefinementError in the other digitizer services."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _get_or_404(db: Session, product_id: uuid.UUID) -> DigitizedProduct:
    product = db.get(DigitizedProduct, product_id)
    if product is None:
        raise ReviewError("Digitized product not found.", status_code=404)
    return product


def _media_url(product: DigitizedProduct) -> str | None:
    """The best available catalog-ready image for this product, as the
    existing safe media-serving endpoint URL (see api.digitizer.get_job_media
    / services.storage.resolve_media_path). The refined image (Milestone 6)
    is preferred when present; the crop is used otherwise. A pragmatic
    bridge rather than copying files into a separate Product-owned media
    tree -- see README for why this is an intentional Milestone 7
    simplification."""
    if product.refined_image:
        return f"/api/digitizer/jobs/{product.job_id}/media/refined/{product.refined_image}"
    if product.crop_image:
        return f"/api/digitizer/jobs/{product.job_id}/media/products/{product.crop_image}"
    return None


def _source_media_url(product: DigitizedProduct) -> str | None:
    if not product.source_image:
        return None
    return f"/api/digitizer/jobs/{product.job_id}/media/source/{product.source_image}"


def validate_for_approval(product: DigitizedProduct) -> list[str]:
    """Every reason `product` is not currently eligible for approval, or an
    empty list if it is. Deliberately stricter than a plain draft save (see
    DigitizedProductReviewUpdate) but never requires barcode/brand/flavor,
    which are legitimately absent for plenty of real products."""
    reasons: list[str] = []

    if product.review_status == ReviewStatus.MERGED:
        reasons.append(
            "This product was merged into another product and can no longer be approved independently."
        )

    if not product.name_en:
        reasons.append("English name is required.")
    if not product.name_ar:
        reasons.append("Arabic name is required.")
    if not product.category_id:
        reasons.append("Category is required.")
    if product.selling_mode is None:
        reasons.append("Selling mode (weight or unit) is required.")
    if product.price is None or product.price <= 0:
        reasons.append("A valid, positive price is required.")
    if not product.crop_image and not product.refined_image:
        reasons.append("A product image (crop or refined) is required.")
    if product.selling_mode == SellingMode.WEIGHT and product.package_weight is not None:
        reasons.append(
            "Weight-mode products must not have a package weight -- price already represents the "
            "price per kilogram."
        )

    return reasons


def _upsert_catalog_product(db: Session, product: DigitizedProduct) -> Product:
    """Create or update the approved-catalog Product row backing `product`,
    keyed by `product.product_id` -- the traceable link that has existed on
    DigitizedProduct since Milestone 2, unused until now. Reusing it (rather
    than adding a second, competing link) is what makes repeated approval
    idempotent: a second `approve` call updates the same Product row instead
    of inserting a duplicate.
    """
    catalog: Product | None = None
    if product.product_id is not None:
        catalog = db.get(Product, product.product_id)

    if product.barcode:
        stmt = select(Product.id).where(Product.barcode == product.barcode)
        if catalog is not None:
            stmt = stmt.where(Product.id != catalog.id)
        clash = db.scalars(stmt).first()
        if clash is not None:
            raise ReviewError(
                f"Barcode '{product.barcode}' is already used by another catalog product.",
                status_code=409,
            )

    if catalog is None:
        # `product.id` is already a globally unique UUID -- deriving the
        # SKU from it guarantees uniqueness without a separate
        # generation/collision-retry scheme.
        catalog = Product(sku=f"DP-{product.id.hex}")

    catalog.name_en = product.name_en or ""
    catalog.name_ar = product.name_ar or ""
    catalog.description_en = product.description_en
    catalog.description_ar = product.description_ar
    catalog.category_id = product.category_id
    catalog.brand = product.brand
    # Product.weight/unit are the pre-existing (Milestone 2) plain fields --
    # not redesigned here. `unit` stores the selling_mode value as a string
    # since Product.unit was never an enum to begin with.
    catalog.weight = product.package_weight
    catalog.unit = product.selling_mode.value if product.selling_mode else None
    catalog.price = product.price
    catalog.discount_price = None
    catalog.stock_status = product.stock_status
    catalog.barcode = product.barcode
    catalog.image = _media_url(product)
    catalog.source_image = _source_media_url(product)
    catalog.ai_confidence = product.ai_confidence
    catalog.needs_review = False
    catalog.ai_raw_result = product.ai_raw_result

    db.add(catalog)
    db.flush()
    product.product_id = catalog.id
    return catalog


def _apply_approval(db: Session, product: DigitizedProduct) -> None:
    _upsert_catalog_product(db, product)
    now = utcnow()
    if product.reviewed_at is None:
        product.reviewed_at = now
    product.approved_at = now
    product.review_status = ReviewStatus.APPROVED
    db.add(product)
    db.commit()
    db.refresh(product)


def update_review_fields(
    db: Session, product_id: uuid.UUID, payload: DigitizedProductReviewUpdate
) -> DigitizedProduct:
    """Apply a human review edit. Always a human touch -- always stamps
    `reviewed_at`, which is what guards this product from a later
    re-enrichment call silently overwriting it (see
    digitizer_enrichment_service.enrich_digitized_product). `review_status`
    may only be set to DRAFT through this endpoint (a deliberate "save as
    incomplete"); approval/rejection/merge go through their own endpoints
    with their own rules. Omitting `review_status` entirely leaves it
    unchanged -- a plain field-edit save does not force any status
    transition.
    """
    product = _get_or_404(db, product_id)
    if product.review_status == ReviewStatus.MERGED:
        raise ReviewError(
            "This product was merged into another product and can no longer be edited independently.",
            status_code=409,
        )

    data = payload.model_dump(exclude_unset=True)
    set_draft = data.pop("review_status", None) is not None
    for field, value in data.items():
        setattr(product, field, value)
    if set_draft:
        product.review_status = ReviewStatus.DRAFT

    product.reviewed_at = utcnow()

    # An already-approved product has a live catalog listing -- a plain
    # field-edit save must keep that listing in sync rather than silently
    # drifting from what the reviewer just edited. Reuses the same
    # create-or-update mapping approval itself uses (see
    # _upsert_catalog_product) so this can never insert a second Product:
    # product.product_id already points at the existing row, and that
    # function updates it in place.
    if product.review_status == ReviewStatus.APPROVED:
        _upsert_catalog_product(db, product)

    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def approve_digitized_product(db: Session, product_id: uuid.UUID) -> DigitizedProduct:
    """Approve exactly one DigitizedProduct: validates it against the
    stricter approval rules, then creates or updates its linked catalog
    Product transactionally (see _upsert_catalog_product). Idempotent:
    calling this twice in a row updates the same Product row rather than
    creating a second one.
    """
    product = _get_or_404(db, product_id)
    reasons = validate_for_approval(product)
    if reasons:
        raise ReviewError(" ".join(reasons), status_code=422)

    _apply_approval(db, product)
    return product


def reject_digitized_product(
    db: Session, product_id: uuid.UUID, reason: str | None = None
) -> DigitizedProduct:
    """Reject one DigitizedProduct. Unlike approval, this never requires
    catalog completeness -- a product can be rejected for any reason, at
    any stage of completeness. `reason` is accepted for API completeness
    (e.g. a future audit trail, Milestone 11) but is not persisted to a
    dedicated column in this milestone -- see README for this documented
    simplification.
    """
    product = _get_or_404(db, product_id)
    if product.review_status == ReviewStatus.MERGED:
        raise ReviewError(
            "This product was merged into another product and can no longer be reviewed independently.",
            status_code=409,
        )

    if product.reviewed_at is None:
        product.reviewed_at = utcnow()
    product.review_status = ReviewStatus.REJECTED
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _match_rows_within(db: Session, product_ids: set[uuid.UUID]) -> list[DigitizedProductDuplicateMatch]:
    """Every pairwise match row (both directions) strictly BETWEEN members
    of `product_ids` -- i.e. exactly the relationships a resolution action
    over that set should touch. A relationship one of these products has
    with a product OUTSIDE the set is deliberately never returned here, so
    resolving A/B can never accidentally silence an A/C warning."""
    if not product_ids:
        return []
    stmt = select(DigitizedProductDuplicateMatch).where(
        DigitizedProductDuplicateMatch.product_id.in_(product_ids),
        DigitizedProductDuplicateMatch.matched_product_id.in_(product_ids),
    )
    return list(db.scalars(stmt).all())


def resolve_duplicate_keep_separate(
    db: Session, product_ids: list[uuid.UUID]
) -> list[DigitizedProduct]:
    """Mark the duplicate relationship(s) BETWEEN the listed products as
    human-resolved (KEPT_SEPARATE) -- never merges or deletes anything.

    Resolution is applied per pairwise `DigitizedProductDuplicateMatch` row
    (both directions), not as a single flag on each product -- a product
    can have one resolved and one still-unresolved duplicate relationship
    at the same time, which only a per-relationship record can represent
    correctly (see DigitizedProduct.has_unresolved_duplicates). Once every
    relationship a product has is resolved, it stops being presented as an
    unresolved duplicate by the review list's "Duplicates" filter; a
    relationship with a product NOT in `product_ids` is untouched and, if
    still unresolved, keeps that warning showing. Both products remain
    independently reviewable and approvable either way, and no historical
    duplicate-match evidence is ever removed by this call.
    """
    products = [_get_or_404(db, product_id) for product_id in product_ids]
    for product in products:
        if product.review_status == ReviewStatus.MERGED:
            raise ReviewError(
                "A product that was merged into another product cannot be marked keep-separate.",
                status_code=409,
            )

    matches = _match_rows_within(db, {p.id for p in products})
    if not matches:
        raise ReviewError(
            "No duplicate relationship exists between the selected products.", status_code=400
        )

    for match in matches:
        match.resolution = DuplicateResolution.KEPT_SEPARATE
        db.add(match)
    db.commit()
    for product in products:
        db.refresh(product)
    return products


def merge_duplicates(
    db: Session, canonical_id: uuid.UUID, merge_ids: list[uuid.UUID]
) -> tuple[DigitizedProduct, list[DigitizedProduct]]:
    """Merge one or more duplicate candidates into a single human-chosen
    canonical survivor. Never deletes the merged-away rows -- they are kept
    for traceability, flipped to review_status=MERGED (a terminal state) and
    linked back to the survivor via `merged_into_id`, which is exactly what
    stops them from later being approved independently (see
    validate_for_approval). The canonical record itself is not otherwise
    modified here; a reviewer edits it normally afterward through
    update_review_fields.
    """
    canonical = _get_or_404(db, canonical_id)
    if canonical.review_status == ReviewStatus.MERGED:
        raise ReviewError(
            "The chosen canonical product was itself merged into another product -- choose its "
            "survivor instead.",
            status_code=409,
        )
    if canonical_id in merge_ids:
        raise ReviewError("The canonical product cannot also be listed as a product to merge away.")

    candidates: list[DigitizedProduct] = []
    seen: set[uuid.UUID] = set()
    for merge_id in merge_ids:
        if merge_id in seen:
            continue
        seen.add(merge_id)
        candidate = _get_or_404(db, merge_id)
        if candidate.review_status == ReviewStatus.MERGED:
            raise ReviewError(
                "One of the selected products has already been merged into another product.",
                status_code=409,
            )
        if candidate.review_status == ReviewStatus.APPROVED:
            # Already has its own catalog Product row (see
            # _upsert_catalog_product) -- merging it away here would leave
            # that Product independently active alongside the canonical's,
            # exactly the "two independently-approved catalog products"
            # outcome this milestone must prevent. Refuse rather than
            # silently deactivating catalog state Milestone 7 has no
            # mandate to manage.
            raise ReviewError(
                "This product has already been approved into the catalog and cannot be merged away; "
                "resolve it manually first.",
                status_code=409,
            )
        candidates.append(candidate)

    if not candidates:
        raise ReviewError("No valid products to merge were provided.")

    for candidate in candidates:
        candidate.merged_into_id = canonical.id
        candidate.review_status = ReviewStatus.MERGED
        candidate.duplicate_resolution = DuplicateResolution.MERGED
        db.add(candidate)

    # Resolve the actual pairwise relationship(s) this merge settles --
    # canonical<->each merged candidate, and candidate<->candidate if more
    # than one was merged in the same call -- so has_unresolved_duplicates
    # correctly drops for the canonical once this was its only unresolved
    # relationship, WITHOUT touching any relationship either product has
    # with a third product outside this merge (see _match_rows_within).
    involved_ids = {canonical.id, *(candidate.id for candidate in candidates)}
    for match in _match_rows_within(db, involved_ids):
        match.resolution = DuplicateResolution.MERGED
        db.add(match)

    db.add(canonical)
    db.commit()
    db.refresh(canonical)
    for candidate in candidates:
        db.refresh(candidate)
    return canonical, candidates


def bulk_approve(
    db: Session, product_ids: list[uuid.UUID]
) -> tuple[list[DigitizedProduct], list[tuple[uuid.UUID, list[str]]]]:
    """Approve every listed product that individually passes
    `validate_for_approval`, plus one additional bulk-only safety check: a
    product that STILL has an unresolved duplicate relationship (see
    DigitizedProduct.has_unresolved_duplicates) is never silently
    bulk-approved (a reviewer approving that exact single item one at a
    time, having just looked at it, is a deliberate decision -- see
    api.review.approve_product -- but a batch action must not make that
    judgment call on the reviewer's behalf). A product whose only
    duplicate relationship was already merged or explicitly kept separate
    is NOT blocked -- only a genuinely still-unresolved relationship is.
    Never bulk-merges duplicates. A product that fails any check is left
    completely unchanged and reported in `failed` with its specific
    reasons; one product's failure never blocks or rolls back another's
    approval.
    """
    approved: list[DigitizedProduct] = []
    failed: list[tuple[uuid.UUID, list[str]]] = []

    for product_id in product_ids:
        product = db.get(DigitizedProduct, product_id)
        if product is None:
            failed.append((product_id, ["Digitized product not found."]))
            continue

        reasons = validate_for_approval(product)
        if product.has_unresolved_duplicates:
            reasons.append(
                "This product has an unresolved duplicate flag; resolve it (merge or keep separate) "
                "before bulk approval, or approve it individually."
            )

        if reasons:
            failed.append((product_id, reasons))
            continue

        _apply_approval(db, product)
        approved.append(product)

    return approved, failed
