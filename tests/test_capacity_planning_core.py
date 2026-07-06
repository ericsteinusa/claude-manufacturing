"""Tests for capacity_planning_core — Finite Capacity Scheduling (P3-A).

No live database: pure packing math is tested directly with plain dicts
and callables; DB-touching functions use a fake connection that records
calls and replays canned rows (mirroring test_sampling_plan_core.py /
test_document_control_core.py), plus unittest.mock.patch for the
routing_core/work_orders_core functions this module re-imports.
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from manufacturing.capacity_planning_core import (
    MIN_OPERATION_HOURS,
    ensure_capacity_tables, list_calendar_exceptions, set_calendar_exception,
    remove_calendar_exception, set_workcenter_calendar,
    list_workcenters_with_calendar,
    _load_workcenter_calendar, _to_date, get_booked_hours_by_day,
    _pack_forward, _pack_backward, _hour_to_datetime,
    forward_schedule_wo, backward_schedule_wo,
    get_capacity_check, identify_bottlenecks,
    suggest_load_leveling, apply_load_leveling_suggestion,
)


# ── fake DB infrastructure ──────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows, rowcount=1):
        self._rows = rows
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _DispatchConn:
    """Returns canned rows based on a substring match against the SQL."""
    def __init__(self, routes, default_rowcount=1):
        self.routes = routes
        self.calls = []
        self.default_rowcount = default_rowcount

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params) if params is not None else []))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows, self.default_rowcount)
        return _Cursor([], self.default_rowcount)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


def _wc_row(capacity=8.0, mon=True, tue=True, wed=True, thu=True, fri=True,
           sat=False, sun=False):
    return {
        'capacity_hours_per_day': capacity,
        'works_mon': mon, 'works_tue': tue, 'works_wed': wed, 'works_thu': thu,
        'works_fri': fri, 'works_sat': sat, 'works_sun': sun,
    }


# ── _hour_to_datetime / _to_date ─────────────────────────────────────────────

def test_hour_to_datetime_whole_hour():
    d = date(2026, 7, 6)
    assert _hour_to_datetime(d, 8.0) == datetime(2026, 7, 6, 8, 0)


def test_hour_to_datetime_fractional_hour():
    d = date(2026, 7, 6)
    dt = _hour_to_datetime(d, 8.5)
    assert dt == datetime(2026, 7, 6, 8, 30)


def test_to_date_from_date_object():
    d = date(2026, 7, 6)
    assert _to_date(d) is d


def test_to_date_from_datetime_object():
    dt = datetime(2026, 7, 6, 14, 30)
    assert _to_date(dt) == date(2026, 7, 6)


def test_to_date_from_iso_string():
    assert _to_date('2026-07-06T14:30:00Z') == date(2026, 7, 6)


# ── _pack_forward ────────────────────────────────────────────────────────────

def test_pack_forward_fits_within_one_day():
    booked = {}
    start, end = _pack_forward(4.0, date(2026, 7, 6), lambda d: 8.0, booked)
    assert start == datetime(2026, 7, 6, 8, 0)
    assert end == datetime(2026, 7, 6, 12, 0)
    assert booked[date(2026, 7, 6)] == 4.0


def test_pack_forward_spans_multiple_days():
    booked = {}
    start, end = _pack_forward(20.0, date(2026, 7, 6), lambda d: 8.0, booked)
    # 8 + 8 + 4 = 20 over three days
    assert start == datetime(2026, 7, 6, 8, 0)
    assert end == datetime(2026, 7, 8, 12, 0)
    assert booked[date(2026, 7, 6)] == 8.0
    assert booked[date(2026, 7, 7)] == 8.0
    assert booked[date(2026, 7, 8)] == 4.0


def test_pack_forward_respects_existing_bookings():
    booked = {date(2026, 7, 6): 6.0}  # only 2h free today
    start, end = _pack_forward(4.0, date(2026, 7, 6), lambda d: 8.0, booked)
    assert start == datetime(2026, 7, 6, 14, 0)  # starts after the 6h already booked
    assert end == datetime(2026, 7, 7, 10, 0)     # spills 2h into the next day
    assert booked[date(2026, 7, 6)] == 8.0
    assert booked[date(2026, 7, 7)] == 2.0


def test_pack_forward_skips_zero_capacity_days():
    # Weekend simulated as zero-capacity
    def avail(d):
        return 0.0 if d.weekday() >= 5 else 8.0
    booked = {}
    # Friday 2026-07-03 + Saturday/Sunday off + Monday
    start, end = _pack_forward(12.0, date(2026, 7, 3), avail, booked)
    assert start == datetime(2026, 7, 3, 8, 0)
    assert end == datetime(2026, 7, 6, 12, 0)  # Fri 8h + Mon 4h, weekend skipped
    assert date(2026, 7, 4) not in booked
    assert date(2026, 7, 5) not in booked


def test_pack_forward_zero_hours_uses_minimum_floor():
    booked = {}
    start, end = _pack_forward(0.0, date(2026, 7, 6), lambda d: 8.0, booked)
    assert (end - start).total_seconds() / 3600 == pytest.approx(MIN_OPERATION_HOURS)


def test_pack_forward_raises_when_calendar_always_zero():
    with pytest.raises(ValueError):
        _pack_forward(4.0, date(2026, 7, 6), lambda d: 0.0, {})


# ── _pack_backward ───────────────────────────────────────────────────────────

def test_pack_backward_fits_within_one_day():
    # A backward-packed segment ends at the day's actual close (workday_start
    # + capacity = 8:00 + 8h = 16:00 here) and occupies the last `consume`
    # hours before that, not the first hours of the day (that's what
    # distinguishes it from a forward pack of the same duration).
    booked = {}
    start, end = _pack_backward(4.0, date(2026, 7, 6), lambda d: 8.0, booked)
    assert end == datetime(2026, 7, 6, 16, 0)
    assert start == datetime(2026, 7, 6, 12, 0)
    assert booked[date(2026, 7, 6)] == 4.0


def test_pack_backward_spans_multiple_days():
    booked = {}
    start, end = _pack_backward(20.0, date(2026, 7, 8), lambda d: 8.0, booked)
    assert end == datetime(2026, 7, 8, 16, 0)
    assert start == datetime(2026, 7, 6, 12, 0)
    assert booked[date(2026, 7, 6)] == 4.0
    assert booked[date(2026, 7, 7)] == 8.0
    assert booked[date(2026, 7, 8)] == 8.0


def test_pack_backward_respects_existing_bookings():
    # 6h already booked -> 2h free, ending at 8:00+8h=16:00 minus the 6h
    # already used = the free slice is [10:00, 16:00); a 1h op takes the
    # start of that slice (backward-fill still consumes the earliest part
    # of whatever's left once the "used" hours are accounted for).
    booked = {date(2026, 7, 6): 6.0}
    start, end = _pack_backward(1.0, date(2026, 7, 6), lambda d: 8.0, booked)
    assert start == datetime(2026, 7, 6, 9, 0)
    assert end == datetime(2026, 7, 6, 10, 0)


def test_pack_backward_skips_zero_capacity_days():
    def avail(d):
        return 0.0 if d.weekday() >= 5 else 8.0
    booked = {}
    # Monday 2026-07-06, working backward through the weekend to Friday
    start, end = _pack_backward(12.0, date(2026, 7, 6), avail, booked)
    assert end == datetime(2026, 7, 6, 16, 0)
    assert start == datetime(2026, 7, 3, 12, 0)
    assert date(2026, 7, 4) not in booked
    assert date(2026, 7, 5) not in booked


def test_pack_backward_raises_when_calendar_always_zero():
    with pytest.raises(ValueError):
        _pack_backward(4.0, date(2026, 7, 6), lambda d: 0.0, {})


def test_pack_forward_and_backward_are_symmetric_on_flat_calendar():
    booked_f = {}
    f_start, f_end = _pack_forward(20.0, date(2026, 7, 6), lambda d: 8.0, booked_f)
    booked_b = {}
    b_start, b_end = _pack_backward(20.0, f_end.date(), lambda d: 8.0, booked_b)
    assert b_start.date() == f_start.date()


# ── _load_workcenter_calendar ────────────────────────────────────────────────

def test_load_workcenter_calendar_default_mon_fri():
    conn = _DispatchConn([
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
    ])
    cal = _load_workcenter_calendar(conn, 1, date(2026, 7, 6), date(2026, 7, 12))
    # 2026-07-06 is a Monday
    assert cal[date(2026, 7, 6)] == 8.0  # Mon
    assert cal[date(2026, 7, 11)] == 0.0  # Sat
    assert cal[date(2026, 7, 12)] == 0.0  # Sun


def test_load_workcenter_calendar_exception_overrides_weekday():
    conn = _DispatchConn([
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", [
            {'exception_date': date(2026, 7, 6), 'hours_available': 0.0},   # holiday on a Monday
            {'exception_date': date(2026, 7, 11), 'hours_available': 4.0},  # OT Saturday
        ]),
    ])
    cal = _load_workcenter_calendar(conn, 1, date(2026, 7, 6), date(2026, 7, 12))
    assert cal[date(2026, 7, 6)] == 0.0
    assert cal[date(2026, 7, 11)] == 4.0


def test_load_workcenter_calendar_missing_workcenter_returns_empty():
    conn = _DispatchConn([("FROM workcenter WHERE id", [])])
    assert _load_workcenter_calendar(conn, 999, date(2026, 7, 6), date(2026, 7, 6)) == {}


# ── get_booked_hours_by_day ──────────────────────────────────────────────────

def test_get_booked_hours_distributes_evenly_across_span():
    conn = _DispatchConn([
        ("FROM wo_operation", [
            {'std_hours': 12.0, 'scheduled_start': datetime(2026, 7, 6, 8, 0),
             'scheduled_end': datetime(2026, 7, 7, 12, 0)},
        ]),
    ])
    booked = get_booked_hours_by_day(conn, 1, date(2026, 7, 6), date(2026, 7, 7))
    assert booked[date(2026, 7, 6)] == pytest.approx(6.0)
    assert booked[date(2026, 7, 7)] == pytest.approx(6.0)


def test_get_booked_hours_excludes_wo_id_when_asked():
    conn = _DispatchConn([("FROM wo_operation", [])])
    get_booked_hours_by_day(conn, 1, date(2026, 7, 6), date(2026, 7, 6), exclude_wo_id=5)
    assert "wo_id != %s" in conn.last_sql
    assert 5 in conn.last_params


def test_get_booked_hours_empty_when_no_scheduled_ops():
    conn = _DispatchConn([("FROM wo_operation", [])])
    assert get_booked_hours_by_day(conn, 1, date(2026, 7, 6), date(2026, 7, 6)) == {}


# ── forward_schedule_wo / backward_schedule_wo ──────────────────────────────

def _op(id_, seq, name, wc_id, hours, status='pending'):
    return {
        'id': id_, 'operation_seq': seq, 'operation_name': name,
        'workcenter_id': wc_id, 'workcenter_name': f'WC{wc_id}',
        'std_hours': hours, 'status': status,
    }


def test_forward_schedule_wo_raises_when_no_schedulable_ops():
    with patch('manufacturing.capacity_planning_core.get_wo_operations',
              return_value=[_op(1, 10, 'Cut', 1, 4.0, status='completed')]):
        with pytest.raises(ValueError):
            forward_schedule_wo(_DispatchConn([]), wo_id=1)


def test_forward_schedule_wo_sequences_operations_and_persists():
    ops = [_op(1, 10, 'Cut', 1, 4.0), _op(2, 20, 'Weld', 1, 4.0)]
    conn = _DispatchConn([
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", []),  # no pre-existing bookings
        ("UPDATE wo_operation", []),
    ])
    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops):
        result = forward_schedule_wo(conn, wo_id=1, start_from='2026-07-06')

    assert len(result['operations']) == 2
    op1, op2 = result['operations']
    assert op1['scheduled_start'].startswith('2026-07-06T08:00')
    assert op1['scheduled_end'].startswith('2026-07-06T12:00')
    # Second op continues right after the first on the same workcenter/day
    assert op2['scheduled_start'].startswith('2026-07-06T12:00')
    assert op2['scheduled_end'].startswith('2026-07-06T16:00')
    assert result['computed_end_date'] == '2026-07-06'


def test_forward_schedule_wo_cross_workcenter_respects_prior_finish():
    """Regression test: operation 2 is on a DIFFERENT workcenter than
    operation 1, whose own calendar/booked ledger has no idea operation 1
    exists — without the not_before constraint, operation 2 could start
    at that workcenter's own day-open (08:00) even though operation 1
    (say, assembly) doesn't finish until 09:30, which would mean QA
    inspecting a part that hasn't been assembled yet."""
    ops = [_op(1, 10, 'Assemble', 1, 1.5), _op(2, 20, 'Inspect', 2, 0.3)]

    def route_conn():
        return _DispatchConn([
            ("FROM workcenter WHERE id", [_wc_row()]),
            ("FROM workcenter_calendar_exception", []),
            ("FROM wo_operation", []),
            ("UPDATE wo_operation", []),
        ])

    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops):
        result = forward_schedule_wo(route_conn(), wo_id=1, start_from='2026-07-06')

    op1, op2 = result['operations']
    assert op1['scheduled_end'] == '2026-07-06T09:30:00Z'
    assert op2['scheduled_start'] == '2026-07-06T09:30:00Z'  # not 08:00
    assert op2['scheduled_end'] == '2026-07-06T09:48:00Z'


