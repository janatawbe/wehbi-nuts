"""HTTP-level tests for POST /api/storefront/checkout."""
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import StockStatus
from app.models.order import Order
from app.models.product import Product


def make_product(db_session: Session, **overrides) -> Product:
    defaults = dict(
        sku=f'SKU-{uuid.uuid4().hex[:8]}',
        name_en='Roasted Almonds',
        name_ar='لوز محمص',
        price=Decimal('20.00'),
        unit='weight',
        needs_review=False,
        stock_status=StockStatus.IN_STOCK,
    )
    defaults.update(overrides)
    product = Product(**defaults)
    db_session.add(product)
    db_session.commit()
    return product


def checkout_payload(items: list[dict], **overrides) -> dict:
    defaults = dict(
        customer_name='Jana Tawbe',
        customer_phone='+96170000000',
        delivery_address='Building 4, Hamra Street',
        delivery_area='Hamra',
        notes=None,
        items=items,
    )
    defaults.update(overrides)
    return defaults


def weight_line(product_id, grams=300) -> dict:
    return {'product_id': str(product_id), 'selling_mode': 'weight', 'weight_grams': grams}


def unit_line(product_id, quantity=2) -> dict:
    return {'product_id': str(product_id), 'selling_mode': 'unit', 'quantity': quantity}


def test_checkout_creates_an_order_and_returns_server_computed_totals(client: TestClient, db_session: Session):
    product = make_product(db_session, price=Decimal('20.00'))

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id, grams=500)]))

    assert response.status_code == 201
    body = response.json()
    assert body['order_number'].startswith('WN')
    assert body['status'] == 'pending'
    assert body['subtotal'] == '10.00'
    assert body['total'] == '10.00'
    assert len(body['items']) == 1
    assert body['items'][0]['selling_mode'] == 'weight'
    assert body['items'][0]['line_total'] == '10.00'


def test_checkout_response_includes_the_arabic_product_name(client: TestClient, db_session: Session):
    """Regression: the storefront's Order Success page localizes the
    order-line product name via localizedField(product_name,
    product_name_ar, language) -- the backend must snapshot BOTH names at
    order time, not just the English one."""
    product = make_product(db_session, name_en='Roasted Almonds', name_ar='لوز محمص')

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id)]))

    item = response.json()['items'][0]
    assert item['product_name'] == 'Roasted Almonds'
    assert item['product_name_ar'] == 'لوز محمص'


def test_checkout_response_carries_an_empty_arabic_name_through_unchanged(
    client: TestClient, db_session: Session
):
    """Product.name_ar itself is NOT NULL in the DB, but can still be
    empty for a not-yet-translated product -- the snapshot must carry
    that through as-is (never substituting the English name), leaving the
    frontend's existing localizedField() fallback to handle it, exactly
    like every other bilingual field in the app."""
    product = make_product(db_session, name_en='Roasted Almonds', name_ar='')

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id)]))

    item = response.json()['items'][0]
    assert item['product_name'] == 'Roasted Almonds'
    assert item['product_name_ar'] == ''


def test_checkout_ignores_any_price_the_client_tries_to_send(client: TestClient, db_session: Session):
    """The request schema has no price field at all -- an extra
    'total'/'unit_price' key in the JSON body is simply ignored, never
    used."""
    product = make_product(db_session, price=Decimal('20.00'))
    payload = checkout_payload([weight_line(product.id, grams=100)])
    payload['total'] = '0.01'
    payload['items'][0]['unit_price'] = '0.01'

    response = client.post('/api/storefront/checkout', json=payload)

    assert response.status_code == 201
    assert response.json()['total'] == '2.00'  # 20.00/kg * 0.1kg, from the DB -- not 0.01


def test_checkout_persists_the_order_to_the_database(client: TestClient, db_session: Session):
    product = make_product(db_session)

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id)]))

    order_id = uuid.UUID(response.json()['id'])
    assert db_session.get(Order, order_id) is not None


def test_checkout_rejects_an_empty_cart(client: TestClient):
    response = client.post('/api/storefront/checkout', json=checkout_payload([]))
    assert response.status_code == 422


def test_checkout_rejects_a_missing_required_field(client: TestClient, db_session: Session):
    product = make_product(db_session)
    payload = checkout_payload([weight_line(product.id)])
    del payload['delivery_area']

    response = client.post('/api/storefront/checkout', json=payload)

    assert response.status_code == 422


def test_checkout_rejects_a_zero_weight(client: TestClient, db_session: Session):
    product = make_product(db_session)

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id, grams=0)]))

    assert response.status_code == 422


def test_checkout_rejects_a_negative_weight(client: TestClient, db_session: Session):
    product = make_product(db_session)

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id, grams=-100)]))

    assert response.status_code == 422


def test_checkout_accepts_an_arbitrary_weight_not_on_the_old_fixed_preset_list(client: TestClient, db_session: Session):
    """137 g was rejected before this change (only 100/200/300/400/500/
    1000 were allowed) -- it must now be accepted like any other positive
    weight."""
    product = make_product(db_session, price=Decimal('20.00'))

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id, grams=137)]))

    assert response.status_code == 201
    assert response.json()['items'][0]['quantity'] == '0.137'


def test_checkout_accepts_a_weight_over_one_kilogram(client: TestClient, db_session: Session):
    product = make_product(db_session, price=Decimal('20.00'))

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id, grams=1500)]))

    assert response.status_code == 201
    body = response.json()
    assert body['items'][0]['quantity'] == '1.500'
    assert body['total'] == '30.00'


def test_checkout_accepts_several_kilograms(client: TestClient, db_session: Session):
    product = make_product(db_session, price=Decimal('10.00'))

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id, grams=7000)]))

    assert response.status_code == 201
    body = response.json()
    assert body['items'][0]['quantity'] == '7.000'
    assert body['total'] == '70.00'


def test_checkout_rejects_a_duplicate_product_in_one_request(client: TestClient, db_session: Session):
    product = make_product(db_session)

    response = client.post(
        '/api/storefront/checkout',
        json=checkout_payload([weight_line(product.id), weight_line(product.id)]),
    )

    assert response.status_code == 422


def test_checkout_rejects_an_unknown_product(client: TestClient):
    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(uuid.uuid4())]))
    assert response.status_code == 422


def test_checkout_rejects_an_out_of_stock_product(client: TestClient, db_session: Session):
    product = make_product(db_session, stock_status=StockStatus.OUT_OF_STOCK)

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id)]))

    assert response.status_code == 422


def test_checkout_rejects_a_hidden_needs_review_product(client: TestClient, db_session: Session):
    product = make_product(db_session, needs_review=True)

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id)]))

    assert response.status_code == 422


def test_checkout_rejects_a_selling_mode_mismatch(client: TestClient, db_session: Session):
    product = make_product(db_session, unit='unit')

    response = client.post('/api/storefront/checkout', json=checkout_payload([weight_line(product.id)]))

    assert response.status_code == 422


def test_checkout_supports_a_unit_mode_product_with_package_weight(client: TestClient, db_session: Session):
    product = make_product(db_session, unit='unit', price=Decimal('5.00'), weight=Decimal('0.250'))

    response = client.post('/api/storefront/checkout', json=checkout_payload([unit_line(product.id, quantity=3)]))

    assert response.status_code == 201
    item = response.json()['items'][0]
    assert item['quantity'] == '3.000'
    assert item['line_total'] == '15.00'
    assert item['package_weight'] == '0.250'
