"""Mobile JSON API views — mounted at /api/v1/ by urls.py.

All endpoints return {"ok": true/false, "data": ...} or {"ok": false, "error": ...}.
All mutating endpoints are @csrf_exempt (token auth is stateless).
"""
import json
import datetime

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .accounts import _verify_login, _get_user_profile
from .api_auth import ensure_api_token_table, create_token, revoke_token
from .api_decorators import api_err, api_ok, api_required
from .db_pg import get_db_connection
from .mrp_core import next_sequence_number
from . import (
    personnel_core,
    purchase_requisitions_core,
    reports_core,
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
    if not _verify_login(email, password):
        return api_err('Invalid email or password.', 401)
    profile = _get_user_profile(email)
    if not profile:
        return api_err('User profile not found.', 400)
    conn = get_db_connection()
    try:
        ensure_api_token_table(conn)
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
