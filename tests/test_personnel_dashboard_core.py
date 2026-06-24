"""Tests for get_personnel_dashboard in personnel_core.py.

Uses MagicMock — no live DB required.
"""
from unittest.mock import MagicMock

from manufacturing.personnel_core import get_personnel_dashboard


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _conn(emp_row, dept_rows, to_row, recent_rows):
    c = MagicMock()
    m1 = MagicMock(); m1.fetchone.return_value = emp_row
    m2 = MagicMock(); m2.fetchall.return_value = dept_rows
    m3 = MagicMock(); m3.fetchone.return_value = to_row
    m4 = MagicMock(); m4.fetchall.return_value = recent_rows
    c.execute.side_effect = [m1, m2, m3, m4]
    return c


def _make_row(**kwargs):
    """Return a MagicMock that behaves like a dict row (supports dict())."""
    row = MagicMock()
    row.keys.return_value = list(kwargs.keys())
    row.__iter__ = lambda s: iter(kwargs.items())
    row.__getitem__ = lambda s, k: kwargs[k]
    # dict(row) uses keys() + __getitem__; we need the mapping protocol
    row._asdict = lambda: kwargs
    # psycopg2 RealDictRow supports dict(row) via items()
    row.items.return_value = kwargs.items()
    # Simplest: make dict(row) work by subclassing dict isn't possible here,
    # so we return a plain dict directly from the mock helpers instead.
    return kwargs  # return plain dict so dict(row) == kwargs


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

EMP_ROW = {'total': 42}
DEPT_ROWS = [
    {'dept_name': 'Engineering', 'count': 12},
    {'dept_name': 'Sales', 'count': 8},
]
TO_ROW = {'pending': 3, 'approved': 7}
RECENT_ROWS = [
    {'id': 10, 'first_name': 'Alice', 'last_name': 'Smith',
     'email': 'alice@example.com', 'dept_name': 'Engineering', 'job_title': 'Engineer'},
    {'id': 9, 'first_name': 'Bob', 'last_name': 'Jones',
     'email': 'bob@example.com', 'dept_name': 'Sales', 'job_title': 'Rep'},
]


def _std_conn():
    return _conn(EMP_ROW, DEPT_ROWS, TO_ROW, RECENT_ROWS)


# ---------------------------------------------------------------------------
# Tests — return structure
# ---------------------------------------------------------------------------

def test_returns_dict():
    result = get_personnel_dashboard(_std_conn())
    assert isinstance(result, dict)


def test_has_employees_key():
    result = get_personnel_dashboard(_std_conn())
    assert 'employees' in result


def test_has_by_dept_key():
    result = get_personnel_dashboard(_std_conn())
    assert 'by_dept' in result


def test_has_time_off_key():
    result = get_personnel_dashboard(_std_conn())
    assert 'time_off' in result


def test_has_recent_employees_key():
    result = get_personnel_dashboard(_std_conn())
    assert 'recent_employees' in result


# ---------------------------------------------------------------------------
# Tests — employees
# ---------------------------------------------------------------------------

def test_employees_total():
    result = get_personnel_dashboard(_std_conn())
    assert result['employees']['total'] == 42


def test_employees_empty_when_fetchone_none():
    c = _conn(None, DEPT_ROWS, TO_ROW, RECENT_ROWS)
    result = get_personnel_dashboard(c)
    assert result['employees'] == {}


# ---------------------------------------------------------------------------
# Tests — by_dept
# ---------------------------------------------------------------------------

def test_by_dept_is_list():
    result = get_personnel_dashboard(_std_conn())
    assert isinstance(result['by_dept'], list)


def test_by_dept_items_have_dept_name():
    result = get_personnel_dashboard(_std_conn())
    assert all('dept_name' in d for d in result['by_dept'])


def test_by_dept_items_have_count():
    result = get_personnel_dashboard(_std_conn())
    assert all('count' in d for d in result['by_dept'])


def test_by_dept_empty_list_when_fetchall_empty():
    c = _conn(EMP_ROW, [], TO_ROW, RECENT_ROWS)
    result = get_personnel_dashboard(c)
    assert result['by_dept'] == []


# ---------------------------------------------------------------------------
# Tests — time_off
# ---------------------------------------------------------------------------

def test_time_off_pending():
    result = get_personnel_dashboard(_std_conn())
    assert result['time_off']['pending'] == 3


def test_time_off_approved():
    result = get_personnel_dashboard(_std_conn())
    assert result['time_off']['approved'] == 7


def test_time_off_empty_when_fetchone_none():
    c = _conn(EMP_ROW, DEPT_ROWS, None, RECENT_ROWS)
    result = get_personnel_dashboard(c)
    assert result['time_off'] == {}


# ---------------------------------------------------------------------------
# Tests — recent_employees
# ---------------------------------------------------------------------------

def test_recent_employees_is_list():
    result = get_personnel_dashboard(_std_conn())
    assert isinstance(result['recent_employees'], list)


def test_recent_employees_have_first_name():
    result = get_personnel_dashboard(_std_conn())
    assert all('first_name' in e for e in result['recent_employees'])


def test_recent_employees_have_last_name():
    result = get_personnel_dashboard(_std_conn())
    assert all('last_name' in e for e in result['recent_employees'])


def test_recent_employees_have_email():
    result = get_personnel_dashboard(_std_conn())
    assert all('email' in e for e in result['recent_employees'])


def test_recent_employees_empty_when_fetchall_empty():
    c = _conn(EMP_ROW, DEPT_ROWS, TO_ROW, [])
    result = get_personnel_dashboard(c)
    assert result['recent_employees'] == []


# ---------------------------------------------------------------------------
# Tests — SQL / call count
# ---------------------------------------------------------------------------

def test_execute_called_four_times():
    c = _std_conn()
    get_personnel_dashboard(c)
    assert c.execute.call_count == 4


def test_first_sql_references_people():
    c = _std_conn()
    get_personnel_dashboard(c)
    first_sql = c.execute.call_args_list[0][0][0]
    assert 'people' in first_sql.lower()


def test_third_sql_references_time_off_request():
    c = _std_conn()
    get_personnel_dashboard(c)
    third_sql = c.execute.call_args_list[2][0][0]
    assert 'time_off_request' in third_sql.lower()


def test_fourth_sql_uses_limit_8():
    c = _std_conn()
    get_personnel_dashboard(c)
    fourth_sql = c.execute.call_args_list[3][0][0]
    assert 'limit 8' in fourth_sql.lower()
