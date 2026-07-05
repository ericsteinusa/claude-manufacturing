"""
production_core.py — Qt-free production data layer.

Aggregates KPIs from work_order, product (inventory), and bom tables
for the production dashboard view.  Deeper operations (CRUD, MRP run,
BOM explosion) live in their respective *_core modules.
"""

from datetime import date, timedelta


def get_production_dashboard(conn) -> dict:
    """Return a dict with keys: work_orders, inventory, recent_wos.

    work_orders: {draft, open, in_progress, completed_today, overdue, total}
    inventory:   {total_products, zero_stock, low_stock}
    recent_wos:  list of last 8 WO rows (id, wo_number, description,
                 due_date, status, product_name)
    """
    today = date.today().isoformat()

    wo_row = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE status = 'draft') AS draft, "
        "COUNT(*) FILTER (WHERE status = 'open') AS open, "
        "COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress, "
        "COUNT(*) FILTER (WHERE status = 'completed' "
        "                 AND due_date = %s) AS completed_today, "
        "COUNT(*) FILTER (WHERE status NOT IN ('completed','cancelled') "
        "                 AND due_date IS NOT NULL "
        "                 AND due_date < %s) AS overdue, "
        "COUNT(*) AS total "
        "FROM work_order",
        (today, today),
    ).fetchone()

    inv_row = conn.execute(
        "SELECT "
        "COUNT(*) AS total_products, "
        "COUNT(*) FILTER (WHERE COALESCE(amount,0) <= 0) AS zero_stock, "
        "COUNT(*) FILTER (WHERE COALESCE(amount,0) > 0 "
        "                 AND reorder_point > 0 "
        "                 AND COALESCE(amount,0) <= reorder_point) AS low_stock "
        "FROM product"
    ).fetchone()

    recent_rows = conn.execute(
        "SELECT wo.id, wo.wo_number, wo.description, wo.due_date, wo.status, "
        "p.name AS product_name "
        "FROM work_order wo "
        "LEFT JOIN product p ON p.id = wo.product_id "
        "ORDER BY wo.id DESC LIMIT 8"
    ).fetchall()

    return {
        'work_orders': dict(wo_row) if wo_row else {},
        'inventory': dict(inv_row) if inv_row else {},
        'recent_wos': [dict(r) for r in recent_rows],
    }


