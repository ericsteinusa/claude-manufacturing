"""Tests for scenario_planning_core — what-if MRP/capacity comparison."""

import datetime

import pytest

from manufacturing.scenario_planning_core import (
    create_scenario, add_demand_adjustment, add_capacity_adjustment,
    summarize_mrp, apply_capacity_adjustments, rank_bottlenecks, run_scenario,
)
import manufacturing.scenario_planning_core as scenario_planning_core


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


# ── CRUD basics ──────────────────────────────────────────────────────────

def test_create_scenario_returns_id():
    conn = _Conn(rows=[{'id': 3}])
    scenario_id = create_scenario(conn, 'Holiday Rush', created_by='eric')
    assert scenario_id == 3


def test_create_scenario_requires_name():
    conn = _Conn(rows=[{'id': 3}])
    with pytest.raises(ValueError):
        create_scenario(conn, '   ')


def test_add_demand_adjustment_requires_positive_qty():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_demand_adjustment(conn, 1, 10, qty=0, need_date='2026-08-01')


def test_add_capacity_adjustment_rejects_backwards_dates():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_capacity_adjustment(conn, 1, 5, date_from='2026-08-10',
                                date_to='2026-08-01', hours_per_day=16)


def test_add_capacity_adjustment_rejects_negative_hours():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_capacity_adjustment(conn, 1, 5, date_from='2026-08-01',
                                date_to='2026-08-10', hours_per_day=-1)


# ── summarize_mrp ─────────────────────────────────────────────────────────

def test_summarize_mrp_splits_make_and_buy():
    planned = [
        {'order_type': 'make', 'qty': 10},
        {'order_type': 'make', 'qty': 5},
        {'order_type': 'buy', 'qty': 100},
    ]
    summary = summarize_mrp(planned)
    assert summary['order_count'] == 3
    assert summary['make_count'] == 2
    assert summary['buy_count'] == 1
    assert summary['make_qty'] == 15
    assert summary['buy_qty'] == 100
    assert summary['total_qty'] == 115


def test_summarize_mrp_empty():
    summary = summarize_mrp([])
    assert summary['order_count'] == 0
    assert summary['total_qty'] == 0


# ── apply_capacity_adjustments ────────────────────────────────────────────

def _baseline_capacity():
    return [
        {
            'workcenter_id': 1, 'workcenter_name': 'Assembly',
            'days': [
                {'date': '2026-08-01', 'available': 8.0, 'booked': 6.0, 'pct': 75.0, 'over_capacity': False},
                {'date': '2026-08-02', 'available': 8.0, 'booked': 10.0, 'pct': 125.0, 'over_capacity': True},
            ],
        },
        {
            'workcenter_id': 2, 'workcenter_name': 'Paint',
            'days': [
                {'date': '2026-08-01', 'available': 8.0, 'booked': 2.0, 'pct': 25.0, 'over_capacity': False},
            ],
        },
    ]


def test_apply_capacity_adjustments_overrides_matching_window():
    baseline = _baseline_capacity()
    adjustments = [
        {'workcenter_id': 1, 'date_from': '2026-08-02', 'date_to': '2026-08-02', 'hours_per_day': 16.0},
    ]
    scenario = apply_capacity_adjustments(baseline, adjustments)
    day = scenario[0]['days'][1]
    assert day['available'] == 16.0
    assert day['over_capacity'] is False  # 10 booked vs 16 available now fits
    assert day['pct'] == pytest.approx(62.5)


def test_apply_capacity_adjustments_does_not_mutate_input():
    baseline = _baseline_capacity()
    adjustments = [
        {'workcenter_id': 1, 'date_from': '2026-08-02', 'date_to': '2026-08-02', 'hours_per_day': 16.0},
    ]
    apply_capacity_adjustments(baseline, adjustments)
    assert baseline[0]['days'][1]['available'] == 8.0  # untouched


def test_apply_capacity_adjustments_leaves_other_workcenters_untouched():
    baseline = _baseline_capacity()
    adjustments = [
        {'workcenter_id': 1, 'date_from': '2026-08-01', 'date_to': '2026-08-02', 'hours_per_day': 0.0},
    ]
    scenario = apply_capacity_adjustments(baseline, adjustments)
    assert scenario[1]['days'][0]['available'] == 8.0


def test_apply_capacity_adjustments_leaves_days_outside_window_untouched():
    baseline = _baseline_capacity()
    adjustments = [
        {'workcenter_id': 1, 'date_from': '2026-08-02', 'date_to': '2026-08-02', 'hours_per_day': 16.0},
    ]
    scenario = apply_capacity_adjustments(baseline, adjustments)
    assert scenario[0]['days'][0]['available'] == 8.0  # 08-01 not in the adjustment window


