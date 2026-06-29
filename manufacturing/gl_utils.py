"""
gl_utils.py — Shared GL journal-entry helper.

Usage:
    from gl_utils import post_gl_entry

    jid = post_gl_entry(
        journal_date = "2026-05-19",
        reference    = "AP-2026-0001",
        description  = "AP Invoice – Acme Corp",
        lines        = [
            ("5000", 1500.00, 0.00, "Cost of goods"),
            ("2000", 0.00,  1500.00, "Accounts Payable"),
        ],
        created_by   = "System",
    )
    # jid is None if an account number wasn't found in the chart of accounts.
"""

from .db_pg import get_db
from .log_utils import get_logger

log = get_logger(__name__)


def _conn():
    c = get_db()
    return c


def post_gl_entry(journal_date, reference, description,
                  lines, created_by="System"):
    """
    Create a draft GL journal entry and return its ID, or None if an
    account number could not be resolved against the chart of accounts.

    Parameters
    ----------
    journal_date : str          "YYYY-MM-DD"
    reference    : str          e.g. "AP-2026-0001"
    description  : str          free-text description
    lines        : list of (account_number, debit, credit, memo)
                   OR (account_number, debit, credit, memo, cost_center_id)
    created_by   : str
    """
    try:
        with _conn() as con:
            resolved = []
            for line in lines:
                acct_num, debit, credit, memo = line[:4]
                cost_center_id = line[4] if len(line) > 4 else None
                row = con.execute(
                    "SELECT id FROM gl_account WHERE account_number=%s", (
                        acct_num,)
                ).fetchone()
                if not row:
                    log.warning(
                        "GL entry %s aborted: account number %s not found "
                        "in chart of accounts", reference, acct_num)
                    return None
                resolved.append(
                    (row["id"], float(debit), float(credit),
                     str(memo), cost_center_id))

            cur = con.execute(
                "INSERT INTO gl_journal(journal_date, reference, description, "
                "posted, created_by) "
                "VALUES(%s,%s,%s,0,%s) RETURNING id",
                (journal_date, reference, description, created_by),
            )
            jid = cur.fetchone()['id']
            con.executemany(
                "INSERT INTO gl_journal_line(journal_id, account_id, debit, "
                "credit, memo, cost_center_id) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                [(jid, aid, dr, cr, m, cc)
                 for aid, dr, cr, m, cc in resolved],
            )
        log.info("Posted GL journal entry %s (reference %s)", jid, reference)
        return jid
    except Exception:
        log.error(
            "Failed to post GL entry (reference %s)", reference, exc_info=True)
        return None


def gl_accounts_by_type(*types):
    """Return list of (account_number, account_name) for the given account types."""  # noqa: E501
    placeholders = ",".join("%s" for _ in types)
    with _conn() as con:
        rows = con.execute(
            f"SELECT account_number, account_name FROM gl_account "
            f"WHERE is_active=1 AND account_type IN ({placeholders}) "
            f"ORDER BY account_number",
            types,
        ).fetchall()
    log.debug(
        "gl_accounts_by_type(%s) returned %d account(s)", types, len(rows))
    return [(r["account_number"], r["account_name"]) for r in rows]
