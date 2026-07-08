"""Views: Landed Cost Allocation on a PO's received line items (P3-D)."""

from django.shortcuts import render, redirect
from django.http import HttpResponse

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger

from ..landed_cost_core import (
    ensure_landed_cost_tables, ALLOCATION_METHODS,
    list_receivable_po_items, get_landed_cost, create_landed_cost,
)
from ..purchase_orders_core import get_po

log = get_logger(__name__)


def _float_or_zero(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dept_required('purchasing', write_redirect='po_list')
def po_landed_cost_new(request, po_id):
    conn = get_db_connection()
    try:
        ensure_landed_cost_tables(conn)
        conn.commit()
        po = get_po(conn, po_id)
        if not po:
            return HttpResponse('Not found', status=404)
        items = list_receivable_po_items(conn, po_id)

        if request.method == 'POST':
            method = request.POST.get('method', 'value')
            freight = _float_or_zero(request.POST.get('freight'))
            duty = _float_or_zero(request.POST.get('duty'))
            broker_fee = _float_or_zero(request.POST.get('broker_fee'))
            insurance = _float_or_zero(request.POST.get('insurance'))
            line_weights = {}
            for it in items:
                raw = request.POST.get(f'weight_{it["id"]}')
                if raw not in (None, ''):
                    line_weights[it['id']] = _float_or_zero(raw)
            try:
                lc_id = create_landed_cost(
                    conn, po_id, freight, duty, broker_fee, insurance,
                    method, line_weights,
                    request.session.get('user_email', ''))
                conn.commit()
            except ValueError as e:
                return render(request, 'po_landed_cost_new.html', {
                    'po': po, 'items': items, 'methods': ALLOCATION_METHODS,
                    'error': str(e),
                })
            return redirect('po_landed_cost_detail', po_id=po_id, lc_id=lc_id)
    finally:
        conn.close()
    return render(request, 'po_landed_cost_new.html', {
        'po': po, 'items': items, 'methods': ALLOCATION_METHODS,
    })


@dept_required('purchasing')
def po_landed_cost_detail(request, po_id, lc_id):
    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        lc = get_landed_cost(conn, lc_id)
        if not po or not lc or lc['po_id'] != po_id:
            return HttpResponse('Not found', status=404)
    finally:
        conn.close()
    return render(request, 'po_landed_cost_detail.html', {'po': po, 'lc': lc})
