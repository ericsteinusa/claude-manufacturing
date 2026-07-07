"""Views: Warehouse Management System — bin master, put-away rules,
receiving put-away, pick lists, pack station, ship confirmation (P3-B)."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..wms_core import (
    ensure_wms_tables, PUTAWAY_MATCH_TYPES, PICK_LIST_STATUSES,
    get_or_create_default_warehouse,
    list_zones, create_zone,
    list_bins, get_bin, create_bin, deactivate_bin, get_bin_stock,
    list_putaway_rules, create_putaway_rule, delete_putaway_rule,
    suggest_putaway_bin, receive_and_putaway,
    list_confirmed_sos_awaiting_pick, generate_pick_list,
    list_pick_lists, get_pick_list, get_pick_list_lines, record_pick,
    create_carton, add_carton_item, set_carton_dimensions, close_carton,
    get_cartons_for_pick_list, get_carton_items, mark_pick_list_packed,
    confirm_shipment,
)
from ..purchase_orders_core import list_pos, get_po_items

log = get_logger(__name__)

_WMS_DEPT_KEYS = {'production', 'engineering', 'maintenance', 'purchasing'}


def _wms_ctx(request, **extra):
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


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Bin master
# ---------------------------------------------------------------------------

@dept_required(_WMS_DEPT_KEYS)
def wms_bin_list(request):
    zone_id = _int_or_none(request.GET.get('zone_id'))
    search = request.GET.get('q') or None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        bins = list_bins(conn, zone_id=zone_id, search=search)
        zones = list_zones(conn)
    finally:
        conn.close()
    return render(request, 'wms_bin_list.html', _wms_ctx(
        request, bins=bins, zones=zones, zone_id=zone_id, search=search or '',
    ))


@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_bin_list')
def wms_bin_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'create_zone':
                    wh_id = get_or_create_default_warehouse(conn)
                    create_zone(
                        conn, wh_id,
                        request.POST.get('code', ''),
                        request.POST.get('name', ''),
                        pick_sequence=_int_or_none(request.POST.get('pick_sequence')) or 0,
                    )
                elif action == 'create_bin':
                    create_bin(
                        conn, int(request.POST.get('zone_id')),
                        request.POST.get('aisle', ''),
                        request.POST.get('rack', ''),
                        request.POST.get('shelf', ''),
                        request.POST.get('bin_code', ''),
                    )
                conn.commit()
                return redirect('wms_bin_list')
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        zones = list_zones(conn)
    finally:
        conn.close()
    return render(request, 'wms_bin_new.html', _wms_ctx(request, zones=zones, error=error))


@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_bin_list')
def wms_bin_detail(request, bin_id):
    conn = get_db_connection()
    error = None
    try:
        ensure_wms_tables(conn)
        if request.method == 'POST' and request.POST.get('action') == 'deactivate':
            deactivate_bin(conn, bin_id)
            conn.commit()
            return redirect('wms_bin_list')
        bin_row = get_bin(conn, bin_id)
        if not bin_row:
            return redirect('wms_bin_list')
        stock = get_bin_stock(conn, bin_id)
    finally:
        conn.close()
    return render(request, 'wms_bin_detail.html', _wms_ctx(
        request, bin=bin_row, stock=stock, error=error,
    ))


# ---------------------------------------------------------------------------
# Put-away rules
# ---------------------------------------------------------------------------

@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_putaway_rule_list')
def wms_putaway_rule_list(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            try:
                if action == 'create':
                    create_putaway_rule(
                        conn, request.POST.get('match_type', ''),
                        request.POST.get('match_value', ''),
                        int(request.POST.get('zone_id')),
                        priority=_int_or_none(request.POST.get('priority')) or 0,
                    )
                elif action == 'delete':
                    delete_putaway_rule(conn, int(request.POST.get('rule_id')))
                conn.commit()
                return redirect('wms_putaway_rule_list')
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        rules = list_putaway_rules(conn)
        zones = list_zones(conn)
    finally:
        conn.close()
    return render(request, 'wms_putaway_rule_list.html', _wms_ctx(
        request, rules=rules, zones=zones, match_types=PUTAWAY_MATCH_TYPES, error=error,
    ))


# ---------------------------------------------------------------------------
# Receiving put-away
# ---------------------------------------------------------------------------

def _open_po_items(conn):
    """PO items still owed on sent/partial POs, with linked products only —
    free-text lines (no product_id) can't be put away automatically."""
    result = []
    for po in list_pos(conn, status='sent') + list_pos(conn, status='partial'):
        for item in get_po_items(conn, po['id']):
            if item['product_id'] and item['qty_received'] < item['qty_ordered']:
                item['po_id'] = po['id']
                item['po_number'] = po['po_number']
                result.append(item)
    return result


