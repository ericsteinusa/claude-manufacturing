"""Tests for api_views — mobile JSON API view functions (/api/v1/...).

Needs Django settings bootstrapped (see conftest.py). Views are called
directly with a RequestFactory-built request, bypassing urls.py — the same
"import and call the function directly" style used for *_core.py modules
elsewhere in this suite.

get_db_connection is patched at the api_views-module name it was imported
into, with a fake connection. The *_core / api_auth / accounts functions
each view delegates to are patched too (also at their api_views-module
names) so these tests pin down api_views' own glue logic — request
parsing, auth-header handling, status codes, and response shaping — not
the already-separately-tested logic inside api_auth_core/accounts/etc.

Currently covers the Auth group (api_login, api_refresh, api_logout,
api_profile), the Dashboards group (api_dashboard,
api_financial_dashboard, api_production_dashboard,
api_inventory_dashboard), the Time Clock group (api_tc_status,
api_tc_clock_in, api_tc_clock_out, api_tc_hours, api_time_off), and the
Work Orders group (api_wo_list, api_wo_detail, api_wo_status,
api_wo_operations, api_wo_operation_complete, api_wo_operation_start),
the Requisitions group (api_req, api_req_add_item, api_req_submit,
api_req_pending, api_req_decide), the Inventory group
(api_inventory_list, api_inventory_receive), the Quality group
(api_ncr, api_ncr_detail), the Maintenance group (api_maint_wo_list,
api_maint_wo_detail, api_maint_wo_complete), the Approval Workflow
group (api_workflow_pending, api_workflow_decide), and the
Lots/Serials group (api_lot_list, api_lot_expiry, api_lot_detail,
api_lot_status, api_serial_list, api_serial_status); other endpoint
groups (workcenters/routing, costing) are a separate follow-up.
"""
import json

from unittest.mock import patch

from django.test import RequestFactory

from manufacturing.api_views import (
    api_login, api_refresh, api_logout, api_profile,
    api_dashboard, api_financial_dashboard, api_production_dashboard,
    api_inventory_dashboard,
    api_tc_status, api_tc_clock_in, api_tc_clock_out, api_tc_hours,
    api_time_off,
    api_wo_list, api_wo_detail, api_wo_status,
    api_wo_operations, api_wo_operation_complete, api_wo_operation_start,
    api_req, api_req_add_item, api_req_submit, api_req_pending, api_req_decide,
    api_inventory_list, api_inventory_receive,
    api_ncr, api_ncr_detail,
    api_maint_wo_list, api_maint_wo_detail, api_maint_wo_complete,
    api_workflow_pending, api_workflow_decide,
    api_lot_list, api_lot_expiry, api_lot_detail, api_lot_status,
    api_serial_list, api_serial_status,
)
from manufacturing import (
    reports_core, time_clock_core, personnel_core,
    work_orders_core, routing_core,
    purchase_requisitions_core, approval_workflow_core,
    inventory_core, quality_core, maintenance_core,
    cycle_count_core, document_control_core, lot_core,
)


rf = RequestFactory()


class _FakeConn:
    def __init__(self, rows=None):
        self.calls = []
        self.committed = False
        self.closed = False
        self._rows = rows if rows is not None else []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class _QCursor:
    def __init__(self, rows):
        self._rows = rows if rows is not None else []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _QueueConn:
    """Returns each queued row-set in order across successive execute()
    calls, regardless of SQL content — for view bodies that issue several
    different queries per request with different row shapes (e.g. a dict
    row from a SELECT, then a tuple row from an INSERT ... RETURNING)."""
    def __init__(self, responses):
        self._queue = list(responses)
        self.calls = []
        self.committed = False
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        rows = self._queue.pop(0) if self._queue else None
        return _QCursor(rows)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _post(path, body):
    return rf.post(path, data=json.dumps(body), content_type='application/json')


def _auth_get(path, token='goodtoken'):
    return rf.get(path, HTTP_AUTHORIZATION=f'Bearer {token}')


def _auth_post(path, token='goodtoken'):
    return rf.post(path, HTTP_AUTHORIZATION=f'Bearer {token}')


def _auth_post_json(path, body=None, token='goodtoken'):
    kwargs = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
    if body is not None:
        kwargs['data'] = json.dumps(body)
        kwargs['content_type'] = 'application/json'
    return rf.post(path, **kwargs)


def _auth_post_empty_body(path, token='goodtoken'):
    """A POST with a genuinely empty request.body — plain rf.post() without
    data still encodes an (empty) multipart form, which is non-empty bytes."""
    return rf.post(path, data=b'', content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {token}')


def _decorator_auth(user):
    """Patch the @api_required decorator's own DB/token-verification calls
    (looked up in api_decorators' namespace, not api_views') so tests for
    the three @api_required-wrapped views below (api_refresh, api_logout,
    api_profile) don't hit a real DB just to get past the decorator."""
    return patch.multiple(
        'manufacturing.api_decorators',
        get_db_connection=lambda: _FakeConn(),
        ensure_api_token_table=lambda c: None,
        verify_token=lambda c, token: user,
    )


_PROFILE = {
    'people_id': 42, 'role_name': 'Manager', 'dept_name': 'Sales',
    'dept_key': 'sales',
}


# ── api_login ────────────────────────────────────────────────────────────

def test_api_login_rejects_invalid_json_body():
    request = rf.post('/api/v1/auth/login/', data=b'not json',
                       content_type='application/json')
    resp = api_login(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_login_requires_email_and_password():
    request = _post('/api/v1/auth/login/', {'email': '', 'password': ''})
    resp = api_login(request)
    assert resp.status_code == 400
    assert 'required' in json.loads(resp.content)['error']


def test_api_login_rate_limited_returns_429():
    conn = _FakeConn()
    with patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        is_rate_limited=lambda c, email: True,
    ):
        resp = api_login(_post('/api/v1/auth/login/',
                                {'email': 'a@b.com', 'password': 'x'}))
    assert resp.status_code == 429
    assert conn.closed is True


def test_api_login_bad_credentials_records_failed_attempt_and_returns_401():
    conn = _FakeConn()
    recorded = []
    with patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        is_rate_limited=lambda c, email: False,
        _verify_login=lambda email, password: False,
        record_login_attempt=lambda c, email, success: recorded.append((email, success)),
    ):
        resp = api_login(_post('/api/v1/auth/login/',
                                {'email': 'a@b.com', 'password': 'wrong'}))
    assert resp.status_code == 401
    assert recorded == [('a@b.com', False)]
    assert conn.committed is True
    assert conn.closed is True


def test_api_login_missing_profile_returns_400():
    conn = _FakeConn()
    with patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        is_rate_limited=lambda c, email: False,
        _verify_login=lambda email, password: True,
        record_login_attempt=lambda c, email, success: None,
        _get_user_profile=lambda email: {},
    ):
        resp = api_login(_post('/api/v1/auth/login/',
                                {'email': 'a@b.com', 'password': 'x'}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'User profile not found.'


def test_api_login_success_returns_token_and_user_shape():
    conn = _FakeConn()
    with patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        is_rate_limited=lambda c, email: False,
        _verify_login=lambda email, password: True,
        record_login_attempt=lambda c, email, success: None,
        _get_user_profile=lambda email: _PROFILE,
        create_token=lambda c, people_id: 'tok-123',
    ):
        resp = api_login(_post('/api/v1/auth/login/',
                                {'email': 'A@B.com', 'password': 'x'}))
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data['token'] == 'tok-123'
    assert data['user'] == {
        'id': 42, 'email': 'a@b.com', 'role': 'Manager',
        'dept_name': 'Sales', 'dept_key': 'sales',
        'full_access': False, 'is_manager': False,
    }
    assert conn.committed is True
    assert conn.closed is True


def test_api_login_full_access_and_manager_flags_for_president():
    conn = _FakeConn()
    profile = dict(_PROFILE, role_name='President')
    with patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        is_rate_limited=lambda c, email: False,
        _verify_login=lambda email, password: True,
        record_login_attempt=lambda c, email, success: None,
        _get_user_profile=lambda email: profile,
        create_token=lambda c, people_id: 'tok-123',
    ):
        resp = api_login(_post('/api/v1/auth/login/',
                                {'email': 'a@b.com', 'password': 'x'}))
    data = json.loads(resp.content)['data']
    assert data['user']['full_access'] is True
    assert data['user']['is_manager'] is True


def test_api_login_lowercases_and_trims_email():
    conn = _FakeConn()
    seen = []
    with patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        is_rate_limited=lambda c, email: seen.append(email) or False,
        _verify_login=lambda email, password: True,
        record_login_attempt=lambda c, email, success: None,
        _get_user_profile=lambda email: _PROFILE,
        create_token=lambda c, people_id: 'tok-123',
    ):
        api_login(_post('/api/v1/auth/login/',
                         {'email': '  A@B.com  ', 'password': 'x'}))
    assert seen == ['a@b.com']


# ── api_refresh ──────────────────────────────────────────────────────────