# ── rank_bottlenecks ──────────────────────────────────────────────────────

def test_rank_bottlenecks_sorts_by_utilization_desc():
    ranked = rank_bottlenecks(_baseline_capacity())
    assert ranked[0]['workcenter_name'] == 'Assembly'
    assert ranked[0]['utilization_pct'] > ranked[1]['utilization_pct']


def test_rank_bottlenecks_counts_over_capacity_days():
    ranked = rank_bottlenecks(_baseline_capacity())
    assembly = next(r for r in ranked if r['workcenter_name'] == 'Assembly')
    assert assembly['over_capacity_days'] == 1


# ── run_scenario ──────────────────────────────────────────────────────────

def test_run_scenario_raises_if_missing(monkeypatch):
    monkeypatch.setattr(scenario_planning_core, 'get_scenario', lambda conn, sid: None)
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='No scenario'):
        run_scenario(conn, 999)


def test_run_scenario_merges_demand_and_reruns_mrp(monkeypatch):
    monkeypatch.setattr(scenario_planning_core, 'get_scenario', lambda conn, sid: {'id': sid, 'name': 'Test'})
    monkeypatch.setattr(scenario_planning_core, 'list_demand_adjustments', lambda conn, sid: [
        {'product_id': 10, 'qty': 50, 'need_date': '2026-08-15'},
    ])
    monkeypatch.setattr(scenario_planning_core, 'list_capacity_adjustments', lambda conn, sid: [])

    calls = []

    def fake_run_mrp_dated(conn, include_forecast=False, extra_demand=None):
        calls.append(extra_demand)
        if extra_demand:
            return [{'order_type': 'buy', 'qty': 50}]
        return [{'order_type': 'buy', 'qty': 10}]

    monkeypatch.setattr(scenario_planning_core, 'run_mrp_dated', fake_run_mrp_dated)
    monkeypatch.setattr(scenario_planning_core, 'get_capacity_check', lambda conn, f, t: [])

    result = run_scenario(_Conn(rows=[]), 1, capacity_date_from='2026-08-01', capacity_date_to='2026-08-05')
    assert result['mrp_baseline']['total_qty'] == 10
    assert result['mrp_scenario']['total_qty'] == 50
    assert calls[0] is None  # baseline call has no extra demand
    assert calls[1] == {10: [(50, datetime.date(2026, 8, 15))]}


def test_run_scenario_normalizes_string_need_date_to_date(monkeypatch):
    """Regression test: get_demand_dated's real SO-derived dates come back
    as datetime.date (DATE column), but a scenario's need_date is stored
    as TEXT — merging a str into the same list plan_orders_dated sorts by
    need_date raises TypeError: '<' not supported between str and date."""
    monkeypatch.setattr(scenario_planning_core, 'get_scenario', lambda conn, sid: {'id': sid, 'name': 'Test'})
    monkeypatch.setattr(scenario_planning_core, 'list_demand_adjustments', lambda conn, sid: [
        {'product_id': 10, 'qty': 50, 'need_date': '2026-09-01'},
    ])
    monkeypatch.setattr(scenario_planning_core, 'list_capacity_adjustments', lambda conn, sid: [])

    captured = {}

    def fake_run_mrp_dated(conn, include_forecast=False, extra_demand=None):
        captured['extra_demand'] = extra_demand
        return []

    monkeypatch.setattr(scenario_planning_core, 'run_mrp_dated', fake_run_mrp_dated)
    monkeypatch.setattr(scenario_planning_core, 'get_capacity_check', lambda conn, f, t: [])

    run_scenario(_Conn(rows=[]), 1)
    qty, need_date = captured['extra_demand'][10][0]
    assert isinstance(need_date, datetime.date)
    assert need_date == datetime.date(2026, 9, 1)


def test_run_scenario_no_adjustments_scenario_equals_baseline(monkeypatch):
    monkeypatch.setattr(scenario_planning_core, 'get_scenario', lambda conn, sid: {'id': sid, 'name': 'Empty'})
    monkeypatch.setattr(scenario_planning_core, 'list_demand_adjustments', lambda conn, sid: [])
    monkeypatch.setattr(scenario_planning_core, 'list_capacity_adjustments', lambda conn, sid: [])
    monkeypatch.setattr(
        scenario_planning_core, 'run_mrp_dated',
        lambda conn, include_forecast=False, extra_demand=None: [{'order_type': 'buy', 'qty': 5}],
    )
    monkeypatch.setattr(scenario_planning_core, 'get_capacity_check', lambda conn, f, t: _baseline_capacity())

    result = run_scenario(_Conn(rows=[]), 1)
    assert result['mrp_baseline'] == result['mrp_scenario']
    assert result['capacity_baseline'] == result['capacity_scenario']
