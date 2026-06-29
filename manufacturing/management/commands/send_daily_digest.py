"""Django management command — send the daily ERP digest report.

Usage:
    python manage.py send_daily_digest [--email recipient@example.com]

Scheduled via Windows Task Scheduler or cron:
    # cron (Linux): run at 7 AM every weekday
    0 7 * * 1-5 cd /path/to/project && python manage.py send_daily_digest

    # Task Scheduler (Windows): action = python manage.py send_daily_digest
    # Trigger: daily at 07:00

The report body is built by reports_core.daily_digest_text(). If
EMAIL_HOST is configured in settings the report is emailed; otherwise
it is printed to stdout so it appears in scheduler logs.
"""

from django.core.management.base import BaseCommand

from manufacturing.db_pg import get_db_connection
from manufacturing import reports_core


class Command(BaseCommand):
    help = 'Print or email the daily ERP digest report.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email', dest='email', default='',
            help='Email address to send the digest to (requires EMAIL_HOST setting).',
        )

    def handle(self, *args, **options):
        conn = get_db_connection()
        try:
            digest = reports_core.daily_digest_text(conn)
        finally:
            conn.close()

        recipient = options.get('email', '').strip()
        if recipient:
            self._send_email(digest, recipient)
        else:
            self.stdout.write(digest)

    def _send_email(self, body: str, recipient: str) -> None:
        import datetime
        from django.conf import settings
        from django.core.mail import send_mail

        subject = (f"ERP Daily Digest — "
                   f"{datetime.date.today().strftime('%A, %B %-d, %Y')}")

        try:
            host = getattr(settings, 'EMAIL_HOST', '')
            if not host:
                self.stderr.write(
                    'EMAIL_HOST not configured — printing instead.\n')
                self.stdout.write(body)
                return
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL',
                                   'erp@localhost'),
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(
                self.style.SUCCESS(f'Digest emailed to {recipient}.'))
        except Exception as exc:
            self.stderr.write(f'Email failed: {exc}\n')
            self.stdout.write(body)
