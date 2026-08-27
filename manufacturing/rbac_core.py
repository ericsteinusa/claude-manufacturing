"""rbac_core.py — Qt-free row-level ownership scoping.

Closes the "row-level permission control" gap named in
COMPETITIVE_GAP_ANALYSIS.md §6.3: access control elsewhere in this app is
whole-view only (auth_decorators.dept_required/role_required — a person
either sees an entire view or none of it). Real per-record ownership
existed in exactly one place before this module, views/_ess.py, as a
one-off pattern hand-copied into every ESS view (compare a fetched
record's people_id to the caller's own, or filter a list query by it).
This generalizes that pattern into two reusable calls any view can adopt:
owned_scope() for list queries, owns_row() for detail views.

Privilege model: a manager or full-access role (President/VP) sees
everything an ownership-scoped view would otherwise restrict a regular
staff member to — matches the bypass auth_decorators.dept_required
already grants full-access roles, so this doesn't introduce a second,
inconsistent notion of "privileged." Employee Self-Service is a
deliberate exception: those views scope to the caller's own record
unconditionally, even for a full-access role, since ESS is "my own
record" by definition, not a management view — use the _strict variants
there instead of the privilege-bypassing ones.

Column names passed to owned_scope()/owned_scope_strict() are always a
hardcoded string literal from the calling view's own source, never user
input, so building the WHERE fragment with an f-string is the same trust
boundary this codebase's other dynamic-SQL helpers already rely on (e.g.
collection_activity's update_collection_activity()).
"""


def is_privileged(request) -> bool:
    """True if this session's role sees beyond its own records by
    default — full-access roles (President/VP) or a department
    manager/supervisor, the same two session flags
    auth_decorators.dept_required already treats as elevated."""
    return bool(
        request.session.get('user_full_access')
        or request.session.get('user_is_manager')
    )


def owned_scope(request, column: str, session_key: str = 'user_email') -> tuple[str, list]:
    """SQL WHERE fragment + params restricting *column* to the caller's
    own identity (request.session[session_key]) unless they're
    privileged. AND this into an existing query's WHERE clause.

    Returns ('TRUE', []) — no restriction — for a privileged caller.
    """
    if is_privileged(request):
        return 'TRUE', []
    return f'{column} = %s', [request.session.get(session_key, '')]


def owns_row(request, record: dict, column: str, session_key: str = 'user_email') -> bool:
    """True if *record* belongs to the caller, or they're privileged.

    Requires the record's value to be genuinely set (not just equal to an
    empty session value) — two blank strings must never count as a match.
    """
    if is_privileged(request):
        return True
    value = record.get(column)
    return bool(value) and value == request.session.get(session_key)


def owned_scope_strict(request, column: str, session_key: str) -> tuple[str, list]:
    """Like owned_scope(), but never bypassed by privilege — for
    self-service-only views (ESS) where even a full-access role should
    only ever see their own record, not everyone's."""
    return f'{column} = %s', [request.session.get(session_key)]


def owns_row_strict(request, record: dict, column: str, session_key: str) -> bool:
    """Like owns_row(), but never bypassed by privilege."""
    value = request.session.get(session_key)
    return value is not None and record.get(column) == value
