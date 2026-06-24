"""Tests for manufacturing/it_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.it_core import get_it_dashboard

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
        MagicMock(**{'fetchone.return_value': ts}),
        MagicMock(**{'fetchone.return_value': ast}),
        MagicMock(**{'fetchall.return_value': rec}),
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
    first_sql = c.execute.call_args_list[0][0][0]
    assert 'it_ticket' in first_sql


def test_sql_queries_it_asset_second():
    c = _conn()
    get_it_dashboard(c)
    second_sql = c.execute.call_args_list[1][0][0]
    assert 'it_asset' in second_sql


def test_sql_recent_uses_limit_8():
    c = _conn()
    get_it_dashboard(c)
    third_sql = c.execute.call_args_list[2][0][0]
    assert 'LIMIT 8' in third_sql


def test_sql_tickets_counts_open():
    c = _conn()
    get_it_dashboard(c)
    sql = c.execute.call_args_list[0][0][0]
    assert 'open' in sql


def test_sql_tickets_counts_critical():
    c = _conn()
    get_it_dashboard(c)
    sql = c.execute.call_args_list[0][0][0]
    assert 'critical' in sql
