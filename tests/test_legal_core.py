"""Tests for manufacturing/legal_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.legal_core import get_legal_dashboard

_CONTRACT_STATS = {'total': 10, 'active': 6, 'draft': 2}
_COMPLIANCE_STATS = {'total': 8, 'pending': 3, 'completed': 5}
_LITIGATION_STATS = {'total': 4, 'open': 2, 'closed': 2}

_CONTRACT_ROW = {
    'id': 1, 'title': 'Vendor Agreement', 'counterparty': 'ACME Corp',
    'contract_type': 'Vendor', 'value': 50000.0,
    'status': 'Active', 'end_date': '2027-01-01',
}


def _conn(contract_stats=None, compliance_stats=None, litigation_stats=None,
          recent=None):
    c = MagicMock()
    cs = contract_stats if contract_stats is not None else _CONTRACT_STATS
    comp = compliance_stats if compliance_stats is not None else _COMPLIANCE_STATS
    lit = litigation_stats if litigation_stats is not None else _LITIGATION_STATS
    rec = recent if recent is not None else []
    c.execute.side_effect = [
        MagicMock(**{'fetchone.return_value': cs}),
        MagicMock(**{'fetchone.return_value': comp}),
        MagicMock(**{'fetchone.return_value': lit}),
        MagicMock(**{'fetchall.return_value': rec}),
    ]
    return c


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_returns_dict():
    assert isinstance(get_legal_dashboard(_conn()), dict)


def test_has_contracts_key():
    assert 'contracts' in get_legal_dashboard(_conn())


def test_has_compliance_key():
    assert 'compliance' in get_legal_dashboard(_conn())


def test_has_litigation_key():
    assert 'litigation' in get_legal_dashboard(_conn())


def test_has_recent_contracts_key():
    assert 'recent_contracts' in get_legal_dashboard(_conn())


# ---------------------------------------------------------------------------
# contracts stats
# ---------------------------------------------------------------------------

def test_contracts_total():
    assert get_legal_dashboard(_conn())['contracts']['total'] == 10


def test_contracts_active():
    assert get_legal_dashboard(_conn())['contracts']['active'] == 6


def test_contracts_draft():
    assert get_legal_dashboard(_conn())['contracts']['draft'] == 2


# ---------------------------------------------------------------------------
# compliance stats
# ---------------------------------------------------------------------------

def test_compliance_total():
    assert get_legal_dashboard(_conn())['compliance']['total'] == 8


def test_compliance_pending():
    assert get_legal_dashboard(_conn())['compliance']['pending'] == 3


def test_compliance_completed():
    assert get_legal_dashboard(_conn())['compliance']['completed'] == 5


# ---------------------------------------------------------------------------
# litigation stats
# ---------------------------------------------------------------------------

def test_litigation_total():
    assert get_legal_dashboard(_conn())['litigation']['total'] == 4


def test_litigation_open():
    assert get_legal_dashboard(_conn())['litigation']['open'] == 2


def test_litigation_closed():
    assert get_legal_dashboard(_conn())['litigation']['closed'] == 2


# ---------------------------------------------------------------------------
# recent_contracts
# ---------------------------------------------------------------------------

def test_recent_contracts_is_list():
    result = get_legal_dashboard(_conn(recent=[_CONTRACT_ROW]))
    assert isinstance(result['recent_contracts'], list)


def test_recent_contracts_items_are_dicts():
    result = get_legal_dashboard(_conn(recent=[_CONTRACT_ROW]))
    assert isinstance(result['recent_contracts'][0], dict)


def test_recent_contracts_have_title():
    result = get_legal_dashboard(_conn(recent=[_CONTRACT_ROW]))
    assert result['recent_contracts'][0]['title'] == 'Vendor Agreement'


def test_recent_contracts_have_status():
    result = get_legal_dashboard(_conn(recent=[_CONTRACT_ROW]))
    assert result['recent_contracts'][0]['status'] == 'Active'


def test_recent_contracts_empty_when_no_rows():
    assert get_legal_dashboard(_conn(recent=[]))['recent_contracts'] == []


# ---------------------------------------------------------------------------
# SQL sanity
# ---------------------------------------------------------------------------

def test_sql_first_query_hits_legal_contract():
    c = _conn()
    get_legal_dashboard(c)
    assert 'legal_contract' in c.execute.call_args_list[0][0][0]


def test_sql_second_query_hits_legal_compliance():
    c = _conn()
    get_legal_dashboard(c)
    assert 'legal_compliance' in c.execute.call_args_list[1][0][0]


def test_sql_third_query_hits_legal_litigation():
    c = _conn()
    get_legal_dashboard(c)
    assert 'legal_litigation' in c.execute.call_args_list[2][0][0]


def test_sql_recent_uses_limit_8():
    c = _conn()
    get_legal_dashboard(c)
    assert 'LIMIT 8' in c.execute.call_args_list[3][0][0]