def test_api_refresh_requires_auth():
    resp = api_refresh(rf.post('/api/v1/auth/refresh/'))
    assert resp.status_code == 401


def test_api_refresh_token_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        refresh_token=lambda c, token: False,
    ):
        resp = api_refresh(_auth_post('/api/v1/auth/refresh/'))
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_refresh_success():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        refresh_token=lambda c, token: True,
    ):
        resp = api_refresh(_auth_post('/api/v1/auth/refresh/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Token refreshed.'
    assert conn.committed is True
    assert conn.closed is True


# ── api_logout ───────────────────────────────────────────────────────────

def test_api_logout_requires_auth():
    resp = api_logout(rf.post('/api/v1/auth/logout/'))
    assert resp.status_code == 401


def test_api_logout_success_revokes_token():
    conn = _FakeConn()
    revoked = []
    with _decorator_auth({'id': 1}), patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
        revoke_token=lambda c, token: revoked.append(token),
    ):
        resp = api_logout(_auth_post('/api/v1/auth/logout/', token='sometoken'))
    assert resp.status_code == 200
    assert revoked == ['sometoken']
    assert conn.committed is True
    assert conn.closed is True


# ── api_profile ──────────────────────────────────────────────────────────

def test_api_profile_requires_auth():
    resp = api_profile(rf.get('/api/v1/auth/profile/'))
    assert resp.status_code == 401


_TOKEN_USER = {
    'id': 99, 'role': 'Manager', 'dept_name': 'Sales',
    'dept_key': 'sales', 'full_access': False, 'is_manager': True,
}


def test_api_profile_not_found_returns_404():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_TOKEN_USER), patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
    ):
        resp = api_profile(_auth_get('/api/v1/auth/profile/'))
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_profile_success_merges_people_row_and_token_user_fields():
    conn = _FakeConn(rows=[{
        'id': 99, 'first_name': 'Alice', 'last_name': 'Smith',
        'employee_id': 'E-1', 'email': 'alice@example.com',
    }])
    with _decorator_auth(_TOKEN_USER), patch.multiple(
        'manufacturing.api_views',
        get_db_connection=lambda: conn,
    ):
        resp = api_profile(_auth_get('/api/v1/auth/profile/'))
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data == {
        'id': 99, 'first_name': 'Alice', 'last_name': 'Smith',
        'employee_id': 'E-1', 'email': 'alice@example.com',
        'role': 'Manager', 'dept_name': 'Sales', 'dept_key': 'sales',
        'full_access': False, 'is_manager': True,
    }
    assert conn.closed is True


# ── dashboards ────────────────────────────────────────────────────────────
#
# All four are thin wrappers: open a conn, call one (or a fixed set of)
# reports_core function(s), close the conn, return api_ok(data) — so each
# gets an auth-required check plus a success check that the right
# reports_core call(s) feed straight into the response, with reports_core's
# own patched at the reports_core module (api_views imports the module
# itself, not the individual functions, so patching there is equivalent to
# patching manufacturing.api_views.reports_core.<fn>).

def test_api_dashboard_requires_auth():
    resp = api_dashboard(rf.get('/api/v1/dashboard/'))
    assert resp.status_code == 401


