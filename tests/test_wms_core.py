"""Tests for wms_core — Warehouse Management System (P3-B).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_production_core.py /
test_capacity_planning_core.py), plus unittest.mock.patch for the
cross-module functions this module re-imports by name.
"""

from unittest.mock import MagicMock, patch

import pytest

from manufacturing.wms_core import (
    create_bin, get_or_create_unassigned_bin, is_unassigned_bin,
    _adjust_bin_stock, _build_full_code, _next_sequence,
    suggest_putaway_bin, receive_and_putaway, credit_unassigned_receipt,
    generate_pick_list, _resequence_pick_list, record_pick,
    add_carton_item, mark_pick_list_packed, confirm_shipment,
    create_transfer, add_transfer_line, remove_transfer_line,
    ship_transfer, receive_transfer_line, cancel_transfer,
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


# ── bin master ──────────────────────────────────────────────────────────────

def test_build_full_code_joins_nonempty_parts():
    assert _build_full_code('Z1', 'A1', 'R1', 'S1', 'B03') == 'Z1-A1-R1-S1-B03'
    assert _build_full_code('Z1', '', '', '', 'B03') == 'Z1-B03'


def test_create_bin_builds_full_code_and_returns_id():
    conn = _conn(fetchone_results=[{'code': 'Z1'}, {'id': 7}])
    bin_id = create_bin(conn, zone_id=1, aisle='A1', rack='R1', shelf='S1', bin_code='B03')
    assert bin_id == 7
    insert_sql, insert_params = conn.execute.call_args_list[1][0]
    assert 'INSERT INTO wms_bin' in insert_sql
    assert insert_params[-1] == 'Z1-A1-R1-S1-B03'


def test_create_bin_raises_for_missing_zone():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        create_bin(conn, zone_id=999, aisle='', rack='', shelf='', bin_code='B01')


def test_get_or_create_unassigned_bin_creates_once_then_reuses():
    conn = _conn(fetchone_results=[
        None,               # no existing unassigned bin
        {'id': 1},          # default warehouse already exists
        None,               # no existing unassigned zone
        {'id': 2},          # new zone id
        {'code': 'UNASSIGNED'},  # zone code lookup inside create_bin
        {'id': 3},          # new bin id
    ])
    bin_id = get_or_create_unassigned_bin(conn)
    assert bin_id == 3

    conn2 = _conn(fetchone_results=[{'id': 3}])
    bin_id_again = get_or_create_unassigned_bin(conn2)
    assert bin_id_again == 3
    assert conn2.execute.call_count == 1


def test_is_unassigned_bin_true_and_false():
    conn = _conn(fetchone_results=[{'full_code': 'UNASSIGNED-UNASSIGNED'}])
    assert is_unassigned_bin(conn, 3) is True

    conn2 = _conn(fetchone_results=[{'full_code': 'Z1-B03'}])
    assert is_unassigned_bin(conn2, 5) is False


def test_adjust_bin_stock_upserts_on_increase():
    conn = _conn(fetchone_results=[None])  # no existing row
    new_qty = _adjust_bin_stock(conn, bin_id=1, product_id=2, delta=5)
    assert new_qty == 5
    insert_sql = conn.execute.call_args_list[1][0][0]
    assert 'INSERT INTO wms_bin_stock' in insert_sql


def test_adjust_bin_stock_raises_on_over_decrement():
    conn = _conn(fetchone_results=[{'qty': 2}])
    with pytest.raises(ValueError):
        _adjust_bin_stock(conn, bin_id=1, product_id=2, delta=-5)


# ── put-away rules ───────────────────────────────────────────────────────────

@patch('manufacturing.wms_core.get_bin')
@patch('manufacturing.wms_core.get_or_create_unassigned_bin')
@patch('manufacturing.wms_core._least_full_active_bin_in_zone')
@patch('manufacturing.wms_core.list_putaway_rules')
@patch('manufacturing.wms_core.compute_abc_classes')
def test_suggest_putaway_bin_first_match_wins(
    mock_abc, mock_rules, mock_least_full, mock_unassigned, mock_get_bin,
):
    conn = _conn(fetchone_results=[{'category': 'raw material'}])
    mock_abc.return_value = {42: 'B'}
    mock_rules.return_value = [
        {'id': 1, 'match_type': 'category', 'match_value': 'raw material', 'zone_id': 10, 'priority': 5},
        {'id': 2, 'match_type': 'abc', 'match_value': 'B', 'zone_id': 20, 'priority': 1},
    ]
    mock_least_full.return_value = {'id': 100, 'full_code': 'ZONE10-B01'}

    result = suggest_putaway_bin(conn, product_id=42)

    assert result == {'bin_id': 100, 'full_code': 'ZONE10-B01', 'rule_id': 1, 'reason': 'rule match'}
    mock_unassigned.assert_not_called()


@patch('manufacturing.wms_core.get_bin')
@patch('manufacturing.wms_core.get_or_create_unassigned_bin')
@patch('manufacturing.wms_core.list_putaway_rules')
@patch('manufacturing.wms_core.compute_abc_classes')
def test_suggest_putaway_bin_falls_back_to_unassigned(
    mock_abc, mock_rules, mock_unassigned, mock_get_bin,
):
    conn = _conn(fetchone_results=[{'category': ''}])
    mock_abc.return_value = {}
    mock_rules.return_value = []
    mock_unassigned.return_value = 9
    mock_get_bin.return_value = {'id': 9, 'full_code': 'UNASSIGNED-UNASSIGNED'}

    result = suggest_putaway_bin(conn, product_id=42)

    assert result['bin_id'] == 9
    assert result['reason'] == 'no rule matched'
    assert result['rule_id'] is None


# ── receiving put-away ───────────────────────────────────────────────────────

@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.record_transaction')
@patch('manufacturing.wms_core.receive_po_item')
def test_receive_and_putaway_happy_path(mock_receive, mock_record_txn, mock_adjust):
    conn = _conn(fetchone_results=[{'qty_ordered': 10, 'qty_received': 2}])
    mock_receive.return_value = 1
    mock_record_txn.return_value = 42.0
    mock_adjust.return_value = 5.0

    result = receive_and_putaway(
        conn, po_item_id=1, po_id=1, product_id=7, qty=5, bin_id=3, created_by='eric')

    mock_receive.assert_called_once_with(conn, 1, 7, po_id=1)
    mock_record_txn.assert_called_once()
    assert mock_record_txn.call_args[0][2] == 'receive'
    assert mock_record_txn.call_args[0][3] == 5
    mock_adjust.assert_called_once_with(conn, 3, 7, 5)
    assert result == {'received_qty': 5, 'new_amount': 42.0, 'bin_qty': 5.0}


@patch('manufacturing.wms_core.receive_po_item')
def test_receive_and_putaway_raises_when_item_not_updated(mock_receive):
    conn = _conn(fetchone_results=[{'qty_ordered': 10, 'qty_received': 0}])
    mock_receive.return_value = 0
    with pytest.raises(ValueError):
        receive_and_putaway(conn, po_item_id=1, po_id=1, product_id=7, qty=5,
                            bin_id=3, created_by='eric')


def test_receive_and_putaway_raises_for_nonpositive_qty():
    conn = _conn()
    with pytest.raises(ValueError):
        receive_and_putaway(conn, po_item_id=1, po_id=1, product_id=7, qty=0,
                            bin_id=3, created_by='eric')


@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.get_or_create_unassigned_bin')
@patch('manufacturing.wms_core.record_transaction')
def test_credit_unassigned_receipt_noops_on_nonpositive_delta(
    mock_record_txn, mock_unassigned, mock_adjust,
):
    conn = _conn()
    result = credit_unassigned_receipt(conn, product_id=1, delta=0,
                                       reference='x', created_by='eric')
    assert result is None
    mock_record_txn.assert_not_called()
    mock_adjust.assert_not_called()


@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.get_or_create_unassigned_bin')
@patch('manufacturing.wms_core.record_transaction')
def test_credit_unassigned_receipt_credits_positive_delta(
    mock_record_txn, mock_unassigned, mock_adjust,
):
    conn = _conn()
    mock_unassigned.return_value = 9
    mock_adjust.return_value = 3.0
    result = credit_unassigned_receipt(conn, product_id=1, delta=3,
                                       reference='PO item 1', created_by='eric')
    mock_record_txn.assert_called_once_with(
        conn, 1, 'receive', 3, reference='PO item 1', notes='PO receipt',
        created_by='eric')
    mock_adjust.assert_called_once_with(conn, 9, 1, 3)
    assert result == 3.0


# ── pick list generation ─────────────────────────────────────────────────────

@patch('manufacturing.wms_core._resequence_pick_list')
@patch('manufacturing.wms_core._next_sequence')
@patch('manufacturing.wms_core.get_product_bin_stock')
@patch('manufacturing.wms_core.get_so')
def test_generate_pick_list_raises_for_non_confirmed_so(mock_get_so, *_):
    mock_get_so.return_value = {'id': 1, 'status': 'draft'}
    conn = _conn()
    with pytest.raises(ValueError):
        generate_pick_list(conn, so_id=1, created_by='eric')


@patch('manufacturing.wms_core._resequence_pick_list')
@patch('manufacturing.wms_core.get_so')
def test_generate_pick_list_raises_when_active_pick_list_exists(mock_get_so, _reseq):
    mock_get_so.return_value = {'id': 1, 'status': 'confirmed'}
    conn = _conn(fetchone_results=[{'id': 55}])  # existing active pick list found
    with pytest.raises(ValueError):
        generate_pick_list(conn, so_id=1, created_by='eric')


@patch('manufacturing.wms_core._resequence_pick_list')
@patch('manufacturing.wms_core._next_sequence')
@patch('manufacturing.wms_core.get_product_bin_stock')
@patch('manufacturing.wms_core.get_bin')
@patch('manufacturing.wms_core.get_or_create_unassigned_bin')
@patch('manufacturing.wms_core.get_so')
def test_generate_pick_list_assigns_tracked_bin_when_available(
    mock_get_so, mock_unassigned, mock_get_bin, mock_product_bins,
    mock_next_seq, _reseq,
):
    mock_get_so.return_value = {'id': 1, 'status': 'confirmed'}
    mock_next_seq.return_value = 'PICK-2026-0001'
    mock_product_bins.return_value = [{'bin_id': 3, 'zone_id': 10, 'qty': 20}]
    conn = _conn(
        fetchone_results=[
            None,                       # no active pick list
            {'id': 999},                # INSERT wms_pick_list RETURNING id
            {'id': 101},                # INSERT wms_pick_list_line RETURNING id
        ],
        fetchall_results=[
            [{'id': 1, 'product_id': 5, 'description': 'Widget', 'qty': 10}],  # so_item rows
        ],
    )
    pick_list_id = generate_pick_list(conn, so_id=1, created_by='eric')
    assert pick_list_id == 999
    mock_unassigned.assert_not_called()
    insert_line_sql, insert_line_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO wms_pick_list_line' in insert_line_sql
    assert insert_line_params[5] == 3  # bin_id
    assert insert_line_params[6] == 10  # zone_id


@patch('manufacturing.wms_core._resequence_pick_list')
@patch('manufacturing.wms_core._next_sequence')
@patch('manufacturing.wms_core.get_product_bin_stock')
@patch('manufacturing.wms_core.get_bin')
@patch('manufacturing.wms_core.get_or_create_unassigned_bin')
@patch('manufacturing.wms_core.get_so')
def test_generate_pick_list_falls_back_to_unassigned_bin(
    mock_get_so, mock_unassigned, mock_get_bin, mock_product_bins,
    mock_next_seq, _reseq,
):
    mock_get_so.return_value = {'id': 1, 'status': 'confirmed'}
    mock_next_seq.return_value = 'PICK-2026-0001'
    mock_product_bins.return_value = []  # nothing tracked for this product
    mock_unassigned.return_value = 9
    mock_get_bin.return_value = {'id': 9, 'zone_id': 999, 'full_code': 'UNASSIGNED-UNASSIGNED'}
    conn = _conn(
        fetchone_results=[None, {'id': 999}, {'id': 101}],
        fetchall_results=[[{'id': 1, 'product_id': 5, 'description': 'Widget', 'qty': 10}]],
    )
    generate_pick_list(conn, so_id=1, created_by='eric')
    insert_line_params = conn.execute.call_args_list[-1][0][1]
    assert insert_line_params[5] == 9
    assert insert_line_params[6] == 999


def test_resequence_pick_list_orders_by_zone_then_bin_code():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'zone_seq': 2, 'full_code': 'B-01'},
        {'id': 2, 'zone_seq': 1, 'full_code': 'A-02'},
        {'id': 3, 'zone_seq': 1, 'full_code': 'A-01'},
    ]])
    _resequence_pick_list(conn, pick_list_id=5)
    update_calls = [c for c in conn.execute.call_args_list
                   if 'UPDATE wms_pick_list_line SET pick_sequence' in c[0][0]]
    order = [c[0][1][1] for c in update_calls]  # line id is the 2nd bound param
    assert order == [3, 2, 1]


