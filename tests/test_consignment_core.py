"""Tests for consignment_core — Consignment (Vendor-Owned) Inventory.

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_blanket_po_core.py). Write-path
tests patch the same-module helper ``get_agreement`` and the two
cross-module functions this module calls by name
(``inventory_core.record_transaction``, ``accounting_core.create_ap_invoice``)
to isolate validation logic from the read-path query chain.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from manufacturing.consignment_core import (
    ensure_consignment_tables, next_agreement_number, _next_usage_invoice_number,
    _sync_status,
    list_agreements, get_agreement, list_receipts, list_usages,
    create_agreement, receive_stock, record_usage, cancel_agreement,
)

YEAR = datetime.now().year


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


# ── setup ────────────────────────────────────────────────────────────────

def test_ensure_consignment_tables_creates_all_three():
    conn = MagicMock()
    ensure_consignment_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS consignment_agreement (' in c for c in calls)
    assert any('consignment_receipt' in c for c in calls)
    assert any('consignment_usage' in c for c in calls)


# ── numbering ────────────────────────────────────────────────────────────

def test_next_agreement_number_first_of_year():
    conn = _conn(fetchall_results=[[]])
    assert next_agreement_number(conn) == f"CONSIGN-{YEAR}-0001"


def test_next_agreement_number_increments_from_max_suffix():
    conn = _conn(fetchall_results=[[
        {'agreement_number': f'CONSIGN-{YEAR}-0001'},
        {'agreement_number': f'CONSIGN-{YEAR}-0004'},
    ]])
    assert next_agreement_number(conn) == f"CONSIGN-{YEAR}-0005"


def test_next_usage_invoice_number_first_for_agreement():
    conn = _conn(fetchall_results=[[]])
    result = _next_usage_invoice_number(conn, f'CONSIGN-{YEAR}-0001')
    assert result == f"CONSIGN-{YEAR}-0001-U0001"


def test_next_usage_invoice_number_gap_safe_not_count_based():
    """Regression test for the count-based collision bug: max-suffix+1 over
    the real ap_invoice rows, not len(list_usages(...)) + 1 — two usage
    records created close together must never compute the same number."""
    conn = _conn(fetchall_results=[[
        {'invoice_number': f'CONSIGN-{YEAR}-0001-U0001'},
        {'invoice_number': f'CONSIGN-{YEAR}-0001-U0003'},  # a gap at U0002
    ]])
    result = _next_usage_invoice_number(conn, f'CONSIGN-{YEAR}-0001')
    assert result == f"CONSIGN-{YEAR}-0001-U0004"
    select_sql = conn.execute.call_args_list[0][0][0]
    assert 'FROM ap_invoice' in select_sql


# ── create_agreement ─────────────────────────────────────────────────────

def test_create_agreement_raises_without_supplier():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_agreement(conn, None, 5, 12.0, '2026-01-01', '2026-12-31', '', 'eric')
    assert conn.execute.call_count == 0


def test_create_agreement_raises_for_nonpositive_unit_cost():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_agreement(conn, 1, 5, 0, '2026-01-01', '2026-12-31', '', 'eric')
    assert conn.execute.call_count == 0


def test_create_agreement_raises_without_product():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_agreement(conn, 1, None, 5.0, '2026-01-01', '2026-12-31', '', 'eric')
    assert conn.execute.call_count == 0


def test_create_agreement_raises_bad_date_range():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_agreement(conn, 1, 5, 5.0, '2026-12-31', '2026-01-01', '', 'eric')
    assert conn.execute.call_count == 0


def test_create_agreement_raises_when_product_missing():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        create_agreement(conn, 1, 999, 5.0, '2026-01-01', '2026-12-31', '', 'eric')


def test_create_agreement_inserts_and_returns_id():
    conn = _conn(fetchall_results=[[]], fetchone_results=[{'id': 5}, {'id': 10}])
    agreement_id = create_agreement(
        conn, 1, 5, 12.50, '2026-01-01', '2026-12-31', 'annual VMI', 'eric')
    assert agreement_id == 10
    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO consignment_agreement' in insert_sql
    assert insert_params[0] == f"CONSIGN-{YEAR}-0001"
    assert insert_params[1] == 1
    assert insert_params[2] == 5
    assert insert_params[3] == 12.50
    assert insert_params[6] == 'active'


# ── _sync_status ─────────────────────────────────────────────────────────

def test_sync_status_expires_when_past_end_date():
    conn = _conn(fetchone_results=[{'status': 'active', 'end_date': '2020-01-01'}])
    assert _sync_status(conn, 1) == 'expired'
    update_calls = [c for c in conn.execute.call_args_list
                    if 'UPDATE consignment_agreement SET status' in c[0][0]]
    assert len(update_calls) == 1
    assert update_calls[0][0][1] == ('expired', 1)


def test_sync_status_noop_when_still_valid():
    conn = _conn(fetchone_results=[{'status': 'active', 'end_date': '2099-01-01'}])
    assert _sync_status(conn, 1) == 'active'
    update_calls = [c for c in conn.execute.call_args_list
                    if 'UPDATE consignment_agreement SET status' in c[0][0]]
    assert len(update_calls) == 0


def test_sync_status_short_circuits_for_cancelled():
    conn = _conn(fetchone_results=[{'status': 'cancelled', 'end_date': ''}])
    assert _sync_status(conn, 1) == 'cancelled'
    assert conn.execute.call_count == 1


def test_sync_status_returns_empty_for_missing_agreement():
    conn = _conn(fetchone_results=[None])
    assert _sync_status(conn, 999) == ''


# ── read / balances ──────────────────────────────────────────────────────

def test_get_agreement_computes_on_hand_balance():
    conn = _conn(fetchone_results=[
        {'status': 'active', 'end_date': '2099-01-01'},
        {'id': 1, 'agreement_number': f'CONSIGN-{YEAR}-0001', 'supplier_id': 2,
         'product_id': 5, 'unit_cost': 10.0, 'start_date': '2026-01-01',
         'end_date': '2099-01-01', 'status': 'active', 'notes': '',
         'created_by': 'eric', 'created_at': 'now', 'supplier_name': 'Acme Corp',
         'product_name': 'Widget'},
        {'qty': 100.0},
        {'qty': 30.0, 'value': 300.0},
    ])
    agreement = get_agreement(conn, 1)
    assert agreement['received_qty'] == 100.0
    assert agreement['used_qty'] == 30.0
    assert agreement['on_hand_qty'] == 70.0
    assert agreement['on_hand_value'] == 700.0
    assert agreement['used_value'] == 300.0


def test_get_agreement_returns_none_when_missing():
    conn = _conn(fetchone_results=[None, None])
    assert get_agreement(conn, 999) is None


def test_list_agreements_filters_by_synced_status():
    with patch('manufacturing.consignment_core._sync_status',
               side_effect=lambda conn, aid: 'active' if aid == 1 else 'expired'), \
         patch('manufacturing.consignment_core._with_balances',
               side_effect=lambda conn, d: d):
        conn = _conn(fetchall_results=[[{'id': 1}, {'id': 2}]])
        result = list_agreements(conn, status='active')
        assert [r['id'] for r in result] == [1]


def test_list_receipts_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'qty': 50.0}]])
    assert list_receipts(conn, 5) == [{'id': 1, 'qty': 50.0}]


def test_list_usages_returns_rows_with_total_cost():
    conn = _conn(fetchall_results=[[{'id': 1, 'qty': 10.0, 'unit_cost': 8.0}]])
    result = list_usages(conn, 5)
    assert result == [{'id': 1, 'qty': 10.0, 'unit_cost': 8.0, 'total_cost': 80.0}]


# ── receive_stock ────────────────────────────────────────────────────────

def test_receive_stock_raises_if_agreement_not_found():
    with patch('manufacturing.consignment_core.get_agreement', return_value=None):
        conn = MagicMock()
        with pytest.raises(ValueError):
            receive_stock(conn, 1, 10, '', 'eric')


def test_receive_stock_raises_if_cancelled():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'cancelled'}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            receive_stock(conn, 1, 10, '', 'eric')


def test_receive_stock_raises_for_nonpositive_qty():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'active'}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            receive_stock(conn, 1, 0, '', 'eric')


def test_receive_stock_inserts_without_touching_inventory():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'active'}), \
         patch('manufacturing.consignment_core.record_transaction') as mock_txn:
        conn = _conn(fetchone_results=[{'id': 7}])
        receipt_id = receive_stock(conn, 1, 50, 'PO-VMI-1', 'eric')
        assert receipt_id == 7
        insert_sql = conn.execute.call_args_list[-1][0][0]
        assert 'INSERT INTO consignment_receipt' in insert_sql
        mock_txn.assert_not_called()


# ── record_usage ─────────────────────────────────────────────────────────

def test_record_usage_raises_if_agreement_not_found():
    with patch('manufacturing.consignment_core.get_agreement', return_value=None):
        conn = MagicMock()
        with pytest.raises(ValueError):
            record_usage(conn, 1, 10, '', 'eric')


def test_record_usage_raises_if_cancelled():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'cancelled', 'on_hand_qty': 100.0}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            record_usage(conn, 1, 10, '', 'eric')


def test_record_usage_raises_when_exceeding_on_hand_balance():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'active', 'on_hand_qty': 5.0, 'supplier_id': 2}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            record_usage(conn, 1, 10, '', 'eric')


def test_record_usage_raises_without_supplier_on_agreement():
    """Defense in depth: an agreement created before create_agreement
    required a supplier (or one otherwise missing its supplier_id) must
    not be allowed to bill a null vendor."""
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'active', 'on_hand_qty': 100.0, 'supplier_id': None}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            record_usage(conn, 1, 10, '', 'eric')


def test_record_usage_happy_path():
    agreement = {
        'status': 'active', 'on_hand_qty': 100.0, 'unit_cost': 8.0,
        'product_id': 5, 'supplier_id': 2, 'product_name': 'Widget',
        'agreement_number': f'CONSIGN-{YEAR}-0001',
    }
    with patch('manufacturing.consignment_core.get_agreement', return_value=agreement), \
         patch('manufacturing.consignment_core.record_transaction') as mock_txn, \
         patch('manufacturing.consignment_core.create_ap_invoice') as mock_ap:
        mock_txn.return_value = 60.0
        mock_ap.return_value = 42

        conn = _conn(fetchone_results=[{'id': 99}], fetchall_results=[[]])
        result = record_usage(conn, 1, 10, 'WO-500', 'eric')

        mock_txn.assert_called_once_with(
            conn, 5, 'receive', 10,
            reference='WO-500',
            notes=f"Consignment usage — CONSIGN-{YEAR}-0001",
            created_by='eric',
        )
        mock_ap.assert_called_once()
        ap_kwargs = mock_ap.call_args
        assert ap_kwargs.kwargs['vendor_id'] == 2
        assert ap_kwargs.kwargs['amount'] == 80.0

        assert result == {
            'usage_id': 99, 'new_product_amount': 60.0,
            'ap_invoice_id': 42, 'total_cost': 80.0,
        }
        insert_sql, insert_params = conn.execute.call_args_list[-1][0]
        assert 'INSERT INTO consignment_usage' in insert_sql
        assert insert_params[0] == 1
        assert insert_params[1] == 10
        assert insert_params[2] == 8.0
        assert insert_params[3] == 42


# ── cancel_agreement ─────────────────────────────────────────────────────

def test_cancel_agreement_success():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'active'}):
        conn = MagicMock()
        cancel_agreement(conn, 1)
        update_sql, update_params = conn.execute.call_args_list[-1][0]
        assert 'UPDATE consignment_agreement SET status' in update_sql
        assert update_params == ('cancelled', 1)


def test_cancel_agreement_raises_if_not_active():
    with patch('manufacturing.consignment_core.get_agreement',
               return_value={'status': 'expired'}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            cancel_agreement(conn, 1)


def test_cancel_agreement_raises_if_missing():
    with patch('manufacturing.consignment_core.get_agreement', return_value=None):
        conn = MagicMock()
        with pytest.raises(ValueError):
            cancel_agreement(conn, 1)
