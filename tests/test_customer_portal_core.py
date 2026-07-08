"""Tests for customer_portal_core — Customer Self-Service Portal (P3-C).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_wms_core.py), plus
unittest.mock.patch for the cross-module functions this module re-imports
by name.
"""

from unittest.mock import MagicMock, patch

import bcrypt
import pytest

from manufacturing.customer_portal_core import (
    find_customer_by_email, has_portal_login,
    register_customer_login, verify_customer_login, get_portal_profile,
    list_my_shipments, get_my_shipment,
    list_my_rmas, get_my_rma, submit_rma,
    get_tracking_events,
    create_payment_intent, confirm_payment_intent,
    render_invoice_pdf, render_packing_slip_pdf,
)


def _conn(fetchone_results=None, fetchall_results=None):
    """A MagicMock conn whose execute(...) returns one shared cursor mock;
    .fetchone()/.fetchall() replay the given results in call order."""
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── portal login ─────────────────────────────────────────────────────────────

def test_find_customer_by_email_found():
    conn = _conn(fetchone_results=[{'id': 5, 'email': 'a@b.com'}])
    result = find_customer_by_email(conn, 'A@B.com')
    assert result == {'id': 5, 'email': 'a@b.com'}


def test_find_customer_by_email_not_found():
    conn = _conn(fetchone_results=[None])
    assert find_customer_by_email(conn, 'nope@nowhere.com') is None


def test_has_portal_login_true_false():
    conn = _conn(fetchone_results=[{'id': 1}])
    assert has_portal_login(conn, 5) is True

    conn2 = _conn(fetchone_results=[None])
    assert has_portal_login(conn2, 5) is False


@patch('manufacturing.customer_portal_core.has_portal_login')
@patch('manufacturing.customer_portal_core.find_customer_by_email')
def test_register_customer_login_raises_when_no_customer(mock_find, mock_has):
    mock_find.return_value = None
    conn = _conn()
    with pytest.raises(ValueError):
        register_customer_login(conn, 'nope@nowhere.com', 'pw')


@patch('manufacturing.customer_portal_core.has_portal_login')
@patch('manufacturing.customer_portal_core.find_customer_by_email')
def test_register_customer_login_raises_when_already_registered(mock_find, mock_has):
    mock_find.return_value = {'id': 5, 'email': 'a@b.com'}
    mock_has.return_value = True
    conn = _conn()
    with pytest.raises(ValueError):
        register_customer_login(conn, 'a@b.com', 'pw')


@patch('manufacturing.customer_portal_core.has_portal_login')
@patch('manufacturing.customer_portal_core.find_customer_by_email')
def test_register_customer_login_inserts_hashed_password(mock_find, mock_has):
    mock_find.return_value = {'id': 5, 'email': 'a@b.com'}
    mock_has.return_value = False
    conn = _conn()
    customer_id = register_customer_login(conn, 'a@b.com', 'secret123')
    assert customer_id == 5
    insert_sql, insert_params = conn.execute.call_args_list[0][0]
    assert 'INSERT INTO customer_login' in insert_sql
    assert insert_params[0] == 5
    stored_hash = insert_params[2]
    assert bcrypt.checkpw(b'secret123', stored_hash.encode())


def test_verify_customer_login_returns_none_for_unknown_email():
    conn = _conn(fetchone_results=[None])
    assert verify_customer_login(conn, 'nope@nowhere.com', 'pw') is None


def test_verify_customer_login_returns_none_for_bad_password():
    good_hash = bcrypt.hashpw(b'rightpw', bcrypt.gensalt()).decode()
    conn = _conn(fetchone_results=[
        {'customer_id': 5, 'password_hash': good_hash, 'email': 'a@b.com',
         'company_name': 'Acme', 'first_name': '', 'last_name': ''},
    ])
    assert verify_customer_login(conn, 'a@b.com', 'wrongpw') is None


def test_verify_customer_login_success_returns_profile():
    good_hash = bcrypt.hashpw(b'rightpw', bcrypt.gensalt()).decode()
    conn = _conn(fetchone_results=[
        {'customer_id': 5, 'password_hash': good_hash, 'email': 'a@b.com',
         'company_name': 'Acme', 'first_name': '', 'last_name': ''},
        {'customer_id': 5, 'company_name': 'Acme', 'first_name': '', 'last_name': '', 'email': 'a@b.com'},
    ])
    profile = verify_customer_login(conn, 'a@b.com', 'rightpw')
    assert profile['customer_id'] == 5
    assert profile['display_name'] == 'Acme'


