"""Views: Workforce Analytics & Headcount Planning."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..workforce_analytics_core import (
    ensure_workforce_columns, ensure_headcount_plan_table,
    set_employment_dates, get_headcount_summary, get_headcount_trend,
    create_headcount_plan, get_plan_vs_actual,
    EMPLOYMENT_STATUSES,
)
from ..personnel_core import list_people, load_depts

log = get_logger(__name__)

_WORKFORCE_DEPT_KEYS = {'personnel'}


def _workforce_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'employment_statuses': EMPLOYMENT_STATUSES,
    }
    ctx.update(extra)
    return ctx


def _ensure_tables(conn):
    ensure_workforce_columns(conn)
    ensure_headcount_plan_table(conn)


@dept_required(_WORKFORCE_DEPT_KEYS)
def workforce_analytics(request):
    conn = get_db_connection()
    try:
        _ensure_tables(conn)
        summary = get_headcount_summary(conn)
        trend = get_headcount_trend(conn, months=12)
        plan_vs_actual = get_plan_vs_actual(conn)
    finally:
        conn.close()
    return render(request, 'workforce_analytics.html', _workforce_ctx(
        request, summary=summary, trend=trend, plan_vs_actual=plan_vs_actual,
    ))


@dept_required(_WORKFORCE_DEPT_KEYS, write_redirect='workforce_analytics')
def headcount_plan_new(request):
    conn = get_db_connection()
    error = None
    try:
        _ensure_tables(conn)
        depts = load_depts(conn)
        if request.method == 'POST':
            try:
                create_headcount_plan(
                    conn, int(request.POST['dept_id']),
                    int(request.POST.get('target_headcount') or 0),
                    request.POST.get('target_date', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('workforce_analytics')
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'headcount_plan_new.html', _workforce_ctx(
        request, depts=depts, error=error,
    ))


@dept_required(_WORKFORCE_DEPT_KEYS, write_redirect='workforce_analytics')
def employee_employment_dates(request, people_id):
    conn = get_db_connection()
    error = success = None
    try:
        _ensure_tables(conn)
        people = list_people(conn)
        person = next((p for p in people if p['id'] == people_id), None)
        if not person:
            return redirect('workforce_analytics')

        if request.method == 'POST':
            try:
                set_employment_dates(
                    conn, people_id,
                    request.POST.get('hire_date', '').strip(),
                    termination_date=request.POST.get('termination_date', '').strip() or None,
                    employment_status=request.POST.get('employment_status', 'active'),
                )
                conn.commit()
                success = 'Employment dates updated.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'employee_employment_dates.html', _workforce_ctx(
        request, person=person, error=error, success=success,
    ))
