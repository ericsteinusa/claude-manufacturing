"""Tests for sampling_plan_core — Sampling Plans & AQL (P2-E).

No live database: a fake connection replays canned rows, so the ISO
2859-1 lookup math and CRUD SQL are pinned down without Postgres.
"""

import pytest

from manufacturing.sampling_plan_core import (
    INSPECTION_LEVELS, SAMPLE_SIZE_BY_CODE, LOT_SIZE_RANGES,
    code_letter_for_lot_size, resolve_sampling_plan, evaluate_sampling_result,
    list_sampling_plans, get_sampling_plan, create_sampling_plan,
    update_sampling_plan, find_applicable_plans, ensure_sampling_plan_tables,
)


# ── fake DB infrastructure ──────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Single canned row-set returned for every execute() call."""
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


class _DispatchConn:
    """Returns canned rows based on a substring match against the SQL."""
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows)
        return _Cursor([])


# ── code_letter_for_lot_size ─────────────────────────────────────────────────

def test_code_letter_smallest_lot_level_ii():
    assert code_letter_for_lot_size(5, 'II') == 'A'


def test_code_letter_boundaries_are_inclusive():
    # 281-500 -> level II code H
    assert code_letter_for_lot_size(281, 'II') == 'H'
    assert code_letter_for_lot_size(500, 'II') == 'H'
    assert code_letter_for_lot_size(501, 'II') == 'J'


def test_code_letter_differs_by_inspection_level():
    # lot size 100 -> level I: D, level II: F, level III: G
    assert code_letter_for_lot_size(100, 'I') == 'D'
    assert code_letter_for_lot_size(100, 'II') == 'F'
    assert code_letter_for_lot_size(100, 'III') == 'G'


def test_code_letter_unbounded_top_range():
    assert code_letter_for_lot_size(10_000_000, 'II') == 'Q'


def test_code_letter_below_smallest_range_returns_none():
    assert code_letter_for_lot_size(1, 'II') is None


def test_code_letter_rejects_unknown_inspection_level():
    with pytest.raises(ValueError):
        code_letter_for_lot_size(100, 'IV')


def test_lot_size_ranges_cover_every_code_letter_used():
    used_codes = {c for _, _, *codes in LOT_SIZE_RANGES for c in codes}
    assert used_codes <= set(SAMPLE_SIZE_BY_CODE)


def test_inspection_levels_constant():
    assert INSPECTION_LEVELS == ('I', 'II', 'III')


# ── resolve_sampling_plan ─────────────────────────────────────────────────────

def test_resolve_sampling_plan_computes_code_and_sample_size():
    plan_row = {'id': 1, 'plan_name': 'P', 'aql_value': 2.5,
                'inspection_level': 'II', 'product_id': None,
                'supplier_id': None, 'product_name': None, 'supplier_name': None}
    conn = _DispatchConn([
        ("FROM sampling_plan", [plan_row]),
        ("FROM aql_accept_reject", [{'accept_number': 3, 'reject_number': 4}]),
    ])
    result = resolve_sampling_plan(conn, 1, lot_qty=300)
    # lot 300 -> level II -> code H; AQL 2.5 @ H -> 3/4 in the starter set
    assert result == {
        'code_letter': 'H', 'sample_size': 50,
        'accept_number': 3, 'reject_number': 4,
    }


def test_resolve_sampling_plan_missing_accept_reject_row_leaves_none():
    plan_row = {'id': 1, 'plan_name': 'P', 'aql_value': 99.0,
                'inspection_level': 'II', 'product_id': None,
                'supplier_id': None, 'product_name': None, 'supplier_name': None}
    conn = _DispatchConn([
        ("FROM sampling_plan", [plan_row]),
        ("FROM aql_accept_reject", []),
    ])
    result = resolve_sampling_plan(conn, 1, lot_qty=300)
    assert result['code_letter'] == 'H'
    assert result['sample_size'] == 50
    assert result['accept_number'] is None
    assert result['reject_number'] is None


def test_resolve_sampling_plan_raises_for_missing_plan():
    conn = _DispatchConn([("FROM sampling_plan", [])])
    with pytest.raises(ValueError):
        resolve_sampling_plan(conn, 999, lot_qty=100)


