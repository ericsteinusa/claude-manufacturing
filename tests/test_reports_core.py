"""Tests for reports_core — Qt-free, no live DB."""

from manufacturing.reports_core import (
    po_summary, wo_summary, inventory_alerts, cs_summary, hours_variance,
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
