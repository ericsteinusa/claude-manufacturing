"""Views: sales price list admin (P1-E)."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..price_list_core import (
    ensure_price_list_tables, list_price_lists, get_price_list,
    create_price_list, update_price_list, list_price_list_lines,
    add_price_list_line, update_price_list_line, delete_price_list_line,
)
from ..sales_orders_core import load_products
from ..currency_core import init_currency_schema, list_currencies

log = get_logger(__name__)

_PL_DEPT_KEYS = {'sales', 'accounting'}


def _pl_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_PL_DEPT_KEYS)
def pl_list(request):
    conn = get_db_connection()
    try:
        ensure_price_list_tables(conn)
        price_lists = list_price_lists(conn)
    finally:
        conn.close()
    return render(request, 'pl_list.html', _pl_ctx(
        request, price_lists=price_lists,
    ))


@dept_required(_PL_DEPT_KEYS, write_redirect='pl_list')
def pl_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_price_list_tables(conn)
        init_currency_schema(conn)
        currencies = list_currencies(conn, active_only=True)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    pl_id = create_price_list(
                        conn, name,
                        currency=request.POST.get('currency', 'USD'),
                        effective_date=request.POST.get('effective_date') or None,
                        expiry_date=request.POST.get('expiry_date') or None,
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('pl_detail', pl_id=pl_id)
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'pl_new.html', _pl_ctx(
        request, currencies=currencies, error=error,
    ))


@dept_required(_PL_DEPT_KEYS, write_redirect='pl_list')
def pl_detail(request, pl_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_price_list_tables(conn)
        init_currency_schema(conn)
        price_list = get_price_list(conn, pl_id)
        if not price_list:
            return redirect('pl_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_line':
                    add_price_list_line(
                        conn, pl_id,
                        product_id=int(request.POST.get('product_id')),
                        unit_price=float(request.POST.get('unit_price', 0) or 0),
                        min_qty=float(request.POST.get('min_qty', 1) or 1),
                    )
                    conn.commit()
                    success = 'Line added.'
                elif action == 'update_line':
                    update_price_list_line(
                        conn, int(request.POST.get('line_id')),
                        unit_price=float(request.POST.get('unit_price', 0) or 0),
                        min_qty=float(request.POST.get('min_qty', 1) or 1),
                    )
                    conn.commit()
                    success = 'Line updated.'
                elif action == 'delete_line':
                    delete_price_list_line(conn, int(request.POST.get('line_id')))
                    conn.commit()
                    success = 'Line removed.'
                elif action == 'update_header':
                    update_price_list(
                        conn, pl_id,
                        name=request.POST.get('name', '').strip(),
                        currency=request.POST.get('currency', 'USD'),
                        effective_date=request.POST.get('effective_date') or None,
                        expiry_date=request.POST.get('expiry_date') or None,
                        is_active=request.POST.get('is_active') == '1',
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Price list updated.'
            except Exception as exc:
                conn.rollback()
                error = str(exc)
            price_list = get_price_list(conn, pl_id)

        lines = list_price_list_lines(conn, pl_id)
        products = load_products(conn)
        currencies = list_currencies(conn, active_only=True)
    finally:
        conn.close()

    return render(request, 'pl_detail.html', _pl_ctx(
        request, price_list=price_list, lines=lines, products=products,
        currencies=currencies, error=error, success=success,
    ))
