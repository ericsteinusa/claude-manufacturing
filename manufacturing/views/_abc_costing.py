"""Views: Activity-Based Costing (ABC)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..abc_costing_core import (
    ensure_abc_costing_tables, list_activities, get_activity, create_activity,
    list_product_drivers, set_product_driver, remove_product_driver,
    set_product_output, get_product_output, compare_to_traditional,
    get_abc_summary_all_products, VARIANCE_FLAG_THRESHOLD_PCT,
)
from ..sales_orders_core import load_products

log = get_logger(__name__)

_ABC_DEPT_KEYS = {'accounting', 'finance'}


def _abc_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_ABC_DEPT_KEYS)
def abc_activity_list(request):
    conn = get_db_connection()
    try:
        ensure_abc_costing_tables(conn)
        activities = list_activities(conn, search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'abc_activity_list.html', _abc_ctx(
        request, activities=activities, q=request.GET.get('q', ''),
    ))


@dept_required(_ABC_DEPT_KEYS, write_redirect='abc_activity_list')
def abc_activity_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_abc_costing_tables(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    activity_id = create_activity(
                        conn, name,
                        cost_pool_amount=float(request.POST.get('cost_pool_amount', 0) or 0),
                        driver_uom=request.POST.get('driver_uom', '').strip(),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('abc_activity_detail', activity_id=activity_id)
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'abc_activity_new.html', _abc_ctx(request, error=error))


@dept_required(_ABC_DEPT_KEYS, write_redirect='abc_activity_list')
def abc_activity_detail(request, activity_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_abc_costing_tables(conn)
        activity = get_activity(conn, activity_id)
        if not activity:
            return redirect('abc_activity_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'set_driver':
                    set_product_driver(
                        conn, activity_id, int(request.POST['product_id']),
                        driver_qty=float(request.POST.get('driver_qty', 0) or 0),
                    )
                    conn.commit()
                    success = 'Driver usage recorded.'
                elif action == 'remove_driver':
                    remove_product_driver(conn, int(request.POST['driver_id']))
                    conn.commit()
                    success = 'Driver usage removed.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        drivers = list_product_drivers(conn, activity_id=activity_id)
        products = load_products(conn)
    finally:
        conn.close()

    return render(request, 'abc_activity_detail.html', _abc_ctx(
        request, activity=activity, drivers=drivers, products=products,
        error=error, success=success,
    ))


@dept_required(_ABC_DEPT_KEYS)
def abc_report(request):
    conn = get_db_connection()
    try:
        ensure_abc_costing_tables(conn)
        summary = get_abc_summary_all_products(conn)
    finally:
        conn.close()
    return render(request, 'abc_report.html', _abc_ctx(
        request, summary=summary, variance_threshold_pct=VARIANCE_FLAG_THRESHOLD_PCT,
    ))


@dept_required(_ABC_DEPT_KEYS, write_redirect='abc_report')
def abc_product_output(request, product_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_abc_costing_tables(conn)
        if request.method == 'POST':
            try:
                set_product_output(
                    conn, product_id,
                    output_qty=float(request.POST.get('output_qty', 0) or 0),
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Output quantity saved.'
            except ValueError as exc:
                conn.rollback()
                error = str(exc)

        output = get_product_output(conn, product_id)
        comparison = compare_to_traditional(conn, product_id)
        product_row = conn.execute(
            "SELECT name FROM product WHERE id = %s", (product_id,),
        ).fetchone()
        product_name = product_row['name'] if product_row else f'Product {product_id}'
    finally:
        conn.close()

    return render(request, 'abc_product_output.html', _abc_ctx(
        request, product_id=product_id, product_name=product_name, output=output,
        comparison=comparison, error=error, success=success,
    ))
