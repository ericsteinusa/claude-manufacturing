"""Tests for abc_costing_core — activity-based costing vs. traditional overhead."""

import pytest

from manufacturing.abc_costing_core import (
    create_activity, update_activity, set_product_driver, set_product_output,
    compute_activity_rate, get_abc_overhead_for_product, compare_to_traditional,
    get_abc_summary_all_products, VARIANCE_FLAG_THRESHOLD_PCT,
)
import manufacturing.abc_costing_core as abc_costing_core


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


# ── CRUD basics ──────────────────────────────────────────────────────────

def test_create_activity_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    activity_id = create_activity(conn, 'Machine Setups', 50000.0, driver_uom='per setup')
    assert activity_id == 1


def test_create_activity_requires_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_activity(conn, '   ', 100.0)


def test_create_activity_rejects_negative_pool():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_activity(conn, 'Bad Pool', -5.0)


def test_update_activity_rejects_negative_pool():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        update_activity(conn, 1, cost_pool_amount=-10)


def test_set_product_driver_rejects_negative_qty():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_product_driver(conn, 1, 10, driver_qty=-1)


def test_set_product_output_rejects_negative_qty():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_product_output(conn, 10, output_qty=-1)


# ── compute_activity_rate ────────────────────────────────────────────────

def test_compute_activity_rate_divides_pool_by_total_driver_qty():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Setups', 'cost_pool_amount': 1000.0}],
        [{'total': 200.0}],
    ])
    rate = compute_activity_rate(conn, 1)
    assert rate == 5.0


def test_compute_activity_rate_none_when_no_driver_usage():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Setups', 'cost_pool_amount': 1000.0}],
        [{'total': 0.0}],
    ])
    assert compute_activity_rate(conn, 1) is None


def test_compute_activity_rate_raises_if_missing():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError, match='No activity'):
        compute_activity_rate(conn, 999)


# ── get_abc_overhead_for_product ─────────────────────────────────────────

def test_get_abc_overhead_for_product_allocates_and_divides_by_output(monkeypatch):
    monkeypatch.setattr(abc_costing_core, 'list_product_drivers', lambda conn, product_id=None, activity_id=None: [
        {'activity_id': 1, 'activity_name': 'Setups', 'driver_uom': 'per setup', 'driver_qty': 40.0},
    ])
    monkeypatch.setattr(abc_costing_core, 'compute_activity_rate', lambda conn, activity_id: 5.0)
    monkeypatch.setattr(abc_costing_core, 'get_product_output', lambda conn, product_id: {'output_qty': 100.0})

    result = get_abc_overhead_for_product(_Conn(), 10)
    assert result['total_allocated_cost'] == 200.0  # 5.0 * 40
    assert result['abc_overhead_per_unit'] == 2.0    # 200 / 100


def test_get_abc_overhead_for_product_none_per_unit_when_no_output(monkeypatch):
    monkeypatch.setattr(abc_costing_core, 'list_product_drivers', lambda conn, product_id=None, activity_id=None: [
        {'activity_id': 1, 'activity_name': 'Setups', 'driver_uom': '', 'driver_qty': 40.0},
    ])
    monkeypatch.setattr(abc_costing_core, 'compute_activity_rate', lambda conn, activity_id: 5.0)
    monkeypatch.setattr(abc_costing_core, 'get_product_output', lambda conn, product_id: None)

    result = get_abc_overhead_for_product(_Conn(), 10)
    assert result['abc_overhead_per_unit'] is None


# ── compare_to_traditional ───────────────────────────────────────────────

def test_compare_to_traditional_flags_large_variance(monkeypatch):
    monkeypatch.setattr(abc_costing_core, 'get_abc_overhead_for_product', lambda conn, product_id: {
        'product_id': product_id, 'activities': [], 'total_allocated_cost': 200.0,
        'output_qty': 100.0, 'abc_overhead_per_unit': 10.0,
    })
    monkeypatch.setattr(abc_costing_core, 'get_standard_cost', lambda conn, product_id: {
        'std_overhead_cost': 2.0,
    })
    result = compare_to_traditional(_Conn(), 10)
    assert result['variance'] == 8.0
    assert result['variance_pct'] == pytest.approx(400.0)
    assert result['flagged'] is True


def test_compare_to_traditional_not_flagged_when_close(monkeypatch):
    monkeypatch.setattr(abc_costing_core, 'get_abc_overhead_for_product', lambda conn, product_id: {
        'product_id': product_id, 'activities': [], 'total_allocated_cost': 100.0,
        'output_qty': 100.0, 'abc_overhead_per_unit': 5.0,
    })
    monkeypatch.setattr(abc_costing_core, 'get_standard_cost', lambda conn, product_id: {
        'std_overhead_cost': 4.9,
    })
    result = compare_to_traditional(_Conn(), 10)
    assert abs(result['variance_pct']) < VARIANCE_FLAG_THRESHOLD_PCT
    assert result['flagged'] is False


def test_compare_to_traditional_handles_missing_traditional_cost(monkeypatch):
    monkeypatch.setattr(abc_costing_core, 'get_abc_overhead_for_product', lambda conn, product_id: {
        'product_id': product_id, 'activities': [], 'total_allocated_cost': 100.0,
        'output_qty': 100.0, 'abc_overhead_per_unit': 5.0,
    })
    monkeypatch.setattr(abc_costing_core, 'get_standard_cost', lambda conn, product_id: None)
    result = compare_to_traditional(_Conn(), 10)
    assert result['traditional_overhead_per_unit'] is None
    assert result['variance'] is None
    assert result['flagged'] is False


def test_compare_to_traditional_flags_when_traditional_is_zero(monkeypatch):
    monkeypatch.setattr(abc_costing_core, 'get_abc_overhead_for_product', lambda conn, product_id: {
        'product_id': product_id, 'activities': [], 'total_allocated_cost': 50.0,
        'output_qty': 100.0, 'abc_overhead_per_unit': 0.5,
    })
    monkeypatch.setattr(abc_costing_core, 'get_standard_cost', lambda conn, product_id: {
        'std_overhead_cost': 0.0,
    })
    result = compare_to_traditional(_Conn(), 10)
    assert result['flagged'] is True


# ── get_abc_summary_all_products ─────────────────────────────────────────

def test_get_abc_summary_all_products_sorts_by_absolute_variance(monkeypatch):
    conn = _Conn(rows=[
        {'product_id': 1, 'product_name': 'Small Variance Product'},
        {'product_id': 2, 'product_name': 'Big Variance Product'},
    ])

    def fake_compare(conn, product_id):
        return {'variance': 1.0 if product_id == 1 else -20.0}

    monkeypatch.setattr(abc_costing_core, 'compare_to_traditional', fake_compare)
    summary = get_abc_summary_all_products(conn)
    assert summary[0]['product_name'] == 'Big Variance Product'
    assert summary[1]['product_name'] == 'Small Variance Product'
