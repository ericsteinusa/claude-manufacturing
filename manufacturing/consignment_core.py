"""
consignment_core.py — Qt-free Consignment (Vendor-Owned) Inventory.

A consignment agreement lets a supplier ship stock into our warehouse that
we don't own (and don't pay for) until we actually use it. This is a
single-product, open-ended replenishment relationship — not a fixed-ceiling
agreement like ``blanket_po_core.py`` — so there's no "total value/qty" to
track against; instead it's two running ledgers per agreement:

    consignment_receipt — vendor ships stock in. Increases the vendor-owned
        balance. Deliberately does **not** touch ``product.amount`` or call
        ``inventory_core.record_transaction`` — the goods are physically
        on-site but not yet company-owned, so they must not appear in our
        own stock count (the same "don't blend two ownership concepts into
        one column" discipline as ``wms_core.py``'s bin-stock-vs-aggregate
        split, just one level earlier: vendor-owned vs. company-owned,
        before company-owned vs. bin-located).

    consignment_usage — we use/consume consigned stock. This is the single
        moment ownership transfers: it decrements the vendor-owned balance,
        credits ``product.amount`` via ``inventory_core.record_transaction``
        (a plain ``'receive'`` — the stock is now ours to count and use, the
        same front-door every other "goods become company-owned" event in
        this codebase goes through), and creates an open AP invoice for the
        vendor via ``accounting_core.create_ap_invoice`` — consumption *is*
        the billing trigger in a consignment arrangement, unlike a normal
        PO where the invoice follows receipt. **Deliberately simplified**:
        in a real warehouse, consigned stock can be physically picked
        straight out of its bin for production/shipment without a separate
        "we now own this" administrative step — modeling that exactly would
        mean hooking into WO material-pick and SO-ship (both already-pinned
        call sites in other modules). Instead, recording usage here is the
        one explicit action that stands in for "this qty left vendor
        ownership and entered ours," made at whatever point staff choose
        (immediately on pick, or in a periodic batch reconciliation) —
        the same honest scoping choice ``landed_cost_core.py`` documents for
        why its allocation is a separate action rather than auto-triggered
        by receiving.

Every function takes an open connection; the caller owns the transaction
(same convention as blanket_po_core / landed_cost_core / wms_core).
"""

from __future__ import annotations

from datetime import datetime, date, timedelta

from .log_utils import get_logger
from .mrp_core import next_sequence_number
from .inventory_core import record_transaction
from .accounting_core import create_ap_invoice

log = get_logger(__name__)

AGREEMENT_STATUSES = ('active', 'expired', 'cancelled')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_consignment_tables(conn) -> None:
    """Create consignment tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consignment_agreement (
            id                SERIAL PRIMARY KEY,
            agreement_number  TEXT UNIQUE,
            supplier_id       INTEGER,
            product_id        INTEGER NOT NULL REFERENCES product(id),
            unit_cost         REAL NOT NULL DEFAULT 0,
            start_date        TEXT DEFAULT '',
            end_date          TEXT DEFAULT '',
            status            TEXT DEFAULT 'active',
            notes             TEXT DEFAULT '',
            created_by        TEXT DEFAULT '',
            created_at        TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consignment_receipt (
            id             SERIAL PRIMARY KEY,
            agreement_id   INTEGER NOT NULL REFERENCES consignment_agreement(id) ON DELETE CASCADE,
            qty            REAL NOT NULL,
            reference      TEXT DEFAULT '',
            created_by     TEXT DEFAULT '',
            created_at     TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consignment_usage (
            id             SERIAL PRIMARY KEY,
            agreement_id   INTEGER NOT NULL REFERENCES consignment_agreement(id) ON DELETE CASCADE,
            qty            REAL NOT NULL,
            unit_cost      REAL NOT NULL,
            ap_invoice_id  INTEGER,
            reference      TEXT DEFAULT '',
            created_by     TEXT DEFAULT '',
            created_at     TEXT DEFAULT ''
        )
    """)


def next_agreement_number(conn) -> str:
    year = datetime.now().year
    rows = conn.execute(
        "SELECT agreement_number FROM consignment_agreement WHERE agreement_number LIKE %s",
        (f"CONSIGN-{year}-%",),
    ).fetchall()
    existing = [dict(r)['agreement_number'] for r in rows]
    return next_sequence_number(existing, f"CONSIGN-{year}-")


