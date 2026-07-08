"""Tests for costing_layers_core — FIFO / LIFO / Weighted-Average costing.

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_wms_core.py / test_landed_cost_core.py),
plus unittest.mock.patch for the one cross-module function this module
re-imports by name (``inventory_core.record_transaction``).
"""

from unittest.mock import MagicMock, patch

import pytest

from manufacturing.costing_layers_core import (
    get_costing_method, set_costing_method,
    receive_layer, receive_with_costing,
    _consume_fifo, _consume_lifo, _consume_average,
    consume_cost, issue_with_costing,
    get_inventory_valuation, list_inventory_valuation, list_cogs_history,
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


# ── costing method ───────────────────────────────────────────────────────────

def test_get_costing_method_defaults_to_standard_when_blank():
    conn = _conn(fetchone_results=[{'costing_method': ''}])
    assert get_costing_method(conn, 1) == 'standard'


def test_get_costing_method_returns_stored_value():
    conn = _conn(fetchone_results=[{'costing_method': 'fifo'}])
    assert get_costing_method(conn, 1) == 'fifo'


def test_set_costing_method_raises_for_unknown_method():
    conn = _conn()
    with pytest.raises(ValueError):
        set_costing_method(conn, 1, 'moving_average_ish')


def test_set_costing_method_raises_for_missing_product():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        set_costing_method(conn, 1, 'fifo')


def test_set_costing_method_happy_path():
    conn = _conn(fetchone_results=[{'id': 1}])
    set_costing_method(conn, 1, 'lifo')
    update_sql, params = conn.execute.call_args_list[0][0]
    assert 'UPDATE product SET costing_method' in update_sql
    assert params == ('lifo', 1)


# ── cost layers ──────────────────────────────────────────────────────────────

def test_receive_layer_raises_for_nonpositive_qty():
    conn = _conn()
    with pytest.raises(ValueError):
        receive_layer(conn, product_id=1, qty=0, unit_cost=5, reference='', created_by='eric')


def test_receive_layer_raises_for_negative_unit_cost():
    conn = _conn()
    with pytest.raises(ValueError):
        receive_layer(conn, product_id=1, qty=10, unit_cost=-1, reference='', created_by='eric')


def test_receive_layer_happy_path():
    conn = _conn(fetchone_results=[{'id': 42}])
    layer_id = receive_layer(conn, product_id=1, qty=10, unit_cost=5.5, reference='PO-1', created_by='eric')
    assert layer_id == 42
    insert_sql = conn.execute.call_args_list[0][0][0]
    assert 'INSERT INTO inventory_cost_layer' in insert_sql


@patch('manufacturing.costing_layers_core.record_transaction')
def test_receive_with_costing_raises_when_standard(mock_record_txn):
    conn = _conn(fetchone_results=[{'costing_method': 'standard'}])
    with pytest.raises(ValueError):
        receive_with_costing(conn, product_id=1, qty=10, unit_cost=5,
                             reference='', notes='', created_by='eric')
    mock_record_txn.assert_not_called()


@patch('manufacturing.costing_layers_core.record_transaction')
def test_receive_with_costing_happy_path(mock_record_txn):
    mock_record_txn.return_value = 60.0
    conn = _conn(fetchone_results=[{'costing_method': 'fifo'}, {'id': 7}])
    result = receive_with_costing(conn, product_id=1, qty=10, unit_cost=5,
                                  reference='PO-1', notes='', created_by='eric')
    mock_record_txn.assert_called_once_with(
        conn, 1, 'receive', 10, reference='PO-1', notes='', created_by='eric')
    assert result == {'new_amount': 60.0, 'layer_id': 7}


# ── consumption ordering ─────────────────────────────────────────────────────

def test_consume_fifo_drains_oldest_layer_first():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'unit_cost': 4.0, 'qty_remaining': 6},
        {'id': 2, 'unit_cost': 6.0, 'qty_remaining': 10},
    ]])
    total_cost, shortfall = _consume_fifo(conn, product_id=1, qty=8)
    # 6 units @ 4.0 + 2 units @ 6.0
    assert total_cost == pytest.approx(24.0 + 12.0)
    assert shortfall == 0.0
    update_calls = [c for c in conn.execute.call_args_list if 'UPDATE inventory_cost_layer' in c[0][0]]
    assert len(update_calls) == 2
    assert update_calls[0][0][1] == (6, 1)
    assert update_calls[1][0][1] == (2, 2)


