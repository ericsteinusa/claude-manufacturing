"""
Tests for manufacturing/maintenance_core.py — pure unit tests, no Qt, no DB.
"""

import datetime
import pytest
from unittest.mock import MagicMock

from manufacturing.maintenance_core import (
    WO_STATUSES, WORK_TYPES, PRIORITIES,
    EQUIPMENT_STATUSES, SCHEDULE_STATUSES, FREQUENCIES,
    INSPECTION_STATUSES, INSPECTION_TYPES,
    DOWNTIME_STATUSES, DOWNTIME_CATEGORIES,
    PART_STATUSES, PART_CATEGORIES,
    MECHANIC_STATUSES, MECHANIC_TRADES, MECHANIC_SHIFTS,
    get_dashboard_counts,
    load_mechanics,
    list_work_orders, get_work_order, create_work_order,
    update_work_order, complete_work_order,
    list_equipment, get_equipment, create_equipment, update_equipment,
    list_schedules, get_schedule, create_schedule,
    update_schedule, complete_schedule,
    list_inspections, get_inspection, create_inspection,
    update_inspection, complete_inspection,
    list_downtime, get_downtime, create_downtime, update_downtime,
    resolve_downtime,
    list_parts, get_part, create_part, update_part,
    list_mechanics, get_mechanic, create_mechanic, update_mechanic,
)


def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


def _today():
    return datetime.date.today().isoformat()


def _days_ago(n):
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_wo_statuses_complete():
    for s in ('Open', 'Assigned', 'In Progress', 'On Hold', 'Completed', 'Cancelled'):
        assert s in WO_STATUSES


def test_priorities_four_levels():
    assert 'Critical' in PRIORITIES and 'Low' in PRIORITIES


def test_equipment_statuses_include_down():
    assert 'Down' in EQUIPMENT_STATUSES
    assert 'Operational' in EQUIPMENT_STATUSES


def test_schedule_statuses_include_overdue():
    assert 'Overdue' in SCHEDULE_STATUSES


def test_downtime_statuses_include_ongoing():
    assert 'Ongoing' in DOWNTIME_STATUSES
    assert 'Resolved' in DOWNTIME_STATUSES


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def test_dashboard_counts_returns_dict():
    conn = _conn(fetchone={
        'open_wos': 5, 'critical_wos': 1, 'equip_issues': 2,
        'due_schedules': 3, 'pending_inspections': 4,
        'active_downtime': 1, 'overdue_wos': 2,
    })
    result = get_dashboard_counts(conn)
    assert result['open_wos'] == 5
    assert result['critical_wos'] == 1


def test_dashboard_counts_fallback_none():
    conn = _conn(fetchone=None)
    result = get_dashboard_counts(conn)
    assert result['open_wos'] == 0


def test_dashboard_counts_passes_today():
    conn = _conn(fetchone={'open_wos': 0, 'critical_wos': 0, 'equip_issues': 0,
                           'due_schedules': 0, 'pending_inspections': 0,
                           'active_downtime': 0, 'overdue_wos': 0})
    get_dashboard_counts(conn)
    params = conn.execute.call_args[0][1]
    assert _today() in params


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------

