"""Qt-free purchase-requisition data layer and authorization logic.

Tables: purchase_requisition, requisition_item, requisition_approval.
Mirrors the existing Mobile API's requisition endpoints
(api_views.py's api_req / api_req_add_item / api_req_submit / api_req_decide)
so the web UI behaves identically — same statuses, same visibility rules,
same dept-level (not multi-tier) decision.
"""

import datetime

from .mrp_core import next_sequence_number

REQ_STATUSES = (
    'draft', 'submitted', 'dept_approved', 'dept_denied',
    'approved', 'denied', 'cancelled',
)

COMPANY_WIDE_ROLES = (
    "President",
    "Vice President",
)

AUTHORIZER_ROLES = (
    "Department Manager",
    "Supervisor",
) + COMPANY_WIDE_ROLES


def is_manager(role_name):
    """True if role may authorize requisitions."""
    return role_name in AUTHORIZER_ROLES


def is_company_wide(role_name):
    """True if role may authorize any department's requests (not just own)."""
    return role_name in COMPANY_WIDE_ROLES


def can_authorize(role, status, req_dept_id, actor_dept_id, is_own):
    """Return True if the actor may authorize or deny a requisition.

    Rules:
    - Actor must hold an authorizer role (manager / supervisor / executive)
    - Requisition must be in 'submitted' status
    - Actor must be in scope: company-wide role OR same dept as the request
    - Actor cannot authorize their own request
    - None dept IDs are never treated as matching (prevents accidental
      cross-dept access)
    """
    if not is_manager(role):
        return False
    if status != "submitted":
        return False
    if is_own:
        return False
    in_scope = is_company_wide(role) or (
        req_dept_id is not None and req_dept_id == actor_dept_id)
    return in_scope


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

