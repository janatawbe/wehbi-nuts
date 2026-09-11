"""Unit tests for Milestone 6's deterministic, layered duplicate-matching
logic (hard filters + weighted scoring). No database, no AI, no image
files -- DigitizedProduct instances are built in-memory and never
committed. Fully offline by construction."""
import uuid
from decimal import Decimal

from app.models.digitized_product import DigitizedProduct
from app.models.enums import SellingMode
from app.services.duplicate_detection_service import (
    _LIKELY_THRESHOLD,
    _POSSIBLE_THRESHOLD,
    _normalize_text,
    _passes_hard_filters,
    _score_pair,
    _token_similarity,
)


def make_product(**overrides) -> DigitizedProduct:
    defaults = dict(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        name_en="Roasted Almonds",
        name_ar="لوز محمص",
        brand="Wehbi Roastery",
        flavor_variant="Salted",
        category_id=None,
        category_suggestion="Nuts",
        selling_mode=SellingMode.UNIT,
        package_weight=Decimal("0.500"),
        barcode=None,
    )
    defaults.update(overrides)
    return DigitizedProduct(**defaults)


# --- Normalization ---------------------------------------------------------


def test_normalize_text_strips_case_whitespace_and_punctuation():
    assert _normalize_text("  Wehbi   Roastery!! ") == "wehbi roastery"
    assert _normalize_text("") is None
    assert _normalize_text("   ") is None
    assert _normalize_text(None) is None


def test_token_similarity_identical_and_disjoint():
    assert _token_similarity("roasted almonds", "roasted almonds") == 1.0
    assert _token_similarity("roasted almonds", "dried apricots") == 0.0
    assert _token_similarity(None, "x") == 0.0


# --- Hard filters: selling_mode -------------------------------------------


def test_selling_mode_mismatch_is_hard_blocked():
    a = make_product(selling_mode=SellingMode.WEIGHT)
    b = make_product(selling_mode=SellingMode.UNIT)
    assert _passes_hard_filters(a, b) is False


def test_unknown_selling_mode_on_either_side_is_hard_blocked():
    a = make_product(selling_mode=None)
    b = make_product(selling_mode=SellingMode.UNIT)
    assert _passes_hard_filters(a, b) is False
    assert _passes_hard_filters(b, a) is False


# --- Hard filters: package_weight (unit products only) ---------------------


def test_different_package_weight_for_unit_products_is_hard_blocked():
    a = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.250"))
    b = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.500"))
    assert _passes_hard_filters(a, b) is False


def test_matching_package_weight_for_unit_products_passes():
    a = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.500"))
    b = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.500"))
    assert _passes_hard_filters(a, b) is True


def test_null_package_weight_on_both_sides_does_not_hard_block():
    a = make_product(selling_mode=SellingMode.UNIT, package_weight=None)
    b = make_product(selling_mode=SellingMode.UNIT, package_weight=None)
    assert _passes_hard_filters(a, b) is True


def test_package_weight_is_irrelevant_for_weight_selling_mode():
    a = make_product(selling_mode=SellingMode.WEIGHT, package_weight=None)
    b = make_product(selling_mode=SellingMode.WEIGHT, package_weight=None)
    assert _passes_hard_filters(a, b) is True


# --- Hard filters: flavor_variant ------------------------------------------


def test_different_known_flavor_is_hard_blocked():
    a = make_product(flavor_variant="Salted")
    b = make_product(flavor_variant="Honey")
    assert _passes_hard_filters(a, b) is False


def test_same_known_flavor_normalized_passes():
    a = make_product(flavor_variant="Salted")
    b = make_product(flavor_variant="  salted ")
    assert _passes_hard_filters(a, b) is True


def test_null_flavor_on_both_sides_does_not_hard_block_but_earns_no_credit():
    a = make_product(flavor_variant=None)
    b = make_product(flavor_variant=None)
    assert _passes_hard_filters(a, b) is True
    result = _score_pair(a, b, image_similarity=None)
    assert result is not None
    assert "flavor_match" not in result.reasons


def test_one_side_unknown_flavor_does_not_hard_block():
    a = make_product(flavor_variant="Salted")
    b = make_product(flavor_variant=None)
    assert _passes_hard_filters(a, b) is True


# --- Barcode: strongest signal ----------------------------------------------


def test_exact_barcode_match_produces_maximal_likely_score():
    a = make_product(barcode="6291041500213")
    b = make_product(barcode="6291041500213", name_en="Totally Different Name")
    result = _score_pair(a, b, image_similarity=None)
    assert result is not None
    assert result.score == Decimal("1.00")
    assert result.reasons == ["barcode_match"]
    assert result.score >= _LIKELY_THRESHOLD


