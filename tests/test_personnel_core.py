"""Tests for the Qt-free personnel data layer (personnel_core).

No live database: a fake connection records SQL calls and returns
canned rows, so filter assembly, field mapping, and time-off logic
are pinned without Postgres or PyQt6.
"""

from datetime import date


from manufacturing.personnel_core import (
    TIME_OFF_STATUSES, TIME_OFF_TYPES, TIME_OFF_STATUS_COLORS,
    list_people, get_person, get_person_by_email,
    create_person, update_person, load_depts, load_dept_subs,
    create_dept, update_dept, delete_dept,
    list_time_off_requests, get_time_off_request,
    create_time_off_request, set_time_off_status,
    DEFAULT_ANNUAL_ALLOTMENT_DAYS,
    ensure_time_off_balance_table, get_time_off_balance, set_time_off_allotment,
    ensure_contact_columns, get_own_contact_info, update_own_contact_info,
)
import pytest


class _FakeCursor:
    def __init__(self, rows, rowcount=0):
        self._rows = rows
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Records every (sql, params) call and replays preset rows."""

    def __init__(self, rows=None, rowcount=0):
        self.rows = rows or []
        self.rowcount = rowcount
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeCursor(self.rows, self.rowcount)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ── constants ───────────────────────────────────────────────────────────

def test_all_statuses_have_colors():
    assert set(TIME_OFF_STATUSES) == set(TIME_OFF_STATUS_COLORS)


def test_time_off_types_nonempty():
    assert len(TIME_OFF_TYPES) > 0


# ── list_people ──────────────────────────────────────────────────────────

def test_list_people_no_filter():
    row = {'id': 1, 'first_name': 'Alice', 'last_name': 'Smith',
           'employee_id': 101, 'email': 'alice@example.com',
           'dept_id': 2, 'dept_name': 'Engineering',
           'dept_sub_id': None, 'dept_sub_name': None,
           'job_title': 'Engineer'}
    conn = _FakeConn(rows=[row])
    result = list_people(conn)
    assert len(result) == 1
    assert result[0]['first_name'] == 'Alice'
    sql = conn.calls[0][0]
    assert 'WHERE' not in sql
    assert 'ORDER BY' in sql


def test_list_people_dept_filter():
    conn = _FakeConn()
    list_people(conn, dept_id=5)
    sql, params = conn.calls[0]
    assert 'WHERE' in sql
    assert 'dept_id' in sql
    assert 5 in params


def test_list_people_search_filter():
    conn = _FakeConn()
    list_people(conn, search='jones')
    sql, params = conn.calls[0]
    assert 'ILIKE' in sql
    assert '%jones%' in params


def test_list_people_combined_filters():
    conn = _FakeConn()
    list_people(conn, dept_id=3, search='bob')
    sql, params = conn.calls[0]
    assert 'dept_id' in sql
    assert 'ILIKE' in sql
    assert 3 in params
    assert '%bob%' in params


# ── get_person ───────────────────────────────────────────────────────────

def test_get_person_returns_dict():
    row = {'id': 7, 'first_name': 'Bob', 'last_name': 'Jones',
           'employee_id': 5, 'emp_id': None,
           'address': '', 'city': '', 'state': '', 'zip_code': '',
           'email': 'bob@example.com', 'dept_id': 1,
           'dept_name': 'HR', 'dept_sub_id': None, 'dept_sub_name': None,
           'job_title': 'Manager', 'role_name': 'HR / Personnel',
           'created_by': None}
    conn = _FakeConn(rows=[row])
    result = get_person(conn, 7)
    assert result is not None
    assert result['last_name'] == 'Jones'
    assert 7 in conn.last_params


def test_get_person_missing_returns_none():
    conn = _FakeConn(rows=[])
    assert get_person(conn, 99) is None


# ── get_person_by_email ──────────────────────────────────────────────────

def test_get_person_by_email_found():
    conn = _FakeConn(rows=[{'id': 3}])
    result = get_person_by_email(conn, 'alice@example.com')
    assert result == {'id': 3}
    assert 'alice@example.com' in conn.last_params


def test_get_person_by_email_not_found():
    conn = _FakeConn(rows=[])
    assert get_person_by_email(conn, 'nobody@example.com') is None


# ── create_person ────────────────────────────────────────────────────────

def test_create_person_inserts_and_upserts_position():
    conn = _FakeConn(rows=[{'id': 42}])
    person_id = create_person(
        conn, 'Carol', 'White', email='carol@example.com',
        job_title='Analyst', created_by='admin@example.com')
    assert person_id == 42
    assert len(conn.calls) == 2
    insert_sql = conn.calls[0][0]
    upsert_sql = conn.calls[1][0]
    assert 'INSERT INTO people' in insert_sql
    assert 'RETURNING id' in insert_sql
    assert 'ON CONFLICT' in upsert_sql


def test_create_person_zero_employee_id_when_none():
    conn = _FakeConn(rows=[{'id': 1}])
    create_person(conn, 'X', 'Y', employee_id=None)
    params = conn.calls[0][1]
    assert 0 in params


# ── update_person ────────────────────────────────────────────────────────

def test_update_person_updates_and_upserts():
    conn = _FakeConn()
    update_person(conn, 10, 'Carol', 'White', email='carol@example.com',
                  job_title='Senior Analyst')
    assert len(conn.calls) == 2
    update_sql = conn.calls[0][0]
    assert 'UPDATE people SET' in update_sql
    assert 10 in conn.calls[0][1]
    upsert_sql = conn.calls[1][0]
    assert 'ON CONFLICT' in upsert_sql


# ── load_depts / load_dept_subs ──────────────────────────────────────────

def test_load_depts():
    row = {'dept_id': 1, 'dept_name': 'Engineering', 'address': '', 'city': '',
           'state': '', 'zip_code': ''}
    conn = _FakeConn(rows=[row])
    result = load_depts(conn)
    assert len(result) == 1
    assert result[0]['dept_id'] == 1
    assert result[0]['dept_name'] == 'Engineering'
    assert 'ORDER BY' in conn.last_sql


# ── Department CRUD ──────────────────────────────────────────────────────

def test_create_dept_requires_name():
    conn = _FakeConn()
    with pytest.raises(ValueError):
        create_dept(conn, '   ')


def test_create_dept_inserts_address_fields():
    conn = _FakeConn(rows=[{'dept_id': 5}])
    create_dept(conn, 'Engineering', address='123 Main St', city='Sarasota',
                state='FL', zip_code='34231')
    sql, params = conn.calls[0]
    assert 'address' in sql and 'city' in sql and 'state' in sql and 'zip_code' in sql
    assert params == ['Engineering', '123 Main St', 'Sarasota', 'FL', '34231']


def test_update_dept_requires_name():
    conn = _FakeConn()
    with pytest.raises(ValueError):
        update_dept(conn, 1, '')


def test_update_dept_updates_address_fields():
    conn = _FakeConn()
    update_dept(conn, 1, 'Engineering', address='123 Main St', city='Sarasota',
                state='FL', zip_code='34231')
    sql, params = conn.calls[0]
    assert 'address' in sql and 'city' in sql and 'state' in sql and 'zip_code' in sql
    assert params == ['Engineering', '123 Main St', 'Sarasota', 'FL', '34231', 1]


class _SeqConn:
    """Like _FakeConn, but replays a different canned row per execute() call
    (in order) — needed for delete_dept's multiple sequential guard queries."""

    def __init__(self, row_sequence):
        self.row_sequence = list(row_sequence)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self.row_sequence.pop(0)
        return _FakeCursor(rows)


