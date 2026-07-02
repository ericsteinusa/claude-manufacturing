"""Qt-free personnel data layer.

Covers employee directory (people/dept/position tables) and time-off
requests. Every function takes an open connection; the caller controls
the transaction and lifetime (%s placeholders, psycopg2).
"""
from datetime import date

TIME_OFF_STATUSES = ('pending', 'approved', 'denied')
TIME_OFF_TYPES = ('Vacation', 'Sick', 'Personal', 'Bereavement', 'Other')

TIME_OFF_STATUS_COLORS = {
    'pending':  '#fff3cd',
    'approved': '#d4edda',
    'denied':   '#f8d7da',
}


# ---------------------------------------------------------------------------
# Employee directory
# ---------------------------------------------------------------------------

def list_people(conn, dept_id=None, search=None):
    """Return people rows with dept name, sub-dept name, and job title.

    Filters are optional; search matches first name, last name, or email
    (case-insensitive). Ordered by last name then first name.
    """
    sql = """
        SELECT p.id, p.first_name, p.last_name, p.employee_id, p.email,
               p.dept_id, d.dept_name, p.dept_sub_id, ds.dept_sub_name,
               pos.job_title
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN dept_sub ds ON ds.dept_sub_id = p.dept_sub_id
        LEFT JOIN position pos ON pos.people_id = p.id
    """
    conds, params = [], []
    if dept_id:
        conds.append("p.dept_id = %s")
        params.append(dept_id)
    if search:
        conds.append(
            "(p.first_name ILIKE %s OR p.last_name ILIKE %s OR p.email ILIKE %s)"
        )
        like = f'%{search}%'
        params += [like, like, like]
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY p.last_name, p.first_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_person(conn, person_id):
    """Return one person with dept, sub-dept, job title, and role, or None."""
    row = conn.execute("""
        SELECT p.id, p.first_name, p.last_name, p.employee_id, p.emp_id,
               p.address, p.city, p.state, p.zip_code, p.email,
               p.dept_id, d.dept_name, p.dept_sub_id, ds.dept_sub_name,
               pos.job_title, r.role_name, p.created_by
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN dept_sub ds ON ds.dept_sub_id = p.dept_sub_id
        LEFT JOIN position pos ON pos.people_id = p.id
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE p.id = %s
    """, (person_id,)).fetchone()
    return dict(row) if row else None


def get_person_by_email(conn, email):
    """Return {id} for the person with this email, or None."""
    row = conn.execute(
        "SELECT id FROM people WHERE email = %s", (email,)
    ).fetchone()
    return dict(row) if row else None


def create_person(conn, first_name, last_name, employee_id: int | None = 0, email='',
                  address='', city='', state='', zip_code='',
                  dept_id=None, dept_sub_id=None, job_title='',
                  created_by=None):
    """Insert a person and upsert their job title. Returns new id.
    Does not commit.
    """
    row = conn.execute(
        "INSERT INTO people (first_name, last_name, employee_id, email, "
        "address, city, state, zip_code, dept_id, dept_sub_id, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (first_name, last_name, employee_id or 0, email,
         address, city, state, zip_code, dept_id, dept_sub_id, created_by)
    ).fetchone()
    person_id = row['id']
    _upsert_position(conn, person_id, job_title or '')
    return person_id


def update_person(conn, person_id, first_name, last_name, employee_id: int | None = 0,
                  email='', address='', city='', state='', zip_code='',
                  dept_id=None, dept_sub_id=None, job_title=''):
    """Update a person's fields and upsert their job title. Does not commit."""
    conn.execute(
        "UPDATE people SET first_name=%s, last_name=%s, employee_id=%s, "
        "email=%s, address=%s, city=%s, state=%s, zip_code=%s, "
        "dept_id=%s, dept_sub_id=%s WHERE id=%s",
        (first_name, last_name, employee_id or 0, email,
         address, city, state, zip_code, dept_id, dept_sub_id, person_id)
    )
    _upsert_position(conn, person_id, job_title or '')


def _upsert_position(conn, person_id, job_title):
    conn.execute(
        "INSERT INTO position (people_id, job_title) VALUES (%s, %s) "
        "ON CONFLICT (people_id) DO UPDATE SET job_title = EXCLUDED.job_title",
        (person_id, job_title)
    )