# ── picking ──────────────────────────────────────────────────────────────────

@patch('manufacturing.wms_core.is_unassigned_bin')
@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.record_transaction')
def test_record_pick_marks_picked_and_advances_pick_list(
    mock_record_txn, mock_adjust, mock_is_unassigned,
):
    mock_is_unassigned.return_value = False
    conn = _conn(fetchone_results=[
        {'id': 1, 'pick_list_id': 5, 'product_id': 7, 'qty_ordered': 10,
         'bin_id': 3, 'pick_number': 'PICK-2026-0001'},
        {'n': 0},  # no remaining pending lines
    ])
    status = record_pick(conn, line_id=1, qty_picked=10, created_by='eric')
    assert status == 'picked'
    mock_record_txn.assert_called_once()
    assert mock_record_txn.call_args[0][2] == 'issue'
    mock_adjust.assert_called_once_with(conn, 3, 7, -10)
    update_pl_calls = [c for c in conn.execute.call_args_list
                      if 'wms_pick_list SET status' in c[0][0]]
    assert len(update_pl_calls) == 1


@patch('manufacturing.wms_core.is_unassigned_bin')
@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.record_transaction')
def test_record_pick_marks_short_when_under_ordered_qty(
    mock_record_txn, mock_adjust, mock_is_unassigned,
):
    mock_is_unassigned.return_value = False
    conn = _conn(fetchone_results=[
        {'id': 1, 'pick_list_id': 5, 'product_id': 7, 'qty_ordered': 10,
         'bin_id': 3, 'pick_number': 'PICK-2026-0001'},
        {'n': 2},  # other lines still pending
    ])
    status = record_pick(conn, line_id=1, qty_picked=4, created_by='eric')
    assert status == 'short'
    update_pl_calls = [c for c in conn.execute.call_args_list
                      if 'wms_pick_list SET status' in c[0][0]]
    assert len(update_pl_calls) == 0


