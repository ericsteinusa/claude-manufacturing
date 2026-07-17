"""Tests for webhook_core.py — Qt-free, no live network, no live database."""
import pytest
from unittest.mock import MagicMock, patch

from manufacturing.webhook_core import (
    EVENT_TYPES,
    ensure_webhook_tables,
    create_subscription,
    list_subscriptions,
    get_subscription,
    update_subscription,
    delete_subscription,
    list_deliveries,
    dispatch_event,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_event_types_contains_expected():
    assert 'po.received' in EVENT_TYPES
    assert 'wo.completed' in EVENT_TYPES
    assert 'so.confirmed' in EVENT_TYPES
    assert 'ncr.opened' in EVENT_TYPES


# ---------------------------------------------------------------------------
# ensure_webhook_tables
# ---------------------------------------------------------------------------

def test_ensure_webhook_tables_creates_both_tables():
    conn = MagicMock()
    ensure_webhook_tables(conn)
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS webhook_subscription' in s for s in sqls)
    assert any('CREATE TABLE IF NOT EXISTS webhook_delivery' in s for s in sqls)


def test_ensure_webhook_tables_creates_index():
    conn = MagicMock()
    ensure_webhook_tables(conn)
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE INDEX IF NOT EXISTS webhook_subscription_event' in s for s in sqls)


# ---------------------------------------------------------------------------
# create_subscription
# ---------------------------------------------------------------------------

def test_create_subscription_invalid_event_type():
    conn = MagicMock()
    with pytest.raises(ValueError, match="event_type"):
        create_subscription(conn, 'bad.event', 'https://example.com/hook')


def test_create_subscription_empty_target_url():
    conn = MagicMock()
    with pytest.raises(ValueError, match="target_url"):
        create_subscription(conn, 'po.received', '   ')


def test_create_subscription_returns_id():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 9}
    result = create_subscription(conn, 'po.received', 'https://example.com/hook')
    assert result == 9


def test_create_subscription_passes_correct_params():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 1}
    create_subscription(conn, 'wo.completed', 'https://example.com/hook',
                        secret='shh', created_by='eric@example.com')
    params = conn.execute.call_args[0][1]
    assert 'wo.completed' in params
    assert 'https://example.com/hook' in params
    assert 'shh' in params
    assert 'eric@example.com' in params


# ---------------------------------------------------------------------------
# list_subscriptions
# ---------------------------------------------------------------------------

def test_list_subscriptions_active_only_adds_where():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    list_subscriptions(conn, active_only=True)
    sql = conn.execute.call_args[0][0]
    assert 'is_active = TRUE' in sql


def test_list_subscriptions_event_type_filter():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    list_subscriptions(conn, event_type='ncr.opened')
    sql, params = conn.execute.call_args[0]
    assert 'event_type = %s' in sql
    assert 'ncr.opened' in params


def test_list_subscriptions_returns_dicts():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'event_type': 'po.received', 'target_url': 'https://x/', 'secret': '',
         'is_active': True, 'created_by': '', 'created_at': '2026-01-01'},
    ]
    result = list_subscriptions(conn)
    assert result[0]['id'] == 1


# ---------------------------------------------------------------------------
# get_subscription
# ---------------------------------------------------------------------------

def test_get_subscription_returns_dict():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 3, 'event_type': 'so.shipped'}
    result = get_subscription(conn, 3)
    assert result['id'] == 3


def test_get_subscription_returns_none_when_missing():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert get_subscription(conn, 999) is None


# ---------------------------------------------------------------------------
# update_subscription
# ---------------------------------------------------------------------------

def test_update_subscription_ignores_unknown_fields():
    conn = MagicMock()
    update_subscription(conn, 1, bogus_field='x')
    conn.execute.assert_not_called()


def test_update_subscription_invalid_event_type():
    conn = MagicMock()
    with pytest.raises(ValueError, match="event_type"):
        update_subscription(conn, 1, event_type='bad.event')


def test_update_subscription_builds_set_clause():
    conn = MagicMock()
    update_subscription(conn, 7, target_url='https://new/', is_active=False)
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE webhook_subscription SET' in sql
    assert 7 in params


# ---------------------------------------------------------------------------
# delete_subscription
# ---------------------------------------------------------------------------

def test_delete_subscription_issues_delete():
    conn = MagicMock()
    delete_subscription(conn, 3)
    sql, params = conn.execute.call_args[0]
    assert 'DELETE FROM webhook_subscription' in sql
    assert params == (3,)


# ---------------------------------------------------------------------------
# list_deliveries
# ---------------------------------------------------------------------------

def test_list_deliveries_returns_dicts():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'subscription_id': 1, 'event_type': 'po.received', 'entity_type': 'purchase_order',
         'entity_id': 5, 'payload': '{}', 'status': 'success', 'detail': 'HTTP 200',
         'created_at': '2026-01-01'},
    ]
    result = list_deliveries(conn)
    assert result[0]['status'] == 'success'