def get_daily_output_trend(conn, days: int = 14) -> list[dict]:
    """Return [{date, qty}] — units completed per day over the last
    ``days`` days, using due_date as the completion-date proxy (work_order
    has no separate completed-date column; get_production_dashboard's
    'completed_today' filter above uses the same convention).
    """
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT due_date AS day, COALESCE(SUM(quantity), 0) AS qty "
        "FROM work_order "
        "WHERE status = 'completed' AND due_date >= %s "
        "GROUP BY due_date ORDER BY due_date",
        (start,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_wo_status_breakdown(conn) -> list[dict]:
    """Return [{status, cnt}] — work order count by status, for a
    completion-rate chart on the production dashboard."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM work_order "
        "GROUP BY status ORDER BY status"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Production Schedule
# ---------------------------------------------------------------------------

def list_scheduled_wos(conn, date_from=None, date_to=None, status=None) -> list:
    conds, params = [], []
    if date_from:
        conds.append("wo.due_date >= %s")
        params.append(date_from)
    if date_to:
        conds.append("wo.due_date <= %s")
        params.append(date_to)
    if status:
        conds.append("wo.status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return [dict(r) for r in conn.execute(f"""
        SELECT wo.id, wo.wo_number, wo.description, wo.due_date,
               wo.quantity, wo.status,
               p.name AS product_name
        FROM work_order wo
        LEFT JOIN product p ON p.id = wo.product_id
        {where}
        ORDER BY wo.due_date ASC NULLS LAST, wo.id DESC
    """, params or None).fetchall()]


# ---------------------------------------------------------------------------
# Production Reports
# ---------------------------------------------------------------------------

def get_prod_reports(conn) -> dict:
    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    month_start = date.today().replace(day=1).isoformat()

    by_status = conn.execute("""
        SELECT status, COUNT(*) AS cnt FROM work_order GROUP BY status ORDER BY status
    """).fetchall()

    completed_today = conn.execute(
        "SELECT COUNT(*) AS cnt FROM work_order WHERE status='completed' AND due_date=%s",
        (today,)
    ).fetchone()

    completed_week = conn.execute(
        "SELECT COUNT(*) AS cnt FROM work_order "
        "WHERE status='completed' AND due_date >= %s",
        (week_start,)
    ).fetchone()

    completed_month = conn.execute(
        "SELECT COUNT(*) AS cnt FROM work_order "
        "WHERE status='completed' AND due_date >= %s",
        (month_start,)
    ).fetchone()

    overdue = conn.execute(
        "SELECT wo.id, wo.wo_number, wo.description, wo.due_date, wo.status, "
        "p.name AS product_name "
        "FROM work_order wo LEFT JOIN product p ON p.id = wo.product_id "
        "WHERE wo.status NOT IN ('completed','cancelled') "
        "AND wo.due_date IS NOT NULL AND wo.due_date < %s "
        "ORDER BY wo.due_date ASC LIMIT 20",
        (today,)
    ).fetchall()

    low_stock = conn.execute(
        "SELECT id, name, amount, reorder_point, bin "
        "FROM product "
        "WHERE COALESCE(amount,0) <= reorder_point AND reorder_point > 0 "
        "ORDER BY (reorder_point - COALESCE(amount,0)) DESC LIMIT 15"
    ).fetchall()

    return {
        'by_status': [dict(r) for r in by_status],
        'completed_today': (completed_today['cnt'] if completed_today else 0),
        'completed_week':  (completed_week['cnt']  if completed_week  else 0),
        'completed_month': (completed_month['cnt'] if completed_month else 0),
        'overdue': [dict(r) for r in overdue],
        'low_stock': [dict(r) for r in low_stock],
    }


# ---------------------------------------------------------------------------
# Shipping
# ---------------------------------------------------------------------------

SHIPMENT_STATUSES = ('pending', 'in_transit', 'delivered', 'cancelled')


def _today_str() -> str:
    return date.today().isoformat()


def _next_ship_number(conn) -> str:
    yr = date.today().year
    prefix = f"SH-{yr}-"
    rows = conn.execute(
        "SELECT ship_number FROM shipment WHERE ship_number LIKE %s",
        (f"{prefix}%",)
    ).fetchall()
    nums = []
    for r in rows:
        tail = r['ship_number'][len(prefix):]
        if tail.isdigit():
            nums.append(int(tail))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


def list_shipments(conn, status=None, search=None) -> list:
    conds, params = [], []
    if status:
        conds.append("s.status = %s")
        params.append(status)
    if search:
        conds.append("(s.ship_number ILIKE %s OR s.carrier ILIKE %s OR s.tracking_number ILIKE %s)")
        params.extend([f"%{search}%"] * 3)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return [dict(r) for r in conn.execute(f"""
        SELECT s.id, s.ship_number, s.ship_date, s.carrier,
               s.tracking_number, s.status, s.notes,
               so.so_number
        FROM shipment s
        LEFT JOIN sales_order so ON so.id = s.so_id
        {where}
        ORDER BY s.ship_date DESC NULLS LAST, s.id DESC
    """, params or None).fetchall()]


def get_shipment(conn, shipment_id: int) -> dict | None:
    row = conn.execute("""
        SELECT s.*, so.so_number
        FROM shipment s
        LEFT JOIN sales_order so ON so.id = s.so_id
        WHERE s.id = %s
    """, (shipment_id,)).fetchone()
    return dict(row) if row else None


def get_shipment_items(conn, shipment_id: int) -> list:
    return [dict(r) for r in conn.execute("""
        SELECT si.id, si.shipment_id, si.description, si.qty,
               p.name AS product_name
        FROM shipment_item si
        LEFT JOIN product p ON p.id = si.product_id
        WHERE si.shipment_id = %s
        ORDER BY si.id
    """, (shipment_id,)).fetchall()]


def create_shipment(conn, so_id, ship_date: str, carrier: str,
                    tracking_number: str, status: str,
                    notes: str, created_by: str) -> int:
    ship_number = _next_ship_number(conn)
    row = conn.execute(
        "INSERT INTO shipment "
        "(ship_number, so_id, ship_date, carrier, tracking_number, "
        "status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (ship_number, so_id or None, ship_date or _today_str(),
         carrier or '', tracking_number or '',
         status or 'pending', notes or '', created_by or '')
    ).fetchone()
    return row['id']


def update_shipment(conn, shipment_id: int, **fields) -> None:
    allowed = {'ship_date', 'carrier', 'tracking_number', 'status', 'notes', 'so_id'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE shipment SET {set_clause} WHERE id = %s",
        list(cols.values()) + [shipment_id],
    )


def add_shipment_item(conn, shipment_id: int, description: str,
                      product_id, qty: int) -> int:
    if not description.strip():
        raise ValueError("Description is required.")
    row = conn.execute(
        "INSERT INTO shipment_item (shipment_id, description, product_id, qty) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (shipment_id, description.strip(), product_id or None, qty or 1)
    ).fetchone()
    return row['id']


def init_shipment_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment (
            id              SERIAL PRIMARY KEY,
            ship_number     TEXT NOT NULL,
            so_id           INTEGER,
            ship_date       TEXT,
            carrier         TEXT DEFAULT '',
            tracking_number TEXT DEFAULT '',
            status          TEXT DEFAULT 'pending',
            notes           TEXT DEFAULT '',
            created_by      TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment_item (
            id          SERIAL PRIMARY KEY,
            shipment_id INTEGER NOT NULL REFERENCES shipment(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            product_id  INTEGER,
            qty         INTEGER DEFAULT 1
        )
    """)


