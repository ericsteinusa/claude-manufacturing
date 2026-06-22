"""
contacts_core.py — Qt-free customer and supplier data layer.

Both tables (``customer`` and ``supplier``) share the same schema, so a
single shared implementation handles both.  The public API exposes explicit
per-entity functions so callers stay readable.
"""

from .log_utils import get_logger

log = get_logger(__name__)


def contact_label(row: dict) -> str:
    """Human-readable name: company name if set, else 'First Last'."""
    company = (row.get('company_name') or '').strip()
    first = (row.get('first_name') or '').strip()
    last = (row.get('last_name') or '').strip()
    name = f"{first} {last}".strip()
    return company if company else name or '(unnamed)'


# ---------------------------------------------------------------------------
# Shared internals — table name always comes from our own code, never user input
# ---------------------------------------------------------------------------

def _list(conn, table: str, search: str | None) -> list[dict]:
    if search:
        where = (
            "(company_name ILIKE %s OR first_name ILIKE %s "
            "OR last_name ILIKE %s OR email ILIKE %s)"
        )
        params: list = [f'%{search}%'] * 4
    else:
        where = '1=1'
        params = []

    rows = conn.execute(
        f"SELECT id, first_name, last_name, company_name, "
        f"phone_number, city, state, email "
        f"FROM {table} "
        f"WHERE {where} "
        f"ORDER BY LOWER(COALESCE(NULLIF(company_name,''), last_name, first_name))",
        params,
    ).fetchall()
    result = [dict(r) for r in rows]
    for r in result:
        r['label'] = contact_label(r)
    return result


def _get(conn, table: str, record_id: int) -> dict | None:
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = %s",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d['label'] = contact_label(d)
    return d


def _create(conn, table: str, fields: dict) -> int:
    """Insert a contact row and return its new id. Does not commit."""
    row = conn.execute(
        f"INSERT INTO {table} "
        f"(first_name, last_name, company_name, phone_number, "
        f"address, city, state, zip_code, email, created_by) "
        f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (
            (fields.get('first_name') or '').strip(),
            (fields.get('last_name') or '').strip(),
            (fields.get('company_name') or '').strip(),
            (fields.get('phone_number') or '').strip(),
            (fields.get('address') or '').strip(),
            (fields.get('city') or '').strip(),
            (fields.get('state') or '').strip(),
            (fields.get('zip_code') or '').strip(),
            (fields.get('email') or '').strip(),
            fields.get('created_by') or '',
        ),
    ).fetchone()
    return row['id']


def _update(conn, table: str, record_id: int, fields: dict) -> None:
    """Update editable contact fields. Does not commit."""
    conn.execute(
        f"UPDATE {table} SET "
        f"first_name=%s, last_name=%s, company_name=%s, phone_number=%s, "
        f"address=%s, city=%s, state=%s, zip_code=%s, email=%s "
        f"WHERE id=%s",
        (
            (fields.get('first_name') or '').strip(),
            (fields.get('last_name') or '').strip(),
            (fields.get('company_name') or '').strip(),
            (fields.get('phone_number') or '').strip(),
            (fields.get('address') or '').strip(),
            (fields.get('city') or '').strip(),
            (fields.get('state') or '').strip(),
            (fields.get('zip_code') or '').strip(),
            (fields.get('email') or '').strip(),
            record_id,
        ),
    )


# ---------------------------------------------------------------------------
# Customer API
# ---------------------------------------------------------------------------

def list_customers(conn, search: str | None = None) -> list[dict]:
    return _list(conn, 'customer', search)


def get_customer(conn, customer_id: int) -> dict | None:
    return _get(conn, 'customer', customer_id)


def create_customer(conn, **fields) -> int:
    cid = _create(conn, 'customer', fields)
    log.info("Created customer id=%s label=%r", cid,
             contact_label(fields))
    return cid


def update_customer(conn, customer_id: int, **fields) -> None:
    _update(conn, 'customer', customer_id, fields)
    log.info("Updated customer id=%s", customer_id)


def get_customer_orders(conn, customer_id: int) -> list[dict]:
    """Recent sales orders for this customer (newest first)."""
    rows = conn.execute(
        "SELECT so.id, so.so_number, so.status, so.order_date, "
        "COALESCE(SUM(si.qty * si.unit_price), 0) AS total "
        "FROM sales_order so "
        "LEFT JOIN so_item si ON si.so_id = so.id "
        "WHERE so.customer_id = %s "
        "GROUP BY so.id ORDER BY so.id DESC LIMIT 20",
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Supplier API
# ---------------------------------------------------------------------------

def list_suppliers(conn, search: str | None = None) -> list[dict]:
    return _list(conn, 'supplier', search)


def get_supplier(conn, supplier_id: int) -> dict | None:
    return _get(conn, 'supplier', supplier_id)


def create_supplier(conn, **fields) -> int:
    sid = _create(conn, 'supplier', fields)
    log.info("Created supplier id=%s label=%r", sid,
             contact_label(fields))
    return sid


def update_supplier(conn, supplier_id: int, **fields) -> None:
    _update(conn, 'supplier', supplier_id, fields)
    log.info("Updated supplier id=%s", supplier_id)


def get_supplier_orders(conn, supplier_id: int) -> list[dict]:
    """Recent purchase orders for this supplier (newest first)."""
    rows = conn.execute(
        "SELECT po.id, po.po_number, po.status, po.order_date, "
        "COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) AS total "
        "FROM purchase_order po "
        "LEFT JOIN po_item pi ON pi.po_id = po.id "
        "WHERE po.supplier_id = %s "
        "GROUP BY po.id ORDER BY po.id DESC LIMIT 20",
        (supplier_id,),
    ).fetchall()
    return [dict(r) for r in rows]
