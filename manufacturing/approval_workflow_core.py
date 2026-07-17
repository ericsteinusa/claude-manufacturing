"""
approval_workflow_core.py — Configurable multi-level approval workflows.

Approval rules define who must sign off on what, in what order, and when
to escalate:

    approval_rule  — one row per "stage" (entity_type + threshold + seq)
    approval_step  — one row per pending/decided sign-off on a real entity

Typical rule set for Purchase Orders:
    seq=1  entity_type='purchase_order'  threshold=500    approver_role='Department Manager'
    seq=2  entity_type='purchase_order'  threshold=5000   approver_role='Vice President'

When ``submit_for_approval`` is called, it finds all rules that apply
(amount ≥ threshold, dept matches), creates one ``approval_step`` per rule
ordered by seq, and returns the list of step ids.  Steps must be approved
in seq order — a step is only actionable once all lower-seq steps are done.

Supported entity types: 'purchase_order', 'purchase_requisition', 'gl_journal',
'cycle_count', 'document'
"""

from .log_utils import get_logger

log = get_logger(__name__)

ENTITY_TYPES = ('purchase_order', 'purchase_requisition', 'gl_journal',
                'cycle_count', 'document')
STEP_STATUSES = ('pending', 'approved', 'rejected', 'escalated', 'skipped')


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def ensure_approval_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_rule (
            id                   SERIAL PRIMARY KEY,
            entity_type          TEXT NOT NULL,
            dept_key             TEXT NOT NULL DEFAULT '',
            threshold_amount     REAL NOT NULL DEFAULT 0.0,
            approver_role        TEXT NOT NULL,
            seq                  INTEGER NOT NULL DEFAULT 10,
            escalate_after_hours REAL NOT NULL DEFAULT 24.0,
            is_active            BOOLEAN NOT NULL DEFAULT TRUE,
            notes                TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_step (
            id             SERIAL PRIMARY KEY,
            rule_id        INTEGER REFERENCES approval_rule(id),
            entity_type    TEXT NOT NULL,
            entity_id      INTEGER NOT NULL,
            seq            INTEGER NOT NULL DEFAULT 10,
            status         TEXT NOT NULL DEFAULT 'pending',
            approver_role  TEXT NOT NULL,
            decided_by     TEXT NOT NULL DEFAULT '',
            decided_at     TIMESTAMPTZ,
            notes          TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS approval_step_entity "
        "ON approval_step(entity_type, entity_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS approval_step_role_pending "
        "ON approval_step(approver_role, status)"
    )


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------

def create_approval_rule(
    conn, entity_type: str, approver_role: str, seq: int = 10,
    dept_key: str = '', threshold_amount: float = 0.0,
    escalate_after_hours: float = 24.0, notes: str = '',
) -> int:
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {ENTITY_TYPES}")
    if not approver_role:
        raise ValueError("approver_role is required")
    row = conn.execute(
        "INSERT INTO approval_rule "
        "(entity_type, dept_key, threshold_amount, approver_role, "
        "seq, escalate_after_hours, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (entity_type, dept_key or '', float(threshold_amount),
         approver_role, seq, float(escalate_after_hours), notes or ''),
    ).fetchone()
    return row['id']


def get_approval_rule(conn, rule_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_type, dept_key, threshold_amount, approver_role, "
        "seq, escalate_after_hours, is_active, notes "
        "FROM approval_rule WHERE id = %s",
        (rule_id,),
    ).fetchone()
    return dict(row) if row else None


