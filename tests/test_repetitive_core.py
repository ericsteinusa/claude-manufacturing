"""Tests for repetitive_core — Repetitive Manufacturing."""

import pytest

from manufacturing import repetitive_core
from manufacturing.repetitive_core import (
    create_schedule, set_schedule_status, log_production,
    get_schedule_summary, SCHEDULE_STATUSES,
)


# ── fake DB infrastructure (mirrors test_skills_matrix_core.py) ────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)


class _MultiConn:
    def __init__(self, responses):
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])


# ── create_schedule ──────────────────────────────────────────────────────

def test_create_schedule_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    schedule_id = create_schedule(conn, product_id=10, workcenter_id=1, rate_per_day=100.0)
    assert schedule_id == 1


def test_create_schedule_requires_positive_rate():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_schedule(conn, product_id=10, workcenter_id=1, rate_per_day=0)


# ── set_schedule_status ──────────────────────────────────────────────────

def test_set_schedule_status_validates():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_schedule_status(conn, schedule_id=1, status='bogus')


def test_all_schedule_statuses_accepted():
    for status in SCHEDULE_STATUSES:
        conn = _Conn(rows=[])
        set_schedule_status(conn, schedule_id=1, status=status)  # no raise


# ── log_production / backflush ───────────────────────────────────────────

def test_log_production_raises_when_schedule_missing(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: None)
    with pytest.raises(ValueError, match='No schedule'):
        log_production(_Conn(), schedule_id=1, production_date='2026-07-10', qty_completed=10)


def test_log_production_rejects_negative_quantities(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: {
        'id': 1, 'product_id': 10,
    })
    with pytest.raises(ValueError, match='cannot be negative'):
        log_production(_Conn(), schedule_id=1, production_date='2026-07-10', qty_completed=-5)


def test_log_production_zero_completed_skips_backflush(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: {
        'id': 1, 'product_id': 10,
    })
    record_calls = []
    monkeypatch.setattr(repetitive_core, 'record_transaction',
                        lambda *a, **k: record_calls.append(a))
    conn = _Conn(rows=[{'id': 99}])
    log_id = log_production(conn, schedule_id=1, production_date='2026-07-10',
                            qty_completed=0, qty_scrapped=5)
    assert log_id == 99
    assert record_calls == []


def test_log_production_backflushes_components_and_receives_output(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: {
        'id': 1, 'product_id': 10,
    })
    monkeypatch.setattr(repetitive_core, 'get_bom', lambda conn, pid: [
        {'component_id': 5, 'qty_required': 2.0, 'scrap_pct': 0.0},
        {'component_id': 6, 'qty_required': 1.0, 'scrap_pct': 0.0},
    ])
    record_calls = []

    def fake_record_transaction(conn, product_id, trans_type, quantity, reference, notes, created_by):
        record_calls.append((product_id, trans_type, quantity))

    monkeypatch.setattr(repetitive_core, 'record_transaction', fake_record_transaction)
    conn = _Conn(rows=[{'id': 77}])

    log_id = log_production(conn, schedule_id=1, production_date='2026-07-10',
                            qty_completed=50, qty_scrapped=2, created_by='op@example.com')
    assert log_id == 77
    # two component issues + one finished-good receive
    assert (5, 'issue', 100.0) in record_calls
    assert (6, 'issue', 50.0) in record_calls
    assert (10, 'receive', 50.0) in record_calls
    assert len(record_calls) == 3


# ── get_schedule_summary ─────────────────────────────────────────────────

def test_get_schedule_summary_raises_when_missing(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: None)
    with pytest.raises(ValueError, match='No schedule'):
        get_schedule_summary(_Conn(), schedule_id=1, date_from='2026-07-01', date_to='2026-07-10')


def test_get_schedule_summary_computes_attainment(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: {
        'id': 1, 'rate_per_day': 100.0,
    })
    conn = _Conn(rows=[{'actual': 800.0, 'scrapped': 20.0}])
    # 10-day range (inclusive) x 100/day = 1000 planned
    summary = get_schedule_summary(conn, schedule_id=1, date_from='2026-07-01', date_to='2026-07-10')
    assert summary['planned_qty'] == 1000.0
    assert summary['actual_qty'] == 800.0
    assert summary['scrapped_qty'] == 20.0
    assert summary['attainment_pct'] == 80.0


def test_get_schedule_summary_handles_zero_planned(monkeypatch):
    monkeypatch.setattr(repetitive_core, 'get_schedule', lambda conn, sid: {
        'id': 1, 'rate_per_day': 0.0,
    })
    conn = _Conn(rows=[{'actual': 0.0, 'scrapped': 0.0}])
    summary = get_schedule_summary(conn, schedule_id=1, date_from='2026-07-01', date_to='2026-07-01')
    assert summary['attainment_pct'] is None
