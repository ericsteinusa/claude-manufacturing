"""Tests for apm_core — Asset Performance Management."""

import pytest

from manufacturing import apm_core
from manufacturing.apm_core import (
    set_asset_criticality, get_asset_criticality, get_asset_health,
    get_apm_dashboard, CRITICALITY_LEVELS,
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


# ── criticality ──────────────────────────────────────────────────────────

def test_set_asset_criticality_requires_equipment():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_asset_criticality(conn, '   ', 'high')


def test_set_asset_criticality_validates_level():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError):
        set_asset_criticality(conn, 'CNC-01', 'extreme')


def test_all_criticality_levels_accepted():
    for level in CRITICALITY_LEVELS:
        conn = _Conn(rows=[])
        set_asset_criticality(conn, 'CNC-01', level)  # no raise


def test_get_asset_criticality_returns_default_when_unset():
    conn = _Conn(rows=[])
    result = get_asset_criticality(conn, 'CNC-01')
    assert result['criticality'] == 'medium'
    assert result['replacement_cost'] == 0.0


def test_get_asset_criticality_returns_stored_row():
    conn = _Conn(rows=[{'equipment': 'CNC-01', 'criticality': 'critical',
                        'replacement_cost': 50000.0, 'notes': 'line-stopper'}])
    result = get_asset_criticality(conn, 'CNC-01')
    assert result['criticality'] == 'critical'
    assert result['replacement_cost'] == 50000.0


# ── get_asset_health ──────────────────────────────────────────────────────

def test_get_asset_health_no_downtime_history_scores_full(monkeypatch):
    monkeypatch.setattr(apm_core, 'get_asset_criticality', lambda conn, eq: {
        'equipment': eq, 'criticality': 'medium', 'replacement_cost': 0, 'notes': '',
    })
    monkeypatch.setattr(apm_core, 'get_mtbf', lambda conn, eq, months=12: {
        'availability_pct': None, 'failure_count': 0,
    })
    conn = _Conn(rows=[{'total_cost': 0}])
    health = get_asset_health(conn, 'CNC-01')
    assert health['availability_pct'] == 100.0
    assert health['health_score'] == 100.0
    assert health['recommendation'] == 'monitor'


def test_get_asset_health_critical_asset_recommends_replacement_sooner(monkeypatch):
    monkeypatch.setattr(apm_core, 'get_asset_criticality', lambda conn, eq: {
        'equipment': eq, 'criticality': 'critical', 'replacement_cost': 0, 'notes': '',
    })
    monkeypatch.setattr(apm_core, 'get_mtbf', lambda conn, eq, months=12: {
        'availability_pct': 90.0, 'failure_count': 6,
    })
    conn = _Conn(rows=[{'total_cost': 5000}])
    health = get_asset_health(conn, 'CNC-01')
    # penalty = 6 * weight(5) * 2 = 60 -> health_score = 90 - 60 = 30
    assert health['health_score'] == 30.0
    assert health['recommendation'] == 'consider_replacement'
    assert health['lifecycle_cost'] == 5000.0


def test_get_asset_health_low_criticality_more_forgiving(monkeypatch):
    monkeypatch.setattr(apm_core, 'get_asset_criticality', lambda conn, eq: {
        'equipment': eq, 'criticality': 'low', 'replacement_cost': 0, 'notes': '',
    })
    monkeypatch.setattr(apm_core, 'get_mtbf', lambda conn, eq, months=12: {
        'availability_pct': 90.0, 'failure_count': 6,
    })
    conn = _Conn(rows=[{'total_cost': 0}])
    health = get_asset_health(conn, 'CNC-01')
    # penalty = 6 * weight(1) * 2 = 12 -> health_score = 90 - 12 = 78
    assert health['health_score'] == 78.0
    assert health['recommendation'] == 'monitor'  # low criticality threshold is 75


def test_get_asset_health_score_clamped_to_zero(monkeypatch):
    monkeypatch.setattr(apm_core, 'get_asset_criticality', lambda conn, eq: {
        'equipment': eq, 'criticality': 'critical', 'replacement_cost': 0, 'notes': '',
    })
    monkeypatch.setattr(apm_core, 'get_mtbf', lambda conn, eq, months=12: {
        'availability_pct': 50.0, 'failure_count': 20,
    })
    conn = _Conn(rows=[{'total_cost': 0}])
    health = get_asset_health(conn, 'CNC-01')
    assert health['health_score'] == 0.0


# ── get_apm_dashboard ────────────────────────────────────────────────────

def test_get_apm_dashboard_sorts_worst_first(monkeypatch):
    monkeypatch.setattr(apm_core, 'get_asset_health', lambda conn, name, months=12: {
        'CNC-01': {'equipment': 'CNC-01', 'health_score': 80.0},
        'PRESS-02': {'equipment': 'PRESS-02', 'health_score': 30.0},
    }[name])
    conn = _MultiConn([
        [{'equipment': 'CNC-01'}, {'equipment': 'PRESS-02'}],  # from asset_criticality
        [],  # from maint_downtime distinct
    ])
    dashboard = get_apm_dashboard(conn)
    assert [d['equipment'] for d in dashboard] == ['PRESS-02', 'CNC-01']
