"""
supplier_portal_core.py — Qt-free Supplier Self-Service Portal, 6/10 of
the top-10 ERPs have it.

Same shape as ``customer_portal_core.py`` (P3-C): a separate, non-employee
login layered on top of the existing ``supplier`` master file rather than a
parallel signup system — ``supplier_login`` (new) holds one bcrypt-hashed
credential per ``supplier.id``, matched at registration time against that
supplier's own ``email`` column (case-insensitive). Session/auth wiring
lives in ``auth_decorators.supplier_login_required`` and
``views/_supplier_portal.py``, in a session namespace (``portal_supplier_id``
etc.) kept deliberately separate from both the employee ``user_*`` keys and
the customer portal's ``portal_customer_id`` keys — a person could
conceivably be logged into more than one portal type on the same browser
without them colliding, though that's an edge case this app has no reason
to actually support.

Everything else is read/write through existing core modules, never forked:
  purchase orders — purchase_orders_core.list_pos/get_po/get_po_items
                    (supplier_id is already a first-class filter there)
  AP invoices     — accounting_core.list_ap_invoices/get_ap_invoice/
                    create_ap_invoice (vendor_id *is* supplier_id — the
                    ap_invoice table's column is just named differently;
                    already computes outstanding balance via the
                    ap_payment LEFT JOIN)
  RFQs            — rfq_core.list_rfq_items/enter_quote (rfq_vendor already
                    models which suppliers are invited to which RFQ; a
                    supplier submitting a quote through the portal calls
                    the exact same enter_quote() an internal buyer would
                    use when keying in a phoned-in quote)
This module only adds supplier-scoped read/ownership-check helpers plus
what's genuinely new: portal login, PO acknowledgement (new columns on
``purchase_order``, since nothing tracked "did the supplier confirm this
order" before), and self-service AP invoice submission.

Every function takes an open connection; the caller owns the transaction
(same convention as customer_portal_core / wms_core).
"""

from __future__ import annotations

from datetime import datetime

import bcrypt

from .purchase_orders_core import list_pos, get_po
from .accounting_core import list_ap_invoices, get_ap_invoice, create_ap_invoice
from .rfq_core import list_rfq_items, get_rfq, enter_quote, get_quote


def ensure_supplier_portal_tables(conn) -> None:
    """Create supplier_login and add PO-acknowledgement columns if absent.
    Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supplier_login (
            id            SERIAL PRIMARY KEY,
            supplier_id   INTEGER NOT NULL UNIQUE,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "ALTER TABLE purchase_order ADD COLUMN IF NOT EXISTS "
        "supplier_acknowledged_at TEXT"
    )
    conn.execute(
        "ALTER TABLE purchase_order ADD COLUMN IF NOT EXISTS "
        "supplier_ack_notes TEXT NOT NULL DEFAULT ''"
    )


# ---------------------------------------------------------------------------
# Portal login
# ---------------------------------------------------------------------------

def find_supplier_by_email(conn, email: str) -> dict | None:
    """Case-insensitive lookup of an existing supplier master record."""
    row = conn.execute(
        "SELECT id, first_name, last_name, company_name, email "
        "FROM supplier WHERE LOWER(email) = LOWER(%s)",
        (email.strip(),),
    ).fetchone()
    return dict(row) if row else None


def has_portal_login(conn, supplier_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM supplier_login WHERE supplier_id = %s", (supplier_id,)
    ).fetchone()
    return row is not None


def register_supplier_login(conn, email: str, password: str) -> int:
    """Create portal access for an existing supplier. Returns supplier_id.

    Raises ValueError if no matching supplier record exists, or if that
    supplier already has portal access.
    """
    if not email or not password:
        raise ValueError("Email and password are required.")
    supplier = find_supplier_by_email(conn, email)
    if not supplier:
        raise ValueError(
            "No supplier account found with that email. Contact your buyer.")
    if has_portal_login(conn, supplier["id"]):
        raise ValueError("Portal access already exists for this account. Please log in.")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO supplier_login (supplier_id, email, password_hash, created_at) "
        "VALUES (%s,%s,%s,%s)",
        (supplier["id"], email.strip(), password_hash, datetime.now().isoformat()),
    )
    return supplier["id"]


def verify_supplier_login(conn, email: str, password: str) -> dict | None:
    """Return the portal profile dict on success, else None."""
    row = conn.execute("""
        SELECT sl.supplier_id, sl.password_hash,
               s.email, s.company_name, s.first_name, s.last_name
        FROM supplier_login sl
        JOIN supplier s ON s.id = sl.supplier_id
        WHERE LOWER(sl.email) = LOWER(%s)
    """, (email.strip(),)).fetchone()
    if not row:
        return None
    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return None
    return get_portal_profile(conn, row["supplier_id"])


def get_portal_profile(conn, supplier_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id AS supplier_id, company_name, first_name, last_name, email "
        "FROM supplier WHERE id = %s",
        (supplier_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    company = d["company_name"] or ""
    name = f"{d['first_name'] or ''} {d['last_name'] or ''}".strip()
    d["display_name"] = company if company else (name or d["email"])
    return d


# ---------------------------------------------------------------------------
# Purchase Orders (supplier-scoped, reusing purchase_orders_core)
# ---------------------------------------------------------------------------

def list_my_pos(conn, supplier_id: int) -> list:
    return list_pos(conn, supplier_id=supplier_id)


def get_my_po(conn, supplier_id: int, po_id: int) -> dict | None:
    po = get_po(conn, po_id)
    if not po or po["supplier_id"] != supplier_id:
        return None
    return po


def acknowledge_po(conn, supplier_id: int, po_id: int, notes: str = '') -> None:
    """Record that the supplier has confirmed a PO. Raises if the PO
    doesn't belong to this supplier."""
    po = get_my_po(conn, supplier_id, po_id)
    if not po:
        raise ValueError("That purchase order does not belong to your account.")
    conn.execute(
        "UPDATE purchase_order SET supplier_acknowledged_at = %s, "
        "supplier_ack_notes = %s WHERE id = %s",
        (datetime.now().isoformat(), notes or '', po_id),
    )