def test_delete_dept_blocked_by_people():
    conn = _SeqConn([[{'c': 2}]])
    with pytest.raises(ValueError, match='employees'):
        delete_dept(conn, 1)
    assert not any('DELETE FROM dept' in c[0] for c in conn.calls)


def test_delete_dept_blocked_by_sub_depts():
    conn = _SeqConn([[{'c': 0}], [{'c': 1}]])
    with pytest.raises(ValueError, match='sub-departments'):
        delete_dept(conn, 1)
    assert not any('DELETE FROM dept' in c[0] for c in conn.calls)


def test_delete_dept_blocked_by_budgets():
    conn = _SeqConn([[{'c': 0}], [{'c': 0}], [{'c': 3}]])
    with pytest.raises(ValueError, match='budgets'):
        delete_dept(conn, 1)
    assert not any('DELETE FROM dept' in c[0] for c in conn.calls)


def test_delete_dept_succeeds_when_unused():
    conn = _SeqConn([[{'c': 0}], [{'c': 0}], [{'c': 0}], []])
    delete_dept(conn, 1)
    assert 'DELETE FROM dept' in conn.calls[-1][0]
    assert conn.calls[-1][1] == [1]


def test_load_dept_subs_no_filter():
    conn = _FakeConn()
    load_dept_subs(conn)
    assert 'WHERE' not in conn.last_sql


