"""Tests for reports_core — Qt-free, no live DB."""

from manufacturing.reports_core import (
    po_summary, wo_summary, inventory_alerts, cs_summary, hours_variance,
    sales_dashboard, accounting_dashboard, customer_service_dashboard,
    engineering_dashboard, customers_dashboard, payroll_dashboard,
)


# ── hours_variance ──────────────────────────────────────────────────────────

def test_hours_variance_over_standard():
    variance, pct = hours_variance(std_hours=10.0, actual_hours=12.0)
    assert variance == 2.0
    assert pct == 20.0


def test_hours_variance_under_standard():
    variance, pct = hours_variance(std_hours=10.0, actual_hours=8.0)
    assert variance == -2.0
    assert pct == -20.0


def test_hours_variance_zero_std_hours_pct_is_none():
    variance, pct = hours_variance(std_hours=0.0, actual_hours=5.0)
    assert variance == 5.0
    assert pct is None


def test_hours_variance_none_std_hours_pct_is_none():
    variance, pct = hours_variance(std_hours=None, actual_hours=3.0)
    assert variance == 3.0
    assert pct is None


def test_hours_variance_none_actual_hours_treated_as_zero():
    variance, pct = hours_variance(std_hours=4.0, actual_hours=None)
    assert variance == -4.0
    assert pct == -100.0


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Returns preset row sets in sequence, one per execute() call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self._idx = 0

    def execute(self, sql, params=None):
        rows = self._responses[self._idx]
        self._idx += 1
        return _FakeCursor(rows)


# ── po_summary ───────────────────────────────────────────────────────────────

def test_po_summary_counts_by_status():
    conn = _FakeConn([
        [{"status": "draft", "n": 3}, {"status": "sent", "n": 2}],
        [{"total": "5000.00"}],
        [{"n": 1}],
    ])
    result = po_summary(conn)
    assert result["by_status"] == {"draft": 3, "sent": 2}
    assert result["total_spend"] == 5000.0
    assert result["overdue"] == 1


def test_po_summary_empty_db():
    conn = _FakeConn([[], [{"total": None}], [{"n": 0}]])
    result = po_summary(conn)
    assert result["by_status"] == {}
    assert result["total_spend"] == 0.0
    assert result["overdue"] == 0


def test_po_summary_spend_excludes_cancelled():
    # Just verifies the spend query is issued (it always excludes cancelled).
    conn = _FakeConn([
        [{"status": "received", "n": 1}],
        [{"total": "250.00"}],
        [{"n": 0}],
    ])
    result = po_summary(conn)
    assert result["total_spend"] == 250.0


# ── wo_summary ───────────────────────────────────────────────────────────────

def test_wo_summary_by_status():
    conn = _FakeConn([
        [{"status": "open", "n": 5}, {"status": "completed", "n": 10}],
    ])
    result = wo_summary(conn)
    assert result["by_status"] == {"open": 5, "completed": 10}


def test_wo_summary_empty():
    conn = _FakeConn([[]])
    result = wo_summary(conn)
    assert result["by_status"] == {}


# ── inventory_alerts ─────────────────────────────────────────────────────────

def test_inventory_alerts_returns_items_and_count():
    conn = _FakeConn([
        [{"name": "Widget A", "on_hand": 2.0, "reorder_point": 10.0}],
        [{"n": 1}],
    ])
    result = inventory_alerts(conn)
    assert result["alert_count"] == 1
    assert result["items"][0]["name"] == "Widget A"
    assert result["items"][0]["on_hand"] == 2.0


def test_inventory_alerts_none_below_reorder():
    conn = _FakeConn([[], [{"n": 0}]])
    result = inventory_alerts(conn)
    assert result["alert_count"] == 0
    assert result["items"] == []


# ── cs_summary ───────────────────────────────────────────────────────────────

def test_cs_summary_computes_closed():
    conn = _FakeConn([
        [{"n": 100}],
        [{"n": 15}],
        [{"n": 3}],
    ])
    result = cs_summary(conn)
    assert result["total"] == 100
    assert result["open"] == 15
    assert result["closed"] == 85
    assert result["today"] == 3


