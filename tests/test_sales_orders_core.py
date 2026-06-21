"""Tests for the Qt-free sales-order helpers (sales_orders_core)."""
from datetime import date

import pytest

from manufacturing.sales_orders_core import (
    SO_STATUSES, SO_STATUS_COLORS, SO_STATUS_TRANSITIONS,
    allowed_transitions, can_transition, customer_label,
    next_so_number, list_sos, get_so, get_so_items,
    load_customers, load_products,
    create_so, update_so, add_so_item, delete_so_item, set_so_status,
)


# ── fake DB infrastructure ────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows, rowcount=0):
        self._rows = rows
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows=None, rowcount=0):
        self.rows = rows or []
        self.rowcount = rowcount
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeCursor(self.rows, self.rowcount)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ── constants ─────────────────────────────────────────────────────────────

def test_statuses_and_colors_match():
    assert set(SO_STATUSES) == set(SO_STATUS_COLORS)


def test_all_statuses_have_transition_entries():
    assert set(SO_STATUSES) == set(SO_STATUS_TRANSITIONS)


# ── customer_label ────────────────────────────────────────────────────────

def test_customer_label_prefers_company_name():
    row = {"company_name": "Acme Inc", "first_name": "John",
           "last_name": "Doe"}
    assert customer_label(row) == "Acme Inc"


def test_customer_label_falls_back_to_name():
    row = {"company_name": None, "first_name": "Jane", "last_name": "Smith"}
    assert customer_label(row) == "Jane Smith"


def test_customer_label_handles_empty_company():
    row = {"company_name": "", "first_name": "Bob", "last_name": ""}
    assert customer_label(row) == "Bob"


def test_customer_label_all_missing():
    row = {"company_name": None, "first_name": None, "last_name": None}
    assert customer_label(row) == ""


# ── status transitions ────────────────────────────────────────────────────

def test_allowed_transitions_follow_workflow():
    assert set(allowed_transitions("draft"))     == {"confirmed", "cancelled"}
    assert set(allowed_transitions("confirmed")) == {"shipped", "cancelled"}
    assert set(allowed_transitions("shipped"))   == {"invoiced", "cancelled"}


def test_terminal_states_have_no_transitions():
    assert allowed_transitions("invoiced")  == ()
    assert allowed_transitions("cancelled") == ()
    assert allowed_transitions("bogus")     == ()


def test_can_transition_rejects_skips_and_reopens():
    assert can_transition("draft", "confirmed")
    assert not can_transition("draft", "invoiced")    # skip
    assert not can_transition("invoiced", "shipped")  # reopen
    assert not can_transition("cancelled", "draft")


# ── next_so_number ────────────────────────────────────────────────────────

def test_next_so_number_starts_at_one_when_empty():
    conn = _FakeConn(rows=[])
    assert next_so_number(conn, today=date(2026, 6, 1)) == "SO-2026-0001"
    assert conn.calls[0][1] == ["SO-2026-%"]


def test_next_so_number_is_max_suffix_plus_one_not_count():
    conn = _FakeConn(rows=[{"so_number": "SO-2026-0001"},
                           {"so_number": "SO-2026-0005"}])
    assert next_so_number(conn, today=date(2026, 1, 1)) == "SO-2026-0006"


def test_next_so_number_ignores_other_years():
    conn = _FakeConn(rows=[{"so_number": "SO-2025-0099"}])
    assert next_so_number(conn, today=date(2026, 1, 1)) == "SO-2026-0001"


def test_next_so_number_ignores_malformed_entries():
    conn = _FakeConn(rows=[{"so_number": "SO-2026-XXXX"},
                           {"so_number": "SO-2026-0004"}])
    assert next_so_number(conn, today=date(2026, 1, 1)) == "SO-2026-0005"


# ── list_sos: filter assembly ─────────────────────────────────────────────

def test_list_sos_without_filters_applies_no_conditions():
    conn = _FakeConn(rows=[])
    list_sos(conn)
    assert "so.status = %s"      not in conn.last_sql
    assert "so.customer_id = %s" not in conn.last_sql
    assert "so.order_date >= %s" not in conn.last_sql
    assert conn.last_params      == []


def test_list_sos_status_filter():
    conn = _FakeConn(rows=[])
    list_sos(conn, status="confirmed")
    assert "so.status = %s" in conn.last_sql
    assert conn.last_params == ["confirmed"]


def test_list_sos_customer_and_date_filters():
    conn = _FakeConn(rows=[])
    list_sos(conn, customer_id=3, date_from="2026-01-01", date_to="2026-12-31")
    assert "so.customer_id = %s" in conn.last_sql
    assert "so.order_date >= %s" in conn.last_sql
    assert "so.order_date <= %s" in conn.last_sql
    assert conn.last_params      == [3, "2026-01-01", "2026-12-31"]


