"""coa_core.py — Qt-free Certificate of Analysis (CoA) generation.

A CoA certifies that a specific lot's tested characteristics meet spec —
7/10 of the top-10 ERPs ship this for regulated/quality-conscious
manufacturers, and this codebase had no CoA concept at all before this
module.

Rather than inventing a new set of "certified characteristics", this
reuses the SPC infrastructure that already exists (quality_core.py's
spc_measurement + spc_control_limit, Phase 6A) — a CoA is generated from
whatever SPC measurements have already been recorded against a lot
(spc_measurement.lot_id), snapshotted at generation time into coa_result
rows. Snapshotting (rather than computing live on every view, the
convention most other reports in this codebase use) is deliberate here:
a certificate that silently changed if someone later edited or added a
measurement would defeat the point of a certificate — see
costing_core.roll_standard_cost / carbon_core.carbon_roll for the same
roll-then-snapshot precedent.

A lot with no SPC measurements recorded against it has nothing to
certify — generate_coa raises ValueError rather than emitting an empty
or fabricated certificate.

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / sampling_plan_core).
"""

from __future__ import annotations

import datetime
import io

from .lot_core import get_lot

COA_RESULTS = ('pass', 'fail', 'no_spec')


def ensure_coa_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coa_document (
            id             SERIAL PRIMARY KEY,
            coa_number     TEXT NOT NULL UNIQUE,
            lot_id         INTEGER NOT NULL REFERENCES lot(id),
            issued_date    TEXT NOT NULL,
            issued_by      TEXT NOT NULL DEFAULT '',
            overall_result TEXT NOT NULL DEFAULT 'pending',
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coa_result (
            id             SERIAL PRIMARY KEY,
            coa_id         INTEGER NOT NULL REFERENCES coa_document(id),
            characteristic TEXT NOT NULL,
            measured_value REAL,
            target         REAL,
            lcl            REAL,
            ucl            REAL,
            result         TEXT NOT NULL DEFAULT 'no_spec'
        )
    """)


def next_coa_number(conn) -> str:
    year = datetime.date.today().year
    prefix = f'COA-{year}-'
    rows = conn.execute(
        "SELECT coa_number FROM coa_document WHERE coa_number LIKE %s",
        (f'{prefix}%',),
    ).fetchall()
    max_n = 0
    for r in rows:
        try:
            max_n = max(max_n, int(r['coa_number'].split('-')[-1]))
        except (ValueError, IndexError, AttributeError):
            pass
    return f'{prefix}{max_n + 1:04d}'


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _latest_measurements_for_lot(conn, lot_id):
    """One row per characteristic — the most recent spc_measurement
    recorded against this lot, joined to that product's spec limits (if
    any). A characteristic with no spc_control_limit row has nothing to
    compare against ('no_spec'), which is reported rather than silently
    dropped."""
    rows = conn.execute("""
        SELECT DISTINCT ON (sm.characteristic)
            sm.characteristic, sm.measured_value, sm.in_control,
            sm.measured_at, scl.target, scl.lcl, scl.ucl
        FROM spc_measurement sm
        LEFT JOIN spc_control_limit scl
            ON scl.product_id = sm.product_id
           AND scl.characteristic = sm.characteristic
        WHERE sm.lot_id = %s
        ORDER BY sm.characteristic, sm.measured_at DESC
    """, (lot_id,)).fetchall()
    return [dict(r) for r in rows]


def generate_coa(conn, lot_id, issued_by, created_by, issued_date=None,
                 notes=''):
    """Snapshot this lot's latest-per-characteristic SPC measurements into
    a new CoA. Raises ValueError if the lot doesn't exist or has no SPC
    measurements recorded at all."""
    lot = get_lot(conn, lot_id)
    if not lot:
        raise ValueError(f'No lot with id {lot_id}')
    measurements = _latest_measurements_for_lot(conn, lot_id)
    if not measurements:
        raise ValueError(
            'No SPC measurements are recorded against this lot — '
            'nothing to certify.')

    coa_number = next_coa_number(conn)
    row = conn.execute(
        "INSERT INTO coa_document "
        "(coa_number, lot_id, issued_date, issued_by, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (coa_number, lot_id, issued_date or datetime.date.today().isoformat(),
         issued_by or '', notes or '', created_by or ''),
    ).fetchone()
    coa_id = row['id']

    any_fail = False
    for m in measurements:
        has_spec = m['ucl'] is not None or m['lcl'] is not None
        if not has_spec:
            result = 'no_spec'
        elif m['in_control']:
            result = 'pass'
        else:
            result = 'fail'
            any_fail = True
        conn.execute(
            "INSERT INTO coa_result "
            "(coa_id, characteristic, measured_value, target, lcl, ucl, result) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (coa_id, m['characteristic'], m['measured_value'], m['target'],
             m['lcl'], m['ucl'], result),
        )

    overall = 'fail' if any_fail else 'pass'
    conn.execute(
        "UPDATE coa_document SET overall_result = %s WHERE id = %s",
        (overall, coa_id),
    )
    return coa_id


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_coas(conn, lot_id=None, search=None):
    conditions = []
    params: list = []
    if lot_id:
        conditions.append("c.lot_id = %s")
        params.append(lot_id)
    if search:
        conditions.append("(c.coa_number ILIKE %s OR p.name ILIKE %s OR l.lot_number ILIKE %s)")
        params.extend([f"%{search}%"] * 3)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(f"""
        SELECT c.*, l.lot_number, p.name AS product_name
        FROM coa_document c
        JOIN lot l ON l.id = c.lot_id
        JOIN product p ON p.id = l.product_id
        {where}
        ORDER BY c.created_at DESC, c.id DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_coa(conn, coa_id):
    row = conn.execute("""
        SELECT c.*, l.lot_number, l.product_id, p.name AS product_name
        FROM coa_document c
        JOIN lot l ON l.id = c.lot_id
        JOIN product p ON p.id = l.product_id
        WHERE c.id = %s
    """, (coa_id,)).fetchone()
    return dict(row) if row else None


