"""Tests for skills_matrix_core — competency gap analysis."""

import pytest

from manufacturing.skills_matrix_core import (
    _validate_level, create_skill, create_job_requirement,
    update_job_requirement, upsert_employee_skill, get_employee_gap_report,
    get_org_gap_summary, SKILL_LEVELS,
)


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


# ── _validate_level ──────────────────────────────────────────────────────

def test_validate_level_accepts_all_defined_levels():
    for lvl in SKILL_LEVELS:
        _validate_level(lvl)  # no raise


def test_validate_level_rejects_out_of_range():
    with pytest.raises(ValueError):
        _validate_level(6)


def test_validate_level_rejects_zero():
    with pytest.raises(ValueError):
        _validate_level(0)


# ── CRUD basics ──────────────────────────────────────────────────────────

def test_create_skill_returns_id():
    conn = _Conn(rows=[{'id': 5}])
    skill_id = create_skill(conn, 'TIG Welding', category='Fabrication')
    assert skill_id == 5


def test_create_skill_requires_name():
    conn = _Conn(rows=[{'id': 5}])
    with pytest.raises(ValueError):
        create_skill(conn, '   ')


def test_create_job_requirement_validates_level():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_job_requirement(conn, 'Welder', 1, required_level=9)


def test_create_job_requirement_returns_id():
    conn = _Conn(rows=[{'id': 11}])
    req_id = create_job_requirement(conn, 'Welder', 1, required_level=3)
    assert req_id == 11


def test_update_job_requirement_validates_level():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        update_job_requirement(conn, 1, required_level=99)


def test_upsert_employee_skill_validates_level():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        upsert_employee_skill(conn, 1, 1, level=10)


def test_upsert_employee_skill_passes_params():
    conn = _Conn(rows=[])
    upsert_employee_skill(conn, 7, 3, level=4, certified_date='2026-01-01')
    assert conn.calls[-1][1][:3] == [7, 3, 4]


# ── get_employee_gap_report ──────────────────────────────────────────────

def test_get_employee_gap_report_raises_if_employee_missing():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError, match='No employee'):
        get_employee_gap_report(conn, 999)


def test_get_employee_gap_report_flags_gap_and_met():
    conn = _MultiConn([
        [{'id': 1, 'first_name': 'Ana', 'last_name': 'Reyes', 'job_title': 'Welder'}],
        [
            {'skill_id': 1, 'skill_name': 'TIG Welding', 'required_level': 4, 'actual_level': 2},
            {'skill_id': 2, 'skill_name': 'Safety', 'required_level': 3, 'actual_level': 3},
        ],
    ])
    report = get_employee_gap_report(conn, 1)
    assert report['job_title'] == 'Welder'
    tig = next(g for g in report['gaps'] if g['skill_name'] == 'TIG Welding')
    assert tig['gap'] == 2
    assert tig['status'] == 'gap'
    safety = next(g for g in report['gaps'] if g['skill_name'] == 'Safety')
    assert safety['gap'] == 0
    assert safety['status'] == 'met'


def test_get_employee_gap_report_not_assessed_when_no_row():
    conn = _MultiConn([
        [{'id': 1, 'first_name': 'Ana', 'last_name': 'Reyes', 'job_title': 'Welder'}],
        [{'skill_id': 1, 'skill_name': 'TIG Welding', 'required_level': 3, 'actual_level': None}],
    ])
    report = get_employee_gap_report(conn, 1)
    g = report['gaps'][0]
    assert g['actual_level'] == 0
    assert g['status'] == 'not_assessed'
    assert g['gap'] == 3


# ── get_org_gap_summary ──────────────────────────────────────────────────

def test_get_org_gap_summary_computes_gap_count():
    conn = _Conn(rows=[
        {'people_id': 1, 'first_name': 'Ana', 'last_name': 'Reyes',
         'job_title': 'Welder', 'dept_name': 'Production',
         'required_count': 3, 'met_count': 1},
    ])
    summary = get_org_gap_summary(conn)
    assert summary[0]['gap_count'] == 2
