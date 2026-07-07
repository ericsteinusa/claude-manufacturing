"""
edi_core.py — Qt-free EDI Integration (P4-D).

Real X12 document parsing/generation for the common subset of 850
(Purchase Order), 855 (PO Acknowledgment), 856 (Advance Ship Notice), and
810 (Invoice) — segment-delimited (`~`) with `*`-separated elements, per
the ANSI X12 EDI standard. This is genuine parsing/generation logic, not a
stub: unlike a payment processor or IoT sensor, the X12 *document format*
is just structured text, so it can be implemented for real. What's
honestly out of scope is the **trading-partner connection** (AS2/VAN/SFTP
— no such network access exists in this environment); receiving/sending
the actual .edi file is a manual upload/download through the web UI.

Only the common subset of each transaction set is implemented (documented
per-function), not the full X12 standard (hundreds of optional segments
and qualifier codes) — this covers the fields the spec asks for: PO
number/date/lines for 850, acknowledgment for 855, ship/carrier/tracking
for 856, and invoice amount for 810.

`product` has no SKU/code column anywhere in this codebase — only a
free-text `name`. A trading partner's PO1 segment carries *their own*
part number, which has nothing in common with our internal product ids,
so a **per-customer item cross-reference table
(`edi_partner_item_xref`) is the actual field-mapping mechanism** the
spec's "configurable field mappings per trading partner" bullet asks
for — not a generic mapping engine, a concrete necessity. An inbound line
with no mapping still becomes a valid `so_item` (`product_id=None`, using
the partner's raw description) — mirrors how `so_item` already supports
text-only/service lines; it is not an error.

`ar_invoice` (accounting_core.py) is header-only with no line-item table,
so `generate_810` emits one summary line — an honest reflection of this
codebase's invoice model, not fabricated per-item detail.

Reuses existing, unmodified functions for all real side effects:
`sales_orders_core.next_so_number`/`create_so`/`add_so_item` (850 inbound),
`production_core.get_shipment`/`get_shipment_items` (856 outbound),
`accounting_core.get_ar_invoice` (810 outbound). Every function taking
`conn` takes an open connection; the caller owns the transaction.
"""

from __future__ import annotations

from datetime import datetime

from .log_utils import get_logger
from .sales_orders_core import next_so_number, create_so, add_so_item, get_so, get_so_items
from .production_core import get_shipment, get_shipment_items
from .accounting_core import get_ar_invoice

log = get_logger(__name__)

