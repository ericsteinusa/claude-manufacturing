"""
approval_core.py — PO approval workflow.

Purchase orders whose line-item total exceeds APPROVAL_THRESHOLD require
a second sign-off from a President or Vice President before being sent to
the supplier.  The web ``po_set_status`` view intercepts the
``draft -> sent`` transition and routes the PO through this module instead.

Lifecycle
---------
draft  -->  (total > threshold)  -->  pending_approval
                                           |
                          approve()        |       reject()
                              |            v           |
                             sent   <-- decision --> draft
"""

from .db_pg import get_db_connection
from .log_utils import get_logger

log = get_logger(__name__)

# Dollar threshold above which a PO requires approval.
APPROVAL_THRESHOLD = 500.0

# Roles that may approve or reject.
APPROVAL_ROLES = {'President', 'Vice President'}


def needs_approval(total: float) -> bool:
    """Return True if a PO with *total* requires VP/President sign-off."""
    return (total or 0) > APPROVAL_THRESHOLD


def request_approval(conn, po_id: int, requested_by: str) -> int:
    """Insert a pending approval record and set the PO to pending_approval.

    Returns the new approval id.
    """
    row = conn.execute(
        "INSERT INTO po_approval (po_id, requested_by) "
        "VALUES (%s, %s) RETURNING id",
        (po_id, requested_by),
    ).fetchone()
    approval_id = row[0]
    conn.execute(
        "UPDATE purchase_order SET status = 'pending_approval' WHERE id = %s",
        (po_id,),
    )
    log.info("PO %s submitted for approval (approval id=%s) by %s",
             po_id, approval_id, requested_by)
    return approval_id


def approve_po(conn, approval_id: int, decided_by: str, notes: str = '') -> None:
    """Approve a pending PO: mark the approval record and advance PO to sent."""
    row = conn.execute(
        "SELECT po_id FROM po_approval WHERE id = %s AND status = 'pending'",
        (approval_id,),
    ).fetchone()
    if not row:
        raise ValueError("Approval request not found or already decided.")
    po_id = row[0]
    conn.execute(
        "UPDATE po_approval "
        "SET status = 'approved', decided_by = %s, decided_at = NOW(), notes = %s "
        "WHERE id = %s",
        (decided_by, notes or '', approval_id),
    )
    conn.execute(
        "UPDATE purchase_order SET status = 'sent' WHERE id = %s",
        (po_id,),
    )
    log.info("PO %s approved (approval id=%s) by %s", po_id, approval_id, decided_by)


def reject_po(conn, approval_id: int, decided_by: str, notes: str = '') -> None:
    """Reject a pending PO: mark the approval record and return PO to draft."""
    row = conn.execute(
        "SELECT po_id FROM po_approval WHERE id = %s AND status = 'pending'",
        (approval_id,),
    ).fetchone()
    if not row:
        raise ValueError("Approval request not found or already decided.")
    po_id = row[0]
    conn.execute(
        "UPDATE po_approval "
        "SET status = 'rejected', decided_by = %s, decided_at = NOW(), notes = %s "
        "WHERE id = %s",
        (decided_by, notes or '', approval_id),
    )
    conn.execute(
        "UPDATE purchase_order SET status = 'draft' WHERE id = %s",
        (po_id,),
    )
    log.info("PO %s rejected (approval id=%s) by %s", po_id, approval_id, decided_by)


def get_pending_approvals(conn) -> list[dict]:
    """Return all POs awaiting approval, newest first."""
    rows = conn.execute(
        "SELECT a.id, a.po_id, a.requested_by, a.requested_at, "
        "       po.po_number, s.company_name, "
        "       (SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) "
        "        FROM po_item pi WHERE pi.po_id = po.id) AS total "
        "FROM po_approval a "
        "JOIN purchase_order po ON po.id = a.po_id "
        "LEFT JOIN supplier s ON s.id = po.supplier_id "
        "WHERE a.status = 'pending' "
        "ORDER BY a.requested_at DESC",
    ).fetchall()
    return [dict(r) for r in rows]


def count_pending(conn) -> int:
    """Return the number of POs awaiting approval."""
    row = conn.execute(
        "SELECT COUNT(*) FROM po_approval WHERE status = 'pending'",
    ).fetchone()
    return row[0] if row else 0


def get_approval_by_id(conn, approval_id: int) -> dict | None:
    """Return an approval record with PO details, or None if not found."""
    row = conn.execute(
        "SELECT a.id, a.po_id, a.requested_by, a.status, "
        "       po.po_number, "
        "       (SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) "
        "        FROM po_item pi WHERE pi.po_id = po.id) AS total "
        "FROM po_approval a "
        "JOIN purchase_order po ON po.id = a.po_id "
        "WHERE a.id = %s",
        (approval_id,),
    ).fetchone()
    return dict(row) if row else None


def get_po_approval(conn, po_id: int) -> dict | None:
    """Return the most recent approval record for a PO, or None."""
    row = conn.execute(
        "SELECT id, po_id, requested_by, requested_at, "
        "       status, decided_by, decided_at, notes "
        "FROM po_approval "
        "WHERE po_id = %s "
        "ORDER BY requested_at DESC LIMIT 1",
        (po_id,),
    ).fetchone()
    return dict(row) if row else None
