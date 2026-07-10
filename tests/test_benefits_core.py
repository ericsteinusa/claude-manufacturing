"""Tests for benefits_core — Benefits Management."""

import pytest

from manufacturing.benefits_core import (
    create_plan, update_plan, enroll_employee, waive_enrollment,
    terminate_enrollment, get_employee_benefits, get_benefits_dashboard,
    PLAN_TYPES, TIERS,
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


# ── create_plan ──────────────────────────────────────────────────────────

def test_create_plan_returns_id():
    conn = _Conn(rows=[{'id': 3}])
    plan_id = create_plan(conn, 'PPO Gold', 'Health', carrier='Acme Health',
                          employee_cost_per_pay=45.0, employer_cost_per_pay=180.0)
    assert plan_id == 3


def test_create_plan_requires_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_plan(conn, '   ', 'Health')


def test_create_plan_validates_plan_type():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_plan(conn, 'Bad Plan', 'NotARealType')


def test_all_plan_types_accepted():
    for pt in PLAN_TYPES:
        conn = _Conn(rows=[{'id': 1}])
        create_plan(conn, 'Plan', pt)  # no raise


# ── update_plan ──────────────────────────────────────────────────────────

def test_update_plan_validates_plan_type():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        update_plan(conn, 1, plan_type='Bogus')


def test_update_plan_noop_with_no_allowed_fields():
    conn = _Conn(rows=[])
    update_plan(conn, 1, unrelated_field='x')
    assert conn.calls == []


def test_update_plan_builds_set_clause():
    conn = _Conn(rows=[])
    update_plan(conn, 1, name='New Name', is_active=0)
    sql, params = conn.calls[-1]
    assert 'name = %s' in sql
    assert 'is_active = %s' in sql
    assert params[-1] == 1


# ── enroll_employee ──────────────────────────────────────────────────────

def test_enroll_employee_raises_if_plan_missing():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError, match='No plan'):
        enroll_employee(conn, 1, 99, 'Employee Only')


def test_enroll_employee_raises_if_plan_inactive():
    conn = _MultiConn([[{'id': 1, 'name': 'Old Plan', 'is_active': 0}]])
    with pytest.raises(ValueError, match='not active'):
        enroll_employee(conn, 1, 1, 'Employee Only')


def test_enroll_employee_validates_tier():
    conn = _MultiConn([[{'id': 1, 'name': 'Plan', 'is_active': 1}]])
    with pytest.raises(ValueError, match='tier must be'):
        enroll_employee(conn, 1, 1, 'Not A Tier')


def test_enroll_employee_rejects_duplicate_active_enrollment():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Plan', 'is_active': 1}],
        [{'id': 5}],
    ])
    with pytest.raises(ValueError, match='already has an active enrollment'):
        enroll_employee(conn, 1, 1, 'Employee Only')


def test_enroll_employee_returns_new_id():
    conn = _MultiConn([
        [{'id': 1, 'name': 'Plan', 'is_active': 1}],
        [],
        [{'id': 42}],
    ])
    enrollment_id = enroll_employee(conn, 7, 1, 'Family', dependents_count=2)
    assert enrollment_id == 42


def test_all_tiers_accepted():
    for tier in TIERS:
        conn = _MultiConn([
            [{'id': 1, 'name': 'Plan', 'is_active': 1}],
            [],
            [{'id': 1}],
        ])
        enroll_employee(conn, 1, 1, tier)  # no raise


# ── status transitions ──────────────────────────────────────────────────

def test_waive_enrollment_sets_status():
    conn = _Conn(rows=[])
    waive_enrollment(conn, 9)
    sql, params = conn.calls[-1]
    assert 'waived' in params
    assert params[-1] == 9


def test_terminate_enrollment_sets_status():
    conn = _Conn(rows=[])
    terminate_enrollment(conn, 9)
    sql, params = conn.calls[-1]
    assert 'terminated' in params


# ── reporting ────────────────────────────────────────────────────────────

def test_get_employee_benefits_sums_costs():
    conn = _Conn(rows=[
        {'id': 1, 'people_id': 5, 'plan_id': 1, 'tier': 'Family',
         'status': 'active', 'plan_name': 'PPO Gold', 'plan_type': 'Health',
         'employee_cost_per_pay': 45.0, 'employer_cost_per_pay': 180.0,
         'first_name': 'Ana', 'last_name': 'Reyes', 'carrier': 'Acme',
         'dependents_count': 2, 'enrollment_date': '2026-01-01',
         'termination_date': None, 'notes': '', 'created_by': ''},
        {'id': 2, 'people_id': 5, 'plan_id': 2, 'tier': 'Employee Only',
         'status': 'active', 'plan_name': 'Dental Basic', 'plan_type': 'Dental',
         'employee_cost_per_pay': 10.0, 'employer_cost_per_pay': 20.0,
         'first_name': 'Ana', 'last_name': 'Reyes', 'carrier': 'Acme',
         'dependents_count': 0, 'enrollment_date': '2026-01-01',
         'termination_date': None, 'notes': '', 'created_by': ''},
    ])
    result = get_employee_benefits(conn, 5)
    assert result['total_employee_cost_per_pay'] == 55.0
    assert result['total_employer_cost_per_pay'] == 200.0
    assert len(result['enrollments']) == 2


def test_get_benefits_dashboard_shape():
    conn = _MultiConn([
        [{'total': 4, 'active': 3}],
        [{'active_count': 10, 'total_employee_cost': 500.0, 'total_employer_cost': 2000.0}],
        [{'plan_type': 'Health', 'enrolled_count': 7, 'employer_cost': 1500.0}],
    ])
    dash = get_benefits_dashboard(conn)
    assert dash['plans']['active'] == 3
    assert dash['enrollments']['active_count'] == 10
    assert dash['by_plan_type'][0]['plan_type'] == 'Health'
