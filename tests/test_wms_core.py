"""Tests for wms_core — Warehouse Management System (P3-B).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_production_core.py /
test_capacity_planning_core.py), plus unittest.mock.patch for the
cross-module functions this module re-imports by name.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from manufacturing.wms_core import (
    create_bin, get_or_create_unassigned_bin, is_unassigned_bin,
    _adjust_bin_stock, _build_full_code, _next_sequence,
    suggest_putaway_bin, receive_and_putaway, credit_unassigned_receipt,
    generate_pick_list, _resequence_pick_list, record_pick,
    add_carton_item, mark_pick_list_packed, confirm_shipment,
    create_transfer, add_transfer_line, remove_transfer_line,
    ship_transfer, receive_transfer_line, cancel_transfer,
    _sync_wave_status, create_wave, record_wave_pick, cancel_wave,
    find_cross_dock_candidates, receive_cross_dock,
    create_reader, create_tag, simulate_tag_read, retire_tag,
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


# ── wave picking ─────────────────────────────────────────────────────────────

def test_sync_wave_status_returns_empty_for_missing_wave():
    conn = _conn(fetchone_results=[None])
    assert _sync_wave_status(conn, wave_id=1) == ''


def test_sync_wave_status_short_circuits_for_cancelled():
    conn = _conn()
    result = _sync_wave_status(conn, wave_id=1, current_status='cancelled')
    assert result == 'cancelled'
    conn.execute.assert_not_called()


def test_sync_wave_status_becomes_completed_when_no_pending():
    conn = _conn(fetchone_results=[{'pending': 0, 'resolved': 5}])
    result = _sync_wave_status(conn, wave_id=1, current_status='picking')
    assert result == 'completed'
    update_calls = [c for c in conn.execute.call_args_list if 'wms_wave SET status' in c[0][0]]
    assert len(update_calls) == 1
    assert update_calls[0][0][1] == ('completed', 1)


def test_sync_wave_status_becomes_picking_when_some_resolved():
    conn = _conn(fetchone_results=[{'pending': 3, 'resolved': 2}])
    result = _sync_wave_status(conn, wave_id=1, current_status='open')
    assert result == 'picking'


def test_sync_wave_status_stays_open_noop_when_nothing_resolved():
    conn = _conn(fetchone_results=[{'pending': 5, 'resolved': 0}])
    result = _sync_wave_status(conn, wave_id=1, current_status='open')
    assert result == 'open'
    update_calls = [c for c in conn.execute.call_args_list if 'wms_wave SET status' in c[0][0]]
    assert len(update_calls) == 0


def test_create_wave_raises_for_empty_so_ids():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_wave(conn, [], created_by='eric')
    assert conn.execute.call_count == 0


@patch('manufacturing.wms_core.generate_pick_list')
@patch('manufacturing.wms_core._next_sequence')
def test_create_wave_dedupes_so_ids(mock_seq, mock_gen):
    mock_seq.return_value = 'WAVE-2026-0001'
    mock_gen.return_value = 101
    conn = _conn(fetchone_results=[{'id': 5}])
    wave_id = create_wave(conn, [9, 9, 9], created_by='eric')
    assert wave_id == 5
    mock_gen.assert_called_once_with(conn, 9, 'eric')


@patch('manufacturing.wms_core.generate_pick_list')
@patch('manufacturing.wms_core._next_sequence')
def test_create_wave_happy_path(mock_seq, mock_gen):
    mock_seq.return_value = 'WAVE-2026-0001'
    mock_gen.side_effect = [101, 102]
    conn = _conn(fetchone_results=[{'id': 5}])
    wave_id = create_wave(conn, [9, 10], created_by='eric')

    assert wave_id == 5
    assert mock_gen.call_args_list == [call(conn, 9, 'eric'), call(conn, 10, 'eric')]
    update_calls = [c for c in conn.execute.call_args_list if 'wms_pick_list SET wave_id' in c[0][0]]
    assert len(update_calls) == 2
    assert update_calls[0][0][1] == (5, 101)
    assert update_calls[1][0][1] == (5, 102)


def test_record_wave_pick_raises_for_nonpositive_qty():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_wave_pick(conn, wave_id=1, product_id=1, bin_id=1, qty_picked=0, created_by='eric')


@patch('manufacturing.wms_core.get_wave')
def test_record_wave_pick_raises_when_wave_not_found(mock_get_wave):
    mock_get_wave.return_value = None
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_wave_pick(conn, wave_id=1, product_id=1, bin_id=1, qty_picked=5, created_by='eric')


@patch('manufacturing.wms_core.get_wave')
def test_record_wave_pick_raises_when_wave_cancelled(mock_get_wave):
    mock_get_wave.return_value = {'id': 1, 'status': 'cancelled'}
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_wave_pick(conn, wave_id=1, product_id=1, bin_id=1, qty_picked=5, created_by='eric')


@patch('manufacturing.wms_core.get_wave')
def test_record_wave_pick_raises_when_no_matching_lines(mock_get_wave):
    mock_get_wave.return_value = {'id': 1, 'status': 'open'}
    conn = _conn(fetchall_results=[[]])
    with pytest.raises(ValueError):
        record_wave_pick(conn, wave_id=1, product_id=1, bin_id=1, qty_picked=5, created_by='eric')


@patch('manufacturing.wms_core.get_wave')
def test_record_wave_pick_raises_when_exceeding_total_needed(mock_get_wave):
    mock_get_wave.return_value = {'id': 1, 'status': 'open'}
    conn = _conn(fetchall_results=[[
        {'id': 10, 'qty_ordered': 5}, {'id': 11, 'qty_ordered': 3},
    ]])
    with pytest.raises(ValueError):
        record_wave_pick(conn, wave_id=1, product_id=1, bin_id=1, qty_picked=100, created_by='eric')


@patch('manufacturing.wms_core._sync_wave_status')
@patch('manufacturing.wms_core.record_pick')
@patch('manufacturing.wms_core.get_wave')
def test_record_wave_pick_allocates_across_multiple_lines(mock_get_wave, mock_record_pick, mock_sync):
    mock_get_wave.return_value = {'id': 1, 'status': 'open'}
    conn = _conn(fetchall_results=[[
        {'id': 10, 'qty_ordered': 5}, {'id': 11, 'qty_ordered': 3},
    ]])
    result = record_wave_pick(conn, wave_id=1, product_id=7, bin_id=3, qty_picked=6, created_by='eric')

    assert mock_record_pick.call_args_list == [
        call(conn, 10, 5, 'eric'),  # first (oldest) line fully covered
        call(conn, 11, 1, 'eric'),  # second line gets the remaining 1
    ]
    assert result == {'lines_updated': 2, 'total_allocated': 6}
    mock_sync.assert_called_once_with(conn, 1)


@patch('manufacturing.wms_core.get_wave')
def test_cancel_wave_raises_when_missing(mock_get_wave):
    mock_get_wave.return_value = None
    conn = MagicMock()
    with pytest.raises(ValueError):
        cancel_wave(conn, wave_id=1)


@patch('manufacturing.wms_core.get_wave')
def test_cancel_wave_raises_when_not_open(mock_get_wave):
    mock_get_wave.return_value = {'id': 1, 'status': 'picking'}
    conn = MagicMock()
    with pytest.raises(ValueError):
        cancel_wave(conn, wave_id=1)


@patch('manufacturing.wms_core.get_wave')
def test_cancel_wave_happy_path(mock_get_wave):
    mock_get_wave.return_value = {'id': 1, 'status': 'open'}
    conn = MagicMock()
    cancel_wave(conn, wave_id=1)
    calls = conn.execute.call_args_list
    assert "wms_wave SET status = 'cancelled'" in calls[0][0][0]
    assert calls[0][0][1] == (1,)
    assert "wms_pick_list SET status = 'cancelled'" in calls[1][0][0]
    assert calls[1][0][1] == (1,)


# ── cross-docking ────────────────────────────────────────────────────────────

def test_find_cross_dock_candidates_queries_unassigned_bin_only():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'qty_ordered': 5, 'pick_list_id': 10,
         'pick_number': 'PICK-2026-0001', 'so_number': 'SO-1'},
    ]])
    result = find_cross_dock_candidates(conn, product_id=7)
    assert result == [{'id': 1, 'qty_ordered': 5, 'pick_list_id': 10,
                       'pick_number': 'PICK-2026-0001', 'so_number': 'SO-1'}]
    sql, params = conn.execute.call_args_list[0][0]
    assert 'wms_pick_list_line' in sql
    assert params[0] == 7
    assert params[1] == 'UNASSIGNED-UNASSIGNED'


def test_receive_cross_dock_raises_for_nonpositive_qty():
    conn = MagicMock()
    with pytest.raises(ValueError):
        receive_cross_dock(conn, po_item_id=1, po_id=1, product_id=7, qty=0,
                           pick_list_line_id=1, created_by='eric')
    assert conn.execute.call_count == 0


def test_receive_cross_dock_raises_when_line_not_found():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        receive_cross_dock(conn, po_item_id=1, po_id=1, product_id=7, qty=5,
                           pick_list_line_id=1, created_by='eric')


def test_receive_cross_dock_raises_for_wrong_product():
    conn = _conn(fetchone_results=[
        {'id': 1, 'product_id': 99, 'qty_ordered': 10, 'status': 'pending', 'bin_id': 5},
    ])
    with pytest.raises(ValueError):
        receive_cross_dock(conn, po_item_id=1, po_id=1, product_id=7, qty=5,
                           pick_list_line_id=1, created_by='eric')


def test_receive_cross_dock_raises_when_line_not_pending():
    conn = _conn(fetchone_results=[
        {'id': 1, 'product_id': 7, 'qty_ordered': 10, 'status': 'picked', 'bin_id': 5},
    ])
    with pytest.raises(ValueError):
        receive_cross_dock(conn, po_item_id=1, po_id=1, product_id=7, qty=5,
                           pick_list_line_id=1, created_by='eric')


@patch('manufacturing.wms_core.is_unassigned_bin')
def test_receive_cross_dock_raises_when_bin_is_real(mock_is_unassigned):
    mock_is_unassigned.return_value = False
    conn = _conn(fetchone_results=[
        {'id': 1, 'product_id': 7, 'qty_ordered': 10, 'status': 'pending', 'bin_id': 5},
    ])
    with pytest.raises(ValueError):
        receive_cross_dock(conn, po_item_id=1, po_id=1, product_id=7, qty=5,
                           pick_list_line_id=1, created_by='eric')


@patch('manufacturing.wms_core.is_unassigned_bin')
def test_receive_cross_dock_raises_when_qty_exceeds_line_need(mock_is_unassigned):
    mock_is_unassigned.return_value = True
    conn = _conn(fetchone_results=[
        {'id': 1, 'product_id': 7, 'qty_ordered': 10, 'status': 'pending', 'bin_id': 9},
    ])
    with pytest.raises(ValueError):
        receive_cross_dock(conn, po_item_id=1, po_id=1, product_id=7, qty=50,
                           pick_list_line_id=1, created_by='eric')


@patch('manufacturing.wms_core.record_pick')
@patch('manufacturing.wms_core.record_transaction')
@patch('manufacturing.wms_core._apply_po_receipt')
@patch('manufacturing.wms_core.is_unassigned_bin')
def test_receive_cross_dock_happy_path(
    mock_is_unassigned, mock_apply, mock_record_txn, mock_record_pick,
):
    mock_is_unassigned.return_value = True
    mock_apply.return_value = 5
    mock_record_txn.return_value = 42.0
    mock_record_pick.return_value = 'picked'
    conn = _conn(fetchone_results=[
        {'id': 1, 'product_id': 7, 'qty_ordered': 10, 'status': 'pending', 'bin_id': 9},
    ])

    result = receive_cross_dock(conn, po_item_id=3, po_id=2, product_id=7, qty=5,
                                pick_list_line_id=1, created_by='eric')

    mock_apply.assert_called_once_with(conn, 3, 2, 5)
    mock_record_txn.assert_called_once()
    assert mock_record_txn.call_args[0][2] == 'receive'
    assert mock_record_txn.call_args[0][3] == 5
    mock_record_pick.assert_called_once_with(conn, 1, 5, 'eric')
    assert result == {'received_qty': 5, 'new_amount': 42.0, 'pick_status': 'picked'}


@patch('manufacturing.wms_core.record_pick')
@patch('manufacturing.wms_core.record_transaction')
@patch('manufacturing.wms_core._apply_po_receipt')
@patch('manufacturing.wms_core.is_unassigned_bin')
def test_receive_cross_dock_picks_only_the_actually_received_delta(
    mock_is_unassigned, mock_apply, mock_record_txn, mock_record_pick,
):
    """If the PO item was nearly fully received already, _apply_po_receipt
    clamps the delta below the requested qty -- the pick must reflect what
    was actually received, not the original request."""
    mock_is_unassigned.return_value = True
    mock_apply.return_value = 3  # clamped below the requested 5
    mock_record_txn.return_value = 42.0
    mock_record_pick.return_value = 'short'
    conn = _conn(fetchone_results=[
        {'id': 1, 'product_id': 7, 'qty_ordered': 10, 'status': 'pending', 'bin_id': 9},
    ])

    receive_cross_dock(conn, po_item_id=3, po_id=2, product_id=7, qty=5,
                       pick_list_line_id=1, created_by='eric')

    mock_record_pick.assert_called_once_with(conn, 1, 3, 'eric')


# ── RFID tracking (simulated) ────────────────────────────────────────────────

def test_create_reader_raises_for_blank_code():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_reader(conn, zone_id=1, reader_code='  ')
    assert conn.execute.call_count == 0


def test_create_reader_happy_path():
    conn = _conn(fetchone_results=[{'id': 5}])
    reader_id = create_reader(conn, zone_id=1, reader_code='DOCK-A', description='Inbound dock A')
    assert reader_id == 5
    insert_sql = conn.execute.call_args_list[0][0][0]
    assert 'INSERT INTO wms_rfid_reader' in insert_sql


def test_create_tag_raises_for_nonpositive_qty():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_tag(conn, tag_code='TAG-1', product_id=1, qty=0, bin_id=1, created_by='eric')
    assert conn.execute.call_count == 0


def test_create_tag_raises_for_blank_code():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_tag(conn, tag_code='  ', product_id=1, qty=5, bin_id=1, created_by='eric')
    assert conn.execute.call_count == 0


def test_create_tag_raises_when_bin_has_insufficient_stock():
    conn = _conn(fetchone_results=[{'qty': 2}])  # only 2 tracked, tagging 5
    with pytest.raises(ValueError):
        create_tag(conn, tag_code='TAG-1', product_id=1, qty=5, bin_id=1, created_by='eric')


def test_create_tag_raises_when_no_stock_row_at_all():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        create_tag(conn, tag_code='TAG-1', product_id=1, qty=5, bin_id=1, created_by='eric')


def test_create_tag_happy_path():
    conn = _conn(fetchone_results=[{'qty': 10}, {'id': 9}])
    tag_id = create_tag(conn, tag_code='TAG-1', product_id=1, qty=5, bin_id=1, created_by='eric')
    assert tag_id == 9
    insert_sql = conn.execute.call_args_list[-1][0][0]
    assert 'INSERT INTO wms_rfid_tag' in insert_sql


@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_raises_when_tag_not_found(mock_get_tag):
    mock_get_tag.return_value = None
    conn = MagicMock()
    with pytest.raises(ValueError):
        simulate_tag_read(conn, tag_id=1, reader_id=1, created_by='eric')


@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_raises_when_tag_retired(mock_get_tag):
    mock_get_tag.return_value = {'id': 1, 'status': 'retired', 'bin_id': 3, 'product_id': 7, 'qty': 5}
    conn = MagicMock()
    with pytest.raises(ValueError):
        simulate_tag_read(conn, tag_id=1, reader_id=1, created_by='eric')


@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_raises_when_reader_not_found(mock_get_tag):
    mock_get_tag.return_value = {'id': 1, 'status': 'active', 'bin_id': 3, 'product_id': 7, 'qty': 5}
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        simulate_tag_read(conn, tag_id=1, reader_id=1, created_by='eric')


@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_same_zone_is_heartbeat_no_move(mock_get_tag):
    mock_get_tag.return_value = {'id': 1, 'status': 'active', 'bin_id': 3, 'product_id': 7, 'qty': 5}
    conn = _conn(fetchone_results=[
        {'id': 10, 'zone_id': 2},  # reader lookup
        {'zone_id': 2},            # tag's current bin -> same zone
    ])
    result = simulate_tag_read(conn, tag_id=1, reader_id=10, created_by='eric')
    assert result == {'moved': False, 'bin_id': 3}
    insert_calls = [c for c in conn.execute.call_args_list if 'INSERT INTO wms_rfid_read_event' in c[0][0]]
    assert len(insert_calls) == 1
    assert insert_calls[0][0][1] == (1, 10, 3, 3, False, 'eric')


@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core._least_full_active_bin_in_zone')
@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_different_zone_relocates(mock_get_tag, mock_least_full, mock_adjust):
    mock_get_tag.return_value = {'id': 1, 'status': 'active', 'bin_id': 3, 'product_id': 7, 'qty': 5}
    mock_least_full.return_value = {'id': 20, 'full_code': 'Z2-B01'}
    conn = _conn(fetchone_results=[
        {'id': 10, 'zone_id': 2},  # reader lookup
        {'zone_id': 9},            # tag's current bin -> different zone
    ])

    result = simulate_tag_read(conn, tag_id=1, reader_id=10, created_by='eric')

    assert result == {'moved': True, 'bin_id': 20}
    assert mock_adjust.call_args_list == [
        call(conn, 3, 7, -5),   # decrement old bin
        call(conn, 20, 7, 5),   # credit new bin
    ]
    update_calls = [c for c in conn.execute.call_args_list if 'wms_rfid_tag SET bin_id' in c[0][0]]
    assert len(update_calls) == 1
    assert update_calls[0][0][1] == (20, 1)
    insert_calls = [c for c in conn.execute.call_args_list if 'INSERT INTO wms_rfid_read_event' in c[0][0]]
    assert insert_calls[0][0][1] == (1, 10, 3, 20, True, 'eric')


@patch('manufacturing.wms_core._least_full_active_bin_in_zone')
@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_raises_when_target_zone_has_no_bin(mock_get_tag, mock_least_full):
    mock_get_tag.return_value = {'id': 1, 'status': 'active', 'bin_id': 3, 'product_id': 7, 'qty': 5}
    mock_least_full.return_value = None
    conn = _conn(fetchone_results=[
        {'id': 10, 'zone_id': 2},
        {'zone_id': 9},
    ])
    with pytest.raises(ValueError):
        simulate_tag_read(conn, tag_id=1, reader_id=10, created_by='eric')


@patch('manufacturing.wms_core._adjust_bin_stock')
@patch('manufacturing.wms_core._least_full_active_bin_in_zone')
@patch('manufacturing.wms_core.get_tag')
def test_simulate_tag_read_first_placement_has_no_source_bin_to_decrement(
    mock_get_tag, mock_least_full, mock_adjust,
):
    """A tag with no prior location (bin_id=None) has never been placed --
    the first read should credit the target bin without trying to
    decrement a nonexistent source."""
    mock_get_tag.return_value = {'id': 1, 'status': 'active', 'bin_id': None, 'product_id': 7, 'qty': 5}
    mock_least_full.return_value = {'id': 20, 'full_code': 'Z2-B01'}
    conn = _conn(fetchone_results=[{'id': 10, 'zone_id': 2}])

    result = simulate_tag_read(conn, tag_id=1, reader_id=10, created_by='eric')

    assert result == {'moved': True, 'bin_id': 20}
    mock_adjust.assert_called_once_with(conn, 20, 7, 5)


@patch('manufacturing.wms_core.get_tag')
def test_retire_tag_raises_when_missing(mock_get_tag):
    mock_get_tag.return_value = None
    conn = MagicMock()
    with pytest.raises(ValueError):
        retire_tag(conn, tag_id=1)


@patch('manufacturing.wms_core.get_tag')
def test_retire_tag_raises_when_already_retired(mock_get_tag):
    mock_get_tag.return_value = {'id': 1, 'status': 'retired'}
    conn = MagicMock()
    with pytest.raises(ValueError):
        retire_tag(conn, tag_id=1)


@patch('manufacturing.wms_core.get_tag')
def test_retire_tag_happy_path(mock_get_tag):
    mock_get_tag.return_value = {'id': 1, 'status': 'active'}
    conn = MagicMock()
    retire_tag(conn, tag_id=1)
    update_sql, params = conn.execute.call_args_list[-1][0]
    assert "wms_rfid_tag SET status = 'retired'" in update_sql
    assert params == (1,)
