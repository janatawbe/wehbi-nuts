import re
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.digitized_product import DigitizedProduct
from app.models.digitized_product_duplicate_match import DigitizedProductDuplicateMatch
from app.models.enums import DuplicateStatus, EnrichmentStatus, SellingMode
from app.services.storage import get_job_products_dir

# Milestone 6's duplicate detection: deterministic and layered, scoped to
# candidates WITHIN ONE JOB (catalog-wide matching is deferred to
# Milestone 7 -- see README). Never uses an AI/OpenRouter call and never
# merges or deletes a DigitizedProduct; it only writes duplicate_status,
# duplicate_group_id, and pairwise evidence rows for a human to review
# later.
#
# ELIGIBILITY: only candidates with enrichment_status == ENRICHED are ever
# compared. A candidate that hasn't been enriched yet has no selling_mode
# (M4 never sets it) and therefore cannot be confidently compared to
# anything -- it is left at duplicate_status=NOT_CHECKED (never silently
# downgraded to NONE, which would misleadingly look identical to "this WAS
# compared and has no duplicate"). See summarize_duplicate_detection,
# which reports exactly how many candidates were skipped this way.
#
# Three layers, in order of trust, applied only to eligible pairs:
#   1. Hard compatibility filters (selling_mode, package_weight,
#      flavor_variant, barcode) -- a pair failing any of these is never
#      even scored, regardless of how similar anything else looks. A
#      field that is unknown on either side is INCONCLUSIVE, never a
#      conflict -- null is "no evidence", not "different".
#   2. An exact non-null barcode match -- the strongest possible evidence;
#      short-circuits straight to a maximal, "likely" score.
#   3. Otherwise, a score NORMALIZED over only the metadata fields that
#      are actually APPLICABLE (known on both sides) for this specific
#      pair, so a field that is legitimately null on both sides (no
#      brand, no flavor, no package weight -- all common, honest outcomes
#      of Milestone 5's "never invent" rules) does not permanently cap the
#      achievable score. A capped perceptual-image-hash contribution is
#      then added on top, as supporting evidence only -- it can nudge an
#      already-evidenced pair but can never, by itself, be the only
#      evidence for a match.

# Perceptual-hash similarity is capped well below _POSSIBLE_THRESHOLD so
# image similarity alone can NEVER be sufficient on its own to flag a
# duplicate -- it can only support an already-plausible metadata match. It
# is deliberately NOT part of the applicable-weight normalization below:
# a pair with zero applicable metadata evidence is never scored at all,
# regardless of how similar the crops look (see _score_pair).
_IMAGE_HASH_MAX_CONTRIBUTION = 0.20

_LIKELY_THRESHOLD = Decimal("0.90")
_POSSIBLE_THRESHOLD = Decimal("0.60")