@patch('manufacturing.wms_core.is_unassigned_bin')
@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.record_transaction')
def test_record_pick_skips_bin_adjustment_for_unassigned_sentinel(
    mock_record_txn, mock_adjust, mock_is_unassigned,
):
    mock_is_unassigned.return_value = True
    conn = _conn(fetchone_results=[
        {'id': 1, 'pick_list_id': 5, 'product_id': 7, 'qty_ordered': 10,
         'bin_id': 9, 'pick_number': 'PICK-2026-0001'},
        {'n': 0},
    ])
    record_pick(conn, line_id=1, qty_picked=10, created_by='eric')
    mock_adjust.assert_not_called()


# ── pack station ─────────────────────────────────────────────────────────────

def test_add_carton_item_rejects_over_allocation():
    conn = _conn(fetchone_results=[
        {'product_id': 1, 'qty_picked': 5},  # line lookup
        {'packed': 3},                       # already packed
    ])
    with pytest.raises(ValueError):
        add_carton_item(conn, carton_id=1, pick_list_line_id=1, qty=3)


def test_mark_pick_list_packed_raises_if_not_fully_packed():
    conn = _conn(fetchone_results=[
        {'n': 0},       # no open cartons
        {'packed': 3},  # only 3 of 5 packed
    ], fetchall_results=[
        [{'id': 1, 'qty_picked': 5}],  # picked lines
    ])
    with pytest.raises(ValueError):
        mark_pick_list_packed(conn, pick_list_id=5)


