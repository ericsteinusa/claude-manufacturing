"""Views: finite capacity scheduling — capacity check, bottlenecks, and
load-leveling suggestions (P3-A)."""

from datetime import date, timedelta

from django.shortcuts import render

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..capacity_planning_core import (
    ensure_capacity_tables, get_capacity_check, identify_bottlenecks,
    suggest_load_leveling, apply_load_leveling_suggestion,
)
from ._common import parse_date_param

log = get_logger(__name__)


def _cap_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': request.session.get('user_full_access', False),
        'can_edit': role not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required('production')
def capacity_planning(request):
    today = date.today()
    raw_from = parse_date_param(request.GET.get('date_from'))
    raw_to = parse_date_param(request.GET.get('date_to'))
    date_from_d = date.fromisoformat(raw_from) if raw_from else today
    date_to_d = date.fromisoformat(raw_to) if raw_to else today + timedelta(days=13)
    if date_to_d < date_from_d:
        date_from_d, date_to_d = date_to_d, date_from_d
    date_from = date_from_d.isoformat()
    date_to = date_to_d.isoformat()

    error = success = None
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    if request.method == 'POST' and can_edit:
        conn = get_db_connection()
        try:
            ensure_capacity_tables(conn)
            try:
                op_id = int(request.POST.get('op_id'))
                delay_days = int(request.POST.get('delay_days'))
                apply_load_leveling_suggestion(conn, op_id, delay_days)
                conn.commit()
                success = f'Delayed operation by {delay_days} day(s).'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        finally:
            conn.close()

    conn = get_db_connection()
    try:
        ensure_capacity_tables(conn)
        capacity = get_capacity_check(conn, date_from, date_to)
        bottlenecks = identify_bottlenecks(conn, date_from, date_to)
        suggestions = suggest_load_leveling(conn, date_from, date_to)
    finally:
        conn.close()

    day_range = []
    d = date_from_d
    while d <= date_to_d:
        day_range.append(d.isoformat())
        d += timedelta(days=1)

    return render(request, 'capacity_planning.html', _cap_ctx(
        request,
        date_from=date_from, date_to=date_to, day_range=day_range,
        capacity=capacity, bottlenecks=bottlenecks, suggestions=suggestions,
        error=error, success=success,
    ))