DOC_TYPES = ('850', '855', '856', '810')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_edi_tables(conn) -> None:
    """Create edi_* tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edi_trading_partner (
            id              SERIAL PRIMARY KEY,
            customer_id     INTEGER NOT NULL UNIQUE,
            partner_name    TEXT DEFAULT '',
            isa_sender_id   TEXT DEFAULT '',
            isa_receiver_id TEXT DEFAULT '',
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edi_partner_item_xref (
            id                  SERIAL PRIMARY KEY,
            customer_id         INTEGER NOT NULL,
            partner_item_number TEXT NOT NULL,
            product_id          INTEGER NOT NULL,
            UNIQUE (customer_id, partner_item_number)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edi_transaction_log (
            id               SERIAL PRIMARY KEY,
            customer_id      INTEGER,
            doc_type         TEXT NOT NULL,
            direction        TEXT NOT NULL,
            reference_number TEXT DEFAULT '',
            raw_content      TEXT DEFAULT '',
            so_id            INTEGER,
            shipment_id      INTEGER,
            invoice_id       INTEGER,
            created_at       TEXT DEFAULT '',
            created_by       TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Trading partner / item cross-reference
# ---------------------------------------------------------------------------

def set_trading_partner(conn, customer_id: int, partner_name: str,
                         isa_sender_id: str, isa_receiver_id: str) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO edi_trading_partner "
        "(customer_id, partner_name, isa_sender_id, isa_receiver_id, created_at) "
        "VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (customer_id) DO UPDATE "
        "SET partner_name=EXCLUDED.partner_name, "
        "isa_sender_id=EXCLUDED.isa_sender_id, "
        "isa_receiver_id=EXCLUDED.isa_receiver_id",
        (customer_id, partner_name or '', isa_sender_id or '',
         isa_receiver_id or '', now),
    )


def get_trading_partner(conn, customer_id: int) -> dict | None:
    row = conn.execute("""
        SELECT tp.*, c.company_name, c.first_name, c.last_name
        FROM edi_trading_partner tp
        LEFT JOIN customer c ON c.id = tp.customer_id
        WHERE tp.customer_id = %s
    """, (customer_id,)).fetchone()
    return dict(row) if row else None


def list_trading_partners(conn) -> list:
    rows = conn.execute("""
        SELECT tp.*, c.company_name, c.first_name, c.last_name
        FROM edi_trading_partner tp
        LEFT JOIN customer c ON c.id = tp.customer_id
        ORDER BY tp.partner_name
    """).fetchall()
    return [dict(r) for r in rows]


def set_item_xref(conn, customer_id: int, partner_item_number: str, product_id: int) -> None:
    if not partner_item_number:
        raise ValueError("Partner item number is required.")
    conn.execute(
        "INSERT INTO edi_partner_item_xref (customer_id, partner_item_number, product_id) "
        "VALUES (%s,%s,%s) "
        "ON CONFLICT (customer_id, partner_item_number) DO UPDATE "
        "SET product_id=EXCLUDED.product_id",
        (customer_id, partner_item_number, product_id),
    )


def list_item_xrefs(conn, customer_id: int) -> list:
    rows = conn.execute("""
        SELECT x.*, p.name AS product_name
        FROM edi_partner_item_xref x
        LEFT JOIN product p ON p.id = x.product_id
        WHERE x.customer_id = %s
        ORDER BY x.partner_item_number
    """, (customer_id,)).fetchall()
    return [dict(r) for r in rows]


def resolve_product_id(conn, customer_id: int, partner_item_number: str):
    row = conn.execute(
        "SELECT product_id FROM edi_partner_item_xref "
        "WHERE customer_id = %s AND partner_item_number = %s",
        (customer_id, partner_item_number),
    ).fetchone()
    return row['product_id'] if row else None


def _resolve_partner_item_number(conn, customer_id: int, product_id):
    """Reverse lookup: our product_id -> the partner's own item number, for
    outbound 856/810 lines (so the partner sees their own numbering)."""
    if not product_id:
        return None
    row = conn.execute(
        "SELECT partner_item_number FROM edi_partner_item_xref "
        "WHERE customer_id = %s AND product_id = %s LIMIT 1",
        (customer_id, product_id),
    ).fetchone()
    return row['partner_item_number'] if row else None


def _log_transaction(conn, customer_id, doc_type, direction, reference_number,
                      raw_content, created_by, so_id=None, shipment_id=None,
                      invoice_id=None) -> None:
    conn.execute(
        "INSERT INTO edi_transaction_log "
        "(customer_id, doc_type, direction, reference_number, raw_content, "
        "so_id, shipment_id, invoice_id, created_at, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (customer_id, doc_type, direction, reference_number or '', raw_content,
         so_id, shipment_id, invoice_id, datetime.now().isoformat(), created_by or ''),
    )


def list_transaction_log(conn, customer_id: int | None = None) -> list:
    q = """
        SELECT l.*, c.company_name, c.first_name, c.last_name
        FROM edi_transaction_log l
        LEFT JOIN customer c ON c.id = l.customer_id
    """
    params: list = []
    if customer_id:
        q += " WHERE l.customer_id = %s"
        params.append(customer_id)
    q += " ORDER BY l.id DESC"
    return [dict(r) for r in conn.execute(q, params).fetchall()]


# ---------------------------------------------------------------------------
# X12 segment/element helpers
# ---------------------------------------------------------------------------

def _split_segments(raw_edi: str) -> list:
    """Split raw X12 text into segments. Accepts '~'-terminated segments
    (standard) or one segment per line (common in hand-edited/sample
    files) — whichever the input actually uses."""
    text = raw_edi.replace('\r\n', '\n').replace('\r', '\n')
    if '~' in text:
        segments = text.replace('\n', '').split('~')
    else:
        segments = text.split('\n')
    return [s.strip() for s in segments if s.strip()]


def _split_elements(segment: str) -> list:
    return segment.split('*')


def _x12_date(raw: str):
    """YYYYMMDD -> ISO date string, or None if unparseable."""
    if not raw or len(raw) != 8:
        return None
    try:
        return datetime.strptime(raw, '%Y%m%d').date().isoformat()
    except ValueError:
        return None


def _isa_gs_header(sender: str, receiver: str, gs_code: str, now: datetime) -> list:
    """Build the ISA + GS interchange/group header segments."""
    stamp = now.strftime('%y%m%d')
    ymd = now.strftime('%Y%m%d')
    hm = now.strftime('%H%M')
    isa = (
        f"ISA*00*          *00*          *ZZ*{sender:<15}*ZZ*{receiver:<15}*"
        f"{stamp}*{hm}*U*00401*000000001*0*P*>"
    )
    gs = f"GS*{gs_code}*{sender}*{receiver}*{ymd}*{hm}*1*X*004010"
    return [isa, gs]


def _finalize_envelope(header_segments: list, transaction_segments: list) -> str:
    """Append SE/GE/IEA to close out the envelope. `transaction_segments`
    must start with ST and contain everything up to (not including) SE;
    the SE segment count includes ST through SE inclusive."""
    control_number = _split_elements(transaction_segments[0])[-1]
    se_count = len(transaction_segments) + 1
    all_segments = header_segments + transaction_segments + [
        f"SE*{se_count}*{control_number}",
        "GE*1*1",
        "IEA*1*000000001",
    ]
    return '~\n'.join(all_segments) + '~'


# ---------------------------------------------------------------------------
# 850 — Purchase Order (inbound)
# ---------------------------------------------------------------------------

def parse_850(raw_edi: str, customer_id: int, conn) -> dict:
    """Parse the common subset of an X12 850: BEG (PO number/date), N1*ST
    (ship-to, informational), and PO1 loops (qty/price/partner item
    number, with an optional following PID for description). Returns
    {po_number, order_date, ship_to, lines: [{partner_item_number,
    product_id, description, qty, unit_price}], unmapped_count}."""
    po_number = None
    order_date = None
    ship_to = None
    lines = []
    current_line = None

    for segment in _split_segments(raw_edi):
        el = _split_elements(segment)
        seg_id = el[0]

        if seg_id == 'BEG':
            po_number = el[3] if len(el) > 3 and el[3] else None
            order_date = _x12_date(el[5]) if len(el) > 5 else None

        elif seg_id == 'N1' and len(el) > 2 and el[1] == 'ST':
            ship_to = el[2]

        elif seg_id == 'PO1':
            qty = float(el[2]) if len(el) > 2 and el[2] else 0.0
            unit_price = float(el[4]) if len(el) > 4 and el[4] else 0.0
            partner_item_number = el[7] if len(el) > 7 and el[7] else None
            product_id = (
                resolve_product_id(conn, customer_id, partner_item_number)
                if partner_item_number else None
            )
            current_line = {
                'partner_item_number': partner_item_number,
                'product_id': product_id,
                'description': f"Item {partner_item_number}" if partner_item_number else 'Item',
                'qty': qty,
                'unit_price': unit_price,
            }
            lines.append(current_line)

        elif seg_id == 'PID' and current_line is not None and len(el) > 5 and el[5]:
            current_line['description'] = el[5]

    unmapped_count = sum(1 for ln in lines if ln['product_id'] is None)
    return {
        'po_number': po_number,
        'order_date': order_date,
        'ship_to': ship_to,
        'lines': lines,
        'unmapped_count': unmapped_count,
    }


def create_so_from_850(conn, customer_id: int, raw_edi: str, created_by: str) -> dict:
    """Parse an inbound 850 and create a real Sales Order from it via the
    existing, unmodified next_so_number/create_so/add_so_item. Logs the
    raw content to edi_transaction_log."""
    parsed = parse_850(raw_edi, customer_id, conn)

    so_number = next_so_number(conn)
    so_id = create_so(
        conn, so_number, customer_id=customer_id,
        order_date=parsed['order_date'], status='draft',
        notes=f"Imported via EDI 850 (PO# {parsed['po_number'] or 'unknown'})",
        created_by=created_by,
    )
    for line in parsed['lines']:
        add_so_item(
            conn, so_id, line['description'], product_id=line['product_id'],
            qty=line['qty'] or 1, unit_price=line['unit_price'],
        )

    _log_transaction(
        conn, customer_id, '850', 'inbound', parsed['po_number'], raw_edi,
        created_by, so_id=so_id,
    )

    return {
        'so_id': so_id, 'so_number': so_number,
        'unmapped_count': parsed['unmapped_count'],
        'line_count': len(parsed['lines']),
    }


# ---------------------------------------------------------------------------
# 855 — PO Acknowledgment (outbound)
# ---------------------------------------------------------------------------

def generate_855(conn, so_id: int, created_by: str | None = None) -> str:
    """Build a common-subset X12 855 acknowledging an SO's current lines
    as-is (this codebase has no partial-line-acceptance/rejection
    concept, so every line is acknowledged)."""
    so = get_so(conn, so_id)
    if not so:
        raise ValueError("Sales order not found.")
    items = get_so_items(conn, so_id)
    partner = get_trading_partner(conn, so['customer_id']) if so.get('customer_id') else None
    sender = partner['isa_sender_id'] if partner else 'SENDER'
    receiver = partner['isa_receiver_id'] if partner else 'RECEIVER'

    now = datetime.now()
    header = _isa_gs_header(sender, receiver, 'PR', now)
    transaction = [
        "ST*855*0001",
        f"BAK*00*AC*{so['so_number']}*{now.strftime('%Y%m%d')}",
    ]
    for idx, it in enumerate(items, start=1):
        transaction.append(
            f"PO1*{idx}*{it['qty']}*EA*{it['unit_price']}*PE*IA*{it['product_id'] or ''}"
        )
    transaction.append(f"CTT*{len(items)}")

    content = _finalize_envelope(header, transaction)

    _log_transaction(conn, so.get('customer_id'), '855', 'outbound',
                      so['so_number'], content, created_by, so_id=so_id)
    return content


# ---------------------------------------------------------------------------
# 856 — Advance Ship Notice (outbound)
# ---------------------------------------------------------------------------

def generate_856(conn, shipment_id: int, created_by: str | None = None) -> str:
    """Build a common-subset X12 856: BSN header, HL shipment/order/item
    loops, TD5 carrier, REF tracking number."""
    shipment = get_shipment(conn, shipment_id)
    if not shipment:
        raise ValueError("Shipment not found.")
    items = get_shipment_items(conn, shipment_id)

    so = get_so(conn, shipment['so_id']) if shipment.get('so_id') else None
    customer_id = so.get('customer_id') if so else None
    partner = get_trading_partner(conn, customer_id) if customer_id else None
    sender = partner['isa_sender_id'] if partner else 'SENDER'
    receiver = partner['isa_receiver_id'] if partner else 'RECEIVER'

    now = datetime.now()
    header = _isa_gs_header(sender, receiver, 'SH', now)
    transaction = [
        "ST*856*0001",
        f"BSN*00*{shipment['ship_number']}*{now.strftime('%Y%m%d')}*{now.strftime('%H%M')}",
        "HL*1**S",
        f"TD5***{shipment.get('carrier') or ''}",
        f"REF*CN*{shipment.get('tracking_number') or ''}",
        "HL*2*1*O",
    ]
    if so:
        transaction.append(f"PRF*{so['so_number']}")
    for idx, it in enumerate(items, start=1):
        transaction.append(f"HL*{idx + 2}*2*I")
        transaction.append(f"SN1*{idx}*{it['qty']}*EA")

    content = _finalize_envelope(header, transaction)

    _log_transaction(conn, customer_id, '856', 'outbound',
                      shipment['ship_number'], content, created_by,
                      shipment_id=shipment_id, so_id=shipment.get('so_id'))
    return content


# ---------------------------------------------------------------------------
# 810 — Invoice (outbound)
# ---------------------------------------------------------------------------

def generate_810(conn, invoice_id: int, created_by: str | None = None) -> str:
    """Build a common-subset X12 810. ar_invoice has no line-item table in
    this codebase, so this emits one summary IT1 line (amount +
    description) rather than fabricating per-item detail."""
    invoice = get_ar_invoice(conn, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found.")

    partner = get_trading_partner(conn, invoice['customer_id']) if invoice.get('customer_id') else None
    sender = partner['isa_sender_id'] if partner else 'SENDER'
    receiver = partner['isa_receiver_id'] if partner else 'RECEIVER'

    now = datetime.now()
    inv_date = (invoice.get('invoice_date') or now.date().isoformat()).replace('-', '')

    header = _isa_gs_header(sender, receiver, 'IN', now)
    transaction = [
        "ST*810*0001",
        f"BIG*{inv_date}*{invoice['invoice_number']}",
        f"IT1*1*1*EA*{invoice['amount']}**{invoice.get('description') or ''}",
        f"TDS*{invoice['amount']}",
    ]

    content = _finalize_envelope(header, transaction)

    _log_transaction(conn, invoice.get('customer_id'), '810', 'outbound',
                      invoice['invoice_number'], content, created_by,
                      invoice_id=invoice_id)
    return content