def test_list_sos_normalises_total_and_count():
    conn = _FakeConn(rows=[{
        "id": 1, "so_number": "SO-2026-0001", "order_date": "2026-06-01",
        "ship_date": None, "status": "draft", "notes": None,
        "created_by": None,
        "customer_id": 2, "company_name": "Acme", "first_name": None,
        "last_name": None, "item_count": 3, "total": "75.50",
    }])
    sos = list_sos(conn)
    assert sos[0]["total"]      == pytest.approx(75.50)
    assert isinstance(sos[0]["total"], float)
    assert sos[0]["item_count"] == 3


# ── get_so ────────────────────────────────────────────────────────────────

def test_get_so_returns_none_when_absent():
    assert get_so(_FakeConn(rows=[]), 999) is None


def test_get_so_normalises_null_total():
    conn = _FakeConn(rows=[{
        "id": 5, "so_number": "SO-2026-0005", "order_date": None,
        "ship_date": None, "status": "draft", "notes": None,
        "created_by": None,
        "customer_id": None, "company_name": None, "first_name": None,
        "last_name": None, "item_count": None, "total": None,
    }])
    so = get_so(conn, 5)
    assert so is not None
    assert so["total"]      == 0.0
    assert so["item_count"] == 0


# ── get_so_items ──────────────────────────────────────────────────────────

def test_get_so_items_normalises_floats():
    conn = _FakeConn(rows=[{
        "id": 1, "description": "Widget", "product_id": 3,
        "product_name": "Widget A", "qty": 4,
        "unit_price": "2.50", "line_total": "10.00",
    }])
    items = get_so_items(conn, 1)
    assert items[0]["unit_price"] == pytest.approx(2.50)
    assert items[0]["line_total"] == pytest.approx(10.00)
    assert isinstance(items[0]["line_total"], float)


# ── writes ────────────────────────────────────────────────────────────────

def test_create_so_returns_new_id():
    conn = _FakeConn(rows=[{"id": 42}])
    new_id = create_so(conn, "SO-2026-0042", customer_id=3,
                       order_date="2026-06-01", status="draft",
                       created_by="bob@example.com")
    assert new_id == 42
    assert conn.last_sql.strip().upper().startswith("INSERT INTO SALES_ORDER")
    assert "RETURNING id" in conn.last_sql
    assert conn.last_params == [
        "SO-2026-0042", 3, "2026-06-01", None, "draft", None,
        "bob@example.com"]


def test_update_so_excludes_so_number_and_status():
    conn = _FakeConn()
    update_so(conn, 7, customer_id=2, order_date="2026-06-05",
              ship_date="2026-06-20", notes="rush")
    sql = conn.last_sql.upper()
    assert sql.strip().startswith("UPDATE SALES_ORDER")
    assert "SO_NUMBER" not in sql
    assert "STATUS"    not in sql
    assert conn.last_params == [2, "2026-06-05", "2026-06-20", "rush", 7]


def test_add_so_item_inserts_line():
    conn = _FakeConn()
    add_so_item(conn, 3, "Widget", product_id=5, qty=10, unit_price=2.50)
    assert "INSERT INTO so_item" in conn.last_sql
    assert conn.last_params == [3, "Widget", 5, 10, 2.50]


def test_delete_so_item_scopes_to_so():
    conn = _FakeConn(rowcount=1)
    n = delete_so_item(conn, 9, so_id=3)
    assert n == 1
    assert "AND so_id=%s" in conn.last_sql
    assert conn.last_params == [9, 3]


def test_delete_so_item_without_so_scope():
    conn = _FakeConn(rowcount=1)
    delete_so_item(conn, 9)
    assert "AND so_id" not in conn.last_sql
    assert conn.last_params == [9]


def test_set_so_status_updates_status():
    conn = _FakeConn()
    set_so_status(conn, 4, "shipped")
    assert "UPDATE sales_order SET status=%s" in conn.last_sql
    assert conn.last_params == ["shipped", 4]


def test_set_so_status_does_not_guard_transition():
    conn = _FakeConn()
    set_so_status(conn, 4, "invoiced")
    set_so_status(conn, 4, "draft")    # illegal reopen — no exception
    assert len(conn.calls) == 2


# ── load helpers ─────────────────────────────────────────────────────────

def test_load_customers_returns_empty_on_error():
    import psycopg2

    class _ErrorConn:
        def execute(self, *a, **kw):
            raise psycopg2.Error("table missing")

    assert load_customers(_ErrorConn()) == []


def test_load_products_returns_empty_on_error():
    import psycopg2

    class _ErrorConn:
        def execute(self, *a, **kw):
            raise psycopg2.Error("table missing")

    assert load_products(_ErrorConn()) == []
