"""Tests for the Qt-free time clock data layer (time_clock_core)."""

from datetime import datetime, timedelta

from manufacturing.time_clock_core import (
    compute_hours, fmt_hours, get_period_dates,
    get_current_entry, clock_in, clock_out_entry,
    list_entries, total_hours, get_attendance,
)


class _FakeCursor:
    def __init__(self, rows, rowcount=0):
        self._rows = rows
        self.rowcount = rowcount

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
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ── compute_hours ─────────────────────────────────────────────────────────

def test_compute_hours_closed_entry():
    h = compute_hours('2026-06-21 08:00:00', '2026-06-21 12:30:00')
    assert abs(h - 4.5) < 0.001


def test_compute_hours_zero_when_same():
    h = compute_hours('2026-06-21 09:00:00', '2026-06-21 09:00:00')
    assert h == 0.0


def test_compute_hours_open_uses_now():
    t_in = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
    h = compute_hours(t_in)
    assert 1.9 < h < 2.1


def test_compute_hours_negative_clamped_to_zero():
    h = compute_hours('2026-06-21 10:00:00', '2026-06-21 09:00:00')
    assert h == 0.0


# ── fmt_hours ─────────────────────────────────────────────────────────────

def test_fmt_hours_exact():
    assert fmt_hours(1.5) == '1:30'


def test_fmt_hours_zero():
    assert fmt_hours(0.0) == '0:00'


def test_fmt_hours_single_digit_minutes():
    assert fmt_hours(1.0 / 6) == '0:10'


def test_fmt_hours_large():
    assert fmt_hours(8.75) == '8:45'


# ── get_period_dates ──────────────────────────────────────────────────────

def test_period_today():
    d_from, d_to = get_period_dates('today')
    assert d_from == d_to
    assert d_from == datetime.now().strftime('%Y-%m-%d')


def test_period_week_contains_today():
    d_from, d_to = get_period_dates('week')
    today = datetime.now().strftime('%Y-%m-%d')
    assert d_from <= today <= d_to


def test_period_week_span():
    d_from, d_to = get_period_dates('week')
    dt_from = datetime.strptime(d_from, '%Y-%m-%d')
    dt_to = datetime.strptime(d_to, '%Y-%m-%d')
    assert (dt_to - dt_from).days == 6
    assert dt_from.weekday() == 0  # Monday


def test_period_month_from_is_first():
    d_from, _ = get_period_dates('month')
    assert d_from.endswith('-01')


def test_period_month_to_is_today():
    _, d_to = get_period_dates('month')
    assert d_to == datetime.now().strftime('%Y-%m-%d')


def test_period_unknown_defaults_to_today():
    d_from, d_to = get_period_dates('bogus')
    assert d_from == d_to == datetime.now().strftime('%Y-%m-%d')


# ── get_current_entry ─────────────────────────────────────────────────────

def test_get_current_entry_found():
    row = {'id': 5, 'people_id': 1, 'clock_in': '2026-06-21 08:00:00',
           'clock_out': None, 'hours_worked': None, 'notes': '', 'created_by': None}
    conn = _FakeConn(rows=[row])
    result = get_current_entry(conn, 1)
    assert result is not None
    assert result['id'] == 5
    assert 'clock_out IS NULL' in conn.last_sql


def test_get_current_entry_not_found():
    conn = _FakeConn(rows=[])
    assert get_current_entry(conn, 99) is None


# ── clock_in ──────────────────────────────────────────────────────────────

def test_clock_in_inserts_and_returns_id():
    conn = _FakeConn(rows=[{'id': 42}])
    new_id = clock_in(conn, people_id=3, created_by='alice@example.com')
    assert new_id == 42
    sql, params = conn.calls[0]
    assert 'INSERT INTO time_clock' in sql
    assert 'RETURNING id' in sql
    assert 3 in params
    assert 'alice@example.com' in params


def test_clock_in_stores_current_time():
    conn = _FakeConn(rows=[{'id': 1}])
    before = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    clock_in(conn, people_id=1)
    _, params = conn.calls[0]
    after = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ts = params[1]
    assert before <= ts <= after


# ── clock_out_entry ───────────────────────────────────────────────────────

def test_clock_out_updates_and_computes_hours():
    entry_row = {'clock_in': '2026-06-21 08:00:00'}
    conn = _FakeConn(rows=[entry_row])
    clock_out_entry(conn, entry_id=7)
    assert len(conn.calls) == 2
    update_sql, update_params = conn.calls[1]
    assert 'UPDATE time_clock SET clock_out' in update_sql
    assert 7 in update_params
    hours = update_params[1]
    assert isinstance(hours, float)
    assert hours > 0