def list_products_for_picker(conn) -> list:
    rows = conn.execute("SELECT id, name FROM product ORDER BY name").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Status sync (lazy auto-expire, same precedent as blanket_po_core)
# ---------------------------------------------------------------------------

def _sync_status(conn, agreement_id: int) -> str:
    header = conn.execute(
        "SELECT status, end_date FROM consignment_agreement WHERE id = %s",
        (agreement_id,),
    ).fetchone()
    if not header:
        return ''
    h = dict(header)
    current = h['status']
    if current in ('cancelled', 'expired'):
        return current

    new_status = current
    if h['end_date']:
        try:
            end = datetime.strptime(h['end_date'][:10], '%Y-%m-%d').date()
            if end < date.today():
                new_status = 'expired'
        except ValueError:
            pass

    if new_status != current:
        conn.execute(
            "UPDATE consignment_agreement SET status = %s WHERE id = %s",
            (new_status, agreement_id),
        )
    return new_status


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _balances(conn, agreement_id: int) -> dict:
    received = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS qty FROM consignment_receipt WHERE agreement_id = %s",
        (agreement_id,),
    ).fetchone()
    used = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS qty, COALESCE(SUM(qty * unit_cost), 0) AS value "
        "FROM consignment_usage WHERE agreement_id = %s",
        (agreement_id,),
    ).fetchone()
    received_qty = float(dict(received)['qty'] or 0.0)
    used_qty = float(dict(used)['qty'] or 0.0)
    used_value = float(dict(used)['value'] or 0.0)
    on_hand_qty = max(received_qty - used_qty, 0.0)
    return {
        'received_qty': received_qty,
        'used_qty': used_qty,
        'used_value': used_value,
        'on_hand_qty': on_hand_qty,
    }


def _with_balances(conn, row: dict) -> dict:
    d = dict(row)
    b = _balances(conn, d['id'])
    d.update(b)
    d['on_hand_value'] = d['on_hand_qty'] * float(d['unit_cost'] or 0.0)
    return d


def list_agreements(conn, status: str | None = None, supplier_id: int | None = None) -> list:
    sql = """
        SELECT ca.*, s.company_name AS supplier_name, p.name AS product_name
        FROM consignment_agreement ca
        LEFT JOIN supplier s ON s.id = ca.supplier_id
        JOIN product p ON p.id = ca.product_id
        WHERE 1=1
    """
    params: list = []
    if supplier_id:
        sql += " AND ca.supplier_id = %s"
        params.append(supplier_id)
    sql += " ORDER BY ca.id DESC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['status'] = _sync_status(conn, d['id'])
        if status and d['status'] != status:
            continue
        out.append(_with_balances(conn, d))
    return out


def get_agreement(conn, agreement_id: int) -> dict | None:
    _sync_status(conn, agreement_id)
    row = conn.execute("""
        SELECT ca.*, s.company_name AS supplier_name, p.name AS product_name
        FROM consignment_agreement ca
        LEFT JOIN supplier s ON s.id = ca.supplier_id
        JOIN product p ON p.id = ca.product_id
        WHERE ca.id = %s
    """, (agreement_id,)).fetchone()
    if not row:
        return None
    return _with_balances(conn, dict(row))


