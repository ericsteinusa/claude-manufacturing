"""Tests for api_decorators — shared response helpers and the @api_required
auth decorator for the mobile JSON API.

Needs Django settings bootstrapped (see conftest.py) because JsonResponse
touches settings.DEFAULT_CHARSET at construction time. No live DB: a fake
connection stands in for get_db_connection(), and verify_token/
ensure_api_token_table are patched at their api_decorators-module names
(where they were imported into), isolating this decorator's own glue logic
from api_auth's own (separately tested) token-verification logic.
"""
import json

from unittest.mock import patch

from django.test import RequestFactory

from manufacturing.api_decorators import api_ok, api_err, api_required


rf = RequestFactory()


class _FakeConn:
    def __init__(self):
        self.calls = []
        self.closed = False
        self.committed = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _patched(user, rate_limited=False):
    """Patch get_db_connection/ensure_api_token_table/verify_token as seen
    from inside api_decorators.py, returning the fake conn used and letting
    the caller control what verify_token resolves to. Rate-limit check/log
    functions are patched out too since _FakeConn doesn't implement a real
    fetchone()."""
    conn = _FakeConn()
    ctx = patch.multiple(
        'manufacturing.api_decorators',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        verify_token=lambda c, token: user,
        is_api_rate_limited=lambda c, i, e: rate_limited,
        record_api_request=lambda c, i, e: None,
    )
    return ctx, conn


# ── api_ok / api_err ─────────────────────────────────────────────────────

def test_api_ok_default_status_and_shape():
    resp = api_ok({'x': 1})
    assert resp.status_code == 200
    assert json.loads(resp.content) == {'ok': True, 'data': {'x': 1}}


def test_api_ok_custom_status():
    resp = api_ok({'created': True}, status=201)
    assert resp.status_code == 201
    assert json.loads(resp.content)['ok'] is True


def test_api_err_default_status_and_shape():
    resp = api_err('Bad input.')
    assert resp.status_code == 400
    assert json.loads(resp.content) == {'ok': False, 'error': 'Bad input.'}


def test_api_err_custom_status():
    resp = api_err('Not found.', status=404)
    assert resp.status_code == 404
    assert json.loads(resp.content)['error'] == 'Not found.'


# ── api_required ─────────────────────────────────────────────────────────

def test_api_required_missing_auth_header_returns_401():
    @api_required
    def view(request):
        return api_ok({'reached': True})

    request = rf.get('/api/v1/whatever/')
    resp = view(request)
    assert resp.status_code == 401
    assert json.loads(resp.content)['error'] == 'Authentication required.'


def test_api_required_non_bearer_auth_header_returns_401():
    @api_required
    def view(request):
        return api_ok({'reached': True})

    request = rf.get('/api/v1/whatever/', HTTP_AUTHORIZATION='Basic abc123')
    resp = view(request)
    assert resp.status_code == 401


def test_api_required_invalid_token_returns_401_and_does_not_call_view():
    called = []

    @api_required
    def view(request):
        called.append(True)
        return api_ok({'reached': True})

    ctx, conn = _patched(user=None)
    request = rf.get('/api/v1/whatever/', HTTP_AUTHORIZATION='Bearer badtoken')
    with ctx:
        resp = view(request)
    assert resp.status_code == 401
    assert json.loads(resp.content)['error'] == 'Invalid or expired token.'
    assert called == []
    assert conn.closed is True


def test_api_required_valid_token_injects_api_user_and_calls_view():
    user = {'id': 1, 'email': 'a@b.com', 'role': 'Manager'}
    seen_user = []

    @api_required
    def view(request):
        seen_user.append(request.api_user)
        return api_ok({'reached': True})

    ctx, conn = _patched(user=user)
    request = rf.get('/api/v1/whatever/', HTTP_AUTHORIZATION='Bearer goodtoken')
    with ctx:
        resp = view(request)
    assert resp.status_code == 200
    assert seen_user == [user]
    assert conn.closed is True


def test_api_required_strips_bearer_prefix_and_whitespace_from_token():
    seen_tokens = []

    @api_required
    def view(request):
        return api_ok({})

    conn = _FakeConn()
    with patch.multiple(
        'manufacturing.api_decorators',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        verify_token=lambda c, token: seen_tokens.append(token) or {'id': 1},
        is_api_rate_limited=lambda c, i, e: False,
        record_api_request=lambda c, i, e: None,
    ):
        request = rf.get('/api/v1/whatever/', HTTP_AUTHORIZATION='Bearer   abc123  ')
        view(request)
    assert seen_tokens == ['abc123']


def test_api_required_preserves_wrapped_function_name():
    @api_required
    def my_view(request):
        return api_ok({})

    assert my_view.__name__ == 'my_view'


# ── per-endpoint rate limiting ──────────────────────────────────────────

def test_api_required_rate_limited_returns_429_and_does_not_call_view():
    called = []

    @api_required
    def view(request):
        called.append(True)
        return api_ok({'reached': True})

    ctx, conn = _patched(user={'id': 1}, rate_limited=True)
    request = rf.get('/api/v1/whatever/', HTTP_AUTHORIZATION='Bearer goodtoken')
    with ctx:
        resp = view(request)
    assert resp.status_code == 429
    assert 'Rate limit exceeded' in json.loads(resp.content)['error']
    assert called == []
    assert conn.closed is True


def test_api_required_under_limit_calls_view_and_records_request():
    user = {'id': 1, 'email': 'a@b.com'}
    recorded = []

    @api_required
    def view(request):
        return api_ok({'reached': True})

    conn = _FakeConn()
    with patch.multiple(
        'manufacturing.api_decorators',
        get_db_connection=lambda: conn,
        ensure_api_token_table=lambda c: None,
        verify_token=lambda c, token: user,
        is_api_rate_limited=lambda c, i, e: False,
        record_api_request=lambda c, i, e: recorded.append((i, e)),
    ):
        request = rf.get('/api/v1/whatever/', HTTP_AUTHORIZATION='Bearer goodtoken')
        resp = view(request)
    assert resp.status_code == 200
    assert recorded == [('1', '/api/v1/whatever/')]
