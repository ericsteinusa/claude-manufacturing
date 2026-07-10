"""Views: Configure-to-Order (CTO)."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..cto_core import (
    ensure_cto_tables, create_option_group, add_option, list_option_groups,
    is_configurable, get_configuration, create_configuration, set_selection,
    is_configuration_complete, generate_configured_bom, release_configured_wo,
)
from ..bom_web_core import list_products, get_product
from ..sales_orders_core import ensure_so_tables
from ..work_orders_core import next_wo_number

log = get_logger(__name__)

_CTO_DEPT_KEYS = {'production', 'engineering'}


def _cto_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_CTO_DEPT_KEYS)
def cto_product_list(request):
    conn = get_db_connection()
    try:
        ensure_cto_tables(conn)
        products = list_products(conn, item_type='make')
        for p in products:
            p['is_configurable'] = is_configurable(conn, p['id'])
    finally:
        conn.close()
    return render(request, 'cto_product_list.html', _cto_ctx(request, products=products))


@dept_required(_CTO_DEPT_KEYS, write_redirect='cto_product_list')
def cto_options(request, product_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_cto_tables(conn)
        product = get_product(conn, product_id)
        if not product:
            return redirect('cto_product_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'add_group':
                    create_option_group(
                        conn, product_id, request.POST.get('name', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Option group added.'
                elif action == 'add_option':
                    add_option(
                        conn, int(request.POST['group_id']),
                        request.POST.get('name', '').strip(),
                        component_id=int(request.POST['component_id']),
                        qty_required=float(request.POST.get('qty_required') or 1.0),
                    )
                    conn.commit()
                    success = 'Option added.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        groups = list_option_groups(conn, product_id)
        components = [p for p in list_products(conn) if p['id'] != product_id]
    finally:
        conn.close()
    return render(request, 'cto_options.html', _cto_ctx(
        request, product=product, groups=groups, components=components,
        error=error, success=success,
    ))


@dept_required(_CTO_DEPT_KEYS, write_redirect='cto_product_list')
def cto_configure(request, so_item_id):
    conn = get_db_connection()
    error = success = None
    try:
        ensure_cto_tables(conn)
        ensure_so_tables(conn)
        item_row = conn.execute(
            "SELECT id, so_id, product_id, description FROM so_item WHERE id = %s",
            (so_item_id,),
        ).fetchone()
        if not item_row or not item_row['product_id']:
            return redirect('cto_product_list')
        item = dict(item_row)

        config_id_row = conn.execute(
            "SELECT id FROM cto_configuration WHERE so_item_id = %s", (so_item_id,)
        ).fetchone()
        if not config_id_row:
            config_id = create_configuration(
                conn, so_item_id, item['product_id'],
                created_by=request.session.get('user_email', ''),
            )
            conn.commit()
        else:
            config_id = config_id_row['id']

        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'select':
                    set_selection(
                        conn, config_id, int(request.POST['group_id']),
                        int(request.POST['option_id']),
                    )
                    conn.commit()
                    success = 'Selection saved.'
                elif action == 'release':
                    wo_number = next_wo_number(conn)
                    wo_id = release_configured_wo(
                        conn, so_item_id, wo_number,
                        quantity=float(request.POST.get('quantity') or 1),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('wo_detail', wo_id=wo_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        groups = list_option_groups(conn, item['product_id'])
        configuration = get_configuration(conn, so_item_id)
        complete = is_configuration_complete(conn, config_id, item['product_id'])
        resolved = generate_configured_bom(conn, so_item_id) if complete else []
    finally:
        conn.close()

    return render(request, 'cto_configure.html', _cto_ctx(
        request, item=item, groups=groups, configuration=configuration,
        complete=complete, resolved=resolved, error=error, success=success,
    ))
