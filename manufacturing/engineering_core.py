"""
engineering_core.py — Qt-free data layer for Engineering web views.
Tables: eng_project, eng_design_review, eng_task
No PyQt6, no commit inside any function.
"""

import datetime

PROJECT_STATUSES = ('planning', 'in_progress', 'on_hold', 'completed', 'cancelled')
TASK_STATUSES    = ('open', 'in_progress', 'on_hold', 'completed', 'cancelled')
ECR_STATUSES     = ('draft', 'pending', 'approved', 'rejected', 'revision_needed')
PRIORITIES       = ('critical', 'high', 'medium', 'low')


def _today():
    return datetime.date.today().isoformat()


def _year():
    return datetime.date.today().year


# ---------------------------------------------------------------------------
# Reference data helpers
# ---------------------------------------------------------------------------

def load_products(conn):
    rows = conn.execute(
        "SELECT id, name FROM product ORDER BY name"
    ).fetchall()
    return [{'id': r['id'], 'label': r['name']} for r in rows]


def load_people(conn):
    rows = conn.execute(
        "SELECT id, first_name, last_name, email FROM people ORDER BY last_name, first_name"
    ).fetchall()
    return [{'id': r['id'],
             'label': f"{r['first_name']} {r['last_name']}",
             'email': r['email']} for r in rows]


# ---------------------------------------------------------------------------
# Sequence number helpers
# ---------------------------------------------------------------------------

def next_project_number(conn):
    yr = _year()
    prefix = f"PROJ-{yr}-"
    row = conn.execute(
        "SELECT project_number FROM eng_project WHERE project_number LIKE %s",
        (f"{prefix}%",)
    ).fetchall()
    nums = []
    for r in row:
        tail = r['project_number'][len(prefix):]
        if tail.isdigit():
            nums.append(int(tail))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


