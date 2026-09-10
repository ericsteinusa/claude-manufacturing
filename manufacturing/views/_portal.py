"""Views: Customer Self-Service Portal (P3-C).

A separate, non-employee login: every view here is gated by
customer_login_required (session key 'portal_customer_id', not the employee
'user_*' keys) plus an explicit ownership check on every detail view
(compare the record's customer_id — or sales_order.customer_id for
shipments/RMAs — to the caller's own), same pattern as ESS (views/_ess.py).
"""

from django.shortcuts import render, redirect
from django.http import HttpResponse

from ..db_pg import get_db_connection
from ..auth_decorators import customer_login_required
from ..log_utils import get_logger

from ..customer_portal_core import (
    ensure_portal_tables, register_customer_login, verify_customer_login,
    list_my_shipments, get_my_shipment,
    list_my_rmas, get_my_rma, submit_rma,
    get_tracking_events,
    create_payment_intent, confirm_payment_intent,
    render_invoice_pdf, render_packing_slip_pdf,
)
from ..sales_orders_core import list_sos, get_so, get_so_items
from ..accounting_core import list_ar_invoices, get_ar_invoice, list_ar_payments
from ..production_core import (
    get_shipment_items, RMA_REASONS, init_shipment_tables, init_rma_table,
)

log = get_logger(__name__)


def _portal_ctx(request, **extra):
    ctx = {
        'portal_email': request.session.get('portal_customer_email', ''),
        'portal_company': request.session.get('portal_customer_company', ''),
    }
    ctx.update(extra)
    return ctx


def _my_customer_id(request):
    return request.session.get('portal_customer_id')


# ---------------------------------------------------------------------------
# Register / login / logout
# ---------------------------------------------------------------------------

