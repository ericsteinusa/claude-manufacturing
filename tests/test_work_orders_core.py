"""Tests for the Qt-free work-order helpers (work_orders_core)."""
from datetime import date

from manufacturing.work_orders_core import next_wo_number


class _FakeConn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return self

    def fetchall(self):
        return self.rows


def test_next_wo_number_starts_at_one_when_empty():
    conn = _FakeConn(rows=[])
    assert next_wo_number(conn, today=date(2026, 6, 1)) == "WO-2026-0001"
    assert conn.calls[0][1] == ["WO-2026-%"]


def test_next_wo_number_is_max_suffix_plus_one_not_count():
    # Gap (0001, 0003) → next is 0004, never a duplicate.
    conn = _FakeConn(rows=[{"wo_number": "WO-2026-0001"},
                           {"wo_number": "WO-2026-0003"}])
    assert next_wo_number(conn, today=date(2026, 1, 1)) == "WO-2026-0004"


def test_next_wo_number_ignores_other_years():
    conn = _FakeConn(rows=[{"wo_number": "WO-2025-0099"}])
    assert next_wo_number(conn, today=date(2026, 1, 1)) == "WO-2026-0001"


def test_next_wo_number_ignores_malformed_entries():
    conn = _FakeConn(rows=[{"wo_number": "WO-2026-XXXX"},
                           {"wo_number": "WO-2026-0002"}])
    assert next_wo_number(conn, today=date(2026, 1, 1)) == "WO-2026-0003"
