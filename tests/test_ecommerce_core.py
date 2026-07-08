"""Tests for ecommerce_core — e-Commerce Integration (P4-E).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_edi_core.py). Cross-module
calls (create_so, add_so_item, get_shipment, get_price_for_product) and
the outbound HTTP call (urlopen) are patched at their usage site so
tests exercise this module's own logic in isolation.
"""

import base64
import hashlib
import hmac
import json
from urllib.error import URLError
from unittest.mock import MagicMock, patch

import pytest

from manufacturing.ecommerce_core import (
    ensure_ecommerce_tables, verify_webhook_signature, parse_order_webhook,
    receive_order_webhook, set_item_xref, resolve_product_id,
    push_inventory_level, push_price_update, push_shipment_confirmation,
    list_sync_log, find_connection_for_so,
)


def _conn(fetchone_results=None, fetchall_results=None):
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


def _sign(secret: str, body: bytes) -> str:
    return base64.b64encode(
        hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    ).decode('utf-8')


SHOPIFY_ORDER = {
    'id': 5551212,
    'created_at': '2026-07-07T12:00:00-04:00',
    'email': 'buyer@example.com',
    'line_items': [
        {'sku': 'SHOP-SKU-1', 'name': 'Widget Deluxe', 'quantity': 2, 'price': '25.50'},
        {'sku': 'SHOP-SKU-UNMAPPED', 'name': 'Gadget', 'quantity': 1, 'price': '9.99'},
    ],
}

WOO_ORDER = {
    'id': 909,
    'date_created': '2026-07-07T09:30:00',
    'billing': {'email': 'woobuyer@example.com'},
    'line_items': [
        {'sku': 'WOO-SKU-1', 'name': 'Bracket', 'quantity': 3, 'price': '4.25'},
    ],
}


# ── setup ────────────────────────────────────────────────────────────────

