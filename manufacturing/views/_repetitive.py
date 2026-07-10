"""Views: Repetitive Manufacturing."""

import datetime

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..repetitive_core import (
    ensure_repetitive_tables, list_schedules, get_schedule, create_schedule,
    set_schedule_status, list_production_log, log_production,
    get_schedule_summary, SCHEDULE_STATUSES,
)
from ..bom_web_core import list_products
from ..routing_core import ensure_routing_tables, list_workcenters

log = get_logger(__name__)

_REPETITIVE_DEPT_KEYS = {'production'}


def _repetitive_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'schedule_statuses': SCHEDULE_STATUSES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_REPETITIVE_DEPT_KEYS)
def repetitive_schedule_list(request):
    conn = get_db_connection()
    try:
        ensure_repetitive_tables(conn)
        schedules = list_schedules(conn, status=request.GET.get('status') or None)
    finally:
        conn.close()
    return render(request, 'repetitive_schedule_list.html', _repetitive_ctx(
        request, schedules=schedules, status=request.GET.get('status', ''),
    ))


@dept_required(_REPETITIVE_DEPT_KEYS, write_redirect='repetitive_schedule_list')
def repetitive_schedule_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_repetitive_tables(conn)
        ensure_routing_tables(conn)
        products = list_products(conn)
        workcenters = list_workcenters(conn)
        if request.method == 'POST':
            try:
                schedule_id = create_schedule(
                    conn, int(request.POST['product_id']),
                    int(request.POST['workcenter_id']) if request.POST.get('workcenter_id') else None,
                    rate_per_day=float(request.POST.get('rate_per_day') or 0),
                    effective_start=request.POST.get('effective_start', '').strip(),
                    effective_end=request.POST.get('effective_end', '').strip() or None,
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('repetitive_schedule_detail', schedule_id=schedule_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'repetitive_schedule_new.html', _repetitive_ctx(
        request, products=products, workcenters=workcenters, error=error,
    ))


@dept_required(_REPETITIVE_DEPT_KEYS, write_redirect='repetitive_schedule_list')
def repetitive_schedule_detail(request, schedule_id):
    conn = get_db_connection()
    error = success = None
    summary = None
    try:
        ensure_repetitive_tables(conn)
        schedule = get_schedule(conn, schedule_id)
        if not schedule:
            return redirect('repetitive_schedule_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'log':
                    log_production(
                        conn, schedule_id,
                        request.POST.get('production_date', '').strip(),
                        qty_completed=float(request.POST.get('qty_completed') or 0),
                        qty_scrapped=float(request.POST.get('qty_scrapped') or 0),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Production logged and materials backflushed.'
                elif action == 'set_status':
                    set_schedule_status(conn, schedule_id, request.POST.get('status', ''))
                    conn.commit()
                    success = 'Status updated.'
                elif action == 'summary':
                    summary = get_schedule_summary(
                        conn, schedule_id,
                        request.POST.get('date_from', '').strip(),
                        request.POST.get('date_to', '').strip(),
                    )
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            schedule = get_schedule(conn, schedule_id)

        log_entries = list_production_log(conn, schedule_id)
    finally:
        conn.close()

    return render(request, 'repetitive_schedule_detail.html', _repetitive_ctx(
        request, schedule=schedule, log_entries=log_entries, summary=summary,
        error=error, success=success, today=datetime.date.today().isoformat(),
    ))
