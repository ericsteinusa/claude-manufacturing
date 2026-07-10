"""Views: Skills Matrix & Competency Gap Analysis."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..skills_matrix_core import (
    ensure_skills_matrix_tables, list_skills, create_skill,
    list_distinct_job_titles, list_job_requirements,
    create_job_requirement, delete_job_requirement, get_org_gap_summary,
    get_employee_gap_report, upsert_employee_skill, SKILL_LEVEL_LABELS,
)

log = get_logger(__name__)

_SKILLS_DEPT_KEYS = {'personnel'}


def _skills_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'skill_level_choices': list(SKILL_LEVEL_LABELS.items()),
    }
    ctx.update(extra)
    return ctx


@dept_required(_SKILLS_DEPT_KEYS)
def skill_list(request):
    conn = get_db_connection()
    try:
        ensure_skills_matrix_tables(conn)
        skills = list_skills(conn, search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'skill_list.html', _skills_ctx(
        request, skills=skills, q=request.GET.get('q', ''),
    ))


@dept_required(_SKILLS_DEPT_KEYS, write_redirect='skill_list')
def skill_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_skills_matrix_tables(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    create_skill(
                        conn, name,
                        category=request.POST.get('category', '').strip(),
                        description=request.POST.get('description', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('skill_list')
                except ValueError as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'skill_new.html', _skills_ctx(request, error=error))


@dept_required(_SKILLS_DEPT_KEYS, write_redirect='skill_list')
def skill_requirements(request):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_skills_matrix_tables(conn)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add':
                    create_job_requirement(
                        conn,
                        job_title=request.POST.get('job_title', '').strip(),
                        skill_id=int(request.POST['skill_id']),
                        required_level=int(request.POST.get('required_level', 1)),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Requirement added.'
                elif action == 'delete':
                    delete_job_requirement(conn, int(request.POST['req_id']))
                    conn.commit()
                    success = 'Requirement removed.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        requirements = list_job_requirements(conn)
        job_titles = list_distinct_job_titles(conn)
        skills = list_skills(conn)
    finally:
        conn.close()

    return render(request, 'skill_requirements.html', _skills_ctx(
        request, requirements=requirements, job_titles=job_titles,
        skills=skills, error=error, success=success,
    ))


@dept_required(_SKILLS_DEPT_KEYS)
def skills_matrix_summary(request):
    conn = get_db_connection()
    try:
        ensure_skills_matrix_tables(conn)
        summary = get_org_gap_summary(conn)
    finally:
        conn.close()
    return render(request, 'skills_matrix_summary.html', _skills_ctx(
        request, summary=summary,
    ))


@dept_required(_SKILLS_DEPT_KEYS, write_redirect='skills_matrix_summary')
def employee_gap_detail(request, people_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_skills_matrix_tables(conn)
        if request.method == 'POST':
            try:
                upsert_employee_skill(
                    conn, people_id,
                    skill_id=int(request.POST['skill_id']),
                    level=int(request.POST.get('level', 1)),
                    certified_date=request.POST.get('certified_date') or None,
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Skill level recorded.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        try:
            report = get_employee_gap_report(conn, people_id)
        except ValueError:
            return redirect('skills_matrix_summary')
        skills = list_skills(conn)
    finally:
        conn.close()

    return render(request, 'employee_gap_detail.html', _skills_ctx(
        request, report=report, skills=skills, error=error, success=success,
    ))
