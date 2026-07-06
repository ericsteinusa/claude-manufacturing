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

from datetime import date, timedelta

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


def get_revenue_by_month(conn, months: int = 6) -> list[dict]:
    """Return [{month, revenue}] — SO revenue by month over the last
    ``months`` months, for a revenue-by-period chart."""
    start = (date.today().replace(day=1) - timedelta(days=31 * (months - 1))).isoformat()
    rows = conn.execute("""
        SELECT to_char(date_trunc('month', so.order_date::date), 'YYYY-MM') AS month,
               COALESCE(SUM(si.qty * si.unit_price), 0) AS revenue
        FROM sales_order so
        LEFT JOIN so_item si ON si.so_id = so.id
        WHERE so.order_date IS NOT NULL AND so.order_date >= %s
        GROUP BY date_trunc('month', so.order_date::date)
        ORDER BY date_trunc('month', so.order_date::date)
    """, (start,)).fetchall()
    return [dict(r) for r in rows]


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
            actual_value    REAL DEFAULT 0,
            status          TEXT DEFAULT 'Draft',
            notes           TEXT DEFAULT '',
            created_by      TEXT DEFAULT '',
            created_date    TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "ALTER TABLE sales_forecast ADD COLUMN IF NOT EXISTS actual_value REAL DEFAULT 0"
    )


def get_forecast_kpis(conn, period=None, search=None) -> dict:
    sql = (
        "SELECT COUNT(*) AS cnt,"
        " COALESCE(SUM(expected_value),0) AS total_expected,"
        " COALESCE(SUM(weighted_value),0) AS total_weighted,"
        " COALESCE(AVG(probability),0) AS avg_prob,"
        " COALESCE(SUM(actual_value),0) AS total_actual"
        " FROM sales_forecast WHERE TRUE"
    )
    params: list = []
    if period:
        sql += " AND period = %s"
        params.append(period)
    if search:
        sql += " AND (rep ILIKE %s OR product_line ILIKE %s OR notes ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    row = conn.execute(sql, params).fetchone()
    if not row:
        return {}
    d = dict(row)
    d['total_variance'] = float(d['total_actual']) - float(d['total_weighted'])
    return d


def get_period_actuals(conn, fiscal_year: int) -> dict:
    """Return {period: revenue} for closed/shipped SOs in fiscal_year."""
    try:
        rows = conn.execute("""
            SELECT EXTRACT(MONTH FROM order_date::date)::int AS mo,
                   COALESCE(SUM(si.qty * si.unit_price), 0) AS rev
            FROM sales_order so
            JOIN so_item si ON si.so_id = so.id
            WHERE order_date IS NOT NULL AND order_date != ''
              AND LOWER(so.status) IN ('closed','shipped','delivered','complete','completed')
              AND EXTRACT(YEAR FROM order_date::date)::int = %s
            GROUP BY 1
        """, [fiscal_year]).fetchall()
    except Exception:
        return {}
    by_month = {r['mo']: float(r['rev']) for r in rows}

    def _sum(*months):
        return sum(by_month.get(m, 0.0) for m in months)

    return {
        'Q1':     _sum(1, 2, 3),
        'Q2':     _sum(4, 5, 6),
        'Q3':     _sum(7, 8, 9),
        'Q4':     _sum(10, 11, 12),
        'H1':     _sum(*range(1, 7)),
        'H2':     _sum(*range(7, 13)),
        'Annual': _sum(*range(1, 13)),
    }