# ── ship confirmation ────────────────────────────────────────────────────────

@patch('manufacturing.wms_core.set_so_status')
@patch('manufacturing.wms_core.can_transition')
@patch('manufacturing.wms_core.get_so')
@patch('manufacturing.wms_core.add_shipment_item')
@patch('manufacturing.wms_core.create_shipment')
@patch('manufacturing.wms_core.get_pick_list_lines')
@patch('manufacturing.wms_core.get_pick_list')
def test_confirm_shipment_happy_path(
    mock_get_pl, mock_get_lines, mock_create_shipment, mock_add_item,
    mock_get_so, mock_can_transition, mock_set_status,
):
    mock_get_pl.return_value = {
        'id': 5, 'status': 'packed', 'so_id': 9, 'pick_number': 'PICK-2026-0001',
    }
    mock_get_lines.return_value = [
        {'status': 'picked', 'description': 'Widget', 'product_name': 'Widget',
         'product_id': 1, 'qty_picked': 10},
    ]
    mock_create_shipment.return_value = 55
    mock_get_so.return_value = {'status': 'confirmed'}
    mock_can_transition.return_value = True
    conn = _conn()

    shipment_id = confirm_shipment(conn, pick_list_id=5, carrier='UPS',
                                   tracking_number='1Z', ship_date='2026-07-06',
                                   created_by='eric')

    assert shipment_id == 55
    mock_add_item.assert_called_once()
    mock_set_status.assert_called_once_with(conn, 9, 'shipped')


