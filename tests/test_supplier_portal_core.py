"""Tests for supplier_portal_core — Supplier Self-Service Portal.

No live database: a MagicMock connection stands in for psycopg2 (mirrors
test_customer_portal_core.py), plus unittest.mock.patch for the
cross-module functions this module re-imports by name.
"""

from unittest.mock import MagicMock, patch

import bcrypt
import pytest

from manufacturing.supplier_portal_core import (
    find_supplier_by_email, has_portal_login,
    register_supplier_login, verify_supplier_login, get_portal_profile,
    list_my_pos, get_my_po, acknowledge_po,
    list_my_invoices, get_my_invoice, submit_invoice,
    list_my_rfqs, get_my_rfq, submit_quote,
    get_portal_dashboard,
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


# ── portal login ─────────────────────────────────────────────────────────

def test_find_supplier_by_email_found():
    conn = _conn(fetchone_results=[{'id': 5, 'email': 'a@b.com'}])
    result = find_supplier_by_email(conn, 'A@B.com')
    assert result == {'id': 5, 'email': 'a@b.com'}


def test_find_supplier_by_email_not_found():
    conn = _conn(fetchone_results=[None])
    assert find_supplier_by_email(conn, 'nope@nowhere.com') is None


def test_has_portal_login_true_false():
    conn = _conn(fetchone_results=[{'id': 1}])
    assert has_portal_login(conn, 5) is True
    conn2 = _conn(fetchone_results=[None])
    assert has_portal_login(conn2, 5) is False


@patch('manufacturing.supplier_portal_core.has_portal_login')
@patch('manufacturing.supplier_portal_core.find_supplier_by_email')
def test_register_supplier_login_raises_when_no_supplier(mock_find, mock_has):
    mock_find.return_value = None
    conn = _conn()
    with pytest.raises(ValueError):
        register_supplier_login(conn, 'nope@nowhere.com', 'pw')


@patch('manufacturing.supplier_portal_core.has_portal_login')
@patch('manufacturing.supplier_portal_core.find_supplier_by_email')
def test_register_supplier_login_raises_when_already_registered(mock_find, mock_has):
    mock_find.return_value = {'id': 5, 'email': 'a@b.com'}
    mock_has.return_value = True
    conn = _conn()
    with pytest.raises(ValueError):
        register_supplier_login(conn, 'a@b.com', 'pw')


@patch('manufacturing.supplier_portal_core.has_portal_login')
@patch('manufacturing.supplier_portal_core.find_supplier_by_email')
def test_register_supplier_login_inserts_hashed_password(mock_find, mock_has):
    mock_find.return_value = {'id': 5, 'email': 'a@b.com'}
    mock_has.return_value = False
    conn = _conn()
    supplier_id = register_supplier_login(conn, 'a@b.com', 'secret123')
    assert supplier_id == 5
    insert_sql, insert_params = conn.execute.call_args_list[0][0]
    assert 'INSERT INTO supplier_login' in insert_sql
    assert insert_params[0] == 5
    stored_hash = insert_params[2]
    assert bcrypt.checkpw(b'secret123', stored_hash.encode())


def test_verify_supplier_login_returns_none_for_unknown_email():
    conn = _conn(fetchone_results=[None])
    assert verify_supplier_login(conn, 'nope@nowhere.com', 'pw') is None


def test_verify_supplier_login_returns_none_for_bad_password():
    good_hash = bcrypt.hashpw(b'rightpw', bcrypt.gensalt()).decode()
    conn = _conn(fetchone_results=[
        {'supplier_id': 5, 'password_hash': good_hash, 'email': 'a@b.com',
         'company_name': 'Acme Supply', 'first_name': '', 'last_name': ''},
    ])
    assert verify_supplier_login(conn, 'a@b.com', 'wrongpw') is None


def test_verify_supplier_login_success_returns_profile():
    good_hash = bcrypt.hashpw(b'rightpw', bcrypt.gensalt()).decode()
    conn = _conn(fetchone_results=[
        {'supplier_id': 5, 'password_hash': good_hash, 'email': 'a@b.com',
         'company_name': 'Acme Supply', 'first_name': '', 'last_name': ''},
        {'supplier_id': 5, 'company_name': 'Acme Supply', 'first_name': '',
         'last_name': '', 'email': 'a@b.com'},
    ])
    profile = verify_supplier_login(conn, 'a@b.com', 'rightpw')
    assert profile['supplier_id'] == 5
    assert profile['display_name'] == 'Acme Supply'


def test_get_portal_profile_prefers_company_then_name():
    conn = _conn(fetchone_results=[
        {'supplier_id': 5, 'company_name': '', 'first_name': 'Jane',
         'last_name': 'Doe', 'email': 'a@b.com'},
    ])
    profile = get_portal_profile(conn, 5)
    assert profile['display_name'] == 'Jane Doe'


def test_get_portal_profile_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_portal_profile(conn, 999) is None


# ── Purchase Orders (supplier-scoped) ────────────────────────────────────

@patch('manufacturing.supplier_portal_core.list_pos')
def test_list_my_pos_scopes_to_supplier(mock_list_pos):
    mock_list_pos.return_value = [{'id': 1}]
    conn = _conn()
    result = list_my_pos(conn, supplier_id=5)
    assert result == [{'id': 1}]
    mock_list_pos.assert_called_once_with(conn, supplier_id=5)


@patch('manufacturing.supplier_portal_core.get_po')
def test_get_my_po_returns_none_when_not_owned(mock_get_po):
    mock_get_po.return_value = {'id': 1, 'supplier_id': 999}
    conn = _conn()
    assert get_my_po(conn, supplier_id=5, po_id=1) is None


@patch('manufacturing.supplier_portal_core.get_po')
def test_get_my_po_returns_po_when_owned(mock_get_po):
    mock_get_po.return_value = {'id': 1, 'supplier_id': 5}
    conn = _conn()
    assert get_my_po(conn, supplier_id=5, po_id=1) == {'id': 1, 'supplier_id': 5}


@patch('manufacturing.supplier_portal_core.get_po')
def test_acknowledge_po_raises_when_not_owned(mock_get_po):
    mock_get_po.return_value = {'id': 1, 'supplier_id': 999}
    conn = _conn()
    with pytest.raises(ValueError):
        acknowledge_po(conn, supplier_id=5, po_id=1)


@patch('manufacturing.supplier_portal_core.get_po')
def test_acknowledge_po_updates_when_owned(mock_get_po):
    mock_get_po.return_value = {'id': 1, 'supplier_id': 5}
    conn = _conn()
    acknowledge_po(conn, supplier_id=5, po_id=1, notes='confirmed')
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE purchase_order SET supplier_acknowledged_at' in sql
    assert params[1] == 'confirmed'
    assert params[2] == 1


# ── AP Invoices (supplier-scoped) ────────────────────────────────────────

@patch('manufacturing.supplier_portal_core.list_ap_invoices')
def test_list_my_invoices_scopes_to_vendor_id(mock_list):
    mock_list.return_value = [{'id': 1}]
    conn = _conn()
    result = list_my_invoices(conn, supplier_id=5)
    assert result == [{'id': 1}]
    mock_list.assert_called_once_with(conn, vendor_id=5)


@patch('manufacturing.supplier_portal_core.get_ap_invoice')
def test_get_my_invoice_returns_none_when_not_owned(mock_get):
    mock_get.return_value = {'id': 1, 'vendor_id': 999}
    conn = _conn()
    assert get_my_invoice(conn, supplier_id=5, inv_id=1) is None


@patch('manufacturing.supplier_portal_core.get_po')
def test_submit_invoice_rejects_po_not_owned(mock_get_po):
    mock_get_po.return_value = {'id': 10, 'supplier_id': 999}
    conn = _conn()
    with pytest.raises(ValueError):
        submit_invoice(conn, supplier_id=5, po_id=10, invoice_number='INV-1',
                       invoice_date='2026-01-01', due_date='2026-02-01',
                       amount=100.0, description='', created_by='a@b.com')


def test_submit_invoice_requires_due_date():
    conn = _conn()
    with pytest.raises(ValueError, match='Due date'):
        submit_invoice(conn, supplier_id=5, po_id=None, invoice_number='INV-1',
                       invoice_date='2026-01-01', due_date='',
                       amount=100.0, description='', created_by='a@b.com')


@patch('manufacturing.supplier_portal_core.create_ap_invoice')
def test_submit_invoice_allows_no_po_reference(mock_create):
    mock_create.return_value = 77
    conn = _conn()
    inv_id = submit_invoice(conn, supplier_id=5, po_id=None, invoice_number='INV-1',
                            invoice_date='2026-01-01', due_date='2026-02-01',
                            amount=100.0, description='', created_by='a@b.com')
    assert inv_id == 77
    mock_create.assert_called_once_with(
        conn, 5, 'INV-1', '2026-01-01', '2026-02-01', 100.0, '', 'a@b.com')


@patch('manufacturing.supplier_portal_core.create_ap_invoice')
@patch('manufacturing.supplier_portal_core.get_po')
def test_submit_invoice_creates_for_owned_po(mock_get_po, mock_create):
    mock_get_po.return_value = {'id': 10, 'supplier_id': 5}
    mock_create.return_value = 88
    conn = _conn()
    inv_id = submit_invoice(conn, supplier_id=5, po_id=10, invoice_number='INV-2',
                            invoice_date='2026-01-01', due_date='2026-02-01',
                            amount=250.0, description='parts', created_by='a@b.com')
    assert inv_id == 88


# ── RFQs (supplier-scoped) ────────────────────────────────────────────────

def test_list_my_rfqs_scopes_to_supplier():
    conn = _conn(fetchall_results=[[{'id': 1, 'rfq_number': 'RFQ-2026-0001'}]])
    result = list_my_rfqs(conn, supplier_id=5)
    assert result == [{'id': 1, 'rfq_number': 'RFQ-2026-0001'}]
    sql, params = conn.execute.call_args[0]
    assert 'rv.supplier_id = %s' in sql
    assert params == (5,)


def test_get_my_rfq_returns_none_when_not_invited():
    conn = _conn(fetchone_results=[None])
    assert get_my_rfq(conn, supplier_id=5, rfq_id=1) is None


@patch('manufacturing.supplier_portal_core.get_quote')
@patch('manufacturing.supplier_portal_core.list_rfq_items')
@patch('manufacturing.supplier_portal_core.get_rfq')
def test_get_my_rfq_merges_own_quotes(mock_get_rfq, mock_list_items, mock_get_quote):
    conn = _conn(fetchone_results=[{'id': 1}])  # _is_invited check
    mock_get_rfq.return_value = {'id': 1, 'rfq_number': 'RFQ-2026-0001'}
    mock_list_items.return_value = [{'id': 100, 'description': 'Widget'}]
    mock_get_quote.return_value = {'quoted_price': 12.5, 'lead_time_days': 7}
    rfq = get_my_rfq(conn, supplier_id=5, rfq_id=1)
    assert rfq['items'][0]['my_quoted_price'] == 12.5
    assert rfq['items'][0]['my_lead_time_days'] == 7


def test_submit_quote_raises_when_item_missing():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError, match='No RFQ item'):
        submit_quote(conn, supplier_id=5, rfq_item_id=999, quoted_price=10.0)