def test_get_portal_profile_prefers_company_then_name():
    conn = _conn(fetchone_results=[
        {'customer_id': 5, 'company_name': '', 'first_name': 'Jane', 'last_name': 'Doe', 'email': 'a@b.com'},
    ])
    profile = get_portal_profile(conn, 5)
    assert profile['display_name'] == 'Jane Doe'


def test_get_portal_profile_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_portal_profile(conn, 999) is None


# ── shipments (customer-scoped) ──────────────────────────────────────────────

def test_list_my_shipments_scopes_query_to_customer():
    conn = _conn(fetchall_results=[[{'id': 1, 'ship_number': 'SHIP-1'}]])
    result = list_my_shipments(conn, customer_id=5)
    assert result == [{'id': 1, 'ship_number': 'SHIP-1'}]
    sql, params = conn.execute.call_args[0]
    assert 'so.customer_id = %s' in sql
    assert params == (5,)


def test_get_my_shipment_returns_none_when_not_owned():
    conn = _conn(fetchone_results=[None])
    assert get_my_shipment(conn, customer_id=5, shipment_id=1) is None


# ── RMA (customer-scoped) ────────────────────────────────────────────────────

def test_list_my_rmas_scopes_query_to_customer():
    conn = _conn(fetchall_results=[[{'id': 1, 'rma_number': 'RMA-2026-0001'}]])
    result = list_my_rmas(conn, customer_id=5)
    assert result == [{'id': 1, 'rma_number': 'RMA-2026-0001'}]
    sql, params = conn.execute.call_args[0]
    assert 'so.customer_id = %s' in sql
    assert params == (5,)


def test_get_my_rma_returns_none_when_not_owned():
    conn = _conn(fetchone_results=[None])
    assert get_my_rma(conn, customer_id=5, rma_id=1) is None


@patch('manufacturing.customer_portal_core.create_rma')
@patch('manufacturing.customer_portal_core.get_portal_profile')
@patch('manufacturing.customer_portal_core.get_so')
def test_submit_rma_rejects_so_not_owned(mock_get_so, mock_profile, mock_create):
    mock_get_so.return_value = {'id': 10, 'customer_id': 999}
    conn = _conn()
    with pytest.raises(ValueError):
        submit_rma(conn, customer_id=5, so_id=10, reason='defective',
                   description='broken', created_by='a@b.com')
    mock_create.assert_not_called()


@patch('manufacturing.customer_portal_core.create_rma')
@patch('manufacturing.customer_portal_core.get_portal_profile')
@patch('manufacturing.customer_portal_core.get_so')
def test_submit_rma_creates_for_owned_so(mock_get_so, mock_profile, mock_create):
    mock_get_so.return_value = {'id': 10, 'customer_id': 5}
    mock_profile.return_value = {'display_name': 'Acme'}
    mock_create.return_value = 77
    conn = _conn()
    rma_id = submit_rma(conn, customer_id=5, so_id=10, reason='defective',
                        description='broken', created_by='a@b.com')
    assert rma_id == 77
    mock_create.assert_called_once_with(conn, 10, 'Acme', 'defective', 'broken', 'a@b.com')


@patch('manufacturing.customer_portal_core.create_rma')
@patch('manufacturing.customer_portal_core.get_portal_profile')
@patch('manufacturing.customer_portal_core.get_so')
def test_submit_rma_defaults_unknown_reason_to_other(mock_get_so, mock_profile, mock_create):
    mock_get_so.return_value = {'id': 10, 'customer_id': 5}
    mock_profile.return_value = {'display_name': 'Acme'}
    conn = _conn()
    submit_rma(conn, customer_id=5, so_id=10, reason='not_a_real_reason',
               description='broken', created_by='a@b.com')
    args = mock_create.call_args[0]
    assert args[3] == 'other'


# ── tracking stub ─────────────────────────────────────────────────────────────