@patch('manufacturing.wms_core.get_pick_list')
def test_confirm_shipment_raises_when_not_packed(mock_get_pl):
    mock_get_pl.return_value = {'id': 5, 'status': 'picked'}
    conn = _conn()
    with pytest.raises(ValueError):
        confirm_shipment(conn, pick_list_id=5, carrier='UPS', tracking_number='1Z',
                         ship_date='2026-07-06', created_by='eric')


@patch('manufacturing.wms_core.set_so_status')
@patch('manufacturing.wms_core.can_transition')
@patch('manufacturing.wms_core.get_so')
@patch('manufacturing.wms_core.add_shipment_item')
@patch('manufacturing.wms_core.create_shipment')
@patch('manufacturing.wms_core.get_pick_list_lines')
@patch('manufacturing.wms_core.get_pick_list')
def test_confirm_shipment_skips_so_transition_when_illegal(
    mock_get_pl, mock_get_lines, mock_create_shipment, mock_add_item,
    mock_get_so, mock_can_transition, mock_set_status,
):
    mock_get_pl.return_value = {
        'id': 5, 'status': 'packed', 'so_id': 9, 'pick_number': 'PICK-2026-0001',
    }
    mock_get_lines.return_value = []
    mock_create_shipment.return_value = 55
    mock_get_so.return_value = {'status': 'shipped'}
    mock_can_transition.return_value = False
    conn = _conn()

    confirm_shipment(conn, pick_list_id=5, carrier='UPS', tracking_number='1Z',
                     ship_date='2026-07-06', created_by='eric')

    mock_set_status.assert_not_called()


