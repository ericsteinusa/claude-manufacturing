"""Tests for the Qt-free sales-order helpers (sales_orders_core)."""
from datetime import date

from manufacturing.sales_orders_core import next_so_number


class _FakeConn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return self

    def fetchall(self):
        return self.rows


def test_next_so_number_starts_at_one_when_empty():
    conn = _FakeConn(rows=[])
    assert next_so_number(conn, today=date(2026, 6, 1)) == "SO-2026-0001"
    assert conn.calls[0][1] == ["SO-2026-%"]


def test_next_so_number_is_max_suffix_plus_one_not_count():
    # Gap (0001, 0005) → next is 0006, never a duplicate.
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