@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_receive')
def wms_receive(request):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        if request.method == 'POST':
            try:
                po_item_id = int(request.POST.get('po_item_id'))
                po_id = int(request.POST.get('po_id'))
                product_id = int(request.POST.get('product_id'))
                qty = float(request.POST.get('qty'))
                bin_id = _int_or_none(request.POST.get('bin_id'))
                if not bin_id:
                    bin_id = suggest_putaway_bin(conn, product_id)['bin_id']
                result = receive_and_putaway(
                    conn, po_item_id, po_id, product_id, qty, bin_id,
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = f"Received {result['received_qty']} and put away."
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        items = _open_po_items(conn)
        for item in items:
            item['qty_owed'] = item['qty_ordered'] - item['qty_received']
            item['suggested_bin'] = suggest_putaway_bin(conn, item['product_id'])
        bins = list_bins(conn)
    finally:
        conn.close()
    return render(request, 'wms_receive.html', _wms_ctx(
        request, items=items, bins=bins,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Pick lists
# ---------------------------------------------------------------------------

@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_pick_list_list')
def wms_pick_list_list(request):
    status = request.GET.get('status') or None
    error = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        if request.method == 'POST' and request.POST.get('action') == 'generate':
            try:
                so_id = int(request.POST.get('so_id'))
                pick_list_id = generate_pick_list(
                    conn, so_id, created_by=request.session.get('user_email', ''))
                conn.commit()
                return redirect('wms_pick_list_detail', pick_list_id=pick_list_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        awaiting = list_confirmed_sos_awaiting_pick(conn)
        pick_lists = list_pick_lists(conn, status=status)
    finally:
        conn.close()
    return render(request, 'wms_pick_list_list.html', _wms_ctx(
        request, awaiting=awaiting, pick_lists=pick_lists, status=status,
        pick_statuses=PICK_LIST_STATUSES, error=error,
    ))


@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_pick_list_list')
def wms_pick_list_detail(request, pick_list_id):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        if request.method == 'POST' and request.POST.get('action') == 'record_pick':
            try:
                line_id = int(request.POST.get('line_id'))
                qty_picked = float(request.POST.get('qty_picked'))
                record_pick(conn, line_id, qty_picked,
                           created_by=request.session.get('user_email', ''))
                conn.commit()
                success = 'Pick recorded.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        pick_list = get_pick_list(conn, pick_list_id)
        if not pick_list:
            return redirect('wms_pick_list_list')
        lines = get_pick_list_lines(conn, pick_list_id)
    finally:
        conn.close()
    return render(request, 'wms_pick_list_detail.html', _wms_ctx(
        request, pick_list=pick_list, lines=lines, error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Pack station
# ---------------------------------------------------------------------------

@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_pick_list_list')
def wms_pack_station(request, pick_list_id):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        pick_list = get_pick_list(conn, pick_list_id)
        if not pick_list:
            return redirect('wms_pick_list_list')

        if request.method == 'POST':
            action = request.POST.get('action', '')
            by = request.session.get('user_email', '')
            try:
                if action == 'create_carton':
                    create_carton(conn, pick_list_id, created_by=by)
                elif action == 'add_item':
                    add_carton_item(
                        conn, int(request.POST.get('carton_id')),
                        int(request.POST.get('line_id')),
                        float(request.POST.get('qty')),
                    )
                elif action == 'set_dims':
                    set_carton_dimensions(
                        conn, int(request.POST.get('carton_id')),
                        weight=_float_or_none(request.POST.get('weight')),
                        weight_uom=request.POST.get('weight_uom', 'lb'),
                        length=_float_or_none(request.POST.get('length')),
                        width=_float_or_none(request.POST.get('width')),
                        height=_float_or_none(request.POST.get('height')),
                        dim_uom=request.POST.get('dim_uom', 'in'),
                    )
                elif action == 'close_carton':
                    close_carton(conn, int(request.POST.get('carton_id')))
                elif action == 'mark_packed':
                    mark_pick_list_packed(conn, pick_list_id)
                conn.commit()
                success = 'Saved.'
                pick_list = get_pick_list(conn, pick_list_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)

        lines = get_pick_list_lines(conn, pick_list_id)
        cartons = get_cartons_for_pick_list(conn, pick_list_id)
        for carton in cartons:
            carton['items'] = get_carton_items(conn, carton['id'])
    finally:
        conn.close()
    return render(request, 'wms_pack_station.html', _wms_ctx(
        request, pick_list=pick_list, lines=lines, cartons=cartons,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Ship confirmation
# ---------------------------------------------------------------------------

@dept_required(_WMS_DEPT_KEYS, write_redirect='wms_pick_list_list')
def wms_ship_confirm(request, pick_list_id):
    error = None
    conn = get_db_connection()
    try:
        ensure_wms_tables(conn)
        pick_list = get_pick_list(conn, pick_list_id)
        if not pick_list:
            return redirect('wms_pick_list_list')

        if request.method == 'POST':
            try:
                confirm_shipment(
                    conn, pick_list_id,
                    request.POST.get('carrier', ''),
                    request.POST.get('tracking_number', ''),
                    request.POST.get('ship_date', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('wms_pick_list_detail', pick_list_id=pick_list_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        lines = get_pick_list_lines(conn, pick_list_id)
    finally:
        conn.close()
    return render(request, 'wms_ship_confirm.html', _wms_ctx(
        request, pick_list=pick_list, lines=lines, error=error,
    ))