# ── gap-safe sequence numbering ─────────────────────────────────────────────

def test_next_sequence_pick_prefix():
    conn = _conn(fetchall_results=[[{'num': 'PICK-2026-0003'}]])
    with patch('manufacturing.wms_core.date') as mock_date:
        mock_date.today.return_value.year = 2026
        result = _next_sequence(conn, 'PICK-')
    assert result == 'PICK-2026-0004'


def test_next_sequence_carton_prefix():
    conn = _conn(fetchall_results=[[{'num': 'CTN-2026-0009'}]])
    with patch('manufacturing.wms_core.date') as mock_date:
        mock_date.today.return_value.year = 2026
        result = _next_sequence(conn, 'CTN-')
    assert result == 'CTN-2026-0010'


def test_next_sequence_transfer_prefix():
    conn = _conn(fetchall_results=[[{'num': 'TRF-2026-0002'}]])
    with patch('manufacturing.wms_core.date') as mock_date:
        mock_date.today.return_value.year = 2026
        result = _next_sequence(conn, 'TRF-')
    assert result == 'TRF-2026-0003'


# ── inter-warehouse transfers ────────────────────────────────────────────────

def test_create_transfer_raises_for_same_warehouse():
    conn = _conn()
    with pytest.raises(ValueError):
        create_transfer(conn, from_warehouse_id=1, to_warehouse_id=1, created_by='eric')


def test_create_transfer_raises_for_missing_warehouse():
    conn = _conn(fetchone_results=[None])  # from_warehouse_id lookup fails
    with pytest.raises(ValueError):
        create_transfer(conn, from_warehouse_id=1, to_warehouse_id=2, created_by='eric')


@patch('manufacturing.wms_core._next_sequence')
def test_create_transfer_happy_path(mock_seq):
    mock_seq.return_value = 'TRF-2026-0001'
    conn = _conn(fetchone_results=[
        {'id': 1},   # from_warehouse exists
        {'id': 2},   # to_warehouse exists
        {'id': 55},  # inserted transfer id
    ])
    transfer_id = create_transfer(conn, from_warehouse_id=1, to_warehouse_id=2, created_by='eric')
    assert transfer_id == 55
    insert_sql = conn.execute.call_args_list[-1][0][0]
    assert 'INSERT INTO wms_transfer' in insert_sql


def test_add_transfer_line_raises_for_nonpositive_qty():
    conn = _conn()
    with pytest.raises(ValueError):
        add_transfer_line(conn, transfer_id=1, product_id=1, from_bin_id=1, qty=0)


def test_add_transfer_line_raises_when_transfer_not_found():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        add_transfer_line(conn, transfer_id=1, product_id=1, from_bin_id=1, qty=5)


def test_add_transfer_line_raises_when_transfer_not_draft():
    conn = _conn(fetchone_results=[{'status': 'in_transit', 'from_warehouse_id': 1}])
    with pytest.raises(ValueError):
        add_transfer_line(conn, transfer_id=1, product_id=1, from_bin_id=1, qty=5)


def test_add_transfer_line_raises_when_bin_in_wrong_warehouse():
    conn = _conn(fetchone_results=[
        {'status': 'draft', 'from_warehouse_id': 1},
        {'warehouse_id': 2},  # bin belongs to a different warehouse
    ])
    with pytest.raises(ValueError):
        add_transfer_line(conn, transfer_id=1, product_id=1, from_bin_id=9, qty=5)


