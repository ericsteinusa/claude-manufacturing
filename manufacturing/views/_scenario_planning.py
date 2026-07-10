"""Views: What-If Scenario Planning."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..scenario_planning_core import (
    ensure_scenario_tables, list_scenarios, get_scenario, create_scenario,
    delete_scenario, list_demand_adjustments, add_demand_adjustment,
    remove_demand_adjustment, list_capacity_adjustments,
    add_capacity_adjustment, remove_capacity_adjustment, run_scenario,
)
from ..sales_orders_core import load_products
from ..routing_core import ensure_routing_tables, list_workcenters

log = get_logger(__name__)

_SCENARIO_DEPT_KEYS = {'production'}


def _scenario_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_SCENARIO_DEPT_KEYS)
def scenario_list(request):
    conn = get_db_connection()
    try:
        ensure_scenario_tables(conn)
        scenarios = list_scenarios(conn, search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'scenario_list.html', _scenario_ctx(
        request, scenarios=scenarios, q=request.GET.get('q', ''),
    ))


@dept_required(_SCENARIO_DEPT_KEYS, write_redirect='scenario_list')
def scenario_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_scenario_tables(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    scenario_id = create_scenario(
                        conn, name,
                        description=request.POST.get('description', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('scenario_detail', scenario_id=scenario_id)
                except ValueError as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'scenario_new.html', _scenario_ctx(request, error=error))


@dept_required(_SCENARIO_DEPT_KEYS, write_redirect='scenario_list')
def scenario_detail(request, scenario_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_scenario_tables(conn)
        ensure_routing_tables(conn)
        scenario = get_scenario(conn, scenario_id)
        if not scenario:
            return redirect('scenario_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_demand':
                    add_demand_adjustment(
                        conn, scenario_id,
                        product_id=int(request.POST['product_id']),
                        qty=float(request.POST.get('qty', 0) or 0),
                        need_date=request.POST.get('need_date', ''),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Demand adjustment added.'
                elif action == 'remove_demand':
                    remove_demand_adjustment(conn, int(request.POST['adjustment_id']))
                    conn.commit()
                    success = 'Demand adjustment removed.'
                elif action == 'add_capacity':
                    add_capacity_adjustment(
                        conn, scenario_id,
                        workcenter_id=int(request.POST['workcenter_id']),
                        date_from=request.POST.get('date_from', ''),
                        date_to=request.POST.get('date_to', ''),
                        hours_per_day=float(request.POST.get('hours_per_day', 0) or 0),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Capacity adjustment added.'
                elif action == 'remove_capacity':
                    remove_capacity_adjustment(conn, int(request.POST['adjustment_id']))
                    conn.commit()
                    success = 'Capacity adjustment removed.'
                elif action == 'delete_scenario':
                    delete_scenario(conn, scenario_id)
                    conn.commit()
                    return redirect('scenario_list')
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        demand_adjustments = list_demand_adjustments(conn, scenario_id)
        capacity_adjustments = list_capacity_adjustments(conn, scenario_id)
        products = load_products(conn)
        workcenters = list_workcenters(conn, active_only=True)
    finally:
        conn.close()

    return render(request, 'scenario_detail.html', _scenario_ctx(
        request, scenario=scenario, demand_adjustments=demand_adjustments,
        capacity_adjustments=capacity_adjustments, products=products,
        workcenters=workcenters, error=error, success=success,
    ))


@dept_required(_SCENARIO_DEPT_KEYS)
def scenario_run(request, scenario_id):
    conn = get_db_connection()
    try:
        ensure_scenario_tables(conn)
        ensure_routing_tables(conn)
        try:
            result = run_scenario(
                conn, scenario_id,
                capacity_date_from=request.GET.get('date_from') or None,
                capacity_date_to=request.GET.get('date_to') or None,
            )
        except ValueError:
            return redirect('scenario_list')
    finally:
        conn.close()

    return render(request, 'scenario_run.html', _scenario_ctx(request, result=result))
