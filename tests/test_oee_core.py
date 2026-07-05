"""Tests for oee_core — workcenter-based OEE (Availability x Performance x Quality)."""

from manufacturing.oee_core import (
    _clamp, _oee_from_totals, _period_days,
    get_workcenter_oee, list_workcenter_oee, get_overall_oee, get_oee_trend,
)


# ── fake DB infrastructure (mirrors test_costing_core.py's _MultiConn) ──────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _MultiConn:
    """Fake connection whose responses are driven by a queue of row-sets."""

    def __init__(self, responses):
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])


# ── pure helpers ─────────────────────────────────────────────────────────

def test_clamp_within_range():
    assert _clamp(0.5) == 0.5


def test_clamp_caps_above_one():
    assert _clamp(1.5) == 1.0


def test_clamp_floors_below_zero():
    assert _clamp(-0.2) == 0.0


def test_period_days_inclusive():
    assert _period_days('2026-06-01', '2026-06-07') == 7


def test_period_days_same_day_is_one():
    assert _period_days('2026-06-01', '2026-06-01') == 1


def test_oee_from_totals_basic_math():
    # 5-day period, 8h/day capacity = 40 scheduled hours, 4h downtime
    # -> availability = 36/40 = 90%
    # std 18h / actual 20h -> performance = 90%
    # 100 qty, 5 scrap -> quality = 95%
    result = _oee_from_totals(8.0, 5, 4.0, 18.0, 20.0, 100.0, 5.0)
    assert result['availability_pct'] == 90.0
    assert result['performance_pct'] == 90.0
    assert result['quality_pct'] == 95.0
    assert result['oee_pct'] == round(0.9 * 0.9 * 0.95 * 100, 1)


def test_oee_from_totals_clamps_performance_over_100pct():
    # actual_hours faster than std_hours would exceed 100% — must clamp
    result = _oee_from_totals(8.0, 1, 0.0, 10.0, 4.0, 10.0, 0.0)
    assert result['performance_pct'] == 100.0


def test_oee_from_totals_zero_actual_hours_gives_zero_performance():
    result = _oee_from_totals(8.0, 1, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert result['performance_pct'] == 0.0
    assert result['oee_pct'] == 0.0


def test_oee_from_totals_zero_qty_defaults_quality_to_full():
    result = _oee_from_totals(8.0, 1, 0.0, 4.0, 4.0, 0.0, 0.0)
    assert result['quality_pct'] == 100.0


def test_oee_from_totals_zero_capacity_gives_zero_availability():
    result = _oee_from_totals(0.0, 1, 0.0, 4.0, 4.0, 10.0, 0.0)
    assert result['availability_pct'] == 0.0


# ── get_workcenter_oee ───────────────────────────────────────────────────

def test_get_workcenter_oee_missing_workcenter_returns_none():
    conn = _MultiConn([[]])  # workcenter lookup returns no rows
    result = get_workcenter_oee(conn, 99, '2026-06-01', '2026-06-07')
    assert result is None


def test_get_workcenter_oee_computes_expected_breakdown():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Laser Cutter', 'capacity_hours_per_day': 8.0}],
        [{'total_std_hours': 18.0, 'total_actual_hours': 20.0,
          'total_qty': 100.0, 'total_scrap': 5.0}],
        [{'total_hours': 4.0}],
    ])
    result = get_workcenter_oee(conn, 1, '2026-06-01', '2026-06-05')
    assert result['workcenter_id'] == 1
    assert result['workcenter_name'] == 'Laser Cutter'
    assert result['availability_pct'] == 90.0
    assert result['performance_pct'] == 90.0
    assert result['quality_pct'] == 95.0


