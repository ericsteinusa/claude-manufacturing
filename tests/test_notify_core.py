"""
Tests for notify_core.py — PO approval email notifications.
"""

from unittest.mock import MagicMock, patch


def _conn_rows(rows):
    """Return a mock connection whose fetchall yields *rows*."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = rows
    return conn


# ---------------------------------------------------------------------------
# get_approver_emails
# ---------------------------------------------------------------------------

def test_get_approver_emails_returns_list():
    from manufacturing.notify_core import get_approver_emails
    conn = _conn_rows([('vp@example.com',), ('president@example.com',)])
    emails = get_approver_emails(conn)
    assert emails == ['vp@example.com', 'president@example.com']


def test_get_approver_emails_empty():
    from manufacturing.notify_core import get_approver_emails
    conn = _conn_rows([])
    assert get_approver_emails(conn) == []


def test_get_approver_emails_queries_correct_roles():
    from manufacturing.notify_core import get_approver_emails
    conn = _conn_rows([])
    get_approver_emails(conn)
    sql = conn.execute.call_args[0][0]
    assert 'President' in sql
    assert 'Vice President' in sql


# ---------------------------------------------------------------------------
# notify_approval_requested
# ---------------------------------------------------------------------------

def test_notify_requested_sends_to_approvers():
    from manufacturing.notify_core import notify_approval_requested
    conn = _conn_rows([('vp@example.com',)])
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_requested(
            conn, 'PO-2026-0001', 1, 750.0, 'buyer@example.com',
            site_url='http://localhost:8000/'
        )
    mock_send.assert_called_once()
    recipients = mock_send.call_args[0][3]
    assert 'vp@example.com' in recipients


def test_notify_requested_subject_contains_po_number():
    from manufacturing.notify_core import notify_approval_requested
    conn = _conn_rows([('vp@example.com',)])
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_requested(
            conn, 'PO-2026-0099', 5, 1200.0, 'buyer@example.com'
        )
    subject = mock_send.call_args[0][0]
    assert 'PO-2026-0099' in subject


def test_notify_requested_subject_contains_total():
    from manufacturing.notify_core import notify_approval_requested
    conn = _conn_rows([('vp@example.com',)])
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_requested(
            conn, 'PO-2026-0001', 1, 750.0, 'buyer@example.com'
        )
    subject = mock_send.call_args[0][0]
    assert '750' in subject


def test_notify_requested_body_contains_requester():
    from manufacturing.notify_core import notify_approval_requested
    conn = _conn_rows([('vp@example.com',)])
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_requested(
            conn, 'PO-2026-0001', 1, 750.0, 'buyer@example.com',
            site_url='http://localhost:8000/'
        )
    body = mock_send.call_args[0][1]
    assert 'buyer@example.com' in body


def test_notify_requested_body_contains_queue_link():
    from manufacturing.notify_core import notify_approval_requested
    conn = _conn_rows([('vp@example.com',)])
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_requested(
            conn, 'PO-2026-0001', 1, 750.0, 'buyer@example.com',
            site_url='http://localhost:8000/'
        )
    body = mock_send.call_args[0][1]
    assert 'po/approvals/' in body


def test_notify_requested_skips_when_no_approvers(caplog):
    from manufacturing.notify_core import notify_approval_requested
    import logging
    conn = _conn_rows([])
    with patch('django.core.mail.send_mail') as mock_send:
        with caplog.at_level(logging.WARNING):
            notify_approval_requested(
                conn, 'PO-2026-0001', 1, 750.0, 'buyer@example.com'
            )
    mock_send.assert_not_called()


def test_notify_requested_swallows_send_error():
    from manufacturing.notify_core import notify_approval_requested
    conn = _conn_rows([('vp@example.com',)])
    with patch('django.core.mail.send_mail', side_effect=Exception("SMTP down")):
        # Must not raise
        notify_approval_requested(
            conn, 'PO-2026-0001', 1, 750.0, 'buyer@example.com'
        )


# ---------------------------------------------------------------------------
# notify_approval_decided
# ---------------------------------------------------------------------------

def test_notify_decided_approved_sends_to_requester():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_decided(
            requester_email='buyer@example.com',
            po_number='PO-2026-0001',
            total=750.0,
            approved=True,
            notes='',
            decided_by='vp@example.com',
        )
    recipients = mock_send.call_args[0][3]
    assert 'buyer@example.com' in recipients


def test_notify_decided_approved_subject():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_decided(
            'buyer@example.com', 'PO-2026-0001', 750.0,
            True, '', 'vp@example.com'
        )
    subject = mock_send.call_args[0][0]
    assert 'Approved' in subject or 'approved' in subject
    assert 'PO-2026-0001' in subject


def test_notify_decided_rejected_subject():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_decided(
            'buyer@example.com', 'PO-2026-0001', 750.0,
            False, 'Over budget', 'vp@example.com'
        )
    subject = mock_send.call_args[0][0]
    assert 'Rejected' in subject or 'rejected' in subject


def test_notify_decided_body_includes_notes():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_decided(
            'buyer@example.com', 'PO-2026-0001', 750.0,
            False, 'Over budget this quarter', 'vp@example.com'
        )
    body = mock_send.call_args[0][1]
    assert 'Over budget this quarter' in body


def test_notify_decided_body_omits_notes_when_empty():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_decided(
            'buyer@example.com', 'PO-2026-0001', 750.0,
            True, '', 'vp@example.com'
        )
    body = mock_send.call_args[0][1]
    assert 'Note:' not in body


def test_notify_decided_skips_when_no_requester_email():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail') as mock_send:
        notify_approval_decided('', 'PO-2026-0001', 750.0, True, '', 'vp@example.com')
    mock_send.assert_not_called()


def test_notify_decided_swallows_send_error():
    from manufacturing.notify_core import notify_approval_decided
    with patch('django.core.mail.send_mail', side_effect=OSError("no route")):
        # Must not raise
        notify_approval_decided(
            'buyer@example.com', 'PO-2026-0001', 750.0,
            True, '', 'vp@example.com'
        )


# ---------------------------------------------------------------------------
# get_approval_by_id (approval_core)
# ---------------------------------------------------------------------------

def test_get_approval_by_id_returns_dict():
    from manufacturing.approval_core import get_approval_by_id
    row = {'id': 5, 'po_id': 3, 'requested_by': 'buyer@example.com',
           'status': 'pending', 'po_number': 'PO-2026-0001', 'total': 750.0}
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = row
    result = get_approval_by_id(conn, 5)
    assert result == row


def test_get_approval_by_id_returns_none_when_missing():
    from manufacturing.approval_core import get_approval_by_id
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert get_approval_by_id(conn, 999) is None


def test_get_approval_by_id_uses_subquery_for_total():
    from manufacturing.approval_core import get_approval_by_id
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    get_approval_by_id(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'po_item' in sql
    assert 'SUM' in sql
