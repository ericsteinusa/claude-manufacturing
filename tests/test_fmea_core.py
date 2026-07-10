"""Tests for fmea_core — control plans and FMEA risk scoring."""

import pytest

from manufacturing.fmea_core import (
    rpn_risk_level, create_control_plan, update_control_plan_status,
    add_control_plan_item, update_control_plan_item, get_high_risk_items,
)


# ── fake DB infrastructure (mirrors test_price_list_core.py) ───────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)


class _MultiConn:
    def __init__(self, responses):
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])


# ── rpn_risk_level ────────────────────────────────────────────────────────

def test_rpn_risk_level_buckets():
    assert rpn_risk_level(10) == 'low'
    assert rpn_risk_level(49) == 'low'
    assert rpn_risk_level(50) == 'medium'
    assert rpn_risk_level(99) == 'medium'
    assert rpn_risk_level(100) == 'high'
    assert rpn_risk_level(199) == 'high'
    assert rpn_risk_level(200) == 'critical'
    assert rpn_risk_level(1000) == 'critical'


# ── control plan CRUD ────────────────────────────────────────────────────

def test_create_control_plan_returns_id():
    conn = _Conn(rows=[{'id': 4}])
    plan_id = create_control_plan(conn, 10, 'Frame Assembly Control Plan')
    assert plan_id == 4


def test_create_control_plan_requires_name():
    conn = _Conn(rows=[{'id': 4}])
    with pytest.raises(ValueError):
        create_control_plan(conn, 10, '   ')


def test_update_control_plan_status_validates():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        update_control_plan_status(conn, 1, 'bogus')


def test_update_control_plan_status_accepts_known_value():
    conn = _Conn(rows=[])
    update_control_plan_status(conn, 1, 'active')  # no raise
    assert conn.calls[-1][1] == ['active', 1]


# ── control plan items / RPN computation ─────────────────────────────────

def test_add_control_plan_item_computes_rpn():
    conn = _Conn(rows=[{'id': 9}])
    item_id = add_control_plan_item(
        conn, 1, 'Bore Diameter', severity=8, occurrence=4, detection=3)
    assert item_id == 9
    # rpn = 8*4*3 = 96, must be among the inserted params
    assert 96 in conn.calls[-1][1]


def test_add_control_plan_item_requires_characteristic():
    conn = _Conn(rows=[{'id': 9}])
    with pytest.raises(ValueError):
        add_control_plan_item(conn, 1, '   ', severity=1, occurrence=1, detection=1)


@pytest.mark.parametrize('field,value', [
    ('severity', 0), ('severity', 11), ('occurrence', -1), ('detection', 15),
])
def test_add_control_plan_item_rejects_out_of_range_ratings(field, value):
    conn = _Conn(rows=[{'id': 9}])
    kwargs = {'severity': 5, 'occurrence': 5, 'detection': 5}
    kwargs[field] = value
    with pytest.raises(ValueError):
        add_control_plan_item(conn, 1, 'Test Characteristic', **kwargs)


def test_update_control_plan_item_recomputes_rpn():
    conn = _MultiConn([
        [{'id': 5, 'severity': 8, 'occurrence': 4, 'detection': 3, 'rpn': 96}],  # get_control_plan_item lookup
        [],  # UPDATE
    ])
    update_control_plan_item(conn, 5, detection=10)
    update_sql, update_params = conn.calls[-1]
    assert 'UPDATE control_plan_item' in update_sql
    # new rpn = 8 * 4 * 10 = 320
    assert 320 in update_params


def test_update_control_plan_item_ignores_unknown_fields():
    conn = _Conn(rows=[])
    update_control_plan_item(conn, 5, bogus='x')
    assert conn.calls == []


def test_update_control_plan_item_validates_new_rating():
    conn = _MultiConn([
        [{'id': 5, 'severity': 8, 'occurrence': 4, 'detection': 3, 'rpn': 96}],
    ])
    with pytest.raises(ValueError):
        update_control_plan_item(conn, 5, severity=99)


# ── risk register ────────────────────────────────────────────────────────

def test_get_high_risk_items_passes_threshold_param():
    conn = _Conn(rows=[])
    get_high_risk_items(conn, threshold=150)
    assert conn.calls[-1][1] == [150]


def test_get_high_risk_items_returns_rows():
    conn = _Conn(rows=[{'characteristic': 'Bore Diameter', 'rpn': 320}])
    items = get_high_risk_items(conn)
    assert items[0]['rpn'] == 320
