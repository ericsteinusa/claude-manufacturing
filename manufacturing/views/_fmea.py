"""Views: Control Plans & FMEA."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..fmea_core import (
    ensure_fmea_tables, list_control_plans, get_control_plan,
    create_control_plan, update_control_plan_status, list_control_plan_items,
    add_control_plan_item, update_control_plan_item, delete_control_plan_item,
    get_high_risk_items, rpn_risk_level, CONTROL_PLAN_STATUSES,
)
from ..sales_orders_core import load_products

log = get_logger(__name__)

_FMEA_DEPT_KEYS = {'quality_assurance'}


def _fmea_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'control_plan_statuses': CONTROL_PLAN_STATUSES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_FMEA_DEPT_KEYS)
def control_plan_list(request):
    conn = get_db_connection()
    try:
        ensure_fmea_tables(conn)
        plans = list_control_plans(conn)
    finally:
        conn.close()
    return render(request, 'control_plan_list.html', _fmea_ctx(request, plans=plans))


@dept_required(_FMEA_DEPT_KEYS, write_redirect='control_plan_list')
def control_plan_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_fmea_tables(conn)
        products = load_products(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    plan_id = create_control_plan(
                        conn, int(request.POST['product_id']), name,
                        revision=request.POST.get('revision', 'A').strip() or 'A',
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('control_plan_detail', plan_id=plan_id)
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'control_plan_new.html', _fmea_ctx(
        request, products=products, error=error,
    ))


@dept_required(_FMEA_DEPT_KEYS, write_redirect='control_plan_list')
def control_plan_detail(request, plan_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_fmea_tables(conn)
        plan = get_control_plan(conn, plan_id)
        if not plan:
            return redirect('control_plan_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_item':
                    add_control_plan_item(
                        conn, plan_id,
                        characteristic=request.POST.get('characteristic', '').strip(),
                        severity=int(request.POST.get('severity', 1)),
                        occurrence=int(request.POST.get('occurrence', 1)),
                        detection=int(request.POST.get('detection', 1)),
                        specification=request.POST.get('specification', '').strip(),
                        control_method=request.POST.get('control_method', '').strip(),
                        recommended_action=request.POST.get('recommended_action', '').strip(),
                        notes=request.POST.get('notes', '').strip(),
                        operation_seq=int(request.POST['operation_seq']) if request.POST.get('operation_seq') else None,
                    )
                    conn.commit()
                    success = 'Item added.'
                elif action == 'update_item':
                    update_control_plan_item(
                        conn, int(request.POST['item_id']),
                        severity=int(request.POST.get('severity', 1)),
                        occurrence=int(request.POST.get('occurrence', 1)),
                        detection=int(request.POST.get('detection', 1)),
                    )
                    conn.commit()
                    success = 'Item risk re-scored.'
                elif action == 'delete_item':
                    delete_control_plan_item(conn, int(request.POST['item_id']))
                    conn.commit()
                    success = 'Item removed.'
                elif action == 'set_status':
                    update_control_plan_status(conn, plan_id, request.POST.get('status', ''))
                    conn.commit()
                    success = 'Status updated.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            plan = get_control_plan(conn, plan_id)

        items = list_control_plan_items(conn, plan_id)
        for item in items:
            item['risk_level'] = rpn_risk_level(item['rpn'])
    finally:
        conn.close()

    return render(request, 'control_plan_detail.html', _fmea_ctx(
        request, plan=plan, items=items, error=error, success=success,
    ))


@dept_required(_FMEA_DEPT_KEYS)
def fmea_risk_register(request):
    conn = get_db_connection()
    try:
        ensure_fmea_tables(conn)
        threshold = int(request.GET.get('threshold', 100) or 100)
        items = get_high_risk_items(conn, threshold=threshold)
        for item in items:
            item['risk_level'] = rpn_risk_level(item['rpn'])
    finally:
        conn.close()
    return render(request, 'fmea_risk_register.html', _fmea_ctx(
        request, items=items, threshold=threshold,
    ))
