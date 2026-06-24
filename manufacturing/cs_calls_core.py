"""Qt-free helpers for the Customer Service Calls screen.

Kept import-safe for CI (no PyQt6, no DB at import time) so the pure logic
— customer-label formatting, id parsing and record validation — can be
unit-tested. The GUI (cs_calls_widget.py) imports from here.

The lower half of this module adds the DB-level functions used by the
web views (cs_ticket_list, cs_ticket_detail, etc.).  They follow the same
"no-commit" contract as the other *_core.py modules.
"""

import datetime

# Editable columns of the calls2 table, in the order the form collects them.
CALL_COLUMNS = ("customer_id", "call", "call_date", "call_time",
                "completion_date", "completion_time", "comments_box",
                "completion_box")

OVERDUE_DAYS = 7      # open tickets older than this are escalations
CRITICAL_DAYS = 14    # escalations older than this are critical


def format_customer_label(
    customer_id, first_name: str | None = "", last_name: str | None = ""
) -> str:
    """Combobox label like ``"7 - Jane Doe"`` (id alone when no name)."""
    parts = [p for p in (first_name or "", last_name or "") if p]
    name = " ".join(parts).strip()
    return f"{customer_id} - {name}" if name else str(customer_id)


def parse_customer_id(label):
    """Extract the leading integer id from a customer label or raw value.

    Tolerates ``"7 - Jane Doe"``, ``"7"``, ``"{7} ..."`` and plain ints;
    returns ``None`` when no id can be read.
    """
    if label is None:
        return None
    if isinstance(label, int):
        return label
    token = str(label).strip().split(" ", 1)[0].strip("{}")
    try:
        return int(token)
    except (TypeError, ValueError):
        return None


def validate_call(customer_id, call) -> list:
    """Return a list of human-readable errors for a new/updated call.

    A call needs a customer and a problem description; completion details
    are optional (an open call has none yet).
    """
    errors = []
    if parse_customer_id(customer_id) is None:
        errors.append("Please select a customer.")
    if not (call or "").strip():
        errors.append("Please enter the call / problem description.")
    return errors


# ---------------------------------------------------------------------------
# DB helpers — used by web views (no PyQt6 import, no commit inside)
# ---------------------------------------------------------------------------

def _ticket_row(row: dict) -> dict:
    """Annotate a raw calls2 row with derived fields."""
    today = datetime.date.today()
    try:
        opened = datetime.date.fromisoformat(row.get('call_date') or '')
        row['days_open'] = (today - opened).days
    except ValueError:
        row['days_open'] = 0
    completed = row.get('completion_box') or 0
    if completed:
        row['status'] = 'completed'
        row['priority'] = 'none'
    elif row['days_open'] >= CRITICAL_DAYS:
        row['status'] = 'open'
        row['priority'] = 'critical'
    elif row['days_open'] >= OVERDUE_DAYS:
        row['status'] = 'open'
        row['priority'] = 'high'
    else:
        row['status'] = 'open'
        row['priority'] = 'normal'
    return row


def load_customers_for_cs(conn) -> list[dict]:
    """[{id, label}] for the customer dropdown on ticket forms."""
    rows = conn.execute(
        "SELECT id, first_name, last_name, company_name "
        "FROM customer "
        "ORDER BY LOWER(COALESCE(NULLIF(company_name,''), last_name, first_name))"
    ).fetchall()
    result = []
    for r in rows:
        r = dict(r)
        company = (r.get('company_name') or '').strip()
        first = (r.get('first_name') or '').strip()
        last = (r.get('last_name') or '').strip()
        name = f"{first} {last}".strip()
        label = company if company else (name if name else str(r['id']))
        result.append({'id': r['id'], 'label': label})
    return result


