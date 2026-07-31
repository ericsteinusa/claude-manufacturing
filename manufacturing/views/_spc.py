"""Views: Statistical Process Control (control limits + measurement log)."""

from urllib.parse import urlencode

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..quality_core import (
    ensure_spc_tables, create_control_limit, list_control_limits,
    log_measurement, get_measurements, compute_cpk, get_spc_alerts,
    load_products_for_qa, SPC_SUBGROUP_SIZES,
)
from ..lot_core import ensure_lot_tables, list_lots

log = get_logger(__name__)

_SPC_DEPT_KEYS = {'quality_assurance', 'production'}


def _spc_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_SPC_DEPT_KEYS, write_redirect='spc_list')
def spc_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    try:
        ensure_spc_tables(conn)
        products = load_products_for_qa(conn)
        if request.method == 'POST' and can_edit:
            try:
                product_raw = request.POST.get('product_id', '').strip()
                create_control_limit(
                    conn,
                    product_id=int(product_raw) if product_raw else None,
                    characteristic=request.POST.get('characteristic', ''),
                    ucl=float(request.POST.get('ucl') or 0),
                    lcl=float(request.POST.get('lcl') or 0),
                    target=float(request.POST['target']) if request.POST.get('target') else None,
                    sigma=float(request.POST['sigma']) if request.POST.get('sigma') else None,
                    subgroup_size=int(request.POST.get('subgroup_size') or 5),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Control limit saved.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        limits = list_control_limits(conn, active_only=False)
        alerts = get_spc_alerts(conn, limit=20)
    finally:
        conn.close()
    return render(request, 'spc_list.html', _spc_ctx(
        request, limits=limits, alerts=alerts, products=products,
        subgroup_sizes=SPC_SUBGROUP_SIZES, error=error, success=success,
    ))


@dept_required(_SPC_DEPT_KEYS, write_redirect='spc_list')
def spc_log(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = result = None
    product_id = request.GET.get('product_id', '').strip()
    characteristic = request.GET.get('characteristic', '').strip()
    logged_action = request.GET.get('logged', '').strip()
    success = f"Measurement logged — {logged_action}." if logged_action else None
    try:
        ensure_spc_tables(conn)
        ensure_lot_tables(conn)
        products = load_products_for_qa(conn)
        lots = list_lots(conn)
        if request.method == 'POST' and can_edit:
            try:
                product_id = request.POST.get('product_id', '').strip()
                characteristic = request.POST.get('characteristic', '').strip()
                lot_raw = request.POST.get('lot_id', '').strip()
                result = log_measurement(
                    conn,
                    product_id=int(product_id) if product_id else None,
                    characteristic=characteristic,
                    measured_value=float(request.POST.get('measured_value') or 0),
                    measured_by=request.session.get('user_email', ''),
                    lot_id=int(lot_raw) if lot_raw else None,
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                qs = urlencode({
                    'product_id': product_id,
                    'characteristic': characteristic,
                    'logged': result['action'],
                })
                return redirect(f"/qa/spc/log/?{qs}")
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        measurements = (
            get_measurements(conn, int(product_id) if product_id else None,
                             characteristic, limit=25)
            if characteristic else []
        )
        cpk = (
            compute_cpk(conn, int(product_id) if product_id else None, characteristic)
            if characteristic else None
        )
    finally:
        conn.close()
    return render(request, 'spc_log.html', _spc_ctx(
        request, products=products, lots=lots,
        product_id=product_id, characteristic=characteristic,
        measurements=measurements, cpk=cpk, result=result,
        error=error, success=success,
    ))
