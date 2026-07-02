"""
Tests for bom_web_core.py — Qt-free BOM data layer.
"""

import pytest
from unittest.mock import MagicMock

from manufacturing.bom_web_core import (
    list_products, get_product, get_bom,
    add_bom_line, update_bom_line, delete_bom_line,
    update_item_master, explode_bom,
    ITEM_TYPES,
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
    """Return a dict that acts as a psycopg2 row (dict-like)."""
    return kw


# ---------------------------------------------------------------------------
# ITEM_TYPES
# ---------------------------------------------------------------------------

def test_item_types_contains_make():
    assert 'make' in ITEM_TYPES


def test_item_types_contains_buy():
    assert 'buy' in ITEM_TYPES


# ---------------------------------------------------------------------------
# list_products
# ---------------------------------------------------------------------------

def test_list_products_no_filter():
    conn = _conn(fetchall=[
        {'id': 1, 'name': 'A', 'item_type': 'make', 'uom': 'ea',
         'lead_time_days': 1, 'amount': 10, 'reorder_point': 5,
         'component_count': 3},
    ])
    result = list_products(conn)
    assert len(result) == 1
    assert result[0]['name'] == 'A'


def test_list_products_filters_by_item_type():
    conn = _conn(fetchall=[])
    list_products(conn, item_type='make')
    sql = conn.execute.call_args[0][0]
    assert 'item_type' in sql


def test_list_products_has_bom_true_filters_zero_count():
    conn = _conn(fetchall=[
        {'id': 1, 'name': 'A', 'item_type': 'make', 'uom': 'ea',
         'lead_time_days': 0, 'amount': 0, 'reorder_point': 0, 'component_count': 2},
        {'id': 2, 'name': 'B', 'item_type': 'buy', 'uom': 'ea',
         'lead_time_days': 0, 'amount': 0, 'reorder_point': 0, 'component_count': 0},
    ])
    result = list_products(conn, has_bom=True)
    assert len(result) == 1
    assert result[0]['name'] == 'A'


def test_list_products_has_bom_false_filters_nonzero():
    conn = _conn(fetchall=[
        {'id': 1, 'name': 'A', 'item_type': 'make', 'uom': 'ea',
         'lead_time_days': 0, 'amount': 0, 'reorder_point': 0, 'component_count': 2},
        {'id': 2, 'name': 'B', 'item_type': 'buy', 'uom': 'ea',
         'lead_time_days': 0, 'amount': 0, 'reorder_point': 0, 'component_count': 0},
    ])
    result = list_products(conn, has_bom=False)
    assert len(result) == 1
    assert result[0]['name'] == 'B'


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------

def test_get_product_returns_dict():
    conn = _conn(fetchone={'id': 5, 'name': 'Widget', 'item_type': 'make',
                           'uom': 'ea', 'lead_time_days': 3,
                           'amount': 0, 'reorder_point': 0})
    result = get_product(conn, 5)
    assert result is not None
    assert result['name'] == 'Widget'


def test_get_product_returns_none_when_missing():
    conn = _conn(fetchone=None)
    assert get_product(conn, 999) is None


# ---------------------------------------------------------------------------
# get_bom
# ---------------------------------------------------------------------------

def test_get_bom_returns_list():
    conn = _conn(fetchall=[
        {'id': 1, 'component_id': 10, 'qty_required': 2.0, 'scrap_pct': 0.0,
         'unit': 'ea', 'notes': '', 'component_name': 'Part A',
         'item_type': 'buy', 'lead_time_days': 7, 'uom': 'ea', 'on_hand': 50},
    ])
    result = get_bom(conn, 1)
    assert len(result) == 1
    assert result[0]['component_name'] == 'Part A'


def test_get_bom_empty_when_no_components():
    conn = _conn(fetchall=[])
    assert get_bom(conn, 99) == []


# ---------------------------------------------------------------------------
# add_bom_line
# ---------------------------------------------------------------------------

def test_add_bom_line_rejects_self_reference():
    conn = _conn(fetchall=[], fetchone=(1,))
    ok, msg = add_bom_line(conn, 5, 5, qty_required=1.0, unit='ea')
    assert ok is False
    assert 'itself' in msg


def test_add_bom_line_rejects_cycle():
    # Existing edges: 5 -> 3. Adding 3 -> 5 creates cycle.
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        (5, 3),  # product_id=5, component_id=3
    ]
    conn.execute.return_value.fetchone.return_value = None
    ok, msg = add_bom_line(conn, 3, 5, qty_required=1.0, unit='ea')
    assert ok is False
    assert 'circular' in msg.lower()


