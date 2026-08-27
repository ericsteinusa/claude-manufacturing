"""
sso_core.py — OpenID Connect SSO client (Authorization Code flow).

Opt-in via OIDC_PROVIDERS (or the legacy single-provider OIDC_CLIENT_ID/
OIDC_DISCOVERY_URL vars) in settings (see manufacture/settings.py) — same
pattern as SENTRY_DSN: unset by default, so local dev/CI never attempt an
SSO round-trip. Works against any spec-compliant OIDC provider (Azure AD/
Entra ID, Google Workspace, Okta, or a local test IdP).

Supports multiple providers configured at once (get_providers()), each
identified by a short "key" slug used in the login/callback URLs. Every
function below takes the specific provider dict to act against — there is
no implicit "the configured provider" global anymore now that there can be
more than one.

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


def get_providers() -> list[dict]:
    """Return configured OIDC providers as a list of dicts with keys:
    key, label, client_id, client_secret, discovery_url.

    OIDC_PROVIDERS (a JSON list) takes precedence when set. Falls back to
    a single provider (key='default') assembled from the legacy
    OIDC_CLIENT_ID/OIDC_CLIENT_SECRET/OIDC_DISCOVERY_URL vars, so existing
    single-provider deployments keep working unchanged.
    """
    raw = settings.OIDC_PROVIDERS
    if raw:
        try:
            configured = json.loads(raw)
        except (TypeError, ValueError):
            log.error("OIDC_PROVIDERS is not valid JSON; SSO disabled")
            return []
        providers = []
        for p in configured:
            if not p.get('key') or not p.get('client_id') or not p.get('discovery_url'):
                log.error(
                    "Skipping OIDC_PROVIDERS entry missing key/client_id/"
                    "discovery_url: %r", p)
                continue
            providers.append({
                'key': p['key'],
                'label': p.get('label') or p['key'],
                'client_id': p['client_id'],
                'client_secret': p.get('client_secret', ''),
                'discovery_url': p['discovery_url'],
            })
        return providers

    if settings.OIDC_CLIENT_ID and settings.OIDC_DISCOVERY_URL:
        return [{
            'key': 'default',
            'label': 'SSO',
            'client_id': settings.OIDC_CLIENT_ID,
            'client_secret': settings.OIDC_CLIENT_SECRET,
            'discovery_url': settings.OIDC_DISCOVERY_URL,
        }]
    return []


def get_provider(key: str) -> dict | None:
    """Return the configured provider matching *key*, or None."""
    for p in get_providers():
        if p['key'] == key:
            return p
    return None


def is_configured() -> bool:
    return bool(get_providers())


def _fetch_json(url: str, timeout: int = 5) -> dict:
    req = Request(url, headers={'Accept': 'application/json'})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_discovery_document(provider: dict) -> dict:
    """Fetch (and cache in-process) the IdP's .well-known/openid-configuration."""
    url = provider['discovery_url']
    if url not in _DISCOVERY_CACHE:
        _DISCOVERY_CACHE[url] = _fetch_json(url)
    return _DISCOVERY_CACHE[url]


def get_jwks(provider: dict) -> KeySet:
    doc = get_discovery_document(provider)
    jwks_dict = _fetch_json(doc['jwks_uri'])
    return KeySet.import_key_set(jwks_dict)


def new_state() -> str:
    return secrets.token_urlsafe(24)


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def build_authorize_url(provider: dict, state: str, nonce: str, redirect_uri: str) -> str:
    doc = get_discovery_document(provider)
    params = {
        'response_type': 'code',
        'client_id': provider['client_id'],
        'redirect_uri': redirect_uri,
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
    }
    return f"{doc['authorization_endpoint']}?{urlencode(params)}"


def exchange_code_for_tokens(provider: dict, code: str, redirect_uri: str) -> dict:
    doc = get_discovery_document(provider)
    data = urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': provider['client_id'],
        'client_secret': provider['client_secret'],
    }).encode('utf-8')
    req = Request(doc['token_endpoint'], data=data, method='POST',
                  headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode('utf-8'))


def verify_id_token(provider: dict, id_token: str, nonce: str) -> dict:
    """Verify signature (RS256 via the IdP's published JWKS), issuer,
    audience, and expiry/not-before, then check *nonce* against the
    one-time value this app generated for the login attempt.

    Raises ValueError on any verification failure — callers must treat that
    as 'reject the login', never fall back to trusting unverified claims.
    """
    doc = get_discovery_document(provider)
    jwks = get_jwks(provider)
    registry = JWTClaimsRegistry(
        iss={'essential': True, 'value': doc['issuer']},
        aud={'essential': True, 'value': provider['client_id']},
    )
    try:
        token = jose_jwt.decode(id_token, jwks)
        registry.validate(token.claims)
    except JoseError as exc:
        raise ValueError(f"ID token verification failed: {exc}") from exc

    if token.claims.get('nonce') != nonce:
        raise ValueError("ID token nonce mismatch")
    return dict(token.claims)
