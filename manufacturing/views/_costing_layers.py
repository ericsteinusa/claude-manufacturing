"""Views: FIFO / LIFO / Weighted-Average inventory costing — an opt-in
valuation subsystem parallel to the existing standard-cost pages
(cost_detail / wo_cost_detail in views/__init__.py). Lives under
/inventory/... since, unlike standard costing, this is fundamentally an
inventory concept that applies to any product, not just ones with a BOM."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import login_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..inventory_core import get_product as inv_get_product

from ..costing_layers_core import (
    COSTING_METHODS, ensure_costing_layers_tables,
    get_costing_method, set_costing_method,
    list_cost_layers, receive_with_costing, issue_with_costing,
    get_inventory_valuation, list_inventory_valuation, list_cogs_history,
)

log = get_logger(__name__)


@login_required
def costing_valuation_list(request):
    conn = get_db_connection()
    try:
        ensure_costing_layers_tables(conn)
        conn.commit()
        valuations = list_inventory_valuation(conn)
    finally:
        conn.close()
    return render(request, 'costing_valuation_list.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        valuations=valuations,
    ))


@login_required
def costing_product_detail(request, product_id):
    error = success = None
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        ensure_costing_layers_tables(conn)
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            by = request.session.get('user_email', '')
            try:
                if action == 'set_method':
                    set_costing_method(conn, product_id, request.POST.get('method', ''))
                    success = 'Costing method updated.'
                elif action == 'receive':
                    receive_with_costing(
                        conn, product_id,
                        float(request.POST.get('qty')),
                        float(request.POST.get('unit_cost')),
                        reference=request.POST.get('reference', ''),
                        notes=request.POST.get('notes', ''),
                        created_by=by,
                    )
                    success = 'Costed receipt recorded.'
                elif action == 'issue':
                    result = issue_with_costing(
                        conn, product_id,
                        float(request.POST.get('qty')),
                        reference=request.POST.get('reference', ''),
                        notes=request.POST.get('notes', ''),
                        created_by=by,
                    )
                    success = (
                        f"Costed issue recorded — COGS ${result['total_cost']:.2f}"
                        + (f" (shortfall {result['shortfall_qty']:.2f} costed at "
                           "current purchase price)" if result['shortfall_qty'] else '')
                    )
                conn.commit()
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        elif request.method == 'POST':
            error = 'You do not have permission to make changes.'

        method = get_costing_method(conn, product_id)
        layers = list_cost_layers(conn, product_id)
        valuation = get_inventory_valuation(conn, product_id)
        cogs_history = list_cogs_history(conn, product_id)
    finally:
        conn.close()
    return render(request, 'costing_product_detail.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=can_edit,
        product=product,
        method=method,
        methods=COSTING_METHODS,
        layers=layers,
        valuation=valuation,
        cogs_history=cogs_history,
        error=error,
        success=success,
    ))