def test_resolve_sampling_plan_raises_for_lot_too_small():
    plan_row = {'id': 1, 'plan_name': 'P', 'aql_value': 2.5,
                'inspection_level': 'II', 'product_id': None,
                'supplier_id': None, 'product_name': None, 'supplier_name': None}
    conn = _DispatchConn([("FROM sampling_plan", [plan_row])])
    with pytest.raises(ValueError):
        resolve_sampling_plan(conn, 1, lot_qty=1)


# ── evaluate_sampling_result ─────────────────────────────────────────────────

def test_evaluate_passes_at_or_below_accept_number():
    assert evaluate_sampling_result(3, 4, 0) == 'passed'
    assert evaluate_sampling_result(3, 4, 3) == 'passed'


def test_evaluate_fails_at_or_above_reject_number():
    assert evaluate_sampling_result(3, 4, 4) == 'failed'
    assert evaluate_sampling_result(3, 4, 10) == 'failed'


def test_evaluate_none_when_accept_reject_unknown():
    assert evaluate_sampling_result(None, None, 0) is None


def test_evaluate_none_when_qty_defective_not_recorded():
    assert evaluate_sampling_result(3, 4, None) is None


# ── sampling_plan CRUD ───────────────────────────────────────────────────────

def test_list_sampling_plans_filters_by_active_and_search():
    conn = _Conn(rows=[])
    list_sampling_plans(conn, is_active=True, search='Steel')
    assert "sp.is_active = %s" in conn.last_sql
    assert "sp.plan_name ILIKE %s" in conn.last_sql
    assert conn.last_params == [True, '%Steel%']


def test_get_sampling_plan_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_sampling_plan(conn, 1) is None


def test_create_sampling_plan_rejects_unknown_inspection_level():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_sampling_plan(conn, 'Plan', 2.5, inspection_level='IX')


def test_create_sampling_plan_inserts_and_returns_id():
    conn = _Conn(rows=[{'id': 7}])
    plan_id = create_sampling_plan(conn, ' Steel Plan ', 2.5, 'II',
                                    product_id=3, supplier_id=None,
                                    notes='n', created_by='qa@x.com')
    assert plan_id == 7
    assert conn.last_params == ['Steel Plan', 2.5, 'II', 3, None, 'n', 'qa@x.com']


def test_update_sampling_plan_ignores_unknown_fields():
    conn = _Conn(rows=[])
    update_sampling_plan(conn, 1, plan_name='New', bogus_field='x')
    assert "plan_name = %s" in conn.last_sql
    assert "bogus_field" not in conn.last_sql


def test_update_sampling_plan_noop_when_no_valid_fields():
    conn = _Conn(rows=[])
    update_sampling_plan(conn, 1, bogus_field='x')
    assert conn.calls == []


def test_find_applicable_plans_includes_general_and_scoped():
    conn = _Conn(rows=[])
    find_applicable_plans(conn, product_id=5, supplier_id=9)
    assert "sp.product_id IS NULL AND sp.supplier_id IS NULL" in conn.last_sql
    assert "sp.product_id = %s" in conn.last_sql
    assert "sp.supplier_id = %s" in conn.last_sql
    assert conn.last_params == [5, 9]


def test_find_applicable_plans_filters_active_only():
    conn = _Conn(rows=[])
    find_applicable_plans(conn)
    assert "sp.is_active = TRUE" in conn.last_sql


# ── ensure_sampling_plan_tables ──────────────────────────────────────────────

def test_ensure_tables_creates_sampling_plan_and_accept_reject():
    conn = _Conn(rows=[{'n': 1}])  # non-zero count -> skip seeding
    ensure_sampling_plan_tables(conn)
    sqls = [s for s, _ in conn.calls]
    assert any('CREATE TABLE IF NOT EXISTS sampling_plan' in s for s in sqls)
    assert any('CREATE TABLE IF NOT EXISTS aql_accept_reject' in s for s in sqls)
    assert any('sampling_plan_id' in s for s in sqls)
    assert any('qty_defective' in s for s in sqls)


def test_ensure_tables_seeds_starter_data_only_when_empty():
    conn = _Conn(rows=[{'n': 0}])
    ensure_sampling_plan_tables(conn)
    sqls = [s for s, _ in conn.calls]
    assert any('INSERT INTO aql_accept_reject' in s for s in sqls)
