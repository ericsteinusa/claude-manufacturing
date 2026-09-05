"""Views: health-check endpoint for container/load-balancer liveness probes.

Deliberately unauthenticated — orchestrators and load balancers hit this
without a session, so it must not require login like every other view here.

Also reports which commit the running process is serving. `status` stays a
pure LIVENESS signal (is the DB reachable) so existing probes that assert
`status == "ok"` keep working: a stale deploy is a real problem but the app
is still serving, and flipping this field would have a load balancer pull a
healthy node out of rotation. Deploy state lives in `version` instead, where
`code_stale` marks the pulled-but-not-restarted window that is otherwise
invisible from outside the box.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ..db_pg import get_db_connection
from ..log_utils import get_logger
from ..version_core import deploy_info

log = get_logger(__name__)


@require_GET
def healthz(request):
    # Version metadata is best-effort and must never be the reason this
    # endpoint fails; deploy_info() swallows its own errors and degrades to
    # nulls rather than raising.
    version = deploy_info()
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        log.warning("Health check failed: %s", exc)
        return JsonResponse(
            {'status': 'error', 'detail': str(exc), 'version': version},
            status=503,
        )
    return JsonResponse({'status': 'ok', 'version': version})
