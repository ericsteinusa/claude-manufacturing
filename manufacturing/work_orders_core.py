"""Qt-free work-order data layer.

Kept separate from work_orders.py (which imports PyQt6) so the SQL can be
imported by Django web views and unit-tested without the Qt shared libraries.
Every function takes an open connection; the caller controls the transaction
and lifetime (pass a db_pg.get_db_connection() connection, %s placeholders).
"""
from datetime import date

import psycopg2

from .mrp_core import next_sequence_number

WO_STATUSES = ("draft", "open", "in_progress", "completed", "cancelled")

WO_STATUS_COLORS = {
    "draft":       "#ffffff",
    "open":        "#cce5ff",
    "in_progress": "#fff3cd",
    "completed":   "#d4edda",
    "cancelled":   "#dcdcdc",
}

WO_STATUS_TRANSITIONS = {
    "draft":       ("open", "cancelled"),
    "open":        ("in_progress", "cancelled"),
    "in_progress": ("completed", "cancelled"),
    "completed":   (),
    "cancelled":   (),
}

WO_STATUS_ACTION_LABELS = {
    "open":        "Open",
    "in_progress": "Start",
    "completed":   "Complete",
    "cancelled":   "Cancel WO",
}


def allowed_transitions(current):
    """Statuses ``current`` may move to (empty tuple for unknown/terminal)."""
    return WO_STATUS_TRANSITIONS.get(current, ())


def can_transition(current, target):
    """True if a WO in ``current`` status may move to ``target``."""
    return target in WO_STATUS_TRANSITIONS.get(current, ())


def ensure_wo_tables(conn):
    """Create work_order / wo_material tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_order (
            id SERIAL PRIMARY KEY,
            wo_number TEXT NOT NULL UNIQUE,
            product_id INTEGER,
            description TEXT,
            quantity INTEGER DEFAULT 1,
            start_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute("""
        ALTER TABLE work_order
        ADD COLUMN IF NOT EXISTS created_by TEXT
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_material (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL REFERENCES work_order(id),
            product_id INTEGER,
            qty_required INTEGER DEFAULT 1,
            qty_issued INTEGER DEFAULT 0,
            notes TEXT
        )
    """)


def next_wo_number(conn, today=None):
    """Return the next WO-<year>-NNNN on conn's transaction.

    Uses max-suffix+1 (gap-safe), generated on the caller's own connection —
    so creating several WOs in one uncommitted transaction yields distinct
    numbers, unlike a COUNT(*) on a fresh connection.
    """
    year = (today or date.today()).year
    prefix = f"WO-{year}-"
    rows = conn.execute(
        "SELECT wo_number FROM work_order WHERE wo_number LIKE %s",
        (prefix + "%",)
    ).fetchall()
    return next_sequence_number([r["wo_number"] for r in rows], prefix)


def list_wos(conn, status=None, date_from=None, date_to=None):
    """Return WO rows (earliest due-date first) with product name and material
    count. All filters are optional; ``date_from`` / ``date_to`` bound
    ``due_date`` inclusively (NULL due-dates are always included).
    """
    sql = """
        SELECT wo.id, wo.wo_number, wo.description, wo.quantity,
               wo.start_date, wo.due_date, wo.status, wo.notes,
               wo.created_by, p.name AS product_name,
               (SELECT COUNT(*) FROM wo_material m WHERE m.wo_id = wo.id)
                   AS mat_count
        FROM work_order wo
        LEFT JOIN product p ON p.id = wo.product_id
    """
    conds, params = [], []
    if status:
        conds.append("wo.status = %s")
        params.append(status)
    if date_from is not None:
        conds.append("(wo.due_date IS NULL OR wo.due_date >= %s)")
        params.append(date_from)
    if date_to is not None:
        conds.append("(wo.due_date IS NULL OR wo.due_date <= %s)")
        params.append(date_to)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY wo.due_date ASC NULLS LAST, wo.id ASC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_wo(conn, wo_id):
    """Return one WO dict (with product name and material count), or None."""
    row = conn.execute("""
        SELECT wo.id, wo.wo_number, wo.description, wo.quantity,
               wo.start_date, wo.due_date, wo.status, wo.notes,
               wo.created_by, p.name AS product_name,
               (SELECT COUNT(*) FROM wo_material m WHERE m.wo_id = wo.id)
                   AS mat_count
        FROM work_order wo
        LEFT JOIN product p ON p.id = wo.product_id
        WHERE wo.id = %s
    """, (wo_id,)).fetchone()
    return dict(row) if row else None


def get_wo_materials(conn, wo_id):
    """Return material rows for a WO, each with product name."""
    rows = conn.execute("""
        SELECT m.id, m.product_id, p.name AS product_name,
               m.qty_required, m.qty_issued, m.notes
        FROM wo_material m
        LEFT JOIN product p ON p.id = m.product_id
        WHERE m.wo_id = %s
        ORDER BY m.id
    """, (wo_id,)).fetchall()
    return [dict(r) for r in rows]


def load_products(conn):
    """Return [{id, product_name}] for the product picker (empty on error)."""
    try:
        rows = conn.execute(
            "SELECT id, name AS product_name FROM product ORDER BY name"
        ).fetchall()
    except psycopg2.Error:
        return []
    return [dict(r) for r in rows]


def create_wo(conn, wo_number, product_id=None, description=None,
              quantity=1, start_date=None, due_date=None,
              status="draft", notes=None, created_by=None):
    """Insert a WO and return its new id. Does not commit.

    Raises psycopg2.IntegrityError if wo_number already exists.
    """
    row = conn.execute(
        "INSERT INTO work_order (wo_number, product_id, description,"
        " quantity, start_date, due_date, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (wo_number, product_id, description, quantity, start_date,
         due_date, status, notes, created_by)
    ).fetchone()
    return row["id"]


def update_wo(conn, wo_id, product_id=None, description=None,
              quantity=1, start_date=None, due_date=None, notes=None):
    """Update editable WO fields. Does not commit.

    wo_number and status are intentionally excluded — status changes go
    through set_wo_status.
    """
    conn.execute(
        "UPDATE work_order SET product_id=%s, description=%s, quantity=%s,"
        " start_date=%s, due_date=%s, notes=%s WHERE id=%s",
        (product_id, description, quantity, start_date, due_date,
         notes, wo_id)
    )


def add_wo_material(conn, wo_id, product_id, qty_required=1,
                    qty_issued=0, notes=None):
    """Append a material line to a WO. Does not commit."""
    conn.execute(
        "INSERT INTO wo_material (wo_id, product_id, qty_required,"
        " qty_issued, notes) VALUES (%s,%s,%s,%s,%s)",
        (wo_id, product_id, qty_required, qty_issued, notes)
    )


def set_wo_status(conn, wo_id, new_status):
    """Set a WO's status. Does not commit and does not check the transition —
    callers should gate with can_transition first.
    """
    conn.execute(
        "UPDATE work_order SET status=%s WHERE id=%s",
        (new_status, wo_id)
    )
