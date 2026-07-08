"""Tests for carbon_core — Sustainability / Carbon Cost Tracking (P4-G).

No live database: a MagicMock connection stands in for psycopg2 (mirrors
tests/test_report_builder_core.py, tests/test_ecommerce_core.py).
"""

from unittest.mock import MagicMock

import pytest

from manufacturing.carbon_core import (
    ensure_carbon_tables, set_material_factor, set_workcenter_factor,
    list_workcenters_with_carbon_factor,
    roll_carbon_footprint, get_carbon_footprint, list_carbon_history,
    save_wo_carbon_actual, get_wo_carbon,
    set_scope2_entry, list_scope2_entries, get_esg_summary,
    _MAX_DEPTH,
)


def _conn(fetchone_results=None, fetchall_results=None):
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── setup ────────────────────────────────────────────────────────────────

def test_ensure_carbon_tables_creates_expected_objects():
    conn = MagicMock()
    ensure_carbon_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('ALTER TABLE product ADD COLUMN IF NOT EXISTS' in c for c in calls)
    assert any('ALTER TABLE workcenter ADD COLUMN IF NOT EXISTS' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS carbon_roll (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS wo_carbon_actual (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS carbon_scope2_entry (' in c for c in calls)


def test_set_material_factor():
    conn = MagicMock()
    set_material_factor(conn, 5, 2.5)
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE product SET kg_co2e_per_unit' in sql
    assert params == (2.5, 5)


def test_set_workcenter_factor():
    conn = MagicMock()
    set_workcenter_factor(conn, 3, 0.8)
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE workcenter SET kg_co2e_per_hour' in sql
    assert params == (0.8, 3)


def test_list_workcenters_with_carbon_factor():
    conn = _conn(fetchall_results=[[{'id': 1, 'name': 'Assembly', 'kg_co2e_per_hour': 1.2}]])
    result = list_workcenters_with_carbon_factor(conn)
    assert result == [{'id': 1, 'name': 'Assembly', 'kg_co2e_per_hour': 1.2}]


# ── roll_carbon_footprint ────────────────────────────────────────────────

def test_roll_carbon_footprint_buy_item_uses_direct_factor():
    conn = _conn(fetchone_results=[
        {'item_type': 'buy', 'kg_co2e_per_unit': 1.5},
    ])
    result = roll_carbon_footprint(conn, product_id=1)
    assert result == {'material_carbon_kg': 1.5, 'process_carbon_kg': 0.0, 'total_carbon_kg': 1.5}
    insert_calls = [c for c in conn.execute.call_args_list if 'INSERT INTO carbon_roll' in c[0][0]]
    assert len(insert_calls) == 1


def test_roll_carbon_footprint_make_item_sums_children_and_process():
    # product 3 is 'make' with one BOM line (component 4, qty 2, scrap 10%)
    # component 4 is 'buy' with kg_co2e_per_unit=5.0; routing process carbon = 3.0
    conn = _conn(
        fetchone_results=[
            {'item_type': 'make', 'kg_co2e_per_unit': 0},   # product 3 lookup
            {'item_type': 'buy', 'kg_co2e_per_unit': 5.0},  # component 4 lookup
            {'process_carbon': 3.0},                        # routing process carbon for product 3
        ],
        fetchall_results=[
            [{'component_id': 4, 'qty_required': 2, 'scrap_pct': 10, 'name': 'Comp',
              'item_type': 'buy', 'kg_co2e_per_unit': 5.0}],  # BOM lines for product 3
        ],
    )
    result = roll_carbon_footprint(conn, product_id=3)
    # material = 5.0 (child total) * 2 * 1.1 = 11.0 ; process = 3.0
    assert abs(result['material_carbon_kg'] - 11.0) < 0.001
    assert abs(result['process_carbon_kg'] - 3.0) < 0.001
    assert abs(result['total_carbon_kg'] - 14.0) < 0.001


def test_roll_carbon_footprint_stops_at_cycle():
    _visited = {10}
    result = roll_carbon_footprint(MagicMock(), product_id=10, _visited=_visited)
    assert result == {'material_carbon_kg': 0.0, 'process_carbon_kg': 0.0, 'total_carbon_kg': 0.0}


def test_roll_carbon_footprint_stops_at_max_depth():
    conn = MagicMock()
    result = roll_carbon_footprint(conn, product_id=1, _depth=_MAX_DEPTH + 1)
    assert result == {'material_carbon_kg': 0.0, 'process_carbon_kg': 0.0, 'total_carbon_kg': 0.0}
    assert conn.execute.call_count == 0


def test_roll_carbon_footprint_missing_product_returns_zeros():
    conn = _conn(fetchone_results=[None])
    result = roll_carbon_footprint(conn, product_id=999)
    assert result == {'material_carbon_kg': 0.0, 'process_carbon_kg': 0.0, 'total_carbon_kg': 0.0}


def test_get_carbon_footprint_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_carbon_footprint(conn, 999) is None


def test_list_carbon_history_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'total_carbon_kg': 5.0}]])
    assert list_carbon_history(conn, 1) == [{'id': 1, 'total_carbon_kg': 5.0}]


