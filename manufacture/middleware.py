from manufacturing.audit_core import set_thread_user


class AuditUserMiddleware:
    """Store the logged-in user's email in a thread-local on every request.

    db_pg.PgConnection reads this when opening a connection and sets the
    PostgreSQL session variable ``app.current_user``, which the audit trigger
    function records as ``changed_by`` on every INSERT/UPDATE/DELETE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_thread_user(request.session.get('user_email', ''))
        try:
            return self.get_response(request)
        finally:
            set_thread_user('')
