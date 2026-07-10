"""batch_record_core.py — Qt-free Batch Record Generation, 6/10 of the
top-10 ERPs have it.

A batch record is the as-built manufacturing document for one completed
Work Order — what was produced, what materials went into it, what it
cost, and what quality inspections were performed — issued as a numbered,
point-in-time record. Nothing new is computed here: this module pulls
together data that already exists across three other modules
(`work_orders_core.get_wo`/`get_wo_materials`/`get_wo_cost_summary`, and
`qa_inspection` rows keyed by `wo_id`) and **snapshots** it into
`batch_record`/`batch_record_material`/`batch_record_inspection` rows at
generation time — the same snapshot-not-live-query choice `coa_core`
already made for Certificates of Analysis, for the same reason: a record
that silently changed if someone later edited a WO's materials would
defeat the point of having a record at all.

Only a completed Work Order has an as-built story worth recording — you
can't issue a batch record for a job that hasn't finished yet.

Every function takes an open connection; the caller owns the transaction
(same convention as coa_core / skills_matrix_core).
"""

from __future__ import annotations

import datetime

from .work_orders_core import get_wo, get_wo_materials, get_wo_cost_summary


def ensure_batch_record_tables(conn):
    """Create batch_record / batch_record_material / batch_record_inspection
    if absent. Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS batch_record (
            id                    SERIAL PRIMARY KEY,
            batch_record_number   TEXT NOT NULL UNIQUE,
            wo_id                 INTEGER NOT NULL REFERENCES work_order(id),
            wo_number             TEXT NOT NULL DEFAULT '',
            product_name          TEXT NOT NULL DEFAULT '',
            quantity              REAL NOT NULL DEFAULT 0,
            material_cost         REAL NOT NULL DEFAULT 0,
            labor_cost            REAL NOT NULL DEFAULT 0,
            total_cost            REAL NOT NULL DEFAULT 0,
            generated_by          TEXT NOT NULL DEFAULT '',
            generated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by            TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS batch_record_material (
            id                SERIAL PRIMARY KEY,
            batch_record_id   INTEGER NOT NULL REFERENCES batch_record(id),
            component_name    TEXT NOT NULL DEFAULT '',
            qty_required      REAL NOT NULL DEFAULT 0,
            qty_issued        REAL NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS batch_record_inspection (
            id                SERIAL PRIMARY KEY,
            batch_record_id   INTEGER NOT NULL REFERENCES batch_record(id),
            insp_number       TEXT NOT NULL DEFAULT '',
            inspector         TEXT NOT NULL DEFAULT '',
            insp_date         TEXT NOT NULL DEFAULT '',
            result            TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS batch_record_material_record "
        "ON batch_record_material(batch_record_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS batch_record_inspection_record "
        "ON batch_record_inspection(batch_record_id)"
    )


def next_batch_record_number(conn) -> str:
    year = datetime.date.today().year
    prefix = f'BR-{year}-'
    rows = conn.execute(
        "SELECT batch_record_number FROM batch_record WHERE batch_record_number LIKE %s",
        (f'{prefix}%',),
    ).fetchall()
    max_n = 0
    for r in rows:
        try:
            max_n = max(max_n, int(r['batch_record_number'].split('-')[-1]))
        except (ValueError, IndexError, AttributeError):
            pass
    return f'{prefix}{max_n + 1:04d}'


def _inspections_for_wo(conn, wo_id):
    rows = conn.execute(
        "SELECT insp_number, inspector, insp_date, result "
        "FROM qa_inspection WHERE wo_id = %s ORDER BY insp_date, id",
        (wo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_batch_record(conn, wo_id, generated_by='', created_by=''):
    """Snapshot a completed Work Order's materials, cost, and quality
    inspections into a new numbered batch record. Raises if the WO
    doesn't exist or isn't 'completed'."""
    wo = get_wo(conn, wo_id)
    if not wo:
        raise ValueError(f'No work order with id {wo_id}')
    if wo['status'] != 'completed':
        raise ValueError(
            "Can only generate a batch record for a 'completed' work order "
            f"(current status: {wo['status']!r})")

    materials = get_wo_materials(conn, wo_id)
    cost = get_wo_cost_summary(conn, wo_id)
    inspections = _inspections_for_wo(conn, wo_id)

    record_number = next_batch_record_number(conn)
    row = conn.execute(
        "INSERT INTO batch_record "
        "(batch_record_number, wo_id, wo_number, product_name, quantity, "
        " material_cost, labor_cost, total_cost, generated_by, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (record_number, wo_id, wo['wo_number'], wo.get('product_name') or '',
         wo['quantity'], cost['material_cost'], cost['labor_cost'],
         cost['total_cost'], generated_by or '', created_by or ''),
    ).fetchone()
    record_id = row['id']

    for m in materials:
        conn.execute(
            "INSERT INTO batch_record_material "
            "(batch_record_id, component_name, qty_required, qty_issued) "
            "VALUES (%s,%s,%s,%s)",
            (record_id, m.get('product_name') or '', m['qty_required'], m['qty_issued']),
        )
    for insp in inspections:
        conn.execute(
            "INSERT INTO batch_record_inspection "
            "(batch_record_id, insp_number, inspector, insp_date, result) "
            "VALUES (%s,%s,%s,%s,%s)",
            (record_id, insp['insp_number'], insp['inspector'],
             insp['insp_date'], insp['result']),
        )
    return record_id


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_batch_records(conn, wo_id=None, search=None):
    sql = "SELECT * FROM batch_record WHERE TRUE"
    params: list = []
    if wo_id:
        sql += " AND wo_id = %s"
        params.append(wo_id)
    if search:
        sql += " AND (batch_record_number ILIKE %s OR wo_number ILIKE %s OR product_name ILIKE %s)"
        params.extend([f'%{search}%'] * 3)
    sql += " ORDER BY generated_at DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_batch_record(conn, record_id):
    row = conn.execute(
        "SELECT * FROM batch_record WHERE id = %s", (record_id,)
    ).fetchone()
    if not row:
        return None
    record = dict(row)
    record['materials'] = [dict(r) for r in conn.execute(
        "SELECT * FROM batch_record_material WHERE batch_record_id = %s ORDER BY id",
        (record_id,),
    ).fetchall()]
    record['inspections'] = [dict(r) for r in conn.execute(
        "SELECT * FROM batch_record_inspection WHERE batch_record_id = %s ORDER BY id",
        (record_id,),
    ).fetchall()]
    return record


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

def render_batch_record_pdf(record: dict) -> bytes:
    """Render a batch record PDF, mirroring the reportlab pattern already
    established in coa_core.py / customer_portal_core.py."""
    import io

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
        Paragraph(f"Batch Record {record['batch_record_number']}", styles['Heading1']),
        Spacer(1, 0.15 * inch),
        Paragraph(f"Work Order: {record['wo_number']}", styles['Normal']),
        Paragraph(f"Product: {record['product_name']}", styles['Normal']),
        Paragraph(f"Quantity: {record['quantity']}", styles['Normal']),
        Paragraph(f"Generated: {record['generated_at']} by {record.get('generated_by') or ''}",
                  styles['Normal']),
        Spacer(1, 0.2 * inch),
    ]

    totals = [
        ['Material Cost', f"${record['material_cost']:.2f}"],
        ['Labor Cost', f"${record['labor_cost']:.2f}"],
        ['Total Cost', f"${record['total_cost']:.2f}"],
    ]
    t = Table(totals, colWidths=[3 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(t)

    if record.get('materials'):
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph('Materials Consumed', styles['Heading3']))
        rows = [['Component', 'Qty Required', 'Qty Issued']]
        for m in record['materials']:
            rows.append([m['component_name'], str(m['qty_required']), str(m['qty_issued'])])
        mt = Table(rows, colWidths=[3 * inch, 1.25 * inch, 1.25 * inch])
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8edf7')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1dae8')),
        ]))
        story.append(mt)

    if record.get('inspections'):
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph('Quality Inspections', styles['Heading3']))
        rows = [['Inspection #', 'Inspector', 'Date', 'Result']]
        for i in record['inspections']:
            rows.append([i['insp_number'], i['inspector'], i['insp_date'], i['result']])
        it = Table(rows, colWidths=[1.5 * inch, 1.5 * inch, 1.2 * inch, 1.3 * inch])
        it.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8edf7')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1dae8')),
        ]))
        story.append(it)

    doc.build(story)
    buf.seek(0)
    return buf.read()