def test_backward_schedule_wo_cross_workcenter_respects_next_start():
    ops = [_op(1, 10, 'Assemble', 1, 1.5), _op(2, 20, 'Inspect', 2, 0.3)]

    def route_conn():
        return _DispatchConn([
            ("FROM workcenter WHERE id", [_wc_row()]),
            ("FROM workcenter_calendar_exception", []),
            ("FROM wo_operation", []),
            ("UPDATE wo_operation", []),
        ])

    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops), \
         patch('manufacturing.capacity_planning_core.get_wo', return_value={'due_date': '2026-07-06'}):
        result = backward_schedule_wo(route_conn(), wo_id=1)

    op1, op2 = result['operations']
    # Inspect (op2) ends at the due date's close of day; Assemble (op1)
    # must finish no later than Inspect's start.
    assert op1['scheduled_end'] == op2['scheduled_start']


def test_forward_schedule_wo_unassigned_workcenter_gets_unconstrained_block():
    ops = [_op(1, 10, 'Inspect', None, 2.0)]
    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops):
        result = forward_schedule_wo(_DispatchConn([]), wo_id=1, start_from='2026-07-06')
    op1 = result['operations'][0]
    assert op1['scheduled_start'].startswith('2026-07-06T08:00')
    assert op1['scheduled_end'].startswith('2026-07-06T10:00')


