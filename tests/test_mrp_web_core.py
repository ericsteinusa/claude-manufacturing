"""
Tests for mrp_web_core.py — Qt-free MRP data layer.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from manufacturing.mrp_web_core import (
    load_mrp_inputs,
    get_demand,
    get_demand_details,
    get_scheduled_receipts_detail,
    run_mrp,
    release_plan,
    _explode_to_wo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


def _row(**kw):
    return kw


# ---------------------------------------------------------------------------
# load_mrp_inputs
# ---------------------------------------------------------------------------

def test_load_mrp_inputs_returns_five_tuple():
    conn = _conn(fetchall=[])
    result = load_mrp_inputs(conn)
    assert len(result) == 5


def test_load_mrp_inputs_product_keyed_by_id():
    conn = MagicMock()
    responses = [
        MagicMock(fetchall=lambda: [
            {'id': 1, 'name': 'Widget', 'item_type': 'make',
             'lead_time_days': 5, 'amount': 10.0, 'safety_stock': 0.0}
        ]),
        MagicMock(fetchall=lambda: []),  # bom rows
        MagicMock(fetchall=lambda: []),  # wo rows
    ]
    conn.execute.side_effect = responses
    products, bom_lines, on_hand, scheduled, safety = load_mrp_inputs(conn)
    assert 1 in products
    assert products[1]['name'] == 'Widget'
    assert on_hand[1] == 10.0
    assert safety[1] == 0.0


def test_load_mrp_inputs_bom_lines_grouped_by_parent():
    conn = MagicMock()
    responses = [
        MagicMock(fetchall=lambda: [
            {'id': 1, 'name': 'A', 'item_type': 'make', 'lead_time_days': 0, 'amount': 0.0, 'safety_stock': 0.0},
            {'id': 2, 'name': 'B', 'item_type': 'buy', 'lead_time_days': 0, 'amount': 0.0, 'safety_stock': 0.0},
        ]),
        MagicMock(fetchall=lambda: [
            {'product_id': 1, 'component_id': 2, 'qty_required': 3.0, 'scrap_pct': 0.0},
        ]),
        MagicMock(fetchall=lambda: []),  # wo rows
    ]
    conn.execute.side_effect = responses
    _, bom_lines, _, _, _ = load_mrp_inputs(conn)
    assert 1 in bom_lines
    assert bom_lines[1] == [(2, 3.0, 0.0)]


def test_load_mrp_inputs_scheduled_receipts_aggregated():
    conn = MagicMock()
    responses = [
        MagicMock(fetchall=lambda: [
            {'id': 5, 'name': 'X', 'item_type': 'make', 'lead_time_days': 2, 'amount': 0.0, 'safety_stock': 0.0}
        ]),
        MagicMock(fetchall=lambda: []),
        MagicMock(fetchall=lambda: [
            {'product_id': 5, 'qty': 20.0}
        ]),
    ]
    conn.execute.side_effect = responses
    _, _, _, scheduled, _ = load_mrp_inputs(conn)
    assert scheduled[5] == 20.0


def test_load_mrp_inputs_empty_db():
    conn = MagicMock()
    responses = [
        MagicMock(fetchall=lambda: []),
        MagicMock(fetchall=lambda: []),
        MagicMock(fetchall=lambda: []),
    ]
    conn.execute.side_effect = responses
    products, bom_lines, on_hand, scheduled, safety = load_mrp_inputs(conn)
    assert products == {}
    assert bom_lines == {}
    assert on_hand == {}
    assert scheduled == {}


# ---------------------------------------------------------------------------
# get_demand
# ---------------------------------------------------------------------------

def test_get_demand_returns_dict():
    conn = _conn(fetchall=[
        {'product_id': 3, 'total': 12.0},
        {'product_id': 7, 'total': 5.0},
    ])
    d = get_demand(conn)
    assert d == {3: 12.0, 7: 5.0}


def test_get_demand_empty_when_no_confirmed_sos():
    conn = _conn(fetchall=[])
    assert get_demand(conn) == {}


def test_get_demand_converts_to_float():
    conn = _conn(fetchall=[{'product_id': 1, 'total': 10}])
    d = get_demand(conn)
    assert isinstance(d[1], float)


def test_get_demand_query_filters_confirmed():
    conn = _conn(fetchall=[])
    get_demand(conn)
    sql = conn.execute.call_args[0][0]
    assert 'confirmed' in sql


# ---------------------------------------------------------------------------
# get_demand_details
# ---------------------------------------------------------------------------

def test_get_demand_details_returns_list_of_dicts():
    conn = _conn(fetchall=[
        {'id': 1, 'name': 'Bike', 'item_type': 'make', 'on_hand': 5.0,
         'demand_qty': 10, 'so_numbers': 'SO-001, SO-002'}
    ])
    rows = get_demand_details(conn)
    assert len(rows) == 1
    assert rows[0]['name'] == 'Bike'
    assert rows[0]['so_numbers'] == 'SO-001, SO-002'


def test_get_demand_details_empty():
    conn = _conn(fetchall=[])
    assert get_demand_details(conn) == []


# ---------------------------------------------------------------------------
# get_scheduled_receipts_detail
# ---------------------------------------------------------------------------

def test_get_scheduled_receipts_detail_keyed_by_product():
    conn = _conn(fetchall=[{'product_id': 2, 'qty': 8.0}])
    sr = get_scheduled_receipts_detail(conn)
    assert sr == {2: 8.0}


def test_get_scheduled_receipts_detail_empty():
    conn = _conn(fetchall=[])
    assert get_scheduled_receipts_detail(conn) == {}


# ---------------------------------------------------------------------------
# run_mrp
# ---------------------------------------------------------------------------

def test_run_mrp_returns_list():
    with patch('manufacturing.mrp_web_core.load_mrp_inputs') as mock_inputs, \
         patch('manufacturing.mrp_web_core.get_demand') as mock_demand, \
         patch('manufacturing.mrp_web_core.plan_orders') as mock_plan:
        mock_inputs.return_value = (
            {1: {'name': 'Widget', 'item_type': 'make', 'lead_time_days': 2, 'amount': 0.0}},
            {},    # bom_lines
            {1: 0.0},   # on_hand
            {},    # scheduled
            {1: 0.0},   # safety
        )
        mock_demand.return_value = {1: 5.0}
        mock_plan.return_value = [
            {'product_id': 1, 'order_type': 'make', 'qty': 5.0, 'lead_time_days': 2}
        ]
        conn = MagicMock()
        result = run_mrp(conn)
    assert len(result) == 1
    assert result[0]['product_name'] == 'Widget'
    assert result[0]['order_type'] == 'make'
    assert result[0]['qty'] == 5.0
    assert 'due_date' in result[0]


def test_run_mrp_due_date_is_iso_string():
    with patch('manufacturing.mrp_web_core.load_mrp_inputs') as mock_inputs, \
         patch('manufacturing.mrp_web_core.get_demand') as mock_demand, \
         patch('manufacturing.mrp_web_core.plan_orders') as mock_plan:
        mock_inputs.return_value = (
            {1: {'name': 'X', 'item_type': 'buy', 'lead_time_days': 7, 'amount': 0.0}},
            {}, {1: 0.0}, {}, {1: 0.0},
        )
        mock_demand.return_value = {1: 3.0}
        mock_plan.return_value = [
            {'product_id': 1, 'order_type': 'buy', 'qty': 3.0, 'lead_time_days': 7}
        ]
        conn = MagicMock()
        result = run_mrp(conn)
    due = result[0]['due_date']
    # Must be parseable as ISO date
    parsed = date.fromisoformat(due)
    assert (parsed - date.today()).days == 7


def test_run_mrp_empty_demand_returns_empty():
    with patch('manufacturing.mrp_web_core.load_mrp_inputs') as mock_inputs, \
         patch('manufacturing.mrp_web_core.get_demand') as mock_demand, \
         patch('manufacturing.mrp_web_core.plan_orders') as mock_plan:
        mock_inputs.return_value = ({}, {}, {}, {}, {})
        mock_demand.return_value = {}
        mock_plan.return_value = []
        conn = MagicMock()
        result = run_mrp(conn)
    assert result == []


def test_run_mrp_unknown_product_id_uses_fallback_name():
    with patch('manufacturing.mrp_web_core.load_mrp_inputs') as mock_inputs, \
         patch('manufacturing.mrp_web_core.get_demand') as mock_demand, \
         patch('manufacturing.mrp_web_core.plan_orders') as mock_plan:
        mock_inputs.return_value = ({}, {}, {}, {}, {})
        mock_demand.return_value = {99: 1.0}
        mock_plan.return_value = [
            {'product_id': 99, 'order_type': 'buy', 'qty': 1.0, 'lead_time_days': 0}
        ]
        conn = MagicMock()
        result = run_mrp(conn)
    assert 'Product 99' in result[0]['product_name']


# ---------------------------------------------------------------------------
# _explode_to_wo
# ---------------------------------------------------------------------------

def test_explode_to_wo_no_bom_returns_zero():
    conn = _conn(fetchall=[])
    count = _explode_to_wo(conn, wo_id=1, product_id=5, wo_quantity=10.0)
    assert count == 0


def test_explode_to_wo_inserts_one_material_line():
    conn = _conn(fetchall=[
        {'component_id': 20, 'qty_required': 2.0, 'scrap_pct': 0.0, 'notes': ''}
    ])
    count = _explode_to_wo(conn, wo_id=1, product_id=5, wo_quantity=3.0)
    assert count == 1
    insert_sql = conn.execute.call_args_list[1][0][0]
    assert 'INSERT INTO wo_material' in insert_sql
    params = conn.execute.call_args_list[1][0][1]
    assert params[0] == 1   # wo_id
    assert params[1] == 20  # component_id
    assert params[2] == pytest.approx(6.0)  # qty_required * wo_quantity


def test_explode_to_wo_applies_scrap():
    conn = _conn(fetchall=[
        {'component_id': 10, 'qty_required': 10.0, 'scrap_pct': 10.0, 'notes': ''}
    ])
    _explode_to_wo(conn, wo_id=1, product_id=5, wo_quantity=1.0)
    params = conn.execute.call_args_list[1][0][1]
    assert params[2] == pytest.approx(11.0)  # 10 * 1.1


def test_explode_to_wo_uses_default_note_when_empty():
    conn = _conn(fetchall=[
        {'component_id': 10, 'qty_required': 1.0, 'scrap_pct': 0.0, 'notes': ''}
    ])
    _explode_to_wo(conn, wo_id=1, product_id=5, wo_quantity=1.0)
    params = conn.execute.call_args_list[1][0][1]
    assert params[3] == 'from BOM'


# ---------------------------------------------------------------------------
# release_plan
# ---------------------------------------------------------------------------

def test_release_plan_empty_list_returns_empty():
    conn = MagicMock()
    wos, pos = release_plan(conn, [], released_by='test@example.com')
    assert wos == []
    assert pos == []


def test_release_plan_make_item_creates_wo():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 42, 'wo_number': 'WO-2026-0001'}
    conn.execute.return_value.fetchall.return_value = []

    items = [{
        'product_id': 1,
        'product_name': 'Widget',
        'order_type': 'make',
        'qty': 5.0,
        'lead_time_days': 3,
        'due_date': '2026-07-01',
    }]

    with patch('manufacturing.mrp_web_core.next_wo_number', return_value='WO-2026-0001'), \
         patch('manufacturing.mrp_web_core.create_wo', return_value=42), \
         patch('manufacturing.mrp_web_core._explode_to_wo', return_value=0):
        wos, pos = release_plan(conn, items, released_by='test@example.com')

    assert len(wos) == 1
    assert wos[0]['wo_number'] == 'WO-2026-0001'
    assert wos[0]['product_name'] == 'Widget'
    assert pos == []


def test_release_plan_buy_item_creates_po():
    conn = MagicMock()

    items = [{
        'product_id': 2,
        'product_name': 'Steel Tube',
        'order_type': 'buy',
        'qty': 20.0,
        'lead_time_days': 7,
        'due_date': '2026-07-07',
    }]

    with patch('manufacturing.mrp_web_core.next_po_number', return_value='PO-2026-0001'), \
         patch('manufacturing.mrp_web_core.create_po', return_value=99), \
         patch('manufacturing.mrp_web_core.add_po_item') as mock_add:
        wos, pos = release_plan(conn, items, released_by='test@example.com')

    assert len(pos) == 1
    assert pos[0]['po_number'] == 'PO-2026-0001'
    assert pos[0]['product_name'] == 'Steel Tube'
    assert wos == []
    mock_add.assert_called_once()


def test_release_plan_mixed_creates_both():
    conn = MagicMock()

    items = [
        {'product_id': 1, 'product_name': 'Bike', 'order_type': 'make',
         'qty': 2.0, 'lead_time_days': 5, 'due_date': '2026-07-05'},
        {'product_id': 3, 'product_name': 'Tire', 'order_type': 'buy',
         'qty': 10.0, 'lead_time_days': 14, 'due_date': '2026-07-14'},
    ]

    with patch('manufacturing.mrp_web_core.next_wo_number', return_value='WO-001'), \
         patch('manufacturing.mrp_web_core.create_wo', return_value=1), \
         patch('manufacturing.mrp_web_core._explode_to_wo', return_value=0), \
         patch('manufacturing.mrp_web_core.next_po_number', return_value='PO-001'), \
         patch('manufacturing.mrp_web_core.create_po', return_value=10), \
         patch('manufacturing.mrp_web_core.add_po_item'):
        wos, pos = release_plan(conn, items, released_by='user@example.com')

    assert len(wos) == 1
    assert len(pos) == 1


def test_release_plan_wo_qty_rounded_to_int():
    conn = MagicMock()
    items = [
        {'product_id': 1, 'product_name': 'X', 'order_type': 'make',
         'qty': 3.7, 'lead_time_days': 1, 'due_date': '2026-07-01'},
    ]
    with patch('manufacturing.mrp_web_core.next_wo_number', return_value='WO-X'), \
         patch('manufacturing.mrp_web_core.create_wo', return_value=1) as mock_create, \
         patch('manufacturing.mrp_web_core._explode_to_wo', return_value=0):
        release_plan(conn, items, released_by='u@e.com')

    _, kwargs = mock_create.call_args
    assert kwargs['quantity'] == 4  # round(3.7) = 4


def test_release_plan_wo_qty_minimum_one():
    conn = MagicMock()
    items = [
        {'product_id': 1, 'product_name': 'X', 'order_type': 'make',
         'qty': 0.1, 'lead_time_days': 0, 'due_date': '2026-07-01'},
    ]
    with patch('manufacturing.mrp_web_core.next_wo_number', return_value='WO-X'), \
         patch('manufacturing.mrp_web_core.create_wo', return_value=1) as mock_create, \
         patch('manufacturing.mrp_web_core._explode_to_wo', return_value=0):
        release_plan(conn, items, released_by='u@e.com')

    _, kwargs = mock_create.call_args
    assert kwargs['quantity'] >= 1


def test_release_plan_does_not_commit():
    """release_plan must NOT commit — that's the caller's responsibility."""
    conn = MagicMock()
    with patch('manufacturing.mrp_web_core.next_po_number', return_value='P'), \
         patch('manufacturing.mrp_web_core.create_po', return_value=1), \
         patch('manufacturing.mrp_web_core.add_po_item'):
        release_plan(conn, [
            {'product_id': 1, 'product_name': 'X', 'order_type': 'buy',
             'qty': 1.0, 'lead_time_days': 0, 'due_date': '2026-07-01'}
        ], released_by='u@e.com')
    conn.commit.assert_not_called()
