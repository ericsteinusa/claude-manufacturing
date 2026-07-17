"""Views: in-app notification center (bell icon in base.html).

Session-gated JSON endpoints, not Bearer-token /api/v1/ endpoints — these
back the web UI's bell icon, not the mobile app, so they use the same
session-cookie auth as every other web view (CSRF-protected, unlike the
csrf_exempt mobile API).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ..db_pg import get_db_connection
from ..log_utils import get_logger
from ..accounts import _get_user_profile
from ..notify_core import (
    ensure_notification_table,
    list_notifications,
    get_unread_count,
    mark_read,
    mark_all_read,
)

log = get_logger(__name__)


def _current_people_id(request):
    email = request.session.get('user_email')
    if not email:
        return None
    return _get_user_profile(email).get('people_id')


@require_GET
def notifications_unread_count(request):
    people_id = _current_people_id(request)
    if not people_id:
        return JsonResponse({'count': 0})
    with get_db_connection() as conn:
        ensure_notification_table(conn)
        count = get_unread_count(conn, people_id)
    return JsonResponse({'count': count})


@require_GET
def notifications_list(request):
    people_id = _current_people_id(request)
    if not people_id:
        return JsonResponse({'notifications': []})
    with get_db_connection() as conn:
        ensure_notification_table(conn)
        notifications = list_notifications(conn, people_id, limit=20)
    return JsonResponse({'notifications': notifications})


@require_POST
def notifications_mark_read(request, notification_id):
    people_id = _current_people_id(request)
    if not people_id:
        return JsonResponse({'ok': False, 'error': 'not authenticated'}, status=401)
    with get_db_connection() as conn:
        ensure_notification_table(conn)
        ok = mark_read(conn, notification_id, people_id)
    return JsonResponse({'ok': ok})


@require_POST
def notifications_mark_all_read(request):
    people_id = _current_people_id(request)
    if not people_id:
        return JsonResponse({'ok': False, 'error': 'not authenticated'}, status=401)
    with get_db_connection() as conn:
        ensure_notification_table(conn)
        count = mark_all_read(conn, people_id)
    return JsonResponse({'ok': True, 'count': count})
