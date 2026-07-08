"""
report_builder_core.py — Qt-free Custom Report Builder (P4-F).

A generic ad-hoc query tool over a hardcoded allowlist of tables/columns:
pick fields, add filters, group-by/aggregate, sort, save with a name and
access level, and schedule email delivery (CSV/PDF).

v1 scope is deliberately **single-table** (no cross-table joins) — this
satisfies every roadmap bullet (field selector, filters, group-by/
aggregate, sort, save, schedule) without the much larger design surface
of a join-graph UI.

SQL injection is the central risk of any report builder: table/column
names are chosen by the user by definition. There is no existing
runtime SQL-identifier-safety infrastructure in this codebase
(``db_pg.py``'s cursor wrapper does plain ``cursor.execute(sql,
params)`` with regex dialect-rewriting — no ``psycopg2.sql.Identifier``
anywhere), so this module is deliberately conservative: every table and
column name that ever reaches a SQL string is first checked against
``REPORTABLE_TABLES``, a hardcoded allowlist dict. String-formatting an
identifier into SQL after that check is safe *specifically because* the
value being formatted is always the literal dict key it was validated
against — never raw, unvalidated user text. Filter *values* are always
sent as ``%s`` parameters, never string-interpolated. Aggregate output
aliases are computed server-side (``f"{func}_{column}"``) rather than
accepted from the client, so a free-text alias field can never reach the
SQL string.

When ``aggregates`` is non-empty, the query's ``SELECT``/output is
``group_by`` columns + aggregate aliases (plain ``columns`` is ignored)
— SQL requires non-aggregated ``SELECT`` columns to exactly match
``GROUP BY``, so mixing the two concepts would either be invalid SQL or
require silently dropping columns; this rule is enforced in
``validate_definition``.

Reuses existing, unmodified functions for CSV/PDF plumbing:
``csv_export.csv_response`` for CSV. PDF is new (no existing tabular-
report PDF pattern; ``barcode_core.py`` is the only existing
``reportlab`` usage, for label layouts, not tables) but follows the same
``reportlab`` shape.
"""

from __future__ import annotations

import datetime
import io
import json

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from .log_utils import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Allowlist — the actual security boundary
# ---------------------------------------------------------------------------

def _cols(*pairs):
    """pairs of (name, label, type) -> {name: {label, type}}."""
    return {name: {'label': label, 'type': type_} for name, label, type_ in pairs}


