"""
saml_core.py — SAML 2.0 SSO client (SP-initiated: HTTP-Redirect binding
for the AuthnRequest, HTTP-POST binding for the assertion).

Opt-in via SAML_PROVIDERS in settings (see manufacture/settings.py) — same
pattern as sso_core.py's OIDC_PROVIDERS: unset by default, so local dev/CI
never attempt a SAML round-trip. Supports multiple IdPs at once, same as
sso_core.py.

XML signature verification (XMLDSig) has no reasonable stdlib or
hand-rollable equivalent — SAML's XML canonicalization / Signature
Wrapping (XSW) attack surface has caught even major vendor
implementations historically, so hand-rolling it would mean
reimplementing security-critical, attack-prone crypto instead of using an
audited library. This module uses python3-saml (OneLogin's SAML toolkit),
which wraps the system libxmlsec1 C library via the xmlsec bindings — the
same "audited library for the crypto" approach sso_core.py already takes
with joserfc for OIDC's RS256 verification.

Identity vs. authorization: same policy as sso_core.py — a SAML login
only proves *who* the user is (a verified NameID/email from a
signature-checked assertion). Provisioning/role-mapping reuses
accounts.provision_sso_user exactly like the OIDC path, not a
SAML-specific mechanism — there is deliberately only one place in this
app that decides what a first-time SSO login is allowed to become.
"""

import json

from django.conf import settings
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from .log_utils import get_logger

log = get_logger(__name__)


def get_providers() -> list[dict]:
    """Return configured SAML providers as a list of dicts with keys:
    key, label, idp_entity_id, idp_sso_url, idp_x509_cert, auto_provision,
    default_dept_key.

    SAML_PROVIDERS is a JSON list of {"key", "label", "idp_entity_id",
    "idp_sso_url", "idp_x509_cert", "auto_provision", "default_dept_key"}
    objects. No legacy single-provider fallback exists here (unlike
    sso_core.py's OIDC_CLIENT_ID/...) since SAML is a new capability, not
    a rename of an existing single-value setting.
    """
    raw = settings.SAML_PROVIDERS
    if not raw:
        return []
    try:
        configured = json.loads(raw)
    except (TypeError, ValueError):
        log.error("SAML_PROVIDERS is not valid JSON; SAML SSO disabled")
        return []

    providers = []
    for p in configured:
        if not p.get('key') or not p.get('idp_entity_id') or \
                not p.get('idp_sso_url') or not p.get('idp_x509_cert'):
            log.error(
                "Skipping SAML_PROVIDERS entry missing key/idp_entity_id/"
                "idp_sso_url/idp_x509_cert: %r", p.get('key'))
            continue
        auto_provision = bool(p.get('auto_provision'))
        default_dept_key = p.get('default_dept_key') or ''
        if auto_provision and not default_dept_key:
            log.error(
                "SAML_PROVIDERS entry %r has auto_provision=true but no "
                "default_dept_key; disabling auto-provision for it",
                p.get('key'))
            auto_provision = False
        providers.append({
            'key': p['key'],
            'label': p.get('label') or p['key'],
            'idp_entity_id': p['idp_entity_id'],
            'idp_sso_url': p['idp_sso_url'],
            'idp_x509_cert': p['idp_x509_cert'],
            'auto_provision': auto_provision,
            'default_dept_key': default_dept_key,
        })
    return providers


def get_provider(key: str) -> dict | None:
    """Return the configured SAML provider matching *key*, or None."""
    for p in get_providers():
        if p['key'] == key:
            return p
    return None


def is_configured() -> bool:
    return bool(get_providers())


def build_settings(provider: dict, sp_entity_id: str, acs_url: str) -> dict:
    """Build the python3-saml settings dict for *provider*.

    "strict": True enables the library's full validation (XML schema,
    timestamps, destinations) — the recommended production setting per
    python3-saml's own docs, not an optional hardening extra.
    wantAssertionsSigned is the property that actually forces signature
    verification against idp_x509_cert; without it the library would
    accept an unsigned assertion. The SP does not sign its own
    AuthnRequest (authnRequestsSigned: False) — this app has no
    standing SP certificate/key, matching the common baseline SAML
    integration (the IdP signs what matters: the assertion proving
    identity, which this app verifies).
    """
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": {
            "entityId": provider['idp_entity_id'],
            "singleSignOnService": {
                "url": provider['idp_sso_url'],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": provider['idp_x509_cert'],
        },
        "security": {
            "wantAssertionsSigned": True,
            "wantNameIdEncrypted": False,
            "wantMessagesSigned": False,
            "authnRequestsSigned": False,
            # This app's identity model is the NameID (email) alone —
            # attributes are only optionally used for name-mapping during
            # auto-provisioning, not required for login itself. Without
            # this, python3-saml rejects any assertion that omits an
            # AttributeStatement, which many IdPs don't send for a bare
            # identity assertion.
            "wantAttributeStatement": False,
        },
    }


def prepare_request_data(request) -> dict:
    """Build the request dict python3-saml expects, from a Django request."""
    return {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.META.get('HTTP_HOST', ''),
        'script_name': request.path,
        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }


def build_auth(request, provider: dict, sp_entity_id: str,
               acs_url: str) -> OneLogin_Saml2_Auth:
    req_data = prepare_request_data(request)
    saml_settings = build_settings(provider, sp_entity_id, acs_url)
    return OneLogin_Saml2_Auth(req_data, saml_settings)


# ---------------------------------------------------------------------------
# Assertion replay protection
#
# process_response(request_id=...) only checks InResponseTo when this SP's
# own session still has the original AuthnRequest ID on hand — a captured,
# still-signature-valid response can otherwise be POSTed again (from the
# same session after its single-use request_id is already consumed, or
# from a different session entirely) and pass every other check until its
# own NotOnOrAfter expires. python3-saml has no built-in replay cache (this
# is normal for a SAML toolkit — assertion-consumption tracking is the
# relying party's responsibility), so this app records each assertion ID
# the first time it's consumed, DB-backed to survive a process restart
# (consistent with this app's Postgres-native conventions elsewhere,
# rather than an in-process cache that wouldn't).
# ---------------------------------------------------------------------------

def ensure_saml_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saml_consumed_assertion (
            assertion_id TEXT PRIMARY KEY,
            consumed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def consume_assertion_once(conn, assertion_id: str) -> bool:
    """Record *assertion_id* as consumed. Returns True the first time (the
    login may proceed), False if it's already been consumed (replay —
    caller must deny the login). Commits on success only, matching this
    module's other single-purpose DB helpers."""
    if not assertion_id:
        return False
    ensure_saml_tables(conn)
    cur = conn.execute(
        "INSERT INTO saml_consumed_assertion (assertion_id) VALUES (%s) "
        "ON CONFLICT (assertion_id) DO NOTHING",
        (assertion_id,),
    )
    conn.commit()
    inserted = cur.rowcount if hasattr(cur, 'rowcount') else 0
    if not inserted:
        log.warning("Rejected replayed SAML assertion %s", assertion_id)
    return bool(inserted)