def test_api_dashboard_success_combines_four_summaries():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.multiple(
             'manufacturing.reports_core',
             po_summary=lambda c: {'open': 3},
             wo_summary=lambda c: {'active': 5},
             inventory_alerts=lambda c: {'low_stock': 2},
             cs_summary=lambda c: {'open_tickets': 1},
         ):
        resp = api_dashboard(_auth_get('/api/v1/dashboard/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {
        'po': {'open': 3}, 'wo': {'active': 5},
        'inventory': {'low_stock': 2}, 'cs': {'open_tickets': 1},
    }
    assert conn.closed is True


def test_api_financial_dashboard_requires_auth():
    resp = api_financial_dashboard(rf.get('/api/v1/dashboard/financial/'))
    assert resp.status_code == 401


def test_api_financial_dashboard_success_passes_through_reports_core():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(reports_core, 'financial_dashboard', lambda c: {'ar_total': 1000}):
        resp = api_financial_dashboard(_auth_get('/api/v1/dashboard/financial/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'ar_total': 1000}
    assert conn.closed is True


def test_api_production_dashboard_requires_auth():
    resp = api_production_dashboard(rf.get('/api/v1/dashboard/production/'))
    assert resp.status_code == 401


def test_api_production_dashboard_success_passes_through_reports_core():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(reports_core, 'production_dashboard', lambda c: {'wo_open': 7}):
        resp = api_production_dashboard(_auth_get('/api/v1/dashboard/production/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'wo_open': 7}
    assert conn.closed is True


def test_api_inventory_dashboard_requires_auth():
    resp = api_inventory_dashboard(rf.get('/api/v1/dashboard/inventory/'))
    assert resp.status_code == 401


def test_api_inventory_dashboard_success_passes_through_reports_core():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(reports_core, 'inventory_dashboard', lambda c: {'low_stock_count': 4}):
        resp = api_inventory_dashboard(_auth_get('/api/v1/dashboard/inventory/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'low_stock_count': 4}
    assert conn.closed is True


# ── time clock ────────────────────────────────────────────────────────────

_TC_USER = {'id': 7, 'email': 'worker@example.com'}


def test_api_tc_status_requires_auth():
    resp = api_tc_status(rf.get('/api/v1/timeclock/status/'))
    assert resp.status_code == 401


def test_api_tc_status_not_clocked_in():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: None):
        resp = api_tc_status(_auth_get('/api/v1/timeclock/status/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'clocked_in': False, 'entry': None}
    assert conn.closed is True


def test_api_tc_status_clocked_in_enriches_entry():
    conn = _FakeConn()
    raw_entry = {'id': 5, 'clock_in': '2026-08-07T08:00:00'}
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: raw_entry), \
         patch.object(time_clock_core, '_enrich',
                      lambda d: dict(d, hours=1.5, hours_fmt='1h 30m', in_progress=True)):
        resp = api_tc_status(_auth_get('/api/v1/timeclock/status/'))
    data = json.loads(resp.content)['data']
    assert data['clocked_in'] is True
    assert data['entry']['hours'] == 1.5
    assert data['entry']['in_progress'] is True


def test_api_tc_status_uses_authenticated_users_id():
    conn = _FakeConn()
    seen_uid = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry',
                      lambda c, uid: seen_uid.append(uid) or None):
        api_tc_status(_auth_get('/api/v1/timeclock/status/'))
    assert seen_uid == [7]


def test_api_tc_clock_in_requires_auth():
    resp = api_tc_clock_in(rf.post('/api/v1/timeclock/clock-in/'))
    assert resp.status_code == 401


def test_api_tc_clock_in_already_clocked_in_returns_409():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: {'id': 1}):
        resp = api_tc_clock_in(_auth_post_empty_body('/api/v1/timeclock/clock-in/'))
    assert resp.status_code == 409
    assert json.loads(resp.content)['error'] == 'Already clocked in.'
    assert conn.closed is True


def test_api_tc_clock_in_empty_body_defaults_notes_to_empty():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: None), \
         patch.object(time_clock_core, 'clock_in',
                      lambda c, uid, notes='', created_by=None: (
                          seen.append((uid, notes, created_by)) or 99)):
        resp = api_tc_clock_in(_auth_post_empty_body('/api/v1/timeclock/clock-in/'))
    assert resp.status_code == 201
    assert json.loads(resp.content)['data'] == {'entry_id': 99, 'message': 'Clocked in.'}
    assert seen == [(7, '', 'mobile')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_tc_clock_in_passes_through_notes_from_body():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: None), \
         patch.object(time_clock_core, 'clock_in',
                      lambda c, uid, notes='', created_by=None: (
                          seen.append((uid, notes, created_by)) or 100)):
        resp = api_tc_clock_in(_auth_post_json(
            '/api/v1/timeclock/clock-in/', {'notes': 'Starting shift'}))
    assert resp.status_code == 201
    assert seen == [(7, 'Starting shift', 'mobile')]


def test_api_tc_clock_out_requires_auth():
    resp = api_tc_clock_out(rf.post('/api/v1/timeclock/clock-out/'))
    assert resp.status_code == 401


def test_api_tc_clock_out_not_clocked_in_returns_409():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: None):
        resp = api_tc_clock_out(_auth_post('/api/v1/timeclock/clock-out/'))
    assert resp.status_code == 409
    assert json.loads(resp.content)['error'] == 'Not currently clocked in.'
    assert conn.closed is True


def test_api_tc_clock_out_success_clocks_out_current_entry():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_current_entry', lambda c, uid: {'id': 42}), \
         patch.object(time_clock_core, 'clock_out_entry',
                      lambda c, entry_id: seen.append(entry_id)):
        resp = api_tc_clock_out(_auth_post('/api/v1/timeclock/clock-out/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Clocked out.'
    assert seen == [42]
    assert conn.committed is True
    assert conn.closed is True


def test_api_tc_hours_requires_auth():
    resp = api_tc_hours(rf.get('/api/v1/timeclock/hours/'))
    assert resp.status_code == 401


def test_api_tc_hours_defaults_to_week_period():
    conn = _FakeConn()
    seen_periods = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_period_dates',
                      lambda period: (seen_periods.append(period) or ('2026-08-03', '2026-08-09'))), \
         patch.object(time_clock_core, 'list_entries', lambda c, uid, f, t: []), \
         patch.object(time_clock_core, 'total_hours', lambda entries: (0.0, '0h 0m')):
        resp = api_tc_hours(_auth_get('/api/v1/timeclock/hours/'))
    assert resp.status_code == 200
    assert seen_periods == ['week']
    data = json.loads(resp.content)['data']
    assert data == {
        'period': 'week', 'date_from': '2026-08-03', 'date_to': '2026-08-09',
        'entries': [], 'total_hours': 0.0, 'total_hours_fmt': '0h 0m',
    }


def test_api_tc_hours_uses_period_query_param():
    conn = _FakeConn()
    seen_periods = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(time_clock_core, 'get_period_dates',
                      lambda period: (seen_periods.append(period) or ('2026-08-01', '2026-08-31'))), \
         patch.object(time_clock_core, 'list_entries', lambda c, uid, f, t: [{'id': 1}]), \
         patch.object(time_clock_core, 'total_hours', lambda entries: (8.0, '8h 0m')):
        resp = api_tc_hours(_auth_get('/api/v1/timeclock/hours/?period=month'))
    assert seen_periods == ['month']
    data = json.loads(resp.content)['data']
    assert data['entries'] == [{'id': 1}]
    assert data['total_hours'] == 8.0


# ── time off ─────────────────────────────────────────────────────────────

def test_api_time_off_requires_auth():
    resp = api_time_off(rf.get('/api/v1/timeoff/'))
    assert resp.status_code == 401


def test_api_time_off_get_returns_requests_and_types():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(personnel_core, 'list_time_off_requests',
                      lambda c, people_id: [{'id': 1, 'status': 'Pending'}]):
        resp = api_time_off(_auth_get('/api/v1/timeoff/'))
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data['requests'] == [{'id': 1, 'status': 'Pending'}]
    assert data['types'] == list(personnel_core.TIME_OFF_TYPES)
    assert conn.closed is True


def test_api_time_off_post_invalid_json_returns_400():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        request = rf.post('/api/v1/timeoff/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_time_off(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_time_off_post_requires_start_and_end_dates():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        resp = api_time_off(_auth_post_json('/api/v1/timeoff/', {
            'start_date': '', 'end_date': '2026-08-10',
        }))
    assert resp.status_code == 400
    assert 'start_date and end_date are required' in json.loads(resp.content)['error']


def test_api_time_off_post_rejects_invalid_request_type():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        resp = api_time_off(_auth_post_json('/api/v1/timeoff/', {
            'start_date': '2026-08-10', 'end_date': '2026-08-12',
            'request_type': 'Sabbatical',
        }))
    assert resp.status_code == 400
    assert 'request_type must be one of' in json.loads(resp.content)['error']


def test_api_time_off_post_success_creates_request():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(personnel_core, 'create_time_off_request',
                      lambda c, uid, start, end, request_type, notes, created_by:
                          seen.append((uid, start, end, request_type, notes, created_by))):
        resp = api_time_off(_auth_post_json('/api/v1/timeoff/', {
            'start_date': '2026-08-10', 'end_date': '2026-08-12',
            'request_type': 'Sick', 'notes': 'Flu',
        }))
    assert resp.status_code == 201
    assert json.loads(resp.content)['data']['message'] == 'Time-off request submitted.'
    assert seen == [(7, '2026-08-10', '2026-08-12', 'Sick', 'Flu', 'mobile')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_time_off_post_defaults_request_type_to_vacation():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(personnel_core, 'create_time_off_request',
                      lambda c, uid, start, end, request_type, notes, created_by:
                          seen.append(request_type)):
        api_time_off(_auth_post_json('/api/v1/timeoff/', {
            'start_date': '2026-08-10', 'end_date': '2026-08-12',
        }))
    assert seen == ['Vacation']


def test_api_time_off_unsupported_method_returns_405():
    conn = _FakeConn()
    with _decorator_auth(_TC_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        request = rf.delete('/api/v1/timeoff/', HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_time_off(request)
    assert resp.status_code == 405
    assert json.loads(resp.content)['error'] == 'Method not allowed.'


# ── work orders ──────────────────────────────────────────────────────────

_WO_USER = {'id': 7, 'email': 'worker@example.com'}


def test_api_wo_list_requires_auth():
    resp = api_wo_list(rf.get('/api/v1/wo/'))
    assert resp.status_code == 401


def test_api_wo_list_success_includes_statuses_and_colors():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'ensure_wo_tables', lambda c: None), \
         patch.object(work_orders_core, 'list_wos',
                      lambda c, status=None: [{'id': 1, 'wo_number': 'WO-1'}]):
        resp = api_wo_list(_auth_get('/api/v1/wo/'))
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data['work_orders'] == [{'id': 1, 'wo_number': 'WO-1'}]
    assert data['statuses'] == list(work_orders_core.WO_STATUSES)
    assert data['status_colors'] == work_orders_core.WO_STATUS_COLORS
    assert conn.committed is True
    assert conn.closed is True


def test_api_wo_list_passes_through_status_query_param():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'ensure_wo_tables', lambda c: None), \
         patch.object(work_orders_core, 'list_wos',
                      lambda c, status=None: seen.append(status) or []):
        api_wo_list(_auth_get('/api/v1/wo/?status=open'))
    assert seen == ['open']


def test_api_wo_detail_requires_auth():
    resp = api_wo_detail(rf.get('/api/v1/wo/1/'), 1)
    assert resp.status_code == 401


def test_api_wo_detail_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'get_wo', lambda c, wo_id: None):
        resp = api_wo_detail(_auth_get('/api/v1/wo/99/'), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_wo_detail_success_merges_materials_and_transitions():
    conn = _FakeConn()
    wo = {'id': 1, 'wo_number': 'WO-1', 'status': 'open'}
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'get_wo', lambda c, wo_id: dict(wo)), \
         patch.object(work_orders_core, 'get_wo_materials',
                      lambda c, wo_id: [{'product_id': 5}]), \
         patch.object(work_orders_core, 'allowed_transitions',
                      lambda status: ('in_progress', 'cancelled')):
        resp = api_wo_detail(_auth_get('/api/v1/wo/1/'), 1)
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']['work_order']
    assert data['materials'] == [{'product_id': 5}]
    assert data['allowed_transitions'] == ['in_progress', 'cancelled']


def test_api_wo_status_requires_auth():
    resp = api_wo_status(rf.post('/api/v1/wo/1/status/'), 1)
    assert resp.status_code == 401


def test_api_wo_status_invalid_json_returns_400():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        request = rf.post('/api/v1/wo/1/status/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_wo_status(request, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_wo_status_requires_status_field():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        resp = api_wo_status(_auth_post_json('/api/v1/wo/1/status/', {'status': ''}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'status is required.'


def test_api_wo_status_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'get_wo', lambda c, wo_id: None):
        resp = api_wo_status(
            _auth_post_json('/api/v1/wo/99/status/', {'status': 'open'}), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_wo_status_invalid_transition_returns_400():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'get_wo',
                      lambda c, wo_id: {'id': 1, 'status': 'completed'}), \
         patch.object(work_orders_core, 'can_transition', lambda cur, new: False):
        resp = api_wo_status(
            _auth_post_json('/api/v1/wo/1/status/', {'status': 'open'}), 1)
    assert resp.status_code == 400
    assert "Cannot move from 'completed' to 'open'" in json.loads(resp.content)['error']


def test_api_wo_status_success_updates_and_commits():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(work_orders_core, 'get_wo',
                      lambda c, wo_id: {'id': 1, 'status': 'open'}), \
         patch.object(work_orders_core, 'can_transition', lambda cur, new: True):
        resp = api_wo_status(
            _auth_post_json('/api/v1/wo/1/status/', {'status': 'in_progress'}), 1)
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data == {'status': 'in_progress',
                     'message': "Status updated to 'in_progress'."}
    assert conn.committed is True
    assert conn.closed is True
    update_calls = [c for c in conn.calls if c[0].startswith('UPDATE work_order')]
    assert update_calls[0][1] == ('in_progress', 1)


def test_api_wo_operations_requires_auth():
    resp = api_wo_operations(rf.get('/api/v1/wo/1/operations/'), 1)
    assert resp.status_code == 401


def test_api_wo_operations_success_combines_ops_and_labor_cost():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'get_wo_operations',
                      lambda c, wo_id: [{'operation_seq': 1, 'status': 'pending'}]), \
         patch.object(routing_core, 'get_wo_labor_cost', lambda c, wo_id: 42.5):
        resp = api_wo_operations(_auth_get('/api/v1/wo/1/operations/'), 1)
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data['operations'] == [{'operation_seq': 1, 'status': 'pending'}]
    assert data['labor_cost'] == 42.5


