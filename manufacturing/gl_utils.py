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

import os
from .db_connection import get_db_connection



def _conn():
    c = get_db_connection()
    return c


def post_gl_entry(journal_date, reference, description, lines, created_by="System"):
    """
    Create a draft GL journal entry and return its ID, or None if an
    account number could not be resolved against the chart of accounts.

    Parameters
    ----------
    journal_date : str          "YYYY-MM-DD"
    reference    : str          e.g. "AP-2026-0001"
    description  : str          free-text description
    lines        : list of (account_number, debit, credit, memo)
    created_by   : str
    """
    try:
        with _conn() as con:
            resolved = []
            for acct_num, debit, credit, memo in lines:
                row = con.execute(
                    "SELECT id FROM gl_account WHERE account_number=%s", (acct_num,)
                ).fetchone()
                if not row:
                    return None
                resolved.append((row["id"], float(debit), float(credit), str(memo)))

            cur = con.execute(
                "INSERT INTO gl_journal(journal_date, reference, description, posted, created_by) "
                "VALUES(%s,%s,%s,0,%s) RETURNING id",
                (journal_date, reference, description, created_by),
            )
            jid = cur.fetchone()['id']
            con.executemany(
                "INSERT INTO gl_journal_line(journal_id, account_id, debit, credit, memo) "
                "VALUES(%s,%s,%s,%s,%s)",
                [(jid, aid, dr, cr, m) for aid, dr, cr, m in resolved],
            )
        return jid
    except Exception:
        return None


def gl_accounts_by_type(*types):
    """Return list of (account_number, account_name) for the given account types."""
    placeholders = ",".join("%s" for _ in types)
    with _conn() as con:
        rows = con.execute(
            f"SELECT account_number, account_name FROM gl_account "
            f"WHERE is_active=1 AND account_type IN ({placeholders}) "
            f"ORDER BY account_number",
            types,
        ).fetchall()
    return [(r["account_number"], r["account_name"]) for r in rows]
