"""Views: discount & promotion management, mirroring _price_list.py."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..discount_core import (
    ensure_discount_tables, list_promotions, get_promotion,
    create_promotion, update_promotion, DISCOUNT_TYPES,
)
from ..sales_orders_core import load_products
from ..contacts_core import list_customers

log = get_logger(__name__)

_PROMO_DEPT_KEYS = {'sales', 'accounting'}


def _promo_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'discount_types': DISCOUNT_TYPES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_PROMO_DEPT_KEYS)
def promo_list(request):
    conn = get_db_connection()
    try:
        ensure_discount_tables(conn)
        promotions = list_promotions(conn, search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'promo_list.html', _promo_ctx(
        request, promotions=promotions, q=request.GET.get('q', ''),
    ))


@dept_required(_PROMO_DEPT_KEYS, write_redirect='promo_list')
def promo_new(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_discount_tables(conn)
        products = load_products(conn)
        customers = list_customers(conn)
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            if not name:
                error = 'Name is required.'
            else:
                try:
                    promo_id = create_promotion(
                        conn, name,
                        discount_type=request.POST.get('discount_type', 'percent'),
                        discount_value=float(request.POST.get('discount_value', 0) or 0),
                        product_id=int(request.POST['product_id']) if request.POST.get('product_id') else None,
                        customer_id=int(request.POST['customer_id']) if request.POST.get('customer_id') else None,
                        min_qty=float(request.POST.get('min_qty', 1) or 1),
                        start_date=request.POST.get('start_date') or None,
                        end_date=request.POST.get('end_date') or None,
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('promo_detail', promo_id=promo_id)
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'promo_new.html', _promo_ctx(
        request, products=products, customers=customers, error=error,
    ))


@dept_required(_PROMO_DEPT_KEYS, write_redirect='promo_list')
def promo_detail(request, promo_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_discount_tables(conn)
        promotion = get_promotion(conn, promo_id)
        if not promotion:
            return redirect('promo_list')

        if request.method == 'POST':
            try:
                update_promotion(
                    conn, promo_id,
                    name=request.POST.get('name', '').strip(),
                    discount_type=request.POST.get('discount_type', 'percent'),
                    discount_value=float(request.POST.get('discount_value', 0) or 0),
                    product_id=int(request.POST['product_id']) if request.POST.get('product_id') else None,
                    customer_id=int(request.POST['customer_id']) if request.POST.get('customer_id') else None,
                    min_qty=float(request.POST.get('min_qty', 1) or 1),
                    start_date=request.POST.get('start_date') or None,
                    end_date=request.POST.get('end_date') or None,
                    is_active=request.POST.get('is_active') == '1',
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Promotion updated.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            promotion = get_promotion(conn, promo_id)

        products = load_products(conn)
        customers = list_customers(conn)
    finally:
        conn.close()

    return render(request, 'promo_detail.html', _promo_ctx(
        request, promotion=promotion, products=products, customers=customers,
        error=error, success=success,
    ))
