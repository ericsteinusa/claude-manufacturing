"""Shared helpers for the mobile JSON API.

Exports:
  api_ok(data, status=200)  → JsonResponse {"ok": true, "data": ...}
  api_err(msg, status=400)  → JsonResponse {"ok": false, "error": ...}
  @api_required              → decorator; injects request.api_user, enforces
                                per-endpoint rate limiting
"""
from functools import wraps

from django.http import JsonResponse

from .api_auth import (
    ensure_api_token_table, verify_token,
    record_api_request, is_api_rate_limited,
    API_RATE_LIMIT_MAX_REQUESTS, API_RATE_LIMIT_WINDOW_SECONDS,
)
from .db_pg import get_db_connection


def api_ok(data, status: int = 200) -> JsonResponse:
    return JsonResponse({"ok": True, "data": data}, status=status)


def api_err(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def api_required(view_func):
    """Verify Bearer token, enforce per-endpoint rate limiting, and inject
    request.api_user before calling the view.

    Rate limiting is keyed on (people_id, endpoint path) rather than just
    the token, so it survives a token refresh/re-login — a user who's
    hammering one endpoint stays throttled even after getting a fresh
    token. Every endpoint decorated with @api_required gets this for free;
    there is no opt-out per view, matching how the login-attempt lockout
    already applies unconditionally to every login attempt.
    """
    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return api_err('Authentication required.', 401)
        token = auth[7:].strip()
        conn = get_db_connection()
        try:
            ensure_api_token_table(conn)
            user = verify_token(conn, token)
            if user is None:
                return api_err('Invalid or expired token.', 401)

            endpoint = request.path
            identifier = str(user['id'])
            if is_api_rate_limited(conn, identifier, endpoint):
                return api_err(
                    f'Rate limit exceeded: max {API_RATE_LIMIT_MAX_REQUESTS} '
                    f'requests per {API_RATE_LIMIT_WINDOW_SECONDS}s for this '
                    f'endpoint.', 429)
            record_api_request(conn, identifier, endpoint)
            conn.commit()
        finally:
            conn.close()
        request.api_user = user
        return view_func(request, *args, **kwargs)
    return _wrapper