def test_cs_summary_empty_db():
    conn = _FakeConn([[], [], []])
    result = cs_summary(conn)
    assert result["total"] == 0
    assert result["open"] == 0
    assert result["closed"] == 0
    assert result["today"] == 0


# ── sales_dashboard ──────────────────────────────────────────────────────────

def test_sales_dashboard_combines_kpis_and_recent_orders():
    conn = _FakeConn([
        [{"draft": 2, "confirmed": 3, "shipped": 1, "invoiced": 4,
          "total": 10, "total_value": "50000.00"}],
        [{"draft": 1, "sent": 2, "won": 3, "total": 6, "won_value": "20000.00"}],
        [{"total_target": "100000.00", "total_actual": "75000.00"}],
        [{"id": 1, "so_number": "SO-2026-0001", "order_date": "2026-08-01",
          "ship_date": None, "status": "confirmed", "notes": "", "created_by": "x",
          "customer_id": 5, "company_name": "Acme Corp", "first_name": None,
          "last_name": None, "item_count": 3, "total": "1200.00"}],
    ])
    result = sales_dashboard(conn)
    assert result["orders"]["total"] == 10
    assert result["quotes"]["won"] == 3
    assert result["targets"]["total_target"] == "100000.00"
    assert result["recent_orders"] == [{
        "id": 1, "so_number": "SO-2026-0001", "customer": "Acme Corp",
        "status": "confirmed", "total": 1200.0, "order_date": "2026-08-01",
    }]


def test_sales_dashboard_recent_order_falls_back_to_contact_name():
    conn = _FakeConn([
        [{"draft": 0, "confirmed": 0, "shipped": 0, "invoiced": 0,
          "total": 0, "total_value": 0}],
        [{"draft": 0, "sent": 0, "won": 0, "total": 0, "won_value": 0}],
        [{"total_target": 0, "total_actual": 0}],
        [{"id": 2, "so_number": "SO-2026-0002", "order_date": None,
          "ship_date": None, "status": "draft", "notes": "", "created_by": "x",
          "customer_id": None, "company_name": None, "first_name": "Jane",
          "last_name": "Doe", "item_count": 0, "total": 0}],
    ])
    result = sales_dashboard(conn)
    assert result["recent_orders"][0]["customer"] == "Jane Doe"
    assert result["recent_orders"][0]["order_date"] is None


def test_sales_dashboard_truncates_recent_orders_to_eight():
    order_row = {"id": 1, "so_number": "SO-1", "order_date": None,
                 "ship_date": None, "status": "draft", "notes": "", "created_by": "x",
                 "customer_id": 1, "company_name": "X", "first_name": None,
                 "last_name": None, "item_count": 1, "total": 1}
    conn = _FakeConn([
        [{"draft": 0, "confirmed": 0, "shipped": 0, "invoiced": 0,
          "total": 0, "total_value": 0}],
        [{"draft": 0, "sent": 0, "won": 0, "total": 0, "won_value": 0}],
        [{"total_target": 0, "total_actual": 0}],
        [dict(order_row) for _ in range(12)],
    ])
    result = sales_dashboard(conn)
    assert len(result["recent_orders"]) == 8


# ── accounting_dashboard ─────────────────────────────────────────────────────

def test_accounting_dashboard_combines_ap_ar_and_journals():
    conn = _FakeConn([
        [{"open_count": 3, "overdue_count": 1, "total_outstanding": "5000.00",
          "total_invoiced": "20000.00", "total_invoices": 10}],
        [{"open_count": 5, "overdue_count": 2, "total_outstanding": "8000.00",
          "total_invoiced": "30000.00", "total_invoices": 12}],
        [{"id": 1, "journal_date": "2026-08-01", "reference": "JE-1",
          "description": "Month-end accrual", "posted": 1, "line_count": 4,
          "total_debit": "1200.00"}],
    ])
    result = accounting_dashboard(conn)
    assert result["ap"]["overdue_count"] == 1
    assert result["ar"]["total_invoices"] == 12
    assert result["recent_journals"] == [{
        "id": 1, "journal_date": "2026-08-01", "reference": "JE-1",
        "description": "Month-end accrual", "posted": 1, "line_count": 4,
        "total_debit": "1200.00",
    }]