def next_ecr_number(conn):
    yr = _year()
    prefix = f"ECR-{yr}-"
    row = conn.execute(
        "SELECT ecr_number FROM eng_design_review WHERE ecr_number LIKE %s",
        (f"{prefix}%",)
    ).fetchall()
    nums = []
    for r in row:
        tail = r['ecr_number'][len(prefix):]
        if tail.isdigit():
            nums.append(int(tail))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_eng_dashboard(conn):
    proj_row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='planning')    AS planning,
            COUNT(*) FILTER (WHERE status='in_progress') AS in_progress,
            COUNT(*) FILTER (WHERE status='on_hold')     AS on_hold,
            COUNT(*) FILTER (WHERE status='completed')   AS completed,
            COUNT(*)                                      AS total
        FROM eng_project
    """).fetchone()
    ecr_row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='draft')    AS draft,
            COUNT(*) FILTER (WHERE status='pending')  AS pending,
            COUNT(*) FILTER (WHERE status='approved') AS approved,
            COUNT(*)                                   AS total
        FROM eng_design_review
    """).fetchone()
    task_row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='open')        AS open_tasks,
            COUNT(*) FILTER (WHERE status='in_progress') AS active_tasks,
            COUNT(*) FILTER (WHERE due_date < %s AND status NOT IN ('completed','cancelled')) AS overdue_tasks
        FROM eng_task
    """, (_today(),)).fetchone()
    return {
        'projects':  dict(proj_row) if proj_row else {},
        'ecrs':      dict(ecr_row) if ecr_row else {},
        'tasks':     dict(task_row) if task_row else {},
    }


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def list_projects(conn, status=None, engineer=None, search=None):
    conds, params = [], []
    if status:
        conds.append('p.status = %s')
        params.append(status)
    if engineer:
        conds.append('p.engineer = %s')
        params.append(engineer)
    if search:
        conds.append('(p.title ILIKE %s OR p.project_number ILIKE %s)')
        params += [f'%{search}%', f'%{search}%']
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(f"""
        SELECT p.*,
               COUNT(t.id)                                                AS task_count,
               COUNT(t.id) FILTER (WHERE t.status='completed')           AS done_count,
               COUNT(t.id) FILTER (WHERE t.due_date < %s
                                   AND t.status NOT IN ('completed','cancelled')) AS overdue_tasks
        FROM eng_project p
        LEFT JOIN eng_task t ON t.project_id = p.id
        {where}
        GROUP BY p.id
        ORDER BY p.due_date ASC NULLS LAST, p.id DESC
    """, [_today()] + params).fetchall()


def get_project(conn, project_id):
    return conn.execute(
        "SELECT * FROM eng_project WHERE id = %s", (project_id,)
    ).fetchone()


def create_project(conn, project_number, title, product_id, engineer,
                   start_date, due_date, status, notes, created_by):
    if not title:
        raise ValueError('Project title is required')
    if not project_number:
        project_number = next_project_number(conn)
    if status not in PROJECT_STATUSES:
        status = 'planning'
    # eng_project predates created_by on some deployments (whichever CREATE
    # TABLE ran first won, and this module's own DDL is a no-op against an
    # already-existing table) -- self-heal since callers commit right after
    # calling this function.
    conn.execute(
        "ALTER TABLE eng_project ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    row = conn.execute(
        "INSERT INTO eng_project (project_number, title, product_id, engineer,"
        " start_date, due_date, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (project_number, title, product_id or None, engineer or '',
         start_date or _today(), due_date or None,
         status, notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_project(conn, project_id, title, product_id, engineer,
                   start_date, due_date, status, notes):
    if not title:
        raise ValueError('Project title is required')
    if status not in PROJECT_STATUSES:
        status = 'planning'
    conn.execute(
        "UPDATE eng_project SET title=%s, product_id=%s, engineer=%s,"
        " start_date=%s, due_date=%s, status=%s, notes=%s WHERE id=%s",
        (title, product_id or None, engineer or '',
         start_date or _today(), due_date or None,
         status, notes or '', project_id)
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def list_project_tasks(conn, project_id):
    return conn.execute("""
        SELECT * FROM eng_task
        WHERE project_id = %s
        ORDER BY
            CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                          WHEN 'medium' THEN 3 ELSE 4 END,
            due_date ASC NULLS LAST
    """, (project_id,)).fetchall()


def list_tasks(conn, status=None, priority=None, assigned_to=None):
    conds, params = [], []
    if status:
        conds.append('status = %s')
        params.append(status)
    if priority:
        conds.append('priority = %s')
        params.append(priority)
    if assigned_to:
        conds.append('assigned_to = %s')
        params.append(assigned_to)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(
        f"SELECT t.*, p.project_number, p.title AS project_title"
        f" FROM eng_task t"
        f" LEFT JOIN eng_project p ON p.id = t.project_id"
        f" {where}"
        f" ORDER BY t.due_date ASC NULLS LAST, t.id DESC",
        params or None
    ).fetchall()


def create_task(conn, project_id, task_name, assigned_to, due_date,
                priority, notes, created_by):
    if not task_name:
        raise ValueError('Task name is required')
    if priority not in PRIORITIES:
        priority = 'medium'
    # eng_task predates created_by on some deployments -- see create_project.
    conn.execute(
        "ALTER TABLE eng_task ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    row = conn.execute(
        "INSERT INTO eng_task (project_id, task_name, assigned_to, due_date,"
        " priority, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,'open',%s,%s) RETURNING id",
        (project_id or None, task_name, assigned_to or '',
         due_date or None, priority, notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_task(conn, task_id, task_name, assigned_to, due_date,
                priority, status, notes):
    if not task_name:
        raise ValueError('Task name is required')
    if priority not in PRIORITIES:
        priority = 'medium'
    if status not in TASK_STATUSES:
        status = 'open'
    conn.execute(
        "UPDATE eng_task SET task_name=%s, assigned_to=%s, due_date=%s,"
        " priority=%s, status=%s, notes=%s WHERE id=%s",
        (task_name, assigned_to or '', due_date or None,
         priority, status, notes or '', task_id)
    )


def get_task(conn, task_id):
    return conn.execute(
        "SELECT t.*, p.project_number, p.title AS project_title"
        " FROM eng_task t LEFT JOIN eng_project p ON p.id = t.project_id"
        " WHERE t.id = %s", (task_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Design Reviews / ECRs
# ---------------------------------------------------------------------------

def list_ecrs(conn, status=None, project_id=None, search=None):
    conds, params = [], []
    if status:
        conds.append('e.status = %s')
        params.append(status)
    if project_id:
        conds.append('e.project_id = %s')
        params.append(project_id)
    if search:
        conds.append('(e.title ILIKE %s OR e.ecr_number ILIKE %s)')
        params += [f'%{search}%', f'%{search}%']
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(f"""
        SELECT e.*, p.project_number, p.title AS project_title
        FROM eng_design_review e
        LEFT JOIN eng_project p ON p.id = e.project_id
        {where}
        ORDER BY e.review_date DESC NULLS LAST, e.id DESC
    """, params or None).fetchall()


def get_ecr(conn, ecr_id):
    return conn.execute("""
        SELECT e.*, p.project_number, p.title AS project_title
        FROM eng_design_review e
        LEFT JOIN eng_project p ON p.id = e.project_id
        WHERE e.id = %s
    """, (ecr_id,)).fetchone()


def create_ecr(conn, ecr_number, title, product_id, project_id,
               requested_by, review_date, notes, created_by):
    if not title:
        raise ValueError('ECR title is required')
    if not ecr_number:
        ecr_number = next_ecr_number(conn)
    # eng_design_review predates created_by on some deployments -- see
    # create_project.
    conn.execute(
        "ALTER TABLE eng_design_review ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    row = conn.execute(
        "INSERT INTO eng_design_review (ecr_number, title, product_id,"
        " project_id, requested_by, review_date, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,'draft',%s,%s) RETURNING id",
        (ecr_number, title, product_id or None, project_id or None,
         requested_by or '', review_date or _today(),
         notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_ecr(conn, ecr_id, title, product_id, project_id,
               requested_by, review_date, status, notes):
    if not title:
        raise ValueError('ECR title is required')
    if status not in ECR_STATUSES:
        status = 'draft'
    conn.execute(
        "UPDATE eng_design_review SET title=%s, product_id=%s, project_id=%s,"
        " requested_by=%s, review_date=%s, status=%s, notes=%s WHERE id=%s",
        (title, product_id or None, project_id or None,
         requested_by or '', review_date or _today(),
         status, notes or '', ecr_id)
    )


def set_ecr_status(conn, ecr_id, status):
    if status not in ECR_STATUSES:
        status = 'draft'
    conn.execute(
        "UPDATE eng_design_review SET status=%s WHERE id=%s", (status, ecr_id)
    )


# ---------------------------------------------------------------------------
# Engineering Reports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Standards & Compliance
# ---------------------------------------------------------------------------

ENG_STANDARD_STATUSES = ('Active', 'Under Review', 'Superseded', 'Withdrawn')
ENG_STANDARD_CATEGORIES = (
    'ISO', 'ANSI', 'ASME', 'IEEE', 'OSHA', 'Internal', 'Industry', 'Regulatory', 'Other',
)


def list_eng_standards(conn, status=None, category=None, search=None) -> list:
    sql = (
        "SELECT id, standard_number, title, category, version, "
        "status, review_date, created_by "
        "FROM eng_standard WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if category:
        sql += " AND category = %s"
        params.append(category)
    if search:
        sql += " AND (standard_number ILIKE %s OR title ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY category, standard_number"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_eng_standard(conn, spec_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM eng_standard WHERE id = %s", (spec_id,)
    ).fetchone()
    return dict(row) if row else None


def create_eng_standard(conn, standard_number: str, title: str,
                        category: str, version: str, status: str,
                        review_date: str, description: str, notes: str,
                        created_by: str) -> int:
    if not title.strip():
        raise ValueError("Title is required.")
    row = conn.execute(
        "INSERT INTO eng_standard "
        "(standard_number, title, category, version, status, "
        "review_date, description, notes, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE) RETURNING id",
        (standard_number, title.strip(), category, version,
         status or 'Active', review_date or None,
         description, notes, created_by),
    ).fetchone()
    return row['id']


def update_eng_standard(conn, spec_id: int, **fields) -> None:
    allowed = {
        'standard_number', 'title', 'category', 'version',
        'status', 'review_date', 'description', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE eng_standard SET {set_clause} WHERE id = %s",
        list(cols.values()) + [spec_id],
    )


def init_eng_standard_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_standard (
            id              SERIAL PRIMARY KEY,
            standard_number TEXT DEFAULT '',
            title           TEXT NOT NULL,
            category        TEXT DEFAULT '',
            version         TEXT DEFAULT '',
            status          TEXT DEFAULT 'Active',
            review_date     TEXT,
            description     TEXT DEFAULT '',
            notes           TEXT DEFAULT '',
            created_by      TEXT DEFAULT '',
            created_date    TEXT DEFAULT ''
        )
    """)


