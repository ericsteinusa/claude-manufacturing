"""Django management command — apply data-retention policies.

Usage:
    python manage.py run_data_retention

Scheduled via cron/Task Scheduler the same way send_daily_digest is:
    # cron (Linux): run once a week
    0 6 * * 1 cd /path/to/project && python manage.py run_data_retention

Runs every active retention_policy (see manufacturing/data_governance_core.py)
and anonymizes any terminated employee whose termination_date is older than
that policy's cutoff. Prints a one-line summary per person anonymized, plus
a final count, so it shows up in scheduler logs the same way the daily
digest does.
"""

from django.core.management.base import BaseCommand

from manufacturing.db_pg import get_db_connection
from manufacturing.data_governance_core import apply_retention_policies


class Command(BaseCommand):
    help = 'Anonymize terminated employees who match an active retention policy.'

    def handle(self, *args, **options):
        conn = get_db_connection()
        try:
            anonymized = apply_retention_policies(conn)
        finally:
            conn.close()

        if anonymized:
            for person_id in anonymized:
                self.stdout.write(f'Anonymized person id {person_id}')
        self.stdout.write(
            self.style.SUCCESS(  # pyright: ignore[reportAttributeAccessIssue]
                f'Retention run complete: {len(anonymized)} person(s) anonymized.'))
