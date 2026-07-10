"""Views: Applicant Tracking / Recruiting (ATS)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..ats_core import (
    ensure_ats_tables, list_requisitions, get_requisition, create_requisition,
    update_requisition_status, list_candidates, get_candidate, create_candidate,
    list_applications, get_application, create_application, advance_stage,
    convert_to_employee, get_ats_dashboard, REQUISITION_STATUSES, STAGES,
)
from ..personnel_core import load_depts

log = get_logger(__name__)

_ATS_DEPT_KEYS = {'personnel'}


def _ats_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'requisition_statuses': REQUISITION_STATUSES,
        'stages': STAGES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_ATS_DEPT_KEYS)
def ats_dashboard(request):
    conn = get_db_connection()
    try:
        ensure_ats_tables(conn)
        dashboard = get_ats_dashboard(conn)
        requisitions = list_requisitions(conn, status='open')
    finally:
        conn.close()
    return render(request, 'ats_dashboard.html', _ats_ctx(
        request, dashboard=dashboard, requisitions=requisitions,
    ))


@dept_required(_ATS_DEPT_KEYS)
def ats_requisition_list(request):
    conn = get_db_connection()
    try:
        ensure_ats_tables(conn)
        requisitions = list_requisitions(conn, status=request.GET.get('status') or None,
                                         search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'ats_requisition_list.html', _ats_ctx(
        request, requisitions=requisitions, status=request.GET.get('status', ''),
        q=request.GET.get('q', ''),
    ))


@dept_required(_ATS_DEPT_KEYS, write_redirect='ats_requisition_list')
def ats_requisition_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_ats_tables(conn)
        depts = load_depts(conn)
        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            if not title:
                error = 'Title is required.'
            else:
                try:
                    req_id = create_requisition(
                        conn, title,
                        int(request.POST['dept_id']) if request.POST.get('dept_id') else None,
                        description=request.POST.get('description', '').strip(),
                        target_hire_date=request.POST.get('target_hire_date') or None,
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('ats_requisition_detail', req_id=req_id)
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'ats_requisition_new.html', _ats_ctx(
        request, depts=depts, error=error,
    ))


@dept_required(_ATS_DEPT_KEYS, write_redirect='ats_requisition_list')
def ats_requisition_detail(request, req_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_ats_tables(conn)
        requisition = get_requisition(conn, req_id)
        if not requisition:
            return redirect('ats_requisition_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'set_status':
                    update_requisition_status(conn, req_id, request.POST.get('status', ''))
                    conn.commit()
                    success = 'Status updated.'
                elif action == 'apply':
                    create_application(
                        conn, req_id, int(request.POST['candidate_id']),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Candidate applied to this requisition.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            requisition = get_requisition(conn, req_id)

        applications = list_applications(conn, requisition_id=req_id)
        candidates = list_candidates(conn)
    finally:
        conn.close()

    return render(request, 'ats_requisition_detail.html', _ats_ctx(
        request, requisition=requisition, applications=applications,
        candidates=candidates, error=error, success=success,
    ))


@dept_required(_ATS_DEPT_KEYS)
def ats_candidate_list(request):
    conn = get_db_connection()
    try:
        ensure_ats_tables(conn)
        candidates = list_candidates(conn, search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'ats_candidate_list.html', _ats_ctx(
        request, candidates=candidates, q=request.GET.get('q', ''),
    ))


@dept_required(_ATS_DEPT_KEYS, write_redirect='ats_candidate_list')
def ats_candidate_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_ats_tables(conn)
        if request.method == 'POST':
            try:
                candidate_id = create_candidate(
                    conn, request.POST.get('first_name', '').strip(),
                    request.POST.get('last_name', '').strip(),
                    email=request.POST.get('email', '').strip(),
                    phone=request.POST.get('phone', '').strip(),
                    resume_notes=request.POST.get('resume_notes', '').strip(),
                    source=request.POST.get('source', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('ats_candidate_detail', candidate_id=candidate_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'ats_candidate_new.html', _ats_ctx(request, error=error))


@dept_required(_ATS_DEPT_KEYS, write_redirect='ats_candidate_list')
def ats_candidate_detail(request, candidate_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_ats_tables(conn)
        candidate = get_candidate(conn, candidate_id)
        if not candidate:
            return redirect('ats_candidate_list')

        if request.method == 'POST':
            try:
                create_application(
                    conn, int(request.POST['requisition_id']), candidate_id,
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Applied to requisition.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        applications = list_applications(conn, candidate_id=candidate_id)
        open_requisitions = list_requisitions(conn, status='open')
    finally:
        conn.close()

    return render(request, 'ats_candidate_detail.html', _ats_ctx(
        request, candidate=candidate, applications=applications,
        open_requisitions=open_requisitions, error=error, success=success,
    ))


@dept_required(_ATS_DEPT_KEYS, write_redirect='ats_candidate_list')
def ats_application_detail(request, app_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_ats_tables(conn)
        application = get_application(conn, app_id)
        if not application:
            return redirect('ats_candidate_list')
        depts = load_depts(conn)

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'advance':
                    advance_stage(
                        conn, app_id, request.POST.get('stage', ''),
                        changed_by=request.session.get('user_email', ''),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Stage updated.'
                elif action == 'hire':
                    convert_to_employee(
                        conn, app_id, request.POST.get('hire_date', '').strip(),
                        dept_id=int(request.POST['dept_id']) if request.POST.get('dept_id') else None,
                        job_title=request.POST.get('job_title', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Candidate hired and added to Personnel.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            application = get_application(conn, app_id)
    finally:
        conn.close()

    return render(request, 'ats_application_detail.html', _ats_ctx(
        request, application=application, depts=depts, error=error, success=success,
    ))