def test_api_wo_operation_complete_requires_auth():
    resp = api_wo_operation_complete(rf.post('/api/v1/wo/1/operations/1/complete/'), 1, 1)
    assert resp.status_code == 401


def test_api_wo_operation_complete_invalid_json_returns_400():
    with _decorator_auth(_WO_USER):
        request = rf.post('/api/v1/wo/1/operations/1/complete/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_wo_operation_complete(request, 1, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_wo_operation_complete_requires_actual_hours():
    with _decorator_auth(_WO_USER):
        resp = api_wo_operation_complete(
            _auth_post_json('/api/v1/wo/1/operations/1/complete/', {}), 1, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'actual_hours is required.'


def test_api_wo_operation_complete_rejects_non_numeric_actual_hours():
    with _decorator_auth(_WO_USER):
        resp = api_wo_operation_complete(
            _auth_post_json('/api/v1/wo/1/operations/1/complete/',
                             {'actual_hours': 'lots'}), 1, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'actual_hours must be a number.'


def test_api_wo_operation_complete_seq_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'get_wo_operations', lambda c, wo_id: []):
        resp = api_wo_operation_complete(
            _auth_post_json('/api/v1/wo/1/operations/9/complete/',
                             {'actual_hours': 2}), 1, 9)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_wo_operation_complete_already_completed_returns_409():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'get_wo_operations',
                      lambda c, wo_id: [{'id': 5, 'operation_seq': 1, 'status': 'completed'}]):
        resp = api_wo_operation_complete(
            _auth_post_json('/api/v1/wo/1/operations/1/complete/',
                             {'actual_hours': 2}), 1, 1)
    assert resp.status_code == 409
    assert json.loads(resp.content)['error'] == 'Operation is already completed.'


def test_api_wo_operation_complete_success_passes_defaults():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'get_wo_operations',
                      lambda c, wo_id: [{'id': 5, 'operation_seq': 1, 'status': 'in_progress'}]), \
         patch.object(routing_core, 'complete_wo_operation',
                      lambda c, op_id, actual_hours, completed_by, scrap_qty, rework_qty, notes:
                          seen.append((op_id, actual_hours, completed_by, scrap_qty, rework_qty, notes))):
        resp = api_wo_operation_complete(
            _auth_post_json('/api/v1/wo/1/operations/1/complete/',
                             {'actual_hours': 3.5}), 1, 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Operation 1 completed.'
    assert seen == [(5, 3.5, 'worker@example.com', 0.0, 0.0, '')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_wo_operation_complete_success_passes_through_optional_fields():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'get_wo_operations',
                      lambda c, wo_id: [{'id': 5, 'operation_seq': 2, 'status': 'in_progress'}]), \
         patch.object(routing_core, 'complete_wo_operation',
                      lambda c, op_id, actual_hours, completed_by, scrap_qty, rework_qty, notes:
                          seen.append((scrap_qty, rework_qty, notes))):
        api_wo_operation_complete(
            _auth_post_json('/api/v1/wo/1/operations/2/complete/', {
                'actual_hours': 3.5, 'scrap_qty': 2, 'rework_qty': 1,
                'notes': 'Minor rework',
            }), 1, 2)
    assert seen == [(2.0, 1.0, 'Minor rework')]


def test_api_wo_operation_start_requires_auth():
    resp = api_wo_operation_start(rf.post('/api/v1/wo/1/operations/1/start/'), 1, 1)
    assert resp.status_code == 401


def test_api_wo_operation_start_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'ensure_routing_tables', lambda c: None), \
         patch.object(routing_core, 'get_wo_operations', lambda c, wo_id: []):
        resp = api_wo_operation_start(_auth_post('/api/v1/wo/1/operations/9/start/'), 1, 9)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_wo_operation_start_rejects_non_pending_operation():
    conn = _FakeConn()
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'ensure_routing_tables', lambda c: None), \
         patch.object(routing_core, 'get_wo_operations',
                      lambda c, wo_id: [{'id': 5, 'operation_seq': 1, 'status': 'in_progress'}]):
        resp = api_wo_operation_start(_auth_post('/api/v1/wo/1/operations/1/start/'), 1, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Operation is already in_progress.'


def test_api_wo_operation_start_success():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_WO_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(routing_core, 'ensure_routing_tables', lambda c: None), \
         patch.object(routing_core, 'get_wo_operations',
                      lambda c, wo_id: [{'id': 5, 'operation_seq': 1, 'status': 'pending'}]), \
         patch.object(routing_core, 'start_wo_operation', lambda c, op_id: seen.append(op_id)):
        resp = api_wo_operation_start(_auth_post('/api/v1/wo/1/operations/1/start/'), 1, 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Operation 1 started.'
    assert seen == [5]
    assert conn.committed is True
    assert conn.closed is True


# ── requisitions ─────────────────────────────────────────────────────────
#
# api_req's GET branch issues its own raw CREATE TABLE/ALTER TABLE/SELECT
# calls (no purchase_requisitions_core delegation), so a plain _FakeConn
# works there — only the final SELECT's fetchall() result is ever read.
# Its POST branch (and api_req_add_item/_submit/_decide) issue several
# queries with different row shapes per call, so those use _QueueConn.

_FULL_ACCESS_USER = {'id': 1, 'email': 'vp@example.com', 'dept_id': 10,
                      'role': 'Vice President', 'full_access': True,
                      'is_manager': True}
_MANAGER_USER = {'id': 2, 'email': 'mgr@example.com', 'dept_id': 20,
                  'role': 'Department Manager', 'full_access': False,
                  'is_manager': True}
_REGULAR_USER = {'id': 3, 'email': 'emp@example.com', 'dept_id': 20,
                  'role': 'Employee', 'full_access': False,
                  'is_manager': False}


def test_api_req_get_requires_auth():
    resp = api_req(rf.get('/api/v1/req/'))
    assert resp.status_code == 401


def test_api_req_get_full_access_user_sees_all_requisitions():
    conn = _FakeConn(rows=[{'id': 1, 'req_number': 'REQ-2026-0001'}])
    with _decorator_auth(_FULL_ACCESS_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        resp = api_req(_auth_get('/api/v1/req/'))
    assert resp.status_code == 200
    select_call = conn.calls[-1]
    assert 'WHERE pr.dept_id' not in select_call[0]
    assert 'WHERE pr.requester_id' not in select_call[0]
    assert select_call[1] == []
    assert json.loads(resp.content)['data']['requisitions'] == [
        {'id': 1, 'req_number': 'REQ-2026-0001'}]


def test_api_req_get_manager_filters_by_dept():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_MANAGER_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        api_req(_auth_get('/api/v1/req/'))
    select_call = conn.calls[-1]
    assert 'WHERE pr.dept_id = %s' in select_call[0]
    assert select_call[1] == [20]


def test_api_req_get_regular_user_filters_by_requester():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn):
        api_req(_auth_get('/api/v1/req/'))
    select_call = conn.calls[-1]
    assert 'WHERE pr.requester_id = %s' in select_call[0]
    assert select_call[1] == [3]


def test_api_req_post_invalid_json_returns_400():
    with _decorator_auth(_REGULAR_USER):
        request = rf.post('/api/v1/req/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_req(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_req_post_requires_purpose():
    with _decorator_auth(_REGULAR_USER):
        resp = api_req(_auth_post_json('/api/v1/req/', {'purpose': '  '}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'purpose is required.'


def test_api_req_post_success_creates_draft_requisition():
    conn = _QueueConn([
        [('REQ-2026-0001',), ('REQ-2026-0003',)],  # existing req_numbers
        [(42,)],                                    # INSERT ... RETURNING id
    ])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req(_auth_post_json('/api/v1/req/', {
            'purpose': 'New monitor', 'notes': 'For home office',
        }))
    assert resp.status_code == 201
    data = json.loads(resp.content)['data']
    assert data == {'id': 42, 'req_number': 'REQ-2026-0004',
                     'message': 'Requisition created.'}
    insert_call = conn.calls[-1]
    assert insert_call[1] == ('REQ-2026-0004', 3, 20, 'New monitor',
                               'For home office', 'mobile')
    assert conn.committed is True
    assert conn.closed is True


def test_api_req_unsupported_method_returns_405():
    with _decorator_auth(_REGULAR_USER):
        request = rf.delete('/api/v1/req/', HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_req(request)
    assert resp.status_code == 405
    assert json.loads(resp.content)['error'] == 'Method not allowed.'


def test_api_req_add_item_requires_auth():
    resp = api_req_add_item(rf.post('/api/v1/req/1/items/'), 1)
    assert resp.status_code == 401


def test_api_req_add_item_invalid_json_returns_400():
    with _decorator_auth(_REGULAR_USER):
        request = rf.post('/api/v1/req/1/items/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_req_add_item(request, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_req_add_item_requires_description():
    with _decorator_auth(_REGULAR_USER):
        resp = api_req_add_item(
            _auth_post_json('/api/v1/req/1/items/', {'description': ' '}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'description is required.'


def test_api_req_add_item_not_found_returns_404():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_add_item(
            _auth_post_json('/api/v1/req/99/items/', {'description': 'Widget'}), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_req_add_item_rejects_non_draft_requisition():
    conn = _FakeConn(rows=[{'status': 'submitted', 'requester_id': 3}])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_add_item(
            _auth_post_json('/api/v1/req/1/items/', {'description': 'Widget'}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Can only add items to draft requisitions.'


def test_api_req_add_item_permission_denied_for_non_owner_non_full_access():
    conn = _FakeConn(rows=[{'status': 'draft', 'requester_id': 999}])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_add_item(
            _auth_post_json('/api/v1/req/1/items/', {'description': 'Widget'}), 1)
    assert resp.status_code == 403
    assert json.loads(resp.content)['error'] == 'Permission denied.'


def test_api_req_add_item_full_access_can_add_to_others_requisition():
    conn = _QueueConn([
        [{'status': 'draft', 'requester_id': 999}],
        [(7,)],
    ])
    with _decorator_auth(_FULL_ACCESS_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_add_item(
            _auth_post_json('/api/v1/req/1/items/', {
                'description': 'Widget', 'quantity': 3, 'unit_price': 9.5,
            }), 1)
    assert resp.status_code == 201
    assert json.loads(resp.content)['data'] == {'id': 7, 'message': 'Item added.'}
    insert_call = conn.calls[-1]
    assert insert_call[1] == (1, 'Widget', 3, 9.5)
    assert conn.committed is True


def test_api_req_add_item_defaults_quantity_and_price():
    conn = _QueueConn([
        [{'status': 'draft', 'requester_id': 3}],
        [(8,)],
    ])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        api_req_add_item(
            _auth_post_json('/api/v1/req/1/items/', {'description': 'Widget'}), 1)
    insert_call = conn.calls[-1]
    assert insert_call[1] == (1, 'Widget', 1, 0.0)


def test_api_req_submit_requires_auth():
    resp = api_req_submit(rf.post('/api/v1/req/1/submit/'), 1)
    assert resp.status_code == 401


def test_api_req_submit_not_found_returns_404():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_submit(_auth_post('/api/v1/req/99/submit/'), 99)
    assert resp.status_code == 404


def test_api_req_submit_permission_denied_for_non_owner_non_full_access():
    conn = _FakeConn(rows=[{'status': 'draft', 'requester_id': 999}])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_submit(_auth_post('/api/v1/req/1/submit/'), 1)
    assert resp.status_code == 403


def test_api_req_submit_rejects_non_draft_requisition():
    conn = _FakeConn(rows=[{'status': 'submitted', 'requester_id': 3}])
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_submit(_auth_post('/api/v1/req/1/submit/'), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Only draft requisitions can be submitted.'


def test_api_req_submit_success_updates_status_and_submits_for_approval():
    conn = _QueueConn([
        [{'status': 'draft', 'requester_id': 3}],   # requisition lookup
        None,                                        # UPDATE ... status
        [{'total': 150.0}],                          # item total
        [{'dept_name': 'Sales'}],                     # dept lookup
    ])
    seen = []
    with _decorator_auth(_REGULAR_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None), \
         patch.object(approval_workflow_core, 'ensure_approval_tables',
                      lambda c: None), \
         patch.object(approval_workflow_core, 'submit_for_approval',
                      lambda c, entity_type, entity_id, total, dept_key, requested_by:
                          seen.append((entity_type, entity_id, total, dept_key, requested_by))):
        resp = api_req_submit(_auth_post('/api/v1/req/1/submit/'), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Requisition submitted for approval.'
    assert seen == [('purchase_requisition', 1, 150.0, 'sales', 'emp@example.com')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_req_pending_requires_auth():
    resp = api_req_pending(rf.get('/api/v1/req/pending/'))
    assert resp.status_code == 401


def test_api_req_pending_rejects_non_manager():
    with _decorator_auth(_REGULAR_USER):
        resp = api_req_pending(_auth_get('/api/v1/req/pending/'))
    assert resp.status_code == 403
    assert json.loads(resp.content)['error'] == 'Manager access required.'


def test_api_req_pending_manager_filters_by_dept():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_MANAGER_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        api_req_pending(_auth_get('/api/v1/req/pending/'))
    sql, params = conn.calls[-1]
    assert 'AND pr.dept_id = %s' in sql
    assert params == [2, 20]


def test_api_req_pending_full_access_sees_all_depts():
    conn = _FakeConn(rows=[{'id': 1, 'req_number': 'REQ-2026-0001'}])
    with _decorator_auth(_FULL_ACCESS_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_pending(_auth_get('/api/v1/req/pending/'))
    sql, params = conn.calls[-1]
    assert 'AND pr.dept_id = %s' not in sql
    assert params == [1]
    assert json.loads(resp.content)['data']['requisitions'] == [
        {'id': 1, 'req_number': 'REQ-2026-0001'}]


def test_api_req_decide_requires_auth():
    resp = api_req_decide(rf.post('/api/v1/req/1/decide/'), 1)
    assert resp.status_code == 401


def test_api_req_decide_rejects_non_manager():
    with _decorator_auth(_REGULAR_USER):
        resp = api_req_decide(
            _auth_post_json('/api/v1/req/1/decide/', {'decision': 'approve'}), 1)
    assert resp.status_code == 403
    assert json.loads(resp.content)['error'] == 'Manager access required.'


def test_api_req_decide_invalid_json_returns_400():
    with _decorator_auth(_MANAGER_USER):
        request = rf.post('/api/v1/req/1/decide/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_req_decide(request, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_req_decide_rejects_invalid_decision_value():
    with _decorator_auth(_MANAGER_USER):
        resp = api_req_decide(
            _auth_post_json('/api/v1/req/1/decide/', {'decision': 'maybe'}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == "decision must be 'approve' or 'deny'."


def test_api_req_decide_not_found_returns_404():
    conn = _FakeConn(rows=[])
    with _decorator_auth(_MANAGER_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None):
        resp = api_req_decide(
            _auth_post_json('/api/v1/req/99/decide/', {'decision': 'approve'}), 99)
    assert resp.status_code == 404


def test_api_req_decide_not_authorized_returns_403():
    conn = _FakeConn(rows=[{'status': 'submitted', 'requester_id': 3, 'dept_id': 20}])
    with _decorator_auth(_MANAGER_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None), \
         patch.object(purchase_requisitions_core, 'can_authorize', lambda *a, **kw: False):
        resp = api_req_decide(
            _auth_post_json('/api/v1/req/1/decide/', {'decision': 'approve'}), 1)
    assert resp.status_code == 403
    assert json.loads(resp.content)['error'] == 'Not authorized to decide on this requisition.'


def test_api_req_decide_approve_success():
    conn = _FakeConn(rows=[{'status': 'submitted', 'requester_id': 3, 'dept_id': 20}])
    with _decorator_auth(_MANAGER_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None), \
         patch.object(purchase_requisitions_core, 'can_authorize', lambda *a, **kw: True):
        resp = api_req_decide(
            _auth_post_json('/api/v1/req/1/decide/', {
                'decision': 'approve', 'comment': 'Looks good',
            }), 1)
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data == {'status': 'dept_approved', 'message': 'Requisition approved.'}
    insert_call = conn.calls[-1]
    assert insert_call[1] == (1, 'approve', 2, 'Looks good')
    assert conn.committed is True
    assert conn.closed is True


def test_api_req_decide_deny_success():
    # Pins actual (slightly awkward) behavior: the message is built as
    # f"Requisition {decision}d." with no special-casing, so 'deny' + 'd'
    # produces "Requisition denyd." rather than "denied." — not fixing this
    # since it wasn't asked for, just documenting what the code does today.
    conn = _FakeConn(rows=[{'status': 'submitted', 'requester_id': 3, 'dept_id': 20}])
    with _decorator_auth(_MANAGER_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(purchase_requisitions_core, 'ensure_requisition_tables',
                      lambda c: None), \
         patch.object(purchase_requisitions_core, 'can_authorize', lambda *a, **kw: True):
        resp = api_req_decide(
            _auth_post_json('/api/v1/req/1/decide/', {'decision': 'deny'}), 1)
    data = json.loads(resp.content)['data']
    assert data == {'status': 'dept_denied', 'message': 'Requisition denyd.'}


# ── inventory ────────────────────────────────────────────────────────────

def test_api_inventory_list_requires_auth():
    resp = api_inventory_list(rf.get('/api/v1/inventory/'))
    assert resp.status_code == 401


def test_api_inventory_list_success_combines_products_and_alerts():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(inventory_core, 'list_products',
                      lambda c, search=None, filter_status=None:
                          [{'id': 1, 'name': 'Widget'}]), \
         patch.object(inventory_core, 'get_alert_counts',
                      lambda c: {'low_stock': 3}):
        resp = api_inventory_list(_auth_get('/api/v1/inventory/'))
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data == {'products': [{'id': 1, 'name': 'Widget'}],
                     'alerts': {'low_stock': 3}}
    assert conn.closed is True


def test_api_inventory_list_passes_through_search_and_status_query_params():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(inventory_core, 'list_products',
                      lambda c, search=None, filter_status=None:
                          seen.append((search, filter_status)) or []), \
         patch.object(inventory_core, 'get_alert_counts', lambda c: {}):
        api_inventory_list(_auth_get('/api/v1/inventory/?q=widget&status=low'))
    assert seen == [('widget', 'low')]


def test_api_inventory_list_defaults_missing_query_params_to_none():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(inventory_core, 'list_products',
                      lambda c, search=None, filter_status=None:
                          seen.append((search, filter_status)) or []), \
         patch.object(inventory_core, 'get_alert_counts', lambda c: {}):
        api_inventory_list(_auth_get('/api/v1/inventory/'))
    assert seen == [(None, None)]


def test_api_inventory_receive_requires_auth():
    resp = api_inventory_receive(rf.post('/api/v1/inventory/receive/'))
    assert resp.status_code == 401


def test_api_inventory_receive_invalid_json_returns_400():
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}):
        request = rf.post('/api/v1/inventory/receive/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_inventory_receive(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_inventory_receive_requires_product_id_and_qty():
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}):
        resp = api_inventory_receive(
            _auth_post_json('/api/v1/inventory/receive/', {'product_id': None, 'qty': 5}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'product_id and qty are required.'


def test_api_inventory_receive_requires_qty_present():
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}):
        resp = api_inventory_receive(
            _auth_post_json('/api/v1/inventory/receive/', {'product_id': 5, 'qty': None}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'product_id and qty are required.'


def test_api_inventory_receive_rejects_non_numeric_qty():
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}):
        resp = api_inventory_receive(
            _auth_post_json('/api/v1/inventory/receive/',
                             {'product_id': 5, 'qty': 'lots'}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'qty must be a number.'


def test_api_inventory_receive_zero_qty_is_caught_by_required_check():
    # qty=0 is falsy in Python, so `if not product_id or not qty` treats it
    # as "missing" and returns the required-fields error rather than ever
    # reaching the `qty <= 0` check below — "qty must be positive." is only
    # reachable via a negative value (see the negative-qty test).
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}):
        resp = api_inventory_receive(
            _auth_post_json('/api/v1/inventory/receive/', {'product_id': 5, 'qty': 0}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'product_id and qty are required.'


def test_api_inventory_receive_rejects_negative_qty():
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}):
        resp = api_inventory_receive(
            _auth_post_json('/api/v1/inventory/receive/', {'product_id': 5, 'qty': -3}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'qty must be positive.'


def test_api_inventory_receive_success():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(inventory_core, 'record_transaction',
                      lambda c, product_id, trans_type, qty, reference, notes, created_by:
                          seen.append((product_id, trans_type, qty, reference, notes,
                                       created_by)) or 42.5):
        resp = api_inventory_receive(_auth_post_json('/api/v1/inventory/receive/', {
            'product_id': '5', 'qty': '10', 'reference': 'PO-100', 'notes': 'Dock A',
        }))
    assert resp.status_code == 201
    assert json.loads(resp.content)['data'] == {'new_qty': 42.5, 'message': 'Stock received.'}
    assert seen == [(5, 'receive', 10.0, 'PO-100', 'Dock A', 'w@example.com')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_inventory_receive_defaults_reference_and_notes_to_empty():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1, 'email': 'w@example.com'}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(inventory_core, 'record_transaction',
                      lambda c, product_id, trans_type, qty, reference, notes, created_by:
                          seen.append((reference, notes)) or 1.0):
        api_inventory_receive(_auth_post_json('/api/v1/inventory/receive/', {
            'product_id': 5, 'qty': 10,
        }))
    assert seen == [('', '')]


# ── quality (NCR) ────────────────────────────────────────────────────────

def test_api_ncr_get_requires_auth():
    resp = api_ncr(rf.get('/api/v1/ncr/'))
    assert resp.status_code == 401


def test_api_ncr_get_success():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(quality_core, 'list_ncrs',
                      lambda c, status=None: [{'id': 1, 'title': 'Bad batch'}]):
        resp = api_ncr(_auth_get('/api/v1/ncr/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {
        'ncrs': [{'id': 1, 'title': 'Bad batch'}]}
    assert conn.closed is True


def test_api_ncr_get_passes_through_status_query_param():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(quality_core, 'list_ncrs',
                      lambda c, status=None: seen.append(status) or []):
        api_ncr(_auth_get('/api/v1/ncr/?status=open'))
    assert seen == ['open']


def test_api_ncr_post_invalid_json_returns_400():
    with _decorator_auth({'id': 1, 'email': 'q@example.com'}):
        request = rf.post('/api/v1/ncr/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_ncr(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_ncr_post_requires_title():
    with _decorator_auth({'id': 1, 'email': 'q@example.com'}):
        resp = api_ncr(_auth_post_json('/api/v1/ncr/', {'title': '  '}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'title is required.'


def test_api_ncr_post_success_creates_ncr():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1, 'email': 'q@example.com'}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(quality_core, 'create_ncr',
                      lambda c, title, source, severity, product, detected_date,
                             disposition, owner, notes, created_by:
                          seen.append((title, source, severity, product, detected_date,
                                       disposition, owner, notes, created_by)) or 9):
        resp = api_ncr(_auth_post_json('/api/v1/ncr/', {
            'title': 'Cracked housing', 'source': 'customer', 'severity': 'major',
            'product': 'Widget', 'detected_date': '2026-08-07',
            'disposition': 'scrap', 'owner': 'alice', 'description': 'Visible crack',
        }))
    assert resp.status_code == 201
    assert json.loads(resp.content)['data'] == {'id': 9, 'message': 'NCR created.'}
    assert seen == [('Cracked housing', 'customer', 'major', 'Widget', '2026-08-07',
                      'scrap', 'alice', 'Visible crack', 'q@example.com')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_ncr_post_defaults_source_and_severity():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1, 'email': 'q@example.com'}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(quality_core, 'create_ncr',
                      lambda c, title, source, severity, product, detected_date,
                             disposition, owner, notes, created_by:
                          seen.append((source, severity)) or 10):
        api_ncr(_auth_post_json('/api/v1/ncr/', {'title': 'Loose bolt'}))
    assert seen == [('internal', 'minor')]


def test_api_ncr_unsupported_method_returns_405():
    with _decorator_auth({'id': 1}):
        request = rf.delete('/api/v1/ncr/', HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_ncr(request)
    assert resp.status_code == 405
    assert json.loads(resp.content)['error'] == 'Method not allowed.'


def test_api_ncr_detail_requires_auth():
    resp = api_ncr_detail(rf.get('/api/v1/ncr/1/'), 1)
    assert resp.status_code == 401


def test_api_ncr_detail_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(quality_core, 'get_ncr', lambda c, ncr_id: None):
        resp = api_ncr_detail(_auth_get('/api/v1/ncr/99/'), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_ncr_detail_success():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(quality_core, 'get_ncr',
                      lambda c, ncr_id: {'id': 1, 'title': 'Bad batch'}):
        resp = api_ncr_detail(_auth_get('/api/v1/ncr/1/'), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'ncr': {'id': 1, 'title': 'Bad batch'}}


# ── maintenance ──────────────────────────────────────────────────────────

def test_api_maint_wo_list_requires_auth():
    resp = api_maint_wo_list(rf.get('/api/v1/maint/wo/'))
    assert resp.status_code == 401


def test_api_maint_wo_list_success():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'list_work_orders',
                      lambda c, status=None: [{'id': 1, 'status': 'open'}]):
        resp = api_maint_wo_list(_auth_get('/api/v1/maint/wo/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'work_orders': [{'id': 1, 'status': 'open'}]}
    assert conn.closed is True


def test_api_maint_wo_list_passes_through_status_query_param():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'list_work_orders',
                      lambda c, status=None: seen.append(status) or []):
        api_maint_wo_list(_auth_get('/api/v1/maint/wo/?status=open'))
    assert seen == ['open']


def test_api_maint_wo_detail_requires_auth():
    resp = api_maint_wo_detail(rf.get('/api/v1/maint/wo/1/'), 1)
    assert resp.status_code == 401


def test_api_maint_wo_detail_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'get_work_order', lambda c, wo_id: None):
        resp = api_maint_wo_detail(_auth_get('/api/v1/maint/wo/99/'), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_maint_wo_detail_success():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'get_work_order',
                      lambda c, wo_id: {'id': 1, 'status': 'open'}):
        resp = api_maint_wo_detail(_auth_get('/api/v1/maint/wo/1/'), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'work_order': {'id': 1, 'status': 'open'}}


def test_api_maint_wo_complete_requires_auth():
    resp = api_maint_wo_complete(rf.post('/api/v1/maint/wo/1/complete/'), 1)
    assert resp.status_code == 401


def test_api_maint_wo_complete_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'get_work_order', lambda c, wo_id: None):
        resp = api_maint_wo_complete(_auth_post('/api/v1/maint/wo/99/complete/'), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_maint_wo_complete_already_completed_returns_409():
    conn = _FakeConn()
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'get_work_order',
                      lambda c, wo_id: {'id': 1, 'status': 'completed'}):
        resp = api_maint_wo_complete(_auth_post('/api/v1/maint/wo/1/complete/'), 1)
    assert resp.status_code == 409
    assert json.loads(resp.content)['error'] == 'Work order is already completed.'


def test_api_maint_wo_complete_success():
    conn = _FakeConn()
    seen = []
    with _decorator_auth({'id': 1}), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(maintenance_core, 'get_work_order',
                      lambda c, wo_id: {'id': 1, 'status': 'open'}), \
         patch.object(maintenance_core, 'complete_work_order',
                      lambda c, wo_id: seen.append(wo_id)):
        resp = api_maint_wo_complete(_auth_post('/api/v1/maint/wo/1/complete/'), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Work order completed.'
    assert seen == [1]
    assert conn.committed is True
    assert conn.closed is True


# ── approval workflow ────────────────────────────────────────────────────
#
# api_workflow_decide dispatches to a domain-specific decision function
# based on the approval_step's entity_type (purchase_requisition/
# cycle_count/document), falling back to approval_workflow_core.decide_step
# for anything else — see the comment in api_views.py itself on why each
# domain needs its own sync wrapper. Its finally block always calls
# conn.close() again even after the except branch already closed it once
# (wrapped in try/except to swallow the double-close) — _FakeConn.close()
# tolerates being called twice, so that's not specially handled here.

_WF_USER = {'id': 4, 'email': 'approver@example.com', 'role': 'Department Manager'}


def test_api_workflow_pending_requires_auth():
    resp = api_workflow_pending(rf.get('/api/v1/workflow/pending/'))
    assert resp.status_code == 401


def test_api_workflow_pending_success_scopes_by_role():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(approval_workflow_core, 'get_pending_steps',
                      lambda c, approver_role=None: seen.append(approver_role) or
                          [{'id': 1, 'entity_type': 'purchase_requisition'}]):
        resp = api_workflow_pending(_auth_get('/api/v1/workflow/pending/'))
    assert resp.status_code == 200
    assert seen == ['Department Manager']
    assert json.loads(resp.content)['data'] == {
        'steps': [{'id': 1, 'entity_type': 'purchase_requisition'}]}
    assert conn.closed is True


def test_api_workflow_decide_requires_auth():
    resp = api_workflow_decide(rf.post('/api/v1/workflow/1/decide/'), 1)
    assert resp.status_code == 401


def test_api_workflow_decide_invalid_json_returns_400():
    with _decorator_auth(_WF_USER):
        request = rf.post('/api/v1/workflow/1/decide/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_workflow_decide(request, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_workflow_decide_rejects_invalid_decision_value():
    with _decorator_auth(_WF_USER):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {'decision': 'maybe'}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == "decision must be 'approved' or 'rejected'."


def test_api_workflow_decide_dispatches_to_requisition_handler():
    conn = _FakeConn(rows=[{'entity_type': 'purchase_requisition', 'entity_id': 5}])
    seen = []
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(purchase_requisitions_core, 'decide_requisition_via_workflow',
                      lambda c, entity_id, step_id, decision, decided_by, notes:
                          seen.append((entity_id, step_id, decision, decided_by, notes))
                          or 'dept_approved'):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {
                'decision': 'approved', 'notes': 'Looks fine',
            }), 1)
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data == {'overall': 'dept_approved', 'message': 'Step approved.'}
    assert seen == [(5, 1, 'approved', 'approver@example.com', 'Looks fine')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_workflow_decide_dispatches_to_cycle_count_handler():
    conn = _FakeConn(rows=[{'entity_type': 'cycle_count', 'entity_id': 7}])
    seen = []
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(cycle_count_core, 'decide_cycle_count',
                      lambda c, entity_id, step_id, decision, decided_by, notes:
                          seen.append(entity_id) or 'closed'):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {'decision': 'approved'}), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['overall'] == 'closed'
    assert seen == [7]


def test_api_workflow_decide_dispatches_to_document_handler():
    conn = _FakeConn(rows=[{'entity_type': 'document', 'entity_id': 9}])
    seen = []
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(document_control_core, 'decide_document',
                      lambda c, entity_id, step_id, decision, decided_by, notes:
                          seen.append(entity_id) or 'released'):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {'decision': 'rejected'}), 1)
    assert resp.status_code == 200
    data = json.loads(resp.content)['data']
    assert data == {'overall': 'released', 'message': 'Step rejected.'}
    assert seen == [9]


def test_api_workflow_decide_falls_back_to_generic_decide_step_when_step_not_found():
    conn = _FakeConn(rows=[])
    seen = []
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(approval_workflow_core, 'decide_step',
                      lambda c, step_id, decision, decided_by, notes:
                          seen.append((step_id, decision, decided_by, notes)) or 'pending'):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/99/decide/', {'decision': 'approved'}), 99)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['overall'] == 'pending'
    assert seen == [(99, 'approved', 'approver@example.com', '')]


def test_api_workflow_decide_falls_back_for_unrecognized_entity_type():
    conn = _FakeConn(rows=[{'entity_type': 'something_else', 'entity_id': 3}])
    seen = []
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(approval_workflow_core, 'decide_step',
                      lambda c, step_id, decision, decided_by, notes:
                          seen.append(step_id) or 'pending'):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {'decision': 'approved'}), 1)
    assert resp.status_code == 200
    assert seen == [1]


def test_api_workflow_decide_uses_user_id_when_email_missing():
    conn = _FakeConn(rows=[])
    seen = []
    user_no_email = {'id': 42, 'role': 'Department Manager'}
    with _decorator_auth(user_no_email), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(approval_workflow_core, 'decide_step',
                      lambda c, step_id, decision, decided_by, notes:
                          seen.append(decided_by) or 'pending'):
        api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {'decision': 'approved'}), 1)
    assert seen == ['42']


def test_api_workflow_decide_value_error_returns_400_and_closes_connection():
    conn = _FakeConn(rows=[{'entity_type': 'purchase_requisition', 'entity_id': 5}])
    with _decorator_auth(_WF_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(approval_workflow_core, 'ensure_approval_tables', lambda c: None), \
         patch.object(purchase_requisitions_core, 'decide_requisition_via_workflow',
                      side_effect=ValueError('Step already decided.')):
        resp = api_workflow_decide(
            _auth_post_json('/api/v1/workflow/1/decide/', {'decision': 'approved'}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Step already decided.'
    assert conn.closed is True
    assert conn.committed is False


# ── lots / serials ───────────────────────────────────────────────────────

_LOT_USER = {'id': 6, 'email': 'wh@example.com'}


def test_api_lot_list_get_requires_auth():
    resp = api_lot_list(rf.get('/api/v1/lots/'))
    assert resp.status_code == 401


def test_api_lot_list_get_success():
    conn = _FakeConn()
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'list_lots',
                      lambda c, product_id=None, status=None:
                          [{'id': 1, 'lot_number': 'LOT-1'}]):
        resp = api_lot_list(_auth_get('/api/v1/lots/'))
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {'lots': [{'id': 1, 'lot_number': 'LOT-1'}]}
    assert conn.closed is True


def test_api_lot_list_get_passes_through_product_id_and_status():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'list_lots',
                      lambda c, product_id=None, status=None:
                          seen.append((product_id, status)) or []):
        api_lot_list(_auth_get('/api/v1/lots/?product_id=5&status=active'))
    assert seen == [(5, 'active')]


def test_api_lot_list_get_defaults_product_id_to_none_when_absent():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'list_lots',
                      lambda c, product_id=None, status=None:
                          seen.append(product_id) or []):
        api_lot_list(_auth_get('/api/v1/lots/'))
    assert seen == [None]


def test_api_lot_list_post_invalid_json_returns_400():
    with _decorator_auth(_LOT_USER):
        request = rf.post('/api/v1/lots/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_lot_list(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_lot_list_post_requires_product_id_and_qty():
    with _decorator_auth(_LOT_USER):
        resp = api_lot_list(_auth_post_json('/api/v1/lots/', {'product_id': None, 'qty': 5}))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'product_id and qty are required.'


def test_api_lot_list_post_allows_zero_qty():
    # Unlike api_inventory_receive, this uses `qty is None` rather than
    # `not qty`, so qty=0 is accepted here (falsy-but-not-None) rather than
    # being rejected as "missing".
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'create_lot',
                      lambda c, **kwargs: seen.append(kwargs.get('qty')) or 1):
        resp = api_lot_list(_auth_post_json('/api/v1/lots/', {'product_id': 5, 'qty': 0}))
    assert resp.status_code == 201
    assert seen == [0.0]


def test_api_lot_list_post_success_creates_lot():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'create_lot',
                      lambda c, product_id, qty, received_date, expiry_date,
                             lot_number, notes, created_by:
                          seen.append((product_id, qty, received_date, expiry_date,
                                       lot_number, notes, created_by)) or 11):
        resp = api_lot_list(_auth_post_json('/api/v1/lots/', {
            'product_id': 5, 'qty': 100, 'received_date': '2026-08-01',
            'expiry_date': '2027-08-01', 'lot_number': 'LOT-CUSTOM',
            'notes': 'Fresh batch',
        }))
    assert resp.status_code == 201
    assert json.loads(resp.content)['data'] == {'id': 11, 'message': 'Lot created.'}
    assert seen == [(5, 100.0, '2026-08-01', '2027-08-01', 'LOT-CUSTOM',
                      'Fresh batch', 'wh@example.com')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_lot_list_post_lot_number_blank_becomes_none():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'create_lot',
                      lambda c, product_id, qty, received_date, expiry_date,
                             lot_number, notes, created_by:
                          seen.append(lot_number) or 12):
        api_lot_list(_auth_post_json('/api/v1/lots/', {
            'product_id': 5, 'qty': 100, 'lot_number': '',
        }))
    assert seen == [None]


def test_api_lot_list_unsupported_method_returns_405():
    with _decorator_auth(_LOT_USER):
        request = rf.delete('/api/v1/lots/', HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_lot_list(request)
    assert resp.status_code == 405
    assert json.loads(resp.content)['error'] == 'Method not allowed.'


def test_api_lot_expiry_requires_auth():
    resp = api_lot_expiry(rf.get('/api/v1/lots/expiry/'))
    assert resp.status_code == 401


def test_api_lot_expiry_defaults_to_thirty_days():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'get_expiry_alerts',
                      lambda c, days_ahead=30: seen.append(days_ahead) or []):
        resp = api_lot_expiry(_auth_get('/api/v1/lots/expiry/'))
    assert seen == [30]
    assert json.loads(resp.content)['data'] == {'alerts': [], 'days_ahead': 30}


def test_api_lot_expiry_uses_days_query_param():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'get_expiry_alerts',
                      lambda c, days_ahead=30: seen.append(days_ahead) or []):
        api_lot_expiry(_auth_get('/api/v1/lots/expiry/?days=7'))
    assert seen == [7]


def test_api_lot_detail_requires_auth():
    resp = api_lot_detail(rf.get('/api/v1/lots/1/'), 1)
    assert resp.status_code == 401


def test_api_lot_detail_not_found_returns_404():
    conn = _FakeConn()
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'get_lot', lambda c, lot_id: None):
        resp = api_lot_detail(_auth_get('/api/v1/lots/99/'), 99)
    assert resp.status_code == 404
    assert conn.closed is True


def test_api_lot_detail_success_combines_genealogy_and_serials():
    conn = _FakeConn()
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'get_lot',
                      lambda c, lot_id: {'id': 1, 'lot_number': 'LOT-1'}), \
         patch.object(lot_core, 'get_lot_genealogy',
                      lambda c, lot_id: [{'parent_lot_id': 2}]), \
         patch.object(lot_core, 'list_serials',
                      lambda c, lot_id=None: [{'serial_number': 'SN-1'}]):
        resp = api_lot_detail(_auth_get('/api/v1/lots/1/'), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data'] == {
        'lot': {'id': 1, 'lot_number': 'LOT-1'},
        'genealogy': [{'parent_lot_id': 2}],
        'serials': [{'serial_number': 'SN-1'}],
    }


def test_api_lot_status_requires_auth():
    resp = api_lot_status(rf.post('/api/v1/lots/1/status/'), 1)
    assert resp.status_code == 401


def test_api_lot_status_invalid_json_returns_400():
    with _decorator_auth(_LOT_USER):
        request = rf.post('/api/v1/lots/1/status/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_lot_status(request, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_lot_status_requires_status_field():
    with _decorator_auth(_LOT_USER):
        resp = api_lot_status(
            _auth_post_json('/api/v1/lots/1/status/', {'status': ' '}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'status is required.'


def test_api_lot_status_value_error_returns_400_and_closes_connection():
    conn = _FakeConn()
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'update_lot_status',
                      side_effect=ValueError('Invalid status transition.')):
        resp = api_lot_status(
            _auth_post_json('/api/v1/lots/1/status/', {'status': 'quarantined'}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid status transition.'
    assert conn.closed is True
    assert conn.committed is False


def test_api_lot_status_success():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'update_lot_status',
                      lambda c, lot_id, status, notes='': seen.append(
                          (lot_id, status, notes))):
        resp = api_lot_status(
            _auth_post_json('/api/v1/lots/1/status/', {
                'status': 'quarantined', 'notes': 'Suspect contamination',
            }), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Lot status set to quarantined.'
    assert seen == [(1, 'quarantined', 'Suspect contamination')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_serial_list_get_requires_auth():
    resp = api_serial_list(rf.get('/api/v1/serials/'))
    assert resp.status_code == 401


def test_api_serial_list_get_success_with_filters():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'list_serials',
                      lambda c, product_id=None, lot_id=None, status=None:
                          seen.append((product_id, lot_id, status)) or
                          [{'serial_number': 'SN-1'}]):
        resp = api_serial_list(
            _auth_get('/api/v1/serials/?product_id=5&lot_id=2&status=active'))
    assert resp.status_code == 200
    assert seen == [(5, 2, 'active')]
    assert json.loads(resp.content)['data'] == {'serials': [{'serial_number': 'SN-1'}]}
    assert conn.closed is True


def test_api_serial_list_get_defaults_filters_to_none():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'list_serials',
                      lambda c, product_id=None, lot_id=None, status=None:
                          seen.append((product_id, lot_id, status)) or []):
        api_serial_list(_auth_get('/api/v1/serials/'))
    assert seen == [(None, None, None)]


def test_api_serial_list_post_invalid_json_returns_400():
    with _decorator_auth(_LOT_USER):
        request = rf.post('/api/v1/serials/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_serial_list(request)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_serial_list_post_requires_serial_number_and_product_id():
    with _decorator_auth(_LOT_USER):
        resp = api_serial_list(_auth_post_json('/api/v1/serials/', {
            'serial_number': '  ', 'product_id': 5,
        }))
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'serial_number and product_id are required.'


def test_api_serial_list_post_success_creates_serial():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'create_serial',
                      lambda c, serial_number, product_id, lot_id, notes, created_by:
                          seen.append((serial_number, product_id, lot_id, notes,
                                       created_by)) or 21):
        resp = api_serial_list(_auth_post_json('/api/v1/serials/', {
            'serial_number': 'SN-100', 'product_id': 5, 'lot_id': 3,
            'notes': 'First unit',
        }))
    assert resp.status_code == 201
    assert json.loads(resp.content)['data'] == {'id': 21, 'message': 'Serial number created.'}
    assert seen == [('SN-100', 5, 3, 'First unit', 'wh@example.com')]
    assert conn.committed is True
    assert conn.closed is True


def test_api_serial_list_post_lot_id_optional():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'create_serial',
                      lambda c, serial_number, product_id, lot_id, notes, created_by:
                          seen.append(lot_id) or 22):
        api_serial_list(_auth_post_json('/api/v1/serials/', {
            'serial_number': 'SN-101', 'product_id': 5,
        }))
    assert seen == [None]


def test_api_serial_list_unsupported_method_returns_405():
    with _decorator_auth(_LOT_USER):
        request = rf.delete('/api/v1/serials/', HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_serial_list(request)
    assert resp.status_code == 405
    assert json.loads(resp.content)['error'] == 'Method not allowed.'


def test_api_serial_status_requires_auth():
    resp = api_serial_status(rf.post('/api/v1/serials/1/status/'), 1)
    assert resp.status_code == 401


def test_api_serial_status_invalid_json_returns_400():
    with _decorator_auth(_LOT_USER):
        request = rf.post('/api/v1/serials/1/status/', data=b'not json',
                           content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = api_serial_status(request, 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Invalid JSON.'


def test_api_serial_status_requires_status_field():
    with _decorator_auth(_LOT_USER):
        resp = api_serial_status(
            _auth_post_json('/api/v1/serials/1/status/', {'status': ''}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'status is required.'


def test_api_serial_status_value_error_returns_400():
    conn = _FakeConn()
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'update_serial_status',
                      side_effect=ValueError('Serial already scrapped.')):
        resp = api_serial_status(
            _auth_post_json('/api/v1/serials/1/status/', {'status': 'scrapped'}), 1)
    assert resp.status_code == 400
    assert json.loads(resp.content)['error'] == 'Serial already scrapped.'
    assert conn.closed is True


def test_api_serial_status_success():
    conn = _FakeConn()
    seen = []
    with _decorator_auth(_LOT_USER), \
         patch.multiple('manufacturing.api_views', get_db_connection=lambda: conn), \
         patch.object(lot_core, 'ensure_lot_tables', lambda c: None), \
         patch.object(lot_core, 'update_serial_status',
                      lambda c, serial_id, status, notes='': seen.append(
                          (serial_id, status, notes))):
        resp = api_serial_status(
            _auth_post_json('/api/v1/serials/1/status/', {'status': 'installed'}), 1)
    assert resp.status_code == 200
    assert json.loads(resp.content)['data']['message'] == 'Serial status set to installed.'
    assert seen == [(1, 'installed', '')]
    assert conn.committed is True
    assert conn.closed is True
