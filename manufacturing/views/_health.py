"""Views: health-check endpoint for container/load-balancer liveness probes.

Deliberately unauthenticated — orchestrators and load balancers hit this
without a session, so it must not require login like every other view here.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ..db_pg import get_db_connection
from ..log_utils import get_logger

log = get_logger(__name__)


@require_GET
def healthz(request):
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        log.warning("Health check failed: %s", exc)
        return JsonResponse({'status': 'error', 'detail': str(exc)}, status=503)
    return JsonResponse({'status': 'ok'})
