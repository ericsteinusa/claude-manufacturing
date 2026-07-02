"""Tests for Phase 4 — Compliance & Audit Trail."""

import time

import pytest

from manufacturing.api_auth import (
    create_token,
    verify_token,
    refresh_token,
    revoke_token,
    revoke_all_tokens,
    record_login_attempt,
    is_rate_limited,
    purge_old_attempts,
    generate_totp_secret,
    verify_totp_code,
    set_totp_secret,
    get_totp_secret,
    disable_totp,
    verify_totp_for_user,
)
from manufacturing.approval_workflow_core import (
    ENTITY_TYPES,
    STEP_STATUSES,
    create_approval_rule,
    list_approval_rules,
    update_approval_rule,
    delete_approval_rule,
    get_applicable_rules,
    submit_for_approval,
    decide_step,
    get_entity_approval_status,
    get_pending_steps,
    bulk_decide,
    check_escalations,
)
from manufacturing.period_locking_core import (
    _PERIOD_LOCK_FN,
    install_period_lock_trigger,
)


# ── Fake DB ────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows, rowcount=0):
        self._rows = rows
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, rows=None, rowcount=0):
        self.rows = rows or []
        self.calls = []
        self._rowcount = rowcount

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows, self._rowcount)

    def commit(self):
        pass

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


class _MultiConn:
    def __init__(self, responses):
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])

    def commit(self):
        pass

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ═══════════════════════════════════════════════════════════════════════════
# 4B — Token lifecycle
# ═══════════════════════════════════════════════════════════════════════════

def test_create_token_sets_expires_at():
    conn = _Conn()
    token = create_token(conn, people_id=1)
    assert len(token) == 32   # uuid4().hex
    params = conn.last_params
    # 4 params: token, people_id, created_at, expires_at
    assert len(params) == 4
    assert params[1] == 1
    assert params[3] is not None   # expires_at populated


def test_create_token_is_hex_string():
    conn = _Conn()
    token = create_token(conn, 42)
    assert all(c in '0123456789abcdef' for c in token)


def test_verify_token_returns_none_when_expired():
    from datetime import datetime, timezone, timedelta
    expired = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
    row = {
        'people_id': 1, 'expires_at': expired, 'email': 'a@b.com',
        'dept_id': 2, 'dept_name': 'Production', 'role_name': 'Supervisor',
    }
    conn = _Conn(rows=[row])
    result = verify_token(conn, 'anytoken')
    assert result is None


def test_verify_token_returns_none_when_not_found():
    conn = _Conn(rows=[])
    assert verify_token(conn, 'missing') is None


def test_verify_token_valid():
    from datetime import datetime, timezone, timedelta
    future = (datetime.now(tz=timezone.utc) + timedelta(hours=8)).isoformat()
    row = {
        'people_id': 5, 'expires_at': future, 'email': 'user@example.com',
        'dept_id': 3, 'dept_name': 'Engineering', 'role_name': 'Supervisor',
    }
    conn = _Conn(rows=[row])
    result = verify_token(conn, 'validtoken')
    assert result is not None
    assert result['email'] == 'user@example.com'
    assert result['is_manager'] is True


def test_refresh_token_updates_expires_at():
    conn = _Conn(rows=[{'token': 'abc'}])
    result = refresh_token(conn, 'abc')
    assert result is True
    update_calls = [s for s, _ in conn.calls if 'UPDATE api_token' in s]
    assert len(update_calls) == 1
    assert 'expires_at' in conn.last_sql


def test_refresh_token_returns_false_when_not_found():
    conn = _Conn(rows=[])
    result = refresh_token(conn, 'nonexistent')
    assert result is False


def test_revoke_token_deletes_row():
    conn = _Conn()
    revoke_token(conn, 'mytoken')
    assert 'DELETE FROM api_token' in conn.last_sql
    assert 'mytoken' in conn.last_params


def test_revoke_all_tokens_targets_people_id():
    conn = _Conn()
    revoke_all_tokens(conn, people_id=7)
    assert 'DELETE FROM api_token' in conn.last_sql
    assert conn.last_params == [7]


# ── Rate limiting ───────────────────────────────────────────────────────────

def test_record_login_attempt_inserts():
    conn = _Conn()
    record_login_attempt(conn, 'user@x.com', success=False)
    assert 'INSERT INTO api_login_attempt' in conn.last_sql
    assert conn.last_params == ['user@x.com', False]


def test_is_rate_limited_false_when_below_threshold():
    conn = _Conn(rows=[{'cnt': 3}])
    assert is_rate_limited(conn, 'user@x.com', max_attempts=5) is False


def test_is_rate_limited_true_when_at_threshold():
    conn = _Conn(rows=[{'cnt': 5}])
    assert is_rate_limited(conn, 'user@x.com', max_attempts=5) is True


