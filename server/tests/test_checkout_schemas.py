"""Pydantic-level validation for the Milestone 10 checkout request shapes
-- these must reject a malformed request before it ever reaches
checkout_service (which then also re-validates defensively; see
test_checkout_service.py for that layer)."""
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.checkout import CheckoutItemRequest, CheckoutRequest


def make_weight_item(**overrides):
    defaults = dict(product_id=uuid.uuid4(), selling_mode='weight', weight_grams=300, quantity=None)
    defaults.update(overrides)
    return defaults


def make_unit_item(**overrides):
    defaults = dict(product_id=uuid.uuid4(), selling_mode='unit', quantity=2, weight_grams=None)
    defaults.update(overrides)
    return defaults


def make_request(items, **overrides):
    defaults = dict(
        customer_name='Jana',
        customer_phone='+96170000000',
        delivery_address='123 Main St',
        delivery_area='Hamra',
        notes=None,
        items=items,
    )
    defaults.update(overrides)
    return defaults


# --- CheckoutItemRequest -----------------------------------------------


def test_accepts_a_valid_weight_item():
    item = CheckoutItemRequest(**make_weight_item(weight_grams=100))
    assert item.weight_grams == 100


@pytest.mark.parametrize('grams', [1, 50, 150, 999, 1500, 2000, 12500, 1_000_000])
def test_accepts_any_positive_weight_no_matter_how_large(grams):
    """There is deliberately no fixed preset list or business-rule
    maximum any more -- a customer can order any practical amount,
    including several kilograms."""
    item = CheckoutItemRequest(**make_weight_item(weight_grams=grams))
    assert item.weight_grams == grams


@pytest.mark.parametrize('grams', [0, -1, -100])
def test_rejects_zero_or_negative_weight(grams):
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_weight_item(weight_grams=grams))


def test_rejects_a_weight_so_large_it_would_overflow_the_database_column():
    """Not a business-rule cap -- purely a safety net against a value too
    large to fit order_items.quantity (Numeric(10, 3))."""
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_weight_item(weight_grams=99_999_999_999))


@pytest.mark.parametrize(
    'grams,label',
    [
        (100, '100 g'),
        (750, '750 g'),
        (1000, '1 kg (as 1000 g)'),
        (1500, '1.5 kg (as 1500 g)'),
        (3000, '3 kg (as 3000 g)'),
        (5000, 'more than 3 kg'),
    ],
)
def test_accepts_the_exact_frontend_normalized_examples(grams, label):
    """The frontend's WeightAmountPicker always normalizes a customer's
    direct entry (e.g. "1.5" + kg, or "750" + g) to a whole-gram integer
    before sending it -- these are exactly the values it would send for
    the examples in the product brief."""
    item = CheckoutItemRequest(**make_weight_item(weight_grams=grams))
    assert item.weight_grams == grams, label


@pytest.mark.parametrize('malformed', ['abc', '', None, 100.5, [100], {'grams': 100}])
def test_rejects_malformed_weight_values(malformed):
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_weight_item(weight_grams=malformed))


def test_rejects_a_weight_item_that_also_sets_quantity():
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_weight_item(quantity=1))


def test_rejects_a_weight_item_missing_weight_grams():
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_weight_item(weight_grams=None))


def test_accepts_a_valid_unit_item():
    item = CheckoutItemRequest(**make_unit_item(quantity=5))
    assert item.quantity == 5


@pytest.mark.parametrize('quantity', [0, -1, 21, 1000])
def test_rejects_a_quantity_outside_the_allowed_range(quantity):
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_unit_item(quantity=quantity))


def test_rejects_a_unit_item_that_also_sets_weight_grams():
    with pytest.raises(ValidationError):
        CheckoutItemRequest(**make_unit_item(weight_grams=100))


# --- CheckoutRequest -----------------------------------------------------


def test_accepts_a_well_formed_request():
    request = CheckoutRequest(**make_request([make_weight_item(), make_unit_item()]))
    assert len(request.items) == 2


def test_rejects_an_empty_cart():
    with pytest.raises(ValidationError):
        CheckoutRequest(**make_request([]))


def test_rejects_a_duplicate_product_id_across_two_lines():
    shared_id = uuid.uuid4()
    with pytest.raises(ValidationError, match='Duplicate product'):
        CheckoutRequest(**make_request([make_weight_item(product_id=shared_id), make_unit_item(product_id=shared_id)]))


@pytest.mark.parametrize('field', ['customer_name', 'customer_phone', 'delivery_address', 'delivery_area'])
def test_rejects_a_blank_required_field(field):
    with pytest.raises(ValidationError):
        CheckoutRequest(**make_request([make_unit_item()], **{field: '   '}))


def test_blank_notes_is_normalized_to_none():
    request = CheckoutRequest(**make_request([make_unit_item()], notes='   '))
    assert request.notes is None


def test_real_notes_are_preserved_and_trimmed():
    request = CheckoutRequest(**make_request([make_unit_item()], notes='  Ring the bell  '))
    assert request.notes == 'Ring the bell'
