"""Views: Asset Performance Management (APM)."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..apm_core import (
    ensure_apm_tables, list_asset_criticality, set_asset_criticality,
    get_asset_health, get_apm_dashboard, CRITICALITY_LEVELS,
)

log = get_logger(__name__)

_APM_DEPT_KEYS = {'maintenance', 'production'}


def _apm_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'criticality_levels': CRITICALITY_LEVELS,
    }
    ctx.update(extra)
    return ctx


@dept_required(_APM_DEPT_KEYS)
def apm_dashboard(request):
    conn = get_db_connection()
    try:
        ensure_apm_tables(conn)
        assets = get_apm_dashboard(conn)
    finally:
        conn.close()
    return render(request, 'apm_dashboard.html', _apm_ctx(request, assets=assets))


@dept_required(_APM_DEPT_KEYS, write_redirect='apm_dashboard')
def apm_criticality(request):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_apm_tables(conn)
        if request.method == 'POST':
            try:
                set_asset_criticality(
                    conn, request.POST.get('equipment', '').strip(),
                    request.POST.get('criticality', 'medium'),
                    replacement_cost=float(request.POST.get('replacement_cost') or 0),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Criticality saved.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        ratings = list_asset_criticality(conn)
    finally:
        conn.close()
    return render(request, 'apm_criticality.html', _apm_ctx(
        request, ratings=ratings, error=error, success=success,
    ))


@dept_required(_APM_DEPT_KEYS)
def apm_asset_detail(request):
    equipment = request.GET.get('equipment', '').strip()
    if not equipment:
        return redirect('apm_dashboard')
    conn = get_db_connection()
    try:
        ensure_apm_tables(conn)
        health = get_asset_health(conn, equipment)
    finally:
        conn.close()
    return render(request, 'apm_asset_detail.html', _apm_ctx(request, health=health))
