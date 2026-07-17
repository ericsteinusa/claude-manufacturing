"""purchase_orders_core.py — Qt-free data layer for purchase orders.

Imported by the Django web views and unit tested independently.

Every function takes an open connection so the caller controls the transaction
and lifetime; pass a :func:`manufacturing.db_pg.get_db_connection` connection
(native PostgreSQL, ``%s`` placeholders).
"""

from datetime import date

import psycopg2

from .mrp_core import next_sequence_number

# Workflow states a PO moves through, in order. ``cancelled`` is terminal.
PO_STATUSES = ("draft", "pending_approval", "sent", "partial", "received", "cancelled")

# Row background colours, shared with the desktop table (mirrored in the web
# list as a status pill). Keyed by status; unknown statuses fall back to white.
PO_STATUS_COLORS = {
    "draft":            "#ffffff",
    "pending_approval": "#fff0b3",
    "sent":             "#cce5ff",
    "partial":          "#fff3cd",
    "received":         "#d4edda",
    "cancelled":        "#dcdcdc",
}

# Allowed forward status moves. ``received`` and ``cancelled`` are terminal.
# ``pending_approval`` is entered automatically by the approval intercept, not
# via a status button, so it has no outbound web transitions of its own.
PO_STATUS_TRANSITIONS = {
    "draft":            ("sent", "cancelled"),
    "pending_approval": ("cancelled",),
    "sent":             ("partial", "received", "cancelled"),
    "partial":          ("received", "cancelled"),
    "received":         (),
    "cancelled":        (),
}

# Button label shown for a transition into each status.
PO_STATUS_ACTION_LABELS = {
    "sent":      "Mark Sent",
    "partial":   "Mark Partial",
    "received":  "Mark Received",
    "cancelled": "Cancel PO",
}


def allowed_transitions(current):
    """Statuses ``current`` may move to (empty tuple for unknown/terminal)."""
    return PO_STATUS_TRANSITIONS.get(current, ())


def can_transition(current, target):
    """True if a PO in ``current`` status may move to ``target``."""
    return target in PO_STATUS_TRANSITIONS.get(current, ())


