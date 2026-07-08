"""Django management command — run due scheduled custom reports and email
them (CSV/PDF) to their configured recipients.

Usage:
    python manage.py run_scheduled_reports

Scheduled via Windows Task Scheduler or cron (real-time push is out of
scope — this batch command is the schedulable delivery mechanism, run
daily so any due daily/weekly/monthly report gets picked up):

    # cron (Linux): run once a day
    0 6 * * * cd /path/to/project && python manage.py run_scheduled_reports

    # Task Scheduler (Windows): action = python manage.py run_scheduled_reports
    # Trigger: daily at 06:00

For every saved_report with schedule_enabled=True that is due (per
report_builder_core._is_due, based on schedule_frequency and
last_run_at), runs the report and emails the CSV or PDF (per
schedule_format) to schedule_recipients (comma-separated) via
django.core.mail.EmailMessage — but only if EMAIL_HOST is configured; if
EMAIL_HOST is unset, no message is sent, and the delivery is printed as
a summary line instead (same EMAIL_HOST-gated fallback used by
send_daily_digest.py). last_run_at advances either way so the schedule
doesn't try to redeliver the same report on every run.
"""

from django.core.management.base import BaseCommand

from manufacturing.db_pg import get_db_connection
from manufacturing import report_builder_core
from manufacturing.reports_core import to_csv_bytes


class Command(BaseCommand):
    help = 'Run due scheduled custom reports and email/print their CSV or PDF output.'

    def handle(self, *args, **options):
        conn = get_db_connection()
        try:
            report_builder_core.ensure_report_builder_tables(conn)
            conn.commit()

            due = report_builder_core.list_due_scheduled_reports(conn)
            sent = printed = failed = 0
            for report in due:
                try:
                    result = report_builder_core.run_report(
                        conn, report['table_name'], report['definition'])
                    if report['schedule_format'] == 'pdf':
                        attachment = report_builder_core.report_to_pdf_bytes(
                            report['name'], result['output_fields'], result['rows'])
                        filename = f"{report['name']}.pdf"
                        mimetype = 'application/pdf'
                    else:
                        headers = [h for _f, h in result['output_fields']]
                        fields = [f for f, _h in result['output_fields']]
                        attachment = to_csv_bytes(
                            headers, [[row.get(f, '') for f in fields] for row in result['rows']])
                        filename = f"{report['name']}.csv"
                        mimetype = 'text/csv'

                    if self._send_email(report, attachment, filename, mimetype):
                        sent += 1
                    else:
                        printed += 1
                    report_builder_core.mark_report_run(conn, report['id'])
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    failed += 1
                    self.stderr.write(f"Report '{report['name']}' failed: {e}\n")
        finally:
            conn.close()

        self.stdout.write(
            f"Scheduled reports: {sent} emailed, {printed} printed "
            f"(no EMAIL_HOST), {failed} failed."
        )

    def _send_email(self, report: dict, attachment: bytes, filename: str, mimetype: str) -> bool:
        from django.conf import settings
        from django.core.mail import EmailMessage

        recipients = [r.strip() for r in (report['schedule_recipients'] or '').split(',') if r.strip()]
        host = getattr(settings, 'EMAIL_HOST', '')
        if not host or not recipients:
            self.stdout.write(
                f"Report '{report['name']}': no EMAIL_HOST/recipients configured — "
                f"generated {filename} ({len(attachment)} bytes), not sent.\n")
            return False
        try:
            email = EmailMessage(
                subject=f"Scheduled Report: {report['name']}",
                body=f"Attached is the scheduled report '{report['name']}'.",
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'erp@localhost'),
                to=recipients,
            )
            email.attach(filename, attachment, mimetype)
            email.send(fail_silently=False)
            return True
        except Exception as e:
            self.stderr.write(f"Email failed for report '{report['name']}': {e}\n")
            return False
