"""Tests for landed_cost_core — Landed Cost Allocation (P3-D).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_wms_core.py).
"""

from unittest.mock import MagicMock, patch

import pytest

from manufacturing.landed_cost_core import (
    _allocate_largest_remainder, create_landed_cost,
    list_receivable_po_items, list_landed_costs, get_landed_cost,
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


# ── allocation math ──────────────────────────────────────────────────────────

def test_allocate_largest_remainder_sums_exactly_to_total():
    result = _allocate_largest_remainder(100.0, [1, 1, 1])
    assert round(sum(result), 2) == 100.0
    assert result == [33.34, 33.33, 33.33]


def test_allocate_largest_remainder_proportional():
    result = _allocate_largest_remainder(300.0, [1, 2])
    assert result == [100.0, 200.0]


def test_allocate_largest_remainder_zero_weight_sum_returns_zeros():
    result = _allocate_largest_remainder(100.0, [0, 0])
    assert result == [0.0, 0.0]


# ── list_receivable_po_items ─────────────────────────────────────────────────

def test_list_receivable_po_items_computes_received_value():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'description': 'Widget', 'product_id': 5, 'product_name': 'Widget',
         'product_weight': 2.5, 'qty_received': 10, 'unit_price': 4.0, 'received_value': 40.0},
    ]])
    items = list_receivable_po_items(conn, po_id=1)
    assert items[0]['received_value'] == 40.0
    assert items[0]['product_weight'] == 2.5


# ── create_landed_cost ───────────────────────────────────────────────────────

@patch('manufacturing.landed_cost_core.list_receivable_po_items')
def test_create_landed_cost_raises_when_no_received_items(mock_items):
    mock_items.return_value = []
    conn = _conn()
    with pytest.raises(ValueError):
        create_landed_cost(conn, po_id=1, freight=100, duty=0, broker_fee=0,
                           insurance=0, method='value', line_weights=None,
                           created_by='a@b.com')


@patch('manufacturing.landed_cost_core.list_receivable_po_items')
def test_create_landed_cost_rejects_unknown_method(mock_items):
    conn = _conn()
    with pytest.raises(ValueError):
        create_landed_cost(conn, po_id=1, freight=100, duty=0, broker_fee=0,
                           insurance=0, method='bogus', line_weights=None,
                           created_by='a@b.com')


@patch('manufacturing.landed_cost_core.list_receivable_po_items')
def test_create_landed_cost_weight_method_raises_when_all_zero(mock_items):
    mock_items.return_value = [
        {'id': 1, 'product_id': 5, 'product_weight': 0.0, 'qty_received': 10,
         'unit_price': 4.0, 'received_value': 40.0},
    ]
    conn = _conn()
    with pytest.raises(ValueError):
        create_landed_cost(conn, po_id=1, freight=100, duty=0, broker_fee=0,
                           insurance=0, method='weight', line_weights=None,
                           created_by='a@b.com')


@patch('manufacturing.landed_cost_core.list_receivable_po_items')
def test_create_landed_cost_allocates_by_value_and_updates_purchase_price(mock_items):
    mock_items.return_value = [
        {'id': 1, 'product_id': 10, 'product_weight': 0.0, 'qty_received': 10,
         'unit_price': 4.0, 'received_value': 40.0},
        {'id': 2, 'product_id': 20, 'product_weight': 0.0, 'qty_received': 20,
         'unit_price': 3.0, 'received_value': 60.0},
    ]
    conn = _conn(fetchone_results=[{'id': 99}])
    lc_id = create_landed_cost(
        conn, po_id=1, freight=80, duty=0, broker_fee=0, insurance=0,
        method='value', line_weights=None, created_by='a@b.com')
    assert lc_id == 99

    calls = conn.execute.call_args_list
    header_sql, header_params = calls[0][0]
    assert 'INSERT INTO landed_cost ' in header_sql
    assert header_params[0] == 1  # po_id
    assert header_params[1] == 80.0  # freight

    line1_sql, line1_params = calls[1][0]
    assert 'INSERT INTO landed_cost_line' in line1_sql
    assert line1_params == (99, 1, 0.0, 32.0)  # 40/100 * 80 = 32
    price1_sql, price1_params = calls[2][0]
    assert 'UPDATE product SET purchase_price' in price1_sql
    assert price1_params == (32.0 / 10, 10)

    line2_sql, line2_params = calls[3][0]
    assert line2_params == (99, 2, 0.0, 48.0)  # 60/100 * 80 = 48
    price2_sql, price2_params = calls[4][0]
    assert price2_params == (48.0 / 20, 20)