def eng_reports(conn):
    proj_by_status = conn.execute("""
        SELECT status, COUNT(*) AS cnt FROM eng_project GROUP BY status ORDER BY status
    """).fetchall()
    ecr_by_status = conn.execute("""
        SELECT status, COUNT(*) AS cnt FROM eng_design_review GROUP BY status ORDER BY status
    """).fetchall()
    overdue_projects = conn.execute("""
        SELECT * FROM eng_project
        WHERE due_date < %s AND status NOT IN ('completed','cancelled')
        ORDER BY due_date ASC
    """, (_today(),)).fetchall()
    open_tasks_by_priority = conn.execute("""
        SELECT priority, COUNT(*) AS cnt FROM eng_task
        WHERE status NOT IN ('completed','cancelled')
        GROUP BY priority
        ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                               WHEN 'medium' THEN 3 ELSE 4 END
    """).fetchall()
    recent_ecrs = conn.execute("""
        SELECT e.*, p.project_number FROM eng_design_review e
        LEFT JOIN eng_project p ON p.id = e.project_id
        ORDER BY e.id DESC LIMIT 10
    """).fetchall()
    return {
        'proj_by_status':        [dict(r) for r in proj_by_status],
        'ecr_by_status':         [dict(r) for r in ecr_by_status],
        'overdue_projects':      [dict(r) for r in overdue_projects],
        'open_tasks_by_priority':[dict(r) for r in open_tasks_by_priority],
        'recent_ecrs':           [dict(r) for r in recent_ecrs],
    }
