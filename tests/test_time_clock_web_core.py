"""Tests for manufacturing.time_clock_web_core — OT and schedule helpers."""

from datetime import datetime

from manufacturing.time_clock_web_core import (
    compute_ot_for_entries,
    get_ot_report,
    get_ot_report_all,
    get_schedule_summary,
    OT_THRESHOLD_DAILY,
    OT_THRESHOLD_WEEKLY,
    STANDARD_DAILY_HOURS,
    STANDARD_WEEKLY_HOURS,
)


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeCursor(self.rows)

    @property
    def last_sql(self):
        return self.calls[-1][0] if self.calls else ''

    @property
    def last_params(self):
        return self.calls[-1][1] if self.calls else []


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------

def test_constants_reasonable():
    assert OT_THRESHOLD_DAILY == 8.0
    assert OT_THRESHOLD_WEEKLY == 40.0
    assert STANDARD_DAILY_HOURS > 0
    assert STANDARD_WEEKLY_HOURS > 0


# ---------------------------------------------------------------------------
# compute_ot_for_entries
# ---------------------------------------------------------------------------

def _make_entry(date_str: str, hours: float) -> dict:
    return {
        'clock_in': f'{date_str} 08:00:00',
        'clock_out': None,
        'hours': hours,
        'in_progress': False,
    }


def test_compute_ot_no_overtime():
    entries = [_make_entry('2026-06-23', 7.5)]
    result = compute_ot_for_entries(entries)
    assert result['ot_hours'] == 0.0
    assert abs(result['total_hours'] - 7.5) < 0.01


def test_compute_ot_daily_overtime():
    entries = [_make_entry('2026-06-23', 10.0)]
    result = compute_ot_for_entries(entries)
    assert abs(result['daily_ot'] - 2.0) < 0.01
    assert result['ot_hours'] >= 2.0


