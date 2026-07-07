"""Tests for shop_floor_core — OEE Live Shop Floor Dashboard (P3-G).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_blanket_po_core.py /
test_multi_entity_core.py).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from manufacturing.shop_floor_core import (
    SHIFTS, SHIFT_LENGTH_HOURS, SHIFT_WINDOWS, current_shift_for_now,
    ensure_shop_floor_tables, record_production, record_downtime,
    set_shift_plan, get_shift_oee, list_live_shift_oee, list_downtime_entries,
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

def test_ensure_shop_floor_tables_creates_everything():
    conn = MagicMock()
    ensure_shop_floor_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS shop_floor_production (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS shop_floor_downtime (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS shop_floor_shift_plan (' in c for c in calls)


# ── current_shift_for_now ────────────────────────────────────────────────

def test_current_shift_for_now_day():
    now = datetime(2026, 7, 7, 9, 0)
    shift, d = current_shift_for_now(now)
    assert shift == 'Day'
    assert d == now.date()


def test_current_shift_for_now_swing():
    now = datetime(2026, 7, 7, 15, 30)
    shift, d = current_shift_for_now(now)
    assert shift == 'Swing'
    assert d == now.date()


def test_current_shift_for_now_night_before_midnight():
    now = datetime(2026, 7, 7, 23, 0)
    shift, d = current_shift_for_now(now)
    assert shift == 'Night'
    assert d == now.date()


def test_current_shift_for_now_night_after_midnight_belongs_to_previous_day():
    now = datetime(2026, 7, 7, 2, 0)
    shift, d = current_shift_for_now(now)
    assert shift == 'Night'
    assert d.isoformat() == '2026-07-06'


def test_shift_windows_cover_all_shifts():
    assert set(SHIFT_WINDOWS.keys()) == set(SHIFTS)


# ── record_production ────────────────────────────────────────────────────

def test_record_production_raises_for_unknown_shift():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_production(conn, 1, 'Graveyard', '2026-07-07', 10, 0, 'eric')
    assert conn.execute.call_count == 0


def test_record_production_raises_for_negative_qty():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_production(conn, 1, 'Day', '2026-07-07', -5, 0, 'eric')
    assert conn.execute.call_count == 0


def test_record_production_inserts_and_returns_id():
    conn = _conn(fetchone_results=[{'id': 7}])
    entry_id = record_production(conn, 1, 'Day', '2026-07-07', 100, 5, 'eric')
    assert entry_id == 7
    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO shop_floor_production' in insert_sql
    assert insert_params[:5] == (1, 'Day', '2026-07-07', 100.0, 5.0)


# ── record_downtime ──────────────────────────────────────────────────────

def test_record_downtime_raises_for_unknown_shift():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_downtime(conn, 1, 'Graveyard', '2026-07-07', 'Breakdown', '', 30, 'eric')
    assert conn.execute.call_count == 0


def test_record_downtime_raises_for_unknown_category():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_downtime(conn, 1, 'Day', '2026-07-07', 'Alien Invasion', '', 30, 'eric')
    assert conn.execute.call_count == 0


def test_record_downtime_raises_for_nonpositive_minutes():
    conn = MagicMock()
    with pytest.raises(ValueError):
        record_downtime(conn, 1, 'Day', '2026-07-07', 'Breakdown', '', 0, 'eric')
    assert conn.execute.call_count == 0


def test_record_downtime_inserts_and_returns_id():
    conn = _conn(fetchone_results=[{'id': 9}])
    entry_id = record_downtime(conn, 1, 'Day', '2026-07-07', 'Breakdown',
                                'Conveyor jam', 45, 'eric')
    assert entry_id == 9
    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO shop_floor_downtime' in insert_sql
    assert insert_params[:6] == (1, 'Day', '2026-07-07', 'Breakdown', 'Conveyor jam', 45.0)


# ── set_shift_plan ───────────────────────────────────────────────────────

def test_set_shift_plan_raises_for_unknown_shift():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_shift_plan(conn, 1, 'Graveyard', '2026-07-07', 100, 'eric')
    assert conn.execute.call_count == 0


def test_set_shift_plan_raises_for_negative_qty():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_shift_plan(conn, 1, 'Day', '2026-07-07', -1, 'eric')
    assert conn.execute.call_count == 0


def test_set_shift_plan_upserts():
    conn = MagicMock()
    set_shift_plan(conn, 1, 'Day', '2026-07-07', 500, 'eric')
    sql, params = conn.execute.call_args[0]
    assert 'ON CONFLICT (workcenter_id, shift, entry_date) DO UPDATE' in sql
    assert params[:4] == (1, 'Day', '2026-07-07', 500.0)


# ── get_shift_oee ────────────────────────────────────────────────────────

def test_get_shift_oee_full_availability_no_plan_defaults_performance_to_100():
    conn = _conn(fetchone_results=[
        {'qty_produced': 400.0, 'qty_scrapped': 0.0},  # production totals
        {'minutes': 0.0},                              # downtime totals
        None,                                            # no shift plan set
    ])
    result = get_shift_oee(conn, 1, 'Day', '2026-07-07')
    assert result['has_plan'] is False
    assert result['availability_pct'] == 100.0
    assert result['performance_pct'] == 100.0
    assert result['quality_pct'] == 100.0
    assert result['oee_pct'] == 100.0


def test_get_shift_oee_computes_performance_against_plan():
    conn = _conn(fetchone_results=[
        {'qty_produced': 250.0, 'qty_scrapped': 0.0},
        {'minutes': 0.0},
        {'planned_qty': 500.0},
    ])
    result = get_shift_oee(conn, 1, 'Day', '2026-07-07')
    assert result['has_plan'] is True
    assert result['performance_pct'] == 50.0


def test_get_shift_oee_performance_clamped_at_100_when_exceeding_plan():
    conn = _conn(fetchone_results=[
        {'qty_produced': 600.0, 'qty_scrapped': 0.0},
        {'minutes': 0.0},
        {'planned_qty': 500.0},
    ])
    result = get_shift_oee(conn, 1, 'Day', '2026-07-07')
    assert result['performance_pct'] == 100.0


def test_get_shift_oee_quality_reflects_scrap():
    conn = _conn(fetchone_results=[
        {'qty_produced': 100.0, 'qty_scrapped': 20.0},
        {'minutes': 0.0},
        None,
    ])
    result = get_shift_oee(conn, 1, 'Day', '2026-07-07')
    assert result['quality_pct'] == 80.0


def test_get_shift_oee_quality_defaults_to_100_when_nothing_produced():
    conn = _conn(fetchone_results=[
        {'qty_produced': 0.0, 'qty_scrapped': 0.0},
        {'minutes': 0.0},
        None,
    ])
    result = get_shift_oee(conn, 1, 'Day', '2026-07-07')
    assert result['quality_pct'] == 100.0


def test_get_shift_oee_availability_reflects_downtime():
    conn = _conn(fetchone_results=[
        {'qty_produced': 0.0, 'qty_scrapped': 0.0},
        {'minutes': 120.0},  # 2 hours of an 8-hour shift
        None,
    ])
    result = get_shift_oee(conn, 1, 'Day', '2026-07-07')
    expected = round((SHIFT_LENGTH_HOURS * 60 - 120) / (SHIFT_LENGTH_HOURS * 60) * 100, 1)
    assert result['availability_pct'] == expected


# ── list_live_shift_oee / list_downtime_entries ─────────────────────────

def test_list_live_shift_oee_aggregates_across_workcenters():
    with patch('manufacturing.shop_floor_core.list_workcenters', return_value=[
            {'id': 1, 'name': 'Laser Cutter'}, {'id': 2, 'name': 'Press Brake'}]), \
         patch('manufacturing.shop_floor_core.get_shift_oee', side_effect=[
             {'oee_pct': 80.0}, {'oee_pct': 60.0}]) as mock_oee:
        conn = MagicMock()
        result = list_live_shift_oee(conn, 'Day', '2026-07-07')

    assert [r['oee_pct'] for r in result] == [80.0, 60.0]
    assert result[0]['workcenter_name'] == 'Laser Cutter'
    assert result[1]['workcenter_name'] == 'Press Brake'
    assert mock_oee.call_args_list[0][0] == (conn, 1, 'Day', '2026-07-07')


def test_list_downtime_entries_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'reason_category': 'Breakdown'}]])
    result = list_downtime_entries(conn, 1, 'Day', '2026-07-07')
    assert result == [{'id': 1, 'reason_category': 'Breakdown'}]