REPORTABLE_TABLES = {
    'sales_order': {
        'label': 'Sales Orders',
        'columns': _cols(
            ('id', 'ID', 'number'), ('so_number', 'SO Number', 'text'),
            ('customer_id', 'Customer ID', 'number'),
            ('order_date', 'Order Date', 'date'), ('ship_date', 'Ship Date', 'date'),
            ('status', 'Status', 'text'), ('notes', 'Notes', 'text'),
            ('currency', 'Currency', 'text'), ('created_by', 'Created By', 'text'),
        ),
    },
    'so_item': {
        'label': 'Sales Order Items',
        'columns': _cols(
            ('id', 'ID', 'number'), ('so_id', 'SO ID', 'number'),
            ('description', 'Description', 'text'),
            ('product_id', 'Product ID', 'number'),
            ('qty', 'Qty', 'number'), ('unit_price', 'Unit Price', 'number'),
        ),
    },
    'work_order': {
        'label': 'Work Orders',
        'columns': _cols(
            ('id', 'ID', 'number'), ('wo_number', 'WO Number', 'text'),
            ('product_id', 'Product ID', 'number'),
            ('description', 'Description', 'text'),
            ('quantity', 'Quantity', 'number'),
            ('start_date', 'Start Date', 'date'), ('due_date', 'Due Date', 'date'),
            ('status', 'Status', 'text'), ('notes', 'Notes', 'text'),
            ('created_by', 'Created By', 'text'),
        ),
    },
    'product': {
        'label': 'Products',
        'columns': _cols(
            ('id', 'ID', 'number'), ('supplier_id', 'Supplier ID', 'number'),
            ('name', 'Name', 'text'), ('purchase_date', 'Purchase Date', 'date'),
            ('purchase_price', 'Purchase Price', 'number'), ('bin', 'Bin', 'text'),
            ('amount', 'Qty on Hand', 'number'),
            ('reorder_point', 'Reorder Point', 'number'),
            ('item_type', 'Item Type', 'text'), ('uom', 'UOM', 'text'),
            ('category', 'Category', 'text'),
        ),
    },
    'purchase_order': {
        'label': 'Purchase Orders',
        'columns': _cols(
            ('id', 'ID', 'number'), ('po_number', 'PO Number', 'text'),
            ('supplier_id', 'Supplier ID', 'number'),
            ('order_date', 'Order Date', 'date'),
            ('expected_date', 'Expected Date', 'date'),
            ('received_date', 'Received Date', 'date'),
            ('status', 'Status', 'text'), ('notes', 'Notes', 'text'),
            ('currency', 'Currency', 'text'), ('created_by', 'Created By', 'text'),
        ),
    },
    'po_item': {
        'label': 'Purchase Order Items',
        'columns': _cols(
            ('id', 'ID', 'number'), ('po_id', 'PO ID', 'number'),
            ('description', 'Description', 'text'),
            ('product_id', 'Product ID', 'number'),
            ('qty_ordered', 'Qty Ordered', 'number'),
            ('qty_received', 'Qty Received', 'number'),
            ('unit_price', 'Unit Price', 'number'),
        ),
    },
    'customer': {
        'label': 'Customers',
        'columns': _cols(
            ('id', 'ID', 'number'), ('first_name', 'First Name', 'text'),
            ('last_name', 'Last Name', 'text'),
            ('company_name', 'Company', 'text'), ('phone_number', 'Phone', 'text'),
            ('city', 'City', 'text'), ('state', 'State', 'text'),
            ('email', 'Email', 'text'),
        ),
    },
    'supplier': {
        'label': 'Suppliers',
        'columns': _cols(
            ('id', 'ID', 'number'), ('first_name', 'First Name', 'text'),
            ('last_name', 'Last Name', 'text'),
            ('company_name', 'Company', 'text'), ('phone_number', 'Phone', 'text'),
            ('city', 'City', 'text'), ('state', 'State', 'text'),
            ('email', 'Email', 'text'),
        ),
    },
    'ar_invoice': {
        'label': 'AR Invoices',
        'columns': _cols(
            ('id', 'ID', 'number'), ('customer_id', 'Customer ID', 'number'),
            ('invoice_number', 'Invoice Number', 'text'),
            ('invoice_date', 'Invoice Date', 'date'), ('due_date', 'Due Date', 'date'),
            ('amount', 'Amount', 'number'), ('description', 'Description', 'text'),
            ('status', 'Status', 'text'),
        ),
    },
    'ap_invoice': {
        'label': 'AP Invoices',
        'columns': _cols(
            ('id', 'ID', 'number'), ('vendor_id', 'Vendor ID', 'number'),
            ('invoice_number', 'Invoice Number', 'text'),
            ('invoice_date', 'Invoice Date', 'date'), ('due_date', 'Due Date', 'date'),
            ('amount', 'Amount', 'number'), ('description', 'Description', 'text'),
            ('status', 'Status', 'text'),
        ),
    },
    'shipment': {
        'label': 'Shipments',
        'columns': _cols(
            ('id', 'ID', 'number'), ('ship_number', 'Ship Number', 'text'),
            ('so_id', 'SO ID', 'number'), ('ship_date', 'Ship Date', 'date'),
            ('carrier', 'Carrier', 'text'),
            ('tracking_number', 'Tracking Number', 'text'),
            ('status', 'Status', 'text'), ('notes', 'Notes', 'text'),
        ),
    },
}

OPERATORS = {'=': '=', '!=': '!=', '>': '>', '<': '<', '>=': '>=', '<=': '<='}
SPECIAL_OPERATORS = {'contains', 'starts_with', 'is_null', 'is_not_null', 'in'}
ALL_OPERATORS = set(OPERATORS) | SPECIAL_OPERATORS

AGGREGATES = {'sum': 'SUM', 'count': 'COUNT', 'avg': 'AVG', 'min': 'MIN', 'max': 'MAX'}

ACCESS_LEVELS = ('private', 'department', 'company')
SCHEDULE_FREQUENCIES = ('daily', 'weekly', 'monthly')
SCHEDULE_FORMATS = ('csv', 'pdf')

_DUE_DAYS = {'daily': 1, 'weekly': 7, 'monthly': 30}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _output_columns(table_name: str, definition: dict) -> list:
    """The resolved list of output field names (not headers)."""
    aggregates = definition.get('aggregates') or []
    if aggregates:
        group_by = definition.get('group_by') or []
        return list(group_by) + [f"{a['func']}_{a['column']}" for a in aggregates]
    return list(definition.get('columns') or [])


