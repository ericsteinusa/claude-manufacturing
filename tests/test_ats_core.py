"""Tests for ats_core — Applicant Tracking / Recruiting (ATS)."""

import pytest

from manufacturing import ats_core
from manufacturing.ats_core import (
    create_requisition, update_requisition_status, create_candidate,
    create_application, advance_stage, convert_to_employee,
    get_ats_dashboard, STAGES, REQUISITION_STATUSES,
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


# ── requisitions ─────────────────────────────────────────────────────────

def test_create_requisition_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    req_id = create_requisition(conn, 'Welder II', 3)
    assert req_id == 1


def test_create_requisition_requires_title():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_requisition(conn, '   ', 3)


def test_update_requisition_status_validates():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        update_requisition_status(conn, 1, 'bogus')


def test_all_requisition_statuses_accepted():
    for status in REQUISITION_STATUSES:
        conn = _Conn(rows=[])
        update_requisition_status(conn, 1, status)  # no raise


# ── candidates ───────────────────────────────────────────────────────────

def test_create_candidate_returns_id():
    conn = _Conn(rows=[{'id': 5}])
    cand_id = create_candidate(conn, 'Ana', 'Reyes', email='ana@example.com')
    assert cand_id == 5


def test_create_candidate_requires_first_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_candidate(conn, '  ', 'Reyes')


def test_create_candidate_requires_last_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_candidate(conn, 'Ana', '  ')


# ── applications / pipeline ──────────────────────────────────────────────

def test_create_application_records_initial_stage_history():
    conn = _MultiConn([
        [{'id': 10}],  # INSERT INTO application
        [],  # INSERT INTO application_stage_history
    ])
    app_id = create_application(conn, 1, 5, notes='referred by Dana')
    assert app_id == 10
    history_calls = [c for c in conn.calls if 'INSERT INTO application_stage_history' in c[0]]
    assert len(history_calls) == 1
    assert history_calls[0][1][1] == 'Applied'


def test_advance_stage_validates_stage_name():
    conn = _MultiConn([[{'stage': 'Applied'}]])
    with pytest.raises(ValueError, match='stage must be one of'):
        advance_stage(conn, 1, 'NotAStage')


def test_advance_stage_raises_if_application_missing():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError, match='No application'):
        advance_stage(conn, 999, 'Screening')


def test_advance_stage_rejects_terminal_stage():
    conn = _MultiConn([[{'stage': 'Hired'}]])
    with pytest.raises(ValueError, match='terminal stage'):
        advance_stage(conn, 1, 'Screening')


def test_advance_stage_updates_and_records_history():
    conn = _MultiConn([
        [{'stage': 'Applied'}],  # lookup
        [],  # UPDATE application
        [],  # INSERT stage history
    ])
    advance_stage(conn, 1, 'Screening', changed_by='hr@example.com')
    update_calls = [c for c in conn.calls if c[0].startswith('UPDATE application SET stage')]
    assert update_calls[0][1] == ['Screening', 1]


def test_all_stages_accepted_by_advance_stage():
    for stage in STAGES:
        conn = _MultiConn([
            [{'stage': 'Applied'}],
            [],
            [],
        ])
        advance_stage(conn, 1, stage)  # no raise


# ── convert_to_employee ──────────────────────────────────────────────────

def test_convert_to_employee_raises_if_application_missing(monkeypatch):
    conn = _MultiConn([[]])  # get_application -> None
    with pytest.raises(ValueError, match='No application'):
        convert_to_employee(conn, 999, '2026-01-01')


def test_convert_to_employee_rejects_terminal_stage(monkeypatch):
    monkeypatch.setattr(ats_core, 'get_application', lambda conn, app_id: {
        'id': app_id, 'stage': 'Rejected', 'first_name': 'Ana', 'last_name': 'Reyes',
        'email': 'ana@example.com',
    })
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='terminal stage'):
        convert_to_employee(conn, 1, '2026-01-01')


def test_convert_to_employee_creates_person_and_sets_hire_date(monkeypatch):
    monkeypatch.setattr(ats_core, 'get_application', lambda conn, app_id: {
        'id': app_id, 'stage': 'Offer', 'first_name': 'Ana', 'last_name': 'Reyes',
        'email': 'ana@example.com',
    })
    created_person_args = {}
    set_dates_args = {}

    def fake_create_person(conn, first_name, last_name, **kwargs):
        created_person_args['first_name'] = first_name
        created_person_args['last_name'] = last_name
        created_person_args.update(kwargs)
        return 77

    def fake_set_employment_dates(conn, people_id, hire_date, **kwargs):
        set_dates_args['people_id'] = people_id
        set_dates_args['hire_date'] = hire_date
        set_dates_args.update(kwargs)

    monkeypatch.setattr(ats_core, 'create_person', fake_create_person)
    monkeypatch.setattr(ats_core, 'set_employment_dates', fake_set_employment_dates)

    conn = _Conn(rows=[])
    people_id = convert_to_employee(conn, 1, '2026-03-01', dept_id=2, job_title='Welder')

    assert people_id == 77
    assert created_person_args['first_name'] == 'Ana'
    assert created_person_args['dept_id'] == 2
    assert set_dates_args['people_id'] == 77
    assert set_dates_args['hire_date'] == '2026-03-01'
    assert set_dates_args['employment_status'] == 'active'

    update_calls = [c for c in conn.calls if "stage = 'Hired'" in c[0]]
    assert len(update_calls) == 1
    assert update_calls[0][1] == [77, 1]


# ── dashboard ────────────────────────────────────────────────────────────

def test_get_ats_dashboard_shape():
    conn = _MultiConn([
        [{'open_requisitions': 3}],
        [{'total_candidates': 12}],
        [{'stage': 'Applied', 'count': 5}, {'stage': 'Hired', 'count': 2}],
        [{'id': 1, 'hired_people_id': 77, 'first_name': 'Ana', 'last_name': 'Reyes',
          'requisition_title': 'Welder II'}],
    ])
    dash = get_ats_dashboard(conn)
    assert dash['open_requisitions'] == 3
    assert dash['total_candidates'] == 12
    assert dash['by_stage']['Applied'] == 5
    assert dash['by_stage']['Hired'] == 2
    assert dash['by_stage']['Rejected'] == 0
    assert dash['recent_hires'][0]['first_name'] == 'Ana'
