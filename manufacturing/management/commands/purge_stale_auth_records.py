"""Django management command -- purge expired/stale auth housekeeping rows.

Usage:
    python manage.py purge_stale_auth_records

Scheduled via cron/Task Scheduler the same way send_daily_digest and
run_data_retention are:
    # cron (Linux): run once a day
    0 3 * * * cd /path/to/project && python manage.py purge_stale_auth_records

Deletes rows past their own natural retention window from three tables
that otherwise grow unbounded forever: api_auth.py's own
purge_old_attempts()/purge_old_api_requests() functions existed but were
never called from anywhere until this command, and accounts.py's
password_reset_token table (added alongside the forgot-password rewrite)
never had a purge function at all. Prints a one-line count per table plus
a final total, so it shows up in scheduler logs the same way the other
periodic commands do.
"""

from django.core.management.base import BaseCommand

from manufacturing.accounts import (
    ensure_password_reset_token_table,
    purge_expired_password_reset_tokens,
)
from manufacturing.api_auth import (
    ensure_api_token_table,
    purge_old_api_requests,
    purge_old_attempts,
)
from manufacturing.db_pg import get_db_connection


class Command(BaseCommand):
    help = ('Delete expired/stale rows from the login-attempt, '
            'API-request-log, and password-reset-token tables.')

    def handle(self, *args, **options):
        conn = get_db_connection()
        try:
            ensure_api_token_table(conn)
            ensure_password_reset_token_table(conn)
            conn.commit()

            login_attempts = purge_old_attempts(conn)
            api_requests = purge_old_api_requests(conn)
            reset_tokens = purge_expired_password_reset_tokens(conn)
            conn.commit()
        finally:
            conn.close()

        self.stdout.write(f'api_login_attempt: {login_attempts} row(s) purged')
        self.stdout.write(f'api_request_log: {api_requests} row(s) purged')
        self.stdout.write(f'password_reset_token: {reset_tokens} row(s) purged')
        total = login_attempts + api_requests + reset_tokens
        self.stdout.write(
            self.style.SUCCESS(  # pyright: ignore[reportAttributeAccessIssue]
                f'Auth cleanup complete: {total} row(s) purged total.'))
