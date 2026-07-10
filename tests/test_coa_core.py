"""Tests for coa_core — Certificate of Analysis generation from SPC data."""

import pytest

from manufacturing.coa_core import generate_coa, get_coa, get_coa_results, next_coa_number
import manufacturing.coa_core as coa_core


# ── fake DB infrastructure (mirrors test_price_list_core.py / test_discount_core.py)

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


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


class _Conn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)


# ── next_coa_number ──────────────────────────────────────────────────────

def test_next_coa_number_first_of_year():
    conn = _Conn(rows=[])
    n = next_coa_number(conn)
    assert n.startswith('COA-')
    assert n.endswith('-0001')


def test_next_coa_number_increments_past_max():
    import datetime
    year = datetime.date.today().year
    conn = _Conn(rows=[{'coa_number': f'COA-{year}-0003'},
                        {'coa_number': f'COA-{year}-0007'}])
    n = next_coa_number(conn)
    assert n == f'COA-{year}-0008'


# ── generate_coa ─────────────────────────────────────────────────────────

def test_generate_coa_raises_if_lot_missing(monkeypatch):
    monkeypatch.setattr(coa_core, 'get_lot', lambda conn, lot_id: None)
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='No lot'):
        generate_coa(conn, 999, 'inspector', 'eric')


def test_generate_coa_raises_if_no_measurements(monkeypatch):
    monkeypatch.setattr(coa_core, 'get_lot', lambda conn, lot_id: {'id': lot_id})
    monkeypatch.setattr(coa_core, '_latest_measurements_for_lot', lambda conn, lot_id: [])
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='nothing to certify'):
        generate_coa(conn, 1, 'inspector', 'eric')


def test_generate_coa_overall_pass_when_all_in_control(monkeypatch):
    monkeypatch.setattr(coa_core, 'get_lot', lambda conn, lot_id: {'id': lot_id})
    monkeypatch.setattr(coa_core, '_latest_measurements_for_lot', lambda conn, lot_id: [
        {'characteristic': 'Diameter', 'measured_value': 5.01, 'in_control': True,
         'target': 5.0, 'lcl': 4.9, 'ucl': 5.1},
        {'characteristic': 'Weight', 'measured_value': 2.0, 'in_control': True,
         'target': 2.0, 'lcl': 1.9, 'ucl': 2.1},
    ])
    conn = _MultiConn([
        [],                 # next_coa_number lookup
        [{'id': 42}],       # INSERT INTO coa_document RETURNING id
        [],                 # INSERT coa_result (Diameter)
        [],                 # INSERT coa_result (Weight)
        [],                 # UPDATE coa_document overall_result
    ])
    coa_id = generate_coa(conn, 1, 'inspector', 'eric')
    assert coa_id == 42
    # last call is the UPDATE with overall_result='pass'
    update_sql, update_params = conn.calls[-1]
    assert 'UPDATE coa_document' in update_sql
    assert update_params[0] == 'pass'


def test_generate_coa_overall_fail_when_any_out_of_control(monkeypatch):
    monkeypatch.setattr(coa_core, 'get_lot', lambda conn, lot_id: {'id': lot_id})
    monkeypatch.setattr(coa_core, '_latest_measurements_for_lot', lambda conn, lot_id: [
        {'characteristic': 'Diameter', 'measured_value': 5.5, 'in_control': False,
         'target': 5.0, 'lcl': 4.9, 'ucl': 5.1},
    ])
    conn = _MultiConn([
        [],
        [{'id': 7}],
        [],
        [],
    ])
    generate_coa(conn, 1, 'inspector', 'eric')
    update_sql, update_params = conn.calls[-1]
    assert update_params[0] == 'fail'


def test_generate_coa_no_spec_when_no_control_limit(monkeypatch):
    monkeypatch.setattr(coa_core, 'get_lot', lambda conn, lot_id: {'id': lot_id})
    monkeypatch.setattr(coa_core, '_latest_measurements_for_lot', lambda conn, lot_id: [
        {'characteristic': 'Color', 'measured_value': None, 'in_control': True,
         'target': None, 'lcl': None, 'ucl': None},
    ])
    conn = _MultiConn([
        [],
        [{'id': 3}],
        [],
        [],
    ])
    generate_coa(conn, 1, 'inspector', 'eric')
    insert_sql, insert_params = conn.calls[-2]
    assert 'INSERT INTO coa_result' in insert_sql
    assert insert_params[-1] == 'no_spec'
    # a lot with only no_spec characteristics still overall-passes (no failure found)
    assert conn.calls[-1][1][0] == 'pass'


# ── get_coa / get_coa_results ────────────────────────────────────────────

def test_get_coa_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_coa(conn, 1) is None


def test_get_coa_results_orders_by_characteristic():
    conn = _Conn(rows=[{'characteristic': 'A'}, {'characteristic': 'B'}])
    results = get_coa_results(conn, 1)
    assert [r['characteristic'] for r in results] == ['A', 'B']
