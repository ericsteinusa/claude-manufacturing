"""Tests for sso_core.py — Qt-free, no live network, no live database.

Crypto verification is tested for real (a real locally-generated RSA
keypair signs real JWTs, verified by real joserfc code) — only the HTTP
calls (discovery document / JWKS fetch / token exchange) are mocked, since
those are just network I/O, not the security-critical part.

sso_core.py reads django.conf.settings directly (OIDC_CLIENT_ID etc.), so —
same as tests/test_web_leaf_urls_coverage.py — DJANGO_SETTINGS_MODULE must
be set before import, but django.setup() is deliberately NOT called (that
would trigger manufacturing.apps.ManufacturingConfig.ready() -> init_schema(),
which opens a real Postgres connection this test suite must not depend on).
Plain attribute access on django.conf.settings needs only the env var.
"""
import os
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacture.settings')

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from django.conf import settings as django_settings  # noqa: E402
from joserfc import jwt as jose_jwt  # noqa: E402
from joserfc.jwk import RSAKey  # noqa: E402

from manufacturing import sso_core  # noqa: E402

ISSUER = 'https://mock-idp.local'
CLIENT_ID = 'test-client-id'


@pytest.fixture
def keypair():
    return RSAKey.generate_key(2048, private=True, auto_kid=True)


@pytest.fixture(autouse=True)
def _clear_discovery_cache():
    sso_core._DISCOVERY_CACHE.clear()
    yield
    sso_core._DISCOVERY_CACHE.clear()


def _make_id_token(key, *, nonce='test-nonce', aud=CLIENT_ID, iss=ISSUER,
                   email='eric@steinman.com', exp_delta=300, extra=None):
    now = int(time.time())
    claims = {
        'iss': iss, 'aud': aud, 'sub': 'user-1', 'email': email,
        'iat': now, 'exp': now + exp_delta, 'nonce': nonce,
    }
    if extra:
        claims.update(extra)
    header = {'alg': 'RS256', 'kid': key.kid}
    return jose_jwt.encode(header, claims, key)


def _discovery_doc():
    return {
        'issuer': ISSUER,
        'authorization_endpoint': f'{ISSUER}/authorize',
        'token_endpoint': f'{ISSUER}/token',
        'jwks_uri': f'{ISSUER}/jwks',
    }


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------

def test_is_configured_false_by_default(monkeypatch):
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_ID', '')
    monkeypatch.setattr(django_settings, 'OIDC_DISCOVERY_URL', '')
    assert sso_core.is_configured() is False


def test_is_configured_true_when_both_set(monkeypatch):
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(django_settings, 'OIDC_DISCOVERY_URL',
                        f'{ISSUER}/.well-known/openid-configuration')
    assert sso_core.is_configured() is True


def test_is_configured_false_when_only_client_id_set(monkeypatch):
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(django_settings, 'OIDC_DISCOVERY_URL', '')
    assert sso_core.is_configured() is False


# ---------------------------------------------------------------------------
# new_state / new_nonce
# ---------------------------------------------------------------------------

def test_new_state_is_url_safe_and_unique():
    a, b = sso_core.new_state(), sso_core.new_state()
    assert a != b
    assert len(a) > 16


def test_new_nonce_is_url_safe_and_unique():
    a, b = sso_core.new_nonce(), sso_core.new_nonce()
    assert a != b


# ---------------------------------------------------------------------------
# build_authorize_url
# ---------------------------------------------------------------------------

def test_build_authorize_url_includes_required_params(monkeypatch):
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(django_settings, 'OIDC_REDIRECT_URI', 'https://app.local/sso/callback/')
    with patch.object(sso_core, '_fetch_json', return_value=_discovery_doc()):
        url = sso_core.build_authorize_url('state123', 'nonce456')
    assert url.startswith(f'{ISSUER}/authorize?')
    assert 'client_id=test-client-id' in url
    assert 'state=state123' in url
    assert 'nonce=nonce456' in url
    assert 'response_type=code' in url


# ---------------------------------------------------------------------------
# get_discovery_document — caching
# ---------------------------------------------------------------------------

