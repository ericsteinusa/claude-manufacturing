"""
sso_core.py — OpenID Connect SSO client (Authorization Code flow).

Opt-in via OIDC_CLIENT_ID / OIDC_DISCOVERY_URL in settings (see
manufacture/settings.py) — same pattern as SENTRY_DSN: unset by default, so
local dev/CI never attempt an SSO round-trip. Works against any
spec-compliant OIDC provider (Azure AD/Entra ID, Google Workspace, Okta, or
a local test IdP) — only the discovery URL and client credentials change,
not this module.

Identity vs. authorization: SSO here only proves *who* the user is (a
verified email from the IdP's signed ID token). It deliberately does NOT
attempt to map arbitrary IdP group/role claims onto this app's own
dept/role model — that mapping is customer-tenant-specific, and this app
already has an authoritative source for it: the existing
people/user_roles/dept tables, resolved via accounts._get_user_profile(email)
exactly like the existing password-login path. A person must already exist
in this app (by email) for SSO login to succeed; SSO doesn't provision new
accounts.

HTTP calls use stdlib urllib (no new dependency), matching this app's
existing convention (ecommerce_core.py, webhook_core.py). Only the JOSE/JWT
signature verification needs a real library — RSA signature verification
has no reasonable stdlib equivalent, and hand-rolling it would mean
reimplementing security-critical crypto instead of using an audited one —
so this module's one new dependency is joserfc (RFC 7515/7517/7519 JWS/JWK/
JWT), not a general-purpose OAuth2/OIDC framework.
"""

import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from joserfc import jwt as jose_jwt
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry
from joserfc.errors import JoseError

from .log_utils import get_logger

log = get_logger(__name__)

_DISCOVERY_CACHE: dict[str, dict] = {}


def is_configured() -> bool:
    return bool(settings.OIDC_CLIENT_ID and settings.OIDC_DISCOVERY_URL)


def _fetch_json(url: str, timeout: int = 5) -> dict:
    req = Request(url, headers={'Accept': 'application/json'})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_discovery_document(discovery_url: str | None = None) -> dict:
    """Fetch (and cache in-process) the IdP's .well-known/openid-configuration."""
    url = discovery_url or settings.OIDC_DISCOVERY_URL
    if url not in _DISCOVERY_CACHE:
        _DISCOVERY_CACHE[url] = _fetch_json(url)
    return _DISCOVERY_CACHE[url]


def get_jwks(discovery_url: str | None = None) -> KeySet:
    doc = get_discovery_document(discovery_url)
    jwks_dict = _fetch_json(doc['jwks_uri'])
    return KeySet.import_key_set(jwks_dict)


def new_state() -> str:
    return secrets.token_urlsafe(24)


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def build_authorize_url(state: str, nonce: str, redirect_uri: str | None = None) -> str:
    doc = get_discovery_document()
    params = {
        'response_type': 'code',
        'client_id': settings.OIDC_CLIENT_ID,
        'redirect_uri': redirect_uri or settings.OIDC_REDIRECT_URI,
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
    }
    return f"{doc['authorization_endpoint']}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str | None = None) -> dict:
    doc = get_discovery_document()
    data = urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri or settings.OIDC_REDIRECT_URI,
        'client_id': settings.OIDC_CLIENT_ID,
        'client_secret': settings.OIDC_CLIENT_SECRET,
    }).encode('utf-8')
    req = Request(doc['token_endpoint'], data=data, method='POST',
                  headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode('utf-8'))


def verify_id_token(id_token: str, nonce: str) -> dict:
    """Verify signature (RS256 via the IdP's published JWKS), issuer,
    audience, and expiry/not-before, then check *nonce* against the
    one-time value this app generated for the login attempt.

    Raises ValueError on any verification failure — callers must treat that
    as 'reject the login', never fall back to trusting unverified claims.
    """
    doc = get_discovery_document()
    jwks = get_jwks()
    registry = JWTClaimsRegistry(
        iss={'essential': True, 'value': doc['issuer']},
        aud={'essential': True, 'value': settings.OIDC_CLIENT_ID},
    )
    try:
        token = jose_jwt.decode(id_token, jwks)
        registry.validate(token.claims)
    except JoseError as exc:
        raise ValueError(f"ID token verification failed: {exc}") from exc

    if token.claims.get('nonce') != nonce:
        raise ValueError("ID token nonce mismatch")
    return dict(token.claims)
