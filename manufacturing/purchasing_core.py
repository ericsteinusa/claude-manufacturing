"""Qt-free purchasing dashboard data layer."""

from datetime import date

CONTRACT_STATUSES = ('Active', 'Pending Renewal', 'Expired', 'Cancelled')
CONTRACT_CATEGORIES = ('Services', 'Materials', 'Equipment', 'Software', 'Maintenance', 'Other')


def get_purchasing_dashboard(conn) -> dict:
    """Return dict with keys: pos, recent_pos.

    pos: {draft, pending_approval, sent, partial, received, open, total}
    recent_pos: list of last 8 PO rows (id, po_number, order_date,
                expected_date, status, supplier_name)
    """
    po_row = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE status = 'draft') AS draft, "
        "COUNT(*) FILTER (WHERE status = 'pending_approval') AS pending_approval, "
        "COUNT(*) FILTER (WHERE status = 'sent') AS sent, "
        "COUNT(*) FILTER (WHERE status = 'partial') AS partial, "
        "COUNT(*) FILTER (WHERE status = 'received') AS received, "
        "COUNT(*) FILTER (WHERE status NOT IN ('received','cancelled')) AS open, "
        "COUNT(*) AS total "
        "FROM purchase_order"
    ).fetchone()

    recent_rows = conn.execute(
        "SELECT po.id, po.po_number, po.order_date, po.expected_date, po.status, "
        "COALESCE(s.company_name, '') AS supplier_name "
        "FROM purchase_order po "
        "LEFT JOIN supplier s ON s.id = po.supplier_id "
        "ORDER BY po.id DESC LIMIT 8"
    ).fetchall()

    # PO status breakdown for doughnut chart
    status_rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM purchase_order GROUP BY status ORDER BY cnt DESC"
    ).fetchall()

    # Spend by month (last 6 months) for bar chart
    spend_rows = conn.execute(
        "SELECT TO_CHAR(DATE_TRUNC('month', po.order_date::date), 'Mon YYYY') AS month, "
        "COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) AS total "
        "FROM purchase_order po "
        "LEFT JOIN po_item pi ON pi.po_id = po.id "
        "WHERE po.order_date >= (CURRENT_DATE - INTERVAL '6 months')::text "
        "GROUP BY DATE_TRUNC('month', po.order_date::date) "
        "ORDER BY DATE_TRUNC('month', po.order_date::date)"
    ).fetchall()

    # Top suppliers by spend
    top_supplier_rows = conn.execute(
        "SELECT COALESCE(s.company_name, 'Unknown') AS supplier, "
        "COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) AS spend "
        "FROM purchase_order po "
        "LEFT JOIN supplier s ON s.id = po.supplier_id "
        "LEFT JOIN po_item pi ON pi.po_id = po.id "
        "GROUP BY s.company_name ORDER BY spend DESC LIMIT 8"
    ).fetchall()

    # PO count by month (last 6 months)
    po_trend_rows = conn.execute(
        "SELECT TO_CHAR(DATE_TRUNC('month', order_date::date), 'Mon YYYY') AS month, "
        "COUNT(*) AS cnt "
        "FROM purchase_order "
        "WHERE order_date >= (CURRENT_DATE - INTERVAL '6 months')::text "
        "GROUP BY DATE_TRUNC('month', order_date::date) "
        "ORDER BY DATE_TRUNC('month', order_date::date)"
    ).fetchall()

    return {
        'pos': dict(po_row) if po_row else {},
        'recent_pos': [dict(r) for r in recent_rows],
        'po_status_chart': [dict(r) for r in status_rows],
        'spend_by_month': [dict(r) for r in spend_rows],
        'top_suppliers': [dict(r) for r in top_supplier_rows],
        'po_trend': [dict(r) for r in po_trend_rows],
    }


# ---------------------------------------------------------------------------
# Vendor Contracts
# ---------------------------------------------------------------------------