def test_compute_ot_weekly_overtime():
    # Mon-Fri of a single week × 9 hours = 45 total → weekly OT = 5 h
    # 2026-06-22 is a Monday
    week_days = ['2026-06-22', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26']
    entries = [_make_entry(d, 9.0) for d in week_days]
    result = compute_ot_for_entries(entries)
    assert result['total_hours'] == 45.0
    assert result['weekly_ot'] >= 5.0
    assert result['ot_hours'] > 0


def test_compute_ot_zero_entries():
    result = compute_ot_for_entries([])
    assert result['total_hours'] == 0.0
    assert result['ot_hours'] == 0.0
    assert result['by_day'] == []
    assert result['by_week'] == []


def test_compute_ot_by_day_aggregation():
    # Two entries on the same day
    entries = [
        _make_entry('2026-06-23', 5.0),
        _make_entry('2026-06-23', 4.0),  # total 9 h → 1 h OT
    ]
    result = compute_ot_for_entries(entries)
    assert len(result['by_day']) == 1
    assert abs(result['by_day'][0]['hours'] - 9.0) < 0.01
    assert abs(result['by_day'][0]['ot_hours'] - 1.0) < 0.01


def test_compute_ot_fmt_strings():
    entries = [_make_entry('2026-06-23', 10.0)]
    result = compute_ot_for_entries(entries)
    assert ':' in result['total_hours_fmt']
    assert ':' in result['ot_hours_fmt']


def test_compute_ot_by_day_sorted_descending():
    entries = [
        _make_entry('2026-06-21', 8.0),
        _make_entry('2026-06-22', 8.0),
        _make_entry('2026-06-23', 8.0),
    ]
    result = compute_ot_for_entries(entries)
    dates = [r['date'] for r in result['by_day']]
    assert dates == sorted(dates, reverse=True)


def test_compute_ot_by_week_aggregation():
    # A single day with 42 h → weekly OT = 2 h
    entries = [_make_entry('2026-06-01', 42.0)]
    result = compute_ot_for_entries(entries)
    assert len(result['by_week']) == 1
    assert result['by_week'][0]['ot_hours'] >= 2.0


def test_compute_ot_entry_missing_clock_in_skipped():
    entries = [{'clock_in': '', 'hours': 8.0, 'in_progress': False}]
    result = compute_ot_for_entries(entries)
    # Entry with blank clock_in should be skipped
    assert result['total_hours'] == 0.0


# ---------------------------------------------------------------------------
# get_ot_report (single employee)
# ---------------------------------------------------------------------------

def _make_tc_row(people_id, date_str, hours):
    clock_in = f'{date_str} 08:00:00'
    clock_out = f'{date_str} {8 + int(hours):02d}:00:00'
    return {
        'id': 1,
        'people_id': people_id,
        'clock_in': clock_in,
        'clock_out': clock_out,
        'first_name': 'Alice',
        'last_name': 'Smith',
    }


def test_get_ot_report_queries_by_person():
    rows = [_make_tc_row(5, '2026-06-23', 9)]
    conn = _FakeConn(rows=rows)
    result = get_ot_report(conn, people_id=5)
    assert result['date_from'] is not None
    assert result['date_to'] is not None
    assert 5 in conn.last_params


def test_get_ot_report_custom_dates():
    conn = _FakeConn(rows=[])
    result = get_ot_report(conn, people_id=1,
                           date_from='2026-06-01', date_to='2026-06-30')
    assert result['date_from'] == '2026-06-01'
    assert result['date_to'] == '2026-06-30'
    assert '2026-06-01' in conn.last_params


def test_get_ot_report_empty():
    conn = _FakeConn(rows=[])
    result = get_ot_report(conn, people_id=99)
    assert result['total_hours'] == 0.0
    assert result['ot_hours'] == 0.0
    assert result['entries'] == []


def test_get_ot_report_default_dates_are_this_month():
    conn = _FakeConn(rows=[])
    result = get_ot_report(conn, people_id=1)
    today = datetime.now()
    expected_from = today.replace(day=1).strftime('%Y-%m-%d')
    assert result['date_from'] == expected_from


# ---------------------------------------------------------------------------
# get_ot_report_all (all employees)
# ---------------------------------------------------------------------------

def _make_all_row(people_id, fn, ln, dept, date_str, hours):
    clock_in = f'{date_str} 08:00:00'
    clock_out = f'{date_str} {8 + int(hours):02d}:00:00'
    return {
        'people_id': people_id,
        'first_name': fn,
        'last_name': ln,
        'dept_name': dept,
        'clock_in': clock_in,
        'clock_out': clock_out,
    }


def test_get_ot_report_all_groups_by_person():
    rows = [
        _make_all_row(1, 'Alice', 'Smith', 'Engineering', '2026-06-23', 9),
        _make_all_row(1, 'Alice', 'Smith', 'Engineering', '2026-06-24', 9),
        _make_all_row(2, 'Bob', 'Jones', 'Sales', '2026-06-23', 7),
    ]
    conn = _FakeConn(rows=rows)
    result = get_ot_report_all(conn)
    assert len(result) == 2
    alice = next(r for r in result if r['first_name'] == 'Alice')
    bob = next(r for r in result if r['first_name'] == 'Bob')
    assert alice['ot_hours'] > 0
    assert bob['ot_hours'] == 0.0


def test_get_ot_report_all_sorted_by_ot_desc():
    rows = [
        _make_all_row(1, 'Alice', 'Smith', 'Eng', '2026-06-23', 9),  # 1h OT
        _make_all_row(2, 'Bob', 'Jones', 'Sales', '2026-06-23', 10),  # 2h OT
        _make_all_row(3, 'Carol', 'White', 'HR', '2026-06-23', 7),   # 0 OT
    ]
    conn = _FakeConn(rows=rows)
    result = get_ot_report_all(conn)
    ot_vals = [r['ot_hours'] for r in result]
    assert ot_vals == sorted(ot_vals, reverse=True)


def test_get_ot_report_all_empty():
    conn = _FakeConn(rows=[])
    result = get_ot_report_all(conn)
    assert result == []


def test_get_ot_report_all_passes_date_params():
    conn = _FakeConn(rows=[])
    get_ot_report_all(conn, date_from='2026-05-01', date_to='2026-05-31')
    assert '2026-05-01' in conn.last_params
    assert '2026-05-31' in conn.last_params


# ---------------------------------------------------------------------------
# get_schedule_summary
# ---------------------------------------------------------------------------

def _make_sched_row(people_id, date_str, hours):
    clock_in = f'{date_str} 08:00:00'
    clock_out = f'{date_str} {8 + int(hours):02d}:00:00'
    return {
        'people_id': people_id,
        'clock_in': clock_in,
        'clock_out': clock_out,
    }


def test_get_schedule_summary_returns_date_range():
    conn = _FakeConn(rows=[])
    result = get_schedule_summary(conn)
    assert 'date_from' in result
    assert 'date_to' in result
    assert result['date_from'] <= result['date_to']


def test_get_schedule_summary_empty():
    conn = _FakeConn(rows=[])
    result = get_schedule_summary(conn, date_from='2026-06-01', date_to='2026-06-30')
    assert result['total_present'] == 0
    assert result['by_day'] == []


def test_get_schedule_summary_groups_by_day():
    rows = [
        _make_sched_row(1, '2026-06-23', 8),
        _make_sched_row(2, '2026-06-23', 7),
        _make_sched_row(1, '2026-06-24', 8),
    ]
    conn = _FakeConn(rows=rows)
    result = get_schedule_summary(conn, date_from='2026-06-23', date_to='2026-06-24')
    assert len(result['by_day']) == 2
    day23 = next(d for d in result['by_day'] if d['date'] == '2026-06-23')
    assert day23['present'] == 2


def test_get_schedule_summary_unique_people_per_day():
    # Same person clocks in twice in one day
    rows = [
        _make_sched_row(1, '2026-06-23', 4),
        _make_sched_row(1, '2026-06-23', 3),
    ]
    conn = _FakeConn(rows=rows)
    result = get_schedule_summary(conn, date_from='2026-06-23', date_to='2026-06-23')
    day = result['by_day'][0]
    assert day['present'] == 1  # one unique person


def test_get_schedule_summary_total_hours():
    rows = [
        _make_sched_row(1, '2026-06-23', 8),
        _make_sched_row(2, '2026-06-23', 6),
    ]
    conn = _FakeConn(rows=rows)
    result = get_schedule_summary(conn, date_from='2026-06-23', date_to='2026-06-23')
    day = result['by_day'][0]
    assert abs(day['total_hours'] - 14.0) < 0.1


def test_get_schedule_summary_passes_date_filter():
    conn = _FakeConn(rows=[])
    get_schedule_summary(conn, date_from='2026-06-01', date_to='2026-06-30')
    assert '2026-06-01' in conn.last_params
    assert '2026-06-30' in conn.last_params


def test_get_schedule_summary_custom_date_range():
    conn = _FakeConn(rows=[])
    result = get_schedule_summary(conn, date_from='2026-06-01', date_to='2026-06-07')
    assert result['date_from'] == '2026-06-01'
    assert result['date_to'] == '2026-06-07'


def test_get_schedule_summary_avg_daily_hours():
    rows = [
        _make_sched_row(1, '2026-06-23', 8),
        _make_sched_row(2, '2026-06-24', 8),
    ]
    conn = _FakeConn(rows=rows)
    result = get_schedule_summary(conn, date_from='2026-06-23', date_to='2026-06-24')
    # 2 days, 8 h each, 1 person each day → avg = 8 h
    assert abs(result['avg_daily_hours'] - 8.0) < 0.1


def test_get_schedule_summary_by_day_has_fmt():
    rows = [_make_sched_row(1, '2026-06-23', 8)]
    conn = _FakeConn(rows=rows)
    result = get_schedule_summary(conn, date_from='2026-06-23', date_to='2026-06-23')
    day = result['by_day'][0]
    assert ':' in day['total_hours_fmt']
    assert ':' in day['avg_hours_fmt']