def list_tickets(conn, search: str | None = None,
                 status: str | None = None,
                 created_by: str | None = None) -> list[dict]:
    """Return annotated ticket rows, newest first.

    status: 'open' | 'completed' | None (all)
    created_by: filter to one user's tickets when set
    """
    conditions = []
    params: list = []

    if status == 'open':
        conditions.append("t.completion_box = 0")
    elif status == 'completed':
        conditions.append("t.completion_box = 1")

    if created_by:
        conditions.append("t.created_by = %s")
        params.append(created_by)

    if search:
        conditions.append(
            "(c.first_name ILIKE %s OR c.last_name ILIKE %s "
            "OR c.company_name ILIKE %s OR t.call ILIKE %s)"
        )
        params += [f'%{search}%'] * 4

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT t.id, t.customer_id, t.call, t.call_date, t.call_time, "
        f"t.completion_date, t.completion_time, t.comments_box, "
        f"t.completion_box, t.created_by, "
        f"COALESCE(NULLIF(c.company_name,''), "
        f"  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), "
        f"  c.first_name, 'Unknown') AS customer_name "
        f"FROM calls2 t "
        f"LEFT JOIN customer c ON c.id = t.customer_id "
        f"{where} "
        f"ORDER BY t.call_date DESC, t.id DESC",
        params,
    ).fetchall()
    return [_ticket_row(dict(r)) for r in rows]


def get_ticket(conn, ticket_id: int) -> dict | None:
    row = conn.execute(
        "SELECT t.*, "
        "COALESCE(NULLIF(c.company_name,''), "
        "  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), "
        "  c.first_name, 'Unknown') AS customer_name "
        "FROM calls2 t "
        "LEFT JOIN customer c ON c.id = t.customer_id "
        "WHERE t.id = %s",
        (ticket_id,),
    ).fetchone()
    if not row:
        return None
    return _ticket_row(dict(row))


def create_ticket(conn, customer_id: int, call: str, call_date: str,
                  call_time: str, comments: str, created_by: str) -> int:
    """Insert a new open ticket. Does not commit."""
    row = conn.execute(
        "INSERT INTO calls2 "
        "(customer_id, call, call_date, call_time, "
        "completion_date, completion_time, comments_box, completion_box, created_by) "
        "VALUES (%s,%s,%s,%s,'','',  %s, 0, %s) RETURNING id",
        (customer_id, call.strip(), call_date, call_time,
         comments.strip(), created_by),
    ).fetchone()
    return row['id']


def update_ticket(conn, ticket_id: int, customer_id: int, call: str,
                  call_date: str, call_time: str, completion_date: str,
                  completion_time: str, comments: str, completed: bool) -> None:
    """Update all editable fields. Does not commit."""
    conn.execute(
        "UPDATE calls2 SET customer_id=%s, call=%s, call_date=%s, call_time=%s, "
        "completion_date=%s, completion_time=%s, comments_box=%s, completion_box=%s "
        "WHERE id=%s",
        (customer_id, call.strip(), call_date, call_time,
         completion_date, completion_time, comments.strip(),
         1 if completed else 0, ticket_id),
    )


def close_ticket(conn, ticket_id: int, comments: str) -> None:
    """Mark a ticket completed with today's date/time. Does not commit."""
    now = datetime.datetime.now()
    conn.execute(
        "UPDATE calls2 SET completion_box=1, "
        "completion_date=%s, completion_time=%s, comments_box=%s "
        "WHERE id=%s",
        (now.date().isoformat(), now.strftime('%H:%M'),
         comments.strip(), ticket_id),
    )


def get_escalations(conn) -> list[dict]:
    """Open tickets that have been open >= OVERDUE_DAYS days."""
    today = datetime.date.today()
    cutoff = (today - datetime.timedelta(days=OVERDUE_DAYS)).isoformat()
    rows = conn.execute(
        "SELECT t.id, t.customer_id, t.call, t.call_date, t.call_time, "
        "t.comments_box, t.completion_box, t.created_by, "
        "COALESCE(NULLIF(c.company_name,''), "
        "  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), "
        "  c.first_name, 'Unknown') AS customer_name "
        "FROM calls2 t "
        "LEFT JOIN customer c ON c.id = t.customer_id "
        "WHERE t.completion_box = 0 AND t.call_date <= %s "
        "ORDER BY t.call_date ASC",
        (cutoff,),
    ).fetchall()
    result = []
    for r in rows:
        d = _ticket_row(dict(r))
        d['completion_date'] = ''
        d['completion_time'] = ''
        result.append(d)
    return result


