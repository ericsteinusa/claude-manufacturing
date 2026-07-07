"""Views: EDI Integration (P4-D) — trading partner + item cross-reference
setup, 850 upload (auto-creates a Sales Order), 855/856/810 download."""

from django.http import HttpResponse
from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..edi_core import (
    ensure_edi_tables, set_trading_partner, get_trading_partner,
    list_trading_partners, set_item_xref, list_item_xrefs,
    create_so_from_850, generate_855, generate_856, generate_810,
    list_transaction_log,
)
from ..sales_orders_core import load_products

log = get_logger(__name__)


def _edi_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def _load_customers(conn):
    rows = conn.execute(
        "SELECT id, company_name, first_name, last_name FROM customer ORDER BY company_name"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        company = d.get('company_name') or ''
        name = f"{d.get('first_name') or ''} {d.get('last_name') or ''}".strip()
        out.append({'id': d['id'], 'label': company if company else name})
    return out


@dept_required('sales')
def edi_partner_list(request):
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        partners = list_trading_partners(conn)
    finally:
        conn.close()
    return render(request, 'edi_partner_list.html', _edi_ctx(request, partners=partners))


@dept_required('sales', write_redirect='edi_partner_list')
def edi_partner_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        customers = _load_customers(conn)
        if request.method == 'POST':
            try:
                customer_id = int(request.POST.get('customer_id'))
                set_trading_partner(
                    conn, customer_id,
                    request.POST.get('partner_name', '').strip(),
                    request.POST.get('isa_sender_id', '').strip(),
                    request.POST.get('isa_receiver_id', '').strip(),
                )
                conn.commit()
                return redirect('edi_partner_detail', customer_id=customer_id)
            except (TypeError, ValueError):
                error = 'Select a customer.'
    finally:
        conn.close()
    return render(request, 'edi_partner_new.html', _edi_ctx(
        request, customers=customers, error=error))


@dept_required('sales', write_redirect='edi_partner_list')
def edi_partner_detail(request, customer_id):
    error = None
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        partner = get_trading_partner(conn, customer_id)
        products = load_products(conn)
        if request.method == 'POST':
            try:
                set_item_xref(
                    conn, customer_id,
                    request.POST.get('partner_item_number', '').strip(),
                    int(request.POST.get('product_id')),
                )
                conn.commit()
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e) or 'Select a product and enter a partner item number.'
        xrefs = list_item_xrefs(conn, customer_id)
    finally:
        conn.close()

    if not partner:
        return redirect('edi_partner_list')

    return render(request, 'edi_partner_detail.html', _edi_ctx(
        request, partner=partner, xrefs=xrefs, products=products, error=error))


@dept_required('sales', write_redirect='edi_partner_list')
def edi_850_upload(request):
    error = result = None
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        customers = _load_customers(conn)
        if request.method == 'POST':
            upload = request.FILES.get('file')
            try:
                customer_id = int(request.POST.get('customer_id'))
                if not upload:
                    raise ValueError('Choose an EDI 850 file to upload.')
                raw_edi = upload.read().decode('utf-8', errors='replace')
                result = create_so_from_850(
                    conn, customer_id, raw_edi,
                    request.session.get('user_email', ''),
                )
                conn.commit()
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'edi_850_upload.html', _edi_ctx(
        request, customers=customers, error=error, result=result))


@dept_required('sales')
def edi_855_download(request, so_id):
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        content = generate_855(conn, so_id, request.session.get('user_email', ''))
        conn.commit()
    finally:
        conn.close()
    resp = HttpResponse(content, content_type='text/plain')
    resp['Content-Disposition'] = f'attachment; filename="855_SO_{so_id}.edi"'
    return resp


@dept_required('sales')
def edi_856_download(request, shipment_id):
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        content = generate_856(conn, shipment_id, request.session.get('user_email', ''))
        conn.commit()
    finally:
        conn.close()
    resp = HttpResponse(content, content_type='text/plain')
    resp['Content-Disposition'] = f'attachment; filename="856_SHIPMENT_{shipment_id}.edi"'
    return resp


@dept_required('sales')
def edi_810_download(request, invoice_id):
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        content = generate_810(conn, invoice_id, request.session.get('user_email', ''))
        conn.commit()
    finally:
        conn.close()
    resp = HttpResponse(content, content_type='text/plain')
    resp['Content-Disposition'] = f'attachment; filename="810_INVOICE_{invoice_id}.edi"'
    return resp


@dept_required('sales')
def edi_transaction_log_list(request):
    conn = get_db_connection()
    try:
        ensure_edi_tables(conn)
        conn.commit()
        log_rows = list_transaction_log(conn)
    finally:
        conn.close()
    return render(request, 'edi_transaction_log_list.html', _edi_ctx(
        request, log_rows=log_rows))