def test_backward_schedule_wo_raises_when_no_due_date_available():
    ops = [_op(1, 10, 'Cut', 1, 4.0)]
    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops), \
         patch('manufacturing.capacity_planning_core.get_wo', return_value={'due_date': None}):
        with pytest.raises(ValueError):
            backward_schedule_wo(_DispatchConn([]), wo_id=1)


def test_backward_schedule_wo_uses_wo_due_date_and_restores_seq_order():
    ops = [_op(1, 10, 'Cut', 1, 4.0), _op(2, 20, 'Weld', 1, 4.0)]
    conn = _DispatchConn([
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", []),
        ("UPDATE wo_operation", []),
    ])
    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops), \
         patch('manufacturing.capacity_planning_core.get_wo', return_value={'due_date': '2026-07-06'}):
        result = backward_schedule_wo(conn, wo_id=1)

    op1, op2 = result['operations']
    assert op1['id'] == 1 and op2['id'] == 2  # restored to seq order, not reversed
    assert op2['scheduled_end'].startswith('2026-07-06T16:00')
    assert op1['scheduled_start'].startswith('2026-07-06T08:00')


def test_backward_schedule_wo_flags_at_risk_when_start_before_today():
    ops = [_op(1, 10, 'Cut', 1, 4.0)]
    conn = _DispatchConn([
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", []),
        ("UPDATE wo_operation", []),
    ])
    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops), \
         patch('manufacturing.capacity_planning_core.get_wo', return_value={'due_date': '2020-01-01'}):
        result = backward_schedule_wo(conn, wo_id=1)
    assert result['at_risk'] is True