def portal_register(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        conn = get_db_connection()
        try:
            ensure_portal_tables(conn)
            conn.commit()
            try:
                register_customer_login(conn, email, password)
                conn.commit()
            except ValueError as e:
                return render(request, 'portal_register.html', {
                    'error': str(e), 'email_value': email,
                })
            return redirect('portal_login')
        finally:
            conn.close()
    return render(request, 'portal_register.html', {})


def portal_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        conn = get_db_connection()
        try:
            ensure_portal_tables(conn)
            conn.commit()
            profile = verify_customer_login(conn, email, password)
        finally:
            conn.close()
        if profile:
            # See views/__init__.py's _complete_login for why this is here.
            request.session.cycle_key()
            request.session['portal_customer_id'] = profile['customer_id']
            request.session['portal_customer_email'] = profile['email']
            request.session['portal_customer_company'] = profile['display_name']
            return redirect('portal_home')
        return render(request, 'portal_login.html', {
            'error': 'Invalid email or password.', 'email_value': email,
        })
    if _my_customer_id(request):
        return redirect('portal_home')
    return render(request, 'portal_login.html', {})


def portal_logout(request):
    # Pop only this portal's own keys — session.flush() would also wipe an
    # active supplier-portal or employee session sharing the same browser
    # session (customer/supplier/employee logins previously shared the
    # single Django session object with unnamespaced 'portal_email'/
    # 'portal_company' keys, so logging out of one silently logged out the
    # others too).
    for key in ('portal_customer_id', 'portal_customer_email', 'portal_customer_company'):
        request.session.pop(key, None)
    request.session.cycle_key()
    return redirect('portal_login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@customer_login_required
def portal_home(request):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        init_rma_table(conn)
        conn.commit()
        orders = list_sos(conn, customer_id=customer_id)
        invoices = list_ar_invoices(conn, customer_id=customer_id)
        rmas = list_my_rmas(conn, customer_id)
    finally:
        conn.close()
    open_invoices = [i for i in invoices if i['status'] in ('open', 'partial', 'overdue')]
    open_orders = [o for o in orders if o['status'] not in ('invoiced', 'cancelled')]
    open_rmas = [r for r in rmas if r['status'] not in ('resolved', 'rejected')]
    return render(request, 'portal_home.html', _portal_ctx(
        request, orders=orders[:5], open_orders=open_orders,
        open_invoices=open_invoices, open_rmas=open_rmas,
    ))


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@customer_login_required
def portal_orders(request):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        orders = list_sos(conn, customer_id=customer_id)
    finally:
        conn.close()
    return render(request, 'portal_orders.html', _portal_ctx(request, orders=orders))


@customer_login_required
def portal_order_detail(request, so_id):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        so = get_so(conn, so_id)
        if not so or so['customer_id'] != customer_id:
            return HttpResponse('Not found', status=404)
        items = get_so_items(conn, so_id)
        shipments = [s for s in list_my_shipments(conn, customer_id) if s['so_id'] == so_id]
    finally:
        conn.close()
    return render(request, 'portal_order_detail.html', _portal_ctx(
        request, so=so, items=items, shipments=shipments))


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@customer_login_required
def portal_invoices(request):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        invoices = list_ar_invoices(conn, customer_id=customer_id)
    finally:
        conn.close()
    return render(request, 'portal_invoices.html', _portal_ctx(request, invoices=invoices))


@customer_login_required
def portal_invoice_detail(request, inv_id):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        invoice = get_ar_invoice(conn, inv_id)
        if not invoice or invoice['customer_id'] != customer_id:
            return HttpResponse('Not found', status=404)
        payments = list_ar_payments(conn, inv_id)
    finally:
        conn.close()
    return render(request, 'portal_invoice_detail.html', _portal_ctx(
        request, invoice=invoice, payments=payments))


@customer_login_required
def portal_invoice_pdf(request, inv_id):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        invoice = get_ar_invoice(conn, inv_id)
        if not invoice or invoice['customer_id'] != customer_id:
            return HttpResponse('Not found', status=404)
        payments = list_ar_payments(conn, inv_id)
    finally:
        conn.close()
    pdf = render_invoice_pdf(invoice, payments)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{invoice["invoice_number"]}.pdf"'
    return resp


@customer_login_required
def portal_invoice_pay(request, inv_id):
    if request.method != 'POST':
        return redirect('portal_invoice_detail', inv_id=inv_id)
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        ensure_portal_tables(conn)
        conn.commit()
        invoice = get_ar_invoice(conn, inv_id)
        if not invoice or invoice['customer_id'] != customer_id:
            return HttpResponse('Not found', status=404)
        if invoice['balance'] <= 0:
            return redirect('portal_invoice_detail', inv_id=inv_id)
        intent = create_payment_intent(conn, inv_id, invoice['balance'])
        confirm_payment_intent(conn, intent['id'])
        conn.commit()
    finally:
        conn.close()
    return redirect('portal_invoice_detail', inv_id=inv_id)


# ---------------------------------------------------------------------------
# Shipments / tracking
# ---------------------------------------------------------------------------

@customer_login_required
def portal_shipment_detail(request, shipment_id):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        shipment = get_my_shipment(conn, customer_id, shipment_id)
        if not shipment:
            return HttpResponse('Not found', status=404)
        items = get_shipment_items(conn, shipment_id)
    finally:
        conn.close()
    events = get_tracking_events(shipment)
    return render(request, 'portal_shipment_detail.html', _portal_ctx(
        request, shipment=shipment, items=items, events=events))


@customer_login_required
def portal_packing_slip_pdf(request, shipment_id):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        shipment = get_my_shipment(conn, customer_id, shipment_id)
        if not shipment:
            return HttpResponse('Not found', status=404)
        items = get_shipment_items(conn, shipment_id)
    finally:
        conn.close()
    pdf = render_packing_slip_pdf(shipment, items)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{shipment["ship_number"]}-packing-slip.pdf"'
    return resp


# ---------------------------------------------------------------------------
# RMA
# ---------------------------------------------------------------------------

@customer_login_required
def portal_rma_list(request):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_rma_table(conn)
        conn.commit()
        rmas = list_my_rmas(conn, customer_id)
    finally:
        conn.close()
    return render(request, 'portal_rma_list.html', _portal_ctx(request, rmas=rmas))


@customer_login_required
def portal_rma_new(request):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_rma_table(conn)
        conn.commit()
        if request.method == 'POST':
            so_id = request.POST.get('so_id')
            reason = request.POST.get('reason', 'other')
            description = request.POST.get('description', '')
            try:
                rma_id = submit_rma(
                    conn, customer_id, int(so_id), reason, description,
                    request.session.get('portal_customer_email', ''))
                conn.commit()
            except (ValueError, TypeError) as e:
                orders = list_sos(conn, customer_id=customer_id)
                return render(request, 'portal_rma_new.html', _portal_ctx(
                    request, error=str(e), orders=orders,
                    reasons=RMA_REASONS))
            return redirect('portal_rma_detail', rma_id=rma_id)
        orders = list_sos(conn, customer_id=customer_id)
    finally:
        conn.close()
    return render(request, 'portal_rma_new.html', _portal_ctx(
        request, orders=orders, reasons=RMA_REASONS))


@customer_login_required
def portal_rma_detail(request, rma_id):
    customer_id = _my_customer_id(request)
    conn = get_db_connection()
    try:
        init_rma_table(conn)
        conn.commit()
        rma = get_my_rma(conn, customer_id, rma_id)
        if not rma:
            return HttpResponse('Not found', status=404)
    finally:
        conn.close()
    return render(request, 'portal_rma_detail.html', _portal_ctx(request, rma=rma))