def list_approval_rules(conn, entity_type: str | None = None,
                        active_only: bool = True) -> list[dict]:
    conds, params = [], []
    if active_only:
        conds.append("is_active = TRUE")
    if entity_type:
        conds.append("entity_type = %s")
        params.append(entity_type)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(
        f"SELECT id, entity_type, dept_key, threshold_amount, approver_role, "
        f"seq, escalate_after_hours, is_active, notes "
        f"FROM approval_rule {where} "
        f"ORDER BY entity_type, seq, threshold_amount",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def update_approval_rule(conn, rule_id: int, **fields) -> None:
    allowed = {
        'entity_type', 'dept_key', 'threshold_amount', 'approver_role',
        'seq', 'escalate_after_hours', 'is_active', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'entity_type' in cols and cols['entity_type'] not in ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {ENTITY_TYPES}")
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE approval_rule SET {set_clause} WHERE id = %s",
        list(cols.values()) + [rule_id],
    )


def delete_approval_rule(conn, rule_id: int) -> None:
    conn.execute("DELETE FROM approval_rule WHERE id = %s", (rule_id,))


# ---------------------------------------------------------------------------
# Workflow engine
# ---------------------------------------------------------------------------

def get_applicable_rules(
    conn, entity_type: str, amount: float, dept_key: str = '',
) -> list[dict]:
    """Return active rules that apply to this entity type and amount.

    A rule applies when:
      - entity_type matches
      - amount >= threshold_amount
      - dept_key is '' (all departments) OR matches the entity's dept_key

    Returns rules sorted by seq ascending (sign-off order).
    """
    rows = conn.execute("""
        SELECT id, entity_type, dept_key, threshold_amount,
               approver_role, seq, escalate_after_hours
        FROM approval_rule
        WHERE entity_type = %s
          AND is_active = TRUE
          AND %s >= threshold_amount
          AND (dept_key = '' OR dept_key = %s)
        ORDER BY seq
    """, (entity_type, float(amount), dept_key or '')).fetchall()
    return [dict(r) for r in rows]


def submit_for_approval(
    conn, entity_type: str, entity_id: int,
    amount: float, dept_key: str = '', requested_by: str = '',
) -> list[int]:
    """Create approval_step rows for all applicable rules.

    Returns the list of step ids created (empty list if no rules apply).
    Idempotent: if steps already exist for this entity they are returned
    without creating duplicates.
    """
    existing = conn.execute(
        "SELECT id FROM approval_step "
        "WHERE entity_type = %s AND entity_id = %s",
        (entity_type, entity_id),
    ).fetchall()
    if existing:
        return [r['id'] for r in existing]

    rules = get_applicable_rules(conn, entity_type, amount, dept_key)
    step_ids: list[int] = []
    for rule in rules:
        row = conn.execute(
            "INSERT INTO approval_step "
            "(rule_id, entity_type, entity_id, seq, approver_role) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (rule['id'], entity_type, entity_id,
             rule['seq'], rule['approver_role']),
        ).fetchone()
        step_ids.append(row['id'])
        log.info(
            "Approval step %s created for %s#%s (seq=%s, role=%s) by %s",
            row['id'], entity_type, entity_id,
            rule['seq'], rule['approver_role'], requested_by,
        )
    return step_ids


def _all_prior_steps_done(conn, entity_type: str,
                          entity_id: int, seq: int) -> bool:
    """Return True if all lower-seq steps for this entity are resolved."""
    pending_prior = conn.execute("""
        SELECT COUNT(*) AS cnt FROM approval_step
        WHERE entity_type = %s AND entity_id = %s
          AND seq < %s AND status = 'pending'
    """, (entity_type, entity_id, seq)).fetchone()
    return (pending_prior['cnt'] if pending_prior else 0) == 0


