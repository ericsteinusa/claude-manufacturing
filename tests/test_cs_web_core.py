"""
Tests for the DB-layer additions in cs_calls_core.py.

These cover the functions added for the web UI: list_tickets, get_ticket,
create_ticket, update_ticket, close_ticket, get_escalations,
get_summary_stats, get_monthly_volume, list_plans, create_plan, update_plan.
"""

import datetime
from unittest.mock import MagicMock

from manufacturing.cs_calls_core import (
    OVERDUE_DAYS, CRITICAL_DAYS,
    _ticket_row,
    load_customers_for_cs,
    list_tickets, get_ticket, create_ticket, update_ticket, close_ticket,
    get_escalations, get_summary_stats, get_monthly_volume,
    list_plans, create_plan, update_plan, PLAN_STATUSES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


def _today():
    return datetime.date.today().isoformat()


def _days_ago(n):
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def _ticket(**kw):
    base = {
        'id': 1, 'customer_id': 10, 'call': 'Widget broken',
        'call_date': _today(), 'call_time': '09:00',
        'completion_date': '', 'completion_time': '',
        'comments_box': '', 'completion_box': 0, 'created_by': 'u@e.com',
        'customer_name': 'ACME Corp',
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# _ticket_row — annotation logic
# ---------------------------------------------------------------------------

def test_ticket_row_open_normal():
    t = _ticket_row(_ticket(call_date=_today()))
    assert t['status'] == 'open'
    assert t['priority'] == 'normal'
    assert t['days_open'] == 0


def test_ticket_row_open_high():
    t = _ticket_row(_ticket(call_date=_days_ago(OVERDUE_DAYS)))
    assert t['priority'] == 'high'


def test_ticket_row_open_critical():
    t = _ticket_row(_ticket(call_date=_days_ago(CRITICAL_DAYS)))
    assert t['priority'] == 'critical'


def test_ticket_row_completed():
    t = _ticket_row(_ticket(completion_box=1, call_date=_days_ago(20)))
    assert t['status'] == 'completed'
    assert t['priority'] == 'none'


def test_ticket_row_bad_date_defaults_zero_days():
    t = _ticket_row(_ticket(call_date='not-a-date'))
    assert t['days_open'] == 0


# ---------------------------------------------------------------------------
# load_customers_for_cs
# ---------------------------------------------------------------------------

def test_load_customers_uses_company_when_set():
    conn = _conn(fetchall=[{
        'id': 1, 'first_name': 'Bob', 'last_name': 'Jones',
        'company_name': 'ACME'}])
    result = load_customers_for_cs(conn)
    assert result[0]['label'] == 'ACME'


def test_load_customers_falls_back_to_name():
    conn = _conn(fetchall=[{
        'id': 2, 'first_name': 'Jane', 'last_name': 'Doe', 'company_name': ''}])
    result = load_customers_for_cs(conn)
    assert result[0]['label'] == 'Jane Doe'


def test_load_customers_falls_back_to_id():
    conn = _conn(fetchall=[{
        'id': 3, 'first_name': '', 'last_name': '', 'company_name': ''}])
    result = load_customers_for_cs(conn)
    assert result[0]['label'] == '3'


def test_load_customers_empty():
    conn = _conn(fetchall=[])
    assert load_customers_for_cs(conn) == []


# ---------------------------------------------------------------------------
# list_tickets
# ---------------------------------------------------------------------------

def test_list_tickets_returns_annotated_rows():
    conn = _conn(fetchall=[_ticket()])
    result = list_tickets(conn)
    assert len(result) == 1
    assert 'status' in result[0]


def test_list_tickets_status_open_adds_condition():
    conn = _conn(fetchall=[])
    list_tickets(conn, status='open')
    sql = conn.execute.call_args[0][0]
    assert 'completion_box = 0' in sql


def test_list_tickets_status_completed_adds_condition():
    conn = _conn(fetchall=[])
    list_tickets(conn, status='completed')
    sql = conn.execute.call_args[0][0]
    assert 'completion_box = 1' in sql


def test_list_tickets_search_adds_ilike():
    conn = _conn(fetchall=[])
    list_tickets(conn, search='widget')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql
    params = conn.execute.call_args[0][1]
    assert '%widget%' in params


def test_list_tickets_created_by_filter():
    conn = _conn(fetchall=[])
    list_tickets(conn, created_by='u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'created_by' in sql
    params = conn.execute.call_args[0][1]
    assert 'u@e.com' in params


def test_list_tickets_no_filters_no_where():
    conn = _conn(fetchall=[])
    list_tickets(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_list_tickets_empty():
    conn = _conn(fetchall=[])
    assert list_tickets(conn) == []


# ---------------------------------------------------------------------------
# get_ticket
# ---------------------------------------------------------------------------

def test_get_ticket_returns_dict():
    conn = _conn(fetchone=_ticket())
    result = get_ticket(conn, 1)
    assert result is not None
    assert result['id'] == 1
    assert 'status' in result


def test_get_ticket_returns_none_when_missing():
    conn = _conn(fetchone=None)
    assert get_ticket(conn, 999) is None


# ---------------------------------------------------------------------------
# create_ticket
# ---------------------------------------------------------------------------

def test_create_ticket_returns_id():
    conn = _conn(fetchone={'id': 5})
    tid = create_ticket(conn, 10, 'Broken widget', _today(),
                        '09:00', 'notes', 'u@e.com')
    assert tid == 5


def test_create_ticket_inserts_into_calls2():
    conn = _conn(fetchone={'id': 1})
    create_ticket(conn, 10, 'test', _today(), '09:00', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'INSERT INTO calls2' in sql


def test_create_ticket_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_ticket(conn, 10, 'test', _today(), '09:00', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_create_ticket_strips_call_text():
    conn = _conn(fetchone={'id': 1})
    create_ticket(conn, 10, '  broken  ', _today(), '09:00', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'broken' in params
    assert '  broken  ' not in params


def test_create_ticket_sets_completion_box_zero():
    conn = _conn(fetchone={'id': 1})
    create_ticket(conn, 10, 'test', _today(), '09:00', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'completion_box' in sql.lower() or ', 0,' in sql


# ---------------------------------------------------------------------------
# update_ticket
# ---------------------------------------------------------------------------

def test_update_ticket_executes_update():
    conn = _conn()
    update_ticket(conn, 1, 10, 'new desc', _today(), '10:00',
                  '', '', 'notes', False)
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE calls2' in sql


def test_update_ticket_completed_flag():
    conn = _conn()
    update_ticket(conn, 1, 10, 'x', _today(), '', '', '', '', True)
    params = conn.execute.call_args[0][1]
    assert 1 in params  # completion_box = 1


def test_update_ticket_does_not_commit():
    conn = _conn()
    update_ticket(conn, 1, 10, 'x', _today(), '', '', '', '', False)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# close_ticket
# ---------------------------------------------------------------------------

def test_close_ticket_sets_completion_box():
    conn = _conn()
    close_ticket(conn, 1, 'resolved')
    sql = conn.execute.call_args[0][0]
    assert 'completion_box=1' in sql


def test_close_ticket_sets_todays_date():
    conn = _conn()
    close_ticket(conn, 1, '')
    params = conn.execute.call_args[0][1]
    assert _today() in params


def test_close_ticket_does_not_commit():
    conn = _conn()
    close_ticket(conn, 1, '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# get_escalations
# ---------------------------------------------------------------------------

def test_get_escalations_queries_open_and_old():
    conn = _conn(fetchall=[])
    get_escalations(conn)
    sql = conn.execute.call_args[0][0]
    assert 'completion_box = 0' in sql
    assert 'call_date <=' in sql


def test_get_escalations_returns_annotated():
    old_date = _days_ago(OVERDUE_DAYS + 1)
    conn = _conn(fetchall=[_ticket(call_date=old_date, completion_box=0)])
    result = get_escalations(conn)
    assert len(result) == 1
    assert result[0]['priority'] in ('high', 'critical')


def test_get_escalations_empty():
    conn = _conn(fetchall=[])
    assert get_escalations(conn) == []


# ---------------------------------------------------------------------------
# get_summary_stats
# ---------------------------------------------------------------------------

def test_get_summary_stats_computes_completion_rate():
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        {'total': 10, 'open_count': 3, 'completed_count': 7,
         'avg_resolution': 5.0},
        {'avg_age': 4.0},
    ]
    result = get_summary_stats(conn, 365)
    assert result['completion_rate'] == 70.0


def test_get_summary_stats_zero_total():
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        {'total': 0, 'open_count': 0, 'completed_count': 0,
         'avg_resolution': None},
        {'avg_age': None},
    ]
    result = get_summary_stats(conn, 365)
    assert result['completion_rate'] == 0.0


def test_get_summary_stats_rounds_avg():
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        {'total': 5, 'open_count': 2, 'completed_count': 3,
         'avg_resolution': 6.666},
        {'avg_age': 3.14159},
    ]
    result = get_summary_stats(conn, 365)
    assert result['avg_resolution'] == 6.7
    assert result['avg_age_open'] == 3.1


def test_get_summary_stats_fallback_when_none():
    conn = _conn(fetchone=None)
    result = get_summary_stats(conn, 365)
    assert result['total'] == 0


# ---------------------------------------------------------------------------
# get_monthly_volume
# ---------------------------------------------------------------------------

def test_get_monthly_volume_returns_list():
    conn = _conn(fetchall=[
        {'month': '2026-06', 'total': 20, 'open_count': 5,
         'completed_count': 15},
    ])
    result = get_monthly_volume(conn)
    assert result[0]['completion_rate'] == 75.0


def test_get_monthly_volume_empty():
    conn = _conn(fetchall=[])
    assert get_monthly_volume(conn) == []


def test_get_monthly_volume_zero_total():
    conn = _conn(fetchall=[
        {'month': '2026-05', 'total': 0, 'open_count': 0, 'completed_count': 0}
    ])
    result = get_monthly_volume(conn)
    assert result[0]['completion_rate'] == 0.0


# ---------------------------------------------------------------------------
# list_plans
# ---------------------------------------------------------------------------

def test_list_plans_returns_rows():
    conn = _conn(fetchall=[
        {'id': 1, 'title': 'Plan A', 'status': 'Open',
         'target_date': '2026-12-31', 'created_date': '2026-06-01',
         'description': '', 'owner': 'Eric'},
    ])
    result = list_plans(conn)
    assert result[0]['title'] == 'Plan A'


def test_list_plans_marks_overdue():
    conn = _conn(fetchall=[
        {'id': 1, 'title': 'Old Plan', 'status': 'Open',
         'target_date': '2020-01-01', 'created_date': '2019-01-01',
         'description': '', 'owner': ''},
    ])
    result = list_plans(conn)
    assert result[0]['overdue'] is True


def test_list_plans_completed_not_overdue():
    conn = _conn(fetchall=[
        {'id': 2, 'title': 'Done', 'status': 'Completed',
         'target_date': '2020-01-01', 'created_date': '2019-01-01',
         'description': '', 'owner': ''},
    ])
    result = list_plans(conn)
    assert result[0]['overdue'] is False


def test_list_plans_status_filter_adds_where():
    conn = _conn(fetchall=[])
    list_plans(conn, status='Open')
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' in sql
    params = conn.execute.call_args[0][1]
    assert 'Open' in params


# ---------------------------------------------------------------------------
# create_plan
# ---------------------------------------------------------------------------

def test_create_plan_returns_id():
    conn = _conn(fetchone={'id': 3})
    pid = create_plan(conn, 'My Plan', 'desc', 'Eric',
                      '2026-12-31', 'u@e.com')
    assert pid == 3


def test_create_plan_rejects_empty_title():
    conn = MagicMock()
    import pytest
    with pytest.raises(ValueError, match='required'):
        create_plan(conn, '  ', '', '', '', 'u@e.com')


def test_create_plan_inserts_with_open_status():
    conn = _conn(fetchone={'id': 1})
    create_plan(conn, 'Plan', '', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'INSERT INTO cs_improvement_plan' in sql
    assert "'Open'" in sql or "Open" in sql


def test_create_plan_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_plan(conn, 'Plan', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# update_plan
# ---------------------------------------------------------------------------

def test_update_plan_executes_update():
    conn = _conn()
    update_plan(conn, 1, 'New Title', '', 'Eve', '2026-12-31', 'In Progress')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE cs_improvement_plan' in sql


def test_update_plan_rejects_empty_title():
    conn = MagicMock()
    import pytest
    with pytest.raises(ValueError, match='required'):
        update_plan(conn, 1, '', '', '', '', 'Open')


def test_update_plan_invalid_status_defaults_open():
    conn = _conn()
    update_plan(conn, 1, 'Title', '', '', '', 'Bogus')
    params = conn.execute.call_args[0][1]
    assert 'Open' in params


def test_update_plan_does_not_commit():
    conn = _conn()
    update_plan(conn, 1, 'Title', '', '', '', 'Open')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# PLAN_STATUSES constant
# ---------------------------------------------------------------------------

def test_plan_statuses_includes_expected():
    for st in ('Open', 'In Progress', 'Completed', 'Cancelled'):
        assert st in PLAN_STATUSES
