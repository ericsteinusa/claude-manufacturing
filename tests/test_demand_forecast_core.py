"""Tests for demand_forecast_core — AI Demand Forecasting (P4-A).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_shop_floor_core.py). The
time-series model itself (``_linear_trend``/``_seasonal_indices``/
``_compute_forecast``) is pure and tested directly without any DB.
"""

from datetime import date
from unittest.mock import MagicMock, patch

from manufacturing.demand_forecast_core import (
    ensure_demand_forecast_tables, get_monthly_history,
    _linear_trend, _seasonal_indices, _compute_forecast,
    generate_forecast_for_product, generate_all_forecasts,
    list_forecast_summary, list_demand_forecast, get_forecast_demand_dated,
)


def _conn(fetchone_results=None, fetchall_results=None):
    """A MagicMock conn whose execute(...) returns one shared cursor mock;
    .fetchone()/.fetchall() replay the given results in call order."""
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── setup ────────────────────────────────────────────────────────────────

def test_ensure_demand_forecast_tables_creates_table():
    conn = MagicMock()
    ensure_demand_forecast_tables(conn)
    sql = conn.execute.call_args[0][0]
    assert 'CREATE TABLE IF NOT EXISTS demand_forecast (' in sql


# ── _linear_trend ────────────────────────────────────────────────────────

def test_linear_trend_perfect_line():
    slope, intercept = _linear_trend([10.0, 20.0, 30.0, 40.0])
    assert abs(slope - 10.0) < 1e-9
    assert abs(intercept - 10.0) < 1e-9


def test_linear_trend_flat_series():
    slope, intercept = _linear_trend([5.0, 5.0, 5.0, 5.0])
    assert abs(slope) < 1e-9
    assert abs(intercept - 5.0) < 1e-9


def test_linear_trend_single_point():
    slope, intercept = _linear_trend([42.0])
    assert slope == 0.0
    assert intercept == 42.0


def test_linear_trend_empty():
    slope, intercept = _linear_trend([])
    assert slope == 0.0
    assert intercept == 0.0


# ── _seasonal_indices ────────────────────────────────────────────────────

def test_seasonal_indices_flat_under_12_months():
    values = [10.0] * 8
    slope, intercept = _linear_trend(values)
    indices = _seasonal_indices(values, slope, intercept)
    assert indices == [1.0] * 12


