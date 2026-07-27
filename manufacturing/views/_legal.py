"""Views: legal domain."""

import json

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..csv_export import export_response

from ..legal_core import (
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

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Legal dashboard
# ---------------------------------------------------------------------------

_LEGAL_DEPT_KEYS = {'legal', 'risk_management'}


def _legal_ctx(request, **extra):
    return {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        **extra,
    }


@dept_required(_LEGAL_DEPT_KEYS)
def legal_dashboard(request):
    with get_db_connection() as conn:
        data = get_legal_dashboard(conn)

        contract_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM legal_contract
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        contract_status_json = json.dumps([dict(r) for r in contract_status_rows])

        contract_type_rows = conn.execute("""
            SELECT contract_type, COUNT(*) AS cnt FROM legal_contract
            WHERE contract_type IS NOT NULL AND contract_type != ''
            GROUP BY contract_type ORDER BY cnt DESC
        """).fetchall()
        contract_type_json = json.dumps([dict(r) for r in contract_type_rows])

        contract_value_rows = conn.execute("""
            SELECT counterparty, SUM(value) AS total_value FROM legal_contract
            WHERE counterparty IS NOT NULL AND counterparty != ''
            GROUP BY counterparty ORDER BY total_value DESC LIMIT 8
        """).fetchall()
        contract_value_json = json.dumps([dict(r) for r in contract_value_rows])

        compliance_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM legal_compliance
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        compliance_status_json = json.dumps([dict(r) for r in compliance_status_rows])

        litigation_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM legal_litigation
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        litigation_status_json = json.dumps([dict(r) for r in litigation_status_rows])

        litigation_type_rows = conn.execute("""
            SELECT case_type, COUNT(*) AS cnt FROM legal_litigation
            WHERE case_type IS NOT NULL AND case_type != ''
            GROUP BY case_type ORDER BY cnt DESC
        """).fetchall()
        litigation_type_json = json.dumps([dict(r) for r in litigation_type_rows])

    ctx = _legal_ctx(request, **data,
                      contract_status_json=contract_status_json,
                      contract_type_json=contract_type_json,
                      contract_value_json=contract_value_json,
                      compliance_status_json=compliance_status_json,
                      litigation_status_json=litigation_status_json,
                      litigation_type_json=litigation_type_json)
    return render(request, 'legal_dashboard.html', ctx)


@dept_required(_LEGAL_DEPT_KEYS)
def legal_contract_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('contract_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        contracts = list_contracts(conn, status=status_f or None,
                                   contract_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_contract(
                    conn,
                    title=request.POST.get('title', ''),
                    counterparty=request.POST.get('counterparty', ''),
                    contract_type=request.POST.get('contract_type', ''),
                    value=float(request.POST.get('value', 0) or 0),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    owner=request.POST.get('owner', ''),
                    status=request.POST.get('status', 'Draft'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('legal_contract_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                contracts = list_contracts(conn, status=status_f or None,
                                           contract_type=type_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'legal_contracts', [
            ('title', 'Title'), ('counterparty', 'Party'), ('contract_type', 'Type'),
            ('value', 'Value'), ('start_date', 'Start Date'),
            ('end_date', 'End Date'), ('owner', 'Owner'), ('status', 'Status'),
        ], contracts)

    return render(request, 'legal_contract_list.html', _legal_ctx(
        request, contracts=contracts, status_filter=status_f, type_filter=type_f,
        search=search, contract_statuses=CONTRACT_STATUSES, contract_types=CONTRACT_TYPES,
        error=error, success=success,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_contract_detail(request, contract_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    contract = None
    try:
        contract = get_contract(conn, contract_id)
        if not contract:
            return redirect('legal_contract_list')
        if request.method == 'POST' and can_edit:
            try:
                update_contract(
                    conn, contract_id,
                    title=request.POST.get('title', ''),
                    counterparty=request.POST.get('counterparty', ''),
                    contract_type=request.POST.get('contract_type', ''),
                    value=float(request.POST.get('value', 0) or 0),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    owner=request.POST.get('owner', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Contract updated.'
                contract = get_contract(conn, contract_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'legal_contract_detail.html', _legal_ctx(
        request, contract=contract, can_edit=can_edit,
        contract_statuses=CONTRACT_STATUSES, contract_types=CONTRACT_TYPES,
        error=error, success=success,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_compliance_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        items = list_compliance(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_compliance(
                    conn,
                    requirement=request.POST.get('requirement', ''),
                    regulation=request.POST.get('regulation', ''),
                    owner=request.POST.get('owner', ''),
                    due_date=request.POST.get('due_date', ''),
                    status=request.POST.get('status', 'Pending'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('legal_compliance_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                items = list_compliance(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'legal_compliance', [
            ('requirement', 'Requirement'), ('regulation', 'Regulation'),
            ('owner', 'Owner'), ('due_date', 'Due Date'), ('status', 'Status'),
        ], items)

    return render(request, 'legal_compliance_list.html', _legal_ctx(
        request, items=items, status_filter=status_f, search=search,
        compliance_statuses=COMPLIANCE_STATUSES, error=error, success=success,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_compliance_detail(request, item_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    item = None
    try:
        item = get_compliance_item(conn, item_id)
        if not item:
            return redirect('legal_compliance_list')
        if request.method == 'POST' and can_edit:
            try:
                update_compliance(
                    conn, item_id,
                    requirement=request.POST.get('requirement', ''),
                    regulation=request.POST.get('regulation', ''),
                    owner=request.POST.get('owner', ''),
                    due_date=request.POST.get('due_date', ''),
                    completed_date=request.POST.get('completed_date', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Item updated.'
                item = get_compliance_item(conn, item_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'legal_compliance_detail.html', _legal_ctx(
        request, item=item, can_edit=can_edit,
        compliance_statuses=COMPLIANCE_STATUSES, error=error, success=success,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_litigation_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('case_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        cases = list_litigation(conn, status=status_f or None,
                                case_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_litigation(
                    conn,
                    case_name=request.POST.get('case_name', ''),
                    opposing_party=request.POST.get('opposing_party', ''),
                    court=request.POST.get('court', ''),
                    case_type=request.POST.get('case_type', ''),
                    filed_date=request.POST.get('filed_date', ''),
                    status=request.POST.get('status', 'Open'),
                    outcome=request.POST.get('outcome', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('legal_litigation_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                cases = list_litigation(conn, status=status_f or None,
                                        case_type=type_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'legal_litigation', [
            ('case_name', 'Case Name'), ('opposing_party', 'Opposing Party'),
            ('case_type', 'Type'), ('filed_date', 'Filed Date'),
            ('status', 'Status'), ('outcome', 'Outcome'),
        ], cases)

    return render(request, 'legal_litigation_list.html', _legal_ctx(
        request, cases=cases, status_filter=status_f, type_filter=type_f,
        search=search, litigation_statuses=LITIGATION_STATUSES,
        litigation_types=LITIGATION_TYPES, error=error, success=success,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_litigation_detail(request, case_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    case = None
    try:
        case = get_litigation_case(conn, case_id)
        if not case:
            return redirect('legal_litigation_list')
        if request.method == 'POST' and can_edit:
            try:
                update_litigation(
                    conn, case_id,
                    case_name=request.POST.get('case_name', ''),
                    opposing_party=request.POST.get('opposing_party', ''),
                    court=request.POST.get('court', ''),
                    case_type=request.POST.get('case_type', ''),
                    filed_date=request.POST.get('filed_date', ''),
                    status=request.POST.get('status', ''),
                    outcome=request.POST.get('outcome', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Case updated.'
                case = get_litigation_case(conn, case_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'legal_litigation_detail.html', _legal_ctx(
        request, case=case, can_edit=can_edit,
        litigation_statuses=LITIGATION_STATUSES, litigation_types=LITIGATION_TYPES,
        error=error, success=success,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_ip_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_ip(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_ip(
                    conn,
                    title=request.POST.get('title', ''),
                    ip_type=request.POST.get('ip_type', ''),
                    registration_no=request.POST.get('registration_no', ''),
                    jurisdiction=request.POST.get('jurisdiction', ''),
                    filed_date=request.POST.get('filed_date', ''),
                    expiry_date=request.POST.get('expiry_date', ''),
                    status=request.POST.get('status', 'Pending'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('legal_ip_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_ip(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'legal_ip_list.html', _legal_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=IP_STATUSES, ip_types=IP_TYPES, error=error,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_employment_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_employment(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_employment(
                    conn,
                    matter=request.POST.get('matter', ''),
                    employee=request.POST.get('employee', ''),
                    matter_type=request.POST.get('matter_type', ''),
                    owner=request.POST.get('owner', ''),
                    opened_date=request.POST.get('opened_date', ''),
                    closed_date=request.POST.get('closed_date', ''),
                    status=request.POST.get('status', 'Open'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('legal_employment_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_employment(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'legal_employment_list.html', _legal_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=EMPLOYMENT_STATUSES, matter_types=EMPLOYMENT_MATTER_TYPES, error=error,
    ))


@dept_required(_LEGAL_DEPT_KEYS)
def legal_governance_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_governance(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_governance(
                    conn,
                    item=request.POST.get('item', ''),
                    category=request.POST.get('category', ''),
                    owner=request.POST.get('owner', ''),
                    ref_date=request.POST.get('ref_date', ''),
                    reference=request.POST.get('reference', ''),
                    status=request.POST.get('status', 'Active'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('legal_governance_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_governance(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'legal_governance_list.html', _legal_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=GOVERNANCE_STATUSES, categories=GOVERNANCE_CATEGORIES, error=error,
    ))