def test_consume_lifo_drains_newest_layer_first():
    conn = _conn(fetchall_results=[[
        {'id': 2, 'unit_cost': 6.0, 'qty_remaining': 10},
        {'id': 1, 'unit_cost': 4.0, 'qty_remaining': 6},
    ]])
    total_cost, shortfall = _consume_lifo(conn, product_id=1, qty=8)
    # LIFO: layer 2 (newest) first, fully covers the 8 units needed
    assert total_cost == pytest.approx(48.0)
    assert shortfall == 0.0
    update_calls = [c for c in conn.execute.call_args_list if 'UPDATE inventory_cost_layer' in c[0][0]]
    assert len(update_calls) == 1
    assert update_calls[0][0][1] == (8, 2)


def test_consume_fifo_reports_shortfall_when_layers_insufficient():
    conn = _conn(fetchall_results=[[{'id': 1, 'unit_cost': 4.0, 'qty_remaining': 3}]])
    total_cost, shortfall = _consume_fifo(conn, product_id=1, qty=10)
    assert total_cost == pytest.approx(12.0)
    assert shortfall == pytest.approx(7.0)


def test_consume_average_costs_uniformly_across_layers():
    # pool: 6 @ 4.0 + 10 @ 6.0 = 24 + 60 = 84 value over 16 qty -> avg 5.25
    conn = _conn(
        fetchone_results=[{'qty': 16, 'value': 84.0}],
        fetchall_results=[[
            {'id': 1, 'qty_remaining': 6},
            {'id': 2, 'qty_remaining': 10},
        ]],
    )
    total_cost, shortfall = _consume_average(conn, product_id=1, qty=8)
    assert total_cost == pytest.approx(8 * 5.25)
    assert shortfall == 0.0
    update_calls = [c for c in conn.execute.call_args_list if 'UPDATE inventory_cost_layer' in c[0][0]]
    # drawn oldest-first: layer 1 (6 remaining) fully drained, then 2 more from layer 2
    assert len(update_calls) == 2
    assert update_calls[0][0][1] == (6, 1)
    assert update_calls[1][0][1] == (2, 2)


def test_consume_average_reports_shortfall_when_pool_empty():
    conn = _conn(fetchone_results=[{'qty': 0, 'value': 0.0}])
    total_cost, shortfall = _consume_average(conn, product_id=1, qty=5)
    assert total_cost == 0.0
    assert shortfall == 5.0


# ── consume_cost dispatch + shortfall fallback ───────────────────────────────

def test_consume_cost_raises_for_unknown_method():
    conn = _conn()
    with pytest.raises(ValueError):
        consume_cost(conn, product_id=1, qty=5, method='moving_average_ish')


@patch('manufacturing.costing_layers_core._consume_fifo')
def test_consume_cost_fully_covered_skips_fallback_lookup(mock_consume):
    mock_consume.return_value = (40.0, 0.0)
    conn = _conn()
    result = consume_cost(conn, product_id=1, qty=8, method='fifo')
    assert result == {'total_cost': 40.0, 'unit_cost': 5.0, 'shortfall_qty': 0.0}
    conn.execute.assert_not_called()


@patch('manufacturing.costing_layers_core._consume_fifo')
def test_consume_cost_shortfall_costed_at_purchase_price(mock_consume):
    mock_consume.return_value = (12.0, 7.0)  # 3 units @4.0 covered, 7 units short
    conn = _conn(fetchone_results=[{'purchase_price': 2.0}])
    result = consume_cost(conn, product_id=1, qty=10, method='fifo')
    assert result['total_cost'] == pytest.approx(12.0 + 7.0 * 2.0)
    assert result['shortfall_qty'] == 7.0
    assert result['unit_cost'] == pytest.approx((12.0 + 14.0) / 10)


