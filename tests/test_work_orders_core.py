"""Tests for the Qt-free work-order helpers (work_orders_core)."""
from datetime import date

import pytest

from manufacturing.work_orders_core import (
    WO_STATUSES, WO_STATUS_COLORS, WO_STATUS_TRANSITIONS,
    allowed_transitions, can_transition,
    next_wo_number, list_wos, get_wo, get_wo_materials,
    load_products, create_wo, update_wo, add_wo_material, set_wo_status,
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
    """Records every (sql, params) and replays preset rows."""

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
    assert set(WO_STATUSES) == set(WO_STATUS_COLORS)


def test_all_statuses_have_transition_entries():
    assert set(WO_STATUSES) == set(WO_STATUS_TRANSITIONS)


# ── status transitions ────────────────────────────────────────────────────

def test_allowed_transitions_follow_workflow():
    assert set(allowed_transitions("draft"))       == {"open", "cancelled"}
    assert set(allowed_transitions("open"))        == {"in_progress", "cancelled"}
    assert set(allowed_transitions("in_progress")) == {"completed", "cancelled"}


def test_terminal_states_have_no_transitions():
    assert allowed_transitions("completed") == ()
    assert allowed_transitions("cancelled") == ()
    assert allowed_transitions("bogus")     == ()


def test_can_transition_rejects_skips_and_reopens():
    assert can_transition("draft", "open")
    assert not can_transition("draft", "completed")   # skip
    assert not can_transition("completed", "open")    # reopen
    assert not can_transition("cancelled", "draft")


# ── next_wo_number ────────────────────────────────────────────────────────

def test_next_wo_number_starts_at_one_when_empty():
    conn = _FakeConn(rows=[])
    assert next_wo_number(conn, today=date(2026, 6, 1)) == "WO-2026-0001"
    assert conn.calls[0][1] == ["WO-2026-%"]


def test_next_wo_number_is_max_suffix_plus_one_not_count():
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


# ── list_wos: filter assembly ─────────────────────────────────────────────

def test_list_wos_without_filters_applies_no_conditions():
    conn = _FakeConn(rows=[])
    list_wos(conn)
    assert "wo.status = %s"                       not in conn.last_sql
    assert "wo.due_date >= %s"                    not in conn.last_sql
    assert conn.last_params                       == []


def test_list_wos_status_filter():
    conn = _FakeConn(rows=[])
    list_wos(conn, status="open")
    assert "wo.status = %s" in conn.last_sql
    assert conn.last_params == ["open"]


def test_list_wos_date_filters():
    conn = _FakeConn(rows=[])
    list_wos(conn, date_from="2026-01-01", date_to="2026-12-31")
    assert "wo.due_date >= %s" in conn.last_sql
    assert "wo.due_date <= %s" in conn.last_sql
    assert conn.last_params    == ["2026-01-01", "2026-12-31"]


def test_list_wos_combined_filters():
    conn = _FakeConn(rows=[])
    list_wos(conn, status="in_progress", date_from="2026-06-01",
             date_to="2026-06-30")
    assert conn.last_params == ["in_progress", "2026-06-01", "2026-06-30"]


# ── create / update / material / status writes ───────────────────────────

def test_create_wo_returns_new_id():
    conn = _FakeConn(rows=[{"id": 7}])
    new_id = create_wo(conn, "WO-2026-0007", description="Test",
                       quantity=5, status="draft",
                       created_by="alice@example.com")
    assert new_id == 7
    assert conn.last_sql.strip().upper().startswith("INSERT INTO WORK_ORDER")
    assert "RETURNING id" in conn.last_sql
    assert conn.last_params == [
        "WO-2026-0007", None, "Test", 5, None, None, "draft", None,
        "alice@example.com"]


def test_update_wo_excludes_wo_number_and_status():
    conn = _FakeConn()
    update_wo(conn, 3, description="Updated", quantity=10,
              start_date="2026-06-01", due_date="2026-06-15")
    sql = conn.last_sql.upper()
    assert sql.strip().startswith("UPDATE WORK_ORDER")
    assert "WO_NUMBER" not in sql
    assert "STATUS"    not in sql
    assert conn.last_params == [None, "Updated", 10,
                                "2026-06-01", "2026-06-15", None, 3]


def test_add_wo_material_inserts_line():
    conn = _FakeConn()
    add_wo_material(conn, 5, product_id=2, qty_required=3,
                    qty_issued=1, notes="urgent")
    assert "INSERT INTO wo_material" in conn.last_sql
    assert conn.last_params == [5, 2, 3, 1, "urgent"]


def test_set_wo_status_updates_status():
    conn = _FakeConn()
    set_wo_status(conn, 5, "in_progress")
    assert "UPDATE work_order SET status=%s" in conn.last_sql
    assert conn.last_params == ["in_progress", 5]


def test_set_wo_status_does_not_guard_transition():
    conn = _FakeConn()
    set_wo_status(conn, 5, "completed")
    set_wo_status(conn, 5, "draft")      # illegal reopen — no exception
    assert len(conn.calls) == 2


# ── load_products ─────────────────────────────────────────────────────────

def test_load_products_returns_empty_on_error():
    import psycopg2

    class _ErrorConn:
        def execute(self, *a, **kw):
            raise psycopg2.Error("table missing")

    assert load_products(_ErrorConn()) == []
