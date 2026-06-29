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
    list_time_off_requests, get_time_off_request,
    create_time_off_request, set_time_off_status,
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
    row = {'dept_id': 1, 'dept_name': 'Engineering'}
    conn = _FakeConn(rows=[row])
    result = load_depts(conn)
    assert result == [{'dept_id': 1, 'dept_name': 'Engineering'}]
    assert 'ORDER BY' in conn.last_sql


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