# ---------------------------------------------------------------------------
# Tracking Dashboard
# ---------------------------------------------------------------------------

def get_tracking_dashboard(conn) -> dict:
    """Return summary data for the shipping tracking dashboard."""
    rows = conn.execute("""
        SELECT s.id, s.ship_number, s.ship_date, s.carrier,
               s.tracking_number, s.status, s.notes,
               so.so_number, so.id AS so_id
        FROM shipment s
        LEFT JOIN sales_order so ON so.id = s.so_id
        ORDER BY s.ship_date DESC NULLS LAST, s.id DESC
        LIMIT 50
    """).fetchall()

    counts = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending')    AS pending,
            COUNT(*) FILTER (WHERE status = 'in_transit') AS in_transit,
            COUNT(*) FILTER (WHERE status = 'delivered')  AS delivered,
            COUNT(*) FILTER (WHERE status = 'cancelled')  AS cancelled,
            COUNT(*)                                       AS total
        FROM shipment
    """).fetchone()

    return {
        'shipments': [dict(r) for r in rows],
        'counts': dict(counts) if counts else {},
    }


def get_delivery_status(conn, status_filter=None, search=None) -> list:
    """List shipments with delivery status details."""
    conds, params = [], []
    if status_filter:
        conds.append("s.status = %s")
        params.append(status_filter)
    if search:
        conds.append(
            "(s.ship_number ILIKE %s OR s.carrier ILIKE %s "
            "OR s.tracking_number ILIKE %s)"
        )
        params.extend([f"%{search}%"] * 3)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return [dict(r) for r in conn.execute(f"""
        SELECT s.id, s.ship_number, s.ship_date, s.carrier,
               s.tracking_number, s.status, s.notes,
               so.so_number, so.id AS so_id
        FROM shipment s
        LEFT JOIN sales_order so ON so.id = s.so_id
        {where}
        ORDER BY s.ship_date DESC NULLS LAST, s.id DESC
    """, params or None).fetchall()]


# ---------------------------------------------------------------------------
# Daily Production Report
# ---------------------------------------------------------------------------

def get_daily_report(conn, report_date: str | None = None) -> dict:
    """Aggregate production metrics for a single day (default: today)."""
    if not report_date:
        report_date = date.today().isoformat()

    completed = conn.execute(
        "SELECT COUNT(*) AS cnt FROM work_order "
        "WHERE status = 'completed' AND due_date = %s",
        (report_date,),
    ).fetchone()

    started = conn.execute(
        "SELECT COUNT(*) AS cnt FROM work_order "
        "WHERE status = 'in_progress' AND due_date = %s",
        (report_date,),
    ).fetchone()

    opened = conn.execute(
        "SELECT COUNT(*) AS cnt FROM work_order "
        "WHERE status = 'open' AND due_date = %s",
        (report_date,),
    ).fetchone()

    wo_detail = conn.execute(
        "SELECT wo.id, wo.wo_number, wo.description, wo.quantity, "
        "wo.status, p.name AS product_name "
        "FROM work_order wo "
        "LEFT JOIN product p ON p.id = wo.product_id "
        "WHERE wo.due_date = %s "
        "ORDER BY wo.status, wo.id",
        (report_date,),
    ).fetchall()

    shipments_today = conn.execute(
        "SELECT COUNT(*) AS cnt FROM shipment WHERE ship_date = %s",
        (report_date,),
    ).fetchone()

    return {
        'report_date': report_date,
        'completed_count': completed['cnt'] if completed else 0,
        'started_count': started['cnt'] if started else 0,
        'opened_count': opened['cnt'] if opened else 0,
        'wo_detail': [dict(r) for r in wo_detail],
        'shipments_today': shipments_today['cnt'] if shipments_today else 0,
    }


# ---------------------------------------------------------------------------
# Performance Report
# ---------------------------------------------------------------------------

def get_performance_report(conn, days: int = 30) -> dict:
    """Return on-time delivery and WO completion metrics for the last N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    today = date.today().isoformat()

    wo_stats = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'completed') AS completed, "
        "COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled, "
        "COUNT(*) FILTER (WHERE status NOT IN ('completed','cancelled') "
        "                 AND due_date < %s) AS overdue "
        "FROM work_order "
        "WHERE due_date >= %s",
        (today, cutoff),
    ).fetchone()

    shipped = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'delivered') AS delivered "
        "FROM shipment WHERE ship_date >= %s",
        (cutoff,),
    ).fetchone()

    top_products = conn.execute(
        "SELECT p.name AS product_name, COUNT(*) AS cnt "
        "FROM work_order wo "
        "LEFT JOIN product p ON p.id = wo.product_id "
        "WHERE wo.status = 'completed' AND wo.due_date >= %s "
        "GROUP BY p.name ORDER BY cnt DESC LIMIT 10",
        (cutoff,),
    ).fetchall()

    return {
        'days': days,
        'cutoff': cutoff,
        'wo_stats': dict(wo_stats) if wo_stats else {},
        'shipped': dict(shipped) if shipped else {},
        'top_products': [dict(r) for r in top_products],
    }


