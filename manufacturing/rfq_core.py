"""rfq_core.py — Qt-free Request for Quote module (P1-F).

rfq             — header: number, status, notes
rfq_item        — line items with qty + target_price (what we hope to pay)
rfq_vendor      — vendors invited to quote (from the supplier table)
rfq_quote_line  — the price/lead-time matrix: one row per (item, vendor)

Flow: create an RFQ, add line items + invite vendors, enter each vendor's
quoted price per line (enter_quote is an upsert), compare side by side via
get_comparison(), then award_items() picks a winning vendor per line,
groups the awarded lines by vendor, and converts each group into its own
draft Purchase Order via purchase_orders_core (one PO per winning vendor —
different lines can go to different vendors).
"""

import datetime

from .mrp_core import next_sequence_number
from .purchase_orders_core import create_po, add_po_item, next_po_number
from .contacts_core import contact_label

STATUSES = ('open', 'awarded', 'closed')


def ensure_rfq_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rfq (
            id         SERIAL PRIMARY KEY,
            rfq_number TEXT NOT NULL UNIQUE,
            status     TEXT NOT NULL DEFAULT 'open',
            notes      TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rfq_item (
            id                SERIAL PRIMARY KEY,
            rfq_id            INTEGER NOT NULL REFERENCES rfq(id),
            description       TEXT NOT NULL,
            product_id        INTEGER REFERENCES product(id),
            qty               INTEGER NOT NULL DEFAULT 1,
            target_price      REAL NOT NULL DEFAULT 0.0,
            awarded_vendor_id INTEGER REFERENCES supplier(id),
            po_id             INTEGER REFERENCES purchase_order(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rfq_vendor (
            id          SERIAL PRIMARY KEY,
            rfq_id      INTEGER NOT NULL REFERENCES rfq(id),
            supplier_id INTEGER NOT NULL REFERENCES supplier(id),
            UNIQUE (rfq_id, supplier_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rfq_quote_line (
            id             SERIAL PRIMARY KEY,
            rfq_item_id    INTEGER NOT NULL REFERENCES rfq_item(id),
            vendor_id      INTEGER NOT NULL REFERENCES supplier(id),
            quoted_price   REAL,
            lead_time_days INTEGER,
            UNIQUE (rfq_item_id, vendor_id)
        )
    """)


def next_rfq_number(conn, today=None):
    year = (today or datetime.date.today()).year
    prefix = f"RFQ-{year}-"
    rows = conn.execute(
        "SELECT rfq_number FROM rfq WHERE rfq_number LIKE %s",
        (prefix + "%",),
    ).fetchall()
    return next_sequence_number([r['rfq_number'] for r in rows], prefix)


# ---------------------------------------------------------------------------
# Header CRUD
# ---------------------------------------------------------------------------

def create_rfq(conn, notes='', created_by=''):
    rfq_number = next_rfq_number(conn)
    row = conn.execute(
        "INSERT INTO rfq (rfq_number, notes, created_by) "
        "VALUES (%s, %s, %s) RETURNING id",
        (rfq_number, notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def get_rfq(conn, rfq_id):
    row = conn.execute("SELECT * FROM rfq WHERE id = %s", (rfq_id,)).fetchone()
    return dict(row) if row else None


def list_rfqs(conn, status=None):
    conds, params = [], []
    if status:
        conds.append("status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(
        f"SELECT * FROM rfq {where} ORDER BY created_at DESC", params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

def add_rfq_item(conn, rfq_id, description, product_id=None, qty=1, target_price=0.0):
    row = conn.execute(
        "INSERT INTO rfq_item (rfq_id, description, product_id, qty, target_price) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (rfq_id, description, product_id, qty, target_price),
    ).fetchone()
    return row['id']


def delete_rfq_item(conn, item_id):
    conn.execute("DELETE FROM rfq_quote_line WHERE rfq_item_id = %s", (item_id,))
    conn.execute("DELETE FROM rfq_item WHERE id = %s", (item_id,))


def get_rfq_item(conn, item_id):
    row = conn.execute(
        "SELECT * FROM rfq_item WHERE id = %s", (item_id,)
    ).fetchone()
    return dict(row) if row else None


def list_rfq_items(conn, rfq_id):
    rows = conn.execute("""
        SELECT ri.*, p.name AS product_name
        FROM rfq_item ri
        LEFT JOIN product p ON p.id = ri.product_id
        WHERE ri.rfq_id = %s
        ORDER BY ri.id
    """, (rfq_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------

def add_rfq_vendor(conn, rfq_id, supplier_id):
    conn.execute(
        "INSERT INTO rfq_vendor (rfq_id, supplier_id) VALUES (%s, %s) "
        "ON CONFLICT (rfq_id, supplier_id) DO NOTHING",
        (rfq_id, supplier_id),
    )


def remove_rfq_vendor(conn, rfq_vendor_id):
    conn.execute("DELETE FROM rfq_vendor WHERE id = %s", (rfq_vendor_id,))


def list_rfq_vendors(conn, rfq_id):
    rows = conn.execute("""
        SELECT rv.id AS rfq_vendor_id, s.*
        FROM rfq_vendor rv
        JOIN supplier s ON s.id = rv.supplier_id
        WHERE rv.rfq_id = %s
        ORDER BY s.company_name
    """, (rfq_id,)).fetchall()
    result = [dict(r) for r in rows]
    for r in result:
        r['label'] = contact_label(r)
    return result


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

def enter_quote(conn, rfq_item_id, vendor_id, quoted_price, lead_time_days=None):
    conn.execute("""
        INSERT INTO rfq_quote_line (rfq_item_id, vendor_id, quoted_price, lead_time_days)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (rfq_item_id, vendor_id)
        DO UPDATE SET quoted_price = EXCLUDED.quoted_price,
                      lead_time_days = EXCLUDED.lead_time_days
    """, (rfq_item_id, vendor_id, quoted_price, lead_time_days))


def get_quote(conn, rfq_item_id, vendor_id):
    row = conn.execute(
        "SELECT * FROM rfq_quote_line WHERE rfq_item_id = %s AND vendor_id = %s",
        (rfq_item_id, vendor_id),
    ).fetchone()
    return dict(row) if row else None


def get_comparison(conn, rfq_id):
    """Return {'vendors': [...], 'rows': [(item, [(vendor, cell), ...]), ...]}.

    Each row's (vendor, cell) pairs are pre-zipped with 'vendors' so a
    template can render the matrix with one nested loop, with no need to
    index a list by another loop's position (Django templates can't do
    that dynamically). A cell is the quote dict (with an 'is_lowest' flag
    added) or None if that vendor hasn't quoted this item.
    """
    vendors = list_rfq_vendors(conn, rfq_id)
    items = list_rfq_items(conn, rfq_id)
    rows = []
    for item in items:
        quotes = conn.execute(
            "SELECT * FROM rfq_quote_line WHERE rfq_item_id = %s",
            (item['id'],),
        ).fetchall()
        by_vendor = {q['vendor_id']: dict(q) for q in quotes}
        priced = [q for q in by_vendor.values() if q['quoted_price'] is not None]
        lowest = min((q['quoted_price'] for q in priced), default=None)
        vendor_cells = []
        for v in vendors:
            cell = by_vendor.get(v['id'])
            if cell:
                cell['is_lowest'] = (
                    lowest is not None and cell['quoted_price'] == lowest
                )
            vendor_cells.append((v, cell))
        rows.append((item, vendor_cells))
    return {'vendors': vendors, 'rows': rows}


# ---------------------------------------------------------------------------
# Award -> convert to PO
# ---------------------------------------------------------------------------

def award_items(conn, rfq_id, awards, created_by):
    """Award RFQ lines to vendors and convert each vendor's awarded lines
    into its own draft Purchase Order.

    ``awards`` is {rfq_item_id: vendor_id}. Uses each item's quoted price
    where a quote exists, else falls back to target_price. Returns the list
    of PO ids created (one per distinct vendor).
    """
    rfq = get_rfq(conn, rfq_id)
    if not rfq:
        raise ValueError(f"RFQ {rfq_id} not found")
    by_vendor: dict = {}
    for item_id, vendor_id in awards.items():
        by_vendor.setdefault(vendor_id, []).append(item_id)

    po_ids = []
    for vendor_id, item_ids in by_vendor.items():
        po_number = next_po_number(conn)
        po_id = create_po(
            conn, po_number, supplier_id=vendor_id,
            order_date=datetime.date.today().isoformat(), status='draft',
            notes=f"Converted from {rfq['rfq_number']}", created_by=created_by,
        )
        for item_id in item_ids:
            item = get_rfq_item(conn, item_id)
            if not item:
                raise ValueError(f"RFQ item {item_id} not found")
            quote = get_quote(conn, item_id, vendor_id)
            unit_price = (
                quote['quoted_price']
                if quote and quote['quoted_price'] is not None
                else item['target_price']
            )
            add_po_item(
                conn, po_id, item['description'], product_id=item['product_id'],
                qty_ordered=item['qty'], unit_price=unit_price,
            )
            conn.execute(
                "UPDATE rfq_item SET awarded_vendor_id = %s, po_id = %s WHERE id = %s",
                (vendor_id, po_id, item_id),
            )
        po_ids.append(po_id)

    conn.execute("UPDATE rfq SET status = 'awarded' WHERE id = %s", (rfq_id,))
    return po_ids
