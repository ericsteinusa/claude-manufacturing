"""
notify_core.py — email notifications for the PO approval workflow, plus
the in-app notification center (persisted, per-user feed behind the
bell icon in base.html).

Uses Django's send_mail so email backend/host/credentials are configured
in settings.py (or via env vars).  All sends are fire-and-forget: a
failed send is logged but never raises, so email issues never break the
approval workflow.
"""

from .log_utils import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# In-app notification center
# ---------------------------------------------------------------------------

def ensure_notification_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification (
            id          SERIAL PRIMARY KEY,
            people_id   INTEGER NOT NULL,
            type        TEXT NOT NULL,
            entity_type TEXT NOT NULL DEFAULT '',
            entity_id   INTEGER,
            message     TEXT NOT NULL,
            read_at     TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS notification_people_unread "
        "ON notification(people_id, read_at)"
    )


def create_notification(conn, people_id: int, type_: str, message: str,
                        entity_type: str = '', entity_id: int | None = None) -> int:
    row = conn.execute(
        "INSERT INTO notification (people_id, type, entity_type, entity_id, message) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (people_id, type_, entity_type, entity_id, message),
    ).fetchone()
    return row['id']


def create_notifications_for_role(conn, role_name: str, type_: str, message: str,
                                  entity_type: str = '', entity_id: int | None = None) -> None:
    """Fan a notification out to every person holding *role_name*, in one query."""
    conn.execute(
        "INSERT INTO notification (people_id, type, entity_type, entity_id, message) "
        "SELECT p.id, %s, %s, %s, %s "
        "FROM people p "
        "JOIN user_roles ur ON ur.people_id = p.id "
        "JOIN roles r ON r.id = ur.role_id "
        "WHERE r.role_name = %s",
        (type_, entity_type, entity_id, message, role_name),
    )


def create_notifications_for_dept(conn, dept_name: str, type_: str, message: str,
                                  entity_type: str = '', entity_id: int | None = None) -> None:
    """Fan a notification out to every person in *dept_name*, in one query."""
    conn.execute(
        "INSERT INTO notification (people_id, type, entity_type, entity_id, message) "
        "SELECT p.id, %s, %s, %s, %s "
        "FROM people p "
        "JOIN dept d ON d.dept_id = p.dept_id "
        "WHERE d.dept_name = %s",
        (type_, entity_type, entity_id, message, dept_name),
    )


def list_notifications(conn, people_id: int, unread_only: bool = False,
                       limit: int = 50) -> list[dict]:
    sql = ("SELECT id, type, entity_type, entity_id, message, read_at, created_at "
           "FROM notification WHERE people_id = %s")
    params = [people_id]
    if unread_only:
        sql += " AND read_at IS NULL"
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_unread_count(conn, people_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM notification "
        "WHERE people_id = %s AND read_at IS NULL",
        (people_id,),
    ).fetchone()
    return row['cnt'] if row else 0


def mark_read(conn, notification_id: int, people_id: int) -> bool:
    """Mark one notification read, scoped to *people_id* so a user can't
    mark someone else's notification by guessing an id. Returns True if a
    row was actually updated (False if not found, not owned, or already read)."""
    row = conn.execute(
        "UPDATE notification SET read_at = NOW() "
        "WHERE id = %s AND people_id = %s AND read_at IS NULL RETURNING id",
        (notification_id, people_id),
    ).fetchone()
    return row is not None


def mark_all_read(conn, people_id: int) -> int:
    rows = conn.execute(
        "UPDATE notification SET read_at = NOW() "
        "WHERE people_id = %s AND read_at IS NULL RETURNING id",
        (people_id,),
    ).fetchall()
    return len(rows)


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


def notify_password_reset(email: str, reset_url: str, lifetime_minutes: int) -> None:
    """Email a single-use password-reset link to the account's own address.

    This is the only thing that proves the requester actually controls the
    email address on file -- see accounts.py's password_reset_token
    functions for why that step didn't exist before."""
    subject = "Password reset request"
    body = (
        "A password reset was requested for your account.\n\n"
        f"Reset your password:  {reset_url}\n\n"
        f"This link expires in {lifetime_minutes} minutes and can only be "
        "used once.\n\n"
        "If you didn't request this, you can safely ignore this email --"
        " your password will not be changed."
    )
    _send(subject, body, [email])


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
