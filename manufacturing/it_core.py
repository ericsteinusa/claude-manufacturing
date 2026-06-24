"""Qt-free IT data layer — dashboard, tickets, assets."""

from datetime import date

TICKET_STATUSES = ('open', 'in_progress', 'resolved', 'closed')
TICKET_PRIORITIES = ('low', 'medium', 'high', 'critical')
ISSUE_TYPES = (
    'Hardware', 'Software', 'Network', 'Email', 'Phone',
    'Printer', 'Access / Permissions', 'Account', 'Other',
)
ASSET_STATUSES = ('active', 'spare', 'repair', 'retired', 'lost')
ASSET_TYPES = (
    'Desktop', 'Laptop', 'Monitor', 'Server', 'Printer',
    'Phone', 'Tablet', 'Switch', 'Router', 'UPS', 'Other',
)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_it_dashboard(conn) -> dict:
    """Return dict with keys: tickets, assets, recent_tickets.

    tickets: {open_count, in_progress_count, critical_count, total_count}
    assets:  {total, active, repair}
    recent_tickets: list of last 8 rows
                    (id, ticket_number, requester, department, issue_type,
                     priority, status, submitted_date)
    """
    t = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE status = 'open') AS open_count, "
        "COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_count, "
        "COUNT(*) FILTER (WHERE priority = 'critical' AND status NOT IN ('resolved','closed')) AS critical_count, "
        "COUNT(*) AS total_count "
        "FROM it_ticket"
    ).fetchone()
    tickets = dict(t) if t else {'open_count': 0, 'in_progress_count': 0,
                                  'critical_count': 0, 'total_count': 0}

    a = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'active') AS active, "
        "COUNT(*) FILTER (WHERE status = 'repair') AS repair "
        "FROM it_asset"
    ).fetchone()
    assets = dict(a) if a else {'total': 0, 'active': 0, 'repair': 0}

    rows = conn.execute(
        "SELECT id, ticket_number, requester, department, issue_type, "
        "priority, status, submitted_date "
        "FROM it_ticket "
        "ORDER BY submitted_date DESC, id DESC LIMIT 8"
    ).fetchall()

    return {
        'tickets': tickets,
        'assets': assets,
        'recent_tickets': [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Ticket helpers
# ---------------------------------------------------------------------------

def next_ticket_number(conn) -> str:
    yr = date.today().year
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTRING(ticket_number FROM 10) AS INTEGER)) "
        "FROM it_ticket WHERE ticket_number LIKE %s",
        (f"TKT-{yr}-%",),
    ).fetchone()
    last = (row[0] or 0) if row else 0
    return f"TKT-{yr}-{last + 1:04d}"


def list_tickets(conn, status=None, priority=None, search=None) -> list:
    sql = (
        "SELECT id, ticket_number, requester, department, issue_type, "
        "priority, status, submitted_date, due_date, assigned_to "
        "FROM it_ticket WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if priority:
        sql += " AND priority = %s"
        params.append(priority)
    if search:
        sql += " AND (ticket_number ILIKE %s OR requester ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY submitted_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_ticket(conn, ticket_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM it_ticket WHERE id = %s", (ticket_id,)
    ).fetchone()
    return dict(row) if row else None


def create_ticket(
    conn, ticket_number: str, requester: str, department: str,
    issue_type: str, description: str, priority: str,
    assigned_to: str, submitted_date: str, due_date: str,
    notes: str, created_by: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO it_ticket "
        "(ticket_number, requester, department, issue_type, description, "
        "priority, assigned_to, submitted_date, due_date, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (ticket_number, requester, department, issue_type, description,
         priority, assigned_to, submitted_date, due_date, notes, created_by),
    )
    return cur.fetchone()[0]


def update_ticket(conn, ticket_id: int, **fields) -> None:
    allowed = {
        'requester', 'department', 'issue_type', 'description', 'priority',
        'assigned_to', 'submitted_date', 'due_date', 'resolved_date',
        'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_ticket SET {set_clause} WHERE id = %s",
        list(cols.values()) + [ticket_id],
    )


def set_ticket_status(conn, ticket_id: int, status: str) -> None:
    resolved = date.today().isoformat() if status in ('resolved', 'closed') else None
    if resolved:
        conn.execute(
            "UPDATE it_ticket SET status = %s, resolved_date = %s WHERE id = %s",
            (status, resolved, ticket_id),
        )
    else:
        conn.execute(
            "UPDATE it_ticket SET status = %s WHERE id = %s",
            (status, ticket_id),
        )


# ---------------------------------------------------------------------------
# Asset helpers
# ---------------------------------------------------------------------------

def list_assets(conn, status=None, asset_type=None, search=None) -> list:
    sql = (
        "SELECT id, asset_tag, asset_type, make, model, serial_number, "
        "assigned_to, department, purchase_date, warranty_exp, status "
        "FROM it_asset WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if asset_type:
        sql += " AND asset_type = %s"
        params.append(asset_type)
    if search:
        sql += " AND (asset_tag ILIKE %s OR make ILIKE %s OR model ILIKE %s OR assigned_to ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY asset_tag"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_asset(conn, asset_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM it_asset WHERE id = %s", (asset_id,)
    ).fetchone()
    return dict(row) if row else None


def create_asset(
    conn, asset_tag: str, asset_type: str, make: str, model: str,
    serial_number: str, assigned_to: str, department: str,
    purchase_date: str, warranty_exp: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO it_asset "
        "(asset_tag, asset_type, make, model, serial_number, assigned_to, "
        "department, purchase_date, warranty_exp, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (asset_tag, asset_type, make, model, serial_number, assigned_to,
         department, purchase_date, warranty_exp, status, notes),
    )
    return cur.fetchone()[0]


def update_asset(conn, asset_id: int, **fields) -> None:
    allowed = {
        'asset_tag', 'asset_type', 'make', 'model', 'serial_number',
        'assigned_to', 'department', 'purchase_date', 'warranty_exp',
        'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_asset SET {set_clause} WHERE id = %s",
        list(cols.values()) + [asset_id],
    )
