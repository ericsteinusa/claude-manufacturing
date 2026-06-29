"""Shared helpers for the mobile JSON API.

Exports:
  api_ok(data, status=200)  → JsonResponse {"ok": true, "data": ...}
  api_err(msg, status=400)  → JsonResponse {"ok": false, "error": ...}
  @api_required              → decorator; injects request.api_user
"""
from functools import wraps

from django.http import JsonResponse

from .api_auth import ensure_api_token_table, verify_token
from .db_pg import get_db_connection


def api_ok(data, status: int = 200) -> JsonResponse:
    return JsonResponse({"ok": True, "data": data}, status=status)


def api_err(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


def api_required(view_func):
    """Verify Bearer token and inject request.api_user before calling the view."""
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
        finally:
            conn.close()
        if user is None:
            return api_err('Invalid or expired token.', 401)
        request.api_user = user
        return view_func(request, *args, **kwargs)
    return _wrapper