_BRAND_WEIGHT = 0.25
_NAME_WEIGHT = 0.25
_CATEGORY_WEIGHT = 0.10
_FLAVOR_WEIGHT = 0.10
_PACKAGE_WEIGHT_WEIGHT = 0.10
# Sum of the weights above -- the metadata ceiling when EVERY field is
# applicable and matches. A pair where only some fields are applicable
# (e.g. brand/flavor/package_weight all null on both sides) is scored
# against the sum of just its own applicable fields instead (see
# _score_pair), not against this full total -- that's the fix for null
# fields otherwise making the "possible" threshold mathematically
# unreachable.
_METADATA_MAX_SCORE = _BRAND_WEIGHT + _NAME_WEIGHT + _CATEGORY_WEIGHT + _FLAVOR_WEIGHT + _PACKAGE_WEIGHT_WEIGHT

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: str | None) -> str | None:
    """Case/whitespace/punctuation-insensitive normalization shared by
    every text field compared below. Returns None for empty/whitespace-only
    input, so "unknown" and "" are never treated as a matchable value."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", value).strip().lower()
    # Punctuation is replaced with a SPACE, not deleted -- "Syrup/Molasses"
    # must normalize to two tokens ("syrup", "molasses"), not one merged
    # "syrupmolasses" that can never match "molasses" from a differently
    # (or un-)punctuated name. Same reasoning for hyphens, commas, etc.
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def _token_similarity(a: str | None, b: str | None) -> float:
    """Jaccard similarity over whitespace-split tokens -- deliberately a
    simple set-overlap measure, not a fuzzy/ML text-similarity model."""
    if a is None or b is None:
        return 0.0
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


def _known_text_conflict(a: str | None, b: str | None) -> bool:
    """True only when BOTH sides are known (normalized non-null) AND
    different. Missing data on either side is inconclusive, never a
    conflict -- null means "no evidence", not "different"."""
    norm_a, norm_b = _normalize_text(a), _normalize_text(b)
    return norm_a is not None and norm_b is not None and norm_a != norm_b


def _passes_hard_filters(a: DigitizedProduct, b: DigitizedProduct) -> bool:
    """Non-negotiable compatibility gates. A pair failing any of these is
    never scored or matched, no matter how similar anything else is.
    Every check here only fires on a KNOWN conflict -- missing data never
    disqualifies a pair on its own."""
    if a.selling_mode is None or b.selling_mode is None:
        # Both candidates must already be enriched for a pair to even
        # reach this function (see detect_duplicates_for_job's eligibility
        # filter) -- this remains as defense in depth.
        return False
    if a.selling_mode != b.selling_mode:
        return False
    if (
        a.selling_mode == SellingMode.UNIT
        and a.package_weight is not None
        and b.package_weight is not None
        and a.package_weight != b.package_weight
    ):
        return False
    if _known_text_conflict(a.flavor_variant, b.flavor_variant):
        return False
    if _known_text_conflict(a.barcode, b.barcode):
        return False
    return True


def _category_evaluation(a: DigitizedProduct, b: DigitizedProduct) -> tuple[bool, bool]:
    """Returns (applicable, matched). Prefers the resolved Category FK
    (unambiguous) when both sides have one; falls back to normalized raw
    AI text only when at least one side has no resolved category yet.
    Not applicable at all when neither side has any comparable category
    information."""
    if a.category_id is not None and b.category_id is not None:
        return True, a.category_id == b.category_id
    norm_a, norm_b = _normalize_text(a.category_suggestion), _normalize_text(b.category_suggestion)
    if norm_a is not None and norm_b is not None:
        return True, norm_a == norm_b
    return False, False


@dataclass(frozen=True)
class _MatchResult:
    score: Decimal
    reasons: list[str]


def _score_pair(
    a: DigitizedProduct, b: DigitizedProduct, image_similarity: float | None
) -> _MatchResult | None:
    """Returns None if the pair fails a hard filter, has no applicable
    metadata evidence at all, or scores below any reporting threshold;
    otherwise the evidence-backed score/reasons.

    The metadata score is normalized over only the fields APPLICABLE to
    this pair (known on both sides) -- a field that is legitimately null
    on both sides contributes to neither the numerator nor the
    denominator, so it never drags an otherwise-strong match down. This
    is what makes "same product, no visible brand/flavor/weight on either
    crop" reach a fair score instead of being capped below the "possible"
    threshold by fields that were never going to have evidence either way.
    """
    if not _passes_hard_filters(a, b):
        return None

    norm_barcode_a, norm_barcode_b = _normalize_text(a.barcode), _normalize_text(b.barcode)
    if norm_barcode_a is not None and norm_barcode_a == norm_barcode_b:
        # The strongest possible signal -- short-circuits straight to a
        # maximal score once the pair has already passed the hard filters
        # above (selling_mode/package_weight/flavor compatibility).
        return _MatchResult(score=Decimal("1.00"), reasons=["barcode_match"])

    reasons: list[str] = []
    applicable_weight = 0.0
    earned_weight = 0.0

    norm_brand_a, norm_brand_b = _normalize_text(a.brand), _normalize_text(b.brand)
    if norm_brand_a is not None and norm_brand_b is not None:
        applicable_weight += _BRAND_WEIGHT
        if norm_brand_a == norm_brand_b:
            earned_weight += _BRAND_WEIGHT
            reasons.append("brand_match")

    norm_name_en_a, norm_name_en_b = _normalize_text(a.name_en), _normalize_text(b.name_en)
    norm_name_ar_a, norm_name_ar_b = _normalize_text(a.name_ar), _normalize_text(b.name_ar)
    name_applicable = (norm_name_en_a is not None and norm_name_en_b is not None) or (
        norm_name_ar_a is not None and norm_name_ar_b is not None
    )
    if name_applicable:
        name_similarity = max(
            _token_similarity(norm_name_en_a, norm_name_en_b),
            _token_similarity(norm_name_ar_a, norm_name_ar_b),
        )
        applicable_weight += _NAME_WEIGHT
        if name_similarity > 0:
            earned_weight += name_similarity * _NAME_WEIGHT
            reasons.append(f"name_similarity:{name_similarity:.2f}")

    category_applicable, category_matched = _category_evaluation(a, b)
    if category_applicable:
        applicable_weight += _CATEGORY_WEIGHT
        if category_matched:
            earned_weight += _CATEGORY_WEIGHT
            reasons.append("category_match")

    norm_flavor_a, norm_flavor_b = _normalize_text(a.flavor_variant), _normalize_text(b.flavor_variant)
    if norm_flavor_a is not None and norm_flavor_b is not None:
        applicable_weight += _FLAVOR_WEIGHT
        if norm_flavor_a == norm_flavor_b:
            earned_weight += _FLAVOR_WEIGHT
            reasons.append("flavor_match")

    if a.selling_mode == SellingMode.UNIT and a.package_weight is not None and b.package_weight is not None:
        applicable_weight += _PACKAGE_WEIGHT_WEIGHT
        if a.package_weight == b.package_weight:
            earned_weight += _PACKAGE_WEIGHT_WEIGHT
            reasons.append("package_weight_match")

    if applicable_weight <= 0:
        # No comparable metadata evidence exists for this pair at all.
        # Image similarity is SUPPORTING evidence only (see module
        # docstring) and must never be sufficient by itself -- without at
        # least one applicable metadata field, there is nothing for it to
        # support, so this pair is never scored/matched regardless of how
        # similar the crops look.
        return None

    score = (earned_weight / applicable_weight) * _METADATA_MAX_SCORE

    if image_similarity is not None and image_similarity > 0:
        contribution = min(image_similarity, 1.0) * _IMAGE_HASH_MAX_CONTRIBUTION
        if contribution > 0.01:
            score += contribution
            reasons.append(f"image_phash_similarity:{image_similarity:.2f}")

    if score <= 0:
        return None

    return _MatchResult(score=Decimal(str(round(min(score, 1.0), 2))), reasons=reasons)


def _phash_similarity(path_a: Path, path_b: Path) -> float | None:
    """Perceptual-hash similarity in [0, 1] between two images on disk, or
    None if either can't be read/hashed -- treated the same as "no image
    evidence available" by the caller, never as a reason to fail the whole
    comparison."""
    try:
        import imagehash

        with Image.open(path_a) as img_a, Image.open(path_b) as img_b:
            hash_a = imagehash.phash(img_a)
            hash_b = imagehash.phash(img_b)
    except Exception:
        return None

    total_bits = len(hash_a.hash) ** 2
    if total_bits == 0:
        return None
    distance = hash_a - hash_b
    return max(0.0, 1.0 - (distance / total_bits))


class _UnionFind:
    """Minimal disjoint-set over UUIDs, used only to group candidates that
    are transitively linked by qualifying pairwise matches (e.g. 5
    identical packages -> 10 pairs -> 1 group)."""

    def __init__(self, ids: list[uuid.UUID]) -> None:
        self._parent: dict[uuid.UUID, uuid.UUID] = {item: item for item in ids}

    def find(self, item: uuid.UUID) -> uuid.UUID:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, a: uuid.UUID, b: uuid.UUID) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_a] = root_b


def _is_eligible(candidate: DigitizedProduct) -> bool:
    """A candidate can only be meaningfully compared once Milestone 5
    enrichment has actually run -- M4 never sets `selling_mode`, and
    without it _passes_hard_filters can never pass (see its own
    docstring). Using `enrichment_status` directly (rather than just
    checking `selling_mode is not None`) keeps this eligibility check
    readable and gives one authoritative definition of "ready to
    compare" that summarize_duplicate_detection reuses for reporting."""
    return candidate.enrichment_status == EnrichmentStatus.ENRICHED


