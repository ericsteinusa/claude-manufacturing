"""Views: Blanket Purchase Orders & Call-offs (P3-E).

A blanket PO is a standalone standing-agreement record (vendor, ceiling,
validity window) — it is not nested under an existing ``purchase_order``,
so it gets its own top-level list/detail pages (same shape as the WMS/
capacity-planning features), with call-offs shown as a card inside the
blanket's own detail page.
"""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..blanket_po_core import (
    BLANKET_STATUSES, ensure_blanket_po_tables,
    list_blanket_pos, get_blanket_po, list_releases,
    create_blanket_po, create_release, cancel_blanket_po,
)
from ..purchase_orders_core import load_suppliers

log = get_logger(__name__)


def _bpo_ctx(request, **extra):
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
def blanket_po_list(request):
    status = request.GET.get('status') or None
    if status not in BLANKET_STATUSES:
        status = None
    supplier_id = _int_or_none(request.GET.get('supplier_id'))

    conn = get_db_connection()
    try:
        ensure_blanket_po_tables(conn)
        conn.commit()
        blankets = list_blanket_pos(conn, status=status, supplier_id=supplier_id)
        conn.commit()
        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    return render(request, 'blanket_po_list.html', _bpo_ctx(
        request,
        blankets=blankets,
        status=status,
        statuses=BLANKET_STATUSES,
        suppliers=suppliers,
        supplier_id=supplier_id,
        back_url='/po/',
    ))


@dept_required('purchasing', write_redirect='blanket_po_list')
def blanket_po_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_blanket_po_tables(conn)
        conn.commit()
        suppliers = load_suppliers(conn)
        if request.method == 'POST':
            try:
                bp_id = create_blanket_po(
                    conn,
                    supplier_id=_int_or_none(request.POST.get('supplier_id')),
                    description=request.POST.get('description', '').strip(),
                    total_value=_float_or_zero(request.POST.get('total_value')),
                    total_qty=_float_or_zero(request.POST.get('total_qty')),
                    start_date=request.POST.get('start_date', '').strip(),
                    end_date=request.POST.get('end_date', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('blanket_po_detail', blanket_po_id=bp_id)
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    return render(request, 'blanket_po_new.html', _bpo_ctx(
        request, suppliers=suppliers, error=error, form=request.POST if request.method == 'POST' else {},
        back_url='/blanket-po/',
    ))


@dept_required('purchasing')
def blanket_po_detail(request, blanket_po_id):
    conn = get_db_connection()
    try:
        ensure_blanket_po_tables(conn)
        conn.commit()
        bp = get_blanket_po(conn, blanket_po_id)
        conn.commit()
        releases = list_releases(conn, blanket_po_id) if bp else []
    finally:
        conn.close()

    if not bp:
        return redirect('blanket_po_list')

    return render(request, 'blanket_po_detail.html', _bpo_ctx(
        request, bp=bp, releases=releases, back_url='/blanket-po/',
    ))


@dept_required('purchasing', write_redirect='blanket_po_list')
def blanket_po_release_new(request, blanket_po_id):
    error = None
    conn = get_db_connection()
    try:
        ensure_blanket_po_tables(conn)
        conn.commit()
        bp = get_blanket_po(conn, blanket_po_id)
        conn.commit()
        if bp and request.method == 'POST':
            try:
                create_release(
                    conn, blanket_po_id,
                    qty=_float_or_zero(request.POST.get('qty')),
                    value=_float_or_zero(request.POST.get('value')),
                    delivery_date=request.POST.get('delivery_date', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('blanket_po_detail', blanket_po_id=blanket_po_id)
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    if not bp:
        return redirect('blanket_po_list')

    return render(request, 'blanket_po_release_new.html', _bpo_ctx(
        request, bp=bp, error=error, back_url='/blanket-po/%s/' % blanket_po_id,
    ))


@dept_required('purchasing', write_redirect='blanket_po_list')
def blanket_po_cancel(request, blanket_po_id):
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            ensure_blanket_po_tables(conn)
            conn.commit()
            try:
                cancel_blanket_po(conn, blanket_po_id)
                conn.commit()
            except ValueError:
                conn.rollback()
        finally:
            conn.close()
    return redirect('blanket_po_detail', blanket_po_id=blanket_po_id)
