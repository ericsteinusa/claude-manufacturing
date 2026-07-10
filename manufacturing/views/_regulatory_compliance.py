"""Views: Regulatory Compliance Templates (FDA, ISO)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..regulatory_compliance_core import (
    ensure_compliance_tables, seed_default_templates, list_templates,
    get_template, create_template, add_template_item, list_checklists,
    create_checklist, get_checklist, update_checklist_item, ITEM_STATUSES,
)

log = get_logger(__name__)

_COMPLIANCE_DEPT_KEYS = {'quality_assurance'}


def _compliance_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'item_statuses': ITEM_STATUSES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_COMPLIANCE_DEPT_KEYS)
def compliance_template_list(request):
    conn = get_db_connection()
    try:
        ensure_compliance_tables(conn)
        seed_default_templates(conn, created_by='system')
        conn.commit()
        templates = list_templates(conn)
    finally:
        conn.close()
    return render(request, 'compliance_template_list.html', _compliance_ctx(
        request, templates=templates,
    ))


@dept_required(_COMPLIANCE_DEPT_KEYS, write_redirect='compliance_template_list')
def compliance_template_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_compliance_tables(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    template_id = create_template(
                        conn, name, request.POST.get('standard', '').strip(),
                        description=request.POST.get('description', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('compliance_template_detail', template_id=template_id)
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'compliance_template_new.html', _compliance_ctx(request, error=error))


@dept_required(_COMPLIANCE_DEPT_KEYS, write_redirect='compliance_template_list')
def compliance_template_detail(request, template_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_compliance_tables(conn)
        template = get_template(conn, template_id)
        if not template:
            return redirect('compliance_template_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_item':
                    add_template_item(
                        conn, template_id,
                        request.POST.get('clause_ref', '').strip(),
                        request.POST.get('requirement_text', '').strip(),
                        category=request.POST.get('category', '').strip(),
                        sort_order=int(request.POST.get('sort_order') or 0),
                    )
                    conn.commit()
                    success = 'Requirement added.'
                elif action == 'create_checklist':
                    checklist_id = create_checklist(
                        conn, template_id,
                        request.POST.get('name', '').strip(),
                        owner=request.POST.get('owner', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('compliance_checklist_detail', checklist_id=checklist_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            template = get_template(conn, template_id)
    finally:
        conn.close()

    return render(request, 'compliance_template_detail.html', _compliance_ctx(
        request, template=template, error=error, success=success,
    ))


@dept_required(_COMPLIANCE_DEPT_KEYS)
def compliance_checklist_list(request):
    conn = get_db_connection()
    try:
        ensure_compliance_tables(conn)
        checklists = list_checklists(conn, status=request.GET.get('status') or None)
    finally:
        conn.close()
    return render(request, 'compliance_checklist_list.html', _compliance_ctx(
        request, checklists=checklists, status=request.GET.get('status', ''),
    ))


@dept_required(_COMPLIANCE_DEPT_KEYS, write_redirect='compliance_checklist_list')
def compliance_checklist_detail(request, checklist_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_compliance_tables(conn)
        checklist = get_checklist(conn, checklist_id)
        if not checklist:
            return redirect('compliance_checklist_list')

        if request.method == 'POST':
            try:
                update_checklist_item(
                    conn, int(request.POST['item_id']),
                    request.POST.get('status', 'not_started'),
                    evidence_notes=request.POST.get('evidence_notes', '').strip(),
                    completed_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Item updated.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            checklist = get_checklist(conn, checklist_id)
    finally:
        conn.close()

    return render(request, 'compliance_checklist_detail.html', _compliance_ctx(
        request, checklist=checklist, error=error, success=success,
    ))