def test_submit_quote_raises_when_not_invited():
    conn = _conn(fetchone_results=[{'rfq_id': 1}, None])
    with pytest.raises(ValueError, match='not invited'):
        submit_quote(conn, supplier_id=5, rfq_item_id=100, quoted_price=10.0)


@patch('manufacturing.supplier_portal_core.enter_quote')
def test_submit_quote_enters_for_invited_supplier(mock_enter):
    conn = _conn(fetchone_results=[{'rfq_id': 1}, {'id': 1}])
    submit_quote(conn, supplier_id=5, rfq_item_id=100, quoted_price=10.0, lead_time_days=5)
    mock_enter.assert_called_once_with(conn, 100, 5, 10.0, 5)


# ── dashboard ────────────────────────────────────────────────────────────

@patch('manufacturing.supplier_portal_core.list_my_rfqs')
@patch('manufacturing.supplier_portal_core.list_my_invoices')
@patch('manufacturing.supplier_portal_core.list_my_pos')
def test_get_portal_dashboard_shape(mock_pos, mock_invoices, mock_rfqs):
    mock_pos.return_value = [
        {'id': 1, 'status': 'sent', 'supplier_acknowledged_at': None},
        {'id': 2, 'status': 'received', 'supplier_acknowledged_at': '2026-01-01'},
        {'id': 3, 'status': 'sent', 'supplier_acknowledged_at': '2026-01-02'},
    ]
    mock_invoices.return_value = [
        {'id': 1, 'status': 'open', 'balance': 100.0},
        {'id': 2, 'status': 'paid', 'balance': 0.0},
    ]
    mock_rfqs.return_value = [
        {'id': 1, 'status': 'open'},
        {'id': 2, 'status': 'closed'},
    ]
    dash = get_portal_dashboard(_conn(), supplier_id=5)
    assert dash['open_po_count'] == 2  # excludes the 'received' one
    assert dash['unacknowledged_po_count'] == 1
    assert dash['open_invoice_count'] == 1
    assert dash['open_invoice_balance'] == 100.0
    assert dash['open_rfq_count'] == 1