def test_list_deliveries_filters_by_subscription():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    list_deliveries(conn, subscription_id=4)
    sql, params = conn.execute.call_args[0]
    assert 'subscription_id = %s' in sql
    assert 4 in params


# ---------------------------------------------------------------------------
# dispatch_event
# ---------------------------------------------------------------------------

def test_dispatch_event_no_subscriptions_returns_zero():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    result = dispatch_event(conn, 'po.received', 'purchase_order', 5)
    assert result == 0


def test_dispatch_event_posts_to_active_subscription():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'target_url': 'https://example.com/hook', 'secret': ''},
    ]
    with patch('manufacturing.webhook_core._post_webhook', return_value=(True, 'HTTP 200')) as mock_post:
        result = dispatch_event(conn, 'po.received', 'purchase_order', 5)
    assert result == 1
    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == 'https://example.com/hook'


def test_dispatch_event_writes_delivery_log():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'target_url': 'https://example.com/hook', 'secret': ''},
    ]
    with patch('manufacturing.webhook_core._post_webhook', return_value=(True, 'HTTP 200')):
        dispatch_event(conn, 'po.received', 'purchase_order', 5)
    insert_calls = [c for c in conn.execute.call_args_list
                    if 'INSERT INTO webhook_delivery' in c[0][0]]
    assert len(insert_calls) == 1
    params = insert_calls[0][0][1]
    assert 'po.received' in params
    assert 'purchase_order' in params
    assert 5 in params
    assert 'success' in params


def test_dispatch_event_logs_failed_status_on_delivery_failure():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'target_url': 'https://example.com/hook', 'secret': ''},
    ]
    with patch('manufacturing.webhook_core._post_webhook',
               return_value=(False, 'Connection refused')):
        dispatch_event(conn, 'wo.completed', 'work_order', 9)
    insert_calls = [c for c in conn.execute.call_args_list
                    if 'INSERT INTO webhook_delivery' in c[0][0]]
    params = insert_calls[0][0][1]
    assert 'failed' in params
    assert 'Connection refused' in params


def test_dispatch_event_never_raises_on_subscription_lookup_error():
    conn = MagicMock()
    conn.execute.side_effect = Exception("db down")
    result = dispatch_event(conn, 'po.received', 'purchase_order', 5)
    assert result == 0


def test_dispatch_event_never_raises_when_one_delivery_fails_unexpectedly():
    conn = MagicMock()

    def side_effect(sql, params=None):
        m = MagicMock()
        if 'SELECT id, target_url, secret' in sql:
            m.fetchall.return_value = [
                {'id': 1, 'target_url': 'https://example.com/hook', 'secret': ''},
                {'id': 2, 'target_url': 'https://example.com/hook2', 'secret': ''},
            ]
        return m
    conn.execute.side_effect = side_effect

    call_count = {'n': 0}

    def flaky_post(url, body, secret, timeout=5):
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise RuntimeError("unexpected boom")
        return True, 'HTTP 200'

    with patch('manufacturing.webhook_core._post_webhook', side_effect=flaky_post):
        result = dispatch_event(conn, 'po.received', 'purchase_order', 5)
    # First subscriber's unexpected error is swallowed; second still gets dispatched.
    assert result == 1


def test_dispatch_event_includes_extra_fields_in_payload():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {'id': 1, 'target_url': 'https://example.com/hook', 'secret': ''},
    ]
    captured = {}

    def capture_post(url, body, secret, timeout=5):
        import json
        captured['payload'] = json.loads(body)
        return True, 'HTTP 200'

    with patch('manufacturing.webhook_core._post_webhook', side_effect=capture_post):
        dispatch_event(conn, 'so.confirmed', 'sales_order', 12, extra={'so_number': 'SO-2026-0001'})
    assert captured['payload']['so_number'] == 'SO-2026-0001'
    assert captured['payload']['event_type'] == 'so.confirmed'
    assert captured['payload']['entity_id'] == 12


# ---------------------------------------------------------------------------
# _sign_payload / _post_webhook
# ---------------------------------------------------------------------------

def test_sign_payload_matches_ecommerce_verification_scheme():
    from manufacturing.webhook_core import _sign_payload
    from manufacturing.ecommerce_core import verify_webhook_signature
    body = b'{"hello":"world"}'
    secret = 'topsecret'
    sig = _sign_payload(secret, body)
    assert verify_webhook_signature(secret, body, sig)


def test_post_webhook_swallows_network_errors():
    from manufacturing.webhook_core import _post_webhook
    with patch('manufacturing.webhook_core.urlopen', side_effect=OSError("unreachable")):
        ok, detail = _post_webhook('https://example.invalid/', b'{}', '')
    assert ok is False
    assert 'unreachable' in detail
