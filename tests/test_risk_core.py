"""Tests for manufacturing/risk_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.risk_core import (
    list_risk_register, create_risk_register,
    list_risk_assessments, create_risk_assessment,
    list_risk_insurance, create_risk_insurance,
    list_risk_continuity, create_risk_continuity,
    list_risk_audits, create_risk_audit,
    list_risk_kris, create_risk_kri,
    RISK_STATUSES, ASSESSMENT_STATUSES, INSURANCE_STATUSES,
    CONTINUITY_STATUSES, AUDIT_STATUSES, KRI_STATUSES,
)


def _conn(rows=None):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows if rows is not None else []
    return c


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_risk_statuses_has_open():
    assert 'Open' in RISK_STATUSES

def test_risk_statuses_has_closed():
    assert 'Closed' in RISK_STATUSES

def test_assessment_statuses_has_identified():
    assert 'Identified' in ASSESSMENT_STATUSES

def test_insurance_statuses_has_active():
    assert 'Active' in INSURANCE_STATUSES

def test_continuity_statuses_has_draft():
    assert 'Draft' in CONTINUITY_STATUSES

def test_audit_statuses_has_scheduled():
    assert 'Scheduled' in AUDIT_STATUSES

def test_kri_statuses_has_normal():
    assert 'Normal' in KRI_STATUSES

def test_kri_statuses_has_breached():
    assert 'Breached' in KRI_STATUSES


# ---------------------------------------------------------------------------
# list_risk_register / create_risk_register
# ---------------------------------------------------------------------------

def test_list_risk_register_returns_list():
    assert isinstance(list_risk_register(_conn()), list)

def test_list_risk_register_status_filter():
    c = _conn()
    list_risk_register(c, status='Open')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Open' in params

def test_list_risk_register_search_filter():
    c = _conn()
    list_risk_register(c, search='fire')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('fire' in str(p) for p in params)

def test_list_risk_register_no_filter_no_params():
    c = _conn()
    list_risk_register(c)
    _, params = c.execute.call_args[0]
    assert params == []

def test_list_risk_register_converts_to_dicts():
    row = {'id': 1, 'risk': 'Flood', 'category': 'Facilities', 'severity': 'High',
           'response': 'Mitigate', 'owner': 'Ops', 'target_date': '2026-12-01',
           'status': 'Open', 'mitigation': ''}
    result = list_risk_register(_conn([row]))
    assert result[0]['risk'] == 'Flood'

def test_create_risk_register_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [7]
    result = create_risk_register(c, 'Flood', 'Facilities', 'High', 'Mitigate',
                                   'Ops', '2026-12-01', 'Open', '')
    assert result == 7

def test_create_risk_register_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_register(c, 'Flood', '', '', '', '', '', 'Open', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'risk_register' in sql


# ---------------------------------------------------------------------------
# list_risk_assessments / create_risk_assessment
# ---------------------------------------------------------------------------

def test_list_risk_assessments_returns_list():
    assert isinstance(list_risk_assessments(_conn()), list)

def test_list_risk_assessments_status_filter():
    c = _conn()
    list_risk_assessments(c, status='Assessed')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Assessed' in params

def test_list_risk_assessments_search_filter():
    c = _conn()
    list_risk_assessments(c, search='cyber')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql

def test_create_risk_assessment_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [4]
    result = create_risk_assessment(c, 'Cyber breach', 'IT', 'Medium', 'High',
                                     'High', 'CISO', '2026-06-01', 'Identified', '')
    assert result == 4

def test_create_risk_assessment_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_assessment(c, 'Cyber', '', '', '', '', '', '', 'Identified', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'risk_assessment' in sql


# ---------------------------------------------------------------------------
# list_risk_insurance / create_risk_insurance
# ---------------------------------------------------------------------------

def test_list_risk_insurance_returns_list():
    assert isinstance(list_risk_insurance(_conn()), list)

def test_list_risk_insurance_status_filter():
    c = _conn()
    list_risk_insurance(c, status='Expired')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Expired' in params

def test_list_risk_insurance_search_filter():
    c = _conn()
    list_risk_insurance(c, search='Travelers')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql

def test_create_risk_insurance_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [2]
    result = create_risk_insurance(c, 'GL-1001', 'Travelers', 'General Liability',
                                    1000000.0, 5000.0, '2026-01-01', '2027-01-01',
                                    'Active', '')
    assert result == 2

def test_create_risk_insurance_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_insurance(c, 'GL-1001', '', '', 0, 0, '', '', 'Active', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'risk_insurance' in sql

def test_create_risk_insurance_defaults_coverage_zero():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_insurance(c, 'GL-1001', '', '', None, None, '', '', 'Active', '')
    params = c.execute.call_args[0][1]
    assert params[3] == 0 and params[4] == 0


# ---------------------------------------------------------------------------
# list_risk_continuity / create_risk_continuity
# ---------------------------------------------------------------------------

def test_list_risk_continuity_returns_list():
    assert isinstance(list_risk_continuity(_conn()), list)

def test_list_risk_continuity_status_filter():
    c = _conn()
    list_risk_continuity(c, status='Active')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Active' in params

def test_create_risk_continuity_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [3]
    result = create_risk_continuity(c, 'DR Plan', 'Data Center', 'Critical',
                                     'IT Mgr', '2026-01-01', '2026-07-01', 'Active', '')
    assert result == 3

def test_create_risk_continuity_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_continuity(c, 'DR Plan', '', '', '', '', '', 'Draft', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'risk_continuity' in sql


# ---------------------------------------------------------------------------
# list_risk_audits / create_risk_audit
# ---------------------------------------------------------------------------

def test_list_risk_audits_returns_list():
    assert isinstance(list_risk_audits(_conn()), list)

def test_list_risk_audits_status_filter():
    c = _conn()
    list_risk_audits(c, status='Completed')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Completed' in params

def test_create_risk_audit_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [6]
    result = create_risk_audit(c, 'SOC 2', 'AICPA', 'Ext. Auditor',
                                '2026-03-01', '', '', 'Scheduled', '')
    assert result == 6

def test_create_risk_audit_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_audit(c, 'SOC 2', '', '', '', '', '', 'Scheduled', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'risk_audit' in sql


# ---------------------------------------------------------------------------
# list_risk_kris / create_risk_kri
# ---------------------------------------------------------------------------

def test_list_risk_kris_returns_list():
    assert isinstance(list_risk_kris(_conn()), list)

def test_list_risk_kris_status_filter():
    c = _conn()
    list_risk_kris(c, status='Breached')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Breached' in params

def test_create_risk_kri_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [8]
    result = create_risk_kri(c, 'Late shipments %', 'Operations', '5%', '7%',
                              'Ops Mgr', '2026-06-01', 'Watch', '')
    assert result == 8

def test_create_risk_kri_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_risk_kri(c, 'Late shipments %', '', '', '', '', '', 'Normal', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'risk_kri' in sql
