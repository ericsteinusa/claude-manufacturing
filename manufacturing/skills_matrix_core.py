"""skills_matrix_core.py — Qt-free Skills Matrix & Competency Gap Analysis.

6/10 of the top-10 ERPs ship this (usually as part of a broader talent-
management module); this codebase already tracks training/certification
records (personnel_core.py's pers_training) but had no concept of "what
skill level does this job require" vs "what skill level does this
employee actually have" before this module.

Tables:
  skill                  — master list of competencies (e.g. "TIG Welding",
                           "Forklift Operation", "SPC Analysis")
  job_skill_requirement  — required proficiency level for a skill, keyed by
                           position.job_title (free text — position has no
                           job-title master table with an id, so this
                           matches on the same free-text value the rest of
                           the personnel domain already uses, the same
                           convention quality_core.qa_supplier matches
                           suppliers by name rather than an FK)
  employee_skill         — an employee's actual assessed level per skill,
                           one row per (people_id, skill_id)

Proficiency levels are 1-5 (see SKILL_LEVEL_LABELS) — coarse enough to
assess in a review, granular enough to show a real gap.

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / sampling_plan_core).
"""

from __future__ import annotations

SKILL_LEVEL_LABELS = {
    1: 'Novice',
    2: 'Basic',
    3: 'Competent',
    4: 'Proficient',
    5: 'Expert',
}
SKILL_LEVELS = tuple(SKILL_LEVEL_LABELS)