def validate_definition(table_name: str, definition: dict) -> None:
    if table_name not in REPORTABLE_TABLES:
        raise ValueError(f"Unknown or disallowed table: {table_name}")
    allowed_cols = REPORTABLE_TABLES[table_name]['columns']

    def check_col(col):
        if col not in allowed_cols:
            raise ValueError(f"Column '{col}' is not reportable on '{table_name}'.")

    columns = definition.get('columns') or []
    filters = definition.get('filters') or []
    group_by = definition.get('group_by') or []
    aggregates = definition.get('aggregates') or []
    sort = definition.get('sort') or []

    for col in columns:
        check_col(col)
    for col in group_by:
        check_col(col)
    for f in filters:
        check_col(f['column'])
        if f['operator'] not in ALL_OPERATORS:
            raise ValueError(f"Unknown filter operator: {f['operator']}")
    for agg in aggregates:
        if agg['func'] not in AGGREGATES:
            raise ValueError(f"Unknown aggregate function: {agg['func']}")
        check_col(agg['column'])
        if agg['func'] != 'count' and allowed_cols[agg['column']]['type'] != 'number':
            raise ValueError(
                f"{agg['func']} requires a numeric column (got '{agg['column']}').")

    output_cols = set(_output_columns(table_name, definition))
    for s in sort:
        if s['column'] not in output_cols:
            raise ValueError(
                f"Sort column '{s['column']}' is not in the selected output.")

    if not columns and not aggregates:
        raise ValueError("Select at least one column or aggregate.")


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

def build_query(table_name: str, definition: dict, limit: int = 1000) -> tuple:
    """Return (sql, params, output_fields). Assumes validate_definition
    already passed — every identifier formatted below is guaranteed to be
    an exact REPORTABLE_TABLES dict key, never raw user text."""
    table = REPORTABLE_TABLES[table_name]
    columns = definition.get('columns') or []
    filters = definition.get('filters') or []
    group_by = definition.get('group_by') or []
    aggregates = definition.get('aggregates') or []
    sort = definition.get('sort') or []

    select_parts = []
    output_fields = []  # [(field_or_alias, header_label), ...]

    if aggregates:
        for col in group_by:
            select_parts.append(col)
            output_fields.append((col, table['columns'][col]['label']))
        for agg in aggregates:
            func_sql = AGGREGATES[agg['func']]
            col = agg['column']
            alias = f"{agg['func']}_{col}"
            select_parts.append(f"{func_sql}({col}) AS {alias}")
            header = f"{agg['func'].upper()}({table['columns'][col]['label']})"
            output_fields.append((alias, header))
    else:
        for col in columns:
            select_parts.append(col)
            output_fields.append((col, table['columns'][col]['label']))

    sql = f"SELECT {', '.join(select_parts)} FROM {table_name}"
    params: list = []

    conditions = []
    for f in filters:
        col = f['column']
        op = f['operator']
        value = f.get('value')
        if op == 'is_null':
            conditions.append(f"{col} IS NULL")
        elif op == 'is_not_null':
            conditions.append(f"{col} IS NOT NULL")
        elif op == 'in':
            values = [v.strip() for v in (value or '').split(',') if v.strip()]
            if not values:
                continue
            placeholders = ', '.join(['%s'] * len(values))
            conditions.append(f"{col} IN ({placeholders})")
            params.extend(values)
        elif op in ('contains', 'starts_with'):
            escaped = (value or '').replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')
            pattern = f"%{escaped}%" if op == 'contains' else f"{escaped}%"
            conditions.append(f"{col} ILIKE %s ESCAPE '\\'")
            params.append(pattern)
        else:
            conditions.append(f"{col} {OPERATORS[op]} %s")
            params.append(value)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    if aggregates and group_by:
        sql += " GROUP BY " + ", ".join(group_by)

    if sort:
        valid_output_cols = {f for f, _ in output_fields}
        order_parts = []
        for s in sort:
            col = s['column']
            if col not in valid_output_cols:
                continue
            direction = 'DESC' if s.get('direction') == 'desc' else 'ASC'
            order_parts.append(f"{col} {direction}")
        if order_parts:
            sql += " ORDER BY " + ", ".join(order_parts)

    sql += " LIMIT %s"
    params.append(limit)

    return sql, params, output_fields


