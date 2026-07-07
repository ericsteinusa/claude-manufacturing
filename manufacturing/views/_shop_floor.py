"""Views: OEE Live Shop Floor Dashboard — operator production/downtime
entry, shift planning, live dashboard, and TV display mode (P3-G)."""

import datetime as _dt

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..maintenance_core import DOWNTIME_CATEGORIES
from ..routing_core import list_workcenters
from ..shop_floor_core import (
    SHIFTS, ensure_shop_floor_tables, current_shift_for_now,
    record_production, record_downtime, set_shift_plan,
    get_shift_oee, list_live_shift_oee, list_downtime_entries,
)

log = get_logger(__name__)

_SF_DEPT_KEYS = {'production', 'maintenance'}


def _sf_ctx(request, **extra):
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'shifts': SHIFTS,
    }
    ctx.update(extra)
    return ctx


def _shift_and_date(request):
    """Resolve (shift, entry_date) from query params, defaulting to
    'right now's' shift so the dashboard/TV works with no input."""
    default_shift, default_date = current_shift_for_now()
    shift = request.GET.get('shift') or default_shift
    if shift not in SHIFTS:
        shift = default_shift
    entry_date = request.GET.get('date') or default_date.isoformat()
    return shift, entry_date


def _live_with_names(conn, workcenters, shift, entry_date):
    live = []
    for wc in workcenters:
        result = get_shift_oee(conn, wc['id'], shift, entry_date)
        result['workcenter_name'] = wc['name']
        live.append(result)
    return live


@dept_required(_SF_DEPT_KEYS, write_redirect='sf_entry')
def sf_entry(request):
    error = None
    shift, entry_date = _shift_and_date(request)
    conn = get_db_connection()
    try:
        ensure_shop_floor_tables(conn)
        conn.commit()
        workcenters = list_workcenters(conn)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            post_shift = request.POST.get('shift', shift)
            post_date = request.POST.get('entry_date', entry_date)
            try:
                workcenter_id = int(request.POST.get('workcenter_id'))
                if action == 'production':
                    record_production(
                        conn, workcenter_id, post_shift, post_date,
                        request.POST.get('qty_produced') or 0,
                        request.POST.get('qty_scrapped') or 0,
                        request.session.get('user_email', ''),
                    )
                elif action == 'downtime':
                    record_downtime(
                        conn, workcenter_id, post_shift, post_date,
                        request.POST.get('reason_category', ''),
                        request.POST.get('notes', '').strip(),
                        request.POST.get('minutes') or 0,
                        request.session.get('user_email', ''),
                    )
                conn.commit()
                return redirect(f"/shop-floor/entry/?shift={post_shift}&date={post_date}")
            except ValueError as e:
                conn.rollback()
                error = str(e)

        live = _live_with_names(conn, workcenters, shift, entry_date)
    finally:
        conn.close()

    return render(request, 'sf_entry.html', _sf_ctx(
        request, workcenters=workcenters, shift=shift, entry_date=entry_date,
        live=live, reason_categories=DOWNTIME_CATEGORIES, error=error,
    ))


@dept_required(_SF_DEPT_KEYS, write_redirect='sf_shift_plan')
def sf_shift_plan(request):
    error = None
    shift, entry_date = _shift_and_date(request)
    conn = get_db_connection()
    try:
        ensure_shop_floor_tables(conn)
        conn.commit()
        workcenters = list_workcenters(conn)
        if request.method == 'POST':
            post_shift = request.POST.get('shift', shift)
            post_date = request.POST.get('entry_date', entry_date)
            try:
                workcenter_id = int(request.POST.get('workcenter_id'))
                set_shift_plan(
                    conn, workcenter_id, post_shift, post_date,
                    request.POST.get('planned_qty') or 0,
                    request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect(f"/shop-floor/plan/?shift={post_shift}&date={post_date}")
            except ValueError as e:
                conn.rollback()
                error = str(e)

        plans = _live_with_names(conn, workcenters, shift, entry_date)
    finally:
        conn.close()

    return render(request, 'sf_shift_plan.html', _sf_ctx(
        request, workcenters=workcenters, shift=shift, entry_date=entry_date,
        plans=plans, error=error,
    ))


@dept_required(_SF_DEPT_KEYS)
def sf_dashboard(request):
    shift, entry_date = _shift_and_date(request)
    conn = get_db_connection()
    try:
        ensure_shop_floor_tables(conn)
        conn.commit()
        live = list_live_shift_oee(conn, shift, entry_date)
        downtime = []
        for wc in live:
            for d in list_downtime_entries(conn, wc['workcenter_id'], shift, entry_date):
                d['workcenter_name'] = wc['workcenter_name']
                downtime.append(d)
        downtime.sort(key=lambda d: d['id'], reverse=True)
    finally:
        conn.close()

    return render(request, 'sf_dashboard.html', _sf_ctx(
        request, live=live, downtime=downtime[:20], shift=shift, entry_date=entry_date,
    ))


@dept_required(_SF_DEPT_KEYS)
def sf_tv(request):
    """Large-format, no-picker, auto-refreshing view of the current shift —
    always 'right now', for an actual shop-floor TV display."""
    shift, entry_date = current_shift_for_now()
    conn = get_db_connection()
    try:
        ensure_shop_floor_tables(conn)
        conn.commit()
        live = list_live_shift_oee(conn, shift, entry_date.isoformat())
    finally:
        conn.close()

    return render(request, 'sf_tv.html', {
        'live': live, 'shift': shift, 'entry_date': entry_date.isoformat(),
        'now': _dt.datetime.now(),
    })
