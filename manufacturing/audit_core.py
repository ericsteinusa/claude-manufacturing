"""
audit_core.py — Database-level audit trail via PostgreSQL triggers.

Every INSERT, UPDATE, and DELETE on audited tables is captured in
``audit_log`` by a single PL/pgSQL trigger function.  The ``changed_by``
field is populated from the PostgreSQL session variable ``app.current_user``,
which callers set via :func:`set_audit_user` before performing writes.

Desktop modules have ``MFGAPP_USER`` propagated by the login shell, and
``db_pg.get_db`` / ``get_db_connection`` set the variable automatically
from that env var on every new connection.

Web views call ``set_audit_user`` explicitly inside request handlers that
write to the database.
"""

from .db_pg import get_db_connection
from .log_utils import get_logger

log = get_logger(__name__)

# Tables whose INSERT/UPDATE/DELETE rows are captured in audit_log.
# All must have an integer ``id`` primary key column.
AUDITED_TABLES = [
    'purchase_order',
    'po_item',
    'work_order',
    'wo_material',
    'sales_order',
    'so_item',
    'purchase_requisition',
    'requisition_item',
    'requisition_approval',
    'product',
    'people',
    'user_roles',
    'time_off_request',
    'payroll_run',
    'payroll_entry',
    'inventory_transaction',
    'maint_work_order',
]

_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION _audit_trigger()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO audit_log(
        table_name, record_id, action, changed_by, old_values, new_values
    ) VALUES (
        TG_TABLE_NAME,
        CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
        TG_OP,
        COALESCE(current_setting('app.current_user', TRUE), ''),
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE row_to_json(OLD)::jsonb END,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE row_to_json(NEW)::jsonb END
    );
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;
"""


def install_triggers(conn=None) -> None:
    """Create the trigger function and attach it to all audited tables.

    Idempotent: uses ``CREATE OR REPLACE`` for the function and
    ``DROP TRIGGER IF EXISTS`` before re-creating each trigger.
    Safe to call on every startup.
    """
    close_after = conn is None
    if conn is None:
        conn = get_db_connection()
    try:
        conn.execute(_TRIGGER_FN)
        for table in AUDITED_TABLES:
            conn.execute(
                f"DROP TRIGGER IF EXISTS _audit ON {table}"
            )
            conn.execute(
                f"CREATE TRIGGER _audit "
                f"AFTER INSERT OR UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION _audit_trigger()"
            )
        conn.commit()
        log.debug("Audit triggers installed on %d tables", len(AUDITED_TABLES))
    finally:
        if close_after:
            conn.close()


def set_audit_user(conn, email: str) -> None:
    """Set the current user for audit logging on this connection.

    Uses a transaction-local setting so it resets after each commit,
    preventing one request's user from leaking into the next.
    """
    conn.execute(
        "SELECT set_config('app.current_user', %s, TRUE)", (email or '',)
    )


def get_history(table_name: str, record_id: int) -> list[dict]:
    """Return the audit history for a single record, newest first."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, action, changed_by, changed_at, old_values, new_values "
            "FROM audit_log "
            "WHERE table_name = %s AND record_id = %s "
            "ORDER BY changed_at DESC",
            (table_name, record_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent(limit: int = 200, table_name: str | None = None,
               changed_by: str | None = None) -> list[dict]:
    """Return recent audit log entries with optional filters."""
    conditions = []
    params: list = []
    if table_name:
        conditions.append("table_name = %s")
        params.append(table_name)
    if changed_by:
        conditions.append("changed_by ILIKE %s")
        params.append(f"%{changed_by}%")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"SELECT id, table_name, record_id, action, changed_by, changed_at "
            f"FROM audit_log {where} "
            f"ORDER BY changed_at DESC LIMIT %s",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