def test_backward_schedule_wo_not_at_risk_for_future_due_date():
    ops = [_op(1, 10, 'Cut', 1, 4.0)]
    far_future = (date.today() + timedelta(days=365 * 5)).isoformat()
    conn = _DispatchConn([
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", []),
        ("UPDATE wo_operation", []),
    ])
    with patch('manufacturing.capacity_planning_core.get_wo_operations', return_value=ops), \
         patch('manufacturing.capacity_planning_core.get_wo', return_value={'due_date': far_future}):
        result = backward_schedule_wo(conn, wo_id=1)
    assert result['at_risk'] is False


# ── get_capacity_check ───────────────────────────────────────────────────────

def test_get_capacity_check_flags_over_capacity_day():
    conn = _DispatchConn([
        ("FROM workcenter WHERE is_active", [{'id': 1, 'name': 'Cutting', 'dept': '',
                                              'capacity_hours_per_day': 8.0,
                                              'labor_rate': 0.0, 'notes': '', 'is_active': True}]),
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", [
            {'std_hours': 10.0, 'scheduled_start': datetime(2026, 7, 6, 8, 0),
             'scheduled_end': datetime(2026, 7, 6, 18, 0)},
        ]),
    ])
    result = get_capacity_check(conn, '2026-07-06', '2026-07-06')
    day = result[0]['days'][0]
    assert day['booked'] == pytest.approx(10.0)
    assert day['available'] == 8.0
    assert day['over_capacity'] is True
    assert day['pct'] == pytest.approx(125.0)


