"""Tests for the Qt-free purchase-order data layer (purchase_orders_core).

No live database: a fake connection records the SQL and params each call
issues and returns canned rows, so filter assembly, PO numbering and row
normalisation are pinned down without Postgres or PyQt6 (CI can't import Qt).
"""

from datetime import date

import pytest

from manufacturing.purchase_orders_core import (
    PO_STATUSES, PO_STATUS_COLORS,
    list_pos, get_po, get_po_items, next_po_number,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Records every (sql, params) and replays preset rows."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeCursor(self.rows)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ── constants ───────────────────────────────────────────────────────────

def test_status_set_matches_colors():
    assert set(PO_STATUSES) == set(PO_STATUS_COLORS)


# ── next_po_number ────────────────────────────────────────────────────────

def test_next_po_number_prefixes_year_and_starts_at_one():
    conn = _FakeConn(rows=[])
    num = next_po_number(conn, today=date(2026, 6, 15))
    assert num == "PO-2026-0001"
    # Filters the query to this year's prefix.
    assert conn.last_params == ["PO-2026-%"]


def test_next_po_number_is_max_suffix_plus_one_not_count():
    # Gap (0001, 0003) -> next is 0004, never a duplicate of an existing row.
    conn = _FakeConn(rows=[{"po_number": "PO-2026-0001"},
                           {"po_number": "PO-2026-0003"}])
    assert next_po_number(conn, today=date(2026, 1, 1)) == "PO-2026-0004"


# ── list_pos: filter assembly ─────────────────────────────────────────────

def test_list_pos_without_filters_applies_no_conditions():
    conn = _FakeConn(rows=[])
    list_pos(conn)
    # No header-level filter clauses (the subquery WHEREs are always present).
    assert "po.status = %s" not in conn.last_sql
    assert "po.supplier_id = %s" not in conn.last_sql
    assert "po.order_date >= %s" not in conn.last_sql
    assert "po.order_date <= %s" not in conn.last_sql
    assert conn.last_params == []


def test_list_pos_status_filter():
    conn = _FakeConn(rows=[])
    list_pos(conn, status="sent")
    assert "po.status = %s" in conn.last_sql
    assert conn.last_params == ["sent"]


def test_list_pos_supplier_and_date_filters():
    conn = _FakeConn(rows=[])
    list_pos(conn, supplier_id=7, date_from="2026-01-01", date_to="2026-12-31")
    assert "po.supplier_id = %s" in conn.last_sql
    assert "po.order_date >= %s" in conn.last_sql
    assert "po.order_date <= %s" in conn.last_sql
    assert conn.last_params == [7, "2026-01-01", "2026-12-31"]


def test_list_pos_normalises_rows():
    conn = _FakeConn(rows=[{
        "id": 1, "po_number": "PO-2026-0001", "order_date": "2026-06-01",
        "expected_date": None, "status": "draft", "notes": None,
        "supplier_id": 3, "company_name": "Acme", "item_count": 2,
        "total": "150.50",
    }])
    pos = list_pos(conn)
    assert pos[0]["total"] == pytest.approx(150.50)
    assert isinstance(pos[0]["total"], float)
    assert pos[0]["item_count"] == 2


# ── get_po / get_po_items ─────────────────────────────────────────────────

def test_get_po_returns_none_when_absent():
    assert get_po(_FakeConn(rows=[]), 999) is None


def test_get_po_normalises_total_and_count():
    conn = _FakeConn(rows=[{
        "id": 5, "po_number": "PO-2026-0005", "order_date": None,
        "expected_date": None, "status": "sent", "notes": "x",
        "supplier_id": None, "company_name": None, "item_count": None,
        "total": None,
    }])
    po = get_po(conn, 5)
    assert po["total"] == 0.0
    assert po["item_count"] == 0


def test_get_po_items_computes_line_total_floats():
    conn = _FakeConn(rows=[{
        "id": 1, "description": "Bolt", "product_id": 2,
        "product_name": "M6 Bolt", "qty_ordered": 10,
        "unit_price": "1.25", "qty_received": 0, "line_total": "12.50",
    }])
    items = get_po_items(conn, 1)
    assert items[0]["unit_price"] == pytest.approx(1.25)
    assert items[0]["line_total"] == pytest.approx(12.50)
    assert isinstance(items[0]["line_total"], float)
