"""Qt-free work-order helpers.

Kept separate from work_orders.py (which imports PyQt6) so sequence
generation can be unit-tested without the Qt shared libraries.
"""
from datetime import date

from .mrp_core import next_sequence_number


def next_wo_number(conn, today=None):
    """Return the next WO-<year>-NNNN on conn's transaction.

    Uses max-suffix+1 (gap-safe), generated on the caller's own connection —
    so creating several WOs in one uncommitted transaction yields distinct
    numbers, unlike a COUNT(*) on a fresh connection.
    """
    year = (today or date.today()).year
    prefix = f"WO-{year}-"
    rows = conn.execute(
        "SELECT wo_number FROM work_order WHERE wo_number LIKE %s",
        (prefix + "%",)
    ).fetchall()
    return next_sequence_number([r["wo_number"] for r in rows], prefix)