def test_get_tracking_events_pending_only_first_step_done():
    events = get_tracking_events({'status': 'pending', 'carrier': 'UPS', 'ship_date': None})
    assert events[0]['label'] == 'Shipping Label Created'
    assert events[0]['done'] is True
    assert all(not e['done'] for e in events[1:])


def test_get_tracking_events_delivered_marks_all_done():
    events = get_tracking_events({'status': 'delivered', 'carrier': 'UPS', 'ship_date': '2026-01-01'})
    assert all(e['done'] for e in events)
    assert events[-1]['label'] == 'Delivered'
    assert events[-1]['date'] == '2026-01-04'


def test_get_tracking_events_cancelled_short_circuits():
    events = get_tracking_events({'status': 'cancelled', 'carrier': 'UPS', 'ship_date': '2026-01-01'})
    assert events[-1]['label'] == 'Shipment Cancelled'


def test_get_tracking_events_is_deterministic():
    shipment = {'status': 'in_transit', 'carrier': 'FedEx', 'ship_date': '2026-01-01'}
    assert get_tracking_events(shipment) == get_tracking_events(shipment)


# ── payment intent stub ───────────────────────────────────────────────────────

def test_create_payment_intent_inserts_and_returns_dict():
    conn = _conn(fetchone_results=[{'id': 42}])
    intent = create_payment_intent(conn, invoice_id=7, amount=150.0)
    assert intent['id'] == 42
    assert intent['invoice_id'] == 7
    assert intent['amount'] == 150.0
    assert intent['status'] == 'requires_confirmation'
    assert intent['stripe_intent_id'].startswith('pi_stub_')


def test_confirm_payment_intent_raises_for_unknown_intent():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        confirm_payment_intent(conn, intent_id=999)


def test_confirm_payment_intent_raises_if_already_succeeded():
    conn = _conn(fetchone_results=[
        {'id': 1, 'invoice_id': 7, 'amount': 100.0, 'status': 'succeeded',
         'stripe_intent_id': 'pi_stub_x'},
    ])
    with pytest.raises(ValueError):
        confirm_payment_intent(conn, intent_id=1)


@patch('manufacturing.customer_portal_core.record_ar_payment')
def test_confirm_payment_intent_records_payment_and_marks_succeeded(mock_record):
    conn = _conn(fetchone_results=[
        {'id': 1, 'invoice_id': 7, 'amount': 100.0, 'status': 'requires_confirmation',
         'stripe_intent_id': 'pi_stub_x'},
    ])
    result = confirm_payment_intent(conn, intent_id=1)
    assert result['status'] == 'succeeded'
    mock_record.assert_called_once()
    args = mock_record.call_args[0]
    assert args[1] == 7          # invoice_id
    assert args[3] == 100.0      # amount
    assert args[4] == 'Credit Card'


# ── PDF rendering ─────────────────────────────────────────────────────────────

def test_render_invoice_pdf_returns_pdf_bytes():
    invoice = {
        'invoice_number': 'INV-0001', 'customer_label': 'Acme',
        'invoice_date': '2026-01-01', 'due_date': '2026-02-01',
        'status': 'open', 'description': 'Widgets', 'amount': 500.0, 'balance': 200.0,
    }
    payments = [{'payment_date': '2026-01-15', 'payment_method': 'Check',
                 'amount': 300.0, 'reference': 'CHK-1'}]
    pdf = render_invoice_pdf(invoice, payments)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b'%PDF')


def test_render_invoice_pdf_handles_no_payments():
    invoice = {
        'invoice_number': 'INV-0002', 'customer_label': 'Acme',
        'invoice_date': '2026-01-01', 'due_date': '2026-02-01',
        'status': 'open', 'description': '', 'amount': 500.0, 'balance': 500.0,
    }
    pdf = render_invoice_pdf(invoice, [])
    assert pdf.startswith(b'%PDF')


def test_render_packing_slip_pdf_returns_pdf_bytes():
    shipment = {
        'ship_number': 'SMPL-SH-0001', 'so_number': 'SO-2026-0001',
        'ship_date': '2026-01-01', 'carrier': 'UPS', 'tracking_number': '1Z999',
    }
    items = [{'description': 'Widget', 'qty': 3}]
    pdf = render_packing_slip_pdf(shipment, items)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b'%PDF')
