"""Views: work-order Gantt scheduler grouped by workcenter (P2-A)."""

import json
from datetime import date, timedelta

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required, dept_access_denied_reason
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..routing_core import (
    ensure_routing_tables, get_gantt_operations,
    get_planned_workcenter_load, reschedule_operation, list_workcenters,
)

log = get_logger(__name__)


def _gantt_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': request.session.get('user_full_access', False),
        'can_edit': role not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def _parse_date_param(raw, default):
    raw = (raw or '').strip()
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return default


@ensure_csrf_cookie
@dept_required('production')
def prod_schedule_gantt(request):
    today = date.today()
    date_from_d = _parse_date_param(request.GET.get('date_from'), today)
    date_to_d = _parse_date_param(request.GET.get('date_to'), today + timedelta(days=13))
    if date_to_d < date_from_d:
        date_from_d, date_to_d = date_to_d, date_from_d
    date_from = date_from_d.isoformat()
    date_to = date_to_d.isoformat()

    wc_raw = request.GET.get('workcenter_id', '').strip()
    workcenter_id = int(wc_raw) if wc_raw.isdigit() else None

    with get_db_connection() as conn:
        ensure_routing_tables(conn)
        all_ops = get_gantt_operations(conn, date_from=date_from, date_to=date_to)
        load_data = get_planned_workcenter_load(conn, date_from, date_to, ops=all_ops)
        workcenters = list_workcenters(conn, active_only=True)

    ops = [o for o in all_ops if not workcenter_id or o['workcenter_id'] == workcenter_id]

    tasks = [{
        'id': f"op-{o['id']}",
        'name': f"{o['workcenter_name'] or '(unassigned)'} · {o['wo_number']} · {o['operation_name']}",
        'start': o['bar_start'],
        'end': o['bar_end'],
        'progress': 100 if o['status'] == 'completed' else (50 if o['status'] == 'in_progress' else 0),
        'custom_class': f"gantt-st-{o['status']}",
    } for o in ops if o['bar_start'] and o['bar_end']]

    return render(request, 'prod_schedule_gantt.html', _gantt_ctx(
        request,
        gantt_tasks_json=json.dumps(tasks),
        load_data=load_data,
        date_from=date_from, date_to=date_to,
        workcenter_id=workcenter_id, workcenters=workcenters,
        ops_count=len(ops),
    ))


def prod_schedule_gantt_reschedule(request):
    """AJAX POST: persist one operation's dragged/resized bar position.

    Not gated with @dept_required(..., write_redirect=...) — that decorator
    issues an HTML redirect on denial, which fetch() would follow and hand
    back an HTML body where the JS expects JSON. dept_access_denied_reason
    runs the same check as the decorator but lets us return JsonResponse.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    reason = dept_access_denied_reason(request, 'production', check_write=True)
    if reason == 'unauthenticated':
        return JsonResponse({'ok': False, 'error': 'not authenticated'}, status=401)
    if reason == 'forbidden':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    if reason == 'read_only':
        return JsonResponse({'ok': False, 'error': 'read-only role'}, status=403)

    try:
        payload = json.loads(request.body)
        op_id = int(payload['op_id'])
        scheduled_start = payload['scheduled_start']
        scheduled_end = payload['scheduled_end']
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'invalid payload'}, status=400)

    conn = get_db_connection()
    try:
        ensure_routing_tables(conn)
        updated = reschedule_operation(conn, op_id, scheduled_start, scheduled_end)
        if not updated:
            conn.rollback()
            return JsonResponse({'ok': False, 'error': 'operation not found'}, status=404)
        conn.commit()
        return JsonResponse({'ok': True})
    except ValueError as exc:
        conn.rollback()
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    except Exception:
        conn.rollback()
        log.exception("reschedule_operation failed for op_id=%s", op_id)
        return JsonResponse({'ok': False, 'error': 'internal error'}, status=500)
    finally:
        conn.close()
