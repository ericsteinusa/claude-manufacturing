"""Views: e-Commerce Integration (P4-E) — storefront connection + item
cross-reference setup, order webhook receiver, on-demand inventory/price
sync, shipment-confirmation push, sync log."""

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..ecommerce_core import (
    ensure_ecommerce_tables, PLATFORMS, create_connection, update_connection,
    get_connection, list_connections, set_item_xref, list_item_xrefs,
    receive_order_webhook, push_inventory_level, push_price_update,
    push_shipment_confirmation, find_connection_for_so, list_sync_log,
)
from ..sales_orders_core import load_customers, load_products
from ..production_core import get_shipment
from ..price_list_core import ensure_price_list_tables, list_price_lists

log = get_logger(__name__)


def _ec_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required('sales')
def ecommerce_connection_list(request):
    conn = get_db_connection()
    try:
        ensure_ecommerce_tables(conn)
        conn.commit()
        connections = list_connections(conn)
    finally:
        conn.close()
    return render(request, 'ecommerce_connection_list.html', _ec_ctx(
        request, connections=connections))


@dept_required('sales', write_redirect='ecommerce_connection_list')
def ecommerce_connection_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_ecommerce_tables(conn)
        ensure_price_list_tables(conn)
        conn.commit()
        customers = load_customers(conn)
        price_lists = list_price_lists(conn)
        if request.method == 'POST':
            try:
                default_customer_id = request.POST.get('default_customer_id') or None
                default_price_list_id = request.POST.get('default_price_list_id') or None
                connection_id = create_connection(
                    conn,
                    request.POST.get('platform', ''),
                    request.POST.get('store_name', '').strip(),
                    request.POST.get('webhook_secret', '').strip(),
                    default_customer_id=int(default_customer_id) if default_customer_id else None,
                    default_price_list_id=int(default_price_list_id) if default_price_list_id else None,
                    sync_endpoint_url=request.POST.get('sync_endpoint_url', '').strip(),
                )
                conn.commit()
                return redirect('ecommerce_connection_detail', connection_id=connection_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'ecommerce_connection_new.html', _ec_ctx(
        request, customers=customers, price_lists=price_lists,
        platforms=PLATFORMS, error=error))


@dept_required('sales', write_redirect='ecommerce_connection_list')
def ecommerce_connection_detail(request, connection_id):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_ecommerce_tables(conn)
        conn.commit()
        connection = get_connection(conn, connection_id)
        products = load_products(conn)
        if request.method == 'POST':
            action = request.POST.get('action', 'xref')
            try:
                if action == 'endpoint':
                    update_connection(
                        conn, connection_id,
                        sync_endpoint_url=request.POST.get('sync_endpoint_url', '').strip(),
                    )
                    conn.commit()
                    success = 'Sync endpoint updated.'
                    connection = get_connection(conn, connection_id)
                elif action == 'sync_inventory':
                    product_id = int(request.POST.get('product_id'))
                    result = push_inventory_level(
                        conn, connection_id, product_id,
                        created_by=request.session.get('user_email', ''))
                    conn.commit()
                    success = f"Inventory sync: {result['status']} — {result['detail']}"
                elif action == 'sync_price':
                    product_id = int(request.POST.get('product_id'))
                    result = push_price_update(
                        conn, connection_id, product_id,
                        created_by=request.session.get('user_email', ''))
                    conn.commit()
                    success = f"Price sync: {result['status']} — {result['detail']}"
                else:
                    set_item_xref(
                        conn, connection_id,
                        request.POST.get('external_sku', '').strip(),
                        int(request.POST.get('product_id')),
                    )
                    conn.commit()
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e) or 'Select a product and enter an external SKU.'
        xrefs = list_item_xrefs(conn, connection_id)
    finally:
        conn.close()

    if not connection:
        return redirect('ecommerce_connection_list')

    webhook_url = request.build_absolute_uri(
        f'/ecommerce/webhook/{connection_id}/order/')
    return render(request, 'ecommerce_connection_detail.html', _ec_ctx(
        request, connection=connection, xrefs=xrefs, products=products,
        webhook_url=webhook_url, error=error, success=success))


@csrf_exempt
@require_http_methods(['POST'])
def ecommerce_order_webhook(request, connection_id):
    """Not dept-gated: the caller is an external storefront, not a logged-
    in user. HMAC signature verification (checked inside
    receive_order_webhook) is the auth here, in place of a session or
    Bearer token."""
    signature = (
        request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
        or request.META.get('HTTP_X_WC_WEBHOOK_SIGNATURE')
        or ''
    )
    conn = get_db_connection()
    try:
        ensure_ecommerce_tables(conn)
        conn.commit()
        result = receive_order_webhook(conn, connection_id, request.body, signature)
        if result.get('ok'):
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    if not result.get('ok'):
        status = 401 if 'signature' in result.get('error', '') else 400
        return JsonResponse(result, status=status)
    return JsonResponse(result)


@dept_required('sales')
def ecommerce_shipment_push(request, shipment_id):
    conn = get_db_connection()
    try:
        ensure_ecommerce_tables(conn)
        conn.commit()
        shipment = get_shipment(conn, shipment_id)
        connection_id = find_connection_for_so(conn, shipment['so_id']) if shipment and shipment.get('so_id') else None
        if connection_id:
            result = push_shipment_confirmation(
                conn, connection_id, shipment_id,
                created_by=request.session.get('user_email', ''))
            conn.commit()
            request.session['_ec_flash'] = f"Shipment push: {result['status']} — {result['detail']}"
        else:
            request.session['_ec_flash'] = "This shipment's sales order has no e-commerce origin."
    finally:
        conn.close()
    return redirect('prod_shipping_detail', shipment_id=shipment_id)


@dept_required('sales')
def ecommerce_sync_log_list(request):
    conn = get_db_connection()
    try:
        ensure_ecommerce_tables(conn)
        conn.commit()
        log_rows = list_sync_log(conn)
    finally:
        conn.close()
    return render(request, 'ecommerce_sync_log_list.html', _ec_ctx(
        request, log_rows=log_rows))
