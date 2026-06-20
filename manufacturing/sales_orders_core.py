"""Qt-free sales-order data layer.

Kept separate from sales_orders.py (which imports PyQt6) so the SQL can be
imported by Django web views and unit-tested without the Qt shared libraries.
Every function takes an open connection; the caller controls the transaction
and lifetime (pass a db_pg.get_db_connection() connection, %s placeholders).
"""
from datetime import date

import psycopg2

from .mrp_core import next_sequence_number

SO_STATUSES = ("draft", "confirmed", "shipped", "invoiced", "cancelled")

SO_STATUS_COLORS = {
    "draft":     "#ffffff",
    "confirmed": "#cce5ff",
    "shipped":   "#fff3cd",
    "invoiced":  "#d4edda",
    "cancelled": "#dcdcdc",
}

SO_STATUS_TRANSITIONS = {
    "draft":     ("confirmed", "cancelled"),
    "confirmed": ("shipped", "cancelled"),
    "shipped":   ("invoiced", "cancelled"),
    "invoiced":  (),
    "cancelled": (),
}

SO_STATUS_ACTION_LABELS = {
    "confirmed": "Confirm",
    "shipped":   "Mark Shipped",
    "invoiced":  "Mark Invoiced",
    "cancelled": "Cancel Order",
}


def allowed_transitions(current):
    """Statuses ``current`` may move to (empty tuple for unknown/terminal)."""
    return SO_STATUS_TRANSITIONS.get(current, ())


def can_transition(current, target):
    """True if an SO in ``current`` status may move to ``target``."""
    return target in SO_STATUS_TRANSITIONS.get(current, ())


def customer_label(row):
    """Return a display string for a customer row dict (company name, or
    first+last if no company)."""
    company = row.get("company_name") or ""
    first = row.get("first_name") or ""
    last = row.get("last_name") or ""
    name = f"{first} {last}".strip()
    return company if company else name