# ---------------------------------------------------------------------------
# AP Invoices (supplier-scoped, reusing accounting_core)
# ---------------------------------------------------------------------------

def list_my_invoices(conn, supplier_id: int) -> list:
    return list_ap_invoices(conn, vendor_id=supplier_id)


def get_my_invoice(conn, supplier_id: int, inv_id: int) -> dict | None:
    invoice = get_ap_invoice(conn, inv_id)
    if not invoice or invoice["vendor_id"] != supplier_id:
        return None
    return invoice


def submit_invoice(conn, supplier_id: int, po_id, invoice_number: str,
                   invoice_date: str, due_date: str, amount: float,
                   description: str, created_by: str) -> int:
    """Submit an AP invoice against one of the caller's own purchase
    orders (or with no PO reference at all — po_id is optional, same as
    the internal AP invoice form). Raises if a po_id is given that
    doesn't belong to this supplier."""
    if po_id:
        po = get_my_po(conn, supplier_id, int(po_id))
        if not po:
            raise ValueError("That purchase order does not belong to your account.")
    if not due_date:
        raise ValueError("Due date is required.")
    return create_ap_invoice(
        conn, supplier_id, invoice_number, invoice_date, due_date,
        amount, description, created_by,
    )


# ---------------------------------------------------------------------------
# RFQs (supplier-scoped, reusing rfq_core)
# ---------------------------------------------------------------------------

def list_my_rfqs(conn, supplier_id: int) -> list:
    """RFQs this supplier has been invited to quote on, newest first."""
    rows = conn.execute("""
        SELECT r.* FROM rfq r
        JOIN rfq_vendor rv ON rv.rfq_id = r.id
        WHERE rv.supplier_id = %s
        ORDER BY r.created_at DESC
    """, (supplier_id,)).fetchall()
    return [dict(r) for r in rows]


def _is_invited(conn, supplier_id: int, rfq_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM rfq_vendor WHERE rfq_id = %s AND supplier_id = %s",
        (rfq_id, supplier_id),
    ).fetchone()
    return row is not None


def get_my_rfq(conn, supplier_id: int, rfq_id: int) -> dict | None:
    """One RFQ this supplier is invited to, with its items and this
    supplier's own existing quotes (if any) merged in. Returns None if
    the supplier was never invited to this RFQ."""
    if not _is_invited(conn, supplier_id, rfq_id):
        return None
    rfq = get_rfq(conn, rfq_id)
    if not rfq:
        return None
    items = list_rfq_items(conn, rfq_id)
    for item in items:
        quote = get_quote(conn, item["id"], supplier_id)
        item["my_quoted_price"] = quote["quoted_price"] if quote else None
        item["my_lead_time_days"] = quote["lead_time_days"] if quote else None
    rfq["items"] = items
    return rfq


def submit_quote(conn, supplier_id: int, rfq_item_id: int,
                 quoted_price: float, lead_time_days=None) -> None:
    """Enter this supplier's own quote for one RFQ line. Raises if the
    line doesn't exist or this supplier was never invited to its RFQ."""
    item = conn.execute(
        "SELECT rfq_id FROM rfq_item WHERE id = %s", (rfq_item_id,)
    ).fetchone()
    if not item:
        raise ValueError(f"No RFQ item with id {rfq_item_id}")
    if not _is_invited(conn, supplier_id, item["rfq_id"]):
        raise ValueError("You were not invited to quote on this RFQ.")
    enter_quote(conn, rfq_item_id, supplier_id, quoted_price, lead_time_days)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_portal_dashboard(conn, supplier_id: int) -> dict:
    """{'open_po_count', 'unacknowledged_po_count', 'open_invoice_count',
    'open_invoice_balance', 'open_rfq_count'}."""
    pos = list_my_pos(conn, supplier_id)
    open_pos = [p for p in pos if p["status"] not in ("received", "cancelled")]
    unacked = [p for p in open_pos if not p.get("supplier_acknowledged_at")]
    invoices = list_my_invoices(conn, supplier_id)
    open_invoices = [i for i in invoices if i["status"] in ("open", "partial", "overdue")]
    rfqs = list_my_rfqs(conn, supplier_id)
    open_rfqs = [r for r in rfqs if r["status"] == "open"]
    return {
        "open_po_count": len(open_pos),
        "unacknowledged_po_count": len(unacked),
        "open_invoice_count": len(open_invoices),
        "open_invoice_balance": sum(i["balance"] for i in open_invoices),
        "open_rfq_count": len(open_rfqs),
    }
