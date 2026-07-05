"""Views: quality domain."""

import json

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..csv_export import csv_response

from ..quality_core import (
    NCR_STATUSES, NCR_SOURCES, NCR_SEVERITIES, NCR_DISPOSITIONS,
    CAPA_STATUSES, CAPA_TYPES,
    AUDIT_STATUSES, AUDIT_TYPES,
    SUPPLIER_STATUSES, SUPPLIER_RATINGS,
    INSP_RESULTS, DEFECT_SEVERITIES,
    get_dashboard_counts,
    list_ncrs, get_ncr, create_ncr, update_ncr, close_ncr,
    list_capas, get_capa, create_capa, update_capa, close_capa,
    list_audits, get_audit, create_audit, update_audit, complete_audit,
    list_supplier_quality, get_supplier_quality,
    create_supplier_quality, update_supplier_quality,
    next_insp_number, list_inspections, get_inspection, create_inspection,
    update_inspection_result, get_defects, log_defect, resolve_defect,
    load_products_for_qa, load_work_orders_for_qa,
    get_qa_reports,
    get_defect_pareto, get_ncr_severity_trend,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Quality Assurance (web)
# ---------------------------------------------------------------------------

_QA_DEPT_KEYS = {'quality_assurance', 'production', 'purchasing'}


def _qa_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_QA_DEPT_KEYS)
def qa_dashboard(request):
    conn = get_db_connection()
    try:
        counts = get_dashboard_counts(conn)
        defect_pareto = get_defect_pareto(conn)
        ncr_trend = get_ncr_severity_trend(conn)
    finally:
        conn.close()
    return render(request, 'qa_dashboard.html', _qa_ctx(
        request, counts=counts,
        defect_pareto_json=json.dumps(defect_pareto),
        ncr_trend_json=json.dumps(ncr_trend),
    ))


# --- NCR ---

