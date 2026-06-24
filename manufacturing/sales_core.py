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


# ---------------------------------------------------------------------------
# Leads & Opportunities
# ---------------------------------------------------------------------------

SALES_LEAD_STATUSES = ('New', 'Contacted', 'Qualified', 'Proposal', 'Won', 'Lost')
SALES_LEAD_SOURCES = (
    'Website', 'Referral', 'Cold Call', 'Trade Show', 'Email Campaign',
    'Social Media', 'Partner', 'Other',
)
SALES_LEAD_PRIORITIES = ('Low', 'Medium', 'High')


def list_sales_leads(conn, status=None, owner=None, search=None) -> list:
    sql = (
        "SELECT id, company, contact, source, status, priority, "
        "estimated_value, owner, created_date "
        "FROM sales_lead WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if owner:
        sql += " AND owner ILIKE %s"
        params.append(f"%{owner}%")
    if search:
        sql += " AND (company ILIKE %s OR contact ILIKE %s OR notes ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY created_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_sales_lead(conn, lead_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sales_lead WHERE id = %s", (lead_id,)
    ).fetchone()
    return dict(row) if row else None


def create_sales_lead(conn, company: str, contact: str, source: str,
                      status: str, priority: str, estimated_value: float,
                      owner: str, notes: str, created_by: str) -> int:
    if not company.strip():
        raise ValueError("Company is required.")
    row = conn.execute(
        "INSERT INTO sales_lead "
        "(company, contact, source, status, priority, estimated_value, "
        "owner, notes, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE) RETURNING id",
        (company.strip(), contact, source, status or 'New',
         priority or 'Medium', float(estimated_value or 0),
         owner, notes, created_by),
    ).fetchone()
    return row['id']


def update_sales_lead(conn, lead_id: int, **fields) -> None:
    allowed = {
        'company', 'contact', 'source', 'status', 'priority',
        'estimated_value', 'owner', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE sales_lead SET {set_clause} WHERE id = %s",
        list(cols.values()) + [lead_id],
    )


def init_sales_lead_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_lead (
            id               SERIAL PRIMARY KEY,
            company          TEXT NOT NULL,
            contact          TEXT DEFAULT '',
            source           TEXT DEFAULT '',
            status           TEXT DEFAULT 'New',
            priority         TEXT DEFAULT 'Medium',
            estimated_value  REAL DEFAULT 0,
            owner            TEXT DEFAULT '',
            notes            TEXT DEFAULT '',
            created_by       TEXT DEFAULT '',
            created_date     TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Sales Contracts
# ---------------------------------------------------------------------------

SALES_CONTRACT_STATUSES = (
    'Draft', 'Pending Approval', 'Active', 'Expired', 'Cancelled', 'Renewed',
)


def list_sales_contracts(conn, status=None, search=None) -> list:
    sql = (
        "SELECT id, customer, title, value, start_date, end_date, "
        "renewal_date, status, owner "
        "FROM sales_contract WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (customer ILIKE %s OR title ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY end_date ASC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_sales_contract(conn, contract_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sales_contract WHERE id = %s", (contract_id,)
    ).fetchone()
    return dict(row) if row else None


def create_sales_contract(conn, customer: str, title: str, value: float,
                          start_date: str, end_date: str, renewal_date: str,
                          status: str, owner: str, notes: str,
                          created_by: str) -> int:
    if not customer.strip():
        raise ValueError("Customer is required.")
    row = conn.execute(
        "INSERT INTO sales_contract "
        "(customer, title, value, start_date, end_date, renewal_date, "
        "status, owner, notes, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE) RETURNING id",
        (customer.strip(), title, float(value or 0),
         start_date or None, end_date or None, renewal_date or None,
         status or 'Draft', owner, notes, created_by),
    ).fetchone()
    return row['id']


def update_sales_contract(conn, contract_id: int, **fields) -> None:
    allowed = {
        'customer', 'title', 'value', 'start_date', 'end_date',
        'renewal_date', 'status', 'owner', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE sales_contract SET {set_clause} WHERE id = %s",
        list(cols.values()) + [contract_id],
    )


def init_sales_contract_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_contract (
            id            SERIAL PRIMARY KEY,
            customer      TEXT NOT NULL,
            title         TEXT DEFAULT '',
            value         REAL DEFAULT 0,
            start_date    TEXT,
            end_date      TEXT,
            renewal_date  TEXT,
            status        TEXT DEFAULT 'Draft',
            owner         TEXT DEFAULT '',
            notes         TEXT DEFAULT '',
            created_by    TEXT DEFAULT '',
            created_date  TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Sales Forecasting
# ---------------------------------------------------------------------------

FORECAST_PERIODS = (
    'Q1', 'Q2', 'Q3', 'Q4',
    'H1', 'H2', 'Annual',
)
FORECAST_STATUSES = ('Draft', 'Submitted', 'Approved', 'Revised')


def list_forecasts(conn, rep=None, period=None, search=None) -> list:
    sql = (
        "SELECT id, rep, period, fiscal_year, product_line, "
        "expected_value, probability, weighted_value, status "
        "FROM sales_forecast WHERE TRUE"
    )
    params: list = []
    if rep:
        sql += " AND rep ILIKE %s"
        params.append(f"%{rep}%")
    if period:
        sql += " AND period = %s"
        params.append(period)
    if search:
        sql += " AND (rep ILIKE %s OR product_line ILIKE %s OR notes ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY fiscal_year DESC, period, rep"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_forecast(conn, forecast_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sales_forecast WHERE id = %s", (forecast_id,)
    ).fetchone()
    return dict(row) if row else None


def create_forecast(conn, rep: str, period: str, fiscal_year: int,
                    product_line: str, expected_value: float,
                    probability: int, status: str, notes: str,
                    created_by: str) -> int:
    weighted = float(expected_value or 0) * int(probability or 0) / 100
    row = conn.execute(
        "INSERT INTO sales_forecast "
        "(rep, period, fiscal_year, product_line, expected_value, "
        "probability, weighted_value, status, notes, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE) RETURNING id",
        (rep, period, fiscal_year or date.today().year,
         product_line, float(expected_value or 0),
         int(probability or 0), weighted,
         status or 'Draft', notes, created_by),
    ).fetchone()
    return row['id']


def update_forecast(conn, forecast_id: int, **fields) -> None:
    allowed = {
        'rep', 'period', 'fiscal_year', 'product_line',
        'expected_value', 'probability', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'expected_value' in cols or 'probability' in cols:
        cols['weighted_value'] = (
            float(cols.get('expected_value', 0)) *
            int(cols.get('probability', 0)) / 100
        )
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE sales_forecast SET {set_clause} WHERE id = %s",
        list(cols.values()) + [forecast_id],
    )


def init_sales_forecast_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_forecast (
            id              SERIAL PRIMARY KEY,
            rep             TEXT DEFAULT '',
            period          TEXT DEFAULT '',
            fiscal_year     INTEGER,
            product_line    TEXT DEFAULT '',
            expected_value  REAL DEFAULT 0,
            probability     INTEGER DEFAULT 0,
            weighted_value  REAL DEFAULT 0,
            status          TEXT DEFAULT 'Draft',
            notes           TEXT DEFAULT '',
            created_by      TEXT DEFAULT '',
            created_date    TEXT DEFAULT ''
        )
    """)