def init_purch_contract_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purch_contract (
            id SERIAL PRIMARY KEY,
            contract_number TEXT,
            supplier_id INTEGER,
            title TEXT NOT NULL,
            category TEXT,
            start_date TEXT,
            end_date TEXT,
            value REAL,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_by TEXT,
            created_date TEXT
        )
    """)
    conn.commit()


def _next_contract_number(conn) -> str:
    yr = date.today().year
    row = conn.execute(
        "SELECT MAX(CAST(SPLIT_PART(contract_number, '-', 3) AS INTEGER)) "
        "FROM purch_contract WHERE contract_number LIKE %s",
        (f'CONT-{yr}-%',)
    ).fetchone()
    n = (row[0] or 0) + 1
    return f'CONT-{yr}-{n:04d}'


def list_contracts(conn, status=None, supplier_id=None, search=None) -> list:
    sql = (
        "SELECT c.id, c.contract_number, c.title, c.category, c.start_date, "
        "c.end_date, c.value, c.status, COALESCE(s.company_name,'') AS supplier_name "
        "FROM purch_contract c "
        "LEFT JOIN supplier s ON s.id = c.supplier_id "
        "WHERE 1=1"
    )
    params = []
    if status:
        sql += " AND c.status = %s"
        params.append(status)
    if supplier_id:
        sql += " AND c.supplier_id = %s"
        params.append(supplier_id)
    if search:
        sql += " AND (c.title ILIKE %s OR c.contract_number ILIKE %s OR s.company_name ILIKE %s)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    sql += " ORDER BY c.end_date ASC NULLS LAST, c.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_contract(conn, contract_id: int) -> dict | None:
    row = conn.execute(
        "SELECT c.*, COALESCE(s.company_name,'') AS supplier_name "
        "FROM purch_contract c "
        "LEFT JOIN supplier s ON s.id = c.supplier_id "
        "WHERE c.id = %s",
        (contract_id,)
    ).fetchone()
    return dict(row) if row else None


def create_contract(conn, title, category, supplier_id, start_date, end_date,
                    value, status, notes, created_by) -> int:
    num = _next_contract_number(conn)
    row = conn.execute(
        "INSERT INTO purch_contract "
        "(contract_number, supplier_id, title, category, start_date, end_date, "
        "value, status, notes, created_by, created_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (num, supplier_id or None, title, category, start_date or None,
         end_date or None, value or None, status, notes or None, created_by,
         date.today().isoformat())
    ).fetchone()
    conn.commit()
    return row[0]


def update_contract(conn, contract_id: int, **fields) -> None:
    allowed = {'title', 'category', 'supplier_id', 'start_date', 'end_date',
               'value', 'status', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ', '.join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE purch_contract SET {set_clause} WHERE id = %s",
        list(cols.values()) + [contract_id]
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Purchasing Reports
# ---------------------------------------------------------------------------

def get_purch_reports(conn) -> dict:
    by_status = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM purchase_order GROUP BY status ORDER BY cnt DESC"
    ).fetchall()

    top_suppliers = conn.execute(
        "SELECT COALESCE(s.company_name, 'Unknown') AS supplier_name, "
        "COUNT(*) AS po_count, "
        "COALESCE(SUM(poi.unit_price * poi.quantity), 0) AS total_value "
        "FROM purchase_order po "
        "LEFT JOIN supplier s ON s.id = po.supplier_id "
        "LEFT JOIN purchase_order_item poi ON poi.po_id = po.id "
        "WHERE po.status != 'cancelled' "
        "GROUP BY s.id, s.company_name "
        "ORDER BY po_count DESC LIMIT 8"
    ).fetchall()

    monthly = conn.execute(
        "SELECT TO_CHAR(TO_DATE(order_date,'YYYY-MM-DD'),'YYYY-MM') AS month, "
        "COUNT(*) AS cnt "
        "FROM purchase_order "
        "WHERE order_date IS NOT NULL "
        "AND TO_DATE(order_date,'YYYY-MM-DD') >= CURRENT_DATE - INTERVAL '6 months' "
        "GROUP BY month ORDER BY month ASC"
    ).fetchall()

    open_value = conn.execute(
        "SELECT COALESCE(SUM(poi.unit_price * poi.quantity), 0) AS total "
        "FROM purchase_order po "
        "JOIN purchase_order_item poi ON poi.po_id = po.id "
        "WHERE po.status NOT IN ('received','cancelled')"
    ).fetchone()

    expiring_contracts = conn.execute(
        "SELECT c.id, c.contract_number, c.title, c.end_date, "
        "COALESCE(s.company_name,'') AS supplier_name "
        "FROM purch_contract c "
        "LEFT JOIN supplier s ON s.id = c.supplier_id "
        "WHERE c.status = 'Active' AND c.end_date IS NOT NULL "
        "AND TO_DATE(c.end_date,'YYYY-MM-DD') <= CURRENT_DATE + INTERVAL '90 days' "
        "ORDER BY c.end_date ASC LIMIT 10"
    ).fetchall()

    return {
        'by_status': [dict(r) for r in by_status],
        'top_suppliers': [dict(r) for r in top_suppliers],
        'monthly': [dict(r) for r in monthly],
        'open_value': float(open_value[0]) if open_value else 0.0,
        'expiring_contracts': [dict(r) for r in expiring_contracts],
    }
