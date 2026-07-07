"""
customer_portal_core.py — Qt-free Customer Self-Service Portal (P3-C).

A separate, non-employee login layered on top of the existing ``customer``
master file rather than a parallel signup system: ``customer_login`` (new)
holds one bcrypt-hashed credential per ``customer.id``, matched at
registration time against that customer's own ``email`` column (case-
insensitive) — there is no blind account creation. Session/auth wiring lives
in ``auth_decorators.customer_login_required`` and ``views/_portal.py``, in
a session namespace (``portal_customer_id`` etc.) kept deliberately separate
from the employee ``user_*`` keys.

Everything else is read/write through existing core modules, never forked:
  orders     — sales_orders_core.list_sos/get_so/get_so_items (customer_id
               is already a first-class filter there)
  invoices   — accounting_core.list_ar_invoices/get_ar_invoice (already
               compute outstanding balance via the ar_payment LEFT JOIN)
  payments   — accounting_core.record_ar_payment (already recomputes invoice
               status from total received)
This module only adds customer-scoped read helpers for the two tables that
don't carry a direct customer_id column (shipment, rma — both reached via
sales_order.customer_id) plus what's genuinely new: portal login, PDF
rendering, and stubbed carrier-tracking / payment-intent gateways.

Stubbed, not wired to a real network call: no Stripe/carrier SDK or outbound
HTTP precedent exists anywhere in this codebase (checked). ``get_tracking_events``
returns a deterministic synthetic timeline derived from the shipment's own
carrier/status/ship_date, and create_payment_intent/confirm_payment_intent
model the Stripe PaymentIntent create->confirm shape without a network call.
Swapping in a real integration means replacing the bodies of those functions
only — every caller-facing shape (return dicts, table columns) already
matches what a real integration would need to populate.

Every function takes an open connection; the caller owns the transaction
(same convention as wms_core / capacity_planning_core).
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime, timedelta

import bcrypt

from .production_core import create_rma, RMA_REASONS
from .sales_orders_core import get_so
from .accounting_core import record_ar_payment
from .log_utils import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_portal_tables(conn) -> None:
    """Create portal-specific tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_login (
            id            SERIAL PRIMARY KEY,
            customer_id   INTEGER NOT NULL UNIQUE,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_payment_intent (
            id               SERIAL PRIMARY KEY,
            invoice_id       INTEGER NOT NULL,
            amount           REAL NOT NULL,
            status           TEXT DEFAULT 'requires_confirmation',
            stripe_intent_id TEXT NOT NULL,
            created_at       TEXT DEFAULT ''
        )
    """)


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Portal login
# ---------------------------------------------------------------------------

def find_customer_by_email(conn, email: str) -> dict | None:
    """Case-insensitive lookup of an existing customer master record."""
    row = conn.execute(
        "SELECT id, first_name, last_name, company_name, email "
        "FROM customer WHERE LOWER(email) = LOWER(%s)",
        (email.strip(),),
    ).fetchone()
    return dict(row) if row else None


def has_portal_login(conn, customer_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM customer_login WHERE customer_id = %s", (customer_id,)
    ).fetchone()
    return row is not None


def register_customer_login(conn, email: str, password: str) -> int:
    """Create portal access for an existing customer. Returns customer_id.

    Raises ValueError if no matching customer record exists, or if that
    customer already has portal access.
    """
    if not email or not password:
        raise ValueError("Email and password are required.")
    customer = find_customer_by_email(conn, email)
    if not customer:
        raise ValueError(
            "No customer account found with that email. Contact your sales rep.")
    if has_portal_login(conn, customer["id"]):
        raise ValueError("Portal access already exists for this account. Please log in.")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO customer_login (customer_id, email, password_hash, created_at) "
        "VALUES (%s,%s,%s,%s)",
        (customer["id"], email.strip(), password_hash, datetime.now().isoformat()),
    )
    return customer["id"]


def verify_customer_login(conn, email: str, password: str) -> dict | None:
    """Return the portal profile dict on success, else None."""
    row = conn.execute("""
        SELECT cl.customer_id, cl.password_hash,
               c.email, c.company_name, c.first_name, c.last_name
        FROM customer_login cl
        JOIN customer c ON c.id = cl.customer_id
        WHERE LOWER(cl.email) = LOWER(%s)
    """, (email.strip(),)).fetchone()
    if not row:
        return None
    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return None
    return get_portal_profile(conn, row["customer_id"])


def get_portal_profile(conn, customer_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id AS customer_id, company_name, first_name, last_name, email "
        "FROM customer WHERE id = %s",
        (customer_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    company = d["company_name"] or ""
    name = f"{d['first_name'] or ''} {d['last_name'] or ''}".strip()
    d["display_name"] = company if company else (name or d["email"])
    return d


# ---------------------------------------------------------------------------
# Shipments (customer-scoped — shipment has no direct customer_id column)
# ---------------------------------------------------------------------------

def list_my_shipments(conn, customer_id: int) -> list:
    return [dict(r) for r in conn.execute("""
        SELECT s.id, s.ship_number, s.ship_date, s.carrier,
               s.tracking_number, s.status, so.so_number, so.id AS so_id
        FROM shipment s
        JOIN sales_order so ON so.id = s.so_id
        WHERE so.customer_id = %s
        ORDER BY s.id DESC
    """, (customer_id,)).fetchall()]


def get_my_shipment(conn, customer_id: int, shipment_id: int) -> dict | None:
    row = conn.execute("""
        SELECT s.*, so.so_number, so.id AS so_id
        FROM shipment s
        JOIN sales_order so ON so.id = s.so_id
        WHERE s.id = %s AND so.customer_id = %s
    """, (shipment_id, customer_id)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# RMA (customer-scoped — rma has no direct customer_id column either)
# ---------------------------------------------------------------------------

def list_my_rmas(conn, customer_id: int) -> list:
    return [dict(r) for r in conn.execute("""
        SELECT r.id, r.rma_number, r.reason, r.status, r.description,
               r.resolution, r.created_at, so.so_number, so.id AS so_id
        FROM rma r
        JOIN sales_order so ON so.id = r.so_id
        WHERE so.customer_id = %s
        ORDER BY r.id DESC
    """, (customer_id,)).fetchall()]


def get_my_rma(conn, customer_id: int, rma_id: int) -> dict | None:
    row = conn.execute("""
        SELECT r.*, so.so_number, so.id AS so_id
        FROM rma r
        JOIN sales_order so ON so.id = r.so_id
        WHERE r.id = %s AND so.customer_id = %s
    """, (rma_id, customer_id)).fetchone()
    return dict(row) if row else None


def submit_rma(conn, customer_id: int, so_id: int, reason: str,
               description: str, created_by: str) -> int:
    """Create an RMA against one of the caller's own sales orders."""
    so = get_so(conn, so_id)
    if not so or so["customer_id"] != customer_id:
        raise ValueError("That sales order does not belong to your account.")
    if reason not in RMA_REASONS:
        reason = "other"
    profile = get_portal_profile(conn, customer_id)
    customer_label = profile["display_name"] if profile else ""
    return create_rma(conn, so_id, customer_label, reason, description, created_by)


# ---------------------------------------------------------------------------
# Carrier tracking (stub — see module docstring)
# ---------------------------------------------------------------------------

def get_tracking_events(shipment: dict) -> list:
    """Return a synthetic tracking timeline derived from the shipment's own
    carrier/status/ship_date. Deterministic (no randomness, no network call)
    so it's stable across repeated views and safe to unit test.

    This is the seam for a real carrier API (e.g. EasyPost/UPS/FedEx) lookup
    by tracking_number — replace this function's body only.
    """
    status = shipment.get("status") or "pending"
    carrier = shipment.get("carrier") or "Carrier"
    try:
        ship_date = datetime.strptime(shipment["ship_date"], "%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        ship_date = None

    def _d(offset):
        return (ship_date + timedelta(days=offset)).date().isoformat() if ship_date else None

    events = [{"date": _d(0), "label": "Shipping Label Created", "done": True}]
    if status == "cancelled":
        events.append({"date": _d(0), "label": "Shipment Cancelled", "done": True})
        return events

    events.append({
        "date": _d(0), "label": f"Picked up by {carrier}",
        "done": status in ("in_transit", "delivered"),
    })
    events.append({
        "date": _d(1), "label": "In Transit",
        "done": status in ("in_transit", "delivered"),
    })
    events.append({
        "date": _d(2), "label": "Out for Delivery",
        "done": status == "delivered",
    })
    events.append({
        "date": _d(3), "label": "Delivered",
        "done": status == "delivered",
    })
    return events


# ---------------------------------------------------------------------------
# Payments (stub Stripe PaymentIntent shape — see module docstring)
# ---------------------------------------------------------------------------

def create_payment_intent(conn, invoice_id: int, amount: float) -> dict:
    """Create a payment intent for an invoice. Returns the intent dict.

    Seam for a real ``stripe.PaymentIntent.create`` call — the persisted
    shape (invoice_id, amount, status, stripe_intent_id) already matches
    what that call would need to record.
    """
    stripe_intent_id = f"pi_stub_{uuid.uuid4().hex[:24]}"
    row = conn.execute(
        "INSERT INTO portal_payment_intent "
        "(invoice_id, amount, status, stripe_intent_id, created_at) "
        "VALUES (%s,%s,'requires_confirmation',%s,%s) RETURNING id",
        (invoice_id, float(amount), stripe_intent_id, datetime.now().isoformat()),
    ).fetchone()
    return {
        "id": row["id"], "invoice_id": invoice_id, "amount": float(amount),
        "status": "requires_confirmation", "stripe_intent_id": stripe_intent_id,
    }


def confirm_payment_intent(conn, intent_id: int) -> dict:
    """Confirm a payment intent: records the ar_payment and marks the
    invoice status (via accounting_core.record_ar_payment), then marks the
    intent succeeded. Raises ValueError if the intent is unknown or already
    confirmed.
    """
    intent = conn.execute(
        "SELECT * FROM portal_payment_intent WHERE id = %s", (intent_id,)
    ).fetchone()
    if not intent:
        raise ValueError("Unknown payment intent.")
    if intent["status"] == "succeeded":
        raise ValueError("Payment already confirmed.")
    record_ar_payment(
        conn, intent["invoice_id"], _today(), intent["amount"],
        "Credit Card", intent["stripe_intent_id"], "Paid via customer portal",
    )
    conn.execute(
        "UPDATE portal_payment_intent SET status='succeeded' WHERE id = %s",
        (intent_id,),
    )
    return dict(intent) | {"status": "succeeded"}


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

def render_invoice_pdf(invoice: dict, payments: list) -> bytes:
    """Render a customer-facing invoice PDF (header + payment history)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                             topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Invoice {invoice['invoice_number']}", styles["Heading1"]),
        Spacer(1, 0.15 * inch),
        Paragraph(f"Bill To: {invoice.get('customer_label', '')}", styles["Normal"]),
        Paragraph(f"Invoice Date: {invoice.get('invoice_date') or ''}", styles["Normal"]),
        Paragraph(f"Due Date: {invoice.get('due_date') or ''}", styles["Normal"]),
        Paragraph(f"Status: {invoice.get('status', '')}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
    ]
    if invoice.get("description"):
        story.append(Paragraph(invoice["description"], styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    totals = [
        ["Invoice Amount", f"${invoice['amount']:.2f}"],
        ["Received", f"${(invoice['amount'] - invoice.get('balance', 0)):.2f}"],
        ["Balance Due", f"${invoice.get('balance', invoice['amount']):.2f}"],
    ]
    t = Table(totals, colWidths=[3 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(t)

    if payments:
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph("Payment History", styles["Heading3"]))
        rows = [["Date", "Method", "Amount", "Reference"]]
        for p in payments:
            rows.append([p.get("payment_date", ""), p.get("payment_method", ""),
                         f"${p.get('amount', 0):.2f}", p.get("reference", "")])
        pt = Table(rows, colWidths=[1.2 * inch, 1.3 * inch, 1 * inch, 2 * inch])
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1dae8")),
        ]))
        story.append(pt)

    doc.build(story)
    buf.seek(0)
    return buf.read()


def render_packing_slip_pdf(shipment: dict, items: list) -> bytes:
    """Render a customer-facing packing slip PDF for a shipment."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                             topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Packing Slip — {shipment['ship_number']}", styles["Heading1"]),
        Spacer(1, 0.15 * inch),
        Paragraph(f"Sales Order: {shipment.get('so_number') or ''}", styles["Normal"]),
        Paragraph(f"Ship Date: {shipment.get('ship_date') or ''}", styles["Normal"]),
        Paragraph(f"Carrier: {shipment.get('carrier') or ''}", styles["Normal"]),
        Paragraph(f"Tracking #: {shipment.get('tracking_number') or ''}", styles["Normal"]),
        Spacer(1, 0.25 * inch),
    ]
    rows = [["Description", "Qty"]]
    for it in items:
        rows.append([it.get("description", ""), str(it.get("qty", ""))])
    t = Table(rows, colWidths=[4.5 * inch, 1 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1dae8")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(t)

    doc.build(story)
    buf.seek(0)
    return buf.read()
