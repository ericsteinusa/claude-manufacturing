"""Views: Termination process — termination records, exit interviews,
offboarding checklist tasks. Gated by dept_required('personnel'), same as
the rest of the Personnel department's manager-facing pages.
"""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..personnel_core import list_people

from ..termination_core import (
    TERM_TYPES, TERM_STATUSES, REHIRE_OPTIONS,
    EXIT_INTERVIEW_RECOMMEND_OPTIONS,
    OFFBOARD_STATUSES, OFFBOARD_DEFAULT_TASKS,
    list_terminations, get_termination, create_termination,
    list_exit_interviews, create_exit_interview,
    list_offboarding_tasks, create_offboarding_task, complete_offboarding_task,
)

log = get_logger(__name__)

_PERS_DEPT_KEYS = {'personnel'}


def _term_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_PERS_DEPT_KEYS)
def termination_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_terminations(conn, status=status_f or None, search=search or None)
        employees = list_people(conn)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                term_id = create_termination(
                    conn,
                    people_id=int(request.POST.get('people_id', 0) or 0),
                    termination_date=request.POST.get('termination_date', ''),
                    term_type=request.POST.get('term_type', ''),
                    reason=request.POST.get('reason', ''),
                    status=request.POST.get('status', 'Initiated'),
                    rehire_eligible=request.POST.get('rehire_eligible', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('termination_detail', term_id=term_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_terminations(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'termination_list.html', _term_ctx(
        request, rows=rows, employees=employees, status_filter=status_f,
        search=search, statuses=TERM_STATUSES, term_types=TERM_TYPES,
        rehire_options=REHIRE_OPTIONS, error=error,
    ))


@dept_required(_PERS_DEPT_KEYS)
def termination_detail(request, term_id):
    conn = get_db_connection()
    error = None
    try:
        term = get_termination(conn, term_id)
        if not term:
            return redirect('termination_list')
    finally:
        conn.close()
    return render(request, 'termination_detail.html', _term_ctx(
        request, term=term, statuses=TERM_STATUSES, error=error,
    ))


@dept_required(_PERS_DEPT_KEYS)
def exit_interview_list(request):
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        rows = list_exit_interviews(conn, search=search or None)
        employees = list_people(conn)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_exit_interview(
                    conn,
                    people_id=int(request.POST.get('people_id', 0) or 0),
                    interview_date=request.POST.get('interview_date', ''),
                    interviewer=request.POST.get('interviewer', ''),
                    reason_for_leaving=request.POST.get('reason_for_leaving', ''),
                    feedback=request.POST.get('feedback', ''),
                    would_recommend=request.POST.get('would_recommend', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('exit_interview_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_exit_interviews(conn, search=search or None)
    finally:
        conn.close()
    return render(request, 'exit_interview_list.html', _term_ctx(
        request, rows=rows, employees=employees, search=search,
        recommend_options=EXIT_INTERVIEW_RECOMMEND_OPTIONS, error=error,
    ))


@dept_required(_PERS_DEPT_KEYS)
def offboarding_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            action = request.POST.get('action')
            try:
                if action == 'complete':
                    complete_offboarding_task(
                        conn, int(request.POST.get('task_id', 0) or 0),
                        request.POST.get('completed_date', ''),
                    )
                else:
                    create_offboarding_task(
                        conn,
                        people_id=int(request.POST.get('people_id', 0) or 0),
                        task=request.POST.get('task', ''),
                        status=request.POST.get('status', 'Pending'),
                        due_date=request.POST.get('due_date', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        notes=request.POST.get('notes', ''),
                    )
                conn.commit()
                return redirect('offboarding_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
        rows = list_offboarding_tasks(conn, status=status_f or None, search=search or None)
        employees = list_people(conn)
    finally:
        conn.close()
    return render(request, 'offboarding_list.html', _term_ctx(
        request, rows=rows, employees=employees, status_filter=status_f,
        search=search, statuses=OFFBOARD_STATUSES,
        default_tasks=OFFBOARD_DEFAULT_TASKS, error=error,
    ))
