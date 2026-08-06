"""Views: Supplier Self-Service Portal.

A separate, non-employee login: every view here is gated by
supplier_login_required (session key 'portal_supplier_id', not the employee
'user_*' keys, and separate from the customer portal's 'portal_customer_id')
plus an explicit ownership check on every detail view, same pattern as
views/_portal.py (customer portal).
"""

from django.shortcuts import render, redirect
from django.http import HttpResponse

from ..db_pg import get_db_connection
from ..auth_decorators import supplier_login_required
from ..log_utils import get_logger

from ..supplier_portal_core import (
    ensure_supplier_portal_tables, register_supplier_login, verify_supplier_login,
    list_my_pos, get_my_po, acknowledge_po,
    list_my_invoices, get_my_invoice, submit_invoice,
    list_my_rfqs, get_my_rfq, submit_quote,
    get_portal_dashboard,
)
from ..purchase_orders_core import ensure_po_tables, get_po_items
from ..rfq_core import ensure_rfq_tables

log = get_logger(__name__)


def _portal_ctx(request, **extra):
    ctx = {
        'portal_email': request.session.get('portal_supplier_email', ''),
        'portal_company': request.session.get('portal_supplier_company', ''),
    }
    ctx.update(extra)
    return ctx


def _my_supplier_id(request):
    return request.session.get('portal_supplier_id')


# ---------------------------------------------------------------------------
# Register / login / logout
# ---------------------------------------------------------------------------

def supplier_portal_register(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        conn = get_db_connection()
        try:
            ensure_supplier_portal_tables(conn)
            conn.commit()
            try:
                register_supplier_login(conn, email, password)
                conn.commit()
            except ValueError as e:
                return render(request, 'supplier_portal_register.html', {
                    'error': str(e), 'email_value': email,
                })
            return redirect('supplier_portal_login')
        finally:
            conn.close()
    return render(request, 'supplier_portal_register.html', {})


def supplier_portal_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        conn = get_db_connection()
        try:
            ensure_supplier_portal_tables(conn)
            conn.commit()
            profile = verify_supplier_login(conn, email, password)
        finally:
            conn.close()
        if profile:
            request.session['portal_supplier_id'] = profile['supplier_id']
            request.session['portal_supplier_email'] = profile['email']
            request.session['portal_supplier_company'] = profile['display_name']
            return redirect('supplier_portal_home')
        return render(request, 'supplier_portal_login.html', {
            'error': 'Invalid email or password.', 'email_value': email,
        })
    if _my_supplier_id(request):
        return redirect('supplier_portal_home')
    return render(request, 'supplier_portal_login.html', {})


def supplier_portal_logout(request):
    # Pop only this portal's own keys — see portal_logout in views/_portal.py
    # for why session.flush() is wrong here.
    for key in ('portal_supplier_id', 'portal_supplier_email', 'portal_supplier_company'):
        request.session.pop(key, None)
    request.session.cycle_key()
    return redirect('supplier_portal_login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@supplier_login_required
def supplier_portal_home(request):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    try:
        ensure_po_tables(conn)
        ensure_supplier_portal_tables(conn)
        ensure_rfq_tables(conn)
        conn.commit()
        dashboard = get_portal_dashboard(conn, supplier_id)
        pos = list_my_pos(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'supplier_portal_home.html', _portal_ctx(
        request, dashboard=dashboard, pos=pos[:8],
    ))


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

@supplier_login_required
def supplier_portal_pos(request):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    try:
        pos = list_my_pos(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'supplier_portal_pos.html', _portal_ctx(request, pos=pos))


@supplier_login_required
def supplier_portal_po_detail(request, po_id):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    error = success = None
    try:
        ensure_supplier_portal_tables(conn)
        conn.commit()
        po = get_my_po(conn, supplier_id, po_id)
        if not po:
            return HttpResponse('Not found', status=404)

        if request.method == 'POST' and request.POST.get('action') == 'acknowledge':
            try:
                acknowledge_po(conn, supplier_id, po_id, notes=request.POST.get('notes', '').strip())
                conn.commit()
                success = 'Order acknowledged.'
            except ValueError as e:
                conn.rollback()
                error = str(e)
            po = get_my_po(conn, supplier_id, po_id)

        items = get_po_items(conn, po_id)
    finally:
        conn.close()
    return render(request, 'supplier_portal_po_detail.html', _portal_ctx(
        request, po=po, items=items, error=error, success=success))


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@supplier_login_required
def supplier_portal_invoices(request):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    try:
        invoices = list_my_invoices(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'supplier_portal_invoices.html', _portal_ctx(request, invoices=invoices))


@supplier_login_required
def supplier_portal_invoice_detail(request, inv_id):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    try:
        invoice = get_my_invoice(conn, supplier_id, inv_id)
        if not invoice:
            return HttpResponse('Not found', status=404)
    finally:
        conn.close()
    return render(request, 'supplier_portal_invoice_detail.html', _portal_ctx(request, invoice=invoice))


@supplier_login_required
def supplier_portal_invoice_new(request):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    error = None
    try:
        if request.method == 'POST':
            try:
                inv_id = submit_invoice(
                    conn, supplier_id,
                    request.POST.get('po_id') or None,
                    request.POST.get('invoice_number', '').strip(),
                    request.POST.get('invoice_date', '').strip(),
                    request.POST.get('due_date', '').strip(),
                    float(request.POST.get('amount') or 0),
                    request.POST.get('description', '').strip(),
                    request.session.get('portal_supplier_email', ''),
                )
                conn.commit()
                return redirect('supplier_portal_invoice_detail', inv_id=inv_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
        pos = list_my_pos(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'supplier_portal_invoice_new.html', _portal_ctx(
        request, pos=pos, error=error, po_id_value=request.GET.get('po_id', '')))


# ---------------------------------------------------------------------------
# RFQs
# ---------------------------------------------------------------------------

@supplier_login_required
def supplier_portal_rfqs(request):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    try:
        ensure_rfq_tables(conn)
        conn.commit()
        rfqs = list_my_rfqs(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'supplier_portal_rfqs.html', _portal_ctx(request, rfqs=rfqs))


@supplier_login_required
def supplier_portal_rfq_detail(request, rfq_id):
    supplier_id = _my_supplier_id(request)
    conn = get_db_connection()
    error = success = None
    try:
        ensure_rfq_tables(conn)
        conn.commit()
        if request.method == 'POST':
            try:
                submit_quote(
                    conn, supplier_id, int(request.POST['rfq_item_id']),
                    float(request.POST.get('quoted_price') or 0),
                    lead_time_days=int(request.POST['lead_time_days'])
                        if request.POST.get('lead_time_days') else None,
                )
                conn.commit()
                success = 'Quote submitted.'
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)

        rfq = get_my_rfq(conn, supplier_id, rfq_id)
        if not rfq:
            return HttpResponse('Not found', status=404)
    finally:
        conn.close()
    return render(request, 'supplier_portal_rfq_detail.html', _portal_ctx(
        request, rfq=rfq, error=error, success=success))
