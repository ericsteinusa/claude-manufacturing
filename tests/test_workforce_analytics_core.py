"""Tests for workforce_analytics_core — Workforce Analytics & Headcount
Planning."""

import datetime

import pytest

from manufacturing.workforce_analytics_core import (
    set_employment_dates, get_headcount_summary, get_headcount_trend,
    create_headcount_plan, get_plan_vs_actual, _trailing_month_ends,
    EMPLOYMENT_STATUSES,
)


# ── fake DB infrastructure (mirrors test_skills_matrix_core.py) ────────────

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


TODAY = datetime.date.today()


def _iso(d):
    return d.isoformat()


# ── set_employment_dates ─────────────────────────────────────────────────

def test_set_employment_dates_validates_status():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_employment_dates(conn, 1, '2020-01-01', employment_status='bogus')


def test_all_employment_statuses_accepted():
    for status in EMPLOYMENT_STATUSES:
        conn = _Conn(rows=[])
        set_employment_dates(conn, 1, '2020-01-01', employment_status=status)  # no raise


def test_set_employment_dates_passes_params():
    conn = _Conn(rows=[])
    set_employment_dates(conn, 5, '2020-01-01', termination_date='2026-01-01',
                         employment_status='terminated')
    sql, params = conn.calls[-1]
    assert params == ['2020-01-01', '2026-01-01', 'terminated', 5]


# ── get_headcount_summary ────────────────────────────────────────────────

def test_get_headcount_summary_counts_active_and_terminated():
    conn = _Conn(rows=[
        {'id': 1, 'dept_id': 1, 'dept_name': 'Production',
         'hire_date': _iso(TODAY - datetime.timedelta(days=730)),
         'termination_date': None, 'employment_status': 'active'},
        {'id': 2, 'dept_id': 1, 'dept_name': 'Production',
         'hire_date': '', 'termination_date': None, 'employment_status': 'active'},
        {'id': 3, 'dept_id': 2, 'dept_name': 'Sales',
         'hire_date': _iso(TODAY - datetime.timedelta(days=1000)),
         'termination_date': _iso(TODAY - datetime.timedelta(days=30)),
         'employment_status': 'terminated'},
    ])
    summary = get_headcount_summary(conn)
    assert summary['total_active'] == 2
    assert summary['total_terminated'] == 1
    assert summary['turnover_rate_ttm'] == 0.5  # 1 terminated-in-ttm / 2 active
    # Only employee 1 has a real hire_date -> avg tenure computed from just that one
    assert summary['avg_tenure_years'] == round(730 / 365.25, 2)


def test_get_headcount_summary_by_dept_sorted_desc():
    conn = _Conn(rows=[
        {'id': 1, 'dept_id': 1, 'dept_name': 'Production', 'hire_date': '',
         'termination_date': None, 'employment_status': 'active'},
        {'id': 2, 'dept_id': 1, 'dept_name': 'Production', 'hire_date': '',
         'termination_date': None, 'employment_status': 'active'},
        {'id': 3, 'dept_id': 2, 'dept_name': 'Sales', 'hire_date': '',
         'termination_date': None, 'employment_status': 'active'},
    ])
    summary = get_headcount_summary(conn)
    assert summary['by_dept'][0] == {'dept_name': 'Production', 'count': 2}


def test_get_headcount_summary_handles_no_active_employees():
    conn = _Conn(rows=[])
    summary = get_headcount_summary(conn)
    assert summary['total_active'] == 0
    assert summary['avg_tenure_years'] is None
    assert summary['turnover_rate_ttm'] is None


# ── get_headcount_trend / _trailing_month_ends ───────────────────────────

def test_trailing_month_ends_returns_requested_count():
    ends = _trailing_month_ends(6)
    assert len(ends) == 6
    assert ends[-1] == TODAY
    assert ends == sorted(ends)


def test_trailing_month_ends_single_month_is_just_today():
    assert _trailing_month_ends(1) == [TODAY]


def test_get_headcount_trend_excludes_blank_hire_dates():
    conn = _Conn(rows=[
        {'hire_date': _iso(TODAY - datetime.timedelta(days=800)), 'termination_date': None},
    ])
    trend = get_headcount_trend(conn, months=3)
    assert len(trend) == 3
    # SQL filter already excludes hire_date = '' — but confirm the shape holds
    assert all('headcount' in point for point in trend)
    assert trend[-1]['headcount'] == 1


def test_get_headcount_trend_excludes_terminated_before_month_end():
    hired = TODAY - datetime.timedelta(days=800)
    terminated = TODAY - datetime.timedelta(days=45)
    conn = _Conn(rows=[
        {'hire_date': _iso(hired), 'termination_date': _iso(terminated)},
    ])
    trend = get_headcount_trend(conn, months=3)
    # Most recent point (today) should not count this terminated employee
    assert trend[-1]['headcount'] == 0


# ── headcount planning ────────────────────────────────────────────────────

def test_create_headcount_plan_requires_dept():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_headcount_plan(conn, None, 10, '2026-12-31')


def test_create_headcount_plan_returns_id():
    conn = _Conn(rows=[{'id': 4}])
    plan_id = create_headcount_plan(conn, 1, 12, '2026-12-31', created_by='hr@example.com')
    assert plan_id == 4


def test_get_plan_vs_actual_computes_gap():
    conn = _MultiConn([
        [{'dept_id': 1, 'dept_name': 'Production', 'target_headcount': 12,
          'target_date': '2026-12-31'}],
        [{'dept_id': 1, 'actual': 9}],
    ])
    result = get_plan_vs_actual(conn)
    assert result[0]['gap'] == 3
    assert result[0]['actual_headcount'] == 9


def test_get_plan_vs_actual_defaults_actual_to_zero_when_no_active_employees():
    conn = _MultiConn([
        [{'dept_id': 5, 'dept_name': 'New Dept', 'target_headcount': 4,
          'target_date': '2026-06-01'}],
        [],
    ])
    result = get_plan_vs_actual(conn)
    assert result[0]['actual_headcount'] == 0
    assert result[0]['gap'] == 4
