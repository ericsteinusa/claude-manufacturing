"""
period_locking_core.py — Fiscal period close/reopen controls.

A closed period blocks any INSERT or UPDATE whose date falls within that
month.  Enforcement happens in the web write views; the desktop path does
not currently enforce period locks (desktop modules hold long-lived
connections and don't validate dates centrally).

Periods are identified by (year, month) and stored in ``closed_periods``.
Only President and Vice President may close or reopen a period.
"""

from datetime import date as _date

from .db_pg import get_db_connection
from .log_utils import get_logger

_PERIOD_LOCK_FN = """
CREATE OR REPLACE FUNCTION _period_lock_check()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    _year  INT;
    _month INT;
BEGIN
    IF NEW.journal_date IS NULL THEN
        RETURN NEW;
    END IF;
    BEGIN
        _year  := EXTRACT(YEAR  FROM NEW.journal_date::date)::INT;
        _month := EXTRACT(MONTH FROM NEW.journal_date::date)::INT;
    EXCEPTION WHEN OTHERS THEN
        RETURN NEW;
    END;
    IF EXISTS (
        SELECT 1 FROM closed_periods
        WHERE period_year = _year AND period_month = _month
    ) THEN
        RAISE EXCEPTION 'Period %/% is closed — GL entries are not permitted',
            _year, _month;
    END IF;
    RETURN NEW;
END;
$$;
"""

log = get_logger(__name__)

# Roles permitted to close / reopen periods.
PERIOD_ADMIN_ROLES = {'President', 'Vice President'}


def is_period_locked(conn, date_str: str) -> bool:
    """Return True if the period containing *date_str* is closed.

    *date_str* is an ISO-8601 date string (``YYYY-MM-DD``).  Returns False
    for empty or unparseable values so that records without a date are never
    blocked.
    """
    if not date_str:
        return False
    try:
        d = _date.fromisoformat(str(date_str)[:10])
    except ValueError:
        return False
    row = conn.execute(
        "SELECT 1 FROM closed_periods "
        "WHERE period_year = %s AND period_month = %s",
        (d.year, d.month),
    ).fetchone()
    return row is not None


def period_label(year: int, month: int) -> str:
    """Return a human-readable label like 'June 2026'."""
    return _date(year, month, 1).strftime('%B %Y')


def list_periods(limit: int = 24) -> list[dict]:
    """Return the most recently closed periods, newest first."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, period_year, period_month, closed_at, closed_by, notes "
            "FROM closed_periods "
            "ORDER BY period_year DESC, period_month DESC "
            "LIMIT %s",
            (limit,),
        ).fetchall()
        return [
            {**dict(r),
             'label': period_label(r['period_year'], r['period_month'])}
            for r in rows
        ]
    finally:
        conn.close()


def close_period(conn, year: int, month: int,
                 closed_by: str, notes: str = '') -> None:
    """Close a period. Raises ValueError if already closed."""
    existing = conn.execute(
        "SELECT 1 FROM closed_periods "
        "WHERE period_year = %s AND period_month = %s",
        (year, month),
    ).fetchone()
    if existing:
        raise ValueError(
            f"{period_label(year, month)} is already closed.")
    conn.execute(
        "INSERT INTO closed_periods "
        "(period_year, period_month, closed_by, notes) "
        "VALUES (%s, %s, %s, %s)",
        (year, month, closed_by, notes or ''),
    )
    log.info("Period %s/%s closed by %s", year, month, closed_by)


def reopen_period(conn, period_id: int, reopened_by: str) -> None:
    """Reopen a closed period by its id."""
    conn.execute(
        "DELETE FROM closed_periods WHERE id = %s", (period_id,))
    log.info("Period id=%s reopened by %s", period_id, reopened_by)


def install_period_lock_trigger(conn=None) -> None:
    """Install a PostgreSQL BEFORE trigger on gl_journal that blocks writes
    to closed periods at the database layer.

    Idempotent — safe to call on every startup.
    """
    close_after = conn is None
    if conn is None:
        conn = get_db_connection()
    try:
        conn.execute(_PERIOD_LOCK_FN)
        conn.execute(
            "DROP TRIGGER IF EXISTS _period_lock ON gl_journal"
        )
        conn.execute(
            "CREATE TRIGGER _period_lock "
            "BEFORE INSERT OR UPDATE ON gl_journal "
            "FOR EACH ROW EXECUTE FUNCTION _period_lock_check()"
        )
        conn.commit()
        log.debug("Period lock trigger installed on gl_journal")
    finally:
        if close_after:
            conn.close()


def recent_months(n: int = 13) -> list[tuple[int, int]]:
    """Return the last *n* (year, month) tuples, current month first."""
    today = _date.today()
    months = []
    year, month = today.year, today.month
    for _ in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return months