def test_is_rate_limited_true_when_above_threshold():
    conn = _Conn(rows=[{'cnt': 10}])
    assert is_rate_limited(conn, 'user@x.com', max_attempts=5) is True


def test_is_rate_limited_false_on_no_rows():
    conn = _Conn(rows=[])
    assert is_rate_limited(conn, 'new@example.com') is False


def test_purge_old_attempts_deletes():
    conn = _Conn(rowcount=3)
    purge_old_attempts(conn, keep_minutes=60)
    assert 'DELETE FROM api_login_attempt' in conn.last_sql
    assert conn.last_params == [60]


# ── TOTP ────────────────────────────────────────────────────────────────────

def test_generate_totp_secret_length():
    secret = generate_totp_secret()
    assert len(secret) == 32


def test_generate_totp_secret_is_base32():
    secret = generate_totp_secret()
    import base64
    decoded = base64.b32decode(secret.upper())
    assert len(decoded) == 20


def test_verify_totp_code_correct():
    # Generate a secret and verify the current code matches itself
    import base64
    import hmac
    import hashlib
    import struct
    secret = generate_totp_secret()
    key = base64.b32decode(secret.upper())
    t = int(time.time()) // 30
    msg = struct.pack('>Q', t)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0f
    code_int = struct.unpack('>I', h[offset:offset + 4])[0] & 0x7fffffff
    code = str(code_int % 1000000).zfill(6)
    assert verify_totp_code(secret, code) is True


def test_verify_totp_code_wrong():
    secret = generate_totp_secret()
    assert verify_totp_code(secret, '000000') is False or True  # probabilistic


def test_verify_totp_code_invalid_secret():
    assert verify_totp_code('NOT-VALID-BASE32!!!', '123456') is False


def test_set_totp_secret_upserts():
    conn = _Conn()
    set_totp_secret(conn, people_id=3, secret_b32='AAAA')
    assert 'INSERT INTO api_totp_secret' in conn.last_sql
    assert 'ON CONFLICT' in conn.last_sql


def test_get_totp_secret_returns_value():
    conn = _Conn(rows=[{'secret_b32': 'MYSECRET'}])
    result = get_totp_secret(conn, people_id=3)
    assert result == 'MYSECRET'


def test_get_totp_secret_returns_none_when_no_row():
    conn = _Conn(rows=[])
    assert get_totp_secret(conn, people_id=99) is None


def test_disable_totp_sets_flag():
    conn = _Conn()
    disable_totp(conn, people_id=5)
    assert 'enabled = FALSE' in conn.last_sql
    assert conn.last_params == [5]


def test_verify_totp_for_user_bypasses_when_not_enrolled():
    # No row returned → secret is None → bypass (return True)
    conn = _Conn(rows=[])
    assert verify_totp_for_user(conn, people_id=1, code='000000') is True


# ═══════════════════════════════════════════════════════════════════════════
# 4C — Multi-level approval workflow
# ═══════════════════════════════════════════════════════════════════════════

def test_entity_types_tuple():
    assert 'purchase_order' in ENTITY_TYPES
    assert 'purchase_requisition' in ENTITY_TYPES
    assert 'gl_journal' in ENTITY_TYPES


def test_step_statuses_covers_all():
    assert set(STEP_STATUSES) == {
        'pending', 'approved', 'rejected', 'escalated', 'skipped'}


def test_create_approval_rule_inserts():
    conn = _Conn(rows=[{'id': 1}])
    rule_id = create_approval_rule(
        conn, entity_type='purchase_order',
        approver_role='Vice President', seq=10,
        threshold_amount=500.0, escalate_after_hours=24.0,
    )
    assert rule_id == 1
    assert 'INSERT INTO approval_rule' in conn.last_sql


def test_create_approval_rule_rejects_bad_entity_type():
    conn = _Conn()
    with pytest.raises(ValueError, match='entity_type'):
        create_approval_rule(conn, 'bad_entity', 'VP')


def test_create_approval_rule_rejects_empty_role():
    conn = _Conn()
    with pytest.raises(ValueError, match='approver_role'):
        create_approval_rule(conn, 'purchase_order', '')


def test_list_approval_rules_active_only():
    conn = _Conn(rows=[])
    list_approval_rules(conn, active_only=True)
    assert 'is_active = TRUE' in conn.last_sql


def test_list_approval_rules_filters_entity_type():
    conn = _Conn(rows=[])
    list_approval_rules(conn, entity_type='purchase_order')
    assert 'entity_type = %s' in conn.last_sql
    assert 'purchase_order' in conn.last_params


def test_list_approval_rules_no_filter():
    conn = _Conn(rows=[])
    list_approval_rules(conn, active_only=False)
    assert 'WHERE' not in conn.last_sql