def get_demand_by_product(conn, fiscal_year: int) -> list:
    """Demand by product × quarter for fiscal_year, from actual SOs."""
    try:
        rows = conn.execute("""
            SELECT COALESCE(p.name, si.description, 'Unknown') AS product,
                   EXTRACT(QUARTER FROM order_date::date)::int AS qtr,
                   COALESCE(SUM(si.qty * si.unit_price), 0)    AS revenue,
                   COALESCE(SUM(si.qty), 0)                    AS units
            FROM sales_order so
            JOIN so_item si ON si.so_id = so.id
            LEFT JOIN product p ON p.id = si.product_id
            WHERE order_date IS NOT NULL AND order_date != ''
              AND EXTRACT(YEAR FROM order_date::date)::int = %s
            GROUP BY 1, 2
            ORDER BY 1, 2
        """, [fiscal_year]).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def update_forecast_actual(conn, forecast_id: int, actual_value: float) -> None:
    conn.execute(
        "UPDATE sales_forecast SET actual_value = %s WHERE id = %s",
        [actual_value, forecast_id],
    )


# ---------------------------------------------------------------------------
# Territory Management
# ---------------------------------------------------------------------------

TERRITORY_STATUSES = ('Active', 'Inactive', 'Under Review')


def init_sales_territory_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_territory (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            region       TEXT DEFAULT '',
            assigned_rep TEXT DEFAULT '',
            status       TEXT DEFAULT 'Active',
            notes        TEXT DEFAULT '',
            created_by   TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)


