"""Views: SSO (OpenID Connect) login.

Deliberately mirrors the session-key-setting block in views/__init__.py's
home() password-login path exactly, so dept_required/role_required continue
working unchanged regardless of which path a user logged in through.
"""

from django.shortcuts import redirect, render

from .. import sso_core
from ..accounts import _get_user_profile, _is_full_access
from ..log_utils import get_logger

log = get_logger(__name__)


def sso_login(request):
    if not sso_core.is_configured():
        return redirect('home')
    state = sso_core.new_state()
    nonce = sso_core.new_nonce()
    request.session['sso_state'] = state
    request.session['sso_nonce'] = nonce
    return redirect(sso_core.build_authorize_url(state, nonce))


def sso_callback(request):
    if not sso_core.is_configured():
        return redirect('home')

    idp_error = request.GET.get('error')
    if idp_error:
        log.warning("SSO callback returned an IdP error: %s", idp_error)
        return render(request, 'home.html', {
            'error': 'SSO login failed: the identity provider denied the request.',
        })

    expected_state = request.session.pop('sso_state', None)
    state = request.GET.get('state', '')
    if not expected_state or state != expected_state:
        log.warning("SSO callback state mismatch")
        return render(request, 'home.html', {
            'error': 'SSO login failed: your session expired — please try again.',
        })

    nonce = request.session.pop('sso_nonce', None)
    code = request.GET.get('code', '')
    try:
        tokens = sso_core.exchange_code_for_tokens(code)
        claims = sso_core.verify_id_token(tokens['id_token'], nonce)
    except Exception as exc:
        log.warning("SSO callback failed to verify identity: %s", exc)
        return render(request, 'home.html', {
            'error': 'SSO login failed: could not verify your identity.',
        })

    email = claims.get('email', '')
    profile = _get_user_profile(email) if email else {}
    if not profile:
        log.warning("SSO login denied: no account for %s", email)
        return render(request, 'home.html', {
            'error': f'No account found for {email}. Contact your administrator.',
        })

    request.session['user_email'] = email
    request.session['user_role'] = profile.get('role_name', '')
    request.session['user_dept_key'] = profile.get('dept_key') or ''
    request.session['user_dept_name'] = profile.get('dept_name', '')
    request.session['user_full_access'] = _is_full_access(profile)
    request.session['user_is_manager'] = profile.get('is_manager', False)
    log.info("SSO login succeeded for %s", email)

    if request.session['user_full_access']:
        return redirect('dashboard')
    dept_key = profile.get('dept_key')
    if dept_key:
        return redirect('dept_menu', dept=dept_key)
    return redirect('dashboard')