def list_receipts(conn, agreement_id: int) -> list:
    rows = conn.execute(
        "SELECT * FROM consignment_receipt WHERE agreement_id = %s ORDER BY id",
        (agreement_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_usages(conn, agreement_id: int) -> list:
    rows = conn.execute(
        "SELECT * FROM consignment_usage WHERE agreement_id = %s ORDER BY id",
        (agreement_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['total_cost'] = float(d['qty'] or 0.0) * float(d['unit_cost'] or 0.0)
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def create_agreement(conn, supplier_id, product_id: int, unit_cost: float,
                      start_date: str, end_date: str, notes: str, created_by: str) -> int:
    """Create a consignment agreement. Raises ValueError for a non-positive
    unit_cost, a missing product, or end_date before start_date."""
    unit_cost = float(unit_cost or 0)
    if unit_cost <= 0:
        raise ValueError("Unit cost must be greater than zero.")
    if not product_id:
        raise ValueError("Select a product.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("End date cannot be before start date.")
    product = conn.execute("SELECT id FROM product WHERE id = %s", (product_id,)).fetchone()
    if not product:
        raise ValueError("Product not found.")

    agreement_number = next_agreement_number(conn)
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO consignment_agreement "
        "(agreement_number, supplier_id, product_id, unit_cost, start_date, end_date, "
        "status, notes, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (agreement_number, supplier_id or None, product_id, unit_cost,
         start_date or '', end_date or '', 'active', notes or '', created_by or '', now),
    ).fetchone()
    return row['id']


def receive_stock(conn, agreement_id: int, qty: float, reference: str, created_by: str) -> int:
    """Record vendor-owned stock arriving. Does not touch product.amount —
    it isn't ours yet. Raises ValueError for a non-positive qty, a missing
    agreement, or a cancelled agreement."""
    agreement = get_agreement(conn, agreement_id)
    if not agreement:
        raise ValueError("Consignment agreement not found.")
    if agreement['status'] == 'cancelled':
        raise ValueError("Agreement is cancelled — cannot receive stock.")
    qty = float(qty or 0)
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")

    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO consignment_receipt (agreement_id, qty, reference, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (agreement_id, qty, reference or '', created_by or '', now),
    ).fetchone()
    return row['id']


def record_usage(conn, agreement_id: int, qty: float, reference: str, created_by: str) -> dict:
    """Consume vendor-owned stock: transfers ownership (credits
    product.amount via inventory_core.record_transaction), bills the vendor
    (opens an AP invoice for qty * unit_cost), and logs the usage. Raises
    ValueError for a non-positive qty, a missing agreement, a cancelled
    agreement, or a qty exceeding the on-hand vendor-owned balance."""
    agreement = get_agreement(conn, agreement_id)
    if not agreement:
        raise ValueError("Consignment agreement not found.")
    if agreement['status'] == 'cancelled':
        raise ValueError("Agreement is cancelled — cannot record usage.")
    qty = float(qty or 0)
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if qty > agreement['on_hand_qty']:
        raise ValueError(
            f"Usage qty {qty:g} exceeds the on-hand consigned balance "
            f"{agreement['on_hand_qty']:g}.")

    unit_cost = float(agreement['unit_cost'] or 0.0)
    new_amount = record_transaction(
        conn, agreement['product_id'], 'receive', qty,
        reference=reference, notes=f"Consignment usage — {agreement['agreement_number']}",
        created_by=created_by,
    )

    invoice_number = f"{agreement['agreement_number']}-U{len(list_usages(conn, agreement_id)) + 1:03d}"
    today = date.today()
    ap_invoice_id = create_ap_invoice(
        conn, vendor_id=agreement['supplier_id'], invoice_number=invoice_number,
        invoice_date=today.isoformat(), due_date=(today + timedelta(days=30)).isoformat(),
        amount=qty * unit_cost,
        description=f"Consignment usage — {agreement['agreement_number']} "
                    f"({agreement['product_name']}, qty {qty:g})",
        created_by=created_by,
    )

    now = datetime.now().isoformat()
    usage_row = conn.execute(
        "INSERT INTO consignment_usage "
        "(agreement_id, qty, unit_cost, ap_invoice_id, reference, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (agreement_id, qty, unit_cost, ap_invoice_id, reference or '', created_by or '', now),
    ).fetchone()

    return {
        'usage_id': usage_row['id'],
        'new_product_amount': new_amount,
        'ap_invoice_id': ap_invoice_id,
        'total_cost': qty * unit_cost,
    }


def cancel_agreement(conn, agreement_id: int) -> None:
    """Cancel a consignment agreement. Raises ValueError unless it is
    currently active. Does not zero out or return any on-hand balance —
    physically returning unused vendor stock is a real-world step outside
    this system's scope, same as blanket_po_core.cancel_blanket_po."""
    agreement = get_agreement(conn, agreement_id)
    if not agreement:
        raise ValueError("Consignment agreement not found.")
    if agreement['status'] != 'active':
        raise ValueError(f"Agreement is already {agreement['status']}.")
    conn.execute(
        "UPDATE consignment_agreement SET status = %s WHERE id = %s",
        ('cancelled', agreement_id),
    )