def test_add_transfer_line_happy_path():
    conn = _conn(fetchone_results=[
        {'status': 'draft', 'from_warehouse_id': 1},
        {'warehouse_id': 1},
        {'id': 77},
    ])
    line_id = add_transfer_line(conn, transfer_id=1, product_id=3, from_bin_id=9, qty=5)
    assert line_id == 77


def test_remove_transfer_line_raises_when_not_found():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        remove_transfer_line(conn, line_id=1)


def test_remove_transfer_line_raises_once_shipped():
    conn = _conn(fetchone_results=[{'transfer_status': 'in_transit'}])
    with pytest.raises(ValueError):
        remove_transfer_line(conn, line_id=1)


def test_remove_transfer_line_happy_path():
    conn = _conn(fetchone_results=[{'transfer_status': 'draft'}])
    remove_transfer_line(conn, line_id=1)
    delete_sql = conn.execute.call_args_list[-1][0][0]
    assert 'DELETE FROM wms_transfer_line' in delete_sql


@patch('manufacturing.wms_core.get_transfer_lines')
@patch('manufacturing.wms_core.get_transfer')
def test_ship_transfer_raises_when_not_found(mock_get_transfer, mock_get_lines):
    mock_get_transfer.return_value = None
    conn = _conn()
    with pytest.raises(ValueError):
        ship_transfer(conn, transfer_id=1, created_by='eric')


@patch('manufacturing.wms_core.get_transfer_lines')
@patch('manufacturing.wms_core.get_transfer')
def test_ship_transfer_raises_when_not_draft(mock_get_transfer, mock_get_lines):
    mock_get_transfer.return_value = {'id': 1, 'status': 'in_transit'}
    conn = _conn()
    with pytest.raises(ValueError):
        ship_transfer(conn, transfer_id=1, created_by='eric')


@patch('manufacturing.wms_core.get_transfer_lines')
@patch('manufacturing.wms_core.get_transfer')
def test_ship_transfer_raises_when_no_lines(mock_get_transfer, mock_get_lines):
    mock_get_transfer.return_value = {'id': 1, 'status': 'draft'}
    mock_get_lines.return_value = []
    conn = _conn()
    with pytest.raises(ValueError):
        ship_transfer(conn, transfer_id=1, created_by='eric')


@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core.get_transfer_lines')
@patch('manufacturing.wms_core.get_transfer')
def test_ship_transfer_happy_path(mock_get_transfer, mock_get_lines, mock_adjust):
    mock_get_transfer.return_value = {'id': 1, 'status': 'draft'}
    mock_get_lines.return_value = [
        {'id': 10, 'from_bin_id': 3, 'product_id': 7, 'qty': 5},
        {'id': 11, 'from_bin_id': 4, 'product_id': 8, 'qty': 2},
    ]
    conn = _conn()
    ship_transfer(conn, transfer_id=1, created_by='eric')

    assert mock_adjust.call_args_list == [
        ((conn, 3, 7, -5),), ((conn, 4, 8, -2),),
    ]
    line_updates = [c for c in conn.execute.call_args_list
                    if 'wms_transfer_line SET status' in c[0][0]]
    assert len(line_updates) == 2
    transfer_updates = [c for c in conn.execute.call_args_list
                       if "wms_transfer SET status = 'in_transit'" in c[0][0]]
    assert len(transfer_updates) == 1
    assert transfer_updates[0][0][1] == ('eric', 1)


def test_ship_transfer_propagates_insufficient_stock():
    """_adjust_bin_stock's own negative-qty guard is the authoritative
    check — ship_transfer doesn't re-validate qty itself, it just lets
    that ValueError propagate."""
    with patch('manufacturing.wms_core.get_transfer') as mock_get_transfer, \
         patch('manufacturing.wms_core.get_transfer_lines') as mock_get_lines:
        mock_get_transfer.return_value = {'id': 1, 'status': 'draft'}
        mock_get_lines.return_value = [
            {'id': 10, 'from_bin_id': 3, 'product_id': 7, 'qty': 500},
        ]
        conn = _conn(fetchone_results=[{'qty': 2}])  # only 2 tracked in the bin
        with pytest.raises(ValueError):
            ship_transfer(conn, transfer_id=1, created_by='eric')


