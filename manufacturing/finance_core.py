"""Qt-free Finance dashboard data layer."""

from .accounting_core import get_ap_dashboard, get_ar_dashboard


def get_finance_dashboard(conn) -> dict:
    """Return dict with keys: ap, ar, recent_journals.

    ap / ar: {open_count, overdue_count, total_outstanding,
              total_invoiced, total_invoices}
    recent_journals: list of last 8 rows
                     (id, journal_date, reference, description,
                      posted, total_debit, line_count)
    """
    ap = get_ap_dashboard(conn)
    ar = get_ar_dashboard(conn)

    rows = conn.execute(
        "SELECT j.id, j.journal_date, j.reference, j.description, j.posted, "
        "COUNT(jl.id) AS line_count, "
        "COALESCE(SUM(jl.debit), 0) AS total_debit "
        "FROM gl_journal j "
        "LEFT JOIN gl_journal_line jl ON jl.journal_id = j.id "
        "GROUP BY j.id "
        "ORDER BY j.journal_date DESC, j.id DESC LIMIT 8"
    ).fetchall()

    return {
        'ap': ap,
        'ar': ar,
        'recent_journals': [dict(r) for r in rows],
    }