# ── save_wo_carbon_actual ────────────────────────────────────────────────

def test_save_wo_carbon_actual_multiplies_by_quantity():
    conn = _conn(fetchone_results=[
        {'product_id': 7, 'quantity': 10},
        {'material_carbon_kg': 2.0, 'process_carbon_kg': 1.0, 'total_carbon_kg': 3.0},
    ])
    result = save_wo_carbon_actual(conn, wo_id=1, created_by='eric')
    assert result == {
        'quantity': 10.0, 'material_carbon_kg': 20.0, 'process_carbon_kg': 10.0,
        'total_carbon_kg': 30.0, 'carbon_per_unit_kg': 3.0,
    }
    insert_calls = [c for c in conn.execute.call_args_list if 'INSERT INTO wo_carbon_actual' in c[0][0]]
    assert len(insert_calls) == 1
    assert 'ON CONFLICT (wo_id) DO UPDATE' in insert_calls[0][0][0]


def test_save_wo_carbon_actual_raises_when_wo_missing():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        save_wo_carbon_actual(conn, wo_id=999)


def test_save_wo_carbon_actual_handles_no_roll_yet():
    conn = _conn(fetchone_results=[
        {'product_id': 7, 'quantity': 5},
        None,  # no carbon_roll exists for this product yet
    ])
    result = save_wo_carbon_actual(conn, wo_id=1)
    assert result['total_carbon_kg'] == 0.0
    assert result['carbon_per_unit_kg'] == 0.0


def test_get_wo_carbon_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_wo_carbon(conn, 999) is None


# ── scope 2 ───────────────────────────────────────────────────────────────

def test_set_scope2_entry_computes_total_and_upserts():
    conn = MagicMock()
    set_scope2_entry(conn, '2026-07', 1000, 0.4, notes='test', created_by='eric')
    sql, params = conn.execute.call_args[0]
    assert 'ON CONFLICT (period_month) DO UPDATE' in sql
    assert params == ('2026-07', 1000, 0.4, 400.0, 'test', 'eric')


def test_set_scope2_entry_requires_period_month():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_scope2_entry(conn, '', 1000, 0.4)
    assert conn.execute.call_count == 0


def test_list_scope2_entries_returns_rows():
    conn = _conn(fetchall_results=[[{'period_month': '2026-07', 'total_kg_co2e': 400.0}]])
    assert list_scope2_entries(conn) == [{'period_month': '2026-07', 'total_kg_co2e': 400.0}]


# ── ESG dashboard summary ─────────────────────────────────────────────────

def test_get_esg_summary_aggregates_all_scopes():
    conn = _conn(
        fetchone_results=[
            {'scope1_kg': 100.0, 'scope3_kg': 250.0},  # scope 1/3 aggregate
            {'scope2_kg': 400.0},                       # scope 2 aggregate
        ],
        fetchall_results=[
            [{'product_id': 1, 'name': 'Widget', 'total_carbon_kg': 350.0}],  # by_product
            [{'month': '2026-07', 'scope1_kg': 100.0, 'scope3_kg': 250.0}],   # monthly_trend
        ],
    )
    result = get_esg_summary(conn)
    assert result['scope1_kg'] == 100.0
    assert result['scope2_kg'] == 400.0
    assert result['scope3_kg'] == 250.0
    assert result['total_kg'] == 750.0
    assert result['by_product'] == [{'product_id': 1, 'name': 'Widget', 'total_carbon_kg': 350.0}]
    assert result['monthly_trend'] == [{'month': '2026-07', 'scope1_kg': 100.0, 'scope3_kg': 250.0}]


def test_get_esg_summary_date_filter_adds_where_clause():
    conn = _conn(
        fetchone_results=[{'scope1_kg': 0.0, 'scope3_kg': 0.0}, {'scope2_kg': 0.0}],
        fetchall_results=[[], []],
    )
    get_esg_summary(conn, date_from='2026-01-01', date_to='2026-12-31')
    first_sql, first_params = conn.execute.call_args_list[0][0]
    assert 'WHERE w.created_at >= %s AND w.created_at <= %s' in first_sql
    assert first_params == ['2026-01-01', '2026-12-31']