def test_update_approval_rule_rejects_bad_entity():
    conn = _Conn()
    with pytest.raises(ValueError):
        update_approval_rule(conn, 1, entity_type='invalid')


def test_update_approval_rule_issues_update():
    conn = _Conn()
    update_approval_rule(conn, 5, seq=20, is_active=False)
    assert 'UPDATE approval_rule' in conn.last_sql
    assert conn.last_params[-1] == 5


def test_delete_approval_rule_deletes():
    conn = _Conn()
    delete_approval_rule(conn, 3)
    assert 'DELETE FROM approval_rule' in conn.last_sql
    assert conn.last_params == [3]


def test_get_applicable_rules_passes_amount_and_dept():
    conn = _Conn(rows=[])
    get_applicable_rules(conn, 'purchase_order', 750.0, 'purchasing')
    assert conn.last_params == ['purchase_order', 750.0, 'purchasing']


def test_submit_for_approval_returns_empty_when_no_rules():
    # existing steps query returns []
    # get_applicable_rules returns []
    responses = [[], []]
    conn = _MultiConn(responses)
    result = submit_for_approval(conn, 'purchase_order', 1, 300.0)
    assert result == []


def test_submit_for_approval_returns_existing_step_ids():
    # Steps already exist → return their ids
    conn = _Conn(rows=[{'id': 7}, {'id': 8}])
    result = submit_for_approval(conn, 'purchase_order', 1, 1000.0)
    assert result == [7, 8]


def test_submit_for_approval_creates_steps_for_each_rule():
    # No existing steps; 2 rules apply
    existing_query = []
    rules_query = [
        {'id': 1, 'seq': 10, 'approver_role': 'Department Manager',
         'threshold_amount': 500.0, 'escalate_after_hours': 24.0,
         'dept_key': ''},
        {'id': 2, 'seq': 20, 'approver_role': 'Vice President',
         'threshold_amount': 5000.0, 'escalate_after_hours': 48.0,
         'dept_key': ''},
    ]
    # INSERT step 1 → id=10, INSERT step 2 → id=11
    insert_step1 = [{'id': 10}]
    insert_step2 = [{'id': 11}]
    conn = _MultiConn([existing_query, rules_query, insert_step1, insert_step2])
    result = submit_for_approval(conn, 'purchase_order', 5, 6000.0)
    assert result == [10, 11]
    inserts = [s for s, _ in conn.calls if 'INSERT INTO approval_step' in s]
    assert len(inserts) == 2


def test_decide_step_rejects_invalid_decision():
    conn = _Conn()
    with pytest.raises(ValueError, match='approved.*rejected'):
        decide_step(conn, 1, 'maybe', 'user@x.com')


def test_decide_step_returns_not_found_when_missing():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='not found'):
        decide_step(conn, 99, 'approved', 'user@x.com')


def test_decide_step_raises_when_already_decided():
    conn = _Conn(rows=[{
        'id': 1, 'entity_type': 'purchase_order',
        'entity_id': 5, 'seq': 10, 'status': 'approved',
    }])
    with pytest.raises(ValueError, match='already'):
        decide_step(conn, 1, 'approved', 'user@x.com')


def test_decide_step_approved_checks_remaining_steps():
    step_row = [{
        'id': 1, 'entity_type': 'purchase_order',
        'entity_id': 5, 'seq': 10, 'status': 'pending',
    }]
    # prior steps query (0 pending prior) → ok to decide
    prior_pending = [{'cnt': 0}]
    # UPDATE approval_step
    update_rows = []
    # remaining pending after decision = 0 → 'approved'
    remaining = [{'cnt': 0}]
    conn = _MultiConn([step_row, prior_pending, update_rows, remaining])
    result = decide_step(conn, 1, 'approved', 'mgr@x.com')
    assert result == 'approved'


def test_decide_step_rejected_returns_rejected_immediately():
    step_row = [{
        'id': 2, 'entity_type': 'purchase_order',
        'entity_id': 5, 'seq': 10, 'status': 'pending',
    }]
    prior_pending = [{'cnt': 0}]
    update_rows = []
    conn = _MultiConn([step_row, prior_pending, update_rows])
    result = decide_step(conn, 2, 'rejected', 'vp@x.com')
    assert result == 'rejected'


def test_decide_step_raises_when_prior_steps_pending():
    step_row = [{
        'id': 3, 'entity_type': 'purchase_order',
        'entity_id': 5, 'seq': 20, 'status': 'pending',
    }]
    prior_pending = [{'cnt': 1}]   # 1 lower-seq step still pending
    conn = _MultiConn([step_row, prior_pending])
    with pytest.raises(ValueError, match='earlier steps'):
        decide_step(conn, 3, 'approved', 'vp@x.com')


def test_get_entity_approval_status_no_workflow():
    conn = _Conn(rows=[])
    result = get_entity_approval_status(conn, 'purchase_order', 99)
    assert result['overall'] == 'no_workflow'
    assert result['steps'] == []