def get_summary_stats(conn, days: int = 365) -> dict:
    """Aggregate KPIs over the last *days* days."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    row = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN completion_box=0 THEN 1 ELSE 0 END) AS open_count, "
        "SUM(CASE WHEN completion_box=1 THEN 1 ELSE 0 END) AS completed_count, "
        "AVG(CASE WHEN completion_box=1 AND completion_date>'' THEN "
        "  (completion_date::date - call_date::date) END) AS avg_resolution "
        "FROM calls2 WHERE call_date >= %s",
        (since,),
    ).fetchone()
    if not row:
        return {'total': 0, 'open_count': 0, 'completed_count': 0,
                'completion_rate': 0.0, 'avg_resolution': None,
                'avg_age_open': None}
    d = dict(row)
    d['completion_rate'] = (
        round(d['completed_count'] / d['total'] * 100, 1)
        if d['total'] else 0.0
    )
    # Average age of still-open tickets
    age_row = conn.execute(
        "SELECT AVG(CURRENT_DATE - call_date::date) AS avg_age "
        "FROM calls2 WHERE completion_box=0 AND call_date >= %s",
        (since,),
    ).fetchone()
    d['avg_age_open'] = round(float(age_row['avg_age']), 1) if (
        age_row and age_row['avg_age'] is not None) else None
    if d['avg_resolution'] is not None:
        d['avg_resolution'] = round(float(d['avg_resolution']), 1)
    return d


def get_monthly_volume(conn, days: int = 365) -> list[dict]:
    """Per-month call volume for the report tab."""
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT TO_CHAR(call_date::date, 'YYYY-MM') AS month, "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN completion_box=0 THEN 1 ELSE 0 END) AS open_count, "
        "SUM(CASE WHEN completion_box=1 THEN 1 ELSE 0 END) AS completed_count "
        "FROM calls2 WHERE call_date >= %s "
        "GROUP BY month ORDER BY month DESC",
        (since,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['completion_rate'] = (
            round(d['completed_count'] / d['total'] * 100, 1)
            if d['total'] else 0.0
        )
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Improvement plans
# ---------------------------------------------------------------------------

PLAN_STATUSES = ('Open', 'In Progress', 'Completed', 'Cancelled')


def list_plans(conn, status: str | None = None) -> list[dict]:
    where = "WHERE status = %s" if status else ""
    params = [status] if status else []
    rows = conn.execute(
        f"SELECT * FROM cs_improvement_plan {where} "
        f"ORDER BY created_date DESC",
        params,
    ).fetchall()
    today = datetime.date.today().isoformat()
    result = []
    for r in rows:
        d = dict(r)
        d['overdue'] = (
            d.get('status') not in ('Completed', 'Cancelled')
            and (d.get('target_date') or '') < today
        )
        result.append(d)
    return result


def create_plan(conn, title: str, description: str, owner: str,
                target_date: str, created_by: str) -> int:
    """Does not commit."""
    if not title.strip():
        raise ValueError("Title is required.")
    row = conn.execute(
        "INSERT INTO cs_improvement_plan "
        "(title, description, owner, target_date, status, created_date, created_by) "
        "VALUES (%s,%s,%s,%s,'Open',%s,%s) RETURNING id",
        (title.strip(), description.strip(), owner.strip(),
         target_date, datetime.date.today().isoformat(), created_by),
    ).fetchone()
    return row['id']


def update_plan(conn, plan_id: int, title: str, description: str,
                owner: str, target_date: str, status: str) -> None:
    """Does not commit."""
    if not title.strip():
        raise ValueError("Title is required.")
    if status not in PLAN_STATUSES:
        status = 'Open'
    conn.execute(
        "UPDATE cs_improvement_plan SET title=%s, description=%s, owner=%s, "
        "target_date=%s, status=%s WHERE id=%s",
        (title.strip(), description.strip(), owner.strip(),
         target_date, status, plan_id),
    )


# ---------------------------------------------------------------------------
# Returns & Refunds
# ---------------------------------------------------------------------------

RETURN_STATUSES = ('Pending', 'Approved', 'Refunded', 'Rejected', 'Closed')
RETURN_REASONS = (
    'Defective', 'Wrong Item', 'Changed Mind', 'Damaged in Shipping',
    'Not as Described', 'Duplicate Order', 'Other',
)


def list_returns(conn, status=None, search=None) -> list:
    sql = (
        "SELECT r.id, r.return_date, r.reason, r.refund_amount, r.status, "
        "r.created_by, r.notes, "
        "COALESCE(NULLIF(c.company_name,''), "
        "  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), "
        "  c.first_name, 'Unknown') AS customer_name "
        "FROM cs_return r "
        "LEFT JOIN customer c ON c.id = r.customer_id "
        "WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND r.status = %s"
        params.append(status)
    if search:
        sql += (" AND (c.first_name ILIKE %s OR c.last_name ILIKE %s "
                "OR c.company_name ILIKE %s OR r.reason ILIKE %s "
                "OR r.notes ILIKE %s)")
        params.extend([f"%{search}%"] * 5)
    sql += " ORDER BY r.return_date DESC NULLS LAST, r.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_return(conn, return_id: int) -> dict | None:
    row = conn.execute(
        "SELECT r.*, "
        "COALESCE(NULLIF(c.company_name,''), "
        "  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), "
        "  c.first_name, 'Unknown') AS customer_name "
        "FROM cs_return r "
        "LEFT JOIN customer c ON c.id = r.customer_id "
        "WHERE r.id = %s",
        (return_id,),
    ).fetchone()
    return dict(row) if row else None


def create_return(conn, customer_id, return_date: str, reason: str,
                  items_returned: str, refund_amount: float,
                  status: str, notes: str, created_by: str) -> int:
    row = conn.execute(
        "INSERT INTO cs_return "
        "(customer_id, return_date, reason, items_returned, refund_amount, "
        "status, notes, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE) RETURNING id",
        (customer_id or None, return_date or None, reason,
         items_returned, refund_amount or 0,
         status or 'Pending', notes, created_by),
    ).fetchone()
    return row['id']


def update_return(conn, return_id: int, **fields) -> None:
    allowed = {
        'customer_id', 'return_date', 'reason', 'items_returned',
        'refund_amount', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE cs_return SET {set_clause} WHERE id = %s",
        list(cols.values()) + [return_id],
    )


def init_return_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_return (
            id             SERIAL PRIMARY KEY,
            customer_id    INTEGER REFERENCES customer(id),
            return_date    TEXT,
            reason         TEXT DEFAULT '',
            items_returned TEXT DEFAULT '',
            refund_amount  REAL DEFAULT 0,
            status         TEXT DEFAULT 'Pending',
            notes          TEXT DEFAULT '',
            created_by     TEXT DEFAULT '',
            created_date   TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

KB_STATUSES = ('Draft', 'Published', 'Archived')
KB_CATEGORIES = (
    'Product', 'Shipping', 'Returns', 'Account', 'Billing',
    'Technical', 'Policy', 'FAQ', 'Other',
)


def list_kb_articles(conn, status=None, category=None, search=None) -> list:
    sql = (
        "SELECT id, title, category, author, published_date, "
        "status, view_count, tags "
        "FROM cs_kb_article WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if category:
        sql += " AND category = %s"
        params.append(category)
    if search:
        sql += " AND (title ILIKE %s OR content ILIKE %s OR tags ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY published_date DESC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_kb_article(conn, article_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM cs_kb_article WHERE id = %s", (article_id,)
    ).fetchone()
    return dict(row) if row else None


def create_kb_article(conn, title: str, category: str, content: str,
                      author: str, published_date: str, status: str,
                      tags: str, created_by: str) -> int:
    row = conn.execute(
        "INSERT INTO cs_kb_article "
        "(title, category, content, author, published_date, status, "
        "tags, view_count, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s,CURRENT_DATE) RETURNING id",
        (title, category, content, author,
         published_date or None, status or 'Draft', tags, created_by),
    ).fetchone()
    return row['id']


def update_kb_article(conn, article_id: int, **fields) -> None:
    allowed = {
        'title', 'category', 'content', 'author',
        'published_date', 'status', 'tags',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE cs_kb_article SET {set_clause} WHERE id = %s",
        list(cols.values()) + [article_id],
    )


def init_kb_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_kb_article (
            id             SERIAL PRIMARY KEY,
            title          TEXT NOT NULL,
            category       TEXT DEFAULT '',
            content        TEXT DEFAULT '',
            author         TEXT DEFAULT '',
            published_date TEXT,
            status         TEXT DEFAULT 'Draft',
            tags           TEXT DEFAULT '',
            view_count     INTEGER DEFAULT 0,
            created_by     TEXT DEFAULT '',
            created_date   TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Surveys & Feedback
# ---------------------------------------------------------------------------

SURVEY_TYPES = ('CSAT', 'NPS', 'Post-Purchase', 'Product', 'Support', 'Other')
SURVEY_STATUSES = ('Draft', 'Active', 'Closed')


def list_surveys(conn, status=None, survey_type=None, search=None) -> list:
    sql = (
        "SELECT id, title, survey_type, status, start_date, end_date, "
        "response_count, avg_score, created_by "
        "FROM cs_survey WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if survey_type:
        sql += " AND survey_type = %s"
        params.append(survey_type)
    if search:
        sql += " AND (title ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{search}%"] * 2)
    sql += " ORDER BY created_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_survey(conn, survey_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM cs_survey WHERE id = %s", (survey_id,)
    ).fetchone()
    return dict(row) if row else None


def get_survey_responses(conn, survey_id: int) -> list:
    rows = conn.execute(
        "SELECT r.*, "
        "COALESCE(NULLIF(c.company_name,''), "
        "  TRIM(COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')), "
        "  c.first_name, NULL) AS customer_name "
        "FROM cs_survey_response r "
        "LEFT JOIN customer c ON c.id = r.customer_id "
        "WHERE r.survey_id = %s ORDER BY r.response_date DESC, r.id DESC",
        (survey_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_survey(conn, title: str, description: str, survey_type: str,
                  status: str, start_date: str, end_date: str,
                  created_by: str) -> int:
    row = conn.execute(
        "INSERT INTO cs_survey "
        "(title, description, survey_type, status, start_date, end_date, "
        "response_count, avg_score, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,0,NULL,%s,CURRENT_DATE) RETURNING id",
        (title, description, survey_type or 'CSAT', status or 'Draft',
         start_date or None, end_date or None, created_by),
    ).fetchone()
    return row['id']


def update_survey(conn, survey_id: int, **fields) -> None:
    allowed = {
        'title', 'description', 'survey_type', 'status',
        'start_date', 'end_date',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE cs_survey SET {set_clause} WHERE id = %s",
        list(cols.values()) + [survey_id],
    )


def add_survey_response(conn, survey_id: int, customer_id,
                        score: int, comments: str,
                        response_date: str) -> None:
    conn.execute(
        "INSERT INTO cs_survey_response "
        "(survey_id, customer_id, score, comments, response_date) "
        "VALUES (%s,%s,%s,%s,%s)",
        (survey_id, customer_id or None, score,
         comments, response_date or None),
    )
    conn.execute(
        "UPDATE cs_survey SET "
        "response_count = (SELECT COUNT(*) FROM cs_survey_response WHERE survey_id = %s), "
        "avg_score = (SELECT ROUND(AVG(score)::numeric, 1) FROM cs_survey_response WHERE survey_id = %s) "
        "WHERE id = %s",
        (survey_id, survey_id, survey_id),
    )


def init_survey_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_survey (
            id             SERIAL PRIMARY KEY,
            title          TEXT NOT NULL,
            description    TEXT DEFAULT '',
            survey_type    TEXT DEFAULT 'CSAT',
            status         TEXT DEFAULT 'Draft',
            start_date     TEXT,
            end_date       TEXT,
            response_count INTEGER DEFAULT 0,
            avg_score      REAL,
            created_by     TEXT DEFAULT '',
            created_date   TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_survey_response (
            id            SERIAL PRIMARY KEY,
            survey_id     INTEGER NOT NULL REFERENCES cs_survey(id) ON DELETE CASCADE,
            customer_id   INTEGER REFERENCES customer(id),
            score         INTEGER,
            comments      TEXT DEFAULT '',
            response_date TEXT
        )
    """)