def test_get_capacity_check_zero_available_zero_booked_not_over():
    conn = _DispatchConn([
        ("FROM workcenter WHERE is_active", [{'id': 1, 'name': 'Cutting', 'dept': '',
                                              'capacity_hours_per_day': 8.0,
                                              'labor_rate': 0.0, 'notes': '', 'is_active': True}]),
        ("FROM workcenter WHERE id", [_wc_row(sat=False, sun=False)]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", []),
    ])
    # 2026-07-11 is a Saturday -> 0 available, 0 booked
    result = get_capacity_check(conn, '2026-07-11', '2026-07-11')
    day = result[0]['days'][0]
    assert day['available'] == 0.0
    assert day['booked'] == 0.0
    assert day['over_capacity'] is False
    assert day['pct'] == 0.0


# ── identify_bottlenecks ─────────────────────────────────────────────────────

def test_identify_bottlenecks_sorts_by_utilization_desc():
    fake_check = [
        {'workcenter_id': 1, 'workcenter_name': 'Low',
         'days': [{'date': '2026-07-06', 'available': 8.0, 'booked': 2.0, 'over_capacity': False}]},
        {'workcenter_id': 2, 'workcenter_name': 'High',
         'days': [{'date': '2026-07-06', 'available': 8.0, 'booked': 10.0, 'over_capacity': True}]},
    ]
    with patch('manufacturing.capacity_planning_core.get_capacity_check', return_value=fake_check):
        result = identify_bottlenecks(_DispatchConn([]), '2026-07-06', '2026-07-06')
    assert result[0]['workcenter_name'] == 'High'
    assert result[0]['utilization_pct'] == pytest.approx(125.0)
    assert result[0]['over_capacity_days'] == 1
    assert result[1]['workcenter_name'] == 'Low'


def test_identify_bottlenecks_zero_availability_workcenter_ranks_by_activity():
    fake_check = [
        {'workcenter_id': 1, 'workcenter_name': 'Idle',
         'days': [{'date': '2026-07-06', 'available': 0.0, 'booked': 0.0, 'over_capacity': False}]},
    ]
    with patch('manufacturing.capacity_planning_core.get_capacity_check', return_value=fake_check):
        result = identify_bottlenecks(_DispatchConn([]), '2026-07-06', '2026-07-06')
    assert result[0]['utilization_pct'] == 0.0


# ── suggest_load_leveling / apply_load_leveling_suggestion ──────────────────

def test_suggest_load_leveling_finds_slack_day():
    fake_check = [
        {'workcenter_id': 1, 'workcenter_name': 'Cutting',
         'days': [{'date': '2026-07-06', 'available': 8.0, 'booked': 10.0, 'over_capacity': True}]},
    ]
    conn = _DispatchConn([
        # Op spans two calendar days (10h @ 5h/day average) so its
        # per-day footprint (5h) fits inside an empty 8h/day probe day.
        ("FROM wo_operation op JOIN work_order", [
            {'id': 42, 'operation_name': 'Cut', 'std_hours': 10.0,
             'scheduled_start': datetime(2026, 7, 6, 8, 0),
             'scheduled_end': datetime(2026, 7, 7, 14, 0),
             'wo_number': 'WO-2026-0001', 'wo_id': 7},
        ]),
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        ("FROM wo_operation", []),  # no bookings on probe days -> first probe day has slack
    ])
    with patch('manufacturing.capacity_planning_core.get_capacity_check', return_value=fake_check):
        suggestions = suggest_load_leveling(conn, '2026-07-06', '2026-07-06')

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s['op_id'] == 42
    assert s['wo_number'] == 'WO-2026-0001'
    assert s['over_by_hours'] == pytest.approx(2.0)
    assert s['delay_to_date'] == '2026-07-07'
    assert s['delay_days'] == 1


def test_suggest_load_leveling_no_candidates_skips_day():
    fake_check = [
        {'workcenter_id': 1, 'workcenter_name': 'Cutting',
         'days': [{'date': '2026-07-06', 'available': 8.0, 'booked': 10.0, 'over_capacity': True}]},
    ]
    conn = _DispatchConn([("FROM wo_operation op JOIN work_order", [])])
    with patch('manufacturing.capacity_planning_core.get_capacity_check', return_value=fake_check):
        suggestions = suggest_load_leveling(conn, '2026-07-06', '2026-07-06')
    assert suggestions == []


def test_suggest_load_leveling_no_slack_found_within_horizon():
    fake_check = [
        {'workcenter_id': 1, 'workcenter_name': 'Cutting',
         'days': [{'date': '2026-07-06', 'available': 8.0, 'booked': 10.0, 'over_capacity': True}]},
    ]
    always_full = [
        {'std_hours': 10.0, 'scheduled_start': datetime(2026, 7, 6, 8, 0),
         'scheduled_end': datetime(2026, 7, 6, 18, 0)},
    ]
    conn = _DispatchConn([
        ("FROM wo_operation op JOIN work_order", [
            {'id': 42, 'operation_name': 'Cut', 'std_hours': 10.0,
             'scheduled_start': datetime(2026, 7, 6, 8, 0),
             'scheduled_end': datetime(2026, 7, 6, 18, 0),
             'wo_number': 'WO-2026-0001', 'wo_id': 7},
        ]),
        ("FROM workcenter WHERE id", [_wc_row()]),
        ("FROM workcenter_calendar_exception", []),
        # Every probe day comes back fully booked too -> no slack ever found
        ("FROM wo_operation", always_full),
    ])
    with patch('manufacturing.capacity_planning_core.get_capacity_check', return_value=fake_check):
        suggestions = suggest_load_leveling(conn, '2026-07-06', '2026-07-06', search_horizon_days=3)
    assert suggestions[0]['delay_to_date'] is None
    assert suggestions[0]['delay_days'] is None


def test_apply_load_leveling_suggestion_shifts_window():
    conn = _DispatchConn([
        ("SELECT scheduled_start, scheduled_end FROM wo_operation", [
            {'scheduled_start': datetime(2026, 7, 6, 8, 0), 'scheduled_end': datetime(2026, 7, 6, 12, 0)},
        ]),
        ("UPDATE wo_operation", []),
    ], default_rowcount=1)
    apply_load_leveling_suggestion(conn, op_id=42, delay_days=2)
    update_calls = [c for c in conn.calls if c[0].startswith('UPDATE wo_operation')]
    assert update_calls[0][1][0] == '2026-07-08T08:00:00'
    assert update_calls[0][1][1] == '2026-07-08T12:00:00'


def test_apply_load_leveling_suggestion_raises_without_scheduled_window():
    conn = _DispatchConn([
        ("SELECT scheduled_start, scheduled_end FROM wo_operation", [
            {'scheduled_start': None, 'scheduled_end': None},
        ]),
    ])
    with pytest.raises(ValueError):
        apply_load_leveling_suggestion(conn, op_id=42, delay_days=1)


# ── calendar admin functions ─────────────────────────────────────────────────

def test_ensure_capacity_tables_creates_exception_table_and_columns():
    conn = _DispatchConn([])
    ensure_capacity_tables(conn)
    sqls = [s for s, _ in conn.calls]
    assert any('CREATE TABLE IF NOT EXISTS workcenter_calendar_exception' in s for s in sqls)
    assert any('works_mon' in s for s in sqls)
    assert any('works_sat' in s for s in sqls)


def test_list_calendar_exceptions_filters_by_date_range():
    conn = _DispatchConn([("FROM workcenter_calendar_exception", [])])
    list_calendar_exceptions(conn, 1, date_from='2026-07-01', date_to='2026-07-31')
    assert "exception_date >= %s" in conn.last_sql
    assert "exception_date <= %s" in conn.last_sql
    assert conn.last_params == [1, '2026-07-01', '2026-07-31']


def test_set_calendar_exception_upserts():
    conn = _DispatchConn([("INSERT INTO workcenter_calendar_exception", [{'id': 9}])])
    exc_id = set_calendar_exception(conn, 1, date(2026, 12, 25), 0.0, notes='Christmas')
    assert exc_id == 9
    assert "ON CONFLICT (workcenter_id, exception_date)" in conn.last_sql


def test_remove_calendar_exception_deletes():
    conn = _DispatchConn([])
    remove_calendar_exception(conn, 9)
    assert "DELETE FROM workcenter_calendar_exception" in conn.last_sql
    assert conn.last_params == [9]


def test_set_workcenter_calendar_updates_only_known_day_flags():
    conn = _DispatchConn([])
    set_workcenter_calendar(conn, 1, works_sat=True, bogus_field=True)
    assert "works_sat = %s" in conn.last_sql
    assert "bogus_field" not in conn.last_sql
    assert conn.last_params == [True, 1]


def test_set_workcenter_calendar_noop_with_no_valid_flags():
    conn = _DispatchConn([])
    set_workcenter_calendar(conn, 1, bogus_field=True)
    assert conn.calls == []


def test_list_workcenters_with_calendar_includes_weekday_flags():
    conn = _DispatchConn([
        ("FROM workcenter", [{
            'id': 1, 'name': 'Cutting', 'dept': '', 'capacity_hours_per_day': 8.0,
            'labor_rate': 0.0, 'notes': '', 'is_active': True,
            'works_mon': True, 'works_tue': True, 'works_wed': True,
            'works_thu': True, 'works_fri': True, 'works_sat': False, 'works_sun': False,
        }]),
    ])
    result = list_workcenters_with_calendar(conn)
    assert result[0]['works_mon'] is True
    assert result[0]['works_sat'] is False
    assert "works_sun" in conn.last_sql