def _wo(**kw):
    base = {'id': 1, 'title': 'Fix pump', 'equipment': 'Pump A',
            'work_type': 'Repair', 'priority': 'High', 'assigned_to': '',
            'requested_date': _today(), 'due_date': '', 'completed_date': '',
            'status': 'Open', 'notes': '', 'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_work_orders_returns_annotated():
    conn = _conn(fetchall=[_wo()])
    result = list_work_orders(conn)
    assert len(result) == 1
    assert 'is_overdue' in result[0]


def test_list_work_orders_not_overdue_no_due_date():
    conn = _conn(fetchall=[_wo(due_date='')])
    result = list_work_orders(conn)
    assert result[0]['is_overdue'] is False


def test_list_work_orders_overdue_when_past_due():
    conn = _conn(fetchall=[_wo(due_date=_days_ago(3), status='Open')])
    result = list_work_orders(conn)
    assert result[0]['is_overdue'] is True


def test_list_work_orders_not_overdue_when_completed():
    conn = _conn(fetchall=[_wo(due_date=_days_ago(3), status='Completed')])
    result = list_work_orders(conn)
    assert result[0]['is_overdue'] is False


def test_list_work_orders_status_filter():
    conn = _conn(fetchall=[])
    list_work_orders(conn, status='Open')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'status = %s' in sql
    assert 'Open' in params


def test_list_work_orders_priority_filter():
    conn = _conn(fetchall=[])
    list_work_orders(conn, priority='Critical')
    params = conn.execute.call_args[0][1]
    assert 'Critical' in params


def test_list_work_orders_search_ilike():
    conn = _conn(fetchall=[])
    list_work_orders(conn, search='pump')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_list_work_orders_no_filter_no_where():
    conn = _conn(fetchall=[])
    list_work_orders(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_get_work_order_returns_dict():
    conn = _conn(fetchone=_wo())
    result = get_work_order(conn, 1)
    assert result['id'] == 1
    assert 'is_overdue' in result


def test_get_work_order_returns_none():
    conn = _conn(fetchone=None)
    assert get_work_order(conn, 99) is None


def test_create_work_order_returns_id():
    conn = _conn(fetchone={'id': 5})
    wid = create_work_order(conn, 'Fix motor', 'Motor A', 'Repair',
                            'High', '', _today(), '', '', 'u@e.com')
    assert wid == 5


def test_create_work_order_rejects_empty_title():
    with pytest.raises(ValueError):
        create_work_order(_conn(), '  ', '', 'Repair', 'Medium',
                          '', '', '', '', 'u@e.com')


def test_create_work_order_open_status():
    conn = _conn(fetchone={'id': 1})
    create_work_order(conn, 'Title', '', 'Repair', 'Medium',
                      '', '', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert "'Open'" in sql


def test_create_work_order_defaults_medium_on_bad_priority():
    conn = _conn(fetchone={'id': 1})
    create_work_order(conn, 'Title', '', 'Repair', 'Bogus',
                      '', '', '', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'Medium' in params


def test_create_work_order_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_work_order(conn, 'Title', '', 'Repair', 'Medium',
                      '', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_work_order_executes_update():
    conn = _conn()
    update_work_order(conn, 1, 'Title', '', 'Repair', 'Medium',
                      '', '', '', '', 'Open', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_work_order' in sql


def test_update_work_order_rejects_empty_title():
    with pytest.raises(ValueError):
        update_work_order(_conn(), 1, '', '', 'Repair', 'Medium',
                          '', '', '', '', 'Open', '')


def test_update_work_order_does_not_commit():
    conn = _conn()
    update_work_order(conn, 1, 'Title', '', 'Repair', 'Medium',
                      '', '', '', '', 'Open', '')
    conn.commit.assert_not_called()


def test_complete_work_order_sets_completed():
    conn = _conn()
    complete_work_order(conn, 1)
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'Completed' in sql
    assert _today() in params


def test_complete_work_order_does_not_commit():
    conn = _conn()
    complete_work_order(conn, 1)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

def _eq(**kw):
    base = {'id': 1, 'name': 'Pump A', 'asset_tag': 'TAG-001',
            'location': 'Bay 1', 'manufacturer': 'Grundfos',
            'install_date': '2020-01-01', 'last_service': '',
            'status': 'Operational', 'notes': '', 'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_equipment_returns_rows():
    conn = _conn(fetchall=[_eq()])
    result = list_equipment(conn)
    assert result[0]['name'] == 'Pump A'


def test_list_equipment_status_filter():
    conn = _conn(fetchall=[])
    list_equipment(conn, status='Down')
    params = conn.execute.call_args[0][1]
    assert 'Down' in params


def test_list_equipment_search():
    conn = _conn(fetchall=[])
    list_equipment(conn, search='pump')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_equipment_returns_dict():
    conn = _conn(fetchone=_eq())
    assert get_equipment(conn, 1)['id'] == 1


def test_get_equipment_returns_none():
    assert get_equipment(_conn(fetchone=None), 99) is None


def test_create_equipment_returns_id():
    conn = _conn(fetchone={'id': 3})
    eid = create_equipment(conn, 'Lathe', 'TAG-002', 'Bay 2',
                           'Haas', '', '', 'Operational', '', 'u@e.com')
    assert eid == 3


def test_create_equipment_rejects_empty_name():
    with pytest.raises(ValueError):
        create_equipment(_conn(), '', '', '', '', '', '', 'Operational', '', 'u@e.com')


def test_create_equipment_defaults_operational():
    conn = _conn(fetchone={'id': 1})
    create_equipment(conn, 'Machine', '', '', '', '', '', 'Bogus', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'Operational' in params


def test_create_equipment_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_equipment(conn, 'M', '', '', '', '', '', 'Operational', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_equipment_executes_update():
    conn = _conn()
    update_equipment(conn, 1, 'Pump A', 'TAG-001', 'Bay 1', '', '', '', 'Down', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_equipment' in sql


def test_update_equipment_rejects_empty_name():
    with pytest.raises(ValueError):
        update_equipment(_conn(), 1, '', '', '', '', '', '', 'Operational', '')


def test_update_equipment_does_not_commit():
    conn = _conn()
    update_equipment(conn, 1, 'Name', '', '', '', '', '', 'Operational', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# PM Schedules
# ---------------------------------------------------------------------------

def _sched(**kw):
    base = {'id': 1, 'task': 'Oil change', 'equipment': 'Pump A',
            'frequency': 'Monthly', 'assigned_to': '', 'last_done': '',
            'next_due': '', 'status': 'Scheduled', 'notes': '',
            'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_schedules_annotates_overdue():
    conn = _conn(fetchall=[_sched(next_due=_days_ago(3), status='Scheduled')])
    result = list_schedules(conn)
    assert result[0]['is_overdue'] is True


def test_list_schedules_not_overdue_when_completed():
    conn = _conn(fetchall=[_sched(next_due=_days_ago(3), status='Completed')])
    result = list_schedules(conn)
    assert result[0]['is_overdue'] is False


def test_list_schedules_not_overdue_no_due_date():
    conn = _conn(fetchall=[_sched(next_due='')])
    result = list_schedules(conn)
    assert result[0]['is_overdue'] is False


def test_list_schedules_status_filter():
    conn = _conn(fetchall=[])
    list_schedules(conn, status='Due')
    params = conn.execute.call_args[0][1]
    assert 'Due' in params


def test_get_schedule_returns_dict():
    conn = _conn(fetchone=_sched())
    assert get_schedule(conn, 1)['task'] == 'Oil change'


def test_get_schedule_returns_none():
    assert get_schedule(_conn(fetchone=None), 99) is None


def test_create_schedule_returns_id():
    conn = _conn(fetchone={'id': 2})
    sid = create_schedule(conn, 'Lubrication', 'Lathe', 'Monthly',
                          '', '', '', '', 'u@e.com')
    assert sid == 2


def test_create_schedule_rejects_empty_task():
    with pytest.raises(ValueError):
        create_schedule(_conn(), '  ', '', 'Monthly', '', '', '', '', 'u@e.com')


def test_create_schedule_scheduled_status():
    conn = _conn(fetchone={'id': 1})
    create_schedule(conn, 'Task', '', 'Monthly', '', '', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert "'Scheduled'" in sql


def test_create_schedule_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_schedule(conn, 'Task', '', 'Monthly', '', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_schedule_executes_update():
    conn = _conn()
    update_schedule(conn, 1, 'Task', '', 'Monthly', '', '', '', 'Due', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_schedule' in sql


def test_update_schedule_rejects_empty_task():
    with pytest.raises(ValueError):
        update_schedule(_conn(), 1, '', '', '', '', '', '', 'Scheduled', '')


def test_complete_schedule_stamps_today():
    conn = _conn()
    complete_schedule(conn, 1)
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'Completed' in sql
    assert _today() in params


def test_complete_schedule_does_not_commit():
    conn = _conn()
    complete_schedule(conn, 1)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------

def _insp(**kw):
    base = {'id': 1, 'area': 'Welding Bay', 'inspection_type': 'Fire Safety',
            'inspector': '', 'scheduled_date': '', 'completed_date': '',
            'result': '', 'status': 'Scheduled', 'notes': '',
            'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_inspections_returns_rows():
    conn = _conn(fetchall=[_insp()])
    result = list_inspections(conn)
    assert result[0]['area'] == 'Welding Bay'
    assert 'is_overdue' in result[0]


def test_list_inspections_overdue_when_past_scheduled():
    conn = _conn(fetchall=[_insp(scheduled_date=_days_ago(2), status='Scheduled')])
    result = list_inspections(conn)
    assert result[0]['is_overdue'] is True


def test_list_inspections_not_overdue_when_passed():
    conn = _conn(fetchall=[_insp(scheduled_date=_days_ago(2), status='Passed')])
    result = list_inspections(conn)
    assert result[0]['is_overdue'] is False


def test_list_inspections_status_filter():
    conn = _conn(fetchall=[])
    list_inspections(conn, status='Scheduled')
    params = conn.execute.call_args[0][1]
    assert 'Scheduled' in params


def test_get_inspection_returns_dict():
    conn = _conn(fetchone=_insp())
    assert get_inspection(conn, 1)['area'] == 'Welding Bay'


def test_get_inspection_returns_none():
    assert get_inspection(_conn(fetchone=None), 99) is None


def test_create_inspection_returns_id():
    conn = _conn(fetchone={'id': 4})
    iid = create_inspection(conn, 'Main Floor', 'General', '', '', '', 'u@e.com')
    assert iid == 4


def test_create_inspection_rejects_empty_area():
    with pytest.raises(ValueError):
        create_inspection(_conn(), '  ', 'General', '', '', '', 'u@e.com')


def test_create_inspection_scheduled_status():
    conn = _conn(fetchone={'id': 1})
    create_inspection(conn, 'Area', 'General', '', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert "'Scheduled'" in sql


def test_create_inspection_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_inspection(conn, 'Area', 'General', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_inspection_executes_update():
    conn = _conn()
    update_inspection(conn, 1, 'Area', 'General', '', '', '', '', 'Scheduled', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_inspection' in sql


def test_update_inspection_rejects_empty_area():
    with pytest.raises(ValueError):
        update_inspection(_conn(), 1, '', 'General', '', '', '', '', 'Scheduled', '')


def test_complete_inspection_pass_stamps_passed():
    conn = _conn()
    complete_inspection(conn, 1, 'pass', '')
    params = conn.execute.call_args[0][1]
    assert 'Passed' in params
    assert _today() in params


def test_complete_inspection_fail_stamps_failed():
    conn = _conn()
    complete_inspection(conn, 1, 'Fail', '')
    params = conn.execute.call_args[0][1]
    assert 'Failed' in params


def test_complete_inspection_does_not_commit():
    conn = _conn()
    complete_inspection(conn, 1, '', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Downtime
# ---------------------------------------------------------------------------

def _dt(**kw):
    base = {'id': 1, 'equipment': 'Pump A', 'reason': 'Bearing failure',
            'category': 'Breakdown', 'down_date': _today(), 'hours': '4.0',
            'cost': 200.0, 'status': 'Ongoing', 'notes': '',
            'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_downtime_returns_rows():
    conn = _conn(fetchall=[_dt()])
    result = list_downtime(conn)
    assert result[0]['equipment'] == 'Pump A'


def test_list_downtime_status_filter():
    conn = _conn(fetchall=[])
    list_downtime(conn, status='Ongoing')
    params = conn.execute.call_args[0][1]
    assert 'Ongoing' in params


def test_list_downtime_search():
    conn = _conn(fetchall=[])
    list_downtime(conn, search='pump')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_downtime_returns_dict():
    conn = _conn(fetchone=_dt())
    assert get_downtime(conn, 1)['equipment'] == 'Pump A'


def test_get_downtime_returns_none():
    assert get_downtime(_conn(fetchone=None), 99) is None


def test_create_downtime_returns_id():
    conn = _conn(fetchone={'id': 6})
    did = create_downtime(conn, 'Press', 'Breakdown', 'Breakdown',
                          _today(), '2.0', '500', '', 'u@e.com')
    assert did == 6


def test_create_downtime_rejects_empty_equipment():
    with pytest.raises(ValueError):
        create_downtime(_conn(), '  ', '', 'Breakdown', '', '', '', '', 'u@e.com')


def test_create_downtime_ongoing_status():
    conn = _conn(fetchone={'id': 1})
    create_downtime(conn, 'Equipment', '', 'Breakdown', '', '', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert "'Ongoing'" in sql


def test_create_downtime_zero_cost_when_empty():
    conn = _conn(fetchone={'id': 1})
    create_downtime(conn, 'Equipment', '', 'Breakdown', '', '', '', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 0.0 in params


def test_create_downtime_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_downtime(conn, 'Equipment', '', 'Breakdown', '', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_downtime_executes_update():
    conn = _conn()
    update_downtime(conn, 1, 'Pump', '', 'Breakdown', '', '', '', 'Resolved', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_downtime' in sql


def test_update_downtime_rejects_empty_equipment():
    with pytest.raises(ValueError):
        update_downtime(_conn(), 1, '', '', '', '', '', '', 'Resolved', '')


def test_resolve_downtime_sets_resolved():
    conn = _conn()
    resolve_downtime(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'Resolved' in sql


def test_resolve_downtime_does_not_commit():
    conn = _conn()
    resolve_downtime(conn, 1)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------

def _part(**kw):
    base = {'id': 1, 'name': 'Bearing 6205', 'part_number': 'BRG-001',
            'category': 'Bearings', 'location': 'Shelf A-1', 'quantity': '10',
            'reorder_level': '3', 'unit_cost': 12.50,
            'status': 'In Stock', 'notes': '', 'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_parts_returns_rows():
    conn = _conn(fetchall=[_part()])
    result = list_parts(conn)
    assert result[0]['name'] == 'Bearing 6205'


def test_list_parts_status_filter():
    conn = _conn(fetchall=[])
    list_parts(conn, status='Low Stock')
    params = conn.execute.call_args[0][1]
    assert 'Low Stock' in params


def test_list_parts_search():
    conn = _conn(fetchall=[])
    list_parts(conn, search='bearing')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_part_returns_dict():
    conn = _conn(fetchone=_part())
    assert get_part(conn, 1)['name'] == 'Bearing 6205'


def test_get_part_returns_none():
    assert get_part(_conn(fetchone=None), 99) is None


def test_create_part_returns_id():
    conn = _conn(fetchone={'id': 7})
    pid = create_part(conn, 'V-Belt', 'VB-001', 'Belts', '',
                      '5', '2', '8.00', 'In Stock', '', 'u@e.com')
    assert pid == 7


def test_create_part_rejects_empty_name():
    with pytest.raises(ValueError):
        create_part(_conn(), '  ', '', 'Other', '', '', '', '', 'In Stock', '', 'u@e.com')


def test_create_part_defaults_in_stock():
    conn = _conn(fetchone={'id': 1})
    create_part(conn, 'Part', '', 'Other', '', '', '', '', 'Bogus', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'In Stock' in params


def test_create_part_zero_cost_when_empty():
    conn = _conn(fetchone={'id': 1})
    create_part(conn, 'Part', '', 'Other', '', '', '', '', 'In Stock', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 0.0 in params


def test_create_part_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_part(conn, 'Part', '', 'Other', '', '', '', '', 'In Stock', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_part_executes_update():
    conn = _conn()
    update_part(conn, 1, 'Bearing 6205', 'BRG-001', 'Bearings',
                '', '10', '3', '12.50', 'In Stock', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_part' in sql


def test_update_part_rejects_empty_name():
    with pytest.raises(ValueError):
        update_part(_conn(), 1, '', '', 'Bearings', '', '', '', '', 'In Stock', '')


def test_update_part_does_not_commit():
    conn = _conn()
    update_part(conn, 1, 'Name', '', 'Other', '', '', '', '', 'In Stock', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Mechanics
# ---------------------------------------------------------------------------

def _mech(**kw):
    base = {'id': 1, 'name': 'Bob Smith', 'trade': 'Mechanical',
            'shift': 'Day', 'phone': '555-1234',
            'status': 'Active', 'notes': '', 'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_load_mechanics_returns_active():
    conn = _conn(fetchall=[{'name': 'Bob'}, {'name': 'Alice'}])
    result = load_mechanics(conn)
    assert len(result) == 2
    sql = conn.execute.call_args[0][0]
    assert "status='Active'" in sql


def test_load_mechanics_empty():
    conn = _conn(fetchall=[])
    assert load_mechanics(conn) == []


def test_list_mechanics_returns_rows():
    conn = _conn(fetchall=[_mech()])
    result = list_mechanics(conn)
    assert result[0]['name'] == 'Bob Smith'


def test_list_mechanics_status_filter():
    conn = _conn(fetchall=[])
    list_mechanics(conn, status='Active')
    params = conn.execute.call_args[0][1]
    assert 'Active' in params


def test_list_mechanics_search():
    conn = _conn(fetchall=[])
    list_mechanics(conn, search='bob')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_mechanic_returns_dict():
    conn = _conn(fetchone=_mech())
    assert get_mechanic(conn, 1)['name'] == 'Bob Smith'


def test_get_mechanic_returns_none():
    assert get_mechanic(_conn(fetchone=None), 99) is None


def test_create_mechanic_returns_id():
    conn = _conn(fetchone={'id': 8})
    mid = create_mechanic(conn, 'Jane Doe', 'Electrical', 'Night',
                          '555-5678', 'Active', '', 'u@e.com')
    assert mid == 8


def test_create_mechanic_rejects_empty_name():
    with pytest.raises(ValueError):
        create_mechanic(_conn(), '  ', 'General', 'Day', '', 'Active', '', 'u@e.com')


def test_create_mechanic_defaults_active():
    conn = _conn(fetchone={'id': 1})
    create_mechanic(conn, 'Alice', 'General', 'Day', '', 'Bogus', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'Active' in params


def test_create_mechanic_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_mechanic(conn, 'Alice', 'General', 'Day', '', 'Active', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_mechanic_executes_update():
    conn = _conn()
    update_mechanic(conn, 1, 'Bob Smith', 'Mechanical', 'Day', '555', 'Active', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE maint_mechanic' in sql


def test_update_mechanic_rejects_empty_name():
    with pytest.raises(ValueError):
        update_mechanic(_conn(), 1, '', 'General', 'Day', '', 'Active', '')


def test_update_mechanic_does_not_commit():
    conn = _conn()
    update_mechanic(conn, 1, 'Bob', 'General', 'Day', '', 'Active', '')
    conn.commit.assert_not_called()
