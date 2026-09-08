"""Views: Receiving (goods-in) — inbound shipment log with WMS bin put-away.

Distinct from wms_receive (PO-item-level put-away): this models a
shipment's own dock paperwork (carrier, tracking, per-line qty), and
existed only as seeded sample data with no web page before this module.
"""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..accounts import READ_ONLY_ROLES

from ..receiving_core import (
    RECEIVING_STATUSES,
    ensure_receiving_tables, list_receipts, get_receipt, get_receipt_items,
    create_receipt, add_receipt_item, receive_item, reject_receipt,
)
from ..wms_core import ensure_bin_tables, list_bins, suggest_putaway_bin
from ..purchase_orders_core import list_pos

_RECEIVING_DEPT_KEYS = {'production', 'purchasing', 'maintenance', 'engineering'}


def _receiving_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_RECEIVING_DEPT_KEYS)
def receiving_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status = request.GET.get('status') or None
    if status not in RECEIVING_STATUSES:
        status = None
    search = request.GET.get('search', '').strip()
    error = None

    conn = get_db_connection()
    try:
        ensure_receiving_tables(conn)
        if request.method == 'POST' and can_edit:
            try:
                receiving_id = create_receipt(
                    conn,
                    po_id=int(request.POST.get('po_id') or 0) or None,
                    rcv_date=request.POST.get('rcv_date', ''),
                    supplier=request.POST.get('supplier', ''),
                    carrier=request.POST.get('carrier', ''),
                    tracking_number=request.POST.get('tracking_number', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('receiving_detail', receiving_id=receiving_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        receipts = list_receipts(conn, status=status, search=search or None)
        pos = list_pos(conn)
    finally:
        conn.close()

    return render(request, 'receiving_list.html', _receiving_ctx(
        request, receipts=receipts, pos=pos, status=status, search=search,
        receiving_statuses=RECEIVING_STATUSES, can_edit=can_edit, error=error,
    ))


@dept_required(_RECEIVING_DEPT_KEYS, write_redirect='receiving_list')
def receiving_detail(request, receiving_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None

    conn = get_db_connection()
    try:
        ensure_receiving_tables(conn)
        ensure_bin_tables(conn)
        receipt = get_receipt(conn, receiving_id)
        if not receipt:
            return redirect('receiving_list')

        action = request.POST.get('action', '') if request.method == 'POST' else None
        if action == 'add_item' and can_edit:
            try:
                add_receipt_item(
                    conn, receiving_id,
                    description=request.POST.get('description', ''),
                    product_id=int(request.POST.get('product_id') or 0) or None,
                    qty_ordered=int(request.POST.get('qty_ordered') or 1),
                )
                conn.commit()
                return redirect('receiving_detail', receiving_id=receiving_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        elif action == 'receive_item' and can_edit:
            try:
                receive_item(
                    conn, int(request.POST.get('item_id', 0)),
                    qty=float(request.POST.get('qty') or 0),
                    bin_id=int(request.POST.get('bin_id') or 0) or None,
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Item received.'
                receipt = get_receipt(conn, receiving_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        elif action == 'reject' and can_edit:
            try:
                reject_receipt(conn, receiving_id, request.POST.get('notes', ''))
                conn.commit()
                receipt = get_receipt(conn, receiving_id)
                success = 'Receipt marked rejected.'
            except Exception as e:
                conn.rollback()
                error = str(e)

        items = get_receipt_items(conn, receiving_id)
        for item in items:
            item['suggested_bin'] = (
                suggest_putaway_bin(conn, item['product_id'])
                if item['product_id'] else None
            )
        bins = list_bins(conn)
    finally:
        conn.close()

    return render(request, 'receiving_detail.html', _receiving_ctx(
        request, receipt=receipt, items=items, bins=bins,
        receiving_statuses=RECEIVING_STATUSES, can_edit=can_edit,
        error=error, success=success,
    ))