def test_clock_out_missing_entry_is_noop():
    conn = _FakeConn(rows=[])
    clock_out_entry(conn, entry_id=99)
    assert len(conn.calls) == 1  # only the SELECT, no UPDATE


# ── list_entries ──────────────────────────────────────────────────────────

def test_list_entries_no_filter():
    row = {'id': 1, 'people_id': 2, 'clock_in': '2026-06-21 08:00:00',
           'clock_out': '2026-06-21 17:00:00', 'hours_worked': 9.0,
           'notes': '', 'created_by': None}
    conn = _FakeConn(rows=[row])
    entries = list_entries(conn, 2)
    assert len(entries) == 1
    assert abs(entries[0]['hours'] - 9.0) < 0.01
    assert entries[0]['hours_fmt'] == '9:00'
    assert entries[0]['in_progress'] is False


def test_list_entries_date_filter():
    conn = _FakeConn()
    list_entries(conn, 1, date_from='2026-06-01', date_to='2026-06-30')
    sql, params = conn.calls[0]
    assert 'SUBSTR' in sql
    assert '2026-06-01' in params
    assert '2026-06-30' in params


def test_list_entries_open_entry_is_in_progress():
    row = {'id': 3, 'people_id': 1, 'clock_in': '2026-06-21 09:00:00',
           'clock_out': None, 'hours_worked': None,
           'notes': '', 'created_by': None}
    conn = _FakeConn(rows=[row])
    entries = list_entries(conn, 1)
    assert entries[0]['in_progress'] is True


# ── total_hours ───────────────────────────────────────────────────────────

def test_total_hours_sums():
    entries = [
        {'hours': 4.0, 'hours_fmt': '4:00', 'in_progress': False},
        {'hours': 3.5, 'hours_fmt': '3:30', 'in_progress': False},
    ]
    h, fmt = total_hours(entries)
    assert abs(h - 7.5) < 0.001
    assert fmt == '7:30'


def test_total_hours_empty():
    h, fmt = total_hours([])
    assert h == 0.0
    assert fmt == '0:00'


# ── get_attendance ────────────────────────────────────────────────────────

def test_get_attendance_present_and_absent():
    rows = [
        # Alice — has a clock entry
        {'people_id': 1, 'first_name': 'Alice', 'last_name': 'Smith',
         'dept_id': 1, 'dept_name': 'Engineering',
         'entry_id': 10, 'clock_in': '2026-06-21 08:00:00',
         'clock_out': '2026-06-21 17:00:00'},
        # Bob — no clock entry (LEFT JOIN produced NULLs)
        {'people_id': 2, 'first_name': 'Bob', 'last_name': 'Jones',
         'dept_id': 2, 'dept_name': 'HR',
         'entry_id': None, 'clock_in': None, 'clock_out': None},
    ]
    conn = _FakeConn(rows=rows)
    result = get_attendance(conn, '2026-06-21')
    assert len(result) == 2
    alice = next(r for r in result if r['first_name'] == 'Alice')
    bob   = next(r for r in result if r['first_name'] == 'Bob')
    assert alice['present'] is True
    assert len(alice['entries']) == 1
    assert bob['present'] is False
    assert len(bob['entries']) == 0


def test_get_attendance_passes_date():
    conn = _FakeConn(rows=[])
    get_attendance(conn, '2026-06-15')
    assert '2026-06-15' in conn.last_params


def test_get_attendance_multiple_entries_same_person():
    rows = [
        {'people_id': 1, 'first_name': 'Carol', 'last_name': 'White',
         'dept_id': 1, 'dept_name': 'Sales',
         'entry_id': 5, 'clock_in': '2026-06-21 07:00:00',
         'clock_out': '2026-06-21 12:00:00'},
        {'people_id': 1, 'first_name': 'Carol', 'last_name': 'White',
         'dept_id': 1, 'dept_name': 'Sales',
         'entry_id': 6, 'clock_in': '2026-06-21 13:00:00',
         'clock_out': '2026-06-21 17:00:00'},
    ]
    conn = _FakeConn(rows=rows)
    result = get_attendance(conn, '2026-06-21')
    assert len(result) == 1
    carol = result[0]
    assert len(carol['entries']) == 2
    assert abs(carol['total_hours'] - 9.0) < 0.01