def test_load_dept_subs_with_filter():
    conn = _FakeConn()
    load_dept_subs(conn, dept_id=4)
    assert 'WHERE' in conn.last_sql
    assert 4 in conn.last_params


# ── list_time_off_requests ───────────────────────────────────────────────

def test_list_time_off_no_filter():
    row = {'id': 1, 'people_id': 5, 'request_date': '2026-06-01',
           'start_date': '2026-07-01', 'end_date': '2026-07-05',
           'request_type': 'Vacation', 'status': 'pending',
           'notes': None, 'created_by': 'alice@example.com',
           'first_name': 'Alice', 'last_name': 'Smith'}
    conn = _FakeConn(rows=[row])
    result = list_time_off_requests(conn)
    assert len(result) == 1
    assert result[0]['status_color'] == TIME_OFF_STATUS_COLORS['pending']
    assert 'WHERE' not in conn.calls[0][0]


def test_list_time_off_by_person():
    conn = _FakeConn()
    list_time_off_requests(conn, people_id=3)
    sql, params = conn.calls[0]
    assert 'people_id' in sql
    assert 3 in params


def test_list_time_off_by_status():
    conn = _FakeConn()
    list_time_off_requests(conn, status='approved')
    sql, params = conn.calls[0]
    assert 'status' in sql
    assert 'approved' in params


def test_list_time_off_unknown_status_gets_white():
    row = {'id': 2, 'people_id': 1, 'request_date': None,
           'start_date': '2026-08-01', 'end_date': '2026-08-02',
           'request_type': 'Other', 'status': 'unknown_status',
           'notes': None, 'created_by': None,
           'first_name': 'X', 'last_name': 'Y'}
    conn = _FakeConn(rows=[row])
    result = list_time_off_requests(conn)
    assert result[0]['status_color'] == '#ffffff'


# ── get_time_off_request ─────────────────────────────────────────────────

def test_get_time_off_request_found():
    row = {'id': 9, 'people_id': 2, 'request_date': '2026-06-10',
           'start_date': '2026-06-20', 'end_date': '2026-06-25',
           'request_type': 'Sick', 'status': 'approved',
           'notes': 'flu', 'created_by': 'bob@example.com',
           'first_name': 'Bob', 'last_name': 'Jones'}
    conn = _FakeConn(rows=[row])
    result = get_time_off_request(conn, 9)
    assert result is not None
    assert result['request_type'] == 'Sick'
    assert result['status_color'] == TIME_OFF_STATUS_COLORS['approved']


def test_get_time_off_request_missing():
    conn = _FakeConn(rows=[])
    assert get_time_off_request(conn, 999) is None


# ── create_time_off_request ──────────────────────────────────────────────

def test_create_time_off_request_sql():
    conn = _FakeConn()
    create_time_off_request(
        conn, people_id=5,
        start_date='2026-08-01', end_date='2026-08-03',
        request_type='Vacation', notes='Holiday',
        created_by='alice@example.com')
    sql, params = conn.calls[0]
    assert 'INSERT INTO time_off_request' in sql
    assert 'pending' in sql
    assert 5 in params
    assert 'Vacation' in params
    assert 'Holiday' in params


def test_create_time_off_request_sets_today():
    conn = _FakeConn()
    create_time_off_request(conn, people_id=1,
                             start_date='2026-09-01', end_date='2026-09-02')
    _, params = conn.calls[0]
    assert date.today().isoformat() in params


# ── set_time_off_status ──────────────────────────────────────────────────

def test_set_time_off_status():
    conn = _FakeConn()
    set_time_off_status(conn, req_id=4, status='approved')
    sql, params = conn.calls[0]
    assert 'UPDATE time_off_request' in sql
    assert 'approved' in params
    assert 4 in params


# ── time-off balance (Employee Self-Service, P2-G) ──────────────────────