def test_accounting_dashboard_empty_journals():
    conn = _FakeConn([
        [{"open_count": 0, "overdue_count": 0, "total_outstanding": 0,
          "total_invoiced": 0, "total_invoices": 0}],
        [{"open_count": 0, "overdue_count": 0, "total_outstanding": 0,
          "total_invoiced": 0, "total_invoices": 0}],
        [],
    ])
    result = accounting_dashboard(conn)
    assert result["recent_journals"] == []


# ── customer_service_dashboard ───────────────────────────────────────────────

def test_customer_service_dashboard_combines_stats_and_recent_tickets():
    conn = _FakeConn([
        [{"total": 20, "open_count": 5, "completed_count": 15,
          "avg_resolution": "2.50"}],
        [{"avg_age": "3.00"}],
        [{"id": 1, "customer_id": 7, "call": "Damaged shipment",
          "call_date": "2026-08-01", "call_time": "09:00", "completion_date": "",
          "completion_time": "", "comments_box": "", "completion_box": 0,
          "created_by": "x", "customer_name": "Acme Corp"}],
    ])
    result = customer_service_dashboard(conn)
    assert result["total"] == 20
    assert result["open_count"] == 5
    assert result["completion_rate"] == 75.0
    assert result["avg_age_open"] == 3.0
    assert result["recent_tickets"] == [{
        "id": 1, "customer_name": "Acme Corp", "call": "Damaged shipment",
        "call_date": "2026-08-01", "completion_box": 0,
    }]


def test_customer_service_dashboard_truncates_recent_tickets_to_eight():
    ticket_row = {"id": 1, "customer_id": 1, "call": "x", "call_date": None,
                  "call_time": "", "completion_date": "", "completion_time": "",
                  "comments_box": "", "completion_box": 0, "created_by": "x",
                  "customer_name": "X"}
    conn = _FakeConn([
        [{"total": 0, "open_count": 0, "completed_count": 0, "avg_resolution": None}],
        [{"avg_age": None}],
        [dict(ticket_row) for _ in range(12)],
    ])
    result = customer_service_dashboard(conn)
    assert len(result["recent_tickets"]) == 8
    assert result["recent_tickets"][0]["call_date"] is None


# ── engineering_dashboard ─────────────────────────────────────────────────────

def test_engineering_dashboard_combines_kpis_and_recent_projects():
    conn = _FakeConn([
        [{"planning": 2, "in_progress": 3, "on_hold": 1, "completed": 5, "total": 11}],
        [{"draft": 1, "pending": 2, "approved": 4, "total": 7}],
        [{"open_tasks": 6, "active_tasks": 3, "overdue_tasks": 2}],
        [{"id": 1, "project_number": "ENG-2026-001", "title": "New valve design",
          "product_id": 5, "engineer": "Alice", "start_date": "2026-07-01",
          "due_date": "2026-09-01", "status": "in_progress", "notes": "",
          "created_by": "x", "task_count": 5, "done_count": 2, "overdue_tasks": 1}],
    ])
    result = engineering_dashboard(conn)
    assert result["projects"]["total"] == 11
    assert result["ecrs"]["pending"] == 2
    assert result["tasks"]["overdue_tasks"] == 2
    assert result["recent_projects"] == [{
        "id": 1, "project_number": "ENG-2026-001", "title": "New valve design",
        "engineer": "Alice", "status": "in_progress", "due_date": "2026-09-01",
        "task_count": 5, "done_count": 2, "overdue_tasks": 1,
    }]


def test_engineering_dashboard_truncates_recent_projects_to_eight():
    project_row = {"id": 1, "project_number": "ENG-1", "title": "X",
                   "product_id": None, "engineer": "", "start_date": None,
                   "due_date": None, "status": "planning", "notes": "",
                   "created_by": "x", "task_count": 0, "done_count": 0, "overdue_tasks": 0}
    conn = _FakeConn([
        [{"planning": 0, "in_progress": 0, "on_hold": 0, "completed": 0, "total": 0}],
        [{"draft": 0, "pending": 0, "approved": 0, "total": 0}],
        [{"open_tasks": 0, "active_tasks": 0, "overdue_tasks": 0}],
        [dict(project_row) for _ in range(12)],
    ])
    result = engineering_dashboard(conn)
    assert len(result["recent_projects"]) == 8


