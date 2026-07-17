"""Views: Approval Rule admin (configures approval_workflow_core's rules).

Cross-departmental system configuration (rules apply across PO, requisition,
GL journal, cycle count, and document approvals), so this is gated like the
other Admin-sidebar pages (User Roles) rather than a single department —
full-access roles only, checked inline the same way user_roles() does it.
"""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..log_utils import get_logger
from ..accounts import _ROLE_ADMIN_ROLES, _get_all_roles
from ..menus import DASHBOARD_DEPARTMENTS
from ..approval_workflow_core import (
    ENTITY_TYPES,
    ensure_approval_tables,
    create_approval_rule,
    list_approval_rules,
    get_approval_rule,
    update_approval_rule,
    delete_approval_rule,
)

log = get_logger(__name__)


def _is_admin(request) -> bool:
    return bool(request.session.get('user_email')) and (
        request.session.get('user_role') in _ROLE_ADMIN_ROLES)


def _ar_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'entity_types': ENTITY_TYPES,
        'departments': DASHBOARD_DEPARTMENTS,
    }
    ctx.update(extra)
    return ctx


def approval_rule_list(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    entity_type = request.GET.get('entity_type', '').strip()
    conn = get_db_connection()
    try:
        ensure_approval_tables(conn)
        rules = list_approval_rules(
            conn, entity_type=entity_type or None, active_only=False)
    finally:
        conn.close()
    return render(request, 'approval_rule_list.html', _ar_ctx(
        request, rules=rules, entity_type=entity_type,
    ))


def approval_rule_new(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    error = None
    conn = get_db_connection()
    try:
        roles = _get_all_roles()
        if request.method == 'POST':
            entity_type = request.POST.get('entity_type', '').strip()
            approver_role = request.POST.get('approver_role', '').strip()
            try:
                rule_id = create_approval_rule(
                    conn, entity_type, approver_role,
                    seq=int(request.POST.get('seq') or 10),
                    dept_key=request.POST.get('dept_key', '').strip(),
                    threshold_amount=float(
                        request.POST.get('threshold_amount') or 0),
                    escalate_after_hours=float(
                        request.POST.get('escalate_after_hours') or 24),
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                return redirect('approval_rule_edit', rule_id=rule_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'approval_rule_new.html', _ar_ctx(
        request, roles=roles, error=error,
    ))


def approval_rule_edit(request, rule_id):
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_admin(request):
        return redirect('dashboard')

    error = success = None
    conn = get_db_connection()
    try:
        ensure_approval_tables(conn)
        rule = get_approval_rule(conn, rule_id)
        if not rule:
            return redirect('approval_rule_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'update':
                    update_approval_rule(
                        conn, rule_id,
                        entity_type=request.POST.get('entity_type', '').strip(),
                        dept_key=request.POST.get('dept_key', '').strip(),
                        threshold_amount=float(
                            request.POST.get('threshold_amount') or 0),
                        approver_role=request.POST.get(
                            'approver_role', '').strip(),
                        seq=int(request.POST.get('seq') or 10),
                        escalate_after_hours=float(
                            request.POST.get('escalate_after_hours') or 24),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Rule updated.'
                elif action == 'toggle_active':
                    update_approval_rule(
                        conn, rule_id, is_active=not rule['is_active'])
                    conn.commit()
                    success = 'Rule deactivated.' if rule['is_active'] else 'Rule activated.'
                elif action == 'delete':
                    delete_approval_rule(conn, rule_id)
                    conn.commit()
                    return redirect('approval_rule_list')
            except Exception as exc:
                conn.rollback()
                error = str(exc)
            rule = get_approval_rule(conn, rule_id)

        roles = _get_all_roles()
    finally:
        conn.close()

    return render(request, 'approval_rule_edit.html', _ar_ctx(
        request, rule=rule, roles=roles, error=error, success=success,
    ))