def test_receive_transfer_line_raises_when_not_found():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        receive_transfer_line(conn, line_id=1, to_bin_id=5, created_by='eric')


def test_receive_transfer_line_raises_when_not_in_transit():
    conn = _conn(fetchone_results=[
        {'id': 1, 'transfer_id': 1, 'product_id': 7, 'qty': 5,
         'status': 'pending', 'to_warehouse_id': 2},
    ])
    with pytest.raises(ValueError):
        receive_transfer_line(conn, line_id=1, to_bin_id=5, created_by='eric')


def test_receive_transfer_line_raises_when_bin_in_wrong_warehouse():
    conn = _conn(fetchone_results=[
        {'id': 1, 'transfer_id': 1, 'product_id': 7, 'qty': 5,
         'status': 'in_transit', 'to_warehouse_id': 2},
        {'warehouse_id': 3},  # bin belongs to a different warehouse
    ])
    with pytest.raises(ValueError):
        receive_transfer_line(conn, line_id=1, to_bin_id=5, created_by='eric')


@patch('manufacturing.wms_core._adjust_bin_stock')
def test_receive_transfer_line_completes_transfer_when_last_line(mock_adjust):
    conn = _conn(fetchone_results=[
        {'id': 1, 'transfer_id': 9, 'product_id': 7, 'qty': 5,
         'status': 'in_transit', 'to_warehouse_id': 2},
        {'warehouse_id': 2},
        {'n': 0},  # no lines left unreceived
    ])
    receive_transfer_line(conn, line_id=1, to_bin_id=5, created_by='eric')

    mock_adjust.assert_called_once_with(conn, 5, 7, 5)
    transfer_updates = [c for c in conn.execute.call_args_list
                       if "wms_transfer SET status = 'completed'" in c[0][0]]
    assert len(transfer_updates) == 1
    assert transfer_updates[0][0][1] == ('eric', 9)


@patch('manufacturing.wms_core._adjust_bin_stock')
def test_receive_transfer_line_leaves_transfer_in_transit_when_lines_remain(mock_adjust):
    conn = _conn(fetchone_results=[
        {'id': 1, 'transfer_id': 9, 'product_id': 7, 'qty': 5,
         'status': 'in_transit', 'to_warehouse_id': 2},
        {'warehouse_id': 2},
        {'n': 1},  # one line still unreceived
    ])
    receive_transfer_line(conn, line_id=1, to_bin_id=5, created_by='eric')

    transfer_updates = [c for c in conn.execute.call_args_list
                       if "wms_transfer SET status = 'completed'" in c[0][0]]
    assert len(transfer_updates) == 0


def test_cancel_transfer_raises_when_not_found():
    with patch('manufacturing.wms_core.get_transfer') as mock_get_transfer:
        mock_get_transfer.return_value = None
        conn = _conn()
        with pytest.raises(ValueError):
            cancel_transfer(conn, transfer_id=1)


def test_cancel_transfer_raises_once_shipped():
    with patch('manufacturing.wms_core.get_transfer') as mock_get_transfer:
        mock_get_transfer.return_value = {'id': 1, 'status': 'in_transit'}
        conn = _conn()
        with pytest.raises(ValueError):
            cancel_transfer(conn, transfer_id=1)


def test_cancel_transfer_happy_path():
    with patch('manufacturing.wms_core.get_transfer') as mock_get_transfer:
        mock_get_transfer.return_value = {'id': 1, 'status': 'draft'}
        conn = _conn()
        cancel_transfer(conn, transfer_id=1)
        update_sql = conn.execute.call_args_list[-1][0][0]
        assert "wms_transfer SET status = 'cancelled'" in update_sql