def ensure_so_tables(conn):
    """Create sales_order / so_item tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_order (
            id SERIAL PRIMARY KEY,
            so_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER,
            order_date TEXT,
            ship_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute("""
        ALTER TABLE sales_order
        ADD COLUMN IF NOT EXISTS created_by TEXT
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS so_item (
            id SERIAL PRIMARY KEY,
            so_id INTEGER NOT NULL REFERENCES sales_order(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0.0
        )
    """)


def next_so_number(conn, today=None):
    """Return the next SO-<year>-NNNN on conn's transaction.

    Uses max-suffix+1 (gap-safe), generated on the caller's own connection —
    so creating several SOs in one uncommitted transaction yields distinct
    numbers, unlike a COUNT(*) on a fresh connection.
    """
    year = (today or date.today()).year
    prefix = f"SO-{year}-"
    rows = conn.execute(
        "SELECT so_number FROM sales_order WHERE so_number LIKE %s",
        (prefix + "%",)
    ).fetchall()
    return next_sequence_number([r["so_number"] for r in rows], prefix)


def list_sos(conn, status=None, customer_id=None,
             date_from=None, date_to=None):
    """Return SO header rows (newest first) with customer name, item count,
    and line total. All filters are optional; date_from / date_to bound
    order_date inclusively (NULL order_dates are always included).
    """
    sql = """
        SELECT so.id, so.so_number, so.order_date, so.ship_date,
               so.status, so.notes, so.created_by, so.customer_id,
               c.company_name, c.first_name, c.last_name,
               (SELECT COUNT(*) FROM so_item si WHERE si.so_id = so.id)
                   AS item_count,
               (SELECT COALESCE(SUM(si.qty * si.unit_price), 0)
                FROM so_item si WHERE si.so_id = so.id) AS total
        FROM sales_order so
        LEFT JOIN customer c ON c.id = so.customer_id
    """
    conds, params = [], []
    if status:
        conds.append("so.status = %s")
        params.append(status)
    if customer_id:
        conds.append("so.customer_id = %s")
        params.append(customer_id)
    if date_from is not None:
        conds.append("(so.order_date IS NULL OR so.order_date >= %s)")
        params.append(date_from)
    if date_to is not None:
        conds.append("(so.order_date IS NULL OR so.order_date <= %s)")
        params.append(date_to)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY so.order_date DESC NULLS LAST, so.id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_so_dict(r) for r in rows]


def get_so(conn, so_id):
    """Return one SO header dict (with customer info + totals), or None."""
    row = conn.execute("""
        SELECT so.id, so.so_number, so.order_date, so.ship_date,
               so.status, so.notes, so.created_by, so.customer_id,
               c.company_name, c.first_name, c.last_name,
               (SELECT COUNT(*) FROM so_item si WHERE si.so_id = so.id)
                   AS item_count,
               (SELECT COALESCE(SUM(si.qty * si.unit_price), 0)
                FROM so_item si WHERE si.so_id = so.id) AS total
        FROM sales_order so
        LEFT JOIN customer c ON c.id = so.customer_id
        WHERE so.id = %s
    """, (so_id,)).fetchone()
    return _so_dict(row) if row else None


def get_so_items(conn, so_id):
    """Return line items for an SO, each with product name and line total."""
    rows = conn.execute("""
        SELECT si.id, si.description, si.product_id,
               p.name AS product_name, si.qty, si.unit_price,
               (si.qty * si.unit_price) AS line_total
        FROM so_item si
        LEFT JOIN product p ON p.id = si.product_id
        WHERE si.so_id = %s
        ORDER BY si.id
    """, (so_id,)).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["unit_price"] = float(d["unit_price"] or 0.0)
        d["line_total"] = float(d["line_total"] or 0.0)
        items.append(d)
    return items


def load_customers(conn):
    """Return [{id, company_name, first_name, last_name}] for the customer
    picker (empty on error)."""
    try:
        rows = conn.execute(
            "SELECT id, company_name, first_name, last_name "
            "FROM customer ORDER BY company_name"
        ).fetchall()
    except psycopg2.Error:
        return []
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


def create_so(conn, so_number, customer_id=None, order_date=None,
              ship_date=None, status="draft", notes=None, created_by=None):
    """Insert an SO and return its new id. Does not commit.

    Raises psycopg2.IntegrityError if so_number already exists.
    """
    row = conn.execute(
        "INSERT INTO sales_order (so_number, customer_id, order_date,"
        " ship_date, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (so_number, customer_id, order_date, ship_date, status, notes,
         created_by)
    ).fetchone()
    return row["id"]


def update_so(conn, so_id, customer_id=None, order_date=None,
              ship_date=None, notes=None):
    """Update editable SO fields. Does not commit.

    so_number and status are intentionally excluded — status changes go
    through set_so_status.
    """
    conn.execute(
        "UPDATE sales_order SET customer_id=%s, order_date=%s,"
        " ship_date=%s, notes=%s WHERE id=%s",
        (customer_id, order_date, ship_date, notes, so_id)
    )


def add_so_item(conn, so_id, description, product_id=None,
                qty=1, unit_price=0.0):
    """Append a line item to an SO. Does not commit."""
    conn.execute(
        "INSERT INTO so_item (so_id, description, product_id, qty,"
        " unit_price) VALUES (%s,%s,%s,%s,%s)",
        (so_id, description, product_id, qty, unit_price)
    )


def delete_so_item(conn, item_id, so_id=None):
    """Remove a line item. If so_id is given, only deletes when the item
    belongs to it (guards against cross-SO deletes from a forged id).
    Does not commit. Returns the number of rows deleted.
    """
    if so_id is None:
        cur = conn.execute("DELETE FROM so_item WHERE id=%s", (item_id,))
    else:
        cur = conn.execute(
            "DELETE FROM so_item WHERE id=%s AND so_id=%s", (item_id, so_id))
    return cur.rowcount


def set_so_status(conn, so_id, new_status):
    """Set an SO's status. Does not commit and does not check the transition —
    callers should gate with can_transition first.
    """
    conn.execute(
        "UPDATE sales_order SET status=%s WHERE id=%s",
        (new_status, so_id)
    )


def _so_dict(row):
    """Normalise an SO header row to a plain dict with float total."""
    d = dict(row)
    d["total"] = float(d["total"] or 0.0)
    d["item_count"] = int(d["item_count"] or 0)
    return d
