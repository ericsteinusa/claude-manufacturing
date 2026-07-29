"""Mobile JSON API views — mounted at /api/v1/ by urls.py.

All endpoints return {"ok": true/false, "data": ...} or {"ok": false, "error": ...}.
All mutating endpoints are @csrf_exempt (token auth is stateless).
"""
import json
import datetime

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .accounts import _verify_login, _get_user_profile
from .api_auth import (
    ensure_api_token_table, create_token, revoke_token, refresh_token,
    record_login_attempt, is_rate_limited,
)
from .api_decorators import api_err, api_ok, api_required
from .db_pg import get_db_connection
from .mrp_core import next_sequence_number
from . import (
    approval_workflow_core,
    costing_core,
    inventory_core,
    lot_core,
    maintenance_core,
    personnel_core,
    purchase_requisitions_core,
    quality_core,
    reports_core,
    routing_core,
    time_clock_core,
    work_orders_core,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
def api_login(request):
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    email = body.get('email', '').strip().lower()
    password = body.get('password', '')
    if not email or not password:
        return api_err('email and password are required.')

    conn = get_db_connection()
    try:
        ensure_api_token_table(conn)
        if is_rate_limited(conn, email):
            return api_err('Too many failed attempts. Try again later.', 429)
        if not _verify_login(email, password):
            record_login_attempt(conn, email, success=False)
            conn.commit()
            return api_err('Invalid email or password.', 401)
        record_login_attempt(conn, email, success=True)
        profile = _get_user_profile(email)
        if not profile:
            conn.commit()
            return api_err('User profile not found.', 400)
        token = create_token(conn, profile['people_id'])
        conn.commit()
    finally:
        conn.close()
    role = profile.get('role_name', '')
    return api_ok({
        'token': token,
        'user': {
            'id': profile['people_id'],
            'email': email,
            'role': role,
            'dept_name': profile.get('dept_name', ''),
            'dept_key': profile.get('dept_key'),
            'full_access': role in {'President', 'Vice President'},
            'is_manager': role in {
                'Department Manager', 'Supervisor',
                'President', 'Vice President',
            },
        },
    })


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_refresh(request):
    """Extend the current token's expiry by TOKEN_LIFETIME_HOURS."""
    token = request.META.get('HTTP_AUTHORIZATION', '')[7:].strip()
    conn = get_db_connection()
    try:
        ok = refresh_token(conn, token)
        if not ok:
            return api_err('Token not found.', 404)
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': 'Token refreshed.'})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_logout(request):
    token = request.META.get('HTTP_AUTHORIZATION', '')[7:].strip()
    conn = get_db_connection()
    try:
        revoke_token(conn, token)
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': 'Logged out.'})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_profile(request):
    u = request.api_user
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, first_name, last_name, employee_id, email"
            " FROM people WHERE id = %s",
            (u['id'],),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return api_err('User not found.', 404)
    data = dict(row)
    data.update({k: u[k] for k in ('role', 'dept_name', 'dept_key',
                                    'full_access', 'is_manager')})
    return api_ok(data)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_dashboard(request):
    conn = get_db_connection()
    try:
        data = {
            'po':        reports_core.po_summary(conn),
            'wo':        reports_core.wo_summary(conn),
            'inventory': reports_core.inventory_alerts(conn),
            'cs':        reports_core.cs_summary(conn),
        }
    finally:
        conn.close()
    return api_ok(data)


# ---------------------------------------------------------------------------
# Time Clock
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_tc_status(request):
    conn = get_db_connection()
    try:
        entry = time_clock_core.get_current_entry(conn, request.api_user['id'])
    finally:
        conn.close()
    if entry:
        entry = time_clock_core._enrich(entry)
    return api_ok({'clocked_in': entry is not None, 'entry': entry})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_tc_clock_in(request):
    uid = request.api_user['id']
    conn = get_db_connection()
    try:
        if time_clock_core.get_current_entry(conn, uid):
            return api_err('Already clocked in.', 409)
        body = json.loads(request.body) if request.body else {}
        entry_id = time_clock_core.clock_in(
            conn, uid, notes=body.get('notes', ''), created_by='mobile'
        )
        conn.commit()
    finally:
        conn.close()
    return api_ok({'entry_id': entry_id, 'message': 'Clocked in.'}, status=201)


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_tc_clock_out(request):
    uid = request.api_user['id']
    conn = get_db_connection()
    try:
        entry = time_clock_core.get_current_entry(conn, uid)
        if not entry:
            return api_err('Not currently clocked in.', 409)
        time_clock_core.clock_out_entry(conn, entry['id'])
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': 'Clocked out.'})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_tc_hours(request):
    period = request.GET.get('period', 'week')
    date_from, date_to = time_clock_core.get_period_dates(period)
    conn = get_db_connection()
    try:
        entries = time_clock_core.list_entries(
            conn, request.api_user['id'], date_from, date_to
        )
    finally:
        conn.close()
    total_h, total_fmt = time_clock_core.total_hours(entries)
    return api_ok({
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'entries': entries,
        'total_hours': total_h,
        'total_hours_fmt': total_fmt,
    })


@csrf_exempt
@api_required
def api_time_off(request):
    uid = request.api_user['id']
    if request.method == 'GET':
        conn = get_db_connection()
        try:
            reqs = personnel_core.list_time_off_requests(conn, people_id=uid)
        finally:
            conn.close()
        return api_ok({
            'requests': reqs,
            'types': list(personnel_core.TIME_OFF_TYPES),
        })
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return api_err('Invalid JSON.')
        start = body.get('start_date', '').strip()
        end = body.get('end_date', '').strip()
        req_type = body.get('request_type', 'Vacation')
        if not start or not end:
            return api_err('start_date and end_date are required.')
        if req_type not in personnel_core.TIME_OFF_TYPES:
            return api_err(
                f'request_type must be one of: {", ".join(personnel_core.TIME_OFF_TYPES)}'
            )
        conn = get_db_connection()
        try:
            personnel_core.create_time_off_request(
                conn, uid, start, end,
                request_type=req_type,
                notes=body.get('notes', ''),
                created_by='mobile',
            )
            conn.commit()
        finally:
            conn.close()
        return api_ok({'message': 'Time-off request submitted.'}, status=201)
    return api_err('Method not allowed.', 405)


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_wo_list(request):
    status = request.GET.get('status') or None
    conn = get_db_connection()
    try:
        work_orders_core.ensure_wo_tables(conn)
        conn.commit()
        wos = work_orders_core.list_wos(conn, status=status)
    finally:
        conn.close()
    return api_ok({
        'work_orders': wos,
        'statuses': list(work_orders_core.WO_STATUSES),
        'status_colors': work_orders_core.WO_STATUS_COLORS,
    })


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_wo_detail(request, wo_id):
    conn = get_db_connection()
    try:
        wo = work_orders_core.get_wo(conn, wo_id)
        if wo is None:
            return api_err('Work order not found.', 404)
        materials = work_orders_core.get_wo_materials(conn, wo_id)
    finally:
        conn.close()
    wo['materials'] = materials
    wo['allowed_transitions'] = list(
        work_orders_core.allowed_transitions(wo['status'])
    )
    return api_ok({'work_order': wo})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_wo_status(request, wo_id):
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    new_status = body.get('status', '').strip()
    if not new_status:
        return api_err('status is required.')
    conn = get_db_connection()
    try:
        wo = work_orders_core.get_wo(conn, wo_id)
        if wo is None:
            return api_err('Work order not found.', 404)
        if not work_orders_core.can_transition(wo['status'], new_status):
            return api_err(
                f"Cannot move from '{wo['status']}' to '{new_status}'.", 400
            )
        conn.execute(
            "UPDATE work_order SET status = %s WHERE id = %s",
            (new_status, wo_id),
        )
        conn.commit()
    finally:
        conn.close()
    return api_ok({'status': new_status, 'message': f"Status updated to '{new_status}'."})


# ---------------------------------------------------------------------------
# Purchase Requisitions
# ---------------------------------------------------------------------------

@csrf_exempt
@api_required
def api_req(request):
    u = request.api_user

    if request.method == 'GET':
        conn = get_db_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS purchase_requisition (
                    id SERIAL PRIMARY KEY,
                    req_number TEXT NOT NULL UNIQUE,
                    requester_id INTEGER, dept_id INTEGER, dept_sub_id INTEGER,
                    needed_date TEXT, justification TEXT, purpose TEXT,
                    status TEXT DEFAULT 'draft', created_date TEXT,
                    po_id INTEGER, created_by TEXT, notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requisition_item (
                    id SERIAL PRIMARY KEY,
                    req_id INTEGER NOT NULL REFERENCES purchase_requisition(id),
                    description TEXT NOT NULL, product_id INTEGER,
                    qty INTEGER DEFAULT 1, est_unit_price REAL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requisition_approval (
                    id SERIAL PRIMARY KEY,
                    req_id INTEGER NOT NULL REFERENCES purchase_requisition(id),
                    level TEXT, approver_id INTEGER, decision TEXT,
                    comment TEXT, decided_date TEXT
                )
            """)
            for col, defn in [
                ('purpose',    'TEXT'),
                ('notes',      'TEXT'),
                ('created_by', 'TEXT'),
                ('dept_sub_id','INTEGER'),
                ('po_id',      'INTEGER'),
            ]:
                conn.execute(
                    f"ALTER TABLE purchase_requisition "
                    f"ADD COLUMN IF NOT EXISTS {col} {defn}"
                )
            conn.commit()
            sql = """
                SELECT pr.id, pr.req_number, pr.dept_id, pr.purpose,
                       pr.status, pr.notes, pr.created_by,
                       p.first_name || ' ' || p.last_name AS requester_name,
                       d.dept_name
                FROM purchase_requisition pr
                LEFT JOIN people p ON p.id = pr.requester_id
                LEFT JOIN dept d ON d.dept_id = pr.dept_id
            """
            params: list = []
            if not u['full_access']:
                if u['is_manager']:
                    sql += " WHERE pr.dept_id = %s"
                    params.append(u['dept_id'])
                else:
                    sql += " WHERE pr.requester_id = %s"
                    params.append(u['id'])
            sql += " ORDER BY pr.id DESC"
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return api_ok({'requisitions': [dict(r) for r in rows]})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return api_err('Invalid JSON.')
        purpose = body.get('purpose', '').strip()
        if not purpose:
            return api_err('purpose is required.')
        conn = get_db_connection()
        try:
            purchase_requisitions_core.ensure_requisition_tables(conn)
            year = datetime.date.today().year
            prefix = f'REQ-{year}-'
            existing = [
                r[0] for r in conn.execute(
                    "SELECT req_number FROM purchase_requisition"
                    " WHERE req_number LIKE %s",
                    (prefix + '%',),
                ).fetchall()
            ]
            req_number = next_sequence_number(existing, prefix)
            row = conn.execute(
                "INSERT INTO purchase_requisition"
                " (req_number, requester_id, dept_id, purpose,"
                "  status, notes, created_by)"
                " VALUES (%s, %s, %s, %s, 'draft', %s, %s)"
                " RETURNING id",
                (req_number, u['id'], u['dept_id'], purpose,
                 body.get('notes', ''), 'mobile'),
            ).fetchone()
            conn.commit()
        finally:
            conn.close()
        return api_ok(
            {'id': row[0], 'req_number': req_number,
             'message': 'Requisition created.'},
            status=201,
        )

    return api_err('Method not allowed.', 405)


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_req_add_item(request, req_id):
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    description = body.get('description', '').strip()
    if not description:
        return api_err('description is required.')
    u = request.api_user
    conn = get_db_connection()
    try:
        purchase_requisitions_core.ensure_requisition_tables(conn)
        req_row = conn.execute(
            "SELECT status, requester_id FROM purchase_requisition WHERE id = %s",
            (req_id,),
        ).fetchone()
        if not req_row:
            return api_err('Requisition not found.', 404)
        if req_row['status'] != 'draft':
            return api_err('Can only add items to draft requisitions.', 400)
        if req_row['requester_id'] != u['id'] and not u['full_access']:
            return api_err('Permission denied.', 403)
        row = conn.execute(
            "INSERT INTO requisition_item"
            " (req_id, description, quantity, unit_price, notes)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (req_id, description,
             body.get('quantity', 1),
             body.get('unit_price', 0.0),
             body.get('notes', '')),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    return api_ok({'id': row[0], 'message': 'Item added.'}, status=201)


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_req_submit(request, req_id):
    u = request.api_user
    conn = get_db_connection()
    try:
        purchase_requisitions_core.ensure_requisition_tables(conn)
        req_row = conn.execute(
            "SELECT status, requester_id FROM purchase_requisition WHERE id = %s",
            (req_id,),
        ).fetchone()
        if not req_row:
            return api_err('Requisition not found.', 404)
        if req_row['requester_id'] != u['id'] and not u['full_access']:
            return api_err('Permission denied.', 403)
        if req_row['status'] != 'draft':
            return api_err('Only draft requisitions can be submitted.', 400)
        conn.execute(
            "UPDATE purchase_requisition SET status = 'submitted' WHERE id = %s",
            (req_id,),
        )
        # Create configurable approval workflow steps if any rules are configured.
        total_row = conn.execute(
            "SELECT COALESCE(SUM(est_unit_price * qty), 0) AS total"
            " FROM requisition_item WHERE req_id = %s",
            (req_id,),
        ).fetchone()
        total = float(total_row['total']) if total_row else 0.0
        dept_row = conn.execute(
            "SELECT dept_key FROM dept WHERE dept_id ="
            " (SELECT dept_id FROM purchase_requisition WHERE id = %s)",
            (req_id,),
        ).fetchone()
        dept_key = dept_row['dept_key'] if dept_row else ''
        approval_workflow_core.ensure_approval_tables(conn)
        approval_workflow_core.submit_for_approval(
            conn, 'purchase_requisition', req_id, total, dept_key,
            requested_by=u.get('email', ''),
        )
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': 'Requisition submitted for approval.'})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_req_pending(request):
    u = request.api_user
    if not u['is_manager']:
        return api_err('Manager access required.', 403)
    conn = get_db_connection()
    try:
        purchase_requisitions_core.ensure_requisition_tables(conn)
        sql = """
            SELECT pr.id, pr.req_number, pr.dept_id, pr.purpose,
                   pr.status, pr.notes,
                   p.first_name || ' ' || p.last_name AS requester_name,
                   d.dept_name
            FROM purchase_requisition pr
            LEFT JOIN people p ON p.id = pr.requester_id
            LEFT JOIN dept d ON d.dept_id = pr.dept_id
            WHERE pr.status = 'submitted'
              AND pr.requester_id != %s
        """
        params: list = [u['id']]
        if not u['full_access']:
            sql += " AND pr.dept_id = %s"
            params.append(u['dept_id'])
        sql += " ORDER BY pr.id DESC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return api_ok({'requisitions': [dict(r) for r in rows]})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_req_decide(request, req_id):
    u = request.api_user
    if not u['is_manager']:
        return api_err('Manager access required.', 403)
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    decision = body.get('decision', '').strip()
    if decision not in ('approve', 'deny'):
        return api_err("decision must be 'approve' or 'deny'.")
    conn = get_db_connection()
    try:
        purchase_requisitions_core.ensure_requisition_tables(conn)
        req_row = conn.execute(
            "SELECT status, requester_id, dept_id"
            " FROM purchase_requisition WHERE id = %s",
            (req_id,),
        ).fetchone()
        if not req_row:
            return api_err('Requisition not found.', 404)
        is_own = req_row['requester_id'] == u['id']
        if not purchase_requisitions_core.can_authorize(
            u['role'], req_row['status'], req_row['dept_id'], u['dept_id'], is_own
        ):
            return api_err('Not authorized to decide on this requisition.', 403)
        new_status = 'dept_approved' if decision == 'approve' else 'dept_denied'
        conn.execute(
            "UPDATE purchase_requisition SET status = %s WHERE id = %s",
            (new_status, req_id),
        )
        conn.execute(
            "INSERT INTO requisition_approval"
            " (req_id, level, decision, approver_id, comment)"
            " VALUES (%s, 'dept', %s, %s, %s)",
            (req_id, decision, u['id'], body.get('comment', '')),
        )
        conn.commit()
    finally:
        conn.close()
    return api_ok({
        'status': new_status,
        'message': f"Requisition {decision}d.",
    })


# ---------------------------------------------------------------------------
# Dashboards  (5A)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_financial_dashboard(request):
    conn = get_db_connection()
    try:
        data = reports_core.financial_dashboard(conn)
    finally:
        conn.close()
    return api_ok(data)


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_production_dashboard(request):
    conn = get_db_connection()
    try:
        data = reports_core.production_dashboard(conn)
    finally:
        conn.close()
    return api_ok(data)


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_inventory_dashboard(request):
    conn = get_db_connection()
    try:
        data = reports_core.inventory_dashboard(conn)
    finally:
        conn.close()
    return api_ok(data)


# ---------------------------------------------------------------------------
# Inventory  (5C)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_inventory_list(request):
    search = request.GET.get('q') or None
    status = request.GET.get('status') or None
    conn = get_db_connection()
    try:
        products = inventory_core.list_products(conn, search=search,
                                                filter_status=status)
        alerts = inventory_core.get_alert_counts(conn)
    finally:
        conn.close()
    return api_ok({'products': products, 'alerts': alerts})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_inventory_receive(request):
    """Receive stock for a product. Optionally assigns / creates a lot."""
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    product_id = body.get('product_id')
    qty = body.get('qty')
    if not product_id or not qty:
        return api_err('product_id and qty are required.')
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return api_err('qty must be a number.')
    if qty <= 0:
        return api_err('qty must be positive.')

    conn = get_db_connection()
    try:
        new_qty = inventory_core.record_transaction(
            conn, int(product_id), 'receive', qty,
            reference=body.get('reference', ''),
            notes=body.get('notes', ''),
            created_by=request.api_user['email'],
        )
        conn.commit()
    finally:
        conn.close()
    return api_ok({'new_qty': new_qty, 'message': 'Stock received.'}, status=201)


# ---------------------------------------------------------------------------
# Quality — NCR  (5C)
# ---------------------------------------------------------------------------

@csrf_exempt
@api_required
def api_ncr(request):
    if request.method == 'GET':
        status_filter = request.GET.get('status') or None
        conn = get_db_connection()
        try:
            ncrs = quality_core.list_ncrs(conn, status=status_filter)
        finally:
            conn.close()
        return api_ok({'ncrs': ncrs})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return api_err('Invalid JSON.')
        title = body.get('title', '').strip()
        source = body.get('source', 'internal').strip()
        severity = body.get('severity', 'minor').strip()
        if not title:
            return api_err('title is required.')
        conn = get_db_connection()
        try:
            ncr_id = quality_core.create_ncr(
                conn,
                title=title,
                source=source,
                severity=severity,
                product=body.get('product', ''),
                lot_number=body.get('lot_number', ''),
                description=body.get('description', ''),
                created_by=request.api_user['email'],
            )
            conn.commit()
        finally:
            conn.close()
        return api_ok({'id': ncr_id, 'message': 'NCR created.'}, status=201)

    return api_err('Method not allowed.', 405)


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_ncr_detail(request, ncr_id):
    conn = get_db_connection()
    try:
        ncr = quality_core.get_ncr(conn, ncr_id)
    finally:
        conn.close()
    if not ncr:
        return api_err('NCR not found.', 404)
    return api_ok({'ncr': ncr})


# ---------------------------------------------------------------------------
# Maintenance Work Orders  (5C)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_maint_wo_list(request):
    status_filter = request.GET.get('status') or None
    conn = get_db_connection()
    try:
        wos = maintenance_core.list_work_orders(conn, status=status_filter)
    finally:
        conn.close()
    return api_ok({'work_orders': wos})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_maint_wo_detail(request, wo_id):
    conn = get_db_connection()
    try:
        wo = maintenance_core.get_work_order(conn, wo_id)
    finally:
        conn.close()
    if not wo:
        return api_err('Work order not found.', 404)
    return api_ok({'work_order': wo})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_maint_wo_complete(request, wo_id):
    conn = get_db_connection()
    try:
        wo = maintenance_core.get_work_order(conn, wo_id)
        if not wo:
            return api_err('Work order not found.', 404)
        if wo.get('status') == 'completed':
            return api_err('Work order is already completed.', 409)
        maintenance_core.complete_work_order(conn, wo_id)
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': 'Work order completed.'})


# ---------------------------------------------------------------------------
# Production WO Operations  (5C)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_wo_operations(request, wo_id):
    conn = get_db_connection()
    try:
        ops = routing_core.get_wo_operations(conn, wo_id)
        cost = routing_core.get_wo_labor_cost(conn, wo_id)
    finally:
        conn.close()
    return api_ok({'operations': ops, 'labor_cost': cost})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_wo_operation_complete(request, wo_id, seq):
    """Log actual hours and complete a WO operation step."""
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    actual_hours = body.get('actual_hours')
    if actual_hours is None:
        return api_err('actual_hours is required.')
    try:
        actual_hours = float(actual_hours)
    except (TypeError, ValueError):
        return api_err('actual_hours must be a number.')

    conn = get_db_connection()
    try:
        ops = routing_core.get_wo_operations(conn, wo_id)
        op = next((o for o in ops if o['operation_seq'] == int(seq)), None)
        if not op:
            return api_err(f'Operation seq {seq} not found on WO {wo_id}.', 404)
        if op['status'] == 'completed':
            return api_err('Operation is already completed.', 409)
        routing_core.complete_wo_operation(
            conn, op['id'],
            actual_hours=actual_hours,
            completed_by=request.api_user['email'],
            scrap_qty=float(body.get('scrap_qty', 0)),
            rework_qty=float(body.get('rework_qty', 0)),
            notes=body.get('notes', ''),
        )
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': f'Operation {seq} completed.'})


# ---------------------------------------------------------------------------
# Approval Workflow  (6B)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_workflow_pending(request):
    """Return pending approval steps for the current user's role."""
    u = request.api_user
    conn = get_db_connection()
    try:
        approval_workflow_core.ensure_approval_tables(conn)
        steps = approval_workflow_core.get_pending_steps(conn, approver_role=u['role'])
    finally:
        conn.close()
    return api_ok({'steps': steps})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_workflow_decide(request, step_id):
    """Approve or reject one approval workflow step."""
    u = request.api_user
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    decision = body.get('decision', '').strip()
    if decision not in ('approved', 'rejected'):
        return api_err("decision must be 'approved' or 'rejected'.")
    conn = get_db_connection()
    try:
        approval_workflow_core.ensure_approval_tables(conn)
        overall = approval_workflow_core.decide_step(
            conn, step_id, decision,
            decided_by=u.get('email', str(u['id'])),
            notes=body.get('notes', ''),
        )
        conn.commit()
    except ValueError as exc:
        conn.close()
        return api_err(str(exc), 400)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return api_ok({'overall': overall, 'message': f'Step {decision}.'})


# ---------------------------------------------------------------------------
# Lot tracking  (7A)
# ---------------------------------------------------------------------------

@csrf_exempt
@api_required
def api_lot_list(request):
    if request.method == 'GET':
        product_id = request.GET.get('product_id')
        status = request.GET.get('status') or None
        conn = get_db_connection()
        try:
            lot_core.ensure_lot_tables(conn)
            lots = lot_core.list_lots(
                conn,
                product_id=int(product_id) if product_id else None,
                status=status,
            )
        finally:
            conn.close()
        return api_ok({'lots': lots})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return api_err('Invalid JSON.')
        product_id = body.get('product_id')
        qty = body.get('qty')
        if not product_id or qty is None:
            return api_err('product_id and qty are required.')
        conn = get_db_connection()
        try:
            lot_core.ensure_lot_tables(conn)
            lot_id = lot_core.create_lot(
                conn,
                product_id=int(product_id),
                qty=float(qty),
                received_date=body.get('received_date'),
                expiry_date=body.get('expiry_date'),
                lot_number=body.get('lot_number') or None,
                notes=body.get('notes', ''),
                created_by=request.api_user.get('email', ''),
            )
            conn.commit()
        finally:
            conn.close()
        return api_ok({'id': lot_id, 'message': 'Lot created.'}, status=201)

    return api_err('Method not allowed.', 405)


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_lot_expiry(request):
    days = int(request.GET.get('days', 30))
    conn = get_db_connection()
    try:
        lot_core.ensure_lot_tables(conn)
        alerts = lot_core.get_expiry_alerts(conn, days_ahead=days)
    finally:
        conn.close()
    return api_ok({'alerts': alerts, 'days_ahead': days})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_lot_detail(request, lot_id):
    conn = get_db_connection()
    try:
        lot_core.ensure_lot_tables(conn)
        lot = lot_core.get_lot(conn, lot_id)
        if not lot:
            return api_err('Lot not found.', 404)
        genealogy = lot_core.get_lot_genealogy(conn, lot_id)
        serials = lot_core.list_serials(conn, lot_id=lot_id)
    finally:
        conn.close()
    return api_ok({'lot': lot, 'genealogy': genealogy, 'serials': serials})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_lot_status(request, lot_id):
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    status = body.get('status', '').strip()
    if not status:
        return api_err('status is required.')
    conn = get_db_connection()
    try:
        lot_core.ensure_lot_tables(conn)
        lot_core.update_lot_status(conn, lot_id, status,
                                   notes=body.get('notes', ''))
        conn.commit()
    except ValueError as exc:
        conn.close()
        return api_err(str(exc), 400)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return api_ok({'message': f'Lot status set to {status}.'})


@csrf_exempt
@api_required
def api_serial_list(request):
    if request.method == 'GET':
        product_id = request.GET.get('product_id')
        lot_id = request.GET.get('lot_id')
        status = request.GET.get('status') or None
        conn = get_db_connection()
        try:
            lot_core.ensure_lot_tables(conn)
            serials = lot_core.list_serials(
                conn,
                product_id=int(product_id) if product_id else None,
                lot_id=int(lot_id) if lot_id else None,
                status=status,
            )
        finally:
            conn.close()
        return api_ok({'serials': serials})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return api_err('Invalid JSON.')
        serial_number = (body.get('serial_number') or '').strip()
        product_id = body.get('product_id')
        if not serial_number or not product_id:
            return api_err('serial_number and product_id are required.')
        conn = get_db_connection()
        try:
            lot_core.ensure_lot_tables(conn)
            sid = lot_core.create_serial(
                conn,
                serial_number=serial_number,
                product_id=int(product_id),
                lot_id=int(body['lot_id']) if body.get('lot_id') else None,
                notes=body.get('notes', ''),
                created_by=request.api_user.get('email', ''),
            )
            conn.commit()
        finally:
            conn.close()
        return api_ok({'id': sid, 'message': 'Serial number created.'}, status=201)

    return api_err('Method not allowed.', 405)


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_serial_status(request, serial_id):
    try:
        body = json.loads(request.body)
    except Exception:
        return api_err('Invalid JSON.')
    status = body.get('status', '').strip()
    if not status:
        return api_err('status is required.')
    conn = get_db_connection()
    try:
        lot_core.ensure_lot_tables(conn)
        lot_core.update_serial_status(conn, serial_id, status,
                                      notes=body.get('notes', ''))
        conn.commit()
    except ValueError as exc:
        conn.close()
        return api_err(str(exc), 400)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return api_ok({'message': f'Serial status set to {status}.'})


# ---------------------------------------------------------------------------
# Routing — workcenters & product routing  (7A)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_workcenters(request):
    conn = get_db_connection()
    try:
        routing_core.ensure_routing_tables(conn)
        wcs = routing_core.list_workcenters(conn, active_only=False)
    finally:
        conn.close()
    return api_ok({'workcenters': wcs})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_product_routing(request, product_id):
    conn = get_db_connection()
    try:
        routing_core.ensure_routing_tables(conn)
        steps = routing_core.get_routing(conn, product_id)
    finally:
        conn.close()
    return api_ok({'product_id': product_id, 'steps': steps})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_wo_operation_start(request, wo_id, seq):
    conn = get_db_connection()
    try:
        routing_core.ensure_routing_tables(conn)
        ops = routing_core.get_wo_operations(conn, wo_id)
        op = next((o for o in ops if o['operation_seq'] == seq), None)
        if not op:
            return api_err('Operation not found.', 404)
        if op['status'] != 'pending':
            return api_err(f"Operation is already {op['status']}.", 400)
        routing_core.start_wo_operation(conn, op['id'])
        conn.commit()
    finally:
        conn.close()
    return api_ok({'message': f'Operation {seq} started.'})


# ---------------------------------------------------------------------------
# Costing  (7A)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_product_cost(request, product_id):
    conn = get_db_connection()
    try:
        costing_core.ensure_costing_tables(conn)
        cost = costing_core.get_standard_cost(conn, product_id)
    finally:
        conn.close()
    if not cost:
        return api_err('No standard cost on record for this product.', 404)
    return api_ok({'cost': cost})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_cost_roll(request, product_id):
    conn = get_db_connection()
    try:
        costing_core.ensure_costing_tables(conn)
        result = costing_core.roll_standard_cost(
            conn, product_id,
            created_by=request.api_user.get('email', ''),
        )
        conn.commit()
    except Exception as exc:
        conn.close()
        return api_err(str(exc), 400)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return api_ok({'cost': result, 'message': 'Standard cost rolled.'})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_cost_history(request, product_id):
    conn = get_db_connection()
    try:
        costing_core.ensure_costing_tables(conn)
        history = costing_core.list_cost_history(conn, product_id)
    finally:
        conn.close()
    return api_ok({'history': history})


@csrf_exempt
@require_http_methods(['GET'])
@api_required
def api_wo_cost(request, wo_id):
    conn = get_db_connection()
    try:
        costing_core.ensure_costing_tables(conn)
        cost = costing_core.get_wo_cost(conn, wo_id)
    finally:
        conn.close()
    if not cost:
        return api_err('No cost record for this work order yet.', 404)
    return api_ok({'cost': cost})


@csrf_exempt
@require_http_methods(['POST'])
@api_required
def api_wo_cost_compute(request, wo_id):
    conn = get_db_connection()
    try:
        costing_core.ensure_costing_tables(conn)
        result = costing_core.save_wo_actual_cost(
            conn, wo_id,
            created_by=request.api_user.get('email', ''),
        )
        conn.commit()
    except Exception as exc:
        conn.close()
        return api_err(str(exc), 400)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return api_ok({'cost': result, 'message': 'WO actual cost computed.'})


@csrf_exempt
@api_required
def api_gl_accounts(request):
    if request.method == 'GET':
        conn = get_db_connection()
        try:
            costing_core.ensure_costing_tables(conn)
            accounts = costing_core.list_gl_account_map(conn)
        finally:
            conn.close()
        return api_ok({'accounts': accounts})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return api_err('Invalid JSON.')
        category = (body.get('category') or '').strip()
        account_number = (body.get('account_number') or '').strip()
        if not category or not account_number:
            return api_err('category and account_number are required.')
        conn = get_db_connection()
        try:
            costing_core.ensure_costing_tables(conn)
            costing_core.set_gl_account_map(
                conn, category, account_number,
                description=body.get('description', ''),
            )
            conn.commit()
        except ValueError as exc:
            conn.close()
            return api_err(str(exc), 400)
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return api_ok({'message': f'GL account {category} → {account_number} saved.'})

    return api_err('Method not allowed.', 405)
