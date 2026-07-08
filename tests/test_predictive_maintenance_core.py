"""Tests for predictive_maintenance_core — Predictive Maintenance (P4-B).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_demand_forecast_core.py). The
pure math (`_failure_probability`/`_risk_level`) is tested directly
without any DB.
"""

import math
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from manufacturing.predictive_maintenance_core import (
    SENSOR_READING_TYPES, ensure_predictive_maintenance_tables,
    _breakdown_dates, get_rolling_mtbf, _failure_probability, _risk_level,
    get_predictive_maintenance_report, record_sensor_reading,
    set_sensor_threshold, list_sensor_readings, get_sensor_alerts,
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

def test_ensure_predictive_maintenance_tables_creates_both():
    conn = MagicMock()
    ensure_predictive_maintenance_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS equipment_sensor_reading (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS equipment_sensor_threshold (' in c for c in calls)


# ── _breakdown_dates / get_rolling_mtbf ─────────────────────────────────

def test_breakdown_dates_parses_iso_strings():
    conn = _conn(fetchall_results=[[
        {'down_date': '2026-01-10'}, {'down_date': '2026-03-10'},
    ]])
    result = _breakdown_dates(conn, 'Laser Cutter')
    assert result == [date(2026, 1, 10), date(2026, 3, 10)]


def test_get_rolling_mtbf_insufficient_data_with_zero_failures():
    with patch('manufacturing.predictive_maintenance_core._breakdown_dates', return_value=[]):
        conn = MagicMock()
        result = get_rolling_mtbf(conn, 'Laser Cutter')
    assert result['failure_count'] == 0
    assert result['mtbf_days'] is None
    assert result['last_failure_date'] is None
    assert result['days_since_last_failure'] is None


def test_get_rolling_mtbf_insufficient_data_with_one_failure():
    with patch('manufacturing.predictive_maintenance_core._breakdown_dates',
               return_value=[date(2026, 1, 1)]):
        conn = MagicMock()
        result = get_rolling_mtbf(conn, 'Laser Cutter')
    assert result['failure_count'] == 1
    assert result['mtbf_days'] is None
    assert result['last_failure_date'] == '2026-01-01'


def test_get_rolling_mtbf_computes_mean_interval():
    # Breakdowns 30 and 60 days apart -> mean interval 45 days.
    dates = [date(2026, 1, 1), date(2026, 1, 31), date(2026, 4, 1)]
    with patch('manufacturing.predictive_maintenance_core._breakdown_dates', return_value=dates):
        conn = MagicMock()
        result = get_rolling_mtbf(conn, 'Laser Cutter')
    assert result['failure_count'] == 3
    assert result['mtbf_days'] == 45.0
    assert result['last_failure_date'] == '2026-04-01'


def test_get_rolling_mtbf_days_since_last_failure():
    with patch('manufacturing.predictive_maintenance_core._breakdown_dates',
               return_value=[date(2020, 1, 1), date(2020, 2, 1)]):
        conn = MagicMock()
        result = get_rolling_mtbf(conn, 'Laser Cutter')
    assert result['days_since_last_failure'] == (date.today() - date(2020, 2, 1)).days


# ── _failure_probability / _risk_level ──────────────────────────────────

def test_failure_probability_known_value():
    # mtbf=30, horizon=30 -> 1 - e^-1
    prob = _failure_probability(30, horizon_days=30)
    assert abs(prob - (1 - math.exp(-1))) < 1e-9


def test_failure_probability_none_when_mtbf_unknown():
    assert _failure_probability(None) is None
    assert _failure_probability(0) is None
    assert _failure_probability(-5) is None


def test_failure_probability_approaches_one_for_short_mtbf():
    prob = _failure_probability(1, horizon_days=30)
    assert prob > 0.99


def test_risk_level_buckets():
    assert _risk_level(None) == 'unknown'
    assert _risk_level(0.1) == 'low'
    assert _risk_level(0.25) == 'low'
    assert _risk_level(0.4) == 'medium'
    assert _risk_level(0.6) == 'medium'
    assert _risk_level(0.9) == 'high'


# ── get_predictive_maintenance_report ────────────────────────────────────

def test_report_flags_approaching_threshold():
    equipment = [{'id': 1, 'name': 'Laser Cutter'}]
    mtbf_result = {
        'equipment': 'Laser Cutter', 'failure_count': 3, 'mtbf_days': 40.0,
        'last_failure_date': '2026-01-01', 'days_since_last_failure': 35,
    }
    with patch('manufacturing.predictive_maintenance_core.list_equipment', return_value=equipment), \
         patch('manufacturing.predictive_maintenance_core.get_sensor_alerts', return_value=[]), \
         patch('manufacturing.predictive_maintenance_core.get_rolling_mtbf', return_value=mtbf_result):
        conn = MagicMock()
        result = get_predictive_maintenance_report(conn, threshold_ratio=0.8)

    row = result[0]
    assert row['threshold_days'] == 32.0
    assert row['approaching_threshold'] is True  # 35 >= 32
    assert row['risk_level'] in ('low', 'medium', 'high')
    assert row['failure_probability_30d'] is not None


def test_report_not_approaching_threshold_when_recent():
    equipment = [{'id': 1, 'name': 'Laser Cutter'}]
    mtbf_result = {
        'equipment': 'Laser Cutter', 'failure_count': 3, 'mtbf_days': 40.0,
        'last_failure_date': '2026-01-01', 'days_since_last_failure': 5,
    }
    with patch('manufacturing.predictive_maintenance_core.list_equipment', return_value=equipment), \
         patch('manufacturing.predictive_maintenance_core.get_sensor_alerts', return_value=[]), \
         patch('manufacturing.predictive_maintenance_core.get_rolling_mtbf', return_value=mtbf_result):
        conn = MagicMock()
        result = get_predictive_maintenance_report(conn, threshold_ratio=0.8)

    assert result[0]['approaching_threshold'] is False


def test_report_handles_insufficient_mtbf_data():
    equipment = [{'id': 1, 'name': 'New Machine'}]
    mtbf_result = {
        'equipment': 'New Machine', 'failure_count': 0, 'mtbf_days': None,
        'last_failure_date': None, 'days_since_last_failure': None,
    }
    with patch('manufacturing.predictive_maintenance_core.list_equipment', return_value=equipment), \
         patch('manufacturing.predictive_maintenance_core.get_sensor_alerts', return_value=[]), \
         patch('manufacturing.predictive_maintenance_core.get_rolling_mtbf', return_value=mtbf_result):
        conn = MagicMock()
        result = get_predictive_maintenance_report(conn)

    row = result[0]
    assert row['threshold_days'] is None
    assert row['approaching_threshold'] is False
    assert row['failure_probability_30d'] is None
    assert row['risk_level'] == 'unknown'


def test_report_merges_sensor_status():
    equipment = [{'id': 1, 'name': 'Laser Cutter'}]
    mtbf_result = {
        'equipment': 'Laser Cutter', 'failure_count': 0, 'mtbf_days': None,
        'last_failure_date': None, 'days_since_last_failure': None,
    }
    sensor_alerts = [
        {'equipment': 'Laser Cutter', 'reading_type': 'vibration', 'status': 'critical'},
    ]
    with patch('manufacturing.predictive_maintenance_core.list_equipment', return_value=equipment), \
         patch('manufacturing.predictive_maintenance_core.get_sensor_alerts', return_value=sensor_alerts), \
         patch('manufacturing.predictive_maintenance_core.get_rolling_mtbf', return_value=mtbf_result):
        conn = MagicMock()
        result = get_predictive_maintenance_report(conn)

    assert result[0]['sensor_statuses'] == ['critical']


# ── sensor readings / thresholds ─────────────────────────────────────────

def test_record_sensor_reading_raises_for_unknown_type():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_sensor_reading(conn, 'Laser Cutter', 'humidity', 50.0, '%', 'eric')
    assert conn.execute.call_count == 0


def test_record_sensor_reading_inserts():
    conn = _conn(fetchone_results=[{'id': 5}])
    reading_id = record_sensor_reading(conn, 'Laser Cutter', 'vibration', 4.2, 'mm/s', 'eric')
    assert reading_id == 5
    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO equipment_sensor_reading' in insert_sql
    assert insert_params[:4] == ('Laser Cutter', 'vibration', 4.2, 'mm/s')


def test_set_sensor_threshold_raises_for_unknown_type():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_sensor_threshold(conn, 'Laser Cutter', 'humidity', 5.0, 8.0)
    assert conn.execute.call_count == 0


def test_set_sensor_threshold_raises_when_warning_not_below_critical():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_sensor_threshold(conn, 'Laser Cutter', 'vibration', 8.0, 5.0)
    assert conn.execute.call_count == 0


def test_set_sensor_threshold_upserts():
    conn = MagicMock()
    set_sensor_threshold(conn, 'Laser Cutter', 'vibration', 5.0, 8.0)
    sql, params = conn.execute.call_args[0]
    assert 'ON CONFLICT (equipment, reading_type) DO UPDATE' in sql
    assert params == ('Laser Cutter', 'vibration', 5.0, 8.0)


def test_list_sensor_readings_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'value': 4.2}]])
    result = list_sensor_readings(conn, 'Laser Cutter', 'vibration')
    assert result == [{'id': 1, 'value': 4.2}]