def list_territories(conn, status=None, search=None) -> list:
    sql = "SELECT * FROM sales_territory WHERE TRUE"
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (name ILIKE %s OR region ILIKE %s OR assigned_rep ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY region, name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_territory(conn, territory_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sales_territory WHERE id = %s", (territory_id,)
    ).fetchone()
    return dict(row) if row else None


def create_territory(conn, name: str, region: str, assigned_rep: str,
                     status: str, notes: str, created_by: str) -> int:
    if not name.strip():
        raise ValueError("Territory name is required.")
    if status not in TERRITORY_STATUSES:
        status = 'Active'
    row = conn.execute(
        "INSERT INTO sales_territory (name, region, assigned_rep, status, notes,"
        " created_by, created_date) VALUES (%s,%s,%s,%s,%s,%s,CURRENT_DATE)"
        " RETURNING id",
        (name.strip(), region, assigned_rep, status, notes, created_by),
    ).fetchone()
    return row['id']


def update_territory(conn, territory_id: int, name: str, region: str,
                     assigned_rep: str, status: str, notes: str) -> None:
    if not name.strip():
        raise ValueError("Territory name is required.")
    if status not in TERRITORY_STATUSES:
        status = 'Active'
    conn.execute(
        "UPDATE sales_territory SET name=%s, region=%s, assigned_rep=%s,"
        " status=%s, notes=%s WHERE id=%s",
        (name.strip(), region, assigned_rep, status, notes, territory_id),
    )


def get_territory_performance(conn) -> list:
    """Aggregate sales order totals per territory for the performance view."""
    rows = conn.execute("""
        SELECT
            t.id,
            t.name,
            t.region,
            t.assigned_rep,
            t.status
        FROM sales_territory t
        ORDER BY t.region, t.name
    """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Commission Tracking
# ---------------------------------------------------------------------------

COMMISSION_PLAN_TYPES = ('Flat Rate', 'Tiered', 'Quota-Based', 'Hybrid')
COMMISSION_STATUSES = ('Pending', 'Approved', 'Paid', 'Voided')


def init_commission_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_commission_plan (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            plan_type    TEXT DEFAULT 'Flat Rate',
            rate         REAL DEFAULT 0,
            description  TEXT DEFAULT '',
            active       BOOLEAN DEFAULT TRUE,
            created_by   TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_commission (
            id           SERIAL PRIMARY KEY,
            rep          TEXT NOT NULL,
            period       TEXT DEFAULT '',
            plan_id      INTEGER,
            sale_amount  REAL DEFAULT 0,
            commission   REAL DEFAULT 0,
            status       TEXT DEFAULT 'Pending',
            notes        TEXT DEFAULT '',
            created_by   TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)


def list_commission_plans(conn, active_only=False) -> list:
    sql = "SELECT * FROM sales_commission_plan WHERE TRUE"
    if active_only:
        sql += " AND active = TRUE"
    sql += " ORDER BY name"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_commission_plan(conn, plan_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sales_commission_plan WHERE id = %s", (plan_id,)
    ).fetchone()
    return dict(row) if row else None


def create_commission_plan(conn, name: str, plan_type: str, rate: float,
                           description: str, created_by: str) -> int:
    if not name.strip():
        raise ValueError("Plan name is required.")
    if plan_type not in COMMISSION_PLAN_TYPES:
        plan_type = 'Flat Rate'
    row = conn.execute(
        "INSERT INTO sales_commission_plan (name, plan_type, rate, description,"
        " created_by, created_date) VALUES (%s,%s,%s,%s,%s,CURRENT_DATE)"
        " RETURNING id",
        (name.strip(), plan_type, float(rate or 0), description, created_by),
    ).fetchone()
    return row['id']


def update_commission_plan(conn, plan_id: int, name: str, plan_type: str,
                           rate: float, description: str, active: bool) -> None:
    if not name.strip():
        raise ValueError("Plan name is required.")
    conn.execute(
        "UPDATE sales_commission_plan SET name=%s, plan_type=%s, rate=%s,"
        " description=%s, active=%s WHERE id=%s",
        (name.strip(), plan_type, float(rate or 0), description, active, plan_id),
    )


def list_commissions(conn, rep=None, period=None, status=None) -> list:
    sql = (
        "SELECT c.*, p.name AS plan_name, p.rate AS plan_rate "
        "FROM sales_commission c "
        "LEFT JOIN sales_commission_plan p ON p.id = c.plan_id "
        "WHERE TRUE"
    )
    params: list = []
    if rep:
        sql += " AND c.rep ILIKE %s"
        params.append(f"%{rep}%")
    if period:
        sql += " AND c.period = %s"
        params.append(period)
    if status:
        sql += " AND c.status = %s"
        params.append(status)
    sql += " ORDER BY c.period DESC, c.rep"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_commission(conn, rep: str, period: str, plan_id,
                      sale_amount: float, commission: float,
                      status: str, notes: str, created_by: str) -> int:
    if not rep.strip():
        raise ValueError("Rep is required.")
    if status not in COMMISSION_STATUSES:
        status = 'Pending'
    row = conn.execute(
        "INSERT INTO sales_commission (rep, period, plan_id, sale_amount,"
        " commission, status, notes, created_by, created_date)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE) RETURNING id",
        (rep.strip(), period, plan_id or None, float(sale_amount or 0),
         float(commission or 0), status, notes, created_by),
    ).fetchone()
    return row['id']


def update_commission(conn, commission_id: int, rep: str, period: str,
                      plan_id, sale_amount: float, commission: float,
                      status: str, notes: str) -> None:
    if not rep.strip():
        raise ValueError("Rep is required.")
    if status not in COMMISSION_STATUSES:
        status = 'Pending'
    conn.execute(
        "UPDATE sales_commission SET rep=%s, period=%s, plan_id=%s,"
        " sale_amount=%s, commission=%s, status=%s, notes=%s WHERE id=%s",
        (rep.strip(), period, plan_id or None, float(sale_amount or 0),
         float(commission or 0), status, notes, commission_id),
    )


def get_commission_summary(conn) -> dict:
    """Summary stats for the commission dashboard."""
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(commission) FILTER (WHERE status='Pending'), 0) AS pending_amount,
            COALESCE(SUM(commission) FILTER (WHERE status='Approved'), 0) AS approved_amount,
            COALESCE(SUM(commission) FILTER (WHERE status='Paid'), 0) AS paid_amount,
            COALESCE(SUM(sale_amount), 0) AS total_sales
        FROM sales_commission
    """).fetchone()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Sales Performance
# ---------------------------------------------------------------------------

def get_sales_performance(conn) -> dict:
    """Aggregate performance data for the performance dashboard."""
    rep_rows = conn.execute("""
        SELECT
            st.rep,
            COALESCE(SUM(st.target), 0) AS total_target,
            COALESCE(SUM(st.actual), 0) AS total_actual,
            COALESCE(SUM(st.actual) - SUM(st.target), 0) AS variance,
            CASE WHEN SUM(st.target) > 0
                 THEN ROUND((SUM(st.actual) / SUM(st.target) * 100)::numeric, 1)
                 ELSE 0 END AS attainment_pct
        FROM sales_target st
        GROUP BY st.rep
        ORDER BY attainment_pct DESC
    """).fetchall()

    so_rep_rows = conn.execute("""
        SELECT
            so.sales_rep,
            COUNT(so.id) AS order_count,
            COALESCE(SUM(si.qty * si.unit_price), 0) AS revenue
        FROM sales_order so
        LEFT JOIN so_item si ON si.so_id = so.id
        WHERE so.sales_rep IS NOT NULL AND so.sales_rep != ''
        GROUP BY so.sales_rep
        ORDER BY revenue DESC
    """).fetchall()

    return {
        'rep_targets': [dict(r) for r in rep_rows],
        'rep_orders': [dict(r) for r in so_rep_rows],
    }


COACHING_NOTE_STATUSES = ('Open', 'In Progress', 'Resolved')
PERF_REVIEW_STATUSES = ('Scheduled', 'Completed', 'Cancelled')


def init_sales_performance_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_coaching_note (
            id           SERIAL PRIMARY KEY,
            rep          TEXT NOT NULL,
            subject      TEXT DEFAULT '',
            note         TEXT DEFAULT '',
            status       TEXT DEFAULT 'Open',
            coach        TEXT DEFAULT '',
            created_by   TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_perf_review (
            id            SERIAL PRIMARY KEY,
            rep           TEXT NOT NULL,
            review_date   TEXT DEFAULT '',
            period        TEXT DEFAULT '',
            rating        TEXT DEFAULT '',
            strengths     TEXT DEFAULT '',
            improvements  TEXT DEFAULT '',
            goals         TEXT DEFAULT '',
            status        TEXT DEFAULT 'Scheduled',
            reviewer      TEXT DEFAULT '',
            created_by    TEXT DEFAULT '',
            created_date  TEXT DEFAULT ''
        )
    """)


def list_coaching_notes(conn, rep=None, status=None) -> list:
    sql = "SELECT * FROM sales_coaching_note WHERE TRUE"
    params: list = []
    if rep:
        sql += " AND rep ILIKE %s"
        params.append(f"%{rep}%")
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY created_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_coaching_note(conn, rep: str, subject: str, note: str,
                         status: str, coach: str, created_by: str) -> int:
    if not rep.strip():
        raise ValueError("Rep is required.")
    row = conn.execute(
        "INSERT INTO sales_coaching_note (rep, subject, note, status, coach,"
        " created_by, created_date) VALUES (%s,%s,%s,%s,%s,%s,CURRENT_DATE)"
        " RETURNING id",
        (rep.strip(), subject, note, status or 'Open', coach, created_by),
    ).fetchone()
    return row['id']


def list_perf_reviews(conn, rep=None, status=None) -> list:
    sql = "SELECT * FROM sales_perf_review WHERE TRUE"
    params: list = []
    if rep:
        sql += " AND rep ILIKE %s"
        params.append(f"%{rep}%")
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY review_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_perf_review(conn, rep: str, review_date: str, period: str,
                       rating: str, strengths: str, improvements: str,
                       goals: str, status: str, reviewer: str,
                       created_by: str) -> int:
    if not rep.strip():
        raise ValueError("Rep is required.")
    row = conn.execute(
        "INSERT INTO sales_perf_review (rep, review_date, period, rating,"
        " strengths, improvements, goals, status, reviewer, created_by,"
        " created_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE)"
        " RETURNING id",
        (rep.strip(), review_date, period, rating, strengths, improvements,
         goals, status or 'Scheduled', reviewer, created_by),
    ).fetchone()
    return row['id']
