"""
Tests for manufacturing/quality_core.py.

Pure unit tests — no Qt, no live DB.  All DB calls go to a MagicMock.
"""

import datetime
import pytest
from unittest.mock import MagicMock

from manufacturing.quality_core import (
    NCR_STATUSES, CAPA_STATUSES, AUDIT_STATUSES, SUPPLIER_STATUSES, INSP_RESULTS, get_dashboard_counts,
    list_ncrs, get_ncr, create_ncr, update_ncr, close_ncr,
    list_capas, get_capa, create_capa, update_capa, close_capa,
    list_audits, get_audit, create_audit, update_audit, complete_audit,
    list_supplier_quality, get_supplier_quality,
    create_supplier_quality, update_supplier_quality,
    next_insp_number, list_inspections, get_inspection, create_inspection,
    update_inspection_result, get_defects, log_defect, resolve_defect,
    load_products_for_qa, load_work_orders_for_qa,
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_ncr_statuses_complete():
    for s in ('Open', 'Under Review', 'Dispositioned', 'Closed'):
        assert s in NCR_STATUSES


def test_capa_statuses_include_overdue():
    assert 'Overdue' in CAPA_STATUSES
    assert 'In Progress' in CAPA_STATUSES


def test_audit_statuses_include_complete():
    assert 'Complete' in AUDIT_STATUSES
    assert 'Scheduled' in AUDIT_STATUSES


def test_supplier_statuses_include_disqualified():
    assert 'Disqualified' in SUPPLIER_STATUSES
    assert 'Approved' in SUPPLIER_STATUSES


def test_insp_results_four_values():
    for r in ('pending', 'passed', 'failed', 'on_hold'):
        assert r in INSP_RESULTS


# ---------------------------------------------------------------------------
# get_dashboard_counts
# ---------------------------------------------------------------------------

def test_dashboard_counts_returns_dict():
    conn = _conn(fetchone={
        'open_ncrs': 3, 'open_capas': 1, 'open_audits': 2,
        'pending_inspections': 5, 'open_defects': 7,
        'critical_ncrs': 1, 'overdue_capas': 0,
    })
    result = get_dashboard_counts(conn)
    assert result['open_ncrs'] == 3
    assert result['critical_ncrs'] == 1


def test_dashboard_counts_fallback_when_none():
    conn = _conn(fetchone=None)
    result = get_dashboard_counts(conn)
    assert result['open_ncrs'] == 0


def test_dashboard_counts_queries_today():
    conn = _conn(fetchone={'open_ncrs': 0, 'open_capas': 0, 'open_audits': 0,
                           'pending_inspections': 0, 'open_defects': 0,
                           'critical_ncrs': 0, 'overdue_capas': 0})
    get_dashboard_counts(conn)
    params = conn.execute.call_args[0][1]
    assert _today() in params


# ---------------------------------------------------------------------------
# NCR
# ---------------------------------------------------------------------------

def test_list_ncrs_returns_all_when_no_filter():
    conn = _conn(fetchall=[
        {'id': 1, 'title': 'bad part', 'source': 'Incoming',
         'severity': 'Minor', 'product': '', 'detected_date': _today(),
         'disposition': 'Pending', 'owner': '', 'status': 'Open',
         'notes': '', 'created_by': 'u@e.com', 'closed_date': None},
    ])
    result = list_ncrs(conn)
    assert len(result) == 1
    assert result[0]['title'] == 'bad part'


def test_list_ncrs_status_filter():
    conn = _conn(fetchall=[])
    list_ncrs(conn, status='Open')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'status = %s' in sql
    assert 'Open' in params


def test_list_ncrs_search_uses_ilike():
    conn = _conn(fetchall=[])
    list_ncrs(conn, search='widget')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'ILIKE' in sql
    assert '%widget%' in params


def test_list_ncrs_no_filter_no_where():
    conn = _conn(fetchall=[])
    list_ncrs(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_get_ncr_returns_dict():
    conn = _conn(fetchone={'id': 1, 'title': 'x', 'source': '', 'severity': '',
                           'product': '', 'detected_date': '', 'disposition': '',
                           'owner': '', 'status': 'Open', 'notes': '',
                           'created_by': '', 'closed_date': None})
    result = get_ncr(conn, 1)
    assert result['id'] == 1


def test_get_ncr_returns_none_when_missing():
    conn = _conn(fetchone=None)
    assert get_ncr(conn, 99) is None


def test_create_ncr_returns_id():
    conn = _conn(fetchone={'id': 7})
    nid = create_ncr(conn, 'Dent in housing', 'Incoming', 'Major',
                     'Widget A', _today(), 'Pending', 'Bob', 'notes', 'u@e.com')
    assert nid == 7


def test_create_ncr_inserts_open_status():
    conn = _conn(fetchone={'id': 1})
    create_ncr(conn, 'Title', 'Incoming', 'Minor', '', _today(),
               'Pending', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'INSERT INTO qa_ncr' in sql
    assert "'Open'" in sql


def test_create_ncr_rejects_empty_title():
    conn = MagicMock()
    with pytest.raises(ValueError, match='required'):
        create_ncr(conn, '  ', 'Incoming', 'Minor', '', _today(),
                   'Pending', '', '', 'u@e.com')


def test_create_ncr_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_ncr(conn, 'Title', 'Incoming', 'Minor', '', _today(),
               'Pending', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_ncr_executes_update():
    conn = _conn()
    update_ncr(conn, 1, 'New Title', 'Final', 'Major', 'Part',
               _today(), 'Scrap', 'Bob', 'Open', 'notes')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE qa_ncr' in sql


def test_update_ncr_rejects_empty_title():
    conn = MagicMock()
    with pytest.raises(ValueError):
        update_ncr(conn, 1, '', 'Final', 'Major', '', _today(), '', '', 'Open', '')


def test_update_ncr_does_not_commit():
    conn = _conn()
    update_ncr(conn, 1, 'Title', 'Incoming', 'Minor', '', _today(), '', '', 'Open', '')
    conn.commit.assert_not_called()


def test_close_ncr_sets_closed():
    conn = _conn()
    close_ncr(conn, 1)
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'Closed' in sql
    assert _today() in params


def test_close_ncr_does_not_commit():
    conn = _conn()
    close_ncr(conn, 1)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# CAPA
# ---------------------------------------------------------------------------

def _capa_row(**kw):
    base = {'id': 1, 'title': 'Fix leak', 'capa_type': 'Corrective',
            'ncr_ref': '', 'owner': '', 'due_date': '', 'completed_date': '',
            'status': 'Open', 'action_plan': '', 'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_capas_returns_annotated():
    conn = _conn(fetchall=[_capa_row()])
    result = list_capas(conn)
    assert 'is_overdue' in result[0]


def test_list_capas_overdue_when_past_due():
    past = _days_ago(5)
    conn = _conn(fetchall=[_capa_row(due_date=past, status='Open')])
    result = list_capas(conn)
    assert result[0]['is_overdue'] is True


def test_list_capas_not_overdue_when_closed():
    past = _days_ago(5)
    conn = _conn(fetchall=[_capa_row(due_date=past, status='Closed')])
    result = list_capas(conn)
    assert result[0]['is_overdue'] is False


def test_list_capas_status_filter():
    conn = _conn(fetchall=[])
    list_capas(conn, status='Open')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'status = %s' in sql
    assert 'Open' in params


def test_get_capa_returns_dict():
    conn = _conn(fetchone=_capa_row())
    result = get_capa(conn, 1)
    assert result['id'] == 1


def test_get_capa_returns_none():
    conn = _conn(fetchone=None)
    assert get_capa(conn, 99) is None


def test_create_capa_returns_id():
    conn = _conn(fetchone={'id': 3})
    cid = create_capa(conn, 'Fix it', 'Corrective', '', 'Eve',
                      _today(), '', 'u@e.com')
    assert cid == 3


def test_create_capa_rejects_empty_title():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_capa(conn, '  ', 'Corrective', '', '', '', '', 'u@e.com')


def test_create_capa_open_status():
    conn = _conn(fetchone={'id': 1})
    create_capa(conn, 'Title', 'Corrective', '', '', '', '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert "'Open'" in sql


def test_create_capa_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_capa(conn, 'Title', 'Corrective', '', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_capa_executes_update():
    conn = _conn()
    update_capa(conn, 1, 'Title', 'Preventive', '', '', '', '', 'Open', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE qa_capa' in sql


def test_update_capa_rejects_empty_title():
    conn = MagicMock()
    with pytest.raises(ValueError):
        update_capa(conn, 1, '', 'Corrective', '', '', '', '', 'Open', '')


def test_close_capa_sets_closed():
    conn = _conn()
    close_capa(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'Closed' in sql
    params = conn.execute.call_args[0][1]
    assert _today() in params


def test_close_capa_does_not_commit():
    conn = _conn()
    close_capa(conn, 1)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Audits
# ---------------------------------------------------------------------------

def _audit_row(**kw):
    base = {'id': 1, 'title': 'ISO check', 'audit_type': 'Internal',
            'auditor': '', 'scheduled_date': '', 'completed_date': '',
            'result': '', 'status': 'Scheduled', 'findings': '',
            'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_audits_returns_rows():
    conn = _conn(fetchall=[_audit_row()])
    result = list_audits(conn)
    assert len(result) == 1
    assert 'is_overdue' in result[0]


def test_list_audits_overdue_when_scheduled_date_past():
    past = _days_ago(3)
    conn = _conn(fetchall=[_audit_row(scheduled_date=past, status='Scheduled')])
    result = list_audits(conn)
    assert result[0]['is_overdue'] is True


def test_list_audits_not_overdue_when_complete():
    past = _days_ago(3)
    conn = _conn(fetchall=[_audit_row(scheduled_date=past, status='Complete')])
    result = list_audits(conn)
    assert result[0]['is_overdue'] is False


def test_list_audits_status_filter():
    conn = _conn(fetchall=[])
    list_audits(conn, status='Scheduled')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'status = %s' in sql
    assert 'Scheduled' in params


def test_get_audit_returns_dict():
    conn = _conn(fetchone=_audit_row())
    result = get_audit(conn, 1)
    assert result['id'] == 1


def test_get_audit_returns_none():
    conn = _conn(fetchone=None)
    assert get_audit(conn, 99) is None


def test_create_audit_returns_id():
    conn = _conn(fetchone={'id': 5})
    aid = create_audit(conn, 'Q1 Audit', 'Internal', 'Alice',
                       _today(), '', 'u@e.com')
    assert aid == 5


def test_create_audit_rejects_empty_title():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_audit(conn, '', 'Internal', '', '', '', 'u@e.com')


def test_create_audit_scheduled_status():
    conn = _conn(fetchone={'id': 1})
    create_audit(conn, 'Audit', 'Internal', '', _today(), '', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert "'Scheduled'" in sql


def test_create_audit_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_audit(conn, 'Audit', 'Internal', '', '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_audit_executes_update():
    conn = _conn()
    update_audit(conn, 1, 'Title', 'External', 'Bob', '', '', '', 'Scheduled', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE qa_audit' in sql


def test_update_audit_rejects_empty_title():
    conn = MagicMock()
    with pytest.raises(ValueError):
        update_audit(conn, 1, '', 'Internal', '', '', '', '', 'Scheduled', '')


def test_complete_audit_stamps_date():
    conn = _conn()
    complete_audit(conn, 1, 'Pass', 'All good')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'Complete' in sql
    assert _today() in params


def test_complete_audit_does_not_commit():
    conn = _conn()
    complete_audit(conn, 1, '', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Supplier Quality
# ---------------------------------------------------------------------------

def _sq_row(**kw):
    base = {'id': 1, 'supplier': 'Acme', 'material': 'Steel',
            'rating': 'A', 'ppm': '0', 'last_audit': '',
            'status': 'Approved', 'notes': '', 'created_by': 'u@e.com'}
    base.update(kw)
    return base


def test_list_supplier_quality_returns_rows():
    conn = _conn(fetchall=[_sq_row()])
    result = list_supplier_quality(conn)
    assert result[0]['supplier'] == 'Acme'


def test_list_supplier_quality_status_filter():
    conn = _conn(fetchall=[])
    list_supplier_quality(conn, status='Approved')
    params = conn.execute.call_args[0][1]
    assert 'Approved' in params


def test_list_supplier_quality_search():
    conn = _conn(fetchall=[])
    list_supplier_quality(conn, search='acme')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_supplier_quality_returns_dict():
    conn = _conn(fetchone=_sq_row())
    result = get_supplier_quality(conn, 1)
    assert result['id'] == 1


def test_get_supplier_quality_returns_none():
    conn = _conn(fetchone=None)
    assert get_supplier_quality(conn, 99) is None


def test_create_supplier_quality_returns_id():
    conn = _conn(fetchone={'id': 4})
    sid = create_supplier_quality(conn, 'BestParts', 'Rubber', 'B',
                                   '50', '', 'Pending', '', 'u@e.com')
    assert sid == 4


def test_create_supplier_quality_rejects_empty_name():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_supplier_quality(conn, '  ', '', '', '', '', 'Pending', '', 'u@e.com')


def test_create_supplier_quality_defaults_pending():
    conn = _conn(fetchone={'id': 1})
    create_supplier_quality(conn, 'SupX', '', '', '', '', '', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'Pending' in params


def test_create_supplier_quality_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_supplier_quality(conn, 'SupX', '', '', '', '', 'Pending', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_update_supplier_quality_executes_update():
    conn = _conn()
    update_supplier_quality(conn, 1, 'Acme', 'Steel', 'A', '0', '', 'Approved', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE qa_supplier' in sql


def test_update_supplier_quality_rejects_empty_name():
    conn = MagicMock()
    with pytest.raises(ValueError):
        update_supplier_quality(conn, 1, '', '', '', '', '', 'Approved', '')


def test_update_supplier_quality_does_not_commit():
    conn = _conn()
    update_supplier_quality(conn, 1, 'Acme', '', '', '', '', 'Approved', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------

def test_next_insp_number_starts_at_0001_when_empty():
    conn = _conn(fetchall=[])
    num = next_insp_number(conn)
    year = datetime.date.today().year
    assert num == f'QA-{year}-0001'


def test_next_insp_number_increments():
    year = datetime.date.today().year
    conn = _conn(fetchall=[
        {'insp_number': f'QA-{year}-0003'},
        {'insp_number': f'QA-{year}-0001'},
    ])
    num = next_insp_number(conn)
    assert num == f'QA-{year}-0004'


def test_next_insp_number_ignores_bad_rows():
    conn = _conn(fetchall=[
        {'insp_number': 'NOT-A-NUMBER'},
    ])
    year = datetime.date.today().year
    num = next_insp_number(conn)
    assert num == f'QA-{year}-0001'


def test_list_inspections_returns_rows():
    conn = _conn(fetchall=[
        {'id': 1, 'insp_number': 'QA-2026-0001', 'product_name': 'Widget',
         'inspector': 'Bob', 'insp_date': _today(), 'result': 'passed',
         'defect_count': 0, 'open_defects': 0, 'notes': ''},
    ])
    result = list_inspections(conn)
    assert result[0]['insp_number'] == 'QA-2026-0001'


def test_list_inspections_result_filter():
    conn = _conn(fetchall=[])
    list_inspections(conn, result='failed')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'result' in sql
    assert 'failed' in params


def test_list_inspections_search_ilike():
    conn = _conn(fetchall=[])
    list_inspections(conn, search='widget')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_inspection_returns_dict():
    conn = _conn(fetchone={'id': 1, 'insp_number': 'QA-2026-0001',
                           'product_name': 'W', 'inspector': 'Bob',
                           'insp_date': _today(), 'result': 'pending',
                           'notes': '', 'product_id': 1, 'wo_id': None,
                           'created_by': 'u@e.com'})
    result = get_inspection(conn, 1)
    assert result['id'] == 1


def test_get_inspection_returns_none():
    conn = _conn(fetchone=None)
    assert get_inspection(conn, 99) is None


def test_create_inspection_returns_id():
    conn = _conn(fetchone={'id': 9})
    iid = create_inspection(conn, 'QA-2026-0001', 1, None,
                             _today(), 'Bob', 'pending', '', 'u@e.com')
    assert iid == 9


def test_create_inspection_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_inspection(conn, 'QA-2026-0001', None, None,
                      _today(), '', 'pending', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_create_inspection_defaults_pending_on_unknown_result():
    conn = _conn(fetchone={'id': 1})
    create_inspection(conn, 'QA-2026-0001', None, None,
                      _today(), '', 'bogus', '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'pending' in params


def test_update_inspection_result_valid():
    conn = _conn()
    update_inspection_result(conn, 1, 'passed')
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'UPDATE qa_inspection' in sql
    assert 'passed' in params


def test_update_inspection_result_invalid_raises():
    conn = _conn()
    with pytest.raises(ValueError):
        update_inspection_result(conn, 1, 'bogus')


def test_update_inspection_result_does_not_commit():
    conn = _conn()
    update_inspection_result(conn, 1, 'failed')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Defects
# ---------------------------------------------------------------------------

def test_get_defects_returns_rows():
    conn = _conn(fetchall=[
        {'id': 1, 'insp_id': 1, 'defect_type': 'Visual', 'severity': 'minor',
         'description': 'scratch', 'resolved': 0, 'created_by': 'u@e.com'},
    ])
    result = get_defects(conn, 1)
    assert result[0]['defect_type'] == 'Visual'


def test_get_defects_empty():
    conn = _conn(fetchall=[])
    assert get_defects(conn, 1) == []


def test_log_defect_returns_id():
    conn = _conn(fetchone={'id': 2})
    did = log_defect(conn, 1, 'Dimensional', 'major', 'Out of spec', 'u@e.com')
    assert did == 2


def test_log_defect_rejects_empty_description():
    conn = MagicMock()
    with pytest.raises(ValueError):
        log_defect(conn, 1, 'Visual', 'minor', '  ', 'u@e.com')


def test_log_defect_defaults_minor_on_bad_severity():
    conn = _conn(fetchone={'id': 1})
    log_defect(conn, 1, 'Type', 'extreme', 'problem', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'minor' in params


def test_log_defect_inserts_resolved_zero():
    conn = _conn(fetchone={'id': 1})
    log_defect(conn, 1, 'V', 'minor', 'desc', 'u@e.com')
    sql = conn.execute.call_args[0][0]
    assert ',0,' in sql or ', 0,' in sql


def test_log_defect_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    log_defect(conn, 1, 'V', 'minor', 'desc', 'u@e.com')
    conn.commit.assert_not_called()


def test_resolve_defect_updates_resolved():
    conn = _conn()
    resolve_defect(conn, 3)
    sql = conn.execute.call_args[0][0]
    params = conn.execute.call_args[0][1]
    assert 'resolved=1' in sql
    assert 3 in params


def test_resolve_defect_does_not_commit():
    conn = _conn()
    resolve_defect(conn, 3)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Product / WO loaders
# ---------------------------------------------------------------------------

def test_load_products_for_qa_returns_list():
    conn = _conn(fetchall=[{'id': 1, 'name': 'Widget'}, {'id': 2, 'name': 'Gear'}])
    result = load_products_for_qa(conn)
    assert len(result) == 2
    assert result[0]['name'] == 'Widget'


def test_load_products_for_qa_empty():
    conn = _conn(fetchall=[])
    assert load_products_for_qa(conn) == []


def test_load_work_orders_for_qa_returns_list():
    conn = _conn(fetchall=[{'id': 10, 'wo_number': 'WO-2026-0001'}])
    result = load_work_orders_for_qa(conn)
    assert result[0]['wo_number'] == 'WO-2026-0001'


def test_load_work_orders_for_qa_empty():
    conn = _conn(fetchall=[])
    assert load_work_orders_for_qa(conn) == []
