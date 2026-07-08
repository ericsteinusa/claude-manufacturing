"""Views: Sustainability / Carbon Cost Tracking (P4-G) — per-product
carbon footprint rollup (structural mirror of cost_detail/wo_cost_detail
in views/__init__.py), WO carbon intensity, and an ESG dashboard."""

import json

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import login_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..inventory_core import get_product as inv_get_product
from ..work_orders_core import get_wo

from ..carbon_core import (
    ensure_carbon_tables, set_material_factor,
    set_workcenter_factor, list_workcenters_with_carbon_factor,
    roll_carbon_footprint, get_carbon_footprint, list_carbon_history,
    save_wo_carbon_actual, get_wo_carbon,
    set_scope2_entry, list_scope2_entries, get_esg_summary,
)

log = get_logger(__name__)


@login_required
def carbon_detail(request, product_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_carbon_tables(conn)
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')
        current_carbon = get_carbon_footprint(conn, product_id)
        history = list_carbon_history(conn, product_id)
        can_edit = request.session.get('user_role') not in READ_ONLY_ROLES

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action')
            if action == 'set_factor':
                try:
                    set_material_factor(
                        conn, product_id,
                        float(request.POST.get('kg_co2e_per_unit') or 0),
                    )
                    conn.commit()
                    product = inv_get_product(conn, product_id)
                    success = 'Material carbon factor updated.'
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
            elif action == 'roll':
                try:
                    roll_carbon_footprint(
                        conn, product_id,
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    current_carbon = get_carbon_footprint(conn, product_id)
                    history = list_carbon_history(conn, product_id)
                    success = 'Carbon footprint rolled successfully.'
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
        elif request.method == 'POST':
            error = 'You do not have permission to make changes.'
    finally:
        conn.close()
    return render(request, 'carbon_detail.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        product=product,
        current_carbon=current_carbon,
        history=history,
        error=error,
        success=success,
    ))


@login_required
def wo_carbon_detail(request, wo_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_carbon_tables(conn)
        wo = get_wo(conn, wo_id)
        if not wo:
            return redirect('wo_list')
        carbon = get_wo_carbon(conn, wo_id)
        if request.method == 'POST' and request.POST.get('action') == 'compute':
            can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
            if not can_edit:
                error = 'You do not have permission to compute carbon actuals.'
            else:
                try:
                    carbon = save_wo_carbon_actual(
                        conn, wo_id,
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'WO carbon actual computed and saved.'
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'wo_carbon_detail.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        wo=wo,
        carbon=carbon,
        error=error,
        success=success,
    ))


@login_required
def esg_dashboard(request):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_carbon_tables(conn)
        conn.commit()
        can_edit = request.session.get('user_role') not in READ_ONLY_ROLES

        if request.method == 'POST' and can_edit:
            try:
                set_scope2_entry(
                    conn,
                    request.POST.get('period_month', '').strip(),
                    float(request.POST.get('kwh_used') or 0),
                    float(request.POST.get('grid_factor') or 0.4),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Scope 2 entry saved.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        date_from = request.GET.get('from') or None
        date_to = request.GET.get('to') or None
        summary = get_esg_summary(conn, date_from, date_to)
        scope2_entries = list_scope2_entries(conn)
        workcenters = list_workcenters_with_carbon_factor(conn)
    finally:
        conn.close()

    return render(request, 'esg_dashboard.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=can_edit,
        summary=summary,
        summary_json=json.dumps(summary),
        scope2_entries=scope2_entries,
        workcenters=workcenters,
        date_from=date_from or '',
        date_to=date_to or '',
        error=error,
        success=success,
    ))


@login_required
def workcenter_carbon_factor(request, wc_id):
    if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
        conn = get_db_connection()
        try:
            ensure_carbon_tables(conn)
            set_workcenter_factor(conn, wc_id, float(request.POST.get('kg_co2e_per_hour') or 0))
            conn.commit()
        finally:
            conn.close()
    return redirect('esg_dashboard')
