"""Qt-free sales-order helpers.

Kept separate from sales_orders.py (which imports PyQt6) so sequence
generation can be unit-tested without the Qt shared libraries.
"""
from datetime import date

from .mrp_core import next_sequence_number


def next_so_number(conn, today=None):
    """Return the next SO-<year>-NNNN on conn's transaction.

    Uses max-suffix+1 (gap-safe), generated on the caller's own connection —
    so creating several SOs in one uncommitted transaction yields distinct
    numbers, unlike a COUNT(*) on a fresh connection.
    """
    year = (today or date.today()).year
    prefix = f"SO-{year}-"
    rows = conn.execute(
        "SELECT so_number FROM sales_order WHERE so_number LIKE %s",
        (prefix + "%",)
    ).fetchall()
    return next_sequence_number([r["so_number"] for r in rows], prefix)
