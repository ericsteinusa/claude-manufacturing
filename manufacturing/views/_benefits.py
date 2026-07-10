"""Views: Benefits Management."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..benefits_core import (
    ensure_benefits_tables, list_plans, get_plan, create_plan, update_plan,
    list_enrollments, enroll_employee, waive_enrollment, terminate_enrollment,
    get_employee_benefits, get_benefits_dashboard, PLAN_TYPES, TIERS,
)
from ..personnel_core import list_people

log = get_logger(__name__)

_BENEFITS_DEPT_KEYS = {'personnel'}


def _benefits_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'plan_types': PLAN_TYPES,
        'tiers': TIERS,
    }
    ctx.update(extra)
    return ctx


@dept_required(_BENEFITS_DEPT_KEYS)
def benefits_dashboard(request):
    conn = get_db_connection()
    try:
        ensure_benefits_tables(conn)
        dashboard = get_benefits_dashboard(conn)
        plans = list_plans(conn)
    finally:
        conn.close()
    return render(request, 'benefits_dashboard.html', _benefits_ctx(
        request, dashboard=dashboard, plans=plans,
    ))


@dept_required(_BENEFITS_DEPT_KEYS, write_redirect='benefits_dashboard')
def benefit_plan_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_benefits_tables(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    plan_id = create_plan(
                        conn, name, request.POST.get('plan_type', 'Health'),
                        carrier=request.POST.get('carrier', '').strip(),
                        description=request.POST.get('description', '').strip(),
                        employee_cost_per_pay=float(request.POST.get('employee_cost_per_pay') or 0),
                        employer_cost_per_pay=float(request.POST.get('employer_cost_per_pay') or 0),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('benefit_plan_detail', plan_id=plan_id)
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'benefit_plan_new.html', _benefits_ctx(request, error=error))


@dept_required(_BENEFITS_DEPT_KEYS, write_redirect='benefits_dashboard')
def benefit_plan_detail(request, plan_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_benefits_tables(conn)
        plan = get_plan(conn, plan_id)
        if not plan:
            return redirect('benefits_dashboard')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'enroll':
                    enroll_employee(
                        conn, int(request.POST['people_id']), plan_id,
                        request.POST.get('tier', TIERS[0]),
                        dependents_count=int(request.POST.get('dependents_count') or 0),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Employee enrolled.'
                elif action == 'waive':
                    waive_enrollment(conn, int(request.POST['enrollment_id']))
                    conn.commit()
                    success = 'Enrollment waived.'
                elif action == 'terminate':
                    terminate_enrollment(conn, int(request.POST['enrollment_id']))
                    conn.commit()
                    success = 'Enrollment terminated.'
                elif action == 'toggle_active':
                    update_plan(conn, plan_id, is_active=0 if plan['is_active'] else 1)
                    conn.commit()
                    success = 'Plan status updated.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            plan = get_plan(conn, plan_id)

        enrollments = list_enrollments(conn, plan_id=plan_id)
        people = list_people(conn)
    finally:
        conn.close()

    return render(request, 'benefit_plan_detail.html', _benefits_ctx(
        request, plan=plan, enrollments=enrollments, people=people,
        error=error, success=success,
    ))


@dept_required(_BENEFITS_DEPT_KEYS)
def employee_benefits(request, people_id):
    conn = get_db_connection()
    try:
        ensure_benefits_tables(conn)
        result = get_employee_benefits(conn, people_id)
        people = list_people(conn)
        person = next((p for p in people if p['id'] == people_id), None)
    finally:
        conn.close()
    if not person:
        return redirect('benefits_dashboard')
    return render(request, 'employee_benefits.html', _benefits_ctx(
        request, result=result, person=person,
    ))