# ---------------------------------------------------------------------------
# Returns / RMA
# ---------------------------------------------------------------------------

RMA_STATUSES = ('pending', 'approved', 'received', 'inspecting',
                'resolved', 'rejected')
RMA_REASONS = ('defective', 'wrong_item', 'damaged_in_transit',
               'not_as_described', 'customer_changed_mind', 'other')


def init_rma_table(conn) -> None:
    """Create the rma table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rma (
            id           SERIAL PRIMARY KEY,
            rma_number   TEXT NOT NULL UNIQUE,
            so_id        INTEGER,
            customer     TEXT DEFAULT '',
            reason       TEXT DEFAULT 'other',
            status       TEXT DEFAULT 'pending',
            description  TEXT DEFAULT '',
            resolution   TEXT DEFAULT '',
            created_at   TEXT,
            created_by   TEXT DEFAULT ''
        )
    """)


def _next_rma_number(conn) -> str:
    yr = date.today().year
    prefix = f"RMA-{yr}-"
    rows = conn.execute(
        "SELECT rma_number FROM rma WHERE rma_number LIKE %s",
        (f"{prefix}%",),
    ).fetchall()
    nums = []
    for r in rows:
        tail = r['rma_number'][len(prefix):]
        if tail.isdigit():
            nums.append(int(tail))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


def list_rmas(conn, status=None, search=None) -> list:
    conds, params = [], []
    if status:
        conds.append("r.status = %s")
        params.append(status)
    if search:
        conds.append(
            "(r.rma_number ILIKE %s OR r.customer ILIKE %s "
            "OR r.description ILIKE %s)"
        )
        params.extend([f"%{search}%"] * 3)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return [dict(r) for r in conn.execute(f"""
        SELECT r.id, r.rma_number, r.customer, r.reason, r.status,
               r.description, r.resolution, r.created_at,
               so.so_number, so.id AS so_id
        FROM rma r
        LEFT JOIN sales_order so ON so.id = r.so_id
        {where}
        ORDER BY r.id DESC
    """, params or None).fetchall()]


def get_rma(conn, rma_id: int) -> dict | None:
    row = conn.execute("""
        SELECT r.*, so.so_number, so.id AS so_id
        FROM rma r
        LEFT JOIN sales_order so ON so.id = r.so_id
        WHERE r.id = %s
    """, (rma_id,)).fetchone()
    return dict(row) if row else None


def create_rma(conn, so_id, customer: str, reason: str,
               description: str, created_by: str) -> int:
    rma_number = _next_rma_number(conn)
    row = conn.execute(
        "INSERT INTO rma "
        "(rma_number, so_id, customer, reason, status, description, "
        "resolution, created_at, created_by) "
        "VALUES (%s,%s,%s,%s,'pending',%s,'',%s,%s) RETURNING id",
        (rma_number, so_id or None, customer or '',
         reason or 'other', description or '',
         date.today().isoformat(), created_by or ''),
    ).fetchone()
    return row['id']


def update_rma(conn, rma_id: int, **fields) -> None:
    allowed = {'customer', 'reason', 'status', 'description',
               'resolution', 'so_id'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE rma SET {set_clause} WHERE id = %s",
        list(cols.values()) + [rma_id],
    )


def get_rma_reports(conn) -> dict:
    """Aggregate RMA statistics."""
    by_status = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM rma GROUP BY status ORDER BY status"
    ).fetchall()
    by_reason = conn.execute(
        "SELECT reason, COUNT(*) AS cnt FROM rma GROUP BY reason ORDER BY cnt DESC"
    ).fetchall()
    recent = conn.execute(
        "SELECT r.id, r.rma_number, r.customer, r.reason, r.status, "
        "r.created_at, so.so_number "
        "FROM rma r LEFT JOIN sales_order so ON so.id = r.so_id "
        "ORDER BY r.id DESC LIMIT 20"
    ).fetchall()
    return {
        'by_status': [dict(r) for r in by_status],
        'by_reason': [dict(r) for r in by_reason],
        'recent': [dict(r) for r in recent],
    }