@patch('manufacturing.landed_cost_core.list_receivable_po_items')
def test_create_landed_cost_weight_method_uses_line_override(mock_items):
    mock_items.return_value = [
        {'id': 1, 'product_id': 10, 'product_weight': 5.0, 'qty_received': 10,
         'unit_price': 4.0, 'received_value': 40.0},
        {'id': 2, 'product_id': 20, 'product_weight': 5.0, 'qty_received': 10,
         'unit_price': 4.0, 'received_value': 40.0},
    ]
    conn = _conn(fetchone_results=[{'id': 5}])
    create_landed_cost(
        conn, po_id=1, freight=100, duty=0, broker_fee=0, insurance=0,
        method='weight', line_weights={1: 30.0}, created_by='a@b.com')

    calls = conn.execute.call_args_list
    # line 1 uses override weight 30, line 2 falls back to product_weight 5
    line1_params = calls[1][0][1]
    assert line1_params[2] == 30.0
    line2_params = calls[3][0][1]
    assert line2_params[2] == 5.0
    # 30 / (30+5) * 100 = 85.71..., 5/(35) * 100 = 14.28... -> sums to 100
    assert round(line1_params[3] + line2_params[3], 2) == 100.0


@patch('manufacturing.landed_cost_core.list_receivable_po_items')
def test_create_landed_cost_skips_price_update_for_line_without_product(mock_items):
    mock_items.return_value = [
        {'id': 1, 'product_id': None, 'product_weight': 0.0, 'qty_received': 10,
         'unit_price': 4.0, 'received_value': 40.0},
    ]
    conn = _conn(fetchone_results=[{'id': 1}])
    create_landed_cost(
        conn, po_id=1, freight=50, duty=0, broker_fee=0, insurance=0,
        method='value', line_weights=None, created_by='a@b.com')
    calls = conn.execute.call_args_list
    # header insert + line insert only, no UPDATE product
    assert len(calls) == 2
    assert all('UPDATE product' not in c[0][0] for c in calls)


# ── list / get ────────────────────────────────────────────────────────────────

def test_list_landed_costs_computes_total():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'po_id': 1, 'freight': 10, 'duty': 5, 'broker_fee': 2,
         'insurance': 3, 'allocation_method': 'value', 'created_at': '2026-01-01',
         'created_by': 'a@b.com', 'total': 20},
    ]])
    result = list_landed_costs(conn, po_id=1)
    assert result[0]['total'] == 20


def test_get_landed_cost_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_landed_cost(conn, 999) is None


def test_get_landed_cost_includes_lines():
    conn = _conn(
        fetchone_results=[
            {'id': 1, 'po_id': 1, 'freight': 10, 'duty': 0, 'broker_fee': 0,
             'insurance': 0, 'allocation_method': 'value', 'created_at': '',
             'created_by': '', 'total': 10},
        ],
        fetchall_results=[[
            {'id': 1, 'po_item_id': 1, 'weight': 0.0, 'allocated_amount': 10.0,
             'description': 'Widget', 'qty_received': 5, 'unit_price': 2.0,
             'product_name': 'Widget'},
        ]],
    )
    result = get_landed_cost(conn, 1)
    assert result['lines'][0]['allocated_amount'] == 10.0
