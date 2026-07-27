"""Tests for manufacturing/legal_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.legal_core import (
    get_legal_dashboard,
    list_contracts, get_contract, create_contract, update_contract,
    list_compliance, get_compliance_item, create_compliance, update_compliance,
    list_litigation, get_litigation_case, create_litigation, update_litigation,
    list_ip, create_ip,
    list_employment, create_employment,
    list_governance, create_governance,
    CONTRACT_TYPES, CONTRACT_STATUSES, COMPLIANCE_STATUSES,
    LITIGATION_TYPES, LITIGATION_STATUSES,
    IP_TYPES, IP_STATUSES, EMPLOYMENT_MATTER_TYPES, EMPLOYMENT_STATUSES,
    GOVERNANCE_CATEGORIES, GOVERNANCE_STATUSES,
)

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
        MagicMock(fetchone=MagicMock(return_value=cs)),
        MagicMock(fetchone=MagicMock(return_value=comp)),
        MagicMock(fetchone=MagicMock(return_value=lit)),
        MagicMock(fetchall=MagicMock(return_value=rec)),
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_contract_statuses_has_active():
    assert 'Active' in CONTRACT_STATUSES

def test_contract_statuses_has_draft():
    assert 'Draft' in CONTRACT_STATUSES

def test_contract_types_has_nda():
    assert 'NDA' in CONTRACT_TYPES

def test_compliance_statuses_has_pending():
    assert 'Pending' in COMPLIANCE_STATUSES

def test_compliance_statuses_has_overdue():
    assert 'Overdue' in COMPLIANCE_STATUSES

def test_litigation_statuses_has_open():
    assert 'Open' in LITIGATION_STATUSES

def test_litigation_statuses_has_closed():
    assert 'Closed' in LITIGATION_STATUSES

def test_litigation_types_has_civil():
    assert 'Civil' in LITIGATION_TYPES


# ---------------------------------------------------------------------------
# list_contracts
# ---------------------------------------------------------------------------

def _list_conn(rows):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c

def test_list_contracts_returns_list():
    assert isinstance(list_contracts(_list_conn([])), list)

def test_list_contracts_status_filter():
    c = _list_conn([])
    list_contracts(c, status='Active')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Active' in params

def test_list_contracts_type_filter():
    c = _list_conn([])
    list_contracts(c, contract_type='NDA')
    sql, params = c.execute.call_args[0]
    assert 'contract_type' in sql and 'NDA' in params

def test_list_contracts_search_filter():
    c = _list_conn([])
    list_contracts(c, search='acme')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('acme' in str(p) for p in params)

def test_list_contracts_no_filter_no_params():
    c = _list_conn([])
    list_contracts(c)
    _, params = c.execute.call_args[0]
    assert params == []

def test_list_contracts_converts_to_dicts():
    row = {'id': 1, 'title': 'NDA', 'counterparty': 'ACME', 'contract_type': 'NDA',
           'value': 0.0, 'start_date': '', 'end_date': '', 'owner': '', 'status': 'Draft'}
    result = list_contracts(_list_conn([row]))
    assert result[0]['title'] == 'NDA'


# ---------------------------------------------------------------------------
# get_contract
# ---------------------------------------------------------------------------

def test_get_contract_returns_dict():
    row = {'id': 1, 'title': 'Vendor Agreement', 'status': 'Active'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_contract(c, 1) == row

def test_get_contract_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_contract(c, 99) is None


# ---------------------------------------------------------------------------
# create_contract
# ---------------------------------------------------------------------------

def test_create_contract_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [5]
    result = create_contract(c, 'NDA', 'ACME', 'NDA', 10000.0,
                             '2026-01-01', '2027-01-01', 'Legal Dept', 'Active', '')
    assert result == 5

def test_create_contract_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_contract(c, 'NDA', 'ACME', 'NDA', 0, '', '', '', 'Draft', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'legal_contract' in sql


# ---------------------------------------------------------------------------
# update_contract
# ---------------------------------------------------------------------------

def test_update_contract_builds_set_clause():
    c = MagicMock()
    update_contract(c, 1, status='Expired', owner='Legal')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE legal_contract' in sql and 'status' in sql

def test_update_contract_ignores_unknown_fields():
    c = MagicMock()
    update_contract(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_contract_noop_when_no_fields():
    c = MagicMock()
    update_contract(c, 1)
    c.execute.assert_not_called()


# ---------------------------------------------------------------------------
# list_compliance
# ---------------------------------------------------------------------------

def test_list_compliance_returns_list():
    assert isinstance(list_compliance(_list_conn([])), list)

def test_list_compliance_status_filter():
    c = _list_conn([])
    list_compliance(c, status='Pending')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Pending' in params

def test_list_compliance_search_filter():
    c = _list_conn([])
    list_compliance(c, search='OSHA')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql

def test_list_compliance_ordered_by_due_date():
    c = _list_conn([])
    list_compliance(c)
    sql, _ = c.execute.call_args[0]
    assert 'due_date' in sql


# ---------------------------------------------------------------------------
# get_compliance_item
# ---------------------------------------------------------------------------

def test_get_compliance_item_returns_dict():
    row = {'id': 2, 'requirement': 'Annual safety report', 'status': 'Pending'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_compliance_item(c, 2) == row

def test_get_compliance_item_returns_none():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_compliance_item(c, 99) is None


# ---------------------------------------------------------------------------
# create_compliance
# ---------------------------------------------------------------------------

def test_create_compliance_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [3]
    result = create_compliance(c, 'Annual report', 'OSHA', 'Safety Mgr',
                               '2026-12-31', 'Pending', '')
    assert result == 3

def test_create_compliance_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_compliance(c, 'Report', '', '', '', 'Pending', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'legal_compliance' in sql


# ---------------------------------------------------------------------------
# update_compliance
# ---------------------------------------------------------------------------

def test_update_compliance_builds_set_clause():
    c = MagicMock()
    update_compliance(c, 1, status='Complete', completed_date='2026-06-01')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE legal_compliance' in sql and 'status' in sql

def test_update_compliance_ignores_unknown():
    c = MagicMock()
    update_compliance(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_compliance_noop_when_no_fields():
    c = MagicMock()
    update_compliance(c, 1)
    c.execute.assert_not_called()


# ---------------------------------------------------------------------------
# list_litigation
# ---------------------------------------------------------------------------

def test_list_litigation_returns_list():
    assert isinstance(list_litigation(_list_conn([])), list)

def test_list_litigation_status_filter():
    c = _list_conn([])
    list_litigation(c, status='Open')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Open' in params

def test_list_litigation_type_filter():
    c = _list_conn([])
    list_litigation(c, case_type='Civil')
    sql, params = c.execute.call_args[0]
    assert 'case_type' in sql and 'Civil' in params

def test_list_litigation_search_filter():
    c = _list_conn([])
    list_litigation(c, search='smith')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql


# ---------------------------------------------------------------------------
# get_litigation_case
# ---------------------------------------------------------------------------

def test_get_litigation_case_returns_dict():
    row = {'id': 1, 'case_name': 'Smith v Co', 'status': 'Open'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_litigation_case(c, 1) == row

def test_get_litigation_case_returns_none():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_litigation_case(c, 99) is None


# ---------------------------------------------------------------------------
# create_litigation
# ---------------------------------------------------------------------------

def test_create_litigation_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [9]
    result = create_litigation(c, 'Smith v Co', 'John Smith', 'Superior Court',
                               'Employment', '2026-01-15', 'Open', '', '')
    assert result == 9

def test_create_litigation_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_litigation(c, 'Case', '', '', 'Civil', '', 'Open', '', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'legal_litigation' in sql


# ---------------------------------------------------------------------------
# update_litigation
# ---------------------------------------------------------------------------

def test_update_litigation_builds_set_clause():
    c = MagicMock()
    update_litigation(c, 1, status='Settled', outcome='Agreed settlement')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE legal_litigation' in sql and 'status' in sql

def test_update_litigation_ignores_unknown():
    c = MagicMock()
    update_litigation(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_litigation_noop_when_no_fields():
    c = MagicMock()
    update_litigation(c, 1)
    c.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Intellectual Property
# ---------------------------------------------------------------------------

def test_ip_types_has_patent():
    assert 'Patent' in IP_TYPES

def test_ip_statuses_has_registered():
    assert 'Registered' in IP_STATUSES

def test_list_ip_returns_list():
    assert isinstance(list_ip(_list_conn([])), list)

def test_list_ip_status_filter():
    c = _list_conn([])
    list_ip(c, status='Registered')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Registered' in params

def test_list_ip_search_filter():
    c = _list_conn([])
    list_ip(c, search='widget')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('widget' in str(p) for p in params)

def test_create_ip_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [11]
    result = create_ip(c, 'Widget Patent', 'Patent', 'US123456', 'US',
                        '2026-01-01', '2046-01-01', 'Pending', '')
    assert result == 11

def test_create_ip_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_ip(c, 'Widget Patent', 'Patent', '', '', '', '', 'Pending', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'legal_ip' in sql


# ---------------------------------------------------------------------------
# Employment Law
# ---------------------------------------------------------------------------

def test_employment_matter_types_has_discrimination():
    assert 'Discrimination' in EMPLOYMENT_MATTER_TYPES

def test_employment_statuses_has_open():
    assert 'Open' in EMPLOYMENT_STATUSES

def test_list_employment_returns_list():
    assert isinstance(list_employment(_list_conn([])), list)

def test_list_employment_status_filter():
    c = _list_conn([])
    list_employment(c, status='Investigating')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Investigating' in params

def test_list_employment_search_filter():
    c = _list_conn([])
    list_employment(c, search='smith')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql

def test_create_employment_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [12]
    result = create_employment(c, 'Wrongful termination claim', 'J. Smith',
                                'Termination', 'HR', '2026-02-01', '', 'Open', '')
    assert result == 12

def test_create_employment_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_employment(c, 'Claim', '', '', '', '', '', 'Open', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'legal_employment' in sql


# ---------------------------------------------------------------------------
# Corporate Governance
# ---------------------------------------------------------------------------

def test_governance_categories_has_bylaw():
    assert 'Bylaw' in GOVERNANCE_CATEGORIES

def test_governance_statuses_has_active():
    assert 'Active' in GOVERNANCE_STATUSES

def test_list_governance_returns_list():
    assert isinstance(list_governance(_list_conn([])), list)

def test_list_governance_status_filter():
    c = _list_conn([])
    list_governance(c, status='Active')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Active' in params

def test_list_governance_search_filter():
    c = _list_conn([])
    list_governance(c, search='bylaws')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql

def test_create_governance_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [13]
    result = create_governance(c, 'Board Bylaws Amendment', 'Bylaw', 'Corp Sec',
                                '2026-01-01', 'BYL-2026-01', 'Active', '')
    assert result == 13

def test_create_governance_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_governance(c, 'Bylaws', '', '', '', '', 'Active', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'legal_governance' in sql