# ── customers_dashboard ──────────────────────────────────────────────────────

def test_customers_dashboard_combines_kpis_and_recent_collections():
    conn = _FakeConn([
        [{"total": 10, "good": 7, "hold": 2, "suspended": 1, "total_exposure": "500000.00"}],
        [{"total": 4, "pending": 1}],
        [{"total": 5, "open": 3}],
        [{"id": 1, "customer_id": 9, "activity_date": "2026-08-01",
          "activity_type": "Phone Call", "contact_name": "Bob", "notes": "",
          "amount_promised": 1200.0, "promise_date": "2026-08-15",
          "follow_up_date": "2026-08-10", "status": "Open", "created_by": "x",
          "company_name": "Acme Corp", "first_name": None, "last_name": None},
         {"id": 2, "customer_id": 3, "activity_date": "2026-07-20",
          "activity_type": "Email", "contact_name": "Sue", "notes": "",
          "amount_promised": None, "promise_date": None,
          "follow_up_date": None, "status": "Closed", "created_by": "x",
          "company_name": "", "first_name": "Sue", "last_name": "Jones"}],
    ])
    result = customers_dashboard(conn)
    assert result["accounts"]["hold"] == 2
    assert result["applications"]["pending"] == 1
    assert result["collections"]["open"] == 3
    # Only the "Open"-status activity survives the status filter.
    assert result["recent_collections"] == [{
        "id": 1, "customer_name": "Acme Corp", "activity_type": "Phone Call",
        "activity_date": "2026-08-01", "status": "Open", "amount_promised": 1200.0,
    }]


def test_customers_dashboard_recent_collection_falls_back_to_contact_name():
    conn = _FakeConn([
        [{"total": 0, "good": 0, "hold": 0, "suspended": 0, "total_exposure": 0}],
        [{"total": 0, "pending": 0}],
        [{"total": 0, "open": 0}],
        [{"id": 1, "customer_id": 3, "activity_date": "2026-07-20",
          "activity_type": "Email", "contact_name": "Sue", "notes": "",
          "amount_promised": None, "promise_date": None,
          "follow_up_date": None, "status": "Escalated", "created_by": "x",
          "company_name": "", "first_name": "Sue", "last_name": "Jones"}],
    ])
    result = customers_dashboard(conn)
    assert result["recent_collections"][0]["customer_name"] == "Sue Jones"


# ── payroll_dashboard ────────────────────────────────────────────────────────

def test_payroll_dashboard_combines_counts_and_recent_runs():
    conn = _FakeConn([
        [{"total_runs": 3, "emp_with_rates": 12, "total_people": 46,
          "active_ded_types": 5, "ytd_gross": 250000.0}],
        [{"id": 1, "run_date": "2026-08-15", "pay_period_start": "2026-08-01",
          "pay_period_end": "2026-08-15", "status": "completed",
          "created_by": "admin", "emp_count": 12, "total_gross": 48000.0,
          "total_net": 36000.0}],
    ])
    result = payroll_dashboard(conn)
    assert result["counts"]["total_runs"] == 3
    assert result["counts"]["ytd_gross"] == 250000.0
    assert result["recent_runs"] == [{
        "id": 1, "run_date": "2026-08-15", "pay_period_start": "2026-08-01",
        "pay_period_end": "2026-08-15", "status": "completed",
        "emp_count": 12, "total_gross": 48000.0, "total_net": 36000.0,
    }]


def test_payroll_dashboard_truncates_recent_runs_to_five():
    run_row = {"id": 1, "run_date": "2026-01-01", "pay_period_start": "2025-12-16",
               "pay_period_end": "2025-12-31", "status": "completed",
               "created_by": "admin", "emp_count": 1, "total_gross": 100.0,
               "total_net": 80.0}
    conn = _FakeConn([
        [{"total_runs": 0, "emp_with_rates": 0, "total_people": 0,
          "active_ded_types": 0, "ytd_gross": 0.0}],
        [dict(run_row) for _ in range(8)],
    ])
    result = payroll_dashboard(conn)
    assert len(result["recent_runs"]) == 5
