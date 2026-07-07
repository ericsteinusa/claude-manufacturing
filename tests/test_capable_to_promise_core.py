"""Tests for capable_to_promise_core — Capable-to-Promise (P4-C).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_predictive_maintenance_core.py).
Cross-module calls (get_atp, get_routing, earliest_capacity_date, get_so,
get_so_items) are patched at their usage site so tests exercise this
module's own combination logic in isolation.
"""

from unittest.mock import MagicMock, patch

from manufacturing.capable_to_promise_core import (
    get_workcenter_hours_required, get_capacity_availability, get_ctp,
    check_so_capacity,
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


# ── get_workcenter_hours_required ────────────────────────────────────────

def test_get_workcenter_hours_required_scales_and_groups():
    routing = [
        {'workcenter_id': 1, 'std_hours': 2.0},
        {'workcenter_id': 2, 'std_hours': 1.0},
        {'workcenter_id': 1, 'std_hours': 0.5},  # second op on same workcenter
    ]
    with patch('manufacturing.capable_to_promise_core.get_routing', return_value=routing):
        result = get_workcenter_hours_required(MagicMock(), 5, qty=10)
    assert result == {1: 25.0, 2: 10.0}


def test_get_workcenter_hours_required_skips_steps_without_workcenter():
    routing = [{'workcenter_id': None, 'std_hours': 3.0}]
    with patch('manufacturing.capable_to_promise_core.get_routing', return_value=routing):
        result = get_workcenter_hours_required(MagicMock(), 5, qty=10)
    assert result == {}


# ── get_capacity_availability ────────────────────────────────────────────

def test_get_capacity_availability_no_routing_passthrough():
    with patch('manufacturing.capable_to_promise_core.get_routing', return_value=[]):
        conn = MagicMock()
        result = get_capacity_availability(conn, 5, qty=10, from_date='2026-07-06')
    assert result == {'workcenters': [], 'capacity_date': '2026-07-06'}


def test_get_capacity_availability_uses_max_across_workcenters():
    routing = [
        {'workcenter_id': 1, 'std_hours': 2.0},
        {'workcenter_id': 2, 'std_hours': 1.0},
    ]
    conn = _conn(fetchone_results=[
        {'name': 'Cutting'}, {'name': 'Assembly'},
    ])
    with patch('manufacturing.capable_to_promise_core.get_routing', return_value=routing), \
         patch('manufacturing.capable_to_promise_core.earliest_capacity_date',
               side_effect=['2026-07-10', '2026-07-08']):
        result = get_capacity_availability(conn, 5, qty=10, from_date='2026-07-06')

    assert result['capacity_date'] == '2026-07-10'
    assert len(result['workcenters']) == 2
    assert result['workcenters'][0]['hours_required'] == 20.0


def test_get_capacity_availability_none_when_any_workcenter_unreachable():
    routing = [{'workcenter_id': 1, 'std_hours': 2.0}]
    conn = _conn(fetchone_results=[{'name': 'Cutting'}])
    with patch('manufacturing.capable_to_promise_core.get_routing', return_value=routing), \
         patch('manufacturing.capable_to_promise_core.earliest_capacity_date', return_value=None):
        result = get_capacity_availability(conn, 5, qty=10, from_date='2026-07-06')
    assert result['capacity_date'] is None


# ── get_ctp ──────────────────────────────────────────────────────────────

def _fake_atp(sufficient, earliest):
    return {
        'product_id': 5, 'on_hand': 0.0, 'committed_qty': 0.0, 'open_po_qty': 0.0,
        'atp_qty': 0.0, 'requested_qty': 10.0, 'requested_date': '2026-07-06',
        'sufficient': sufficient, 'earliest_available_date': earliest,
    }


def test_get_ctp_takes_max_of_material_and_capacity():
    with patch('manufacturing.capable_to_promise_core.get_atp',
               return_value=_fake_atp(False, '2026-07-11')), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value={'workcenters': [], 'capacity_date': '2026-07-14'}):
        result = get_ctp(MagicMock(), 5, 10, requested_date='2026-07-06')

    assert result['material_ready_date'] == '2026-07-11'
    assert result['capacity_ready_date'] == '2026-07-14'
    assert result['ctp_date'] == '2026-07-14'
    assert result['ctp_sufficient'] is False