def test_add_bom_line_rejects_duplicate():
    conn = MagicMock()
    # No existing edges
    conn.execute.return_value.fetchall.return_value = []
    # But duplicate check finds existing row
    conn.execute.return_value.fetchone.return_value = {'id': 99}
    ok, msg = add_bom_line(conn, 1, 2, qty_required=1.0, unit='ea')
    assert ok is False
    assert 'already' in msg


def test_add_bom_line_success():
    conn = MagicMock()
    # fetchall = no existing edges (for cycle check and duplicate check)
    conn.execute.return_value.fetchall.return_value = []
    # Duplicate check: no existing row; INSERT RETURNING id
    responses = [
        MagicMock(fetchall=lambda: [], fetchone=lambda: None),  # cycle check
        MagicMock(fetchall=lambda: [], fetchone=lambda: None),  # duplicate check
        MagicMock(fetchall=lambda: [], fetchone=lambda: (42,)),  # INSERT
    ]
    conn.execute.side_effect = responses
    ok, msg = add_bom_line(conn, 1, 2, qty_required=3.0, unit='ea')
    assert ok is True
    assert msg == '42'


def test_add_bom_line_clamps_negative_qty():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    conn.execute.return_value.fetchone.return_value = None
    # Should clamp qty to 0 (not raise)
    responses = [
        MagicMock(fetchall=lambda: [], fetchone=lambda: None),
        MagicMock(fetchall=lambda: [], fetchone=lambda: None),
        MagicMock(fetchall=lambda: [], fetchone=lambda: (1,)),
    ]
    conn.execute.side_effect = responses
    ok, _ = add_bom_line(conn, 1, 2, qty_required=-5, unit='ea')
    assert ok is True


# ---------------------------------------------------------------------------
# update_bom_line
# ---------------------------------------------------------------------------

def test_update_bom_line_sends_update():
    conn = _conn()
    update_bom_line(conn, line_id=7, qty_required=4.0, unit='kg',
                    notes='test', scrap_pct=2.5)
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE bom' in sql
    assert 4.0 in params
    assert 'kg' in params
    assert 2.5 in params


def test_update_bom_line_clamps_scrap():
    conn = _conn()
    update_bom_line(conn, 1, qty_required=1.0, unit='ea', scrap_pct=-10)
    _, params = conn.execute.call_args[0]
    # scrap_pct should be 0.0 (clamped)
    assert 0.0 in params


# ---------------------------------------------------------------------------
# delete_bom_line
# ---------------------------------------------------------------------------

def test_delete_bom_line_executes_delete():
    conn = _conn()
    result = delete_bom_line(conn, line_id=3)
    assert result is True
    sql = conn.execute.call_args[0][0]
    assert 'DELETE' in sql
    assert 'bom' in sql.lower()


# ---------------------------------------------------------------------------
# update_item_master
# ---------------------------------------------------------------------------

def test_update_item_master_valid():
    conn = _conn()
    update_item_master(conn, product_id=1, item_type='make',
                       lead_time_days=5, uom='kg')
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE product' in sql
    assert 'make' in params
    assert 5 in params
    assert 'kg' in params


def test_update_item_master_invalid_type_defaults_to_buy():
    conn = _conn()
    update_item_master(conn, 1, item_type='invalid', lead_time_days=0, uom='ea')
    _, params = conn.execute.call_args[0]
    assert 'buy' in params


def test_update_item_master_negative_lead_time_clamped():
    conn = _conn()
    update_item_master(conn, 1, item_type='buy', lead_time_days=-3, uom='ea')
    _, params = conn.execute.call_args[0]
    assert 0 in params


def test_update_item_master_empty_uom_defaults_to_ea():
    conn = _conn()
    update_item_master(conn, 1, item_type='buy', lead_time_days=0, uom='')
    _, params = conn.execute.call_args[0]
    assert 'ea' in params


