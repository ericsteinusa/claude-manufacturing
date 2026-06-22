"""
notify_core.py — email notifications for the PO approval workflow.

Uses Django's send_mail so email backend/host/credentials are configured
in settings.py (or via env vars).  All sends are fire-and-forget: a
failed send is logged but never raises, so email issues never break the
approval workflow.
"""

from .log_utils import get_logger

log = get_logger(__name__)


def get_approver_emails(conn) -> list[str]:
    """Return email addresses for all President / VP users."""
    rows = conn.execute(
        "SELECT DISTINCT p.email "
        "FROM people p "
        "JOIN user_roles ur ON ur.people_id = p.id "
        "JOIN roles r ON r.id = ur.role_id "
        "WHERE r.role_name IN ('President', 'Vice President') "
        "AND p.email IS NOT NULL AND p.email != '' "
        "ORDER BY p.email",
    ).fetchall()
    return [r[0] for r in rows]


def notify_approval_requested(
    conn,
    po_number: str,
    po_id: int,
    total: float,
    requested_by: str,
    site_url: str = '',
) -> None:
    """Email all approvers that a PO is waiting for sign-off."""
    recipients = get_approver_emails(conn)
    if not recipients:
        log.warning("notify_approval_requested: no approver emails found, skipping")
        return
    subject = f"PO Approval Required: {po_number} (${total:,.2f})"
    body = (
        f"Purchase order {po_number} has been submitted for approval.\n\n"
        f"  Total:         ${total:,.2f}\n"
        f"  Submitted by:  {requested_by}\n\n"
        f"Review the PO:      {site_url}po/{po_id}/\n"
        f"Approval queue:     {site_url}po/approvals/\n"
    )
    _send(subject, body, recipients)


def notify_approval_decided(
    requester_email: str,
    po_number: str,
    total: float,
    approved: bool,
    notes: str,
    decided_by: str,
    site_url: str = '',
) -> None:
    """Email the submitter that their PO was approved or rejected."""
    if not requester_email:
        log.warning("notify_approval_decided: no requester email, skipping")
        return
    verb = "approved" if approved else "rejected"
    subject = f"PO {verb.title()}: {po_number}"
    body = (
        f"Your purchase order {po_number} (${total:,.2f}) has been {verb}.\n\n"
        f"  Decision by:  {decided_by}\n"
    )
    if notes:
        body += f"  Note:         {notes}\n"
    body += f"\nView purchase orders: {site_url}po/\n"
    _send(subject, body, [requester_email])


_FALLBACK_FROM = 'manufacturing@company.local'


def _send(subject: str, body: str, recipients: list[str]) -> None:
    """Dispatch an email; swallow any exception so callers never fail."""
    try:
        from django.core.mail import send_mail
        try:
            from django.conf import settings as djsettings
            from_email = djsettings.DEFAULT_FROM_EMAIL
        except Exception:
            from_email = _FALLBACK_FROM
        send_mail(subject, body, from_email, recipients, fail_silently=False)
        log.info("Email sent: %r → %s", subject, recipients)
    except Exception as exc:
        log.warning("Email notification failed (%s): %s", type(exc).__name__, exc)