def test_ensure_ecommerce_tables_creates_all_four():
    conn = MagicMock()
    ensure_ecommerce_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS storefront_connection (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS storefront_item_xref (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS ecommerce_order_log (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS ecommerce_sync_log (' in c for c in calls)


# ── webhook signature verification ──────────────────────────────────────

def test_verify_webhook_signature_valid():
    body = b'{"id": 1}'
    sig = _sign('mysecret', body)
    assert verify_webhook_signature('mysecret', body, sig) is True


def test_verify_webhook_signature_invalid():
    body = b'{"id": 1}'
    sig = _sign('mysecret', body)
    assert verify_webhook_signature('wrongsecret', body, sig) is False


def test_verify_webhook_signature_missing_secret_or_signature():
    assert verify_webhook_signature('', b'{}', 'sig') is False
    assert verify_webhook_signature('secret', b'{}', '') is False


# ── parse_order_webhook ──────────────────────────────────────────────────

def test_parse_order_webhook_shopify_shape():
    result = parse_order_webhook(SHOPIFY_ORDER)
    assert result['external_order_id'] == '5551212'
    assert result['order_date'] == '2026-07-07'
    assert result['email'] == 'buyer@example.com'
    assert len(result['lines']) == 2
    assert result['lines'][0] == {
        'external_sku': 'SHOP-SKU-1', 'description': 'Widget Deluxe',
        'qty': 2.0, 'unit_price': 25.50,
    }


def test_parse_order_webhook_woocommerce_shape():
    result = parse_order_webhook(WOO_ORDER)
    assert result['external_order_id'] == '909'
    assert result['order_date'] == '2026-07-07'
    assert len(result['lines']) == 1
    assert result['lines'][0]['external_sku'] == 'WOO-SKU-1'
    assert result['lines'][0]['qty'] == 3.0
    assert result['lines'][0]['unit_price'] == 4.25


def test_parse_order_webhook_missing_id_returns_empty_string():
    assert parse_order_webhook({'line_items': []})['external_order_id'] == ''


# ── item xref ─────────────────────────────────────────────────────────────

def test_set_item_xref_raises_without_external_sku():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_item_xref(conn, 1, '', 10)
    assert conn.execute.call_count == 0


def test_set_item_xref_upserts():
    conn = MagicMock()
    set_item_xref(conn, 1, 'SHOP-SKU-1', 10)
    sql, params = conn.execute.call_args[0]
    assert 'ON CONFLICT (connection_id, external_sku) DO UPDATE' in sql
    assert params == (1, 'SHOP-SKU-1', 10)


def test_resolve_product_id_mapped():
    conn = _conn(fetchone_results=[{'product_id': 42}])
    assert resolve_product_id(conn, 1, 'SHOP-SKU-1') == 42


def test_resolve_product_id_unmapped_sku():
    conn = _conn(fetchone_results=[None])
    assert resolve_product_id(conn, 1, 'UNKNOWN') is None


def test_resolve_product_id_empty_sku_short_circuits():
    conn = MagicMock()
    assert resolve_product_id(conn, 1, '') is None
    assert conn.execute.call_count == 0


# ── receive_order_webhook ────────────────────────────────────────────────

def _active_connection(**overrides):
    conn = {
        'id': 1, 'platform': 'shopify', 'store_name': 'My Shop',
        'webhook_secret': 'mysecret', 'default_customer_id': 5,
        'default_price_list_id': None, 'sync_endpoint_url': '',
        'is_active': True,
    }
    conn.update(overrides)
    return conn


def test_receive_order_webhook_rejects_bad_signature():
    body = json.dumps(SHOPIFY_ORDER).encode('utf-8')
    with patch('manufacturing.ecommerce_core.get_connection', return_value=_active_connection()):
        conn = MagicMock()
        result = receive_order_webhook(conn, 1, body, 'bad-signature')
    assert result['ok'] is False
    assert 'signature' in result['error']


def test_receive_order_webhook_unknown_connection():
    body = json.dumps(SHOPIFY_ORDER).encode('utf-8')
    with patch('manufacturing.ecommerce_core.get_connection', return_value=None):
        conn = MagicMock()
        result = receive_order_webhook(conn, 999, body, 'whatever')
    assert result['ok'] is False


def test_receive_order_webhook_creates_so_with_mapped_and_unmapped_lines():
    body = json.dumps(SHOPIFY_ORDER).encode('utf-8')
    sig = _sign('mysecret', body)

    def fake_resolve(conn, connection_id, external_sku):
        return 42 if external_sku == 'SHOP-SKU-1' else None

    with patch('manufacturing.ecommerce_core.get_connection', return_value=_active_connection()), \
         patch('manufacturing.ecommerce_core.resolve_product_id', side_effect=fake_resolve), \
         patch('manufacturing.ecommerce_core.next_so_number', return_value='SO-2026-0001'), \
         patch('manufacturing.ecommerce_core.create_so', return_value=7) as mock_create_so, \
         patch('manufacturing.ecommerce_core.add_so_item') as mock_add_item:
        conn = _conn(fetchone_results=[None])  # no existing order-log row
        result = receive_order_webhook(conn, 1, body, sig, created_by='eric')

    assert result == {'ok': True, 'duplicate': False, 'so_id': 7,
                       'so_number': 'SO-2026-0001', 'unmapped_count': 1, 'line_count': 2}
    mock_create_so.assert_called_once()
    _, kwargs = mock_create_so.call_args
    assert kwargs['customer_id'] == 5
    assert kwargs['order_date'] == '2026-07-07'
    assert '5551212' in kwargs['notes']

    assert mock_add_item.call_count == 2
    first_call = mock_add_item.call_args_list[0]
    assert first_call[0][2] == 'Widget Deluxe'
    assert first_call[1]['product_id'] == 42
    assert first_call[1]['qty'] == 2.0

    second_call = mock_add_item.call_args_list[1]
    assert second_call[1]['product_id'] is None

    order_log_calls = [c for c in conn.execute.call_args_list
                       if 'INSERT INTO ecommerce_order_log' in c[0][0]]
    assert len(order_log_calls) == 1
    sync_log_calls = [c for c in conn.execute.call_args_list
                      if 'INSERT INTO ecommerce_sync_log' in c[0][0]]
    assert len(sync_log_calls) == 1


def test_receive_order_webhook_detects_duplicate():
    body = json.dumps(SHOPIFY_ORDER).encode('utf-8')
    sig = _sign('mysecret', body)
    with patch('manufacturing.ecommerce_core.get_connection', return_value=_active_connection()), \
         patch('manufacturing.ecommerce_core.create_so') as mock_create_so:
        conn = _conn(fetchone_results=[{'so_id': 99}])
        result = receive_order_webhook(conn, 1, body, sig)

    assert result == {'ok': True, 'duplicate': True, 'so_id': 99}
    mock_create_so.assert_not_called()


def test_receive_order_webhook_invalid_json():
    with patch('manufacturing.ecommerce_core.get_connection', return_value=_active_connection()):
        conn = MagicMock()
        sig = _sign('mysecret', b'not json')
        result = receive_order_webhook(conn, 1, b'not json', sig)
    assert result['ok'] is False
    assert 'JSON' in result['error']


# ── outbound push: inventory / price / shipment ─────────────────────────

def test_push_inventory_level_queued_when_no_endpoint():
    connection = _active_connection(sync_endpoint_url='')
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core._resolve_external_sku', return_value='SHOP-SKU-1'):
        conn = _conn(fetchone_results=[{'amount': 12.0}])
        result = push_inventory_level(conn, 1, 42, created_by='eric')
    assert result['status'] == 'queued'


def test_push_inventory_level_success_when_endpoint_configured():
    connection = _active_connection(sync_endpoint_url='https://store.example/sync')
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.__enter__.return_value = fake_resp
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core._resolve_external_sku', return_value='SHOP-SKU-1'), \
         patch('manufacturing.ecommerce_core.urlopen', return_value=fake_resp):
        conn = _conn(fetchone_results=[{'amount': 12.0}])
        result = push_inventory_level(conn, 1, 42)
    assert result['status'] == 'success'


def test_push_inventory_level_failed_on_connection_error():
    connection = _active_connection(sync_endpoint_url='https://unreachable.example/sync')
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core._resolve_external_sku', return_value='SHOP-SKU-1'), \
         patch('manufacturing.ecommerce_core.urlopen', side_effect=URLError('refused')):
        conn = _conn(fetchone_results=[{'amount': 12.0}])
        result = push_inventory_level(conn, 1, 42)
    assert result['status'] == 'failed'


def test_push_inventory_level_unknown_connection():
    with patch('manufacturing.ecommerce_core.get_connection', return_value=None):
        conn = MagicMock()
        result = push_inventory_level(conn, 999, 42)
    assert result['status'] == 'failed'


def test_push_price_update_no_price_list_configured():
    connection = _active_connection(default_price_list_id=None)
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection):
        conn = MagicMock()
        result = push_price_update(conn, 1, 42)
    assert result['status'] == 'failed'
    assert 'price list' in result['detail']


def test_push_price_update_queued_when_no_endpoint():
    connection = _active_connection(default_price_list_id=3, sync_endpoint_url='')
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core.get_price_for_product', return_value=19.99), \
         patch('manufacturing.ecommerce_core._resolve_external_sku', return_value='SHOP-SKU-1'):
        conn = MagicMock()
        result = push_price_update(conn, 1, 42)
    assert result['status'] == 'queued'


def test_push_shipment_confirmation_no_ecommerce_origin():
    connection = _active_connection()
    shipment = {'id': 1, 'so_id': 7, 'carrier': 'UPS', 'tracking_number': '1Z9'}
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core.get_shipment', return_value=shipment):
        conn = _conn(fetchone_results=[None])
        result = push_shipment_confirmation(conn, 1, 1)
    assert result['status'] == 'failed'
    assert 'e-commerce origin' in result['detail']


def test_push_shipment_confirmation_queued_when_no_endpoint():
    connection = _active_connection(sync_endpoint_url='')
    shipment = {'id': 1, 'so_id': 7, 'carrier': 'UPS', 'tracking_number': '1Z9'}
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core.get_shipment', return_value=shipment):
        conn = _conn(fetchone_results=[{'external_order_id': '5551212'}])
        result = push_shipment_confirmation(conn, 1, 1)
    assert result['status'] == 'queued'


def test_push_shipment_confirmation_shipment_not_found():
    connection = _active_connection()
    with patch('manufacturing.ecommerce_core.get_connection', return_value=connection), \
         patch('manufacturing.ecommerce_core.get_shipment', return_value=None):
        conn = MagicMock()
        result = push_shipment_confirmation(conn, 1, 999)
    assert result['status'] == 'failed'
    assert 'Shipment not found' in result['detail']


# ── sync log / lookups ────────────────────────────────────────────────────

def test_list_sync_log_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'event_type': 'order_webhook'}]])
    result = list_sync_log(conn)
    assert result == [{'id': 1, 'event_type': 'order_webhook'}]


def test_find_connection_for_so_found():
    conn = _conn(fetchone_results=[{'connection_id': 1}])
    assert find_connection_for_so(conn, 7) == 1


def test_find_connection_for_so_not_found():
    conn = _conn(fetchone_results=[None])
    assert find_connection_for_so(conn, 999) is None