def test_get_ctp_sufficient_when_both_dates_on_or_before_requested():
    with patch('manufacturing.capable_to_promise_core.get_atp',
               return_value=_fake_atp(True, '2026-07-06')), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value={'workcenters': [], 'capacity_date': '2026-07-06'}):
        result = get_ctp(MagicMock(), 5, 10, requested_date='2026-07-06')

    assert result['ctp_date'] == '2026-07-06'
    assert result['ctp_sufficient'] is True


def test_get_ctp_none_when_material_unreachable():
    with patch('manufacturing.capable_to_promise_core.get_atp',
               return_value=_fake_atp(False, None)), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value={'workcenters': [], 'capacity_date': '2026-07-14'}):
        result = get_ctp(MagicMock(), 5, 10, requested_date='2026-07-06')

    assert result['ctp_date'] is None
    assert result['ctp_sufficient'] is False


def test_get_ctp_none_when_capacity_unreachable():
    with patch('manufacturing.capable_to_promise_core.get_atp',
               return_value=_fake_atp(True, '2026-07-06')), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value={'workcenters': [], 'capacity_date': None}):
        result = get_ctp(MagicMock(), 5, 10, requested_date='2026-07-06')

    assert result['ctp_date'] is None
    assert result['ctp_sufficient'] is False


# ── check_so_capacity ────────────────────────────────────────────────────

def test_check_so_capacity_empty_when_no_product_lines():
    so = {'id': 1, 'ship_date': '2026-07-06'}
    with patch('manufacturing.capable_to_promise_core.get_so', return_value=so), \
         patch('manufacturing.capable_to_promise_core.get_so_items',
               return_value=[{'id': 1, 'product_id': None, 'qty': 5}]):
        result = check_so_capacity(MagicMock(), 1)
    assert result == []


def test_check_so_capacity_skips_lines_with_no_routing():
    so = {'id': 1, 'ship_date': '2026-07-06'}
    items = [{'id': 1, 'product_id': 5, 'qty': 10, 'product_name': 'Widget'}]
    with patch('manufacturing.capable_to_promise_core.get_so', return_value=so), \
         patch('manufacturing.capable_to_promise_core.get_so_items', return_value=items), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value={'workcenters': [], 'capacity_date': '2026-07-06'}):
        result = check_so_capacity(MagicMock(), 1)
    assert result == []


def test_check_so_capacity_flags_shortfall_past_requested_date():
    so = {'id': 1, 'ship_date': '2026-07-06'}
    items = [{'id': 1, 'product_id': 5, 'qty': 10, 'product_name': 'Widget'}]
    capacity = {
        'workcenters': [{'workcenter_id': 1, 'workcenter_name': 'Cutting',
                          'hours_required': 20.0, 'earliest_date': '2026-07-14'}],
        'capacity_date': '2026-07-14',
    }
    with patch('manufacturing.capable_to_promise_core.get_so', return_value=so), \
         patch('manufacturing.capable_to_promise_core.get_so_items', return_value=items), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value=capacity):
        result = check_so_capacity(MagicMock(), 1)

    assert len(result) == 1
    assert result[0]['product_name'] == 'Widget'
    assert result[0]['earliest_capacity_date'] == '2026-07-14'


def test_check_so_capacity_empty_when_capacity_available_in_time():
    so = {'id': 1, 'ship_date': '2026-07-20'}
    items = [{'id': 1, 'product_id': 5, 'qty': 10, 'product_name': 'Widget'}]
    capacity = {
        'workcenters': [{'workcenter_id': 1, 'workcenter_name': 'Cutting',
                          'hours_required': 20.0, 'earliest_date': '2026-07-14'}],
        'capacity_date': '2026-07-14',
    }
    with patch('manufacturing.capable_to_promise_core.get_so', return_value=so), \
         patch('manufacturing.capable_to_promise_core.get_so_items', return_value=items), \
         patch('manufacturing.capable_to_promise_core.get_capacity_availability',
               return_value=capacity):
        result = check_so_capacity(MagicMock(), 1)
    assert result == []


def test_check_so_capacity_returns_empty_when_so_not_found():
    with patch('manufacturing.capable_to_promise_core.get_so', return_value=None):
        result = check_so_capacity(MagicMock(), 999)
    assert result == []