def ensure_po_tables(conn):
    """Create the ``purchase_order`` / ``po_item`` tables if absent.

    Idempotent (``CREATE TABLE IF NOT EXISTS``). Does not commit — the caller
    owns the transaction.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order (
            id SERIAL PRIMARY KEY,
            po_number TEXT NOT NULL UNIQUE,
            supplier_id INTEGER,
            order_date TEXT,
            expected_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute("""
        ALTER TABLE purchase_order
        ADD COLUMN IF NOT EXISTS created_by TEXT
    """)
    conn.execute("""
        ALTER TABLE purchase_order
        ADD COLUMN IF NOT EXISTS received_date TEXT
    """)
    # Some environments' live schema has supplier_id NOT NULL despite it
    # being nullable here — a PO legitimately starts supplier-less (see
    # po_new's default form and mrp_web_core.release_plan, which creates a
    # draft buy PO before a supplier is necessarily on file for the
    # product). DROP NOT NULL is a no-op if it's already nullable.
    conn.execute("""
        ALTER TABLE purchase_order
        ALTER COLUMN supplier_id DROP NOT NULL
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS po_item (
            id SERIAL PRIMARY KEY,
            po_id INTEGER NOT NULL REFERENCES purchase_order(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty_ordered INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0.0,
            qty_received INTEGER DEFAULT 0
        )
    """)


def next_po_number(conn, today=None):
    """Return the next ``PO-<year>-NNNN`` on ``conn``'s transaction.

    Uses max-suffix+1 over the existing numbers (via
    :func:`mrp_core.next_sequence_number`), generated on the caller's own
    connection — so minting several POs inside one uncommitted transaction
    yields distinct numbers, unlike a ``COUNT(*)`` on a fresh connection.
    """
    year = (today or date.today()).year
    prefix = f"PO-{year}-"
    rows = conn.execute(
        "SELECT po_number FROM purchase_order WHERE po_number LIKE %s",
        (prefix + "%",)).fetchall()
    return next_sequence_number([r["po_number"] for r in rows], prefix)


def list_pos(conn, status=None, supplier_id=None,
             date_from=None, date_to=None):
    """Return PO header rows (newest first) with item count and line total.

    All filters are optional; a ``None`` filter is not applied. ``date_from`` /
    ``date_to`` bound ``order_date`` inclusively (rows with a NULL order_date
    are kept). Mirrors the desktop list query.
    """
    sql = """
        SELECT po.id, po.po_number, po.order_date, po.expected_date,
               po.status, po.notes, po.created_by, po.supplier_id,
               s.company_name,
               (SELECT COUNT(*) FROM po_item pi WHERE pi.po_id = po.id)
                   AS item_count,
               (SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0)
                FROM po_item pi WHERE pi.po_id = po.id) AS total
        FROM purchase_order po
        LEFT JOIN supplier s ON s.id = po.supplier_id
    """
    conds, params = [], []
    if status:
        conds.append("po.status = %s")
        params.append(status)
    if supplier_id:
        conds.append("po.supplier_id = %s")
        params.append(supplier_id)
    if date_from is not None:
        conds.append("(po.order_date IS NULL OR po.order_date >= %s)")
        params.append(date_from)
    if date_to is not None:
        conds.append("(po.order_date IS NULL OR po.order_date <= %s)")
        params.append(date_to)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY po.order_date DESC NULLS LAST, po.id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_po_dict(r) for r in rows]


def get_po(conn, po_id):
    """Return one PO header dict (with supplier name + totals), or None."""
    row = conn.execute("""
        SELECT po.id, po.po_number, po.order_date, po.expected_date,
               po.status, po.notes, po.created_by, po.supplier_id,
               s.company_name,
               (SELECT COUNT(*) FROM po_item pi WHERE pi.po_id = po.id)
                   AS item_count,
               (SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0)
                FROM po_item pi WHERE pi.po_id = po.id) AS total
        FROM purchase_order po
        LEFT JOIN supplier s ON s.id = po.supplier_id
        WHERE po.id = %s
    """, (po_id,)).fetchone()
    return _po_dict(row) if row else None


def get_po_items(conn, po_id):
    """Return the line items for a PO, each with product name + line total."""
    rows = conn.execute("""
        SELECT pi.id, pi.description, pi.product_id, p.name AS product_name,
               pi.qty_ordered, pi.unit_price, pi.qty_received,
               (pi.qty_ordered * pi.unit_price) AS line_total
        FROM po_item pi
        LEFT JOIN product p ON p.id = pi.product_id
        WHERE pi.po_id = %s
        ORDER BY pi.id
    """, (po_id,)).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["unit_price"] = float(d["unit_price"] or 0.0)
        d["line_total"] = float(d["line_total"] or 0.0)
        items.append(d)
    return items


def load_suppliers(conn):
    """Return ``[{id, company_name}]`` for the supplier picker (empty if the
    table is absent)."""
    try:
        rows = conn.execute(
            "SELECT id, company_name FROM supplier ORDER BY company_name"
        ).fetchall()
    except psycopg2.Error:
        return []
    return [dict(r) for r in rows]


def load_products(conn):
    """Return ``[{id, product_name}]`` for the product picker (empty if the
    table is absent)."""
    try:
        rows = conn.execute(
            "SELECT id, name AS product_name FROM product ORDER BY name"
        ).fetchall()
    except psycopg2.Error:
        return []
    return [dict(r) for r in rows]


def create_po(conn, po_number, supplier_id=None, order_date=None,
              expected_date=None, status="draft", notes=None,
              created_by=None):
    """Insert a PO header and return its new id. Does not commit.

    Raises ``psycopg2.IntegrityError`` if ``po_number`` already exists (the
    column is UNIQUE); the caller is expected to surface that to the user.
    """
    row = conn.execute(
        "INSERT INTO purchase_order (po_number, supplier_id, order_date,"
        " expected_date, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (po_number, supplier_id, order_date, expected_date, status, notes,
         created_by)
    ).fetchone()
    return row["id"]


def update_po(conn, po_id, supplier_id=None, order_date=None,
              expected_date=None, notes=None):
    """Update the editable header fields of a PO. Does not commit.

    Status and po_number are intentionally not touched here — status changes
    go through the dedicated workflow action.
    """
    conn.execute(
        "UPDATE purchase_order SET supplier_id=%s, order_date=%s,"
        " expected_date=%s, notes=%s WHERE id=%s",
        (supplier_id, order_date, expected_date, notes, po_id)
    )


def add_po_item(conn, po_id, description, product_id=None,
                qty_ordered=1, unit_price=0.0):
    """Append a line item to a PO. Does not commit."""
    conn.execute(
        "INSERT INTO po_item (po_id, description, product_id,"
        " qty_ordered, unit_price) VALUES (%s,%s,%s,%s,%s)",
        (po_id, description, product_id, qty_ordered, unit_price)
    )


def delete_po_item(conn, item_id, po_id=None):
    """Remove a line item. If ``po_id`` is given, only delete when the item
    belongs to it (guards against cross-PO deletes from a forged id). Does not
    commit. Returns the number of rows deleted.
    """
    if po_id is None:
        cur = conn.execute("DELETE FROM po_item WHERE id=%s", (item_id,))
    else:
        cur = conn.execute(
            "DELETE FROM po_item WHERE id=%s AND po_id=%s", (item_id, po_id))
    return cur.rowcount


def set_po_status(conn, po_id, new_status):
    """Set a PO's status. Does not commit and does not check the transition —
    callers should gate with :func:`can_transition` first.

    Stamps received_date the first time a PO reaches 'received' (kept if
    already set, e.g. a repeated call), so on-time delivery can later be
    measured against expected_date — see supplier_scorecard_core.py.
    """
    if new_status == 'received':
        conn.execute(
            "UPDATE purchase_order SET status=%s, "
            "received_date = COALESCE(received_date, CURRENT_DATE::TEXT) "
            "WHERE id=%s",
            (new_status, po_id))
    else:
        conn.execute(
            "UPDATE purchase_order SET status=%s WHERE id=%s",
            (new_status, po_id))

    from .webhook_core import dispatch_event
    dispatch_event(conn, f'po.{new_status}', 'purchase_order', po_id)


def receive_po_item(conn, item_id, qty_received, po_id=None):
    """Record received quantity for a line item. Does not commit.

    If ``po_id`` is given, only updates when the item belongs to it (guards a
    forged item id). Returns the number of rows updated.
    """
    if po_id is None:
        cur = conn.execute(
            "UPDATE po_item SET qty_received=%s WHERE id=%s",
            (qty_received, item_id))
    else:
        cur = conn.execute(
            "UPDATE po_item SET qty_received=%s WHERE id=%s AND po_id=%s",
            (qty_received, item_id, po_id))
    return cur.rowcount


def _po_dict(row):
    """Normalise a PO header row to a plain dict with a float ``total``."""
    d = dict(row)
    d["total"] = float(d["total"] or 0.0)
    d["item_count"] = int(d["item_count"] or 0)
    return d