def load_depts(conn):
    """Return [{dept_id, dept_name}] ordered by name."""
    rows = conn.execute(
        "SELECT dept_id, dept_name FROM dept ORDER BY dept_name"
    ).fetchall()
    return [dict(r) for r in rows]


def load_dept_subs(conn, dept_id=None):
    """Return [{dept_sub_id, dept_id, dept_sub_name}] optionally by dept."""
    if dept_id:
        rows = conn.execute(
            "SELECT dept_sub_id, dept_id, dept_sub_name FROM dept_sub "
            "WHERE dept_id = %s ORDER BY dept_sub_name", (dept_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT dept_sub_id, dept_id, dept_sub_name FROM dept_sub "
            "ORDER BY dept_sub_name"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Time-off requests
# ---------------------------------------------------------------------------

def list_time_off_requests(conn, people_id=None, status=None):
    """Return time-off request rows with person full name (newest first).

    Filter by people_id to scope to one employee's own requests.
    """
    sql = """
        SELECT t.id, t.people_id, t.request_date, t.start_date, t.end_date,
               t.request_type, t.status, t.notes, t.created_by,
               p.first_name, p.last_name
        FROM time_off_request t
        JOIN people p ON p.id = t.people_id
    """
    conds, params = [], []
    if people_id is not None:
        conds.append("t.people_id = %s")
        params.append(people_id)
    if status:
        conds.append("t.status = %s")
        params.append(status)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY t.id DESC"
    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['status_color'] = TIME_OFF_STATUS_COLORS.get(d['status'], '#ffffff')
        result.append(d)
    return result


def get_time_off_request(conn, req_id):
    """Return one time-off request with person name, or None."""
    row = conn.execute("""
        SELECT t.id, t.people_id, t.request_date, t.start_date, t.end_date,
               t.request_type, t.status, t.notes, t.created_by,
               p.first_name, p.last_name
        FROM time_off_request t
        JOIN people p ON p.id = t.people_id
        WHERE t.id = %s
    """, (req_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d['status_color'] = TIME_OFF_STATUS_COLORS.get(d['status'], '#ffffff')
    return d


def create_time_off_request(conn, people_id, start_date, end_date,
                             request_type='Vacation', notes=None,
                             created_by=None):
    """Insert a time-off request with status='pending'. Does not commit."""
    conn.execute(
        "INSERT INTO time_off_request "
        "(people_id, request_date, start_date, end_date, "
        "request_type, status, notes, created_by) "
        "VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)",
        (people_id, date.today().isoformat(), start_date, end_date,
         request_type, notes, created_by)
    )


def set_time_off_status(conn, req_id, status):
    """Update a request's status. Does not commit."""
    conn.execute(
        "UPDATE time_off_request SET status = %s WHERE id = %s",
        (status, req_id)
    )


# ---------------------------------------------------------------------------
# Department CRUD
# ---------------------------------------------------------------------------

def get_dept(conn, dept_id: int) -> dict | None:
    row = conn.execute(
        "SELECT dept_id, dept_name FROM dept WHERE dept_id = %s", (dept_id,)
    ).fetchone()
    return dict(row) if row else None


def create_dept(conn, dept_name: str) -> int:
    if not dept_name.strip():
        raise ValueError("Department name is required.")
    row = conn.execute(
        "INSERT INTO dept (dept_name) VALUES (%s) RETURNING dept_id",
        (dept_name.strip(),)
    ).fetchone()
    return row['dept_id']


def update_dept(conn, dept_id: int, dept_name: str) -> None:
    if not dept_name.strip():
        raise ValueError("Department name is required.")
    conn.execute(
        "UPDATE dept SET dept_name = %s WHERE dept_id = %s",
        (dept_name.strip(), dept_id)
    )


def get_dept_sub(conn, dept_sub_id: int) -> dict | None:
    row = conn.execute(
        "SELECT ds.dept_sub_id, ds.dept_id, ds.dept_sub_name, d.dept_name "
        "FROM dept_sub ds LEFT JOIN dept d ON d.dept_id = ds.dept_id "
        "WHERE ds.dept_sub_id = %s", (dept_sub_id,)
    ).fetchone()
    return dict(row) if row else None


def create_dept_sub(conn, dept_id: int, dept_sub_name: str) -> int:
    if not dept_sub_name.strip():
        raise ValueError("Sub-department name is required.")
    row = conn.execute(
        "INSERT INTO dept_sub (dept_id, dept_sub_name) VALUES (%s, %s) "
        "RETURNING dept_sub_id",
        (dept_id, dept_sub_name.strip())
    ).fetchone()
    return row['dept_sub_id']


def update_dept_sub(conn, dept_sub_id: int, dept_id: int, dept_sub_name: str) -> None:
    if not dept_sub_name.strip():
        raise ValueError("Sub-department name is required.")
    conn.execute(
        "UPDATE dept_sub SET dept_id = %s, dept_sub_name = %s WHERE dept_sub_id = %s",
        (dept_id, dept_sub_name.strip(), dept_sub_id)
    )


def list_dept_subs_with_dept(conn) -> list:
    rows = conn.execute(
        "SELECT ds.dept_sub_id, ds.dept_id, ds.dept_sub_name, d.dept_name "
        "FROM dept_sub ds LEFT JOIN dept d ON d.dept_id = ds.dept_id "
        "ORDER BY d.dept_name, ds.dept_sub_name"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Performance Reviews
# ---------------------------------------------------------------------------

REVIEW_STATUSES = ('Scheduled', 'In Progress', 'Completed', 'Cancelled')
REVIEW_TYPES = ('Annual', 'Mid-Year', 'Quarterly', '90-Day', 'Probation', 'Other')
REVIEW_RATINGS = (
    'Exceeds Expectations', 'Meets Expectations',
    'Below Expectations', 'Unsatisfactory',
)


def list_reviews(conn, people_id=None, status=None, search=None) -> list:
    sql = (
        "SELECT r.id, r.people_id, r.review_type, r.review_date, "
        "r.reviewer, r.rating, r.status, r.created_by, "
        "p.first_name, p.last_name "
        "FROM pers_review r "
        "JOIN people p ON p.id = r.people_id "
        "WHERE TRUE"
    )
    params: list = []
    if people_id:
        sql += " AND r.people_id = %s"
        params.append(people_id)
    if status:
        sql += " AND r.status = %s"
        params.append(status)
    if search:
        sql += " AND (p.first_name ILIKE %s OR p.last_name ILIKE %s OR r.reviewer ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY r.review_date DESC NULLS LAST, r.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_review(conn, review_id: int) -> dict | None:
    row = conn.execute(
        "SELECT r.*, p.first_name, p.last_name "
        "FROM pers_review r JOIN people p ON p.id = r.people_id "
        "WHERE r.id = %s", (review_id,)
    ).fetchone()
    return dict(row) if row else None


def create_review(conn, people_id: int, review_type: str, review_date: str,
                  reviewer: str, rating: str, status: str,
                  notes: str, created_by: str) -> int:
    if not people_id:
        raise ValueError("Employee is required.")
    row = conn.execute(
        "INSERT INTO pers_review "
        "(people_id, review_type, review_date, reviewer, rating, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (people_id, review_type or 'Annual', review_date or None,
         reviewer or '', rating or '', status or 'Scheduled',
         notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_review(conn, review_id: int, **fields) -> None:
    allowed = {'review_type', 'review_date', 'reviewer', 'rating', 'status', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE pers_review SET {set_clause} WHERE id = %s",
        list(cols.values()) + [review_id],
    )


def init_review_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pers_review (
            id          SERIAL PRIMARY KEY,
            people_id   INTEGER NOT NULL REFERENCES people(id),
            review_type TEXT DEFAULT 'Annual',
            review_date TEXT,
            reviewer    TEXT DEFAULT '',
            rating      TEXT DEFAULT '',
            status      TEXT DEFAULT 'Scheduled',
            notes       TEXT DEFAULT '',
            created_by  TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Training Records
# ---------------------------------------------------------------------------

TRAINING_STATUSES = ('Scheduled', 'In Progress', 'Completed', 'Cancelled')
TRAINING_TYPES = ('Safety', 'Technical', 'Compliance', 'Leadership', 'Software', 'Certification', 'Other')


def list_trainings(conn, people_id=None, status=None, training_type=None,
                   search=None) -> list:
    sql = (
        "SELECT t.id, t.people_id, t.course_name, t.training_type, "
        "t.start_date, t.end_date, t.status, t.created_by, "
        "p.first_name, p.last_name "
        "FROM pers_training t "
        "JOIN people p ON p.id = t.people_id "
        "WHERE TRUE"
    )
    params: list = []
    if people_id:
        sql += " AND t.people_id = %s"
        params.append(people_id)
    if status:
        sql += " AND t.status = %s"
        params.append(status)
    if training_type:
        sql += " AND t.training_type = %s"
        params.append(training_type)
    if search:
        sql += " AND (t.course_name ILIKE %s OR p.first_name ILIKE %s OR p.last_name ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY t.start_date DESC NULLS LAST, t.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_training(conn, training_id: int) -> dict | None:
    row = conn.execute(
        "SELECT t.*, p.first_name, p.last_name "
        "FROM pers_training t JOIN people p ON p.id = t.people_id "
        "WHERE t.id = %s", (training_id,)
    ).fetchone()
    return dict(row) if row else None


def create_training(conn, people_id: int, course_name: str,
                    training_type: str, start_date: str, end_date: str,
                    status: str, notes: str, created_by: str) -> int:
    if not people_id:
        raise ValueError("Employee is required.")
    if not course_name.strip():
        raise ValueError("Course name is required.")
    row = conn.execute(
        "INSERT INTO pers_training "
        "(people_id, course_name, training_type, start_date, end_date, "
        "status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (people_id, course_name.strip(), training_type or 'Other',
         start_date or None, end_date or None,
         status or 'Scheduled', notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_training(conn, training_id: int, **fields) -> None:
    allowed = {'course_name', 'training_type', 'start_date', 'end_date', 'status', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE pers_training SET {set_clause} WHERE id = %s",
        list(cols.values()) + [training_id],
    )


def init_training_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pers_training (
            id            SERIAL PRIMARY KEY,
            people_id     INTEGER NOT NULL REFERENCES people(id),
            course_name   TEXT NOT NULL,
            training_type TEXT DEFAULT 'Other',
            start_date    TEXT,
            end_date      TEXT,
            status        TEXT DEFAULT 'Scheduled',
            notes         TEXT DEFAULT '',
            created_by    TEXT DEFAULT ''
        )
    """)


def get_personnel_dashboard(conn) -> dict:
    """Return dict with keys: employees, by_dept, time_off, recent_employees.

    employees:        {total}
    by_dept:          list of {dept_name, count} top-6 by headcount
    time_off:         {pending, approved}
    recent_employees: list of last 8 people rows
                      (id, first_name, last_name, email, dept_name, job_title)
    """
    emp_row = conn.execute(
        "SELECT COUNT(*) AS total FROM people"
    ).fetchone()

    dept_rows = conn.execute(
        "SELECT d.dept_name, COUNT(p.id) AS count "
        "FROM dept d "
        "LEFT JOIN people p ON p.dept_id = d.dept_id "
        "GROUP BY d.dept_id, d.dept_name "
        "ORDER BY count DESC LIMIT 6"
    ).fetchall()

    to_row = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE status = 'pending') AS pending, "
        "COUNT(*) FILTER (WHERE status = 'approved') AS approved "
        "FROM time_off_request"
    ).fetchone()

    recent_rows = conn.execute(
        "SELECT p.id, p.first_name, p.last_name, p.email, "
        "COALESCE(d.dept_name, '') AS dept_name, "
        "COALESCE(pos.job_title, '') AS job_title "
        "FROM people p "
        "LEFT JOIN dept d ON d.dept_id = p.dept_id "
        "LEFT JOIN position pos ON pos.people_id = p.id "
        "ORDER BY p.id DESC LIMIT 8"
    ).fetchall()

    return {
        'employees': dict(emp_row) if emp_row else {},
        'by_dept': [dict(r) for r in dept_rows],
        'time_off': dict(to_row) if to_row else {},
        'recent_employees': [dict(r) for r in recent_rows],
    }
