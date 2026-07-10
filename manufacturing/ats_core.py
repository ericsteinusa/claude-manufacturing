"""ats_core.py — Qt-free Applicant Tracking / Recruiting (ATS), 5/10 of
the top-10 ERPs have it. Closes HR/Payroll & Personnel's last remaining
domain gap.

A job requisition is an open position; a candidate is a person under
consideration (not yet an employee — `people` stays the single source of
truth for actual staff, the same way `customer`/`supplier` stay separate
master files from each other); an application links one candidate to one
requisition and moves through a fixed pipeline of stages, each transition
recorded in `application_stage_history` so the pipeline funnel is
reconstructable, not just the current snapshot.

**Hiring a candidate is the one place this module writes outside itself**:
`convert_to_employee` creates a real `people` row via
`personnel_core.create_person` and sets its `hire_date` via
`workforce_analytics_core.set_employment_dates` — the same hire-date
column `workforce_analytics_core` added and that its tenure/trend/turnover
math depends on. This is the only path in the app that sets a hire_date
automatically instead of requiring a manual HR entry, so an employee hired
through the ATS is counted correctly by Workforce Analytics from day one;
an employee added directly via `/people/new/` (bypassing the ATS
entirely) still needs its hire_date set by hand, same as before this
module existed.

Every function takes an open connection; the caller owns the transaction
(same convention as skills_matrix_core / benefits_core).
"""

from __future__ import annotations

import datetime

from .personnel_core import create_person
from .workforce_analytics_core import set_employment_dates

REQUISITION_STATUSES = ('open', 'on_hold', 'filled', 'closed')
STAGES = ('Applied', 'Screening', 'Interview', 'Offer', 'Hired', 'Rejected')
OPEN_STAGES = ('Applied', 'Screening', 'Interview', 'Offer')


def _today() -> str:
    return datetime.date.today().isoformat()