def test_sensor_reading_types_are_vibration_and_temperature():
    assert set(SENSOR_READING_TYPES) == {'vibration', 'temperature'}


# ── get_sensor_alerts ────────────────────────────────────────────────────

def test_get_sensor_alerts_ok_below_warning():
    conn = _conn(fetchall_results=[
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration', 'value': 3.0,
          'unit': 'mm/s', 'recorded_at': '2026-07-01'}],
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration',
          'warning_max': 5.0, 'critical_max': 8.0}],
    ])
    result = get_sensor_alerts(conn)
    assert result[0]['status'] == 'ok'


def test_get_sensor_alerts_warning_between_thresholds():
    conn = _conn(fetchall_results=[
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration', 'value': 6.0,
          'unit': 'mm/s', 'recorded_at': '2026-07-01'}],
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration',
          'warning_max': 5.0, 'critical_max': 8.0}],
    ])
    result = get_sensor_alerts(conn)
    assert result[0]['status'] == 'warning'


def test_get_sensor_alerts_critical_above_critical_max():
    conn = _conn(fetchall_results=[
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration', 'value': 9.0,
          'unit': 'mm/s', 'recorded_at': '2026-07-01'}],
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration',
          'warning_max': 5.0, 'critical_max': 8.0}],
    ])
    result = get_sensor_alerts(conn)
    assert result[0]['status'] == 'critical'


def test_get_sensor_alerts_no_threshold_when_reading_but_no_threshold_set():
    conn = _conn(fetchall_results=[
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration', 'value': 9.0,
          'unit': 'mm/s', 'recorded_at': '2026-07-01'}],
        [],
    ])
    result = get_sensor_alerts(conn)
    assert result[0]['status'] == 'no_threshold'


def test_get_sensor_alerts_no_reading_when_threshold_but_no_reading():
    conn = _conn(fetchall_results=[
        [],
        [{'equipment': 'Laser Cutter', 'reading_type': 'vibration',
          'warning_max': 5.0, 'critical_max': 8.0}],
    ])
    result = get_sensor_alerts(conn)
    assert result[0]['status'] == 'no_reading'
    assert result[0]['value'] is None