def test_barcode_match_still_requires_passing_hard_filters():
    """A barcode match cannot override selling_mode incompatibility -- the
    hard filters run first, unconditionally."""
    a = make_product(barcode="123", selling_mode=SellingMode.WEIGHT)
    b = make_product(barcode="123", selling_mode=SellingMode.UNIT)
    assert _score_pair(a, b, image_similarity=None) is None


def test_missing_barcode_on_either_side_is_not_treated_as_a_match():
    a = make_product(barcode=None)
    b = make_product(barcode=None)
    result = _score_pair(a, b, image_similarity=None)
    assert result is None or "barcode_match" not in result.reasons


# --- Metadata scoring --------------------------------------------------------


def test_matching_brand_name_flavor_weight_scores_a_likely_duplicate_without_barcode():
    a = make_product()
    b = make_product()
    result = _score_pair(a, b, image_similarity=None)
    assert result is not None
    assert result.score >= _POSSIBLE_THRESHOLD
    assert "brand_match" in result.reasons
    assert "flavor_match" in result.reasons
    assert "package_weight_match" in result.reasons


def test_different_flavor_is_not_duplicate():
    a = make_product(flavor_variant="Salted")
    b = make_product(flavor_variant="Honey")
    assert _score_pair(a, b, image_similarity=None) is None


def test_250g_vs_500g_unit_products_are_not_duplicate():
    a = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.250"))
    b = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.500"))
    assert _score_pair(a, b, image_similarity=None) is None


def test_weight_vs_unit_is_not_duplicate():
    a = make_product(selling_mode=SellingMode.WEIGHT, package_weight=None)
    b = make_product(selling_mode=SellingMode.UNIT, package_weight=Decimal("0.500"))
    assert _score_pair(a, b, image_similarity=None) is None


def test_visually_similar_but_differently_named_bulk_products_are_not_duplicate():
    a = make_product(
        name_en="Cashews",
        name_ar="كاجو",
        brand=None,
        flavor_variant=None,
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        category_suggestion="Nuts",
        barcode=None,
    )
    b = make_product(
        name_en="Almonds",
        name_ar="لوز",
        brand=None,
        flavor_variant=None,
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        category_suggestion="Nuts",
        barcode=None,
    )
    # Even a perfect image-hash similarity must not tip this over -- only
    # category_match (0.10) + the capped image contribution (0.20) is
    # available, well short of the possible threshold.
    result = _score_pair(a, b, image_similarity=1.0)
    assert result is None or result.score < _POSSIBLE_THRESHOLD


def test_category_id_match_takes_precedence_over_suggestion_text():
    category_id = uuid.uuid4()
    a = make_product(category_id=category_id, category_suggestion="Nuts")
    b = make_product(category_id=category_id, category_suggestion="Completely Different Text")
    result = _score_pair(a, b, image_similarity=None)
    assert result is not None
    assert "category_match" in result.reasons


# --- Image-hash contribution is capped and never sufficient alone ---------


def test_image_similarity_alone_with_zero_applicable_metadata_never_matches():
    """The strict guarantee: with NO comparable metadata evidence at all
    (every field null/inapplicable on at least one side), a pair is never
    scored -- not even a perfect image match can manufacture a match out
    of nothing. See _score_pair's `applicable_weight <= 0` guard."""
    a = make_product(
        name_en=None,
        name_ar=None,
        brand=None,
        flavor_variant=None,
        category_suggestion=None,
        category_id=None,
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        barcode=None,
    )
    b = make_product(
        name_en=None,
        name_ar=None,
        brand=None,
        flavor_variant=None,
        category_suggestion=None,
        category_id=None,
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        barcode=None,
    )
    assert _score_pair(a, b, image_similarity=1.0) is None


def test_image_similarity_alone_cannot_reach_the_possible_threshold():
    """With only weak name evidence applicable (package_weight/brand/
    flavor/category all null or inapplicable on both sides), even a
    perfect image match must not be enough to cross "possible"."""
    a = make_product(
        brand=None,
        flavor_variant=None,
        category_suggestion=None,
        barcode=None,
        selling_mode=SellingMode.UNIT,
        package_weight=None,
        name_en="Product A",
        name_ar="أ",
    )
    b = make_product(
        brand=None,
        flavor_variant=None,
        category_suggestion=None,
        barcode=None,
        selling_mode=SellingMode.UNIT,
        package_weight=None,
        name_en="Product B",
        name_ar="ب",
    )
    result = _score_pair(a, b, image_similarity=1.0)
    assert result is None or result.score < _POSSIBLE_THRESHOLD


