"""purchase_orders_core.py — Qt-free data layer for purchase orders.

Kept separate from :mod:`purchase_orders` (which imports PyQt6) so the SQL can
be imported by the Django web views and unit tested without the Qt shared
libraries — CI runners lack ``libEGL`` and cannot ``import PyQt6``. The Qt
module imports/re-exports the pieces it shares from here (same pattern as
``bom_core`` / ``mrp_core``).

Every function takes an open connection so the caller controls the transaction
and lifetime; pass a :func:`manufacturing.db_pg.get_db_connection` connection
(native PostgreSQL, ``%s`` placeholders).
"""

from datetime import date

from .mrp_core import next_sequence_number

# Workflow states a PO moves through, in order. ``cancelled`` is terminal.
PO_STATUSES = ("draft", "sent", "partial", "received", "cancelled")

# Row background colours, shared with the desktop table (mirrored in the web
# list as a status pill). Keyed by status; unknown statuses fall back to white.
PO_STATUS_COLORS = {
    "draft":     "#ffffff",
    "sent":      "#cce5ff",
    "partial":   "#fff3cd",
    "received":  "#d4edda",
    "cancelled": "#dcdcdc",
}


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
            notes TEXT
        )
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
               po.status, po.notes, po.supplier_id, s.company_name,
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
               po.status, po.notes, po.supplier_id, s.company_name,
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


def _po_dict(row):
    """Normalise a PO header row to a plain dict with a float ``total``."""
    d = dict(row)
    d["total"] = float(d["total"] or 0.0)
    d["item_count"] = int(d["item_count"] or 0)
    return d