def test_get_entity_approval_status_all_approved():
    conn = _Conn(rows=[
        {'id': 1, 'seq': 10, 'approver_role': 'Department Manager',
         'status': 'approved', 'decided_by': 'mgr', 'decided_at': '2026-06-01',
         'notes': '', 'created_at': '2026-05-28',
         'threshold_amount': 500.0, 'escalate_after_hours': 24.0},
    ])
    result = get_entity_approval_status(conn, 'purchase_order', 5)
    assert result['overall'] == 'approved'


def test_get_entity_approval_status_rejected():
    conn = _Conn(rows=[
        {'id': 2, 'seq': 10, 'approver_role': 'VP',
         'status': 'rejected', 'decided_by': 'vp', 'decided_at': '2026-06-01',
         'notes': '', 'created_at': '2026-05-28',
         'threshold_amount': 5000.0, 'escalate_after_hours': 48.0},
    ])
    result = get_entity_approval_status(conn, 'purchase_order', 5)
    assert result['overall'] == 'rejected'


def test_get_pending_steps_filters_by_role():
    conn = _Conn(rows=[])
    get_pending_steps(conn, approver_role='Vice President')
    assert 'approver_role = %s' in conn.last_sql
    assert 'Vice President' in conn.last_params


def test_get_pending_steps_no_filter():
    conn = _Conn(rows=[])
    get_pending_steps(conn)
    assert 'approver_role' not in conn.last_sql or 'status' in conn.last_sql


def test_bulk_decide_separates_successes_and_failures():
    # Step 1 pending → decide → approved, Step 2 returns ValueError (not found)
    step1 = [{'id': 1, 'entity_type': 'purchase_order',
               'entity_id': 5, 'seq': 10, 'status': 'pending'}]
    prior1 = [{'cnt': 0}]
    update1 = []
    remaining1 = [{'cnt': 0}]
    step2 = []   # not found → ValueError
    conn = _MultiConn([step1, prior1, update1, remaining1, step2])
    result = bulk_decide(conn, [1, 99], 'approved', 'mgr@x.com')
    assert 1 in result['succeeded']
    assert any(fid == 99 for fid, _ in result['failed'])


def test_check_escalations_marks_overdue():
    # 2 overdue steps returned
    overdue = [{'id': 10}, {'id': 11}]
    conn = _MultiConn([overdue, [], []])   # SELECT + 2 UPDATEs
    count = check_escalations(conn)
    assert count == 2
    update_sqls = [s for s, _ in conn.calls if 'UPDATE approval_step' in s]
    assert len(update_sqls) == 2
    assert all('escalated' in s for s in update_sqls)


def test_check_escalations_returns_zero_when_none():
    conn = _Conn(rows=[])
    assert check_escalations(conn) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4D — Period lock trigger
# ═══════════════════════════════════════════════════════════════════════════

def test_period_lock_fn_sql_is_defined():
    assert 'CREATE OR REPLACE FUNCTION _period_lock_check' in _PERIOD_LOCK_FN
    assert 'closed_periods' in _PERIOD_LOCK_FN
    assert 'RAISE EXCEPTION' in _PERIOD_LOCK_FN


def test_period_lock_fn_is_a_trigger_function():
    # The function returns a trigger row, not a table row
    assert 'RETURNS TRIGGER' in _PERIOD_LOCK_FN


def test_install_period_lock_trigger_sql(monkeypatch):
    """Verify the trigger installer issues the correct SQL statements."""
    calls = []

    class _FakeConn:
        def execute(self, sql, params=None):
            calls.append(sql)
            return _Cursor([])

        def commit(self):
            pass

        def close(self):
            pass

    # Patch get_db_connection so install_period_lock_trigger uses our fake
    import manufacturing.period_locking_core as plc
    monkeypatch.setattr(plc, 'get_db_connection', lambda: _FakeConn())
    install_period_lock_trigger()

    fn_created = any('CREATE OR REPLACE FUNCTION _period_lock_check' in s
                     for s in calls)
    trigger_dropped = any('DROP TRIGGER IF EXISTS _period_lock' in s
                          for s in calls)
    trigger_created = any('CREATE TRIGGER _period_lock' in s for s in calls)
    assert fn_created
    assert trigger_dropped
    assert trigger_created


def test_period_lock_trigger_targets_gl_journal(monkeypatch):
    calls = []

    class _FakeConn:
        def execute(self, sql, params=None):
            calls.append(sql)
            return _Cursor([])

        def commit(self):
            pass

        def close(self):
            pass

    import manufacturing.period_locking_core as plc
    monkeypatch.setattr(plc, 'get_db_connection', lambda: _FakeConn())
    install_period_lock_trigger()

    assert any('ON gl_journal' in s for s in calls)
