"""Views: SSO (SAML 2.0) login.

Mirrors views/_sso.py's structure (and reuses accounts.apply_sso_session,
the same session-key-setting helper) so dept_required/role_required
continue working unchanged regardless of which login path — password,
OIDC, or SAML — a user came through.
"""

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .. import saml_core
from ..accounts import (
    _get_user_profile, apply_sso_session, provision_sso_user, totp_enrolled,
)
from ..db_pg import get_db_connection
from ..log_utils import get_logger

log = get_logger(__name__)


def _sp_entity_id(request, provider_key):
    """The SP's own entity ID — its login URL doubles as a stable,
    per-provider identifier an IdP admin can use when configuring trust."""
    return request.build_absolute_uri(reverse('saml_login', args=[provider_key]))


def _acs_url(request, provider_key):
    return request.build_absolute_uri(reverse('saml_acs', args=[provider_key]))


def saml_login(request, provider_key):
    provider = saml_core.get_provider(provider_key)
    if not provider:
        return redirect('home')
    auth = saml_core.build_auth(
        request, provider,
        _sp_entity_id(request, provider_key), _acs_url(request, provider_key))
    redirect_url = auth.login()
    # Tracked so saml_acs can verify InResponseTo on the way back — the
    # SAML equivalent of sso_core's OIDC state/nonce replay protection.
    request.session['saml_request_id'] = auth.get_last_request_id()
    return redirect(redirect_url)


@csrf_exempt
def saml_acs(request, provider_key):
    """Assertion Consumer Service — the IdP POSTs the signed SAMLResponse
    here directly (an external third party with no access to our CSRF
    cookie/token, same reason api_views.py's endpoints are csrf_exempt).
    Forgery is prevented by the XML signature check inside
    process_response(), not Django's CSRF token."""
    provider = saml_core.get_provider(provider_key)
    if not provider:
        return redirect('home')

    request_id = request.session.pop('saml_request_id', None)
    auth = saml_core.build_auth(
        request, provider,
        _sp_entity_id(request, provider_key), _acs_url(request, provider_key))
    auth.process_response(request_id=request_id)

    errors = auth.get_errors()
    if errors:
        log.warning(
            "SAML callback failed for provider %s: %s (%s)",
            provider_key, errors, auth.get_last_error_reason())
        return render(request, 'home.html', {
            'error': 'SSO login failed: could not verify your identity.',
        })
    if not auth.is_authenticated():
        log.warning("SAML callback denied for provider %s: not authenticated", provider_key)
        return render(request, 'home.html', {
            'error': 'SSO login failed: the identity provider denied the request.',
        })

    with get_db_connection() as conn:
        assertion_is_fresh = saml_core.consume_assertion_once(
            conn, auth.get_last_assertion_id())
    if not assertion_is_fresh:
        return render(request, 'home.html', {
            'error': 'SSO login failed: this sign-in link has already been used.',
        })

    email = auth.get_nameid()
    profile = _get_user_profile(email) if email else {}
    if not profile and email and provider.get('auto_provision'):
        attrs = auth.get_attributes() or {}
        claims = {
            'given_name': _first_attr(attrs, 'given_name', 'firstName', 'FirstName'),
            'family_name': _first_attr(attrs, 'family_name', 'lastName', 'LastName'),
        }
        if provision_sso_user(email, claims, provider['default_dept_key']):
            profile = _get_user_profile(email)

    if not profile:
        log.warning("SAML login denied: no account for %s", email)
        return render(request, 'home.html', {
            'error': f'No account found for {email}. Contact your administrator.',
        })

    people_id = profile.get('people_id')
    if totp_enrolled(people_id):
        # Defer into the exact same MFA challenge the password-login path
        # uses (views/__init__.py's home()) rather than completing the
        # session here -- otherwise SAML would let an enrolled user skip
        # 2FA entirely just by using this login path instead.
        request.session['mfa_pending_email'] = email
        request.session['mfa_pending_people_id'] = people_id
        return redirect('home')

    apply_sso_session(request, email, profile)
    log.info("SAML login succeeded for %s via provider %s", email, provider_key)

    if request.session['user_full_access']:
        return redirect('dashboard')
    dept_key = profile.get('dept_key')
    if dept_key:
        return redirect('dept_menu', dept=dept_key)
    return redirect('dashboard')


def _first_attr(attrs: dict, *names: str) -> str:
    """SAML attribute names vary by IdP (given_name vs firstName vs a full
    URN) — try each known alias and return the first value found."""
    for name in names:
        values = attrs.get(name)
        if values:
            return values[0]
    return ''


def saml_metadata(request, provider_key):
    """SP metadata XML — what an IdP admin imports to configure the trust
    relationship for this specific provider key."""
    provider = saml_core.get_provider(provider_key)
    if not provider:
        return redirect('home')
    auth = saml_core.build_auth(
        request, provider,
        _sp_entity_id(request, provider_key), _acs_url(request, provider_key))
    settings_obj = auth.get_settings()
    metadata = settings_obj.get_sp_metadata()
    errors = settings_obj.validate_metadata(metadata)
    if errors:
        log.error("Invalid SP metadata for provider %s: %s", provider_key, errors)
        return HttpResponse('Invalid SP metadata configuration', status=500)
    return HttpResponse(metadata, content_type='text/xml')
