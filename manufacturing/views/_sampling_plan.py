"""Views: Sampling Plans & AQL admin (P2-E)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..sampling_plan_core import (
    ensure_sampling_plan_tables, list_sampling_plans, get_sampling_plan,
    create_sampling_plan, update_sampling_plan,
    INSPECTION_LEVELS, COMMON_AQL_VALUES,
)
from ..sales_orders_core import load_products
from ..purchase_orders_core import load_suppliers

log = get_logger(__name__)

_SAMPLING_PLAN_DEPT_KEYS = {'quality_assurance'}


def _sp_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_SAMPLING_PLAN_DEPT_KEYS)
def sampling_plan_list(request):
    conn = get_db_connection()
    try:
        ensure_sampling_plan_tables(conn)
        plans = list_sampling_plans(conn)
    finally:
        conn.close()
    return render(request, 'sampling_plan_list.html', _sp_ctx(
        request, plans=plans,
    ))


@dept_required(_SAMPLING_PLAN_DEPT_KEYS, write_redirect='sampling_plan_list')
def sampling_plan_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_sampling_plan_tables(conn)
        products = load_products(conn)
        suppliers = load_suppliers(conn)
        if request.method == 'POST':
            plan_name = request.POST.get('plan_name', '').strip()
            if not plan_name:
                error = 'Plan name is required.'
            else:
                try:
                    pid_raw = request.POST.get('product_id', '')
                    sid_raw = request.POST.get('supplier_id', '')
                    plan_id = create_sampling_plan(
                        conn, plan_name,
                        aql_value=float(request.POST.get('aql_value', 0) or 0),
                        inspection_level=request.POST.get('inspection_level', 'II'),
                        product_id=int(pid_raw) if pid_raw else None,
                        supplier_id=int(sid_raw) if sid_raw else None,
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('sampling_plan_detail', plan_id=plan_id)
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'sampling_plan_new.html', _sp_ctx(
        request, products=products, suppliers=suppliers, error=error,
        inspection_levels=INSPECTION_LEVELS, common_aql_values=COMMON_AQL_VALUES,
    ))


@dept_required(_SAMPLING_PLAN_DEPT_KEYS, write_redirect='sampling_plan_list')
def sampling_plan_detail(request, plan_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_sampling_plan_tables(conn)
        plan = get_sampling_plan(conn, plan_id)
        if not plan:
            return redirect('sampling_plan_list')

        if request.method == 'POST':
            try:
                pid_raw = request.POST.get('product_id', '')
                sid_raw = request.POST.get('supplier_id', '')
                update_sampling_plan(
                    conn, plan_id,
                    plan_name=request.POST.get('plan_name', '').strip(),
                    aql_value=float(request.POST.get('aql_value', 0) or 0),
                    inspection_level=request.POST.get('inspection_level', 'II'),
                    product_id=int(pid_raw) if pid_raw else None,
                    supplier_id=int(sid_raw) if sid_raw else None,
                    is_active=request.POST.get('is_active') == '1',
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Sampling plan updated.'
                plan = get_sampling_plan(conn, plan_id)
            except Exception as exc:
                conn.rollback()
                error = str(exc)

        products = load_products(conn)
        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    return render(request, 'sampling_plan_detail.html', _sp_ctx(
        request, plan=plan, products=products, suppliers=suppliers,
        inspection_levels=INSPECTION_LEVELS, common_aql_values=COMMON_AQL_VALUES,
        error=error, success=success,
    ))