def run_report(conn, table_name: str, definition: dict, limit: int = 1000) -> dict:
    validate_definition(table_name, definition)
    sql, params, output_fields = build_query(table_name, definition, limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    return {'output_fields': output_fields, 'rows': rows}


# ---------------------------------------------------------------------------
# CSV / PDF export
# ---------------------------------------------------------------------------

def report_to_pdf_bytes(title: str, output_fields: list, rows: list) -> bytes:
    """Render a report as a simple tabular PDF (landscape letter, since
    reports can be wide) — the first tabular-report reportlab usage in
    this codebase; barcode_core.py's is a fixed small label layout."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                             leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                             topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles['Title']), Spacer(1, 0.2 * inch)]

    headers = [header for _field, header in output_fields]
    fields = [field for field, _header in output_fields]
    data = [headers]
    for row in rows:
        data.append([str(row.get(f, '')) for f in fields])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003cb4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Saved reports
# ---------------------------------------------------------------------------

def ensure_report_builder_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_report (
            id                    SERIAL PRIMARY KEY,
            name                  TEXT NOT NULL,
            table_name            TEXT NOT NULL,
            definition            TEXT NOT NULL,
            access_level          TEXT NOT NULL DEFAULT 'private',
            owner_email           TEXT DEFAULT '',
            owner_dept_key        TEXT DEFAULT '',
            schedule_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
            schedule_frequency    TEXT DEFAULT '',
            schedule_recipients   TEXT DEFAULT '',
            schedule_format       TEXT DEFAULT 'csv',
            last_run_at           TEXT,
            created_at            TEXT DEFAULT '',
            created_by            TEXT DEFAULT ''
        )
    """)


def create_saved_report(conn, name: str, table_name: str, definition: dict,
                         access_level: str, owner_email: str, owner_dept_key: str,
                         created_by: str, schedule_enabled: bool = False,
                         schedule_frequency: str = '', schedule_recipients: str = '',
                         schedule_format: str = 'csv') -> int:
    if not name:
        raise ValueError("Report name is required.")
    if access_level not in ACCESS_LEVELS:
        raise ValueError(f"access_level must be one of {ACCESS_LEVELS}.")
    validate_definition(table_name, definition)
    row = conn.execute(
        "INSERT INTO saved_report "
        "(name, table_name, definition, access_level, owner_email, owner_dept_key, "
        "schedule_enabled, schedule_frequency, schedule_recipients, schedule_format, "
        "created_at, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name, table_name, json.dumps(definition), access_level, owner_email or '',
         owner_dept_key or '', schedule_enabled, schedule_frequency or '',
         schedule_recipients or '', schedule_format or 'csv',
         datetime.datetime.now().isoformat(), created_by or ''),
    ).fetchone()
    return row['id']


def update_saved_report(conn, report_id: int, **fields) -> None:
    allowed = {'name', 'table_name', 'access_level', 'schedule_enabled',
               'schedule_frequency', 'schedule_recipients', 'schedule_format'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if 'definition' in fields:
        table_name = fields.get('table_name')
        if table_name is None:
            existing = get_saved_report(conn, report_id)
            table_name = existing['table_name'] if existing else None
        validate_definition(table_name, fields['definition'])
        cols['definition'] = json.dumps(fields['definition'])
    if 'access_level' in cols and cols['access_level'] not in ACCESS_LEVELS:
        raise ValueError(f"access_level must be one of {ACCESS_LEVELS}.")
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE saved_report SET {set_clause} WHERE id = %s",
        (*cols.values(), report_id),
    )


def get_saved_report(conn, report_id: int):
    row = conn.execute(
        "SELECT * FROM saved_report WHERE id = %s", (report_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d['definition'] = json.loads(d['definition'])
    return d


def list_saved_reports(conn, user_email: str, user_dept_key: str, full_access: bool) -> list:
    rows = conn.execute("""
        SELECT * FROM saved_report
        WHERE %s
           OR access_level = 'company'
           OR (access_level = 'department' AND owner_dept_key = %s)
           OR (access_level = 'private' AND owner_email = %s)
        ORDER BY name
    """, (bool(full_access), user_dept_key or '', user_email or '')).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['definition'] = json.loads(d['definition'])
        out.append(d)
    return out


def delete_saved_report(conn, report_id: int) -> None:
    conn.execute("DELETE FROM saved_report WHERE id = %s", (report_id,))


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def _is_due(frequency: str, last_run_at) -> bool:
    if not last_run_at:
        return True
    days_required = _DUE_DAYS.get(frequency)
    if days_required is None:
        return False
    last = datetime.date.fromisoformat(str(last_run_at)[:10])
    return (datetime.date.today() - last).days >= days_required


def list_due_scheduled_reports(conn) -> list:
    rows = conn.execute(
        "SELECT * FROM saved_report WHERE schedule_enabled = TRUE"
    ).fetchall()
    due = []
    for r in rows:
        d = dict(r)
        if _is_due(d.get('schedule_frequency'), d.get('last_run_at')):
            d['definition'] = json.loads(d['definition'])
            due.append(d)
    return due


def mark_report_run(conn, report_id: int) -> None:
    conn.execute(
        "UPDATE saved_report SET last_run_at = %s WHERE id = %s",
        (datetime.datetime.now().isoformat(), report_id),
    )
