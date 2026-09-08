"""Tests for receiving_core — standalone goods-in receipts, distinct from
the PO-item-level WMS Receive & Put-Away screen (see module docstring)."""

from unittest.mock import MagicMock, patch

import pytest

from manufacturing.receiving_core import (
    RECEIVING_STATUSES,
    ensure_receiving_tables, next_rcv_number, list_receipts, get_receipt,
    get_receipt_items, create_receipt, add_receipt_item, _recompute_status,
    receive_item, reject_receipt,
)


def _conn(fetchone_results=None, fetchall_results=None):
    """A MagicMock conn whose execute(...) returns one shared cursor mock;
    .fetchone()/.fetchall() replay the given results in call order (mirrors
    test_wms_core.py's _conn helper)."""
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


def test_group_by_statuses():
    assert set(RECEIVING_STATUSES) == {'pending', 'partial', 'received', 'rejected'}


def test_ensure_receiving_tables_creates_and_self_heals():
    conn = _conn()
    ensure_receiving_tables(conn)
    sqls = [c.args[0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS receiving (' in s for s in sqls)
    assert any('CREATE TABLE IF NOT EXISTS receiving_item (' in s for s in sqls)
    assert any('ADD COLUMN IF NOT EXISTS created_by' in s for s in sqls)
    assert any('ADD COLUMN IF NOT EXISTS bin_id' in s for s in sqls)


def test_next_rcv_number_starts_at_0001():
    conn = _conn(fetchall_results=[[]])
    assert next_rcv_number(conn).endswith('-0001')


def test_next_rcv_number_increments_from_max():
    import datetime
    yr = datetime.date.today().year
    conn = _conn(fetchall_results=[[
        {'rcv_number': f'RCV-{yr}-0003'}, {'rcv_number': f'RCV-{yr}-0001'},
    ]])
    assert next_rcv_number(conn) == f'RCV-{yr}-0004'


def test_create_receipt_requires_supplier():
    conn = _conn()
    with pytest.raises(ValueError):
        create_receipt(conn, None, '2026-01-01', '   ', '', '', '', 'eric')


@patch('manufacturing.receiving_core.next_rcv_number')
def test_create_receipt_inserts_pending(mock_num):
    mock_num.return_value = 'RCV-2026-0001'
    conn = _conn(fetchone_results=[{'id': 5}])
    receiving_id = create_receipt(
        conn, None, '2026-01-01', 'Steel Works Inc.', 'UPS', '1Z999', 'note', 'eric')
    assert receiving_id == 5
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO receiving' in sql
    assert "'pending'" in sql
    assert params == (
        'RCV-2026-0001', None, '2026-01-01', 'Steel Works Inc.', 'UPS',
        '1Z999', 'note', 'eric',
    )


def test_add_receipt_item_requires_description():
    conn = _conn()
    with pytest.raises(ValueError):
        add_receipt_item(conn, 1, '  ', None, 3)


@patch('manufacturing.receiving_core._recompute_status')
def test_add_receipt_item_inserts_and_recomputes(mock_recompute):
    conn = _conn(fetchone_results=[{'id': 9}])
    item_id = add_receipt_item(conn, 1, 'Steel rod', 42, 10)
    assert item_id == 9
    mock_recompute.assert_called_once_with(conn, 1)


# ── _recompute_status ────────────────────────────────────────────────────

def test_recompute_status_leaves_rejected_untouched():
    conn = _conn(fetchone_results=[{'status': 'rejected'}])
    _recompute_status(conn, 1)
    # only the initial status lookup should have run -- no UPDATE issued
    assert conn.execute.call_count == 1


def test_recompute_status_no_lines_is_pending():
    conn = _conn(
        fetchone_results=[{'status': 'pending'}],
        fetchall_results=[[]],
    )
    _recompute_status(conn, 1)
    sql, params = conn.execute.call_args[0]
    assert params == ('pending', 1)


def test_recompute_status_all_received_is_received():
    conn = _conn(
        fetchone_results=[{'status': 'pending'}],
        fetchall_results=[[
            {'qty_ordered': 5, 'qty_received': 5},
            {'qty_ordered': 2, 'qty_received': 2},
        ]],
    )
    _recompute_status(conn, 1)
    sql, params = conn.execute.call_args[0]
    assert params == ('received', 1)


def test_recompute_status_some_received_is_partial():
    conn = _conn(
        fetchone_results=[{'status': 'pending'}],
        fetchall_results=[[
            {'qty_ordered': 5, 'qty_received': 2},
            {'qty_ordered': 2, 'qty_received': 0},
        ]],
    )
    _recompute_status(conn, 1)
    sql, params = conn.execute.call_args[0]
    assert params == ('partial', 1)


def test_recompute_status_none_received_is_pending():
    conn = _conn(
        fetchone_results=[{'status': 'partial'}],
        fetchall_results=[[{'qty_ordered': 5, 'qty_received': 0}]],
    )
    _recompute_status(conn, 1)
    sql, params = conn.execute.call_args[0]
    assert params == ('pending', 1)


# ── receive_item ─────────────────────────────────────────────────────────

def test_receive_item_rejects_nonpositive_qty():
    conn = _conn()
    with pytest.raises(ValueError):
        receive_item(conn, 1, 0, None, 'eric')


def test_receive_item_rejects_missing_line():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        receive_item(conn, 999, 5, None, 'eric')


@patch('manufacturing.receiving_core._recompute_status')
@patch('manufacturing.receiving_core.receive_into_bin')
def test_receive_item_free_text_line_skips_bin_credit(mock_receive_into_bin, mock_recompute):
    # no product_id -- can only track qty_received, never touches inventory/bins
    conn = _conn(fetchone_results=[
        {'id': 1, 'receiving_id': 7, 'product_id': None,
         'qty_ordered': 10, 'qty_received': 2},
    ])
    delta = receive_item(conn, 1, 3, bin_id=4, created_by='eric')
    assert delta == 3
    mock_receive_into_bin.assert_not_called()
    mock_recompute.assert_called_once_with(conn, 7)


@patch('manufacturing.receiving_core._recompute_status')
@patch('manufacturing.receiving_core.receive_into_bin')
def test_receive_item_product_linked_credits_bin(mock_receive_into_bin, mock_recompute):
    conn = _conn(fetchone_results=[
        {'id': 1, 'receiving_id': 7, 'product_id': 42,
         'qty_ordered': 10, 'qty_received': 2},
    ])
    delta = receive_item(conn, 1, 5, bin_id=9, created_by='eric')
    assert delta == 5
    mock_receive_into_bin.assert_called_once()
    args = mock_receive_into_bin.call_args[0]
    assert args[:4] == (conn, 42, 5, 9)


@patch('manufacturing.receiving_core._recompute_status')
@patch('manufacturing.receiving_core.receive_into_bin')
def test_receive_item_product_linked_without_bin_skips_credit(mock_receive_into_bin, mock_recompute):
    # a product-linked line received with no bin chosen can't be put away
    conn = _conn(fetchone_results=[
        {'id': 1, 'receiving_id': 7, 'product_id': 42,
         'qty_ordered': 10, 'qty_received': 2},
    ])
    receive_item(conn, 1, 5, bin_id=None, created_by='eric')
    mock_receive_into_bin.assert_not_called()


def test_receive_item_clamps_to_qty_ordered():
    conn = _conn(fetchone_results=[
        {'id': 1, 'receiving_id': 7, 'product_id': None,
         'qty_ordered': 10, 'qty_received': 8},
    ])
    with patch('manufacturing.receiving_core._recompute_status'):
        delta = receive_item(conn, 1, 100, bin_id=None, created_by='eric')
    assert delta == 2  # clamped: 8 + 100 -> min(108, 10) = 10, delta = 2


def test_receive_item_already_complete_returns_zero_and_no_update():
    conn = _conn(fetchone_results=[
        {'id': 1, 'receiving_id': 7, 'product_id': None,
         'qty_ordered': 10, 'qty_received': 10},
    ])
    delta = receive_item(conn, 1, 5, bin_id=None, created_by='eric')
    assert delta == 0
    # only the SELECT should have run -- no UPDATE, no status recompute
    assert conn.execute.call_count == 1


def test_reject_receipt_sets_status():
    conn = _conn()
    reject_receipt(conn, 1, 'Damaged in transit')
    sql, params = conn.execute.call_args[0]
    assert "status = 'rejected'" in sql
    assert params == ('Damaged in transit', 'Damaged in transit', 1)


# ── list/get helpers ─────────────────────────────────────────────────────

def test_list_receipts_filters_by_status_and_search():
    conn = _conn(fetchall_results=[[]])
    list_receipts(conn, status='pending', search='steel')
    sql, params = conn.execute.call_args[0]
    assert 'status = %s' in sql
    assert 'ILIKE' in sql
    assert params[0] == 'pending'
    assert params[1:] == ['%steel%', '%steel%', '%steel%']


def test_get_receipt_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_receipt(conn, 999) is None


def test_get_receipt_items_joins_product_and_bin():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'description': 'Steel rod', 'product_id': 42, 'qty_ordered': 10,
         'qty_received': 5, 'bin_id': 9, 'product_name': 'Rod', 'bin_code': 'A1-01'},
    ]])
    items = get_receipt_items(conn, 1)
    assert items[0]['product_name'] == 'Rod'
    assert items[0]['bin_code'] == 'A1-01'
