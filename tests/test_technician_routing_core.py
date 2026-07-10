"""Tests for technician_routing_core — Technician Routing & Scheduling."""

import pytest

from manufacturing import technician_routing_core
from manufacturing.technician_routing_core import (
    create_route, set_route_status, add_stop, move_stop, complete_stop,
    get_route_summary, ROUTE_STATUSES,
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


# ── routes ───────────────────────────────────────────────────────────────

def test_create_route_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    route_id = create_route(conn, mechanic_id=5, route_date='2026-07-10')
    assert route_id == 1


def test_set_route_status_validates():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_route_status(conn, route_id=1, status='bogus')


def test_all_route_statuses_accepted():
    for status in ROUTE_STATUSES:
        conn = _Conn(rows=[])
        set_route_status(conn, route_id=1, status=status)  # no raise


# ── stops ────────────────────────────────────────────────────────────────

def test_add_stop_rejects_duplicate_wo():
    conn = _MultiConn([[{'id': 9}]])  # existing stop found
    with pytest.raises(ValueError, match='already on this route'):
        add_stop(conn, route_id=1, wo_id=100)


def test_add_stop_assigns_next_sequence():
    conn = _MultiConn([
        [],  # no existing stop
        [{'max_seq': 20}],  # current max sequence
        [{'id': 5}],  # insert
    ])
    stop_id = add_stop(conn, route_id=1, wo_id=100, estimated_minutes=45)
    assert stop_id == 5
    insert_call = [c for c in conn.calls if 'INSERT INTO technician_route_stop' in c[0]][0]
    assert insert_call[1] == [1, 100, 30, 45, '']


def test_move_stop_validates_direction():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match="'up' or 'down'"):
        move_stop(conn, route_id=1, stop_id=1, direction='sideways')


def test_move_stop_raises_when_stop_not_found(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'list_stops', lambda conn, rid: [
        {'id': 1, 'sequence': 10}, {'id': 2, 'sequence': 20},
    ])
    with pytest.raises(ValueError, match='No stop'):
        move_stop(_Conn(), route_id=1, stop_id=999, direction='up')


def test_move_stop_noop_at_top_edge(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'list_stops', lambda conn, rid: [
        {'id': 1, 'sequence': 10}, {'id': 2, 'sequence': 20},
    ])
    conn = _Conn(rows=[])
    move_stop(conn, route_id=1, stop_id=1, direction='up')
    assert conn.calls == []


def test_move_stop_swaps_sequences(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'list_stops', lambda conn, rid: [
        {'id': 1, 'sequence': 10}, {'id': 2, 'sequence': 20},
    ])
    conn = _Conn(rows=[])
    move_stop(conn, route_id=1, stop_id=2, direction='up')
    updates = [c for c in conn.calls if 'UPDATE technician_route_stop SET sequence' in c[0]]
    assert len(updates) == 2
    assert updates[0][1] == [10, 2]
    assert updates[1][1] == [20, 1]


# ── complete_stop ────────────────────────────────────────────────────────

def test_complete_stop_raises_when_stop_missing():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError, match='No stop'):
        complete_stop(conn, stop_id=999)


def test_complete_stop_raises_when_wo_missing(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'get_work_order', lambda conn, wid: None)
    conn = _MultiConn([[{'route_id': 1, 'wo_id': 100}]])
    with pytest.raises(ValueError, match='No work order'):
        complete_stop(conn, stop_id=1)


def test_complete_stop_completes_wo_and_marks_route_when_all_done(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'get_work_order', lambda conn, wid: {'id': wid})
    complete_wo_calls = []
    monkeypatch.setattr(technician_routing_core, 'complete_work_order',
                        lambda conn, wid: complete_wo_calls.append(wid))
    conn = _MultiConn([
        [{'route_id': 1, 'wo_id': 100}],  # stop lookup
        [],  # UPDATE stop status
        [{'n': 0}],  # remaining incomplete count -> 0
        [],  # UPDATE route status
    ])
    complete_stop(conn, stop_id=1, notes='done')
    assert complete_wo_calls == [100]
    route_status_calls = [c for c in conn.calls if "UPDATE technician_route SET status" in c[0]]
    assert route_status_calls[0][1] == ['completed', 1]


def test_complete_stop_leaves_route_open_when_stops_remain(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'get_work_order', lambda conn, wid: {'id': wid})
    monkeypatch.setattr(technician_routing_core, 'complete_work_order', lambda conn, wid: None)
    conn = _MultiConn([
        [{'route_id': 1, 'wo_id': 100}],
        [],
        [{'n': 2}],  # still 2 remaining
    ])
    complete_stop(conn, stop_id=1)
    route_status_calls = [c for c in conn.calls if "UPDATE technician_route SET status" in c[0]]
    assert route_status_calls == []


# ── get_route_summary ────────────────────────────────────────────────────

def test_get_route_summary_computes_percent(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'list_stops', lambda conn, rid: [
        {'status': 'completed', 'estimated_minutes': 30},
        {'status': 'pending', 'estimated_minutes': 45},
        {'status': 'completed', 'estimated_minutes': 20},
    ])
    summary = get_route_summary(_Conn(), route_id=1)
    assert summary['total_stops'] == 3
    assert summary['completed_stops'] == 2
    assert summary['total_estimated_minutes'] == 95
    assert summary['percent_complete'] == 66.7


def test_get_route_summary_handles_empty_route(monkeypatch):
    monkeypatch.setattr(technician_routing_core, 'list_stops', lambda conn, rid: [])
    summary = get_route_summary(_Conn(), route_id=1)
    assert summary['total_stops'] == 0
    assert summary['percent_complete'] == 0.0