def ensure_ats_tables(conn):
    """Create job_requisition / candidate / application /
    application_stage_history if absent. Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_requisition (
            id                SERIAL PRIMARY KEY,
            title             TEXT NOT NULL,
            dept_id           INTEGER REFERENCES dept(dept_id),
            status            TEXT NOT NULL DEFAULT 'open',
            description       TEXT NOT NULL DEFAULT '',
            target_hire_date  TEXT,
            created_by        TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidate (
            id             SERIAL PRIMARY KEY,
            first_name     TEXT NOT NULL,
            last_name      TEXT NOT NULL,
            email          TEXT NOT NULL DEFAULT '',
            phone          TEXT NOT NULL DEFAULT '',
            resume_notes   TEXT NOT NULL DEFAULT '',
            source         TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS application (
            id             SERIAL PRIMARY KEY,
            requisition_id INTEGER NOT NULL REFERENCES job_requisition(id),
            candidate_id   INTEGER NOT NULL REFERENCES candidate(id),
            stage          TEXT NOT NULL DEFAULT 'Applied',
            applied_date   TEXT NOT NULL DEFAULT '',
            notes          TEXT NOT NULL DEFAULT '',
            hired_people_id INTEGER REFERENCES people(id),
            created_by     TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS application_requisition ON application(requisition_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS application_candidate ON application(candidate_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS application_stage_history (
            id             SERIAL PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES application(id),
            stage          TEXT NOT NULL,
            changed_by     TEXT NOT NULL DEFAULT '',
            changed_at     TEXT NOT NULL DEFAULT '',
            notes          TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS application_stage_history_app "
        "ON application_stage_history(application_id)"
    )


# ---------------------------------------------------------------------------
# Requisitions
# ---------------------------------------------------------------------------

def list_requisitions(conn, status=None, dept_id=None, search=None):
    sql = (
        "SELECT r.*, d.dept_name FROM job_requisition r "
        "LEFT JOIN dept d ON d.dept_id = r.dept_id WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND r.status = %s"
        params.append(status)
    if dept_id:
        sql += " AND r.dept_id = %s"
        params.append(dept_id)
    if search:
        sql += " AND r.title ILIKE %s"
        params.append(f'%{search}%')
    sql += " ORDER BY r.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_requisition(conn, req_id):
    row = conn.execute(
        "SELECT r.*, d.dept_name FROM job_requisition r "
        "LEFT JOIN dept d ON d.dept_id = r.dept_id WHERE r.id = %s",
        (req_id,),
    ).fetchone()
    return dict(row) if row else None


def create_requisition(conn, title, dept_id, description='',
                       target_hire_date=None, created_by=''):
    if not title or not title.strip():
        raise ValueError('title is required')
    row = conn.execute(
        "INSERT INTO job_requisition "
        "(title, dept_id, description, target_hire_date, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (title.strip(), dept_id, description or '', target_hire_date or None,
         created_by or ''),
    ).fetchone()
    return row['id']


def update_requisition_status(conn, req_id, status):
    if status not in REQUISITION_STATUSES:
        raise ValueError(f'status must be one of {REQUISITION_STATUSES}')
    conn.execute(
        "UPDATE job_requisition SET status = %s WHERE id = %s", (status, req_id)
    )


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

def list_candidates(conn, search=None):
    sql = "SELECT * FROM candidate WHERE TRUE"
    params: list = []
    if search:
        sql += " AND (first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s)"
        like = f'%{search}%'
        params += [like, like, like]
    sql += " ORDER BY last_name, first_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_candidate(conn, candidate_id):
    row = conn.execute(
        "SELECT * FROM candidate WHERE id = %s", (candidate_id,)
    ).fetchone()
    return dict(row) if row else None


def create_candidate(conn, first_name, last_name, email='', phone='',
                     resume_notes='', source='', created_by=''):
    if not first_name or not first_name.strip():
        raise ValueError('first_name is required')
    if not last_name or not last_name.strip():
        raise ValueError('last_name is required')
    row = conn.execute(
        "INSERT INTO candidate "
        "(first_name, last_name, email, phone, resume_notes, source, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (first_name.strip(), last_name.strip(), email or '', phone or '',
         resume_notes or '', source or '', created_by or ''),
    ).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Applications & pipeline
# ---------------------------------------------------------------------------

def list_applications(conn, requisition_id=None, candidate_id=None, stage=None):
    sql = (
        "SELECT a.*, c.first_name, c.last_name, c.email, "
        "r.title AS requisition_title "
        "FROM application a "
        "JOIN candidate c ON c.id = a.candidate_id "
        "JOIN job_requisition r ON r.id = a.requisition_id "
        "WHERE TRUE"
    )
    params: list = []
    if requisition_id:
        sql += " AND a.requisition_id = %s"
        params.append(requisition_id)
    if candidate_id:
        sql += " AND a.candidate_id = %s"
        params.append(candidate_id)
    if stage:
        sql += " AND a.stage = %s"
        params.append(stage)
    sql += " ORDER BY a.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_application(conn, app_id):
    row = conn.execute(
        "SELECT a.*, c.first_name, c.last_name, c.email, c.phone, "
        "r.title AS requisition_title, r.id AS requisition_id "
        "FROM application a "
        "JOIN candidate c ON c.id = a.candidate_id "
        "JOIN job_requisition r ON r.id = a.requisition_id "
        "WHERE a.id = %s",
        (app_id,),
    ).fetchone()
    if not row:
        return None
    app = dict(row)
    app['history'] = get_stage_history(conn, app_id)
    return app


def get_stage_history(conn, app_id):
    rows = conn.execute(
        "SELECT * FROM application_stage_history WHERE application_id = %s "
        "ORDER BY id",
        (app_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_application(conn, requisition_id, candidate_id, notes='', created_by=''):
    row = conn.execute(
        "INSERT INTO application "
        "(requisition_id, candidate_id, stage, applied_date, notes, created_by) "
        "VALUES (%s,%s,'Applied',%s,%s,%s) RETURNING id",
        (requisition_id, candidate_id, _today(), notes or '', created_by or ''),
    ).fetchone()
    app_id = row['id']
    _record_stage(conn, app_id, 'Applied', created_by, notes)
    return app_id


def _record_stage(conn, app_id, stage, changed_by='', notes=''):
    conn.execute(
        "INSERT INTO application_stage_history "
        "(application_id, stage, changed_by, changed_at, notes) "
        "VALUES (%s,%s,%s,%s,%s)",
        (app_id, stage, changed_by or '', _today(), notes or ''),
    )


def advance_stage(conn, app_id, new_stage, changed_by='', notes=''):
    """Move an application to a new pipeline stage. Raises if the
    application is already in a terminal stage ('Hired' or 'Rejected') —
    reopening a closed application isn't supported; create a new
    application against a (possibly reopened) requisition instead."""
    if new_stage not in STAGES:
        raise ValueError(f'stage must be one of {STAGES}')
    row = conn.execute(
        "SELECT stage FROM application WHERE id = %s", (app_id,)
    ).fetchone()
    if not row:
        raise ValueError(f'No application with id {app_id}')
    if row['stage'] in ('Hired', 'Rejected'):
        raise ValueError(
            f"Application is already in a terminal stage ({row['stage']!r})"
        )
    conn.execute(
        "UPDATE application SET stage = %s WHERE id = %s", (new_stage, app_id)
    )
    _record_stage(conn, app_id, new_stage, changed_by, notes)


def convert_to_employee(conn, app_id, hire_date, dept_id=None,
                        dept_sub_id=None, job_title='', created_by=''):
    """Advance an application to 'Hired' and create the real `people` row
    for them, with hire_date set via workforce_analytics_core so they're
    immediately counted by Workforce Analytics. Returns the new people id.
    Raises if the application is already in a terminal stage."""
    app = get_application(conn, app_id)
    if not app:
        raise ValueError(f'No application with id {app_id}')
    if app['stage'] in ('Hired', 'Rejected'):
        raise ValueError(
            f"Application is already in a terminal stage ({app['stage']!r})"
        )
    people_id = create_person(
        conn, app['first_name'], app['last_name'], email=app['email'],
        dept_id=dept_id, dept_sub_id=dept_sub_id, job_title=job_title,
        created_by=created_by,
    )
    set_employment_dates(conn, people_id, hire_date, employment_status='active')
    conn.execute(
        "UPDATE application SET stage = 'Hired', hired_people_id = %s WHERE id = %s",
        (people_id, app_id),
    )
    _record_stage(conn, app_id, 'Hired', created_by, f'Converted to employee #{people_id}')
    return people_id


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_ats_dashboard(conn):
    """{'open_requisitions', 'total_candidates', 'by_stage', 'recent_hires'}."""
    req_row = conn.execute(
        "SELECT COUNT(*) AS open_requisitions FROM job_requisition WHERE status = 'open'"
    ).fetchone()
    cand_row = conn.execute(
        "SELECT COUNT(*) AS total_candidates FROM candidate"
    ).fetchone()
    stage_rows = conn.execute(
        "SELECT stage, COUNT(*) AS count FROM application GROUP BY stage"
    ).fetchall()
    hire_rows = conn.execute(
        "SELECT a.id, a.hired_people_id, c.first_name, c.last_name, "
        "r.title AS requisition_title "
        "FROM application a "
        "JOIN candidate c ON c.id = a.candidate_id "
        "JOIN job_requisition r ON r.id = a.requisition_id "
        "WHERE a.stage = 'Hired' ORDER BY a.id DESC LIMIT 8"
    ).fetchall()
    by_stage = {s: 0 for s in STAGES}
    for r in stage_rows:
        by_stage[r['stage']] = r['count']
    return {
        'open_requisitions': req_row['open_requisitions'] if req_row else 0,
        'total_candidates': cand_row['total_candidates'] if cand_row else 0,
        'by_stage': by_stage,
        'recent_hires': [dict(r) for r in hire_rows],
    }