# ---------------------------------------------------------------------------
# explode_bom
# ---------------------------------------------------------------------------

def test_explode_bom_empty_when_no_components():
    conn = _conn(fetchall=[])
    result = explode_bom(conn, product_id=1, qty=1.0)
    assert result == []


def test_explode_bom_single_level():
    component_row = {
        'id': 10, 'component_id': 20, 'qty_required': 2.0, 'scrap_pct': 0.0,
        'unit': 'ea', 'notes': '', 'component_name': 'Part X',
        'item_type': 'buy', 'lead_time_days': 7, 'uom': 'ea', 'on_hand': 100,
    }
    conn = MagicMock()
    # First call: get_bom(product_id=1) → one component
    # Second call: get_bom(component_id=20) — it's 'buy', so not recursed
    conn.execute.return_value.fetchall.return_value = [component_row]
    result = explode_bom(conn, product_id=1, qty=3.0)
    assert len(result) == 1
    assert result[0]['component_name'] == 'Part X'
    assert result[0]['qty_needed'] == pytest.approx(6.0)  # 2.0 * 3.0
    assert result[0]['depth'] == 0


def test_explode_bom_qty_scales_correctly():
    component_row = {
        'id': 1, 'component_id': 99, 'qty_required': 4.0, 'scrap_pct': 0.0,
        'unit': 'ea', 'notes': '', 'component_name': 'Widget',
        'item_type': 'buy', 'lead_time_days': 0, 'uom': 'ea', 'on_hand': 0,
    }
    conn = _conn(fetchall=[component_row])
    result = explode_bom(conn, product_id=1, qty=5.0)
    assert result[0]['qty_needed'] == pytest.approx(20.0)  # 4 * 5


def test_explode_bom_scrap_inflates_qty():
    component_row = {
        'id': 1, 'component_id': 99, 'qty_required': 10.0, 'scrap_pct': 10.0,
        'unit': 'ea', 'notes': '', 'component_name': 'Widget',
        'item_type': 'buy', 'lead_time_days': 0, 'uom': 'ea', 'on_hand': 0,
    }
    conn = _conn(fetchall=[component_row])
    result = explode_bom(conn, product_id=1, qty=1.0)
    assert result[0]['qty_needed'] == pytest.approx(11.0)  # 10 * 1.1


def test_explode_bom_depth_annotated():
    conn = _conn(fetchall=[
        {'id': 1, 'component_id': 50, 'qty_required': 1.0, 'scrap_pct': 0.0,
         'unit': 'ea', 'notes': '', 'component_name': 'Sub',
         'item_type': 'buy', 'lead_time_days': 0, 'uom': 'ea', 'on_hand': 0},
    ])
    result = explode_bom(conn, product_id=1, qty=1.0)
    assert result[0]['depth'] == 0


def test_explode_bom_cycle_guard_visited():
    """Visited set prevents infinite recursion even if cycle guard missed one."""
    # product 1 → component 2 (make) → component 1 (would loop)
    calls = {'n': 0}

    def fake_execute(sql, params=None):
        m = MagicMock()
        pid = (params or [None])[0] if params else None
        if pid == 1:
            m.fetchall.return_value = [{
                'id': 10, 'component_id': 2, 'qty_required': 1.0, 'scrap_pct': 0.0,
                'unit': 'ea', 'notes': '', 'component_name': 'Sub',
                'item_type': 'make', 'lead_time_days': 0, 'uom': 'ea', 'on_hand': 0,
            }]
        elif pid == 2:
            m.fetchall.return_value = [{
                'id': 11, 'component_id': 1, 'qty_required': 1.0, 'scrap_pct': 0.0,
                'unit': 'ea', 'notes': '', 'component_name': 'Parent',
                'item_type': 'make', 'lead_time_days': 0, 'uom': 'ea', 'on_hand': 0,
            }]
        else:
            m.fetchall.return_value = []
        calls['n'] += 1
        assert calls['n'] < 20, "Infinite recursion detected"
        return m

    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    # Should not raise — visited set stops the cycle
    result = explode_bom(conn, product_id=1, qty=1.0)
    # We get product1→sub (depth 0), sub→parent (depth 1), then parent is visited
    assert len(result) == 2
