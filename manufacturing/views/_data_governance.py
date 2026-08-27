"""Views: Data Governance / GDPR tooling admin (data_governance_core.py).

Cross-departmental, PII-wide capability (erasure and export touch a person
regardless of which department they belong to), so this is gated like the
other Admin-sidebar pages (User Roles, Approval Rules, Webhooks) — full-
access roles only.
"""
import json

from django.http import HttpResponse
from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..log_utils import get_logger
from ..accounts import _ROLE_ADMIN_ROLES
from ..personnel_core import list_people, get_person
from ..data_governance_core import (
    ensure_data_governance_tables,
    anonymize_person,
    list_erasure_log,
    export_person_data,
    create_retention_policy,
    list_retention_policies,
    get_retention_policy,
    update_retention_policy,
    delete_retention_policy,
    find_retention_candidates,
)

log = get_logger(__name__)


def _is_admin(request) -> bool:
    return bool(request.session.get('user_email')) and (
        request.session.get('user_role') in _ROLE_ADMIN_ROLES)


def _dg_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def data_governance_dashboard(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        ensure_data_governance_tables(conn)

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'erase':
                    person_id = int(request.POST.get('person_id'))
                    reason = request.POST.get('reason', '').strip()
                    anonymize_person(
                        conn, person_id, request.session.get('user_email', ''),
                        reason=reason,
                    )
                    conn.commit()
                    success = 'Person anonymized.'
                elif action == 'add_policy':
                    create_retention_policy(
                        conn,
                        name=request.POST.get('name', '').strip(),
                        months_after_termination=int(
                            request.POST.get('months_after_termination') or 0),
                    )
                    conn.commit()
                    success = 'Retention policy created.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        people = list_people(conn, search=search) if search else []
        erasure_log = list_erasure_log(conn)
        policies = list_retention_policies(conn)
        for p in policies:
            p['candidate_count'] = len(find_retention_candidates(conn, p))
    finally:
        conn.close()

    return render(request, 'data_governance_dashboard.html', _dg_ctx(
        request, people=people, search=search, erasure_log=erasure_log,
        policies=policies, error=error, success=success,
    ))


def data_governance_export(request, person_id):
    """Subject-access export — download everything on file about one
    person as a single JSON file."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    conn = get_db_connection()
    try:
        person = get_person(conn, person_id)
        if not person:
            return redirect('data_governance_dashboard')
        data = export_person_data(conn, person_id)
    finally:
        conn.close()

    body = json.dumps(data, indent=2, default=str)
    resp = HttpResponse(body, content_type='application/json')
    resp['Content-Disposition'] = (
        f'attachment; filename="person-{person_id}-data-export.json"'
    )
    return resp


def retention_policy_edit(request, policy_id):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    conn = get_db_connection()
    try:
        policy = get_retention_policy(conn, policy_id)
        if not policy:
            return redirect('data_governance_dashboard')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action == 'update':
                update_retention_policy(
                    conn, policy_id,
                    name=request.POST.get('name', '').strip(),
                    months_after_termination=int(
                        request.POST.get('months_after_termination') or 0),
                )
                conn.commit()
            elif action == 'toggle_active':
                update_retention_policy(
                    conn, policy_id, is_active=not policy['is_active'])
                conn.commit()
            elif action == 'delete':
                delete_retention_policy(conn, policy_id)
                conn.commit()
                return redirect('data_governance_dashboard')
            return redirect('data_governance_dashboard')
    finally:
        conn.close()

    return render(request, 'retention_policy_edit.html', _dg_ctx(
        request, policy=policy,
    ))