def detect_duplicates_for_job(
    db: Session, upload_root: Path, job_id: uuid.UUID
) -> list[DigitizedProduct]:
    """Recompute duplicate flags for every DigitizedProduct in one job,
    from scratch, WITHIN this job only (see module docstring). Idempotent:
    always clears this job's prior pairwise rows and duplicate_status/
    duplicate_group_id before recomputing, so repeated calls never
    accumulate rows or leave stale results from a since-changed pair.
    Never deletes a DigitizedProduct row, only ever its own duplicate_*
    bookkeeping and pairwise-match rows.

    Only candidates with `enrichment_status == ENRICHED` are compared
    (see _is_eligible) -- NOT enriched yet is never silently treated the
    same as "compared and found no duplicate": an ineligible candidate is
    left at `duplicate_status = NOT_CHECKED` rather than being downgraded
    to `NONE`, so the two states stay distinguishable to the frontend and
    to summarize_duplicate_detection. This function never triggers
    enrichment itself and never spends any AI call -- the caller decides
    when (and whether) to enrich first.
    """
    stmt = (
        select(DigitizedProduct)
        .where(DigitizedProduct.job_id == job_id)
        .order_by(DigitizedProduct.created_at.asc())
    )
    candidates = list(db.scalars(stmt).all())
    candidate_ids = [candidate.id for candidate in candidates]

    if candidate_ids:
        db.query(DigitizedProductDuplicateMatch).filter(
            DigitizedProductDuplicateMatch.product_id.in_(candidate_ids)
        ).delete(synchronize_session=False)

    for candidate in candidates:
        candidate.duplicate_status = DuplicateStatus.NOT_CHECKED
        candidate.duplicate_group_id = None

    eligible = [candidate for candidate in candidates if _is_eligible(candidate)]
    eligible_ids = [candidate.id for candidate in eligible]

    products_dir = get_job_products_dir(upload_root, job_id)
    by_id = {candidate.id: candidate for candidate in candidates}
    union_find = _UnionFind(eligible_ids)

    pairwise: list[tuple[uuid.UUID, uuid.UUID, _MatchResult]] = []
    for i, a in enumerate(eligible):
        for b in eligible[i + 1 :]:
            image_similarity = None
            if a.crop_image and b.crop_image:
                image_similarity = _phash_similarity(
                    products_dir / a.crop_image, products_dir / b.crop_image
                )
            result = _score_pair(a, b, image_similarity)
            if result is None or result.score < _POSSIBLE_THRESHOLD:
                continue
            pairwise.append((a.id, b.id, result))
            union_find.union(a.id, b.id)

    for a_id, b_id, result in pairwise:
        db.add(
            DigitizedProductDuplicateMatch(
                product_id=a_id, matched_product_id=b_id, score=result.score, reasons=list(result.reasons)
            )
        )
        db.add(
            DigitizedProductDuplicateMatch(
                product_id=b_id, matched_product_id=a_id, score=result.score, reasons=list(result.reasons)
            )
        )

        status = DuplicateStatus.LIKELY if result.score >= _LIKELY_THRESHOLD else DuplicateStatus.POSSIBLE
        for product_id in (a_id, b_id):
            product = by_id[product_id]
            # A product with several qualifying matches keeps its
            # STRONGEST status (likely beats possible); every individual
            # match is still recorded in the pairwise table regardless.
            if product.duplicate_status != DuplicateStatus.LIKELY and (
                status == DuplicateStatus.LIKELY or product.duplicate_status == DuplicateStatus.NOT_CHECKED
            ):
                product.duplicate_status = status

    matched_ids = {product_id for a_id, b_id, _ in pairwise for product_id in (a_id, b_id)}
    group_id_by_root: dict[uuid.UUID, uuid.UUID] = {}
    for product_id in matched_ids:
        root = union_find.find(product_id)
        group_id = group_id_by_root.setdefault(root, uuid.uuid4())
        by_id[product_id].duplicate_group_id = group_id

    for candidate in eligible:
        # Only ELIGIBLE candidates are ever downgraded from NOT_CHECKED to
        # NONE -- an ineligible (not-yet-enriched) candidate keeps
        # NOT_CHECKED from the reset above, since it was never actually
        # compared to anything.
        if candidate.id not in matched_ids:
            candidate.duplicate_status = DuplicateStatus.NONE
            candidate.duplicate_group_id = None

    for candidate in candidates:
        db.add(candidate)

    db.commit()
    for candidate in candidates:
        db.refresh(candidate)
    return candidates


@dataclass(frozen=True)
class DuplicateDetectionSummary:
    """Explainable summary of a job's current duplicate-detection state --
    computed fresh from whatever `duplicate_status`/`enrichment_status`
    the candidates already carry, so it stays accurate whether it's read
    right after a `detect-duplicates` call or on any later job GET. Lets
    the frontend clearly tell the user how many candidates still need
    enrichment before they can be compared, rather than an unqualified
    "no duplicates found"."""

    total_candidates: int
    eligible_candidates: int
    skipped_not_enriched: int
    likely_count: int
    possible_count: int
    none_count: int


def summarize_duplicate_detection(candidates: list[DigitizedProduct]) -> DuplicateDetectionSummary:
    total = len(candidates)
    eligible = sum(1 for c in candidates if _is_eligible(c))
    return DuplicateDetectionSummary(
        total_candidates=total,
        eligible_candidates=eligible,
        skipped_not_enriched=total - eligible,
        likely_count=sum(1 for c in candidates if c.duplicate_status == DuplicateStatus.LIKELY),
        possible_count=sum(1 for c in candidates if c.duplicate_status == DuplicateStatus.POSSIBLE),
        none_count=sum(1 for c in candidates if c.duplicate_status == DuplicateStatus.NONE),
    )