class _DispatchConn:
    """Returns canned rows based on a substring match against the SQL."""
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _FakeCursor(rows)
        return _FakeCursor([])

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


def test_ensure_time_off_balance_table_creates_table():
    conn = _FakeConn()
    ensure_time_off_balance_table(conn)
    assert 'CREATE TABLE IF NOT EXISTS time_off_balance' in conn.last_sql


def test_get_time_off_balance_uses_default_allotment_when_no_row():
    conn = _DispatchConn([
        ("FROM time_off_balance", []),
        ("FROM time_off_request", []),
    ])
    balance = get_time_off_balance(conn, people_id=5, year=2026)
    assert balance['allotted_days'] == DEFAULT_ANNUAL_ALLOTMENT_DAYS
    assert balance['used_days'] == 0.0
    assert balance['remaining_days'] == DEFAULT_ANNUAL_ALLOTMENT_DAYS


def test_get_time_off_balance_uses_configured_allotment():
    conn = _DispatchConn([
        ("FROM time_off_balance", [{'allotted_days': 20.0}]),
        ("FROM time_off_request", []),
    ])
    balance = get_time_off_balance(conn, people_id=5, year=2026)
    assert balance['allotted_days'] == 20.0


def test_get_time_off_balance_subtracts_approved_vacation_days():
    conn = _DispatchConn([
        ("FROM time_off_balance", []),
        ("FROM time_off_request", [
            {'start_date': '2026-03-01', 'end_date': '2026-03-03'},  # 3 days
            {'start_date': '2026-06-10', 'end_date': '2026-06-10'},  # 1 day
        ]),
    ])
    balance = get_time_off_balance(conn, people_id=5, year=2026)
    assert balance['used_days'] == 4.0
    assert balance['remaining_days'] == DEFAULT_ANNUAL_ALLOTMENT_DAYS - 4.0


def test_get_time_off_balance_ignores_malformed_dates():
    conn = _DispatchConn([
        ("FROM time_off_balance", []),
        ("FROM time_off_request", [{'start_date': None, 'end_date': None}]),
    ])
    balance = get_time_off_balance(conn, people_id=5, year=2026)
    assert balance['used_days'] == 0.0


def test_get_time_off_balance_defaults_to_current_year():
    conn = _DispatchConn([
        ("FROM time_off_balance", []),
        ("FROM time_off_request", []),
    ])
    balance = get_time_off_balance(conn, people_id=5)
    assert balance['year'] == date.today().year


def test_set_time_off_allotment_upserts():
    conn = _FakeConn()
    set_time_off_allotment(conn, people_id=5, year=2026, allotted_days=18.0)
    sql, params = conn.calls[0]
    assert 'ON CONFLICT (people_id, year)' in sql
    assert params == [5, 2026, 18.0]


# ── own contact info (Employee Self-Service, P2-G) ──────────────────────

def test_ensure_contact_columns_alters_people_table():
    conn = _FakeConn()
    ensure_contact_columns(conn)
    sqls = [s for s, _ in conn.calls]
    assert any('phone' in s for s in sqls)
    assert any('emergency_contact_name' in s for s in sqls)
    assert any('emergency_contact_phone' in s for s in sqls)
    assert any('emergency_contact_relationship' in s for s in sqls)


def test_get_own_contact_info_returns_dict():
    conn = _FakeConn(rows=[{'id': 5, 'phone': '555-1234'}])
    info = get_own_contact_info(conn, 5)
    assert info['phone'] == '555-1234'


def test_get_own_contact_info_returns_none_when_missing():
    conn = _FakeConn(rows=[])
    assert get_own_contact_info(conn, 999) is None


def test_update_own_contact_info_does_not_touch_dept_or_employee_id():
    conn = _FakeConn()
    update_own_contact_info(
        conn, 5, address='1 Main St', city='Springfield', state='IL',
        zip_code='62704', phone='555-1234',
        emergency_contact_name='Jane Doe', emergency_contact_phone='555-5678',
        emergency_contact_relationship='Spouse',
    )
    sql, params = conn.calls[0]
    assert 'dept_id' not in sql
    assert 'employee_id' not in sql
    assert params == [
        '1 Main St', 'Springfield', 'IL', '62704', '555-1234',
        'Jane Doe', '555-5678', 'Spouse', 5,
    ]
