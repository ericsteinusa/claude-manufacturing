"""Views: Request for Quote (RFQ) module (P1-F)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..rfq_core import (
    ensure_rfq_tables, create_rfq, get_rfq, list_rfqs,
    add_rfq_item, delete_rfq_item,
    add_rfq_vendor, remove_rfq_vendor,
    enter_quote, get_comparison, award_items,
)
from ..purchase_orders_core import load_suppliers, load_products

log = get_logger(__name__)

_RFQ_DEPT_KEYS = {'purchasing'}


def _rfq_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_RFQ_DEPT_KEYS)
def rfq_list(request):
    status = request.GET.get('status') or None
    conn = get_db_connection()
    try:
        ensure_rfq_tables(conn)
        rfqs = list_rfqs(conn, status=status)
    finally:
        conn.close()
    return render(request, 'rfq_list.html', _rfq_ctx(
        request, rfqs=rfqs, status=status,
    ))


@dept_required(_RFQ_DEPT_KEYS, write_redirect='rfq_list')
def rfq_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_rfq_tables(conn)
        if request.method == 'POST':
            try:
                rfq_id = create_rfq(
                    conn, notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('rfq_detail', rfq_id=rfq_id)
            except Exception as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'rfq_new.html', _rfq_ctx(request, error=error))


@dept_required(_RFQ_DEPT_KEYS, write_redirect='rfq_list')
def rfq_detail(request, rfq_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_rfq_tables(conn)
        rfq = get_rfq(conn, rfq_id)
        if not rfq:
            return redirect('rfq_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_item':
                    add_rfq_item(
                        conn, rfq_id,
                        description=request.POST.get('description', '').strip(),
                        product_id=int(request.POST.get('product_id'))
                        if request.POST.get('product_id') else None,
                        qty=int(request.POST.get('qty', 1) or 1),
                        target_price=float(request.POST.get('target_price', 0) or 0),
                    )
                    conn.commit()
                    success = 'Item added.'
                elif action == 'delete_item':
                    delete_rfq_item(conn, int(request.POST.get('item_id')))
                    conn.commit()
                    success = 'Item removed.'
                elif action == 'add_vendor':
                    add_rfq_vendor(conn, rfq_id, int(request.POST.get('supplier_id')))
                    conn.commit()
                    success = 'Vendor invited.'
                elif action == 'remove_vendor':
                    remove_rfq_vendor(conn, int(request.POST.get('rfq_vendor_id')))
                    conn.commit()
                    success = 'Vendor removed.'
                elif action == 'enter_quotes':
                    for key, value in request.POST.items():
                        if key.startswith('quote_') and value.strip() != '':
                            _, item_id, vendor_id = key.split('_')
                            lead_key = f'lead_{item_id}_{vendor_id}'
                            lead_raw = request.POST.get(lead_key, '').strip()
                            enter_quote(
                                conn, int(item_id), int(vendor_id),
                                float(value),
                                int(lead_raw) if lead_raw else None,
                            )
                    conn.commit()
                    success = 'Quotes saved.'
                elif action == 'award':
                    awards = {}
                    for key, value in request.POST.items():
                        if key.startswith('winner_') and value.strip() != '':
                            item_id = int(key[len('winner_'):])
                            awards[item_id] = int(value)
                    if awards:
                        award_items(
                            conn, rfq_id, awards,
                            request.session.get('user_email', ''),
                        )
                        conn.commit()
                        success = 'Awarded and converted to purchase order(s).'
                    else:
                        error = 'Select at least one winning vendor.'
            except Exception as exc:
                conn.rollback()
                error = str(exc)
            rfq = get_rfq(conn, rfq_id)

        comparison = get_comparison(conn, rfq_id)
        suppliers = load_suppliers(conn)
        products = load_products(conn)
    finally:
        conn.close()

    return render(request, 'rfq_detail.html', _rfq_ctx(
        request, rfq=rfq, comparison=comparison,
        suppliers=suppliers, products=products,
        error=error, success=success,
    ))
