"""Tests for manufacturing/it_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.it_core import (
    get_it_dashboard,
    next_ticket_number, list_tickets, get_ticket, create_ticket,
    update_ticket, set_ticket_status,
    list_assets, get_asset, create_asset, update_asset,
    TICKET_STATUSES, TICKET_PRIORITIES, ISSUE_TYPES,
    ASSET_STATUSES, ASSET_TYPES,
)

_TICKET_STATS = {
    'open_count': 3, 'in_progress_count': 2,
    'critical_count': 1, 'total_count': 10,
}
_ASSET_STATS = {'total': 50, 'active': 45, 'repair': 3}

_TICKET_ROW = {
    'id': 1, 'ticket_number': 'TKT-2026-0001',
    'requester': 'Alice', 'department': 'Sales',
    'issue_type': 'Hardware', 'priority': 'high',
    'status': 'open', 'submitted_date': '2026-06-01',
}


def _conn(ticket_stats=None, asset_stats=None, recent=None):
    c = MagicMock()
    ts = ticket_stats if ticket_stats is not None else _TICKET_STATS
    ast = asset_stats if asset_stats is not None else _ASSET_STATS
    rec = recent if recent is not None else []
    c.execute.side_effect = [
        MagicMock(),  # _ensure_ticket_table DDL
        MagicMock(),  # _ensure_asset_table DDL
        MagicMock(fetchone=MagicMock(return_value=ts)),
        MagicMock(fetchone=MagicMock(return_value=ast)),
        MagicMock(fetchall=MagicMock(return_value=rec)),
    ]
    return c


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_returns_dict():
    assert isinstance(get_it_dashboard(_conn()), dict)


def test_has_tickets_key():
    assert 'tickets' in get_it_dashboard(_conn())


def test_has_assets_key():
    assert 'assets' in get_it_dashboard(_conn())


def test_has_recent_tickets_key():
    assert 'recent_tickets' in get_it_dashboard(_conn())


# ---------------------------------------------------------------------------
# ticket stats
# ---------------------------------------------------------------------------

def test_tickets_open_count():
    result = get_it_dashboard(_conn())
    assert result['tickets']['open_count'] == _TICKET_STATS['open_count']


def test_tickets_in_progress_count():
    result = get_it_dashboard(_conn())
    assert result['tickets']['in_progress_count'] == _TICKET_STATS['in_progress_count']


def test_tickets_critical_count():
    result = get_it_dashboard(_conn())
    assert result['tickets']['critical_count'] == _TICKET_STATS['critical_count']


def test_tickets_total_count():
    result = get_it_dashboard(_conn())
    assert result['tickets']['total_count'] == _TICKET_STATS['total_count']


# ---------------------------------------------------------------------------
# asset stats
# ---------------------------------------------------------------------------

def test_assets_total():
    result = get_it_dashboard(_conn())
    assert result['assets']['total'] == _ASSET_STATS['total']


def test_assets_active():
    result = get_it_dashboard(_conn())
    assert result['assets']['active'] == _ASSET_STATS['active']


def test_assets_repair():
    result = get_it_dashboard(_conn())
    assert result['assets']['repair'] == _ASSET_STATS['repair']


# ---------------------------------------------------------------------------
# recent_tickets
# ---------------------------------------------------------------------------

def test_recent_tickets_is_list():
    result = get_it_dashboard(_conn(recent=[_TICKET_ROW]))
    assert isinstance(result['recent_tickets'], list)


def test_recent_tickets_items_are_dicts():
    result = get_it_dashboard(_conn(recent=[_TICKET_ROW]))
    assert isinstance(result['recent_tickets'][0], dict)


def test_recent_tickets_have_ticket_number():
    result = get_it_dashboard(_conn(recent=[_TICKET_ROW]))
    assert result['recent_tickets'][0]['ticket_number'] == 'TKT-2026-0001'


def test_recent_tickets_have_status():
    result = get_it_dashboard(_conn(recent=[_TICKET_ROW]))
    assert result['recent_tickets'][0]['status'] == 'open'


def test_recent_tickets_have_priority():
    result = get_it_dashboard(_conn(recent=[_TICKET_ROW]))
    assert result['recent_tickets'][0]['priority'] == 'high'


def test_recent_tickets_empty_when_no_rows():
    result = get_it_dashboard(_conn(recent=[]))
    assert result['recent_tickets'] == []


# ---------------------------------------------------------------------------
# SQL sanity
# ---------------------------------------------------------------------------

def test_sql_queries_it_ticket_first():
    c = _conn()
    get_it_dashboard(c)
    # index 0-1 are the _ensure_*_table schema DDL calls; the real dashboard
    # queries start at index 2.
    first_sql = c.execute.call_args_list[2][0][0]
    assert 'it_ticket' in first_sql


def test_sql_queries_it_asset_second():
    c = _conn()
    get_it_dashboard(c)
    second_sql = c.execute.call_args_list[3][0][0]
    assert 'it_asset' in second_sql


def test_sql_recent_uses_limit_8():
    c = _conn()
    get_it_dashboard(c)
    third_sql = c.execute.call_args_list[4][0][0]
    assert 'LIMIT 8' in third_sql


def test_sql_tickets_counts_open():
    c = _conn()
    get_it_dashboard(c)
    sql = c.execute.call_args_list[2][0][0]
    assert 'open' in sql


def test_sql_tickets_counts_critical():
    c = _conn()
    get_it_dashboard(c)
    sql = c.execute.call_args_list[2][0][0]
    assert 'critical' in sql


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_ticket_statuses_contains_open():
    assert 'open' in TICKET_STATUSES


def test_ticket_statuses_contains_resolved():
    assert 'resolved' in TICKET_STATUSES


def test_ticket_priorities_contains_critical():
    assert 'critical' in TICKET_PRIORITIES


def test_issue_types_contains_hardware():
    assert 'Hardware' in ISSUE_TYPES


def test_asset_statuses_contains_active():
    assert 'active' in ASSET_STATUSES


def test_asset_statuses_contains_repair():
    assert 'repair' in ASSET_STATUSES


def test_asset_types_contains_laptop():
    assert 'Laptop' in ASSET_TYPES


# ---------------------------------------------------------------------------
# next_ticket_number
# ---------------------------------------------------------------------------

def _num_conn(last_num):
    c = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda self, i: last_num
    c.execute.return_value.fetchone.return_value = row
    return c


def test_next_ticket_number_format():
    import re
    from datetime import date
    c = _num_conn(0)
    num = next_ticket_number(c)
    assert re.match(rf"TKT-{date.today().year}-\d{{4}}", num)


def test_next_ticket_number_increments():
    c = _num_conn(5)
    num = next_ticket_number(c)
    assert num.endswith('-0006')


def test_next_ticket_number_none_starts_at_1():
    c = _num_conn(None)
    num = next_ticket_number(c)
    assert num.endswith('-0001')


# ---------------------------------------------------------------------------
# list_tickets
# ---------------------------------------------------------------------------

def _list_conn(rows):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c


def test_list_tickets_returns_list():
    assert isinstance(list_tickets(_list_conn([])), list)


def test_list_tickets_converts_to_dicts():
    row = {'id': 1, 'ticket_number': 'TKT-2026-0001', 'status': 'open',
           'priority': 'high', 'requester': 'Bob', 'department': 'IT',
           'issue_type': 'Hardware', 'submitted_date': '2026-01-01',
           'due_date': '', 'assigned_to': ''}
    result = list_tickets(_list_conn([row]))
    assert result[0]['ticket_number'] == 'TKT-2026-0001'


def test_list_tickets_status_filter_adds_param():
    c = _list_conn([])
    list_tickets(c, status='open')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql
    assert 'open' in params


def test_list_tickets_priority_filter():
    c = _list_conn([])
    list_tickets(c, priority='critical')
    sql, params = c.execute.call_args[0]
    assert 'priority' in sql
    assert 'critical' in params


def test_list_tickets_search_filter():
    c = _list_conn([])
    list_tickets(c, search='network')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql
    assert any('network' in str(p) for p in params)


def test_list_tickets_no_filter_no_extra_params():
    c = _list_conn([])
    list_tickets(c)
    _, params = c.execute.call_args[0]
    assert params == []


# ---------------------------------------------------------------------------
# get_ticket
# ---------------------------------------------------------------------------

def test_get_ticket_returns_dict():
    row = {'id': 1, 'ticket_number': 'TKT-2026-0001', 'status': 'open'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_ticket(c, 1) == row


def test_get_ticket_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_ticket(c, 99) is None


# ---------------------------------------------------------------------------
# create_ticket
# ---------------------------------------------------------------------------

def test_create_ticket_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [42]
    result = create_ticket(
        c, 'TKT-2026-0001', 'Alice', 'Sales', 'Hardware',
        'Screen broken', 'high', 'Bob', '2026-06-01', '2026-06-04', '', 'alice@x.com',
    )
    assert result == 42


def test_create_ticket_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_ticket(c, 'TKT-2026-0001', 'Alice', 'Sales', 'Hardware',
                  'Screen broken', 'high', 'Bob', '2026-06-01', '2026-06-04', '', 'alice@x.com')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'it_ticket' in sql


# ---------------------------------------------------------------------------
# update_ticket
# ---------------------------------------------------------------------------

def test_update_ticket_builds_set_clause():
    c = MagicMock()
    update_ticket(c, 1, status='resolved', priority='low')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE it_ticket' in sql
    assert 'status' in sql and 'priority' in sql


def test_update_ticket_ignores_unknown_fields():
    c = MagicMock()
    update_ticket(c, 1, bogus_field='x')
    assert not any('UPDATE it_ticket' in call.args[0] for call in c.execute.call_args_list)


def test_update_ticket_noop_when_no_fields():
    c = MagicMock()
    update_ticket(c, 1)
    assert not any('UPDATE it_ticket' in call.args[0] for call in c.execute.call_args_list)


# ---------------------------------------------------------------------------
# set_ticket_status
# ---------------------------------------------------------------------------

def test_set_ticket_status_open_no_resolved_date():
    c = MagicMock()
    set_ticket_status(c, 1, 'open')
    sql = c.execute.call_args[0][0]
    assert 'resolved_date' not in sql


def test_set_ticket_status_resolved_sets_date():
    c = MagicMock()
    set_ticket_status(c, 1, 'resolved')
    sql = c.execute.call_args[0][0]
    assert 'resolved_date' in sql


def test_set_ticket_status_closed_sets_date():
    c = MagicMock()
    set_ticket_status(c, 1, 'closed')
    sql = c.execute.call_args[0][0]
    assert 'resolved_date' in sql


# ---------------------------------------------------------------------------
# list_assets
# ---------------------------------------------------------------------------

def test_list_assets_returns_list():
    assert isinstance(list_assets(_list_conn([])), list)


def test_list_assets_status_filter():
    c = _list_conn([])
    list_assets(c, status='repair')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'repair' in params


def test_list_assets_type_filter():
    c = _list_conn([])
    list_assets(c, asset_type='Laptop')
    sql, params = c.execute.call_args[0]
    assert 'asset_type' in sql and 'Laptop' in params


def test_list_assets_search_filter():
    c = _list_conn([])
    list_assets(c, search='dell')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql


# ---------------------------------------------------------------------------
# get_asset
# ---------------------------------------------------------------------------

def test_get_asset_returns_dict():
    row = {'id': 5, 'asset_tag': 'IT-0005', 'status': 'active'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_asset(c, 5) == row


def test_get_asset_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_asset(c, 99) is None


# ---------------------------------------------------------------------------
# create_asset
# ---------------------------------------------------------------------------

def test_create_asset_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [7]
    result = create_asset(c, 'IT-0007', 'Laptop', 'Dell', 'XPS',
                          'SN123', 'Alice', 'Sales', '2026-01-01', '2029-01-01', 'active', '')
    assert result == 7


def test_create_asset_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_asset(c, 'IT-0001', 'Desktop', 'HP', 'EliteDesk',
                 '', '', '', '', '', 'active', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'it_asset' in sql


# ---------------------------------------------------------------------------
# update_asset
# ---------------------------------------------------------------------------

def test_update_asset_builds_set_clause():
    c = MagicMock()
    update_asset(c, 5, status='repair', assigned_to='Bob')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE it_asset' in sql
    assert 'status' in sql and 'assigned_to' in sql


def test_update_asset_ignores_unknown_fields():
    c = MagicMock()
    update_asset(c, 5, nonexistent='x')
    assert not any('UPDATE it_asset' in call.args[0] for call in c.execute.call_args_list)


def test_update_asset_noop_when_no_fields():
    c = MagicMock()
    update_asset(c, 5)
    assert not any('UPDATE it_asset' in call.args[0] for call in c.execute.call_args_list)