def get_coa_results(conn, coa_id):
    rows = conn.execute(
        "SELECT * FROM coa_result WHERE coa_id = %s ORDER BY characteristic",
        (coa_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

def render_coa_pdf(coa: dict, results: list) -> bytes:
    """Render a Certificate of Analysis PDF, mirroring the reportlab
    pattern already established in customer_portal_core.py."""
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
    result_hex = "1a7f37" if coa.get("overall_result") == "pass" else "c0392b"
    story = [
        Paragraph("Certificate of Analysis", styles["Heading1"]),
        Spacer(1, 0.1 * inch),
        Paragraph(f"CoA Number: {coa['coa_number']}", styles["Normal"]),
        Paragraph(f"Product: {coa.get('product_name', '')}", styles["Normal"]),
        Paragraph(f"Lot Number: {coa.get('lot_number', '')}", styles["Normal"]),
        Paragraph(f"Issued Date: {coa.get('issued_date') or ''}", styles["Normal"]),
        Paragraph(f"Issued By: {coa.get('issued_by') or ''}", styles["Normal"]),
        Spacer(1, 0.1 * inch),
        Paragraph(
            f"Overall Result: <font color='#{result_hex}'>"
            f"{coa.get('overall_result', '').upper()}</font>",
            styles["Heading3"]),
        Spacer(1, 0.2 * inch),
    ]
    if coa.get("notes"):
        story.append(Paragraph(coa["notes"], styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    rows = [["Characteristic", "Measured", "Target", "LCL", "UCL", "Result"]]
    for r in results:
        rows.append([
            r["characteristic"],
            f"{r['measured_value']:.3f}" if r.get("measured_value") is not None else "—",
            f"{r['target']:.3f}" if r.get("target") is not None else "—",
            f"{r['lcl']:.3f}" if r.get("lcl") is not None else "—",
            f"{r['ucl']:.3f}" if r.get("ucl") is not None else "—",
            r["result"].upper(),
        ])
    t = Table(rows, colWidths=[1.6 * inch, 0.9 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1dae8")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]
    for i, r in enumerate(results, start=1):
        if r["result"] == "fail":
            style_cmds.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#c0392b")))
        elif r["result"] == "pass":
            style_cmds.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#1a7f37")))
    t.setStyle(TableStyle(style_cmds))
    story.append(t)

    doc.build(story)
    buf.seek(0)
    return buf.read()
