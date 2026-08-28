"""Views: published API docs for the mobile REST API (COMPETITIVE_GAP_ANALYSIS.md §6.6).

Both views are deliberately unauthenticated — a third-party integrator or a
mobile developer needs to read the docs before they have a token, the same
reasoning _health.py already documents for the health-check endpoint.
"""

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from ..api_openapi_core import build_openapi_spec


@require_GET
def api_openapi_spec(request: HttpRequest) -> JsonResponse:
    base_url = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse(build_openapi_spec(base_url=base_url))


@require_GET
def api_docs(request: HttpRequest) -> HttpResponse:
    """Swagger UI, loaded from a CDN bundle — the same pattern every
    dashboard's Chart.js `<script src="https://cdn.jsdelivr.net/...">`
    already uses, rather than vendoring a JS framework into this app."""
    return HttpResponse(_SWAGGER_UI_HTML)


_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Manufacturing ERP API Docs</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body style="margin:0;">
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: '/api/v1/openapi.json',
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis],
      });
    };
  </script>
</body>
</html>
"""
