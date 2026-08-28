"""api_openapi_core.py — hand-built OpenAPI 3.0 spec for the mobile REST API.

Closes COMPETITIVE_GAP_ANALYSIS.md §6.6's "Published API docs" gap. This is
deliberately hand-curated rather than introspected from Django's URL
resolver: every api_views.py function already declares its own accepted
method(s) via @require_http_methods (or, for the handful with GET+POST
branching inside one view, both), so the ENDPOINTS list below was built by
reading every one of those decorators/branches directly rather than
guessing from naming convention. Keeping it as a plain Python list (not a
decorator-driven auto-generator, and not a new dependency like
drf-spectacular, which would also require adopting Django REST Framework
this app doesn't use) matches this codebase's existing minimal-dependency
convention and is honestly scoped: response bodies are documented as the
generic {"ok": ..., "data": ...}/{"ok": false, "error": ...} envelope every
endpoint actually returns (per api_decorators.api_ok/api_err), not a
fully-typed schema per endpoint, since building 48 endpoint-specific
response schemas would be a much larger undertaking than this gap's own
"comparatively cheap" scoping calls for.

Keep this list in sync with manufacturing/urls.py's `api/v1/` routes and
api_views.py's @require_http_methods decorators when either changes — the
same "has gone stale before" caution CLAUDE.md already gives for the
Mobile REST API section and the user-guide docs.
"""

API_VERSION = 'v1'

# (path relative to the /api/v1 server base, [methods], summary, auth_required)
# auth_required=False only for login, which is how a token is obtained.
ENDPOINTS: list[tuple[str, list[str], str, bool]] = [
    ('/auth/login/', ['post'], 'Log in with email/password, receive a bearer token.', False),
    ('/auth/refresh/', ['post'], "Extend the caller's current token expiry.", True),
    ('/auth/logout/', ['post'], "Revoke the caller's current token.", True),
    ('/auth/profile/', ['get'], "Get the caller's profile.", True),

    ('/dashboard/', ['get'], 'Main dashboard: PO/WO/inventory/CS summary KPIs.', True),
    ('/dashboards/financial/', ['get'], 'Financial dashboard KPIs.', True),
    ('/dashboards/production/', ['get'], 'Production dashboard KPIs.', True),
    ('/dashboards/inventory/', ['get'], 'Inventory dashboard KPIs.', True),
    ('/dashboards/sales/', ['get'], 'Sales dashboard KPIs and recent orders.', True),
    ('/dashboards/personnel/', ['get'], 'Personnel/HR dashboard KPIs and recent hires.', True),
    ('/dashboards/accounting/', ['get'], 'Accounting dashboard: AP/AR KPIs and recent GL journals.', True),

    ('/time-clock/status/', ['get'], "Whether the caller is currently clocked in.", True),
    ('/time-clock/clock-in/', ['post'], 'Clock in.', True),
    ('/time-clock/clock-out/', ['post'], 'Clock out of the current entry.', True),
    ('/time-clock/hours/', ['get'], "The caller's time-clock entries and totals for a period.", True),
    ('/time-off/', ['get', 'post'], "List (GET) or submit (POST) the caller's time-off requests.", True),

    ('/wo/', ['get'], 'List work orders, optionally filtered by status.', True),
    ('/wo/assignees/', ['get'], 'List people eligible to be assigned a work order.', True),
    ('/wo/{wo_id}/', ['get'], 'Work order detail with materials and allowed status transitions.', True),
    ('/wo/{wo_id}/status/', ['post'], "Change a work order's status.", True),
    ('/wo/{wo_id}/assign/', ['post'], 'Assign a work order to a person (Production Manager/Foreman only).', True),
    ('/wo/{wo_id}/operations/', ['get'], "A work order's routing operations and shop-floor progress.", True),
    ('/wo/{wo_id}/operations/{seq}/start/', ['post'], 'Start one routing operation.', True),
    ('/wo/{wo_id}/operations/{seq}/complete/', ['post'], 'Complete one routing operation.', True),
    ('/wo/{wo_id}/cost/', ['get'], "A work order's material/labor/overhead/variance cost summary.", True),
    ('/wo/{wo_id}/cost/compute/', ['post'], "Recompute a work order's actual cost.", True),

    ('/req/', ['get', 'post'], 'List (GET) or create (POST) purchase requisitions.', True),
    ('/req/pending/', ['get'], "Requisitions pending the caller's approval.", True),
    ('/req/{req_id}/items/', ['post'], 'Add a line item to a requisition.', True),
    ('/req/{req_id}/submit/', ['post'], 'Submit a requisition for approval.', True),
    ('/req/{req_id}/decide/', ['post'], 'Approve or deny a requisition.', True),

    ('/inventory/', ['get'], 'List inventory levels, optionally filtered/searched.', True),
    ('/inventory/receive/', ['post'], 'Receive inventory against a product.', True),

    ('/quality/ncr/', ['get', 'post'], 'List (GET) or create (POST) non-conformance reports.', True),
    ('/quality/ncr/{ncr_id}/', ['get'], 'NCR detail.', True),

    ('/maint/wo/', ['get'], 'List maintenance work orders, optionally filtered by status.', True),
    ('/maint/wo/{wo_id}/', ['get'], 'Maintenance work order detail.', True),
    ('/maint/wo/{wo_id}/complete/', ['post'], 'Complete a maintenance work order.', True),

    ('/approvals/pending/', ['get'], "Approval-workflow steps pending the caller's decision.", True),
    ('/approvals/steps/{step_id}/decide/', ['post'], 'Approve or reject one approval-workflow step.', True),

    ('/lots/', ['get', 'post'], 'List (GET) or create (POST) inventory lots.', True),
    ('/lots/expiry/', ['get'], 'Lots nearing or past their expiry date.', True),
    ('/lots/{lot_id}/', ['get'], 'Lot detail.', True),
    ('/lots/{lot_id}/status/', ['post'], "Change a lot's status.", True),

    ('/serials/', ['get', 'post'], 'List (GET) or create (POST) serial numbers.', True),
    ('/serials/{serial_id}/status/', ['post'], "Change a serial number's status.", True),

    ('/workcenters/', ['get'], 'List workcenters.', True),
    ('/routing/{product_id}/', ['get'], "A product's routing steps.", True),

    ('/costs/{product_id}/', ['get'], "A product's standard cost.", True),
    ('/costs/{product_id}/roll/', ['post'], "Recompute a product's standard cost roll.", True),
    ('/costs/{product_id}/history/', ['get'], "A product's standard cost roll history.", True),

    ('/gl-accounts/', ['get', 'post'], 'List (GET) or create (POST) GL accounts.', True),
]