def test_get_workcenter_oee_downtime_query_matches_workcenter_name():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Laser Cutter', 'capacity_hours_per_day': 8.0}],
        [{'total_std_hours': 0.0, 'total_actual_hours': 0.0,
          'total_qty': 0.0, 'total_scrap': 0.0}],
        [{'total_hours': 0.0}],
    ])
    get_workcenter_oee(conn, 1, '2026-06-01', '2026-06-05')
    downtime_call_params = conn.calls[2][1]
    assert downtime_call_params == ['Laser Cutter', '2026-06-01', '2026-06-05']


# ── list_workcenter_oee ──────────────────────────────────────────────────

def test_list_workcenter_oee_iterates_all_active_workcenters():
    conn = _MultiConn([
        [{'id': 1}, {'id': 2}],  # active workcenter ids
        # workcenter 1
        [{'id': 1, 'name': 'Laser Cutter', 'capacity_hours_per_day': 8.0}],
        [{'total_std_hours': 8.0, 'total_actual_hours': 8.0,
          'total_qty': 10.0, 'total_scrap': 0.0}],
        [{'total_hours': 0.0}],
        # workcenter 2
        [{'id': 2, 'name': 'CNC Mill', 'capacity_hours_per_day': 8.0}],
        [{'total_std_hours': 4.0, 'total_actual_hours': 8.0,
          'total_qty': 10.0, 'total_scrap': 2.0}],
        [{'total_hours': 2.0}],
    ])
    results = list_workcenter_oee(conn, '2026-06-01', '2026-06-01')
    assert [r['workcenter_name'] for r in results] == ['Laser Cutter', 'CNC Mill']
    assert results[0]['oee_pct'] == 100.0  # full capacity, on-target, no scrap
    assert results[1]['performance_pct'] == 50.0  # 4h std / 8h actual


# ── get_overall_oee ──────────────────────────────────────────────────────

def test_get_overall_oee_no_workcenters_gives_zero():
    conn = _MultiConn([[]])
    result = get_overall_oee(conn, '2026-06-01', '2026-06-07')
    assert result['oee_pct'] == 0.0


def test_get_overall_oee_sums_across_workcenters():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Laser Cutter', 'capacity_hours_per_day': 8.0},
         {'id': 2, 'name': 'CNC Mill', 'capacity_hours_per_day': 8.0}],
        [{'total_std_hours': 7.0, 'total_actual_hours': 7.0,
          'total_qty': 10.0, 'total_scrap': 0.0}],
        [{'total_hours': 0.0}],
        [{'total_std_hours': 7.0, 'total_actual_hours': 7.0,
          'total_qty': 10.0, 'total_scrap': 0.0}],
        [{'total_hours': 0.0}],
    ])
    result = get_overall_oee(conn, '2026-06-01', '2026-06-01')
    assert result['oee_pct'] == 100.0


# ── get_oee_trend ────────────────────────────────────────────────────────

def test_get_oee_trend_returns_requested_number_of_weeks():
    conn = _MultiConn([[]])  # no active workcenters
    trend = get_oee_trend(conn, end_date='2026-06-30', weeks=4)
    assert len(trend) == 4


def test_get_oee_trend_weeks_ordered_oldest_first():
    conn = _MultiConn([[]])
    trend = get_oee_trend(conn, end_date='2026-06-30', weeks=3)
    assert trend[-1]['week_end'] == '2026-06-30'
    assert trend[0]['week_end'] < trend[-1]['week_end']


def test_get_oee_trend_no_workcenters_gives_zero_oee():
    conn = _MultiConn([[]])
    trend = get_oee_trend(conn, end_date='2026-06-30', weeks=1)
    assert trend[0]['oee_pct'] == 0.0


def test_get_oee_trend_aggregates_across_workcenters():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Laser Cutter', 'capacity_hours_per_day': 8.0}],
        # single week, single workcenter: totals then downtime
        [{'total_std_hours': 7.0, 'total_actual_hours': 7.0,
          'total_qty': 10.0, 'total_scrap': 0.0}],
        [{'total_hours': 0.0}],
    ])
    trend = get_oee_trend(conn, end_date='2026-06-07', weeks=1)
    assert trend[0]['oee_pct'] == 100.0
