"""
production_core.py — Qt-free production dashboard data layer.

Aggregates KPIs from work_order, product (inventory), and bom tables
for the production dashboard view.  Deeper operations (CRUD, MRP run,
BOM explosion) live in their respective *_core modules.
"""

from datetime import date


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
