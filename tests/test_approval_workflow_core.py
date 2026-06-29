"""Tests for approval_workflow_core — Qt-free, no live database."""
import pytest
from manufacturing.approval_workflow_core import (
    ENTITY_TYPES,
    STEP_STATUSES,
    ensure_approval_tables,
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


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = list(rows or [])

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Conn that serves a pre-loaded sequence of row-sets, one per execute()."""

    def __init__(self, *row_sequences):
        self.calls: list[tuple] = []
        self._seq = list(row_sequences)
        self._idx = 0

    def execute(self, sql, params=None):
        self.calls.append((sql.strip(), params))
        rows = self._seq[self._idx] if self._idx < len(self._seq) else []
        self._idx += 1
        return _FakeCursor(rows)

    def _sqls(self):
        return [sql for sql, _ in self.calls]

    def _params(self):
        return [p for _, p in self.calls]


def _row(**kwargs):
    """Return a dict-like object that supports item access."""
    return kwargs


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_entity_types_contains_expected():
    assert 'purchase_order' in ENTITY_TYPES
    assert 'purchase_requisition' in ENTITY_TYPES
    assert 'gl_journal' in ENTITY_TYPES


def test_step_statuses_contains_expected():
    for s in ('pending', 'approved', 'rejected', 'escalated', 'skipped'):
        assert s in STEP_STATUSES


# ---------------------------------------------------------------------------
# ensure_approval_tables
# ---------------------------------------------------------------------------

def test_ensure_approval_tables_creates_both_tables():
    conn = _FakeConn()
    ensure_approval_tables(conn)
    sqls = conn._sqls()
    assert any('CREATE TABLE IF NOT EXISTS approval_rule' in s for s in sqls)
    assert any('CREATE TABLE IF NOT EXISTS approval_step' in s for s in sqls)


def test_ensure_approval_tables_creates_indexes():
    conn = _FakeConn()
    ensure_approval_tables(conn)
    sqls = conn._sqls()
    assert any('CREATE INDEX IF NOT EXISTS approval_step_entity' in s for s in sqls)
    assert any('CREATE INDEX IF NOT EXISTS approval_step_role_pending' in s for s in sqls)


# ---------------------------------------------------------------------------
# create_approval_rule
# ---------------------------------------------------------------------------

def test_create_approval_rule_invalid_entity_type():
    conn = _FakeConn()
    with pytest.raises(ValueError, match="entity_type"):
        create_approval_rule(conn, 'bad_type', 'Manager')


def test_create_approval_rule_empty_role():
    conn = _FakeConn()
    with pytest.raises(ValueError, match="approver_role"):
        create_approval_rule(conn, 'purchase_order', '')


def test_create_approval_rule_returns_id():
    conn = _FakeConn([_row(id=42)])
    result = create_approval_rule(conn, 'purchase_order', 'Vice President',
                                  threshold_amount=500.0)
    assert result == 42


def test_create_approval_rule_passes_correct_params():
    conn = _FakeConn([_row(id=1)])
    create_approval_rule(conn, 'purchase_requisition', 'Department Manager',
                         seq=20, dept_key='purchasing', threshold_amount=250.0,
                         escalate_after_hours=48.0, notes='test')
    _, params = conn.calls[0]
    assert 'purchase_requisition' in params
    assert 'purchasing' in params
    assert 250.0 in params
    assert 'Department Manager' in params
    assert 20 in params
    assert 48.0 in params


# ---------------------------------------------------------------------------
# list_approval_rules
# ---------------------------------------------------------------------------

def test_list_approval_rules_active_only_adds_where():
    conn = _FakeConn([])
    list_approval_rules(conn, active_only=True)
    sql, _ = conn.calls[0]
    assert 'is_active = TRUE' in sql


def test_list_approval_rules_entity_type_filter():
    conn = _FakeConn([])
    list_approval_rules(conn, entity_type='gl_journal')
    sql, params = conn.calls[0]
    assert 'entity_type = %s' in sql
    assert params and 'gl_journal' in params


def test_list_approval_rules_returns_dicts():
    row = _row(id=1, entity_type='purchase_order', dept_key='', threshold_amount=500.0,
               approver_role='VP', seq=10, escalate_after_hours=24.0,
               is_active=True, notes='')
    conn = _FakeConn([row])
    result = list_approval_rules(conn)
    assert isinstance(result, list)
    assert result[0]['id'] == 1


def test_list_approval_rules_no_filter_no_where_on_type():
    conn = _FakeConn([])
    list_approval_rules(conn, active_only=False)
    sql, _ = conn.calls[0]
    assert 'entity_type = %s' not in sql  # no WHERE filter on entity_type


# ---------------------------------------------------------------------------
# update_approval_rule
# ---------------------------------------------------------------------------

def test_update_approval_rule_ignores_unknown_fields():
    conn = _FakeConn()
    update_approval_rule(conn, 1, bogus_field='x')
    assert len(conn.calls) == 0  # no-op


def test_update_approval_rule_invalid_entity_type():
    conn = _FakeConn()
    with pytest.raises(ValueError, match="entity_type"):
        update_approval_rule(conn, 1, entity_type='bad')


def test_update_approval_rule_builds_set_clause():
    conn = _FakeConn()
    update_approval_rule(conn, 7, threshold_amount=1000.0, notes='hi')
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert 'UPDATE approval_rule SET' in sql
    assert 7 in params


# ---------------------------------------------------------------------------
# delete_approval_rule
# ---------------------------------------------------------------------------

def test_delete_approval_rule_issues_delete():
    conn = _FakeConn()
    delete_approval_rule(conn, 3)
    sql, params = conn.calls[0]
    assert 'DELETE FROM approval_rule' in sql
    assert params == (3,)


# ---------------------------------------------------------------------------
# get_applicable_rules
# ---------------------------------------------------------------------------

def test_get_applicable_rules_passes_entity_type_and_amount():
    conn = _FakeConn([])
    get_applicable_rules(conn, 'purchase_order', 600.0)
    sql, params = conn.calls[0]
    assert 'purchase_order' in params
    assert 600.0 in params


def test_get_applicable_rules_returns_dicts():
    row = _row(id=1, entity_type='purchase_order', dept_key='',
               threshold_amount=500.0, approver_role='VP',
               seq=10, escalate_after_hours=24.0)
    conn = _FakeConn([row])
    result = get_applicable_rules(conn, 'purchase_order', 600.0)
    assert len(result) == 1
    assert result[0]['approver_role'] == 'VP'


def test_get_applicable_rules_passes_dept_key():
    conn = _FakeConn([])
    get_applicable_rules(conn, 'purchase_requisition', 100.0, dept_key='engineering')
    _, params = conn.calls[0]
    assert 'engineering' in params


# ---------------------------------------------------------------------------
# submit_for_approval
# ---------------------------------------------------------------------------

def test_submit_for_approval_idempotent_returns_existing():
    # First execute returns existing steps, so no new steps created.
    existing = [_row(id=10), _row(id=11)]
    conn = _FakeConn(existing)
    result = submit_for_approval(conn, 'purchase_order', 99, 600.0)
    assert result == [10, 11]
    # Only one DB call (the existence check) should have been made.
    assert len(conn.calls) == 1


def test_submit_for_approval_creates_steps_for_rules():
    # No existing steps, one applicable rule, step created with id=5.
    rule = _row(id=1, entity_type='purchase_order', dept_key='', threshold_amount=500.0,
                approver_role='VP', seq=10, escalate_after_hours=24.0)
    conn = _FakeConn(
        [],          # existence check → no existing steps
        [rule],      # get_applicable_rules
        [_row(id=5)],  # INSERT step RETURNING id
    )
    result = submit_for_approval(conn, 'purchase_order', 1, 600.0, requested_by='alice')
    assert result == [5]


def test_submit_for_approval_no_rules_returns_empty():
    conn = _FakeConn(
        [],   # no existing steps
        [],   # no applicable rules
    )
    result = submit_for_approval(conn, 'purchase_order', 1, 100.0)
    assert result == []


def test_submit_for_approval_creates_one_step_per_rule():
    rule1 = _row(id=1, entity_type='purchase_order', dept_key='', threshold_amount=500.0,
                 approver_role='Manager', seq=10, escalate_after_hours=24.0)
    rule2 = _row(id=2, entity_type='purchase_order', dept_key='', threshold_amount=5000.0,
                 approver_role='VP', seq=20, escalate_after_hours=24.0)
    conn = _FakeConn(
        [],               # no existing steps
        [rule1, rule2],   # two applicable rules
        [_row(id=10)],    # step 1 insert
        [_row(id=11)],    # step 2 insert
    )
    result = submit_for_approval(conn, 'purchase_order', 1, 6000.0)
    assert result == [10, 11]


# ---------------------------------------------------------------------------
# decide_step
# ---------------------------------------------------------------------------

def test_decide_step_invalid_decision():
    conn = _FakeConn()
    with pytest.raises(ValueError, match="decision"):
        decide_step(conn, 1, 'maybe', 'alice')


def test_decide_step_step_not_found():
    conn = _FakeConn([])  # empty result for SELECT
    with pytest.raises(ValueError, match="not found"):
        decide_step(conn, 99, 'approved', 'alice')


def test_decide_step_already_decided():
    step = _row(id=1, entity_type='purchase_order', entity_id=5,
                seq=10, status='approved')
    conn = _FakeConn([step])
    with pytest.raises(ValueError, match="already"):
        decide_step(conn, 1, 'approved', 'alice')


def test_decide_step_prior_steps_pending():
    step = _row(id=2, entity_type='purchase_order', entity_id=5,
                seq=20, status='pending')
    conn = _FakeConn(
        [step],          # step lookup
        [_row(cnt=1)],   # prior steps check → 1 pending prior
    )
    with pytest.raises(ValueError, match="earlier steps"):
        decide_step(conn, 2, 'approved', 'alice')


def test_decide_step_approved_all_done_returns_approved():
    step = _row(id=1, entity_type='purchase_order', entity_id=5,
                seq=10, status='pending')
    conn = _FakeConn(
        [step],           # step lookup
        [_row(cnt=0)],    # no prior pending
        [],               # UPDATE step
        [_row(cnt=0)],    # remaining pending → 0
    )
    result = decide_step(conn, 1, 'approved', 'alice')
    assert result == 'approved'


def test_decide_step_approved_more_remaining_returns_pending():
    step = _row(id=1, entity_type='purchase_order', entity_id=5,
                seq=10, status='pending')
    conn = _FakeConn(
        [step],
        [_row(cnt=0)],    # no prior pending
        [],               # UPDATE
        [_row(cnt=1)],    # 1 remaining pending
    )
    result = decide_step(conn, 1, 'approved', 'alice')
    assert result == 'pending'


def test_decide_step_rejected_returns_rejected_immediately():
    step = _row(id=1, entity_type='purchase_order', entity_id=5,
                seq=10, status='pending')
    conn = _FakeConn(
        [step],
        [_row(cnt=0)],    # no prior pending
        [],               # UPDATE
    )
    result = decide_step(conn, 1, 'rejected', 'bob', notes='too expensive')
    assert result == 'rejected'
    # Should not query remaining steps after a rejection.
    assert len(conn.calls) == 3


# ---------------------------------------------------------------------------
# get_entity_approval_status
# ---------------------------------------------------------------------------

def test_get_entity_approval_status_no_steps_returns_no_workflow():
    conn = _FakeConn([])
    result = get_entity_approval_status(conn, 'purchase_order', 1)
    assert result['overall'] == 'no_workflow'
    assert result['steps'] == []


def test_get_entity_approval_status_all_approved():
    steps = [
        _row(id=1, seq=10, approver_role='Manager', status='approved',
             decided_by='alice', decided_at='2026-01-01', notes='',
             created_at='2026-01-01', threshold_amount=500.0,
             escalate_after_hours=24.0),
    ]
    conn = _FakeConn(steps)
    result = get_entity_approval_status(conn, 'purchase_order', 5)
    assert result['overall'] == 'approved'


def test_get_entity_approval_status_any_rejected_is_rejected():
    steps = [
        _row(id=1, seq=10, approver_role='Manager', status='rejected',
             decided_by='bob', decided_at='2026-01-01', notes='',
             created_at='2026-01-01', threshold_amount=500.0,
             escalate_after_hours=24.0),
        _row(id=2, seq=20, approver_role='VP', status='pending',
             decided_by='', decided_at=None, notes='',
             created_at='2026-01-01', threshold_amount=5000.0,
             escalate_after_hours=24.0),
    ]
    conn = _FakeConn(steps)
    result = get_entity_approval_status(conn, 'purchase_order', 5)
    assert result['overall'] == 'rejected'


def test_get_entity_approval_status_mixed_is_pending():
    steps = [
        _row(id=1, seq=10, approver_role='Manager', status='approved',
             decided_by='alice', decided_at='2026-01-01', notes='',
             created_at='2026-01-01', threshold_amount=500.0,
             escalate_after_hours=24.0),
        _row(id=2, seq=20, approver_role='VP', status='pending',
             decided_by='', decided_at=None, notes='',
             created_at='2026-01-01', threshold_amount=5000.0,
             escalate_after_hours=24.0),
    ]
    conn = _FakeConn(steps)
    result = get_entity_approval_status(conn, 'purchase_order', 5)
    assert result['overall'] == 'pending'
    assert len(result['steps']) == 2


# ---------------------------------------------------------------------------
# get_pending_steps
# ---------------------------------------------------------------------------

def test_get_pending_steps_no_role_filter():
    conn = _FakeConn([])
    get_pending_steps(conn)
    sql, params = conn.calls[0]
    assert "status = 'pending'" in sql
    assert not params  # no role filter


def test_get_pending_steps_role_filter():
    conn = _FakeConn([])
    get_pending_steps(conn, approver_role='Vice President')
    sql, params = conn.calls[0]
    assert 'approver_role = %s' in sql
    assert params == ['Vice President']


def test_get_pending_steps_returns_dicts():
    row = _row(id=1, entity_type='purchase_order', entity_id=5, seq=10,
               approver_role='VP', created_at='2026-01-01',
               threshold_amount=500.0, escalate_after_hours=24.0)
    conn = _FakeConn([row])
    result = get_pending_steps(conn)
    assert isinstance(result, list)
    assert result[0]['approver_role'] == 'VP'


# ---------------------------------------------------------------------------
# bulk_decide
# ---------------------------------------------------------------------------

def test_bulk_decide_all_succeed():
    step = _row(id=1, entity_type='purchase_order', entity_id=5,
                seq=10, status='pending')
    step2 = _row(id=2, entity_type='purchase_order', entity_id=5,
                 seq=10, status='pending')
    conn = _FakeConn(
        [step],  [_row(cnt=0)], [], [_row(cnt=0)],  # step 1
        [step2], [_row(cnt=0)], [], [_row(cnt=0)],  # step 2
    )
    result = bulk_decide(conn, [1, 2], 'approved', 'alice')
    assert result['succeeded'] == [1, 2]
    assert result['failed'] == []


def test_bulk_decide_partial_failure():
    step = _row(id=1, entity_type='purchase_order', entity_id=5,
                seq=10, status='pending')
    # Step 1 succeeds, step 2 has no row (not found)
    conn = _FakeConn(
        [step], [_row(cnt=0)], [], [_row(cnt=0)],  # step 1: succeed
        [],                                          # step 2: not found
    )
    result = bulk_decide(conn, [1, 2], 'approved', 'alice')
    assert 1 in result['succeeded']
    assert any(sid == 2 for sid, _ in result['failed'])


def test_bulk_decide_returns_error_reasons():
    conn = _FakeConn(
        [],   # step 1 not found
    )
    result = bulk_decide(conn, [99], 'approved', 'alice')
    assert result['succeeded'] == []
    assert len(result['failed']) == 1
    sid, reason = result['failed'][0]
    assert sid == 99
    assert 'not found' in reason.lower()


# ---------------------------------------------------------------------------
# check_escalations
# ---------------------------------------------------------------------------

def test_check_escalations_returns_count():
    overdue = [_row(id=3), _row(id=7)]
    # First call: SELECT overdue; then one UPDATE per row
    conn = _FakeConn(overdue, [], [])
    count = check_escalations(conn)
    assert count == 2


def test_check_escalations_issues_updates():
    overdue = [_row(id=5)]
    conn = _FakeConn(overdue, [])
    check_escalations(conn)
    update_sqls = [s for s, _ in conn.calls if 'UPDATE approval_step' in s]
    assert len(update_sqls) == 1
    assert "status='escalated'" in update_sqls[0]


def test_check_escalations_zero_when_none_overdue():
    conn = _FakeConn([])
    count = check_escalations(conn)
    assert count == 0