_ENVELOPE_OK = {
    'type': 'object',
    'properties': {
        'ok': {'type': 'boolean', 'example': True},
        'data': {'type': 'object'},
    },
}
_ENVELOPE_ERR = {
    'type': 'object',
    'properties': {
        'ok': {'type': 'boolean', 'example': False},
        'error': {'type': 'string'},
    },
}


def build_openapi_spec(base_url: str = '') -> dict:
    """Return a full OpenAPI 3.0 document describing every /api/v1/
    endpoint. *base_url*, if given, is prefixed onto the server URL (e.g.
    the deployment's own scheme+host) so the spec is directly usable from
    Swagger UI/Postman without manual edits.
    """
    paths: dict = {}
    for path, methods, summary, auth_required in ENDPOINTS:
        operations = {}
        for method in methods:
            responses = {
                '200': {
                    'description': 'Success',
                    'content': {'application/json': {'schema': _ENVELOPE_OK}},
                },
                '400': {
                    'description': 'Bad request',
                    'content': {'application/json': {'schema': _ENVELOPE_ERR}},
                },
            }
            if auth_required:
                responses['401'] = {
                    'description': 'Missing, invalid, or expired bearer token',
                    'content': {'application/json': {'schema': _ENVELOPE_ERR}},
                }
                responses['429'] = {
                    'description': 'Per-endpoint rate limit exceeded',
                    'content': {'application/json': {'schema': _ENVELOPE_ERR}},
                }
            operations[method] = {
                'summary': summary,
                'tags': [path.strip('/').split('/')[0] or 'root'],
                'security': [] if not auth_required else [{'bearerAuth': []}],
                'parameters': [
                    {
                        'name': part.strip('{}'),
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    }
                    for part in path.split('/') if part.startswith('{')
                ],
                'responses': responses,
            }
        paths[path] = operations

    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'Manufacturing ERP Mobile API',
            'version': API_VERSION,
            'description': (
                'Stateless JSON API consumed by the React Native mobile app. '
                'All responses are {"ok": true, "data": ...} on success or '
                '{"ok": false, "error": ...} on failure. Authenticate via '
                'POST /auth/login/, then send the returned token as '
                '`Authorization: Bearer <token>` on every other request. '
                'Every authenticated endpoint is rate-limited per user per '
                'endpoint (429 once exceeded).'
            ),
        },
        'servers': [{'url': f'{base_url}/api/{API_VERSION}'}],
        'components': {
            'securitySchemes': {
                'bearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                },
            },
        },
        'security': [{'bearerAuth': []}],
        'paths': paths,
    }
