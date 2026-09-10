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
# notify_password_reset
#
# The email this backs is the only thing that proves the requester actually
# controls the account's address -- see accounts.py's password_reset_token
# functions for the account-takeover bug this closed.
# ---------------------------------------------------------------------------

def test_notify_password_reset_sends_to_account_email():
    from manufacturing.notify_core import notify_password_reset
    with patch('django.core.mail.send_mail') as mock_send:
        notify_password_reset(
            'jane@example.com', 'http://localhost:8000/forgot-password/reset/?token=abc',
            30,
        )
    mock_send.assert_called_once()
    recipients = mock_send.call_args[0][3]
    assert recipients == ['jane@example.com']


def test_notify_password_reset_body_contains_link_and_lifetime():
    from manufacturing.notify_core import notify_password_reset
    with patch('django.core.mail.send_mail') as mock_send:
        notify_password_reset(
            'jane@example.com',
            'http://localhost:8000/forgot-password/reset/?token=abc',
            30,
        )
    body = mock_send.call_args[0][1]
    assert 'http://localhost:8000/forgot-password/reset/?token=abc' in body
    assert '30 minutes' in body


def test_notify_password_reset_swallows_send_error():
    from manufacturing.notify_core import notify_password_reset
    with patch('django.core.mail.send_mail', side_effect=OSError("no route")):
        # Must not raise
        notify_password_reset('jane@example.com', 'http://x/?token=abc', 30)


# ---------------------------------------------------------------------------
# ensure_notification_table
# ---------------------------------------------------------------------------

def test_ensure_notification_table_creates_table_and_index():
    from manufacturing.notify_core import ensure_notification_table
    conn = MagicMock()
    ensure_notification_table(conn)
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS notification' in s for s in sqls)
    assert any('CREATE INDEX IF NOT EXISTS notification_people_unread' in s for s in sqls)


# ---------------------------------------------------------------------------
# create_notification
# ---------------------------------------------------------------------------

def test_create_notification_returns_id():
    from manufacturing.notify_core import create_notification
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 42}
    result = create_notification(conn, 5, 'ncr_assigned', 'NCR #9 assigned to you')
    assert result == 42


def test_create_notification_passes_correct_params():
    from manufacturing.notify_core import create_notification
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 1}
    create_notification(conn, 5, 'low_stock', 'msg', entity_type='product', entity_id=9)
    params = conn.execute.call_args[0][1]
    assert 5 in params and 'low_stock' in params and 'product' in params and 9 in params


# ---------------------------------------------------------------------------
# create_notifications_for_role
# ---------------------------------------------------------------------------

def test_create_notifications_for_role_queries_role_name():
    from manufacturing.notify_core import create_notifications_for_role
    conn = MagicMock()
    create_notifications_for_role(conn, 'Vice President', 'approval_pending', 'msg')
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO notification' in sql
    assert 'r.role_name = %s' in sql
    assert 'Vice President' in params


# ---------------------------------------------------------------------------
# create_notifications_for_dept
# ---------------------------------------------------------------------------

def test_create_notifications_for_dept_queries_dept_name():
    from manufacturing.notify_core import create_notifications_for_dept
    conn = MagicMock()
    create_notifications_for_dept(conn, 'Purchasing', 'low_stock', 'msg')
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO notification' in sql
    assert 'd.dept_name = %s' in sql
    assert 'Purchasing' in params


# ---------------------------------------------------------------------------
# list_notifications
# ---------------------------------------------------------------------------

def test_list_notifications_returns_dicts():
    from manufacturing.notify_core import list_notifications
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'type': 'low_stock', 'entity_type': 'product', 'entity_id': 9,
         'message': 'msg', 'read_at': None, 'created_at': '2026-01-01'},
    ]
    result = list_notifications(conn, 5)
    assert result[0]['id'] == 1


def test_list_notifications_unread_only_adds_filter():
    from manufacturing.notify_core import list_notifications
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    list_notifications(conn, 5, unread_only=True)
    sql = conn.execute.call_args[0][0]
    assert 'read_at IS NULL' in sql


def test_list_notifications_passes_limit():
    from manufacturing.notify_core import list_notifications
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    list_notifications(conn, 5, limit=10)
    params = conn.execute.call_args[0][1]
    assert 10 in params


# ---------------------------------------------------------------------------
# get_unread_count
# ---------------------------------------------------------------------------

def test_get_unread_count_returns_count():
    from manufacturing.notify_core import get_unread_count
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'cnt': 3}
    assert get_unread_count(conn, 5) == 3


def test_get_unread_count_zero_when_no_row():
    from manufacturing.notify_core import get_unread_count
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert get_unread_count(conn, 5) == 0


# ---------------------------------------------------------------------------
# mark_read
# ---------------------------------------------------------------------------

def test_mark_read_returns_true_when_updated():
    from manufacturing.notify_core import mark_read
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 7}
    assert mark_read(conn, 7, 5) is True


def test_mark_read_returns_false_when_not_owned_or_missing():
    from manufacturing.notify_core import mark_read
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert mark_read(conn, 7, 5) is False


def test_mark_read_scopes_to_people_id():
    from manufacturing.notify_core import mark_read
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    mark_read(conn, 7, 5)
    sql, params = conn.execute.call_args[0]
    assert 'people_id = %s' in sql
    assert 7 in params and 5 in params


# ---------------------------------------------------------------------------
# mark_all_read
# ---------------------------------------------------------------------------

def test_mark_all_read_returns_count():
    from manufacturing.notify_core import mark_all_read
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [{'id': 1}, {'id': 2}]
    assert mark_all_read(conn, 5) == 2


def test_mark_all_read_zero_when_none_unread():
    from manufacturing.notify_core import mark_all_read
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    assert mark_all_read(conn, 5) == 0


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
