"""Views: inventory cycle-count workflow (P1-D)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..cycle_count_core import (
    GROUP_BY_OPTIONS,
    ensure_cycle_count_tables, list_group_values, generate_sheet,
    get_cycle_count, get_cycle_count_lines, list_cycle_counts,
    enter_counts, decide_cycle_count,
)
from ..approval_workflow_core import get_entity_approval_status

log = get_logger(__name__)

_CC_DEPT_KEYS = {'production', 'engineering', 'maintenance', 'purchasing'}


def _cc_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_CC_DEPT_KEYS)
def cc_list(request):
    status = request.GET.get('status') or None
    conn = get_db_connection()
    try:
        ensure_cycle_count_tables(conn)
        counts = list_cycle_counts(conn, status=status)
    finally:
        conn.close()
    return render(request, 'cc_list.html', _cc_ctx(
        request, counts=counts, status=status,
    ))


@dept_required(_CC_DEPT_KEYS, write_redirect='cc_list')
def cc_new(request):
    group_by = request.GET.get('group_by', 'bin')
    if group_by not in GROUP_BY_OPTIONS:
        group_by = 'bin'

    conn = get_db_connection()
    error = None
    try:
        ensure_cycle_count_tables(conn)
        group_values = list_group_values(conn, group_by)
        if request.method == 'POST':
            post_group_by = request.POST.get('group_by', 'bin')
            group_value = request.POST.get('group_value', '').strip()
            if post_group_by not in GROUP_BY_OPTIONS or not group_value:
                error = 'Select a group and a value.'
            else:
                try:
                    count_id = generate_sheet(
                        conn, post_group_by, group_value,
                        request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('cc_detail', count_id=count_id)
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()

    return render(request, 'cc_new.html', _cc_ctx(
        request, group_by=group_by, group_values=group_values,
        group_by_options=GROUP_BY_OPTIONS, error=error,
    ))


@dept_required(_CC_DEPT_KEYS, write_redirect='cc_list')
def cc_detail(request, count_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_cycle_count_tables(conn)
        cc = get_cycle_count(conn, count_id)
        if not cc:
            return redirect('cc_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'enter_counts' and cc['status'] == 'open':
                    counted = {}
                    for key, value in request.POST.items():
                        if key.startswith('counted_') and value.strip() != '':
                            line_id = int(key[len('counted_'):])
                            counted[line_id] = float(value)
                    enter_counts(
                        conn, count_id, counted,
                        request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('cc_detail', count_id=count_id)
                elif action == 'decide':
                    step_id = int(request.POST.get('step_id'))
                    decision = request.POST.get('decision', '')
                    decide_cycle_count(
                        conn, count_id, step_id, decision,
                        request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('cc_detail', count_id=count_id)
            except Exception as exc:
                conn.rollback()
                error = str(exc)
            cc = get_cycle_count(conn, count_id)

        lines = get_cycle_count_lines(conn, count_id)
        approval = get_entity_approval_status(conn, 'cycle_count', count_id)
    finally:
        conn.close()

    user_role = request.session.get('user_role', '')
    full_access = request.session.get('user_full_access', False)
    pending_step = next(
        (s for s in approval['steps']
         if s['status'] == 'pending'
         and (full_access or s['approver_role'] == user_role)),
        None,
    )

    return render(request, 'cc_detail.html', _cc_ctx(
        request, cc=cc, lines=lines, approval=approval,
        pending_step=pending_step, error=error, success=success,
    ))