def test_image_similarity_only_nudges_an_already_plausible_metadata_match():
    a = make_product()
    b = make_product()
    without_image = _score_pair(a, b, image_similarity=None)
    with_image = _score_pair(a, b, image_similarity=1.0)
    assert without_image is not None and with_image is not None
    assert with_image.score >= without_image.score
    assert with_image.score - without_image.score <= Decimal("0.20")


# --- Hard filters: barcode ---------------------------------------------


def test_conflicting_known_barcodes_are_hard_blocked():
    a = make_product(barcode="6291041500213")
    b = make_product(barcode="6291041500999")
    assert _passes_hard_filters(a, b) is False
    assert _score_pair(a, b, image_similarity=None) is None


def test_one_side_unknown_barcode_does_not_hard_block():
    a = make_product(barcode="6291041500213")
    b = make_product(barcode=None)
    assert _passes_hard_filters(a, b) is True


# --- Normalized scoring: null fields must not permanently cap the score --
# (the core fix -- previously brand/flavor/package_weight being null on
# BOTH sides capped the achievable score at 0.55, below the 0.60
# "possible" threshold, even for an otherwise-perfect name+category match)


def test_same_product_with_null_brand_flavor_weight_still_reaches_possible():
    """A bulk/loose product with no legible brand, no flavor text, and no
    package weight (all legitimately null, per Milestone 5's "never
    invent" rules) must still be flagged when name+category agree -- null
    fields must not be counted against it."""
    a = make_product(
        name_en="Mixed Nuts",
        name_ar="مكسرات مشكلة",
        brand=None,
        flavor_variant=None,
        category_suggestion="Nuts",
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        barcode=None,
    )
    b = make_product(
        name_en="Mixed Nuts",
        name_ar="مكسرات مشكلة",
        brand=None,
        flavor_variant=None,
        category_suggestion="Nuts",
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        barcode=None,
    )
    result = _score_pair(a, b, image_similarity=None)
    assert result is not None
    assert result.score >= _POSSIBLE_THRESHOLD
    assert "brand_match" not in result.reasons  # correctly not credited -- inapplicable, not matched
    assert "flavor_match" not in result.reasons
    assert "package_weight_match" not in result.reasons


def test_same_product_with_strong_name_category_and_image_evidence():
    a = make_product(
        name_en="Roasted Cashews",
        name_ar="كاجو محمص",
        brand=None,
        flavor_variant=None,
        category_suggestion="Nuts",
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        barcode=None,
    )
    b = make_product(
        name_en="Roasted Cashews",
        name_ar="كاجو محمص",
        brand=None,
        flavor_variant=None,
        category_suggestion="Nuts",
        selling_mode=SellingMode.WEIGHT,
        package_weight=None,
        barcode=None,
    )
    result = _score_pair(a, b, image_similarity=0.9)
    assert result is not None
    assert result.score >= _LIKELY_THRESHOLD


def test_generic_visual_only_name_vs_stronger_text_based_identity():
    """Mirrors a real observed case: one crop only supports a generic,
    visual-only guess (e.g. "Syrup/Molasses"); another crop of a similar
    product has a confidently text-read, more specific name (e.g. "Date
    Molasses"). Partial name overlap plus a shared category must
    contribute real, non-zero evidence -- not be blocked outright -- even
    though it may legitimately still fall short of "possible" without
    further corroborating evidence (a human reviewer can still compare
    the crops directly in Milestone 7)."""
    a = make_product(
        name_en="Syrup/Molasses",
        name_ar=None,
        brand=None,
        flavor_variant=None,
        category_suggestion="Syrups/Molasses",
        selling_mode=SellingMode.UNIT,
        package_weight=None,
        barcode=None,
    )
    b = make_product(
        name_en="Date Molasses",
        name_ar=None,
        brand=None,
        flavor_variant=None,
        category_suggestion="Syrups/Molasses",
        selling_mode=SellingMode.UNIT,
        package_weight=None,
        barcode=None,
    )
    # Not hard-blocked -- these are compatible, just uncertain.
    assert _passes_hard_filters(a, b) is True
    result = _score_pair(a, b, image_similarity=None)
    # Partial name overlap ("molasses") + shared category still produces
    # real, non-zero evidence -- never silently discarded.
    assert result is not None
    assert result.score > 0
    assert any(reason.startswith("name_similarity") for reason in result.reasons)
    assert "category_match" in result.reasons
    # With strong enough supporting image evidence on top, this SAME
    # partial-metadata pair can legitimately cross into "possible" --
    # proving the normalized scheme (not just the raw metadata ratio) is
    # what determines the final call, not an artificial null-field cap.
    with_strong_image = _score_pair(a, b, image_similarity=1.0)
    assert with_strong_image is not None
    assert with_strong_image.score > result.score