def ensure_skills_matrix_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skill (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL UNIQUE,
            category     TEXT NOT NULL DEFAULT '',
            description  TEXT NOT NULL DEFAULT '',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_skill_requirement (
            id              SERIAL PRIMARY KEY,
            job_title       TEXT NOT NULL,
            skill_id        INTEGER NOT NULL REFERENCES skill(id),
            required_level  INTEGER NOT NULL DEFAULT 1,
            notes           TEXT NOT NULL DEFAULT '',
            created_by      TEXT NOT NULL DEFAULT '',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (job_title, skill_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_skill (
            id              SERIAL PRIMARY KEY,
            people_id       INTEGER NOT NULL REFERENCES people(id),
            skill_id        INTEGER NOT NULL REFERENCES skill(id),
            level           INTEGER NOT NULL DEFAULT 1,
            certified_date  TEXT,
            notes           TEXT NOT NULL DEFAULT '',
            created_by      TEXT NOT NULL DEFAULT '',
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (people_id, skill_id)
        )
    """)


def _validate_level(level):
    if level not in SKILL_LEVELS:
        raise ValueError(f'Level must be one of {SKILL_LEVELS}, got {level!r}')


# ---------------------------------------------------------------------------
# Skill master CRUD
# ---------------------------------------------------------------------------

def list_skills(conn, search=None):
    sql = "SELECT * FROM skill WHERE TRUE"
    params: list = []
    if search:
        sql += " AND (name ILIKE %s OR category ILIKE %s)"
        params.extend([f"%{search}%"] * 2)
    sql += " ORDER BY category, name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_skill(conn, skill_id):
    row = conn.execute("SELECT * FROM skill WHERE id = %s", (skill_id,)).fetchone()
    return dict(row) if row else None


def create_skill(conn, name, category='', description='', created_by=''):
    if not name.strip():
        raise ValueError('Name is required.')
    row = conn.execute(
        "INSERT INTO skill (name, category, description, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (name.strip(), category or '', description or '', created_by or ''),
    ).fetchone()
    return row['id']


def update_skill(conn, skill_id, **fields):
    allowed = {'name', 'category', 'description'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE skill SET {set_clause} WHERE id = %s",
        list(cols.values()) + [skill_id],
    )


# ---------------------------------------------------------------------------
# Job requirements
# ---------------------------------------------------------------------------

def list_distinct_job_titles(conn):
    rows = conn.execute(
        "SELECT DISTINCT job_title FROM position "
        "WHERE job_title IS NOT NULL AND job_title != '' "
        "ORDER BY job_title"
    ).fetchall()
    return [r['job_title'] for r in rows]


def list_job_requirements(conn, job_title=None):
    sql = (
        "SELECT jr.*, s.name AS skill_name, s.category AS skill_category "
        "FROM job_skill_requirement jr "
        "JOIN skill s ON s.id = jr.skill_id "
        "WHERE TRUE"
    )
    params: list = []
    if job_title:
        sql += " AND LOWER(jr.job_title) = LOWER(%s)"
        params.append(job_title)
    sql += " ORDER BY jr.job_title, s.name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_job_requirement(conn, job_title, skill_id, required_level,
                           notes='', created_by=''):
    if not job_title.strip():
        raise ValueError('Job title is required.')
    _validate_level(required_level)
    row = conn.execute(
        "INSERT INTO job_skill_requirement "
        "(job_title, skill_id, required_level, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (job_title.strip(), skill_id, required_level, notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def update_job_requirement(conn, req_id, **fields):
    allowed = {'required_level', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'required_level' in cols:
        _validate_level(cols['required_level'])
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE job_skill_requirement SET {set_clause} WHERE id = %s",
        list(cols.values()) + [req_id],
    )


def delete_job_requirement(conn, req_id):
    conn.execute("DELETE FROM job_skill_requirement WHERE id = %s", (req_id,))


# ---------------------------------------------------------------------------
# Employee skill levels
# ---------------------------------------------------------------------------

def list_employee_skills(conn, people_id=None, skill_id=None):
    conditions = ["TRUE"]
    params: list = []
    if people_id:
        conditions.append("es.people_id = %s")
        params.append(people_id)
    if skill_id:
        conditions.append("es.skill_id = %s")
        params.append(skill_id)
    rows = conn.execute(f"""
        SELECT es.*, s.name AS skill_name, s.category AS skill_category,
               p.first_name, p.last_name
        FROM employee_skill es
        JOIN skill s ON s.id = es.skill_id
        JOIN people p ON p.id = es.people_id
        WHERE {" AND ".join(conditions)}
        ORDER BY s.name
    """, params).fetchall()
    return [dict(r) for r in rows]


def upsert_employee_skill(conn, people_id, skill_id, level, certified_date=None,
                          notes='', created_by=''):
    _validate_level(level)
    conn.execute(
        "INSERT INTO employee_skill "
        "(people_id, skill_id, level, certified_date, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (people_id, skill_id) DO UPDATE SET "
        "level = EXCLUDED.level, certified_date = EXCLUDED.certified_date, "
        "notes = EXCLUDED.notes, updated_at = NOW()",
        (people_id, skill_id, level, certified_date or None, notes or '', created_by or ''),
    )


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def get_employee_gap_report(conn, people_id):
    """Return {job_title, gaps: [{skill_id, skill_name, required_level,
    actual_level, gap, status}]} for this employee's job title (from
    position.job_title). actual_level is 0 (status 'not_assessed') when the
    employee has no employee_skill row for a required skill yet — that's a
    gap in its own right, not the same as a confirmed level-0 assessment,
    but is reported the same way since both mean "not meeting the
    requirement today"."""
    person = conn.execute(
        "SELECT p.id, p.first_name, p.last_name, pos.job_title "
        "FROM people p LEFT JOIN position pos ON pos.people_id = p.id "
        "WHERE p.id = %s",
        (people_id,),
    ).fetchone()
    if not person:
        raise ValueError(f'No employee with id {people_id}')
    job_title = person['job_title'] or ''

    rows = conn.execute("""
        SELECT s.id AS skill_id, s.name AS skill_name, jr.required_level,
               es.level AS actual_level
        FROM job_skill_requirement jr
        JOIN skill s ON s.id = jr.skill_id
        LEFT JOIN employee_skill es
               ON es.skill_id = jr.skill_id AND es.people_id = %s
        WHERE LOWER(jr.job_title) = LOWER(%s)
        ORDER BY s.name
    """, (people_id, job_title)).fetchall()

    gaps = []
    for r in rows:
        actual = r['actual_level'] if r['actual_level'] is not None else 0
        required = r['required_level']
        gap = max(0, required - actual)
        status = 'not_assessed' if r['actual_level'] is None else ('met' if gap == 0 else 'gap')
        gaps.append({
            'skill_id': r['skill_id'],
            'skill_name': r['skill_name'],
            'required_level': required,
            'actual_level': actual,
            'gap': gap,
            'status': status,
        })
    return {
        'people_id': people_id,
        'first_name': person['first_name'],
        'last_name': person['last_name'],
        'job_title': job_title,
        'gaps': gaps,
    }


def get_org_gap_summary(conn, dept_id=None):
    """One row per employee whose job title has at least one skill
    requirement defined, with a gap count — the roll-up view for a
    'Skills Matrix' landing page. Employees whose job title has no
    requirements configured yet are omitted (nothing to assess), rather
    than shown with a misleading zero-gap row."""
    conditions = ["jr.job_title IS NOT NULL"]
    params: list = []
    if dept_id:
        conditions.append("p.dept_id = %s")
        params.append(dept_id)
    rows = conn.execute(f"""
        SELECT p.id AS people_id, p.first_name, p.last_name, pos.job_title,
               d.dept_name,
               COUNT(jr.id) AS required_count,
               COUNT(es.id) FILTER (
                   WHERE es.level IS NOT NULL AND es.level >= jr.required_level
               ) AS met_count
        FROM people p
        JOIN position pos ON pos.people_id = p.id
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        JOIN job_skill_requirement jr ON LOWER(jr.job_title) = LOWER(pos.job_title)
        LEFT JOIN employee_skill es
               ON es.people_id = p.id AND es.skill_id = jr.skill_id
        WHERE {" AND ".join(conditions)}
        GROUP BY p.id, p.first_name, p.last_name, pos.job_title, d.dept_name
        ORDER BY (COUNT(jr.id) - COUNT(es.id) FILTER (
                      WHERE es.level IS NOT NULL AND es.level >= jr.required_level
                  )) DESC, p.last_name
    """, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['gap_count'] = d['required_count'] - d['met_count']
        result.append(d)
    return result