def decide_step(conn, step_id: int, decision: str,
                decided_by: str, notes: str = '') -> str:
    """Record a decision on one approval step.

    *decision* must be 'approved' or 'rejected'.
    Returns the overall entity approval status after this decision:
      'approved'   — all steps approved
      'rejected'   — any step rejected
      'pending'    — more steps remain

    Raises ValueError if the step is not found, already decided, or a
    lower-seq step has not been resolved yet.
    """
    if decision not in ('approved', 'rejected'):
        raise ValueError("decision must be 'approved' or 'rejected'")
    row = conn.execute(
        "SELECT id, entity_type, entity_id, seq, status "
        "FROM approval_step WHERE id = %s",
        (step_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Approval step {step_id} not found")
    if row['status'] != 'pending':
        raise ValueError(
            f"Step {step_id} is already {row['status']}")
    if not _all_prior_steps_done(
            conn, row['entity_type'], row['entity_id'], row['seq']):
        raise ValueError(
            "Cannot decide step — earlier steps are still pending")

    conn.execute(
        "UPDATE approval_step "
        "SET status=%s, decided_by=%s, decided_at=NOW(), notes=%s "
        "WHERE id=%s",
        (decision, decided_by, notes or '', step_id),
    )
    log.info("Step %s %s by %s", step_id, decision, decided_by)

    if decision == 'rejected':
        return 'rejected'

    # Check if all steps are now approved
    remaining = conn.execute("""
        SELECT COUNT(*) AS cnt FROM approval_step
        WHERE entity_type = %s AND entity_id = %s AND status = 'pending'
    """, (row['entity_type'], row['entity_id'])).fetchone()
    return 'pending' if (remaining['cnt'] if remaining else 0) > 0 else 'approved'


def get_entity_approval_status(
    conn, entity_type: str, entity_id: int,
) -> dict:
    """Return all steps for an entity and the overall status."""
    rows = conn.execute("""
        SELECT s.id, s.seq, s.approver_role, s.status,
               s.decided_by, s.decided_at, s.notes, s.created_at,
               r.threshold_amount, r.escalate_after_hours
        FROM approval_step s
        LEFT JOIN approval_rule r ON r.id = s.rule_id
        WHERE s.entity_type = %s AND s.entity_id = %s
        ORDER BY s.seq
    """, (entity_type, entity_id)).fetchall()
    steps = [dict(r) for r in rows]
    if not steps:
        return {'steps': [], 'overall': 'no_workflow'}
    statuses = {s['status'] for s in steps}
    if 'rejected' in statuses:
        overall = 'rejected'
    elif statuses == {'approved'}:
        overall = 'approved'
    else:
        overall = 'pending'
    return {'steps': steps, 'overall': overall}


def get_pending_steps(
    conn, approver_role: str | None = None,
) -> list[dict]:
    """Return all pending steps, optionally filtered to one role."""
    conds = ["s.status = 'pending'"]
    params: list = []
    if approver_role:
        conds.append("s.approver_role = %s")
        params.append(approver_role)
    where = "WHERE " + " AND ".join(conds)
    rows = conn.execute(f"""
        SELECT s.id, s.entity_type, s.entity_id, s.seq,
               s.approver_role, s.created_at,
               r.threshold_amount, r.escalate_after_hours
        FROM approval_step s
        LEFT JOIN approval_rule r ON r.id = s.rule_id
        {where}
        ORDER BY s.created_at
    """, params).fetchall()
    return [dict(r) for r in rows]


def bulk_decide(
    conn, step_ids: list[int], decision: str,
    decided_by: str, notes: str = '',
) -> dict:
    """Approve or reject multiple steps.

    Returns {'succeeded': [ids], 'failed': [(id, reason)]}.
    """
    succeeded, failed = [], []
    for sid in step_ids:
        try:
            decide_step(conn, sid, decision, decided_by, notes)
            succeeded.append(sid)
        except ValueError as exc:
            failed.append((sid, str(exc)))
    return {'succeeded': succeeded, 'failed': failed}


def check_escalations(conn) -> int:
    """Advance overdue pending steps to 'escalated' status.

    A step is escalated when it has been pending longer than
    its rule's escalate_after_hours.  Returns the count of steps escalated.
    """
    overdue = conn.execute("""
        SELECT s.id
        FROM approval_step s
        JOIN approval_rule r ON r.id = s.rule_id
        WHERE s.status = 'pending'
          AND s.created_at < NOW() - (r.escalate_after_hours * INTERVAL '1 hour')
    """).fetchall()
    count = 0
    for row in overdue:
        conn.execute(
            "UPDATE approval_step SET status='escalated' WHERE id=%s",
            (row['id'],),
        )
        count += 1
    if count:
        log.info("Escalated %d overdue approval steps", count)
    return count
