"""
sales_core.py — Qt-free data layer for the Sales web UI.

Re-exports the SO helpers from sales_orders_core and adds dashboard,
quotes, and targets.  Tables: sales_order, so_item (via sales_orders_core),
sales_quote, sales_target.
"""

from .sales_orders_core import (       # noqa: F401 — re-exported for views
    SO_STATUSES, SO_STATUS_COLORS, SO_STATUS_TRANSITIONS,
    SO_STATUS_ACTION_LABELS,
    allowed_transitions, can_transition, customer_label,
    next_so_number, list_sos, get_so, get_so_items,
    load_customers, load_products,
    create_so, update_so, add_so_item, delete_so_item, set_so_status,
)

from datetime import date

QUOTE_STATUSES  = ('Draft', 'Sent', 'Won', 'Lost', 'Expired')
TARGET_STATUSES = ('On Track', 'Behind', 'Achieved')


def _today():
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_sales_dashboard(conn):
    so_row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='draft')     AS draft,
            COUNT(*) FILTER (WHERE status='confirmed') AS confirmed,
            COUNT(*) FILTER (WHERE status='shipped')   AS shipped,
            COUNT(*) FILTER (WHERE status='invoiced')  AS invoiced,
            COUNT(*)                                    AS total,
            COALESCE(SUM(
                (SELECT SUM(qty*unit_price) FROM so_item si WHERE si.so_id=so.id)
            ), 0) AS total_value
        FROM sales_order so
    """).fetchone()
    quote_row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status='Draft') AS draft,
            COUNT(*) FILTER (WHERE status='Sent')  AS sent,
            COUNT(*) FILTER (WHERE status='Won')   AS won,
            COUNT(*)                                AS total,
            COALESCE(SUM(amount) FILTER (WHERE status='Won'), 0) AS won_value
        FROM sales_quote
    """).fetchone()
    target_row = conn.execute("""
        SELECT
            COALESCE(SUM(target), 0) AS total_target,
            COALESCE(SUM(actual), 0) AS total_actual
        FROM sales_target
    """).fetchone()
    return {
        'orders':  dict(so_row)    if so_row    else {},
        'quotes':  dict(quote_row) if quote_row else {},
        'targets': dict(target_row) if target_row else {},
    }


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

def list_quotes(conn, status=None, search=None):
    conds, params = [], []
    if status:
        conds.append('status = %s')
        params.append(status)
    if search:
        conds.append('(customer ILIKE %s OR description ILIKE %s)')
        params += [f'%{search}%', f'%{search}%']
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(
        f"SELECT * FROM sales_quote {where}"
        f" ORDER BY quote_date DESC NULLS LAST, id DESC",
        params or None
    ).fetchall()


def get_quote(conn, quote_id):
    return conn.execute(
        "SELECT * FROM sales_quote WHERE id = %s", (quote_id,)
    ).fetchone()


def create_quote(conn, customer, description, amount, owner,
                 quote_date, valid_until, notes, created_by):
    if not customer:
        raise ValueError('Customer name is required')
    row = conn.execute(
        "INSERT INTO sales_quote (customer, description, amount, owner,"
        " quote_date, valid_until, status, notes, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,'Draft',%s,%s) RETURNING id",
        (customer, description or '', float(amount or 0),
         owner or '', quote_date or _today(),
         valid_until or '', notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_quote(conn, quote_id, customer, description, amount, owner,
                 quote_date, valid_until, status, notes):
    if not customer:
        raise ValueError('Customer name is required')
    if status not in QUOTE_STATUSES:
        status = 'Draft'
    conn.execute(
        "UPDATE sales_quote SET customer=%s, description=%s, amount=%s,"
        " owner=%s, quote_date=%s, valid_until=%s, status=%s, notes=%s"
        " WHERE id=%s",
        (customer, description or '', float(amount or 0),
         owner or '', quote_date or _today(),
         valid_until or '', status, notes or '', quote_id)
    )


def set_quote_status(conn, quote_id, status):
    if status not in QUOTE_STATUSES:
        status = 'Draft'
    conn.execute(
        "UPDATE sales_quote SET status=%s WHERE id=%s", (status, quote_id)
    )


# ---------------------------------------------------------------------------
# Sales Targets
# ---------------------------------------------------------------------------

def list_targets(conn, rep=None, period=None):
    conds, params = [], []
    if rep:
        conds.append('rep = %s')
        params.append(rep)
    if period:
        conds.append('period = %s')
        params.append(period)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(
        f"SELECT *, (actual - target) AS variance FROM sales_target {where}"
        f" ORDER BY period DESC, rep ASC",
        params or None
    ).fetchall()


def create_target(conn, rep, period, target, actual, region, status, notes, created_by):
    if not rep:
        raise ValueError('Rep name is required')
    if status not in TARGET_STATUSES:
        status = 'On Track'
    row = conn.execute(
        "INSERT INTO sales_target (rep, period, target, actual, region,"
        " status, notes, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (rep, period or '', float(target or 0), float(actual or 0),
         region or '', status, notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_target(conn, target_id, rep, period, target, actual,
                  region, status, notes):
    if not rep:
        raise ValueError('Rep name is required')
    if status not in TARGET_STATUSES:
        status = 'On Track'
    conn.execute(
        "UPDATE sales_target SET rep=%s, period=%s, target=%s, actual=%s,"
        " region=%s, status=%s, notes=%s WHERE id=%s",
        (rep, period or '', float(target or 0), float(actual or 0),
         region or '', status, notes or '', target_id)
    )
