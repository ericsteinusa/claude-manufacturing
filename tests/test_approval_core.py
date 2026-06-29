"""
Tests for approval_core.py — PO approval workflow.
"""

import pytest
from unittest.mock import MagicMock

from manufacturing.approval_core import (
    needs_approval,
    request_approval,
    approve_po,
    reject_po,
    count_pending,
    get_po_approval,
    APPROVAL_THRESHOLD,
    APPROVAL_ROLES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(fetchone_result=None, fetchall_result=None):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = fetchone_result
    conn.execute.return_value.fetchall.return_value = fetchall_result or []
    return conn


# ---------------------------------------------------------------------------
# needs_approval
# ---------------------------------------------------------------------------

def test_below_threshold_no_approval():
    assert needs_approval(APPROVAL_THRESHOLD - 0.01) is False


def test_at_threshold_no_approval():
    assert needs_approval(APPROVAL_THRESHOLD) is False


def test_above_threshold_needs_approval():
    assert needs_approval(APPROVAL_THRESHOLD + 0.01) is True


def test_none_total_no_approval():
    assert needs_approval(None) is False


def test_zero_total_no_approval():
    assert needs_approval(0) is False


# ---------------------------------------------------------------------------
# request_approval
# ---------------------------------------------------------------------------

def test_request_approval_inserts_record():
    conn = _conn(fetchone_result=(42,))
    result = request_approval(conn, po_id=7, requested_by='buyer@example.com')
    assert result == 42
    insert_call = conn.execute.call_args_list[0]
    sql, params = insert_call[0]
    assert 'INSERT INTO po_approval' in sql
    assert params == (7, 'buyer@example.com')


def test_request_approval_sets_pending_approval_status():
    conn = _conn(fetchone_result=(1,))
    request_approval(conn, po_id=7, requested_by='buyer@example.com')
    update_call = conn.execute.call_args_list[1]
    sql, params = update_call[0]
    assert 'pending_approval' in sql
    assert params == (7,)


def test_request_approval_returns_id():
    conn = _conn(fetchone_result=(99,))
    assert request_approval(conn, 5, 'x@x.com') == 99


# ---------------------------------------------------------------------------
# approve_po
# ---------------------------------------------------------------------------

def test_approve_updates_approval_record():
    conn = _conn(fetchone_result=(3,))  # po_id=3
    approve_po(conn, approval_id=10, decided_by='vp@example.com', notes='OK')
    calls = conn.execute.call_args_list
    assert any('approved' in str(c) for c in calls)
    assert any("status = 'sent'" in str(c) for c in calls)


def test_approve_raises_if_not_found():
    conn = _conn(fetchone_result=None)
    with pytest.raises(ValueError, match='not found or already decided'):
        approve_po(conn, approval_id=99, decided_by='vp@example.com')


def test_approve_advances_po_to_sent():
    conn = _conn(fetchone_result=(7,))
    approve_po(conn, approval_id=1, decided_by='president@example.com')
    calls = [str(c) for c in conn.execute.call_args_list]
    assert any("'sent'" in c and 'purchase_order' in c for c in calls)


# ---------------------------------------------------------------------------
# reject_po
# ---------------------------------------------------------------------------

def test_reject_updates_approval_record():
    conn = _conn(fetchone_result=(5,))
    reject_po(conn, approval_id=10, decided_by='vp@example.com', notes='Over budget')
    calls = conn.execute.call_args_list
    assert any('rejected' in str(c) for c in calls)


def test_reject_raises_if_not_found():
    conn = _conn(fetchone_result=None)
    with pytest.raises(ValueError, match='not found or already decided'):
        reject_po(conn, approval_id=99, decided_by='vp@example.com')


def test_reject_returns_po_to_draft():
    conn = _conn(fetchone_result=(4,))
    reject_po(conn, approval_id=2, decided_by='vp@example.com')
    calls = [str(c) for c in conn.execute.call_args_list]
    assert any("'draft'" in c and 'purchase_order' in c for c in calls)


def test_reject_stores_notes():
    conn = _conn(fetchone_result=(4,))
    reject_po(conn, approval_id=2, decided_by='vp@example.com', notes='Too expensive')
    update_call = conn.execute.call_args_list[1]
    _, params = update_call[0]
    assert 'Too expensive' in params


# ---------------------------------------------------------------------------
# count_pending
# ---------------------------------------------------------------------------

def test_count_pending_returns_integer():
    conn = _conn(fetchone_result=(3,))
    assert count_pending(conn) == 3


def test_count_pending_zero_when_none():
    conn = _conn(fetchone_result=None)
    assert count_pending(conn) == 0


def test_count_pending_queries_pending_status():
    conn = _conn(fetchone_result=(0,))
    count_pending(conn)
    sql = conn.execute.call_args[0][0]
    assert 'pending' in sql.lower()


# ---------------------------------------------------------------------------
# get_po_approval
# ---------------------------------------------------------------------------

def test_get_po_approval_returns_dict():
    row = MagicMock()
    row.keys.return_value = ['id', 'po_id', 'status']
    row.__iter__ = lambda s: iter([1, 7, 'pending'])
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 1, 'po_id': 7, 'status': 'pending'}
    result = get_po_approval(conn, 7)
    assert result is not None
    assert result['status'] == 'pending'


def test_get_po_approval_returns_none_when_missing():
    conn = _conn(fetchone_result=None)
    assert get_po_approval(conn, 999) is None


# ---------------------------------------------------------------------------
# APPROVAL_ROLES
# ---------------------------------------------------------------------------

def test_president_can_approve():
    assert 'President' in APPROVAL_ROLES


def test_vp_can_approve():
    assert 'Vice President' in APPROVAL_ROLES


def test_auditor_cannot_approve():
    assert 'Auditor' not in APPROVAL_ROLES


def test_supervisor_cannot_approve():
    assert 'Supervisor' not in APPROVAL_ROLES