# ── issue_with_costing ────────────────────────────────────────────────────────

@patch('manufacturing.costing_layers_core.consume_cost')
@patch('manufacturing.costing_layers_core.record_transaction')
def test_issue_with_costing_raises_when_standard(mock_record_txn, mock_consume):
    conn = _conn(fetchone_results=[{'costing_method': 'standard'}])
    with pytest.raises(ValueError):
        issue_with_costing(conn, product_id=1, qty=5, reference='', notes='', created_by='eric')
    mock_record_txn.assert_not_called()
    mock_consume.assert_not_called()


@patch('manufacturing.costing_layers_core.consume_cost')
@patch('manufacturing.costing_layers_core.record_transaction')
def test_issue_with_costing_happy_path(mock_record_txn, mock_consume):
    mock_record_txn.return_value = 12.0
    mock_consume.return_value = {'total_cost': 40.0, 'unit_cost': 8.0, 'shortfall_qty': 0.0}
    conn = _conn(fetchone_results=[{'costing_method': 'lifo'}])

    result = issue_with_costing(conn, product_id=1, qty=5, reference='SO-1',
                                notes='', created_by='eric')

    mock_record_txn.assert_called_once_with(
        conn, 1, 'issue', 5, reference='SO-1', notes='', created_by='eric')
    mock_consume.assert_called_once_with(conn, 1, 5, 'lifo')
    assert result == {'new_amount': 12.0, 'total_cost': 40.0, 'unit_cost': 8.0, 'shortfall_qty': 0.0}
    insert_calls = [c for c in conn.execute.call_args_list if 'INSERT INTO inventory_cogs_entry' in c[0][0]]
    assert len(insert_calls) == 1


# ── reporting ─────────────────────────────────────────────────────────────────

def test_get_inventory_valuation_computes_average_cost():
    conn = _conn(fetchone_results=[
        {'costing_method': 'fifo'},
        {'qty': 10, 'value': 55.0},
        {'amount': 10},
    ])
    result = get_inventory_valuation(conn, product_id=1)
    assert result == {
        'product_id': 1, 'method': 'fifo', 'layer_qty_remaining': 10,
        'total_value': 55.0, 'avg_unit_cost': 5.5, 'product_amount': 10,
    }


def test_get_inventory_valuation_zero_qty_avoids_division_by_zero():
    conn = _conn(fetchone_results=[
        {'costing_method': 'fifo'},
        {'qty': 0, 'value': 0.0},
        {'amount': 0},
    ])
    result = get_inventory_valuation(conn, product_id=1)
    assert result['avg_unit_cost'] == 0.0


@patch('manufacturing.costing_layers_core.get_inventory_valuation')
def test_list_inventory_valuation_only_lists_non_standard_products(mock_valuation):
    mock_valuation.side_effect = [
        {'product_id': 1, 'method': 'fifo'}, {'product_id': 2, 'method': 'lifo'},
    ]
    conn = _conn(fetchall_results=[[
        {'id': 1, 'name': 'Widget'}, {'id': 2, 'name': 'Gadget'},
    ]])
    result = list_inventory_valuation(conn)
    assert [r['product_name'] for r in result] == ['Widget', 'Gadget']
    select_sql = conn.execute.call_args_list[0][0][0]
    assert "costing_method != 'standard'" in select_sql


def test_list_cogs_history_filters_by_product_when_given():
    conn = _conn(fetchall_results=[[{'id': 1, 'product_id': 9, 'qty': 5}]])
    result = list_cogs_history(conn, product_id=9)
    assert result == [{'id': 1, 'product_id': 9, 'qty': 5}]
    select_sql, params = conn.execute.call_args_list[0][0]
    assert 'WHERE product_id = %s' in select_sql
    assert params == [9, 100]
