"""receiving_core.py — Qt-free receiving / goods-in workflow.

A ``receiving`` record represents one inbound shipment (from a carrier,
optionally against a PO), with one or more ``receiving_item`` lines. This
is distinct from the PO-item-level "WMS Receive & Put-Away" screen
(wms_core.receive_and_putaway) -- that flow receives *against a specific
PO's own items* one at a time; this one models a shipment's own dock
paperwork (carrier, tracking number, per-line qty ordered/received) and
existed only as seeded sample data with no web page before this module.

Marking a line item received still credits the *same* inventory and WMS
bin-stock numbers as the PO screen, via wms_core.receive_into_bin --
lines with no product_id (free-text descriptions not linked to a real
product record) can only have their own qty_received tracked, the same
"can't be put away automatically" limit documented on wms_core's own
_open_po_items helper.
"""

from datetime import date

from .mrp_core import next_sequence_number
from .wms_core import receive_into_bin

RECEIVING_STATUSES = ('pending', 'partial', 'received', 'rejected')


def ensure_receiving_tables(conn):
    """Create receiving/receiving_item if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving (
            id SERIAL PRIMARY KEY,
            rcv_number TEXT NOT NULL UNIQUE,
            po_id INTEGER,
            rcv_date TEXT,
            supplier TEXT,
            carrier TEXT,
            tracking_number TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving_item (
            id SERIAL PRIMARY KEY,
            receiving_id INTEGER NOT NULL REFERENCES receiving(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty_ordered INTEGER DEFAULT 1,
            qty_received INTEGER DEFAULT 0
        )
    """)
    conn.execute(
        "ALTER TABLE receiving ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''"
    )
    conn.execute(
        "ALTER TABLE receiving_item ADD COLUMN IF NOT EXISTS bin_id INTEGER"
    )


def next_rcv_number(conn, today=None):
    """Return the next ``RCV-<year>-NNNN`` on conn's own transaction (see
    next_po_number's identical rationale for generating on the caller's own
    connection rather than a COUNT(*))."""
    year = (today or date.today()).year
    prefix = f"RCV-{year}-"
    rows = conn.execute(
        "SELECT rcv_number FROM receiving WHERE rcv_number LIKE %s",
        (prefix + "%",),
    ).fetchall()
    return next_sequence_number([r['rcv_number'] for r in rows], prefix)


def list_receipts(conn, status=None, search=None):
    sql = (
        "SELECT id, rcv_number, po_id, rcv_date, supplier, carrier, "
        "tracking_number, status, notes, created_by "
        "FROM receiving WHERE TRUE"
    )
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (rcv_number ILIKE %s OR supplier ILIKE %s OR tracking_number ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY rcv_date DESC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_receipt(conn, receiving_id):
    row = conn.execute(
        "SELECT * FROM receiving WHERE id = %s", (receiving_id,)
    ).fetchone()
    return dict(row) if row else None


def get_receipt_items(conn, receiving_id):
    rows = conn.execute("""
        SELECT ri.id, ri.description, ri.product_id, ri.qty_ordered,
               ri.qty_received, ri.bin_id, p.name AS product_name,
               b.full_code AS bin_code
        FROM receiving_item ri
        LEFT JOIN product p ON p.id = ri.product_id
        LEFT JOIN wms_bin b ON b.id = ri.bin_id
        WHERE ri.receiving_id = %s
        ORDER BY ri.id
    """, (receiving_id,)).fetchall()
    return [dict(r) for r in rows]


def create_receipt(conn, po_id, rcv_date, supplier, carrier,
                    tracking_number, notes, created_by):
    if not supplier or not supplier.strip():
        raise ValueError("Supplier is required.")
    rcv_number = next_rcv_number(conn)
    row = conn.execute(
        "INSERT INTO receiving (rcv_number, po_id, rcv_date, supplier, "
        "carrier, tracking_number, status, notes, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s) RETURNING id",
        (rcv_number, po_id, rcv_date, supplier.strip(), carrier or '',
         tracking_number or '', notes or '', created_by),
    ).fetchone()
    return row['id']


def add_receipt_item(conn, receiving_id, description, product_id, qty_ordered):
    if not description or not description.strip():
        raise ValueError("Description is required.")
    row = conn.execute(
        "INSERT INTO receiving_item (receiving_id, description, product_id, "
        "qty_ordered, qty_received) VALUES (%s, %s, %s, %s, 0) RETURNING id",
        (receiving_id, description.strip(), product_id, qty_ordered or 1),
    ).fetchone()
    _recompute_status(conn, receiving_id)
    return row['id']


def _recompute_status(conn, receiving_id):
    """Derive the header status from its lines' completion. Does not
    commit. A receipt already marked 'rejected' is left untouched -- that's
    a terminal, manually-set status independent of line completion."""
    current = conn.execute(
        "SELECT status FROM receiving WHERE id = %s", (receiving_id,)
    ).fetchone()
    if not current or current['status'] == 'rejected':
        return
    lines = conn.execute(
        "SELECT qty_ordered, qty_received FROM receiving_item "
        "WHERE receiving_id = %s", (receiving_id,)
    ).fetchall()
    if not lines:
        status = 'pending'
    elif all(ln['qty_received'] >= ln['qty_ordered'] for ln in lines):
        status = 'received'
    elif any(ln['qty_received'] > 0 for ln in lines):
        status = 'partial'
    else:
        status = 'pending'
    conn.execute(
        "UPDATE receiving SET status = %s WHERE id = %s",
        (status, receiving_id),
    )


def receive_item(conn, item_id, qty, bin_id, created_by):
    """Receive qty on one receiving_item line, clamped so repeated partial
    receipts never exceed qty_ordered or double-count.

    If the line has a linked product_id, credits inventory + the chosen
    WMS bin via wms_core.receive_into_bin (same mechanism the PO put-away
    screen uses) -- a line with no product_id only updates its own
    qty_received, since there's no product identity to credit stock to.
    Recomputes the parent receipt's status. Does not commit. Raises
    ValueError if qty is not positive or the line doesn't exist.
    """
    if qty is None or qty <= 0:
        raise ValueError("Quantity received must be positive.")
    item = conn.execute(
        "SELECT * FROM receiving_item WHERE id = %s", (item_id,)
    ).fetchone()
    if not item:
        raise ValueError(f"Receiving line {item_id} not found.")

    new_total = min(item['qty_received'] + qty, item['qty_ordered'])
    delta = new_total - item['qty_received']
    if delta <= 0:
        return 0

    conn.execute(
        "UPDATE receiving_item SET qty_received = %s, bin_id = COALESCE(%s, bin_id) "
        "WHERE id = %s",
        (new_total, bin_id, item_id),
    )
    if item['product_id'] and bin_id:
        receive_into_bin(
            conn, item['product_id'], delta, bin_id, created_by,
            reference=f'Receiving item {item_id}', notes='Receiving',
        )
    _recompute_status(conn, item['receiving_id'])
    return delta


def reject_receipt(conn, receiving_id, notes):
    conn.execute(
        "UPDATE receiving SET status = 'rejected', "
        "notes = CASE WHEN %s != '' THEN %s ELSE notes END WHERE id = %s",
        (notes or '', notes or '', receiving_id),
    )
