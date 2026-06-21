"""reports_core.py — Qt-free data queries for the Reports dashboard."""

from __future__ import annotations
import datetime


def po_summary(conn) -> dict:
    """Return PO counts by status, total active spend, and overdue count."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM purchase_order GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}

    spend_row = conn.execute(
        "SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) AS total "
        "FROM po_item pi "
        "JOIN purchase_order po ON po.id = pi.po_id "
        "WHERE po.status NOT IN ('cancelled')"
    ).fetchone()
    total_spend = float(spend_row["total"] or 0) if spend_row else 0.0

    today = datetime.date.today().isoformat()
    overdue_row = conn.execute(
        "SELECT COUNT(*) AS n FROM purchase_order "
        "WHERE expected_date < %s AND status NOT IN ('received', 'cancelled')",
        (today,),
    ).fetchone()
    overdue = overdue_row["n"] if overdue_row else 0

    return {
        "by_status": by_status, "total_spend": total_spend, "overdue": overdue
    }


def wo_summary(conn) -> dict:
    """Return WO counts by status."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM work_order GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}
    return {"by_status": by_status}


def inventory_alerts(conn) -> dict:
    """Return products at or below their reorder point (up to 20 rows)."""
    items = conn.execute(
        "SELECT name, COALESCE(amount, 0) AS on_hand, "
        "COALESCE(reorder_point, 0) AS reorder_point "
        "FROM product "
        "WHERE COALESCE(reorder_point, 0) > 0 "
        "  AND COALESCE(amount, 0) <= COALESCE(reorder_point, 0) "
        "ORDER BY (COALESCE(amount, 0) - COALESCE(reorder_point, 0)) ASC "
        "LIMIT 20"
    ).fetchall()

    count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM product "
        "WHERE COALESCE(reorder_point, 0) > 0 "
        "  AND COALESCE(amount, 0) <= COALESCE(reorder_point, 0)"
    ).fetchone()

    return {
        "alert_count": count_row["n"] if count_row else 0,
        "items": [dict(r) for r in items],
    }


def cs_summary(conn) -> dict:
    """Return CS call counts: total, open, closed, today."""
    total_row = conn.execute("SELECT COUNT(*) AS n FROM calls2").fetchone()
    open_row = conn.execute(
        "SELECT COUNT(*) AS n FROM calls2 WHERE completion_box = 0"
    ).fetchone()
    today = datetime.date.today().isoformat()
    today_row = conn.execute(
        "SELECT COUNT(*) AS n FROM calls2 WHERE call_date = %s", (today,)
    ).fetchone()

    total = total_row["n"] if total_row else 0
    open_count = open_row["n"] if open_row else 0
    today_count = today_row["n"] if today_row else 0
    return {
        "total": total,
        "open": open_count,
        "closed": total - open_count,
        "today": today_count,
    }