def ensure_requisition_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requisition (
            id SERIAL PRIMARY KEY,
            req_number TEXT NOT NULL UNIQUE,
            requester_id INTEGER, dept_id INTEGER, dept_sub_id INTEGER,
            needed_date TEXT, justification TEXT, purpose TEXT,
            status TEXT DEFAULT 'draft', created_date TEXT,
            po_id INTEGER, created_by TEXT, notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requisition_item (
            id SERIAL PRIMARY KEY,
            req_id INTEGER NOT NULL REFERENCES purchase_requisition(id),
            description TEXT NOT NULL, product_id INTEGER,
            qty INTEGER DEFAULT 1, est_unit_price REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requisition_approval (
            id SERIAL PRIMARY KEY,
            req_id INTEGER NOT NULL REFERENCES purchase_requisition(id),
            level TEXT, approver_id INTEGER, decision TEXT,
            comment TEXT, decided_date TEXT
        )
    """)
    conn.commit()


def list_requisitions(conn, *, full_access: bool, is_manager_role: bool,
                       dept_id, requester_id, status=None, search=None) -> list:
    """Visibility mirrors the Mobile API: full-access roles see everything,
    managers see their own department's requisitions, everyone else sees
    only their own."""
    ensure_requisition_tables(conn)
    sql = """
        SELECT pr.id, pr.req_number, pr.dept_id, pr.justification,
               pr.needed_date, pr.status, pr.notes, pr.created_date,
               pr.requester_id,
               p.first_name || ' ' || p.last_name AS requester_name,
               d.dept_name,
               COALESCE((SELECT SUM(ri.qty * ri.est_unit_price)
                         FROM requisition_item ri WHERE ri.req_id = pr.id), 0) AS est_total
        FROM purchase_requisition pr
        LEFT JOIN people p ON p.id = pr.requester_id
        LEFT JOIN dept d ON d.dept_id = pr.dept_id
        WHERE TRUE
    """
    params: list = []
    if not full_access:
        if is_manager_role:
            sql += " AND pr.dept_id = %s"
            params.append(dept_id)
        else:
            sql += " AND pr.requester_id = %s"
            params.append(requester_id)
    if status:
        sql += " AND pr.status = %s"
        params.append(status)
    if search:
        sql += " AND (pr.req_number ILIKE %s OR pr.justification ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY pr.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_requisition(conn, req_id: int) -> dict | None:
    ensure_requisition_tables(conn)
    row = conn.execute("""
        SELECT pr.*,
               p.first_name || ' ' || p.last_name AS requester_name,
               d.dept_name
        FROM purchase_requisition pr
        LEFT JOIN people p ON p.id = pr.requester_id
        LEFT JOIN dept d ON d.dept_id = pr.dept_id
        WHERE pr.id = %s
    """, (req_id,)).fetchone()
    return dict(row) if row else None


def list_requisition_items(conn, req_id: int) -> list:
    ensure_requisition_tables(conn)
    rows = conn.execute("""
        SELECT id, description, product_id, qty, est_unit_price,
               (qty * est_unit_price) AS line_total
        FROM requisition_item WHERE req_id = %s ORDER BY id
    """, (req_id,)).fetchall()
    return [dict(r) for r in rows]


def list_requisition_approvals(conn, req_id: int) -> list:
    ensure_requisition_tables(conn)
    rows = conn.execute("""
        SELECT ra.id, ra.level, ra.decision, ra.comment, ra.decided_date,
               p.first_name || ' ' || p.last_name AS approver_name
        FROM requisition_approval ra
        LEFT JOIN people p ON p.id = ra.approver_id
        WHERE ra.req_id = %s ORDER BY ra.id
    """, (req_id,)).fetchall()
    return [dict(r) for r in rows]


def create_requisition(conn, requester_id, dept_id, dept_sub_id,
                        needed_date, justification, notes, created_by) -> int:
    ensure_requisition_tables(conn)
    year = datetime.date.today().year
    prefix = f'REQ-{year}-'
    existing = [
        r[0] for r in conn.execute(
            "SELECT req_number FROM purchase_requisition WHERE req_number LIKE %s",
            (prefix + '%',),
        ).fetchall()
    ]
    req_number = next_sequence_number(existing, prefix)
    row = conn.execute("""
        INSERT INTO purchase_requisition
        (req_number, requester_id, dept_id, dept_sub_id, needed_date,
         justification, notes, status, created_date, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s) RETURNING id
    """, (req_number, requester_id, dept_id, dept_sub_id, needed_date or None,
          justification, notes, datetime.date.today().isoformat(), created_by)
    ).fetchone()
    return row[0]


def add_requisition_item(conn, req_id: int, description: str,
                          qty: int, est_unit_price: float) -> int:
    ensure_requisition_tables(conn)
    row = conn.execute("""
        INSERT INTO requisition_item (req_id, description, qty, est_unit_price)
        VALUES (%s,%s,%s,%s) RETURNING id
    """, (req_id, description, qty or 1, est_unit_price or 0.0)).fetchone()
    return row[0]


def submit_requisition(conn, req_id: int) -> None:
    """Mark a draft requisition submitted and kick off the configurable
    approval workflow (if any rules are set up for 'purchase_requisition').

    dept.dept_name -> dept_key goes through menus.DEPT_MENU_KEY (a Python
    dict, not a DB column) — the mobile API's api_req_submit assumes a
    dept.dept_key column that doesn't exist live and would 500; this
    mirrors the correct lookup used by accounts._get_user_profile instead.
    """
    from . import approval_workflow_core
    from .menus import DEPT_MENU_KEY
    conn.execute(
        "UPDATE purchase_requisition SET status = 'submitted' WHERE id = %s",
        (req_id,),
    )
    total_row = conn.execute(
        "SELECT COALESCE(SUM(qty * est_unit_price), 0) AS total"
        " FROM requisition_item WHERE req_id = %s",
        (req_id,),
    ).fetchone()
    total = float(total_row['total']) if total_row else 0.0
    dept_row = conn.execute(
        "SELECT dept_name FROM dept WHERE dept_id ="
        " (SELECT dept_id FROM purchase_requisition WHERE id = %s)",
        (req_id,),
    ).fetchone()
    dept_key = DEPT_MENU_KEY.get(dept_row['dept_name'], '') if dept_row else ''
    approval_workflow_core.ensure_approval_tables(conn)
    approval_workflow_core.submit_for_approval(
        conn, 'purchase_requisition', req_id, total, dept_key,
    )


def decide_requisition(conn, req_id: int, decision: str,
                        approver_id, comment: str) -> str:
    """Record a dept-level approve/deny decision. Caller must already have
    checked can_authorize(). Returns the new status."""
    ensure_requisition_tables(conn)
    new_status = 'dept_approved' if decision == 'approve' else 'dept_denied'
    conn.execute(
        "UPDATE purchase_requisition SET status = %s WHERE id = %s",
        (new_status, req_id),
    )
    conn.execute("""
        INSERT INTO requisition_approval
        (req_id, level, decision, approver_id, comment, decided_date)
        VALUES (%s, 'dept', %s, %s, %s, CURRENT_DATE::text)
    """, (req_id, decision, approver_id, comment))
    return new_status


def decide_requisition_via_workflow(conn, req_id: int, step_id: int, decision: str,
                                     decided_by: str, notes: str = '') -> str:
    """Decide one approval_workflow step for a requisition — the path used
    by the mobile Approvals tab (api_workflow_decide) — and sync
    purchase_requisition.status to match, mirroring decide_requisition()'s
    dept_approved/dept_denied semantics.

    Without this, deciding a step via the generic approval_workflow_core
    engine (as opposed to the web app's decide_requisition() path) leaves
    the requisition itself permanently stuck at 'submitted', since
    approval_step and purchase_requisition are otherwise unlinked tables.
    Returns the resulting purchase_requisition status.
    """
    from . import approval_workflow_core
    overall = approval_workflow_core.decide_step(
        conn, step_id, decision, decided_by, notes)
    if overall == 'approved':
        conn.execute(
            "UPDATE purchase_requisition SET status = 'dept_approved' WHERE id = %s",
            (req_id,),
        )
        return 'dept_approved'
    if overall == 'rejected':
        conn.execute(
            "UPDATE purchase_requisition SET status = 'dept_denied' WHERE id = %s",
            (req_id,),
        )
        return 'dept_denied'
    return 'submitted'
