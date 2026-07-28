"""Qt-free Termination process data layer — termination records, exit
interviews, offboarding checklist tasks.

Reuses workforce_analytics_core.set_employment_dates to keep
people.termination_date/employment_status in sync with a termination
record rather than duplicating that logic — creating a termination record
marks the employee terminated as of that date; the record's own `status`
field tracks the separate HR admin process (paperwork, exit interview,
offboarding tasks), which can still be in progress after the employment
itself has ended.
"""

from .workforce_analytics_core import set_employment_dates

TERM_TYPES = ('Voluntary', 'Involuntary', 'Layoff', 'Retirement')
TERM_STATUSES = ('Initiated', 'In Progress', 'Completed')
REHIRE_OPTIONS = ('Yes', 'No', 'Conditional')

EXIT_INTERVIEW_RECOMMEND_OPTIONS = ('Yes', 'No', 'Unsure')

OFFBOARD_STATUSES = ('Pending', 'In Progress', 'Completed')
OFFBOARD_DEFAULT_TASKS = (
    'Return company equipment',
    'Revoke system access',
    'Process final paycheck',
    'Terminate benefits',
    'Collect ID badge/keys',
)


def _ensure_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS termination_record (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL,
            termination_date TEXT, term_type TEXT DEFAULT 'Voluntary',
            reason TEXT DEFAULT '', status TEXT DEFAULT 'Initiated',
            rehire_eligible TEXT DEFAULT 'Yes', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exit_interview (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL,
            interview_date TEXT, interviewer TEXT DEFAULT '',
            reason_for_leaving TEXT DEFAULT '', feedback TEXT DEFAULT '',
            would_recommend TEXT DEFAULT '', notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offboarding_task (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL,
            task TEXT NOT NULL, status TEXT DEFAULT 'Pending',
            due_date TEXT, completed_date TEXT,
            assigned_to TEXT DEFAULT '', notes TEXT DEFAULT ''
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Termination records
# ---------------------------------------------------------------------------

def list_terminations(conn, status=None, search=None) -> list:
    _ensure_tables(conn)
    sql = """
        SELECT tr.id, tr.people_id, tr.termination_date, tr.term_type,
               tr.reason, tr.status, tr.rehire_eligible,
               p.first_name || ' ' || p.last_name AS employee_name,
               d.dept_name
        FROM termination_record tr
        LEFT JOIN people p ON p.id = tr.people_id
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        WHERE TRUE
    """
    params: list = []
    if status:
        sql += " AND tr.status = %s"
        params.append(status)
    if search:
        sql += " AND (p.first_name ILIKE %s OR p.last_name ILIKE %s OR tr.reason ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY tr.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_termination(conn, term_id: int) -> dict | None:
    _ensure_tables(conn)
    row = conn.execute("""
        SELECT tr.*,
               p.first_name || ' ' || p.last_name AS employee_name,
               d.dept_name
        FROM termination_record tr
        LEFT JOIN people p ON p.id = tr.people_id
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        WHERE tr.id = %s
    """, (term_id,)).fetchone()
    return dict(row) if row else None


def create_termination(conn, people_id, termination_date, term_type,
                        reason, status, rehire_eligible, notes,
                        created_by) -> int:
    _ensure_tables(conn)
    row = conn.execute("""
        INSERT INTO termination_record
        (people_id, termination_date, term_type, reason, status,
         rehire_eligible, notes, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (people_id, termination_date or None, term_type or 'Voluntary',
          reason, status or 'Initiated', rehire_eligible or 'Yes',
          notes, created_by)).fetchone()
    if termination_date:
        # set_employment_dates overwrites hire_date unconditionally too —
        # fetch the employee's current one so it isn't wiped out.
        person = conn.execute(
            "SELECT hire_date FROM people WHERE id = %s", (people_id,)
        ).fetchone()
        set_employment_dates(
            conn, people_id, hire_date=person['hire_date'] if person else '',
            termination_date=termination_date, employment_status='terminated',
        )
    return row['id']


def update_termination(conn, term_id: int, **fields) -> None:
    allowed = {
        'termination_date', 'term_type', 'reason', 'status',
        'rehire_eligible', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE termination_record SET {set_clause} WHERE id = %s",
        list(cols.values()) + [term_id],
    )


# ---------------------------------------------------------------------------
# Exit interviews
# ---------------------------------------------------------------------------

def list_exit_interviews(conn, search=None) -> list:
    _ensure_tables(conn)
    sql = """
        SELECT ei.id, ei.people_id, ei.interview_date, ei.interviewer,
               ei.reason_for_leaving, ei.would_recommend,
               p.first_name || ' ' || p.last_name AS employee_name
        FROM exit_interview ei
        LEFT JOIN people p ON p.id = ei.people_id
        WHERE TRUE
    """
    params: list = []
    if search:
        sql += " AND (p.first_name ILIKE %s OR p.last_name ILIKE %s OR ei.reason_for_leaving ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY ei.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_exit_interview(conn, interview_id: int) -> dict | None:
    _ensure_tables(conn)
    row = conn.execute("""
        SELECT ei.*, p.first_name || ' ' || p.last_name AS employee_name
        FROM exit_interview ei
        LEFT JOIN people p ON p.id = ei.people_id
        WHERE ei.id = %s
    """, (interview_id,)).fetchone()
    return dict(row) if row else None


def create_exit_interview(conn, people_id, interview_date, interviewer,
                           reason_for_leaving, feedback, would_recommend,
                           notes) -> int:
    _ensure_tables(conn)
    row = conn.execute("""
        INSERT INTO exit_interview
        (people_id, interview_date, interviewer, reason_for_leaving,
         feedback, would_recommend, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (people_id, interview_date or None, interviewer,
          reason_for_leaving, feedback, would_recommend, notes)).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Offboarding tasks
# ---------------------------------------------------------------------------

def list_offboarding_tasks(conn, status=None, search=None) -> list:
    _ensure_tables(conn)
    sql = """
        SELECT ot.id, ot.people_id, ot.task, ot.status, ot.due_date,
               ot.completed_date, ot.assigned_to,
               p.first_name || ' ' || p.last_name AS employee_name
        FROM offboarding_task ot
        LEFT JOIN people p ON p.id = ot.people_id
        WHERE TRUE
    """
    params: list = []
    if status:
        sql += " AND ot.status = %s"
        params.append(status)
    if search:
        sql += " AND (p.first_name ILIKE %s OR p.last_name ILIKE %s OR ot.task ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY ot.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_offboarding_task(conn, people_id, task, status, due_date,
                             assigned_to, notes) -> int:
    _ensure_tables(conn)
    row = conn.execute("""
        INSERT INTO offboarding_task
        (people_id, task, status, due_date, assigned_to, notes)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
    """, (people_id, task, status or 'Pending', due_date or None,
          assigned_to, notes)).fetchone()
    return row['id']


def complete_offboarding_task(conn, task_id: int, completed_date) -> None:
    conn.execute("""
        UPDATE offboarding_task SET status = 'Completed', completed_date = %s
        WHERE id = %s
    """, (completed_date, task_id))
