"""
Barcode generation and PDF label printing.
Code 39 format, one label per page (full-page PDF).

Prefixes:
  WO-      work order
  PART-    inventory / product
  PO-      purchase order
  RCV-     receiving order
  ASSET-   IT asset
"""
from __future__ import annotations
import io
from barcode import Code39
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


# ── Prefix routing ────────────────────────────────────────────────────────────

PREFIXES = {
    "WO-":    ("wo",        "Work Order"),
    "MWO-":   ("mwo",       "Maintenance WO"),
    "SO-":    ("so",        "Sales Order"),
    "SHIP-":  ("ship",     "Shipment"),
    "CS-":    ("cs",      "CS Ticket"),
    "PART-":  ("inventory", "Part / Product"),
    "PO-":    ("po",        "Purchase Order"),
    "RCV-":   ("receiving", "Receiving"),
    "ASSET-": ("asset",     "IT Asset"),
}


def parse_scan(raw: str) -> tuple[str, str] | None:
    """
    Parse a scanner input and return (record_type, record_key) or None.
    record_type matches PREFIXES values[0]; record_key is the stripped value.
    """
    code = raw.strip().upper()
    for prefix, (rtype, _) in PREFIXES.items():
        if code.startswith(prefix):
            return rtype, code[len(prefix):]
    return None


def resolve_scan_url(raw: str) -> str | None:
    """
    Given a raw scan string, return the URL to redirect to, or None if unknown.
    Looks up the record in the DB to get the numeric ID.
    """
    result = parse_scan(raw)
    if result is None:
        return None
    rtype, key = result
    if rtype == "wo":
        return _lookup_wo_url(key)
    if rtype == "inventory":
        return _lookup_part_url(key)
    if rtype == "po":
        return _lookup_po_url(key)
    if rtype == "receiving":
        return _lookup_po_url(key)   # receiving links to PO detail
    if rtype == "asset":
        return _lookup_asset_url(key)
    if rtype == "mwo":
        return _lookup_mwo_url(key)
    if rtype == "so":
        return _lookup_so_url(key)
    if rtype == "ship":
        return _lookup_ship_url(key)
    if rtype == "cs":
        return _lookup_cs_url(key)
    return None


def _lookup_wo_url(wo_number: str) -> str | None:
    try:
        from .db_pg import get_db_connection
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id FROM work_order WHERE wo_number = %s", [wo_number]
        ).fetchone()
        if row:
            return f"/wo/{row['id']}/"
    except Exception:
        pass
    return None


def _lookup_part_url(key: str) -> str | None:
    try:
        from .db_pg import get_db_connection
        conn = get_db_connection()
        # key may be a numeric id or a name
        row = None
        if key.isdigit():
            row = conn.execute(
                "SELECT id FROM product WHERE id = %s", [int(key)]
            ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT id FROM product WHERE UPPER(name) = %s", [key.upper()]
            ).fetchone()
        if row:
            return f"/inventory/{row['id']}/"
    except Exception:
        pass
    return None


def _lookup_po_url(po_number: str) -> str | None:
    try:
        from .db_pg import get_db_connection
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id FROM purchase_order WHERE po_number = %s", [po_number]
        ).fetchone()
        if row:
            return f"/po/{row['id']}/"
    except Exception:
        pass
    return None


def _lookup_cs_url(key: str) -> str | None:
    if key.isdigit():
        return f"/cs/{key}/"
    return None


def _lookup_ship_url(ship_number: str) -> str | None:
    try:
        from .db_pg import get_db_connection
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id FROM shipment WHERE ship_number = %s", [ship_number]
        ).fetchone()
        if row:
            return f"/prod/shipping/{row['id']}/"
    except Exception:
        pass
    return None


def _lookup_so_url(so_number: str) -> str | None:
    try:
        from .db_pg import get_db_connection
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id FROM sales_order WHERE so_number = %s", [so_number]
        ).fetchone()
        if row:
            return f"/so/{row['id']}/"
    except Exception:
        pass
    return None


def _lookup_mwo_url(key: str) -> str | None:
    if key.isdigit():
        return f"/maint/wo/{key}/"
    return None


def _lookup_asset_url(asset_tag: str) -> str | None:
    try:
        from .db_pg import get_db_connection
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id FROM it_asset WHERE asset_tag = %s", [asset_tag]
        ).fetchone()
        if row:
            return f"/it/assets/{row['id']}/"
    except Exception:
        pass
    return None


# ── Barcode image generation ──────────────────────────────────────────────────

def _barcode_image_bytes(code: str) -> bytes:
    """Return PNG bytes for a Code 39 barcode."""
    writer = ImageWriter()
    buf = io.BytesIO()
    bc = Code39(code, writer=writer, add_checksum=False)
    bc.write(buf, options={
        "module_width": 0.4,
        "module_height": 12.0,
        "font_size": 10,
        "text_distance": 4.0,
        "quiet_zone": 6.0,
        "dpi": 150,
    })
    buf.seek(0)
    return buf.read()


# ── PDF label (full page, one barcode) ───────────────────────────────────────

def generate_label_pdf(
    code: str,
    title: str,
    subtitle: str = "",
) -> bytes:
    """
    Generate a full-page PDF with a single Code 39 barcode label.

    Args:
        code:     The raw barcode string to encode (e.g. "WO-2024-001")
        title:    Large text above the barcode (e.g. "Work Order WO-2024-001")
        subtitle: Smaller text below the barcode (e.g. description / part name)

    Returns:
        PDF bytes ready to send as a response.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=1.5 * inch,
        bottomMargin=1.5 * inch,
        leftMargin=1.5 * inch,
        rightMargin=1.5 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.fontSize = 18
    title_style.spaceAfter = 12
    sub_style = styles["Normal"]
    sub_style.fontSize = 12
    sub_style.spaceAfter = 6

    img_bytes = _barcode_image_bytes(code)
    img_buf = io.BytesIO(img_bytes)
    barcode_img = Image(img_buf, width=4 * inch, height=1.4 * inch)
    barcode_img.hAlign = "CENTER"

    story = [
        Paragraph(title, title_style),
        Spacer(1, 0.2 * inch),
        barcode_img,
    ]
    if subtitle:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph(subtitle, sub_style))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── Convenience builders per record type ─────────────────────────────────────

def wo_label_pdf(wo: dict) -> bytes:
    code = f"WO-{wo['wo_number']}"
    title = f"Work Order: {wo['wo_number']}"
    sub = wo.get("description") or ""
    return generate_label_pdf(code, title, sub)


def part_label_pdf(product: dict) -> bytes:
    sku = product.get("sku") or str(product["id"])
    code = f"PART-{sku}"
    title = f"Part: {sku}"
    sub = product.get("name") or ""
    return generate_label_pdf(code, title, sub)


def po_label_pdf(po: dict) -> bytes:
    code = f"PO-{po['po_number']}"
    title = f"Purchase Order: {po['po_number']}"
    sub = po.get("notes") or ""
    return generate_label_pdf(code, title, sub)


def receiving_label_pdf(po: dict) -> bytes:
    code = f"RCV-{po['po_number']}"
    title = f"Receiving: {po['po_number']}"
    sub = po.get("notes") or ""
    return generate_label_pdf(code, title, sub)


def asset_label_pdf(asset: dict) -> bytes:
    code = f"ASSET-{asset['asset_tag']}"
    title = f"Asset: {asset['asset_tag']}"
    sub = f"{asset.get('make', '')} {asset.get('model', '')}".strip()
    return generate_label_pdf(code, title, sub)