def test_get_discovery_document_caches_per_url(monkeypatch):
    monkeypatch.setattr(django_settings, 'OIDC_DISCOVERY_URL',
                        f'{ISSUER}/.well-known/openid-configuration')
    with patch.object(sso_core, '_fetch_json', return_value=_discovery_doc()) as mock_fetch:
        sso_core.get_discovery_document()
        sso_core.get_discovery_document()
    mock_fetch.assert_called_once()


# ---------------------------------------------------------------------------
# exchange_code_for_tokens
# ---------------------------------------------------------------------------

def test_exchange_code_for_tokens_posts_to_token_endpoint(monkeypatch):
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_SECRET', 'shh')
    monkeypatch.setattr(django_settings, 'OIDC_REDIRECT_URI', 'https://app.local/sso/callback/')

    class _FakeResp:
        def read(self):
            return b'{"id_token": "abc", "access_token": "def"}'
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    with patch.object(sso_core, '_fetch_json', return_value=_discovery_doc()), \
         patch.object(sso_core, 'urlopen', return_value=_FakeResp()) as mock_urlopen:
        result = sso_core.exchange_code_for_tokens('auth-code-123')

    assert result == {'id_token': 'abc', 'access_token': 'def'}
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == f'{ISSUER}/token'
    assert b'auth-code-123' in req.data


# ---------------------------------------------------------------------------
# verify_id_token — real crypto
# ---------------------------------------------------------------------------

def _patch_idp(monkeypatch, key):
    monkeypatch.setattr(django_settings, 'OIDC_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(sso_core, 'get_discovery_document', lambda *a, **kw: _discovery_doc())
    pub_jwks = {'keys': [key.as_dict(private=False)]}
    monkeypatch.setattr(sso_core, '_fetch_json', lambda url, timeout=5: pub_jwks)


def test_verify_id_token_accepts_valid_token(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    token = _make_id_token(keypair, nonce='n1')
    claims = sso_core.verify_id_token(token, 'n1')
    assert claims['email'] == 'eric@steinman.com'
    assert claims['iss'] == ISSUER


def test_verify_id_token_rejects_wrong_nonce(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    token = _make_id_token(keypair, nonce='n1')
    with pytest.raises(ValueError, match='nonce'):
        sso_core.verify_id_token(token, 'different-nonce')


def test_verify_id_token_rejects_wrong_audience(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    token = _make_id_token(keypair, nonce='n1', aud='someone-elses-client-id')
    with pytest.raises(ValueError, match='verification failed'):
        sso_core.verify_id_token(token, 'n1')


def test_verify_id_token_rejects_wrong_issuer(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    token = _make_id_token(keypair, nonce='n1', iss='https://evil-idp.local')
    with pytest.raises(ValueError, match='verification failed'):
        sso_core.verify_id_token(token, 'n1')


def test_verify_id_token_rejects_expired_token(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    token = _make_id_token(keypair, nonce='n1', exp_delta=-300)
    with pytest.raises(ValueError, match='verification failed'):
        sso_core.verify_id_token(token, 'n1')


def test_verify_id_token_rejects_token_signed_by_different_key(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    other_key = RSAKey.generate_key(2048, private=True, auto_kid=True)
    # Sign with a key whose public half is NOT in the (mocked) JWKS.
    token = _make_id_token(other_key, nonce='n1')
    with pytest.raises(ValueError, match='verification failed'):
        sso_core.verify_id_token(token, 'n1')


def test_verify_id_token_rejects_tampered_payload(monkeypatch, keypair):
    _patch_idp(monkeypatch, keypair)
    token = _make_id_token(keypair, nonce='n1')
    # Flip a character in the payload segment without re-signing.
    header_b64, payload_b64, sig_b64 = token.split('.')
    tampered_payload = payload_b64[:-1] + ('A' if payload_b64[-1] != 'A' else 'B')
    tampered = f'{header_b64}.{tampered_payload}.{sig_b64}'
    with pytest.raises(ValueError, match='verification failed'):
        sso_core.verify_id_token(tampered, 'n1')
