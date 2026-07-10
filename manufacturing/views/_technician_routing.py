"""Views: Technician Routing & Scheduling."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..technician_routing_core import (
    ensure_routing_tables, list_routes, get_route, create_route,
    set_route_status, add_stop, move_stop, complete_stop, get_route_summary,
    ROUTE_STATUSES,
)
from ..maintenance_core import load_mechanics, list_work_orders

log = get_logger(__name__)

_ROUTE_DEPT_KEYS = {'maintenance', 'production'}


def _route_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'route_statuses': ROUTE_STATUSES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_ROUTE_DEPT_KEYS)
def technician_route_list(request):
    conn = get_db_connection()
    try:
        ensure_routing_tables(conn)
        routes = list_routes(conn, status=request.GET.get('status') or None)
    finally:
        conn.close()
    return render(request, 'technician_route_list.html', _route_ctx(
        request, routes=routes, status=request.GET.get('status', ''),
    ))


@dept_required(_ROUTE_DEPT_KEYS, write_redirect='technician_route_list')
def technician_route_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_routing_tables(conn)
        mechanics = load_mechanics(conn)
        if request.method == 'POST':
            try:
                route_id = create_route(
                    conn, int(request.POST['mechanic_id']),
                    request.POST.get('route_date', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('technician_route_detail', route_id=route_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'technician_route_new.html', _route_ctx(
        request, mechanics=mechanics, error=error,
    ))


@dept_required(_ROUTE_DEPT_KEYS, write_redirect='technician_route_list')
def technician_route_detail(request, route_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_routing_tables(conn)
        route = get_route(conn, route_id)
        if not route:
            return redirect('technician_route_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_stop':
                    add_stop(
                        conn, route_id, int(request.POST['wo_id']),
                        estimated_minutes=int(request.POST.get('estimated_minutes') or 30),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Stop added.'
                elif action == 'move':
                    move_stop(conn, route_id, int(request.POST['stop_id']),
                             request.POST.get('direction', ''))
                    conn.commit()
                    success = 'Stop reordered.'
                elif action == 'complete_stop':
                    complete_stop(conn, int(request.POST['stop_id']),
                                  notes=request.POST.get('notes', '').strip())
                    conn.commit()
                    success = 'Stop completed and work order closed.'
                elif action == 'set_status':
                    set_route_status(conn, route_id, request.POST.get('status', ''))
                    conn.commit()
                    success = 'Status updated.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            route = get_route(conn, route_id)

        open_wos = list_work_orders(conn, status='Open')
        summary = get_route_summary(conn, route_id)
    finally:
        conn.close()

    return render(request, 'technician_route_detail.html', _route_ctx(
        request, route=route, open_wos=open_wos, summary=summary,
        error=error, success=success,
    ))