@dept_required(_QA_DEPT_KEYS)
def qa_ncr_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    ncrs = []
    try:
        ncrs = list_ncrs(conn, status=status_filter or None,
                         search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_ncr(
                    conn,
                    title=request.POST.get('title', ''),
                    source=request.POST.get('source', ''),
                    severity=request.POST.get('severity', ''),
                    product=request.POST.get('product', ''),
                    detected_date=request.POST.get('detected_date', ''),
                    disposition=request.POST.get('disposition', 'Pending'),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_ncr_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                ncrs = list_ncrs(conn, status=status_filter or None,
                                 search=search or None)
    finally:
        conn.close()
    return render(request, 'qa_ncr_list.html', _qa_ctx(
        request, ncrs=ncrs, status_filter=status_filter, search=search,
        ncr_statuses=NCR_STATUSES, ncr_sources=NCR_SOURCES,
        ncr_severities=NCR_SEVERITIES, ncr_dispositions=NCR_DISPOSITIONS,
        error=error, success=success,
    ))


@dept_required(_QA_DEPT_KEYS)
def qa_ncr_export(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        ncrs = list_ncrs(conn, status=status_filter or None,
                         search=search or None)
    finally:
        conn.close()

    return csv_response('ncrs.csv', [
        ('title', 'Title'), ('source', 'Source'), ('severity', 'Severity'),
        ('product', 'Product'), ('detected_date', 'Detected Date'),
        ('disposition', 'Disposition'), ('owner', 'Owner'),
        ('status', 'Status'), ('closed_date', 'Closed Date'),
    ], ncrs)


@dept_required(_QA_DEPT_KEYS)
def qa_ncr_detail(request, ncr_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    ncr = None
    try:
        ncr = get_ncr(conn, ncr_id)
        if not ncr:
            return redirect('qa_ncr_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'close':
                    close_ncr(conn, ncr_id)
                    success = 'NCR closed.'
                else:
                    update_ncr(
                        conn, ncr_id,
                        title=request.POST.get('title', ''),
                        source=request.POST.get('source', ''),
                        severity=request.POST.get('severity', ''),
                        product=request.POST.get('product', ''),
                        detected_date=request.POST.get('detected_date', ''),
                        disposition=request.POST.get('disposition', ''),
                        owner=request.POST.get('owner', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'NCR updated.'
                conn.commit()
                ncr = get_ncr(conn, ncr_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_ncr_detail.html', _qa_ctx(
        request, ncr=ncr, can_edit=can_edit,
        ncr_statuses=NCR_STATUSES, ncr_sources=NCR_SOURCES,
        ncr_severities=NCR_SEVERITIES, ncr_dispositions=NCR_DISPOSITIONS,
        error=error, success=success,
    ))


# --- CAPA ---

@dept_required(_QA_DEPT_KEYS)
def qa_capa_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    capas = []
    try:
        capas = list_capas(conn, status=status_filter or None,
                           search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_capa(
                    conn,
                    title=request.POST.get('title', ''),
                    capa_type=request.POST.get('capa_type', 'Corrective'),
                    ncr_ref=request.POST.get('ncr_ref', ''),
                    owner=request.POST.get('owner', ''),
                    due_date=request.POST.get('due_date', ''),
                    action_plan=request.POST.get('action_plan', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_capa_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                capas = list_capas(conn, status=status_filter or None,
                                   search=search or None)
    finally:
        conn.close()
    return render(request, 'qa_capa_list.html', _qa_ctx(
        request, capas=capas, status_filter=status_filter, search=search,
        capa_statuses=CAPA_STATUSES, capa_types=CAPA_TYPES,
        error=error, success=success,
    ))


@dept_required(_QA_DEPT_KEYS)
def qa_capa_detail(request, capa_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    capa = None
    try:
        capa = get_capa(conn, capa_id)
        if not capa:
            return redirect('qa_capa_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'close':
                    close_capa(conn, capa_id)
                    success = 'CAPA closed.'
                else:
                    update_capa(
                        conn, capa_id,
                        title=request.POST.get('title', ''),
                        capa_type=request.POST.get('capa_type', ''),
                        ncr_ref=request.POST.get('ncr_ref', ''),
                        owner=request.POST.get('owner', ''),
                        due_date=request.POST.get('due_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        status=request.POST.get('status', ''),
                        action_plan=request.POST.get('action_plan', ''),
                    )
                    success = 'CAPA updated.'
                conn.commit()
                capa = get_capa(conn, capa_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_capa_detail.html', _qa_ctx(
        request, capa=capa, can_edit=can_edit,
        capa_statuses=CAPA_STATUSES, capa_types=CAPA_TYPES,
        error=error, success=success,
    ))


# --- Audits ---

@dept_required(_QA_DEPT_KEYS)
def qa_audit_list(request):
    status_filter = request.GET.get('status', '').strip()
    conn = get_db_connection()
    error = success = None
    audits = []
    try:
        audits = list_audits(conn, status=status_filter or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_audit(
                    conn,
                    title=request.POST.get('title', ''),
                    audit_type=request.POST.get('audit_type', ''),
                    auditor=request.POST.get('auditor', ''),
                    scheduled_date=request.POST.get('scheduled_date', ''),
                    findings=request.POST.get('findings', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_audit_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                audits = list_audits(conn, status=status_filter or None)
    finally:
        conn.close()
    return render(request, 'qa_audit_list.html', _qa_ctx(
        request, audits=audits, status_filter=status_filter,
        audit_statuses=AUDIT_STATUSES, audit_types=AUDIT_TYPES,
        error=error, success=success,
    ))


@dept_required(_QA_DEPT_KEYS)
def qa_audit_detail(request, audit_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    audit = None
    try:
        audit = get_audit(conn, audit_id)
        if not audit:
            return redirect('qa_audit_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_audit(conn, audit_id,
                                   result=request.POST.get('result', ''),
                                   findings=request.POST.get('findings', ''))
                    success = 'Audit marked complete.'
                else:
                    update_audit(
                        conn, audit_id,
                        title=request.POST.get('title', ''),
                        audit_type=request.POST.get('audit_type', ''),
                        auditor=request.POST.get('auditor', ''),
                        scheduled_date=request.POST.get('scheduled_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        result=request.POST.get('result', ''),
                        status=request.POST.get('status', ''),
                        findings=request.POST.get('findings', ''),
                    )
                    success = 'Audit updated.'
                conn.commit()
                audit = get_audit(conn, audit_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_audit_detail.html', _qa_ctx(
        request, audit=audit, can_edit=can_edit,
        audit_statuses=AUDIT_STATUSES, audit_types=AUDIT_TYPES,
        error=error, success=success,
    ))


# --- Supplier Quality ---

@dept_required(_QA_DEPT_KEYS)
def qa_supplier_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    suppliers = []
    try:
        suppliers = list_supplier_quality(conn, status=status_filter or None,
                                          search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_supplier_quality(
                    conn,
                    supplier=request.POST.get('supplier', ''),
                    material=request.POST.get('material', ''),
                    rating=request.POST.get('rating', ''),
                    ppm=request.POST.get('ppm', ''),
                    last_audit=request.POST.get('last_audit', ''),
                    status=request.POST.get('status', 'Pending'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_supplier_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                suppliers = list_supplier_quality(conn, status=status_filter or None,
                                                  search=search or None)
    finally:
        conn.close()
    return render(request, 'qa_supplier_list.html', _qa_ctx(
        request, suppliers=suppliers, status_filter=status_filter, search=search,
        supplier_statuses=SUPPLIER_STATUSES, supplier_ratings=SUPPLIER_RATINGS,
        error=error, success=success,
    ))


@dept_required(_QA_DEPT_KEYS)
def qa_supplier_detail(request, sq_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    supplier = None
    try:
        supplier = get_supplier_quality(conn, sq_id)
        if not supplier:
            return redirect('qa_supplier_list')
        if request.method == 'POST' and can_edit:
            try:
                update_supplier_quality(
                    conn, sq_id,
                    supplier=request.POST.get('supplier', ''),
                    material=request.POST.get('material', ''),
                    rating=request.POST.get('rating', ''),
                    ppm=request.POST.get('ppm', ''),
                    last_audit=request.POST.get('last_audit', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                supplier = get_supplier_quality(conn, sq_id)
                success = 'Supplier quality record updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_supplier_detail.html', _qa_ctx(
        request, supplier=supplier, can_edit=can_edit,
        supplier_statuses=SUPPLIER_STATUSES, supplier_ratings=SUPPLIER_RATINGS,
        error=error, success=success,
    ))


# --- Inspections ---

@dept_required(_QA_DEPT_KEYS)
def qa_inspection_list(request):
    result_filter = request.GET.get('result', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    inspections = []
    products = []
    work_orders = []
    try:
        inspections = list_inspections(conn, result=result_filter or None,
                                       search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            products = load_products_for_qa(conn)
            work_orders = load_work_orders_for_qa(conn)
            try:
                pid_raw = request.POST.get('product_id', '')
                wid_raw = request.POST.get('wo_id', '')
                insp_num = next_insp_number(conn)
                create_inspection(
                    conn,
                    insp_number=insp_num,
                    product_id=int(pid_raw) if pid_raw else None,
                    wo_id=int(wid_raw) if wid_raw else None,
                    insp_date=request.POST.get('insp_date', ''),
                    inspector=request.POST.get('inspector', ''),
                    result=request.POST.get('result', 'pending'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_inspection_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                inspections = list_inspections(conn, result=result_filter or None,
                                               search=search or None)
        else:
            products = load_products_for_qa(conn)
            work_orders = load_work_orders_for_qa(conn)
    finally:
        conn.close()
    return render(request, 'qa_inspection_list.html', _qa_ctx(
        request, inspections=inspections, result_filter=result_filter,
        search=search, insp_results=INSP_RESULTS,
        products=products, work_orders=work_orders,
        error=error, success=success,
    ))


@dept_required(_QA_DEPT_KEYS)
def qa_inspection_detail(request, insp_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    inspection = None
    defects = []
    try:
        inspection = get_inspection(conn, insp_id)
        if not inspection:
            return redirect('qa_inspection_list')
        defects = get_defects(conn, insp_id)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action in ('passed', 'failed', 'on_hold', 'pending'):
                    update_inspection_result(conn, insp_id, action)
                    success = f'Inspection marked {action}.'
                elif action == 'log_defect':
                    log_defect(
                        conn, insp_id,
                        defect_type=request.POST.get('defect_type', ''),
                        severity=request.POST.get('severity', 'minor'),
                        description=request.POST.get('description', ''),
                        created_by=request.session.get('user_email', ''),
                    )
                    success = 'Defect logged.'
                elif action == 'resolve_defect':
                    did = int(request.POST.get('defect_id', 0))
                    resolve_defect(conn, did)
                    success = 'Defect resolved.'
                conn.commit()
                inspection = get_inspection(conn, insp_id)
                defects = get_defects(conn, insp_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_inspection_detail.html', _qa_ctx(
        request, inspection=inspection, defects=defects, can_edit=can_edit,
        defect_severities=DEFECT_SEVERITIES,
        error=error, success=success,
    ))


# --- QA Reports ---

@dept_required(_QA_DEPT_KEYS)
def qa_reports_view(request):
    conn = get_db_connection()
    try:
        data = get_qa_reports(conn)
    finally:
        conn.close()
    return render(request, 'qa_reports.html', _qa_ctx(request, **data))


