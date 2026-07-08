"""Views: Consignment (Vendor-Owned) Inventory.

A consignment agreement is a standalone standing record (vendor, product,
open-ended replenishment window) — same shape as blanket_po_core's own
views (not nested under an existing PO), with receipts/usage shown as cards
inside the agreement's own detail page.
"""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..consignment_core import (
    AGREEMENT_STATUSES, ensure_consignment_tables,
    list_agreements, get_agreement, list_receipts, list_usages,
    create_agreement, receive_stock, record_usage, cancel_agreement,
    list_products_for_picker,
)
from ..purchase_orders_core import load_suppliers

log = get_logger(__name__)


def _ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dept_required('purchasing')
def consignment_list(request):
    status = request.GET.get('status') or None
    if status not in AGREEMENT_STATUSES:
        status = None
    supplier_id = _int_or_none(request.GET.get('supplier_id'))

    conn = get_db_connection()
    try:
        ensure_consignment_tables(conn)
        conn.commit()
        agreements = list_agreements(conn, status=status, supplier_id=supplier_id)
        conn.commit()
        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    return render(request, 'consignment_list.html', _ctx(
        request,
        agreements=agreements,
        status=status,
        statuses=AGREEMENT_STATUSES,
        suppliers=suppliers,
        supplier_id=supplier_id,
        back_url='/po/',
    ))


@dept_required('purchasing', write_redirect='consignment_list')
def consignment_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_consignment_tables(conn)
        conn.commit()
        suppliers = load_suppliers(conn)
        products = list_products_for_picker(conn)
        if request.method == 'POST':
            try:
                agreement_id = create_agreement(
                    conn,
                    supplier_id=_int_or_none(request.POST.get('supplier_id')),
                    product_id=_int_or_none(request.POST.get('product_id')),
                    unit_cost=_float_or_zero(request.POST.get('unit_cost')),
                    start_date=request.POST.get('start_date', '').strip(),
                    end_date=request.POST.get('end_date', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('consignment_detail', agreement_id=agreement_id)
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    return render(request, 'consignment_new.html', _ctx(
        request, suppliers=suppliers, products=products, error=error,
        form=request.POST if request.method == 'POST' else {},
        back_url='/consignment/',
    ))


@dept_required('purchasing')
def consignment_detail(request, agreement_id):
    conn = get_db_connection()
    try:
        ensure_consignment_tables(conn)
        conn.commit()
        agreement = get_agreement(conn, agreement_id)
        conn.commit()
        receipts = list_receipts(conn, agreement_id) if agreement else []
        usages = list_usages(conn, agreement_id) if agreement else []
    finally:
        conn.close()

    if not agreement:
        return redirect('consignment_list')

    return render(request, 'consignment_detail.html', _ctx(
        request, agreement=agreement, receipts=receipts, usages=usages,
        back_url='/consignment/',
    ))


@dept_required('purchasing', write_redirect='consignment_list')
def consignment_receive(request, agreement_id):
    error = None
    conn = get_db_connection()
    try:
        ensure_consignment_tables(conn)
        conn.commit()
        agreement = get_agreement(conn, agreement_id)
        conn.commit()
        if agreement and request.method == 'POST':
            try:
                receive_stock(
                    conn, agreement_id,
                    qty=_float_or_zero(request.POST.get('qty')),
                    reference=request.POST.get('reference', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('consignment_detail', agreement_id=agreement_id)
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    if not agreement:
        return redirect('consignment_list')

    return render(request, 'consignment_receive.html', _ctx(
        request, agreement=agreement, error=error,
        back_url='/consignment/%s/' % agreement_id,
    ))


@dept_required('purchasing', write_redirect='consignment_list')
def consignment_use(request, agreement_id):
    error = None
    success = None
    conn = get_db_connection()
    try:
        ensure_consignment_tables(conn)
        conn.commit()
        agreement = get_agreement(conn, agreement_id)
        conn.commit()
        if agreement and request.method == 'POST':
            try:
                result = record_usage(
                    conn, agreement_id,
                    qty=_float_or_zero(request.POST.get('qty')),
                    reference=request.POST.get('reference', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = (
                    f"Usage recorded — {result['total_cost']:.2f} owed to vendor "
                    f"(AP invoice #{result['ap_invoice_id']})."
                )
                agreement = get_agreement(conn, agreement_id)
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    if not agreement:
        return redirect('consignment_list')

    return render(request, 'consignment_use.html', _ctx(
        request, agreement=agreement, error=error, success=success,
        back_url='/consignment/%s/' % agreement_id,
    ))


@dept_required('purchasing', write_redirect='consignment_list')
def consignment_cancel(request, agreement_id):
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            ensure_consignment_tables(conn)
            conn.commit()
            try:
                cancel_agreement(conn, agreement_id)
                conn.commit()
            except ValueError:
                conn.rollback()
        finally:
            conn.close()
    return redirect('consignment_detail', agreement_id=agreement_id)