def test_seasonal_indices_normalize_to_mean_one():
    # Two full years, flat trend, with a clear high month (index 5 = June).
    values = []
    for _year in range(2):
        values += [10.0, 10.0, 10.0, 10.0, 10.0, 30.0,
                   10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    slope, intercept = _linear_trend(values)
    indices = _seasonal_indices(values, slope, intercept)
    assert len(indices) == 12
    assert abs(sum(indices) / 12 - 1.0) < 1e-6
    assert indices[5] > indices[0]  # June still stands out after normalizing


# ── _compute_forecast ────────────────────────────────────────────────────

def test_compute_forecast_recovers_seasonal_pattern():
    # 3 years of a clean seasonal pattern with a flat trend (no growth).
    base = [10.0, 10.0, 10.0, 10.0, 10.0, 30.0,
            10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    history = base * 3
    forecast = _compute_forecast(history, months_ahead=12, start_position=0)
    assert len(forecast) == 12
    # Position 5 in the forecast horizon (June again) should be the peak.
    assert forecast[5] == max(forecast)
    assert forecast[5] > 20.0


def test_compute_forecast_clamps_to_nonnegative():
    # Sharp downward trend should never forecast negative units.
    history = [100.0, 80.0, 60.0, 40.0, 20.0, 0.0]
    forecast = _compute_forecast(history, months_ahead=6, start_position=0)
    assert all(v >= 0.0 for v in forecast)


def test_compute_forecast_flat_when_no_history():
    forecast = _compute_forecast([], months_ahead=3, start_position=0)
    assert forecast == [0.0, 0.0, 0.0]


# ── get_monthly_history ──────────────────────────────────────────────────

def test_get_monthly_history_zero_fills_gaps():
    # "Today" falls in July; the trailing window ends at June (last
    # complete month), matching get_monthly_history's -1 month offset.
    with patch('manufacturing.demand_forecast_core._month_floor', return_value=date(2026, 7, 1)):
        conn = _conn(fetchall_results=[[
            {'mo': date(2026, 4, 1), 'qty': 50.0},
        ]])
        result = get_monthly_history(conn, 1, months=3)

    months = [m for m, _qty in result]
    qtys = [qty for _m, qty in result]
    assert months == [date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1)]
    assert qtys == [50.0, 0.0, 0.0]


# ── generate_forecast_for_product / generate_all_forecasts ─────────────

def test_generate_forecast_for_product_upserts_rows():
    with patch('manufacturing.demand_forecast_core.get_monthly_history',
               return_value=[(date(2026, 5, 1), 10.0), (date(2026, 6, 1), 10.0)]):
        conn = MagicMock()
        result = generate_forecast_for_product(conn, 1, months_history=2, months_ahead=2)

    assert len(result) == 2
    insert_calls = [c for c in conn.execute.call_args_list
                    if 'INSERT INTO demand_forecast' in c[0][0]]
    assert len(insert_calls) == 2
    assert 'ON CONFLICT (product_id, forecast_month) DO UPDATE' in insert_calls[0][0][0]
    assert insert_calls[0][0][1][0] == 1  # product_id
    assert insert_calls[0][0][1][1] == '2026-07-01'  # first forecast month


def test_generate_all_forecasts_runs_for_each_product():
    with patch('manufacturing.demand_forecast_core.generate_forecast_for_product') as mock_gen:
        conn = _conn(fetchall_results=[[{'product_id': 1}, {'product_id': 2}]])
        count = generate_all_forecasts(conn)

    assert count == 2
    assert mock_gen.call_count == 2
    assert mock_gen.call_args_list[0][0][:2] == (conn, 1)
    assert mock_gen.call_args_list[1][0][:2] == (conn, 2)


# ── read helpers ─────────────────────────────────────────────────────────

def test_list_forecast_summary_returns_rows():
    conn = _conn(fetchall_results=[[
        {'product_id': 1, 'product_name': 'Widget', 'total_forecast_qty': 500.0,
         'generated_at': '2026-07-01T00:00:00'},
    ]])
    result = list_forecast_summary(conn)
    assert result[0]['product_name'] == 'Widget'


def test_list_demand_forecast_merges_actual_and_forecast():
    with patch('manufacturing.demand_forecast_core.get_monthly_history',
               return_value=[(date(2026, 5, 1), 20.0)]):
        conn = _conn(fetchall_results=[[
            {'forecast_month': date(2026, 6, 1), 'forecast_qty': 15.0},
        ]])
        result = list_demand_forecast(conn, 1)

    assert result[0] == {'month': '2026-05-01', 'actual_qty': 20.0,
                         'forecast_qty': None, 'is_forecast': False}
    assert result[1] == {'month': '2026-06-01', 'actual_qty': None,
                         'forecast_qty': 15.0, 'is_forecast': True}


def test_get_forecast_demand_dated_matches_mrp_shape():
    conn = _conn(fetchall_results=[[
        {'product_id': 1, 'forecast_month': date(2026, 8, 1), 'forecast_qty': 40.0},
        {'product_id': 1, 'forecast_month': date(2026, 9, 1), 'forecast_qty': 45.0},
        {'product_id': 2, 'forecast_month': date(2026, 8, 1), 'forecast_qty': 10.0},
    ]])
    result = get_forecast_demand_dated(conn)
    assert result[1] == [(40.0, date(2026, 8, 1)), (45.0, date(2026, 9, 1))]
    assert result[2] == [(10.0, date(2026, 8, 1))]
