"""Views: Risk Management dashboard."""

import json

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..risk_core import (
    list_risk_register, create_risk_register,
    list_risk_assessments, create_risk_assessment,
    list_risk_insurance, create_risk_insurance,
    list_risk_continuity, create_risk_continuity,
    list_risk_audits, create_risk_audit,
    list_risk_kris, create_risk_kri,
    RISK_STATUSES, ASSESSMENT_STATUSES, INSURANCE_STATUSES,
    CONTINUITY_STATUSES, AUDIT_STATUSES, KRI_STATUSES,
)

log = get_logger(__name__)

_RISK_DEPT_KEYS = {'risk_management', 'legal'}


def _risk_ctx(request, **extra):
    return {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        **extra,
    }


def risk_dashboard(request):
    if not request.session.get('user_email'):
        return redirect('home')
    conn = get_db_connection()
    try:
        kpi_row = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM risk_register) AS total_risks,
                (SELECT COUNT(*) FROM risk_register
                 WHERE status NOT IN ('Closed','Mitigated')) AS open_risks,
                (SELECT COUNT(*) FROM risk_assessment) AS total_assessments,
                (SELECT COUNT(*) FROM risk_audit
                 WHERE status NOT IN ('Completed','Closed')) AS open_audits,
                (SELECT COUNT(*) FROM risk_insurance
                 WHERE status = 'Active') AS active_policies,
                (SELECT COUNT(*) FROM risk_continuity) AS continuity_plans
        """).fetchone()
        kpis = dict(kpi_row) if kpi_row else {}

        severity_rows = conn.execute("""
            SELECT severity, COUNT(*) AS cnt
            FROM risk_register
            WHERE severity IS NOT NULL
            GROUP BY severity ORDER BY cnt DESC
        """).fetchall()
        severity_json = json.dumps([dict(r) for r in severity_rows])

        status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM risk_register
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        reg_status_json = json.dumps([dict(r) for r in status_rows])

        level_rows = conn.execute("""
            SELECT risk_level, COUNT(*) AS cnt
            FROM risk_assessment
            WHERE risk_level IS NOT NULL
            GROUP BY risk_level ORDER BY cnt DESC
        """).fetchall()
        risk_level_json = json.dumps([dict(r) for r in level_rows])

        category_rows = conn.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM risk_register
            WHERE category IS NOT NULL
            GROUP BY category ORDER BY cnt DESC
            LIMIT 8
        """).fetchall()
        category_json = json.dumps([dict(r) for r in category_rows])

        kri_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM risk_kri
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        kri_status_json = json.dumps([dict(r) for r in kri_rows])

        audit_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM risk_audit
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        audit_status_json = json.dumps([dict(r) for r in audit_rows])

        recent_risks = [dict(r) for r in conn.execute("""
            SELECT id, risk, category, severity, status, owner
            FROM risk_register
            ORDER BY id DESC LIMIT 10
        """).fetchall()]

        recent_assessments = [dict(r) for r in conn.execute("""
            SELECT id, title, category, risk_level, status, owner
            FROM risk_assessment
            ORDER BY id DESC LIMIT 8
        """).fetchall()]
    finally:
        conn.close()

    return render(request, 'risk_dashboard.html', {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'kpis': kpis,
        'severity_json': severity_json,
        'reg_status_json': reg_status_json,
        'risk_level_json': risk_level_json,
        'category_json': category_json,
        'kri_status_json': kri_status_json,
        'audit_status_json': audit_status_json,
        'recent_risks': recent_risks,
        'recent_assessments': recent_assessments,
    })


@dept_required(_RISK_DEPT_KEYS)
def risk_register_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_risk_register(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_risk_register(
                    conn,
                    risk=request.POST.get('risk', ''),
                    category=request.POST.get('category', ''),
                    severity=request.POST.get('severity', ''),
                    response=request.POST.get('response', ''),
                    owner=request.POST.get('owner', ''),
                    target_date=request.POST.get('target_date', ''),
                    status=request.POST.get('status', 'Open'),
                    mitigation=request.POST.get('mitigation', ''),
                )
                conn.commit()
                return redirect('risk_register_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_risk_register(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'risk_register_list.html', _risk_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=RISK_STATUSES, error=error,
    ))


@dept_required(_RISK_DEPT_KEYS)
def risk_assessment_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_risk_assessments(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_risk_assessment(
                    conn,
                    title=request.POST.get('title', ''),
                    category=request.POST.get('category', ''),
                    likelihood=request.POST.get('likelihood', ''),
                    impact=request.POST.get('impact', ''),
                    risk_level=request.POST.get('risk_level', ''),
                    owner=request.POST.get('owner', ''),
                    assessed_date=request.POST.get('assessed_date', ''),
                    status=request.POST.get('status', 'Identified'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('risk_assessment_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_risk_assessments(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'risk_assessment_list.html', _risk_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=ASSESSMENT_STATUSES, error=error,
    ))


@dept_required(_RISK_DEPT_KEYS)
def risk_insurance_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_risk_insurance(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_risk_insurance(
                    conn,
                    policy=request.POST.get('policy', ''),
                    insurer=request.POST.get('insurer', ''),
                    policy_type=request.POST.get('policy_type', ''),
                    coverage=float(request.POST.get('coverage', 0) or 0),
                    premium=float(request.POST.get('premium', 0) or 0),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    status=request.POST.get('status', 'Active'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('risk_insurance_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_risk_insurance(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'risk_insurance_list.html', _risk_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=INSURANCE_STATUSES, error=error,
    ))


@dept_required(_RISK_DEPT_KEYS)
def risk_continuity_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_risk_continuity(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_risk_continuity(
                    conn,
                    plan=request.POST.get('plan', ''),
                    scope=request.POST.get('scope', ''),
                    criticality=request.POST.get('criticality', ''),
                    owner=request.POST.get('owner', ''),
                    last_tested=request.POST.get('last_tested', ''),
                    next_test=request.POST.get('next_test', ''),
                    status=request.POST.get('status', 'Draft'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('risk_continuity_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_risk_continuity(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'risk_continuity_list.html', _risk_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=CONTINUITY_STATUSES, error=error,
    ))


@dept_required(_RISK_DEPT_KEYS)
def risk_audit_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_risk_audits(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_risk_audit(
                    conn,
                    audit=request.POST.get('audit', ''),
                    framework=request.POST.get('framework', ''),
                    auditor=request.POST.get('auditor', ''),
                    scheduled_date=request.POST.get('scheduled_date', ''),
                    completed_date=request.POST.get('completed_date', ''),
                    finding=request.POST.get('finding', ''),
                    status=request.POST.get('status', 'Scheduled'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('risk_audit_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_risk_audits(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'risk_audit_list.html', _risk_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=AUDIT_STATUSES, error=error,
    ))


@dept_required(_RISK_DEPT_KEYS)
def risk_kri_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_risk_kris(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_risk_kri(
                    conn,
                    indicator=request.POST.get('indicator', ''),
                    category=request.POST.get('category', ''),
                    threshold=request.POST.get('threshold', ''),
                    current_value=request.POST.get('current_value', ''),
                    owner=request.POST.get('owner', ''),
                    measured_date=request.POST.get('measured_date', ''),
                    status=request.POST.get('status', 'Normal'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('risk_kri_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_risk_kris(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'risk_kri_list.html', _risk_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=KRI_STATUSES, error=error,
    ))
