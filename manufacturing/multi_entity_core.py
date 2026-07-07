"""
multi_entity_core.py — Qt-free Multi-Company / Multi-Entity (P3-F).

There is no legal-entity concept anywhere in this codebase — the GL is one
flat, global ledger (`gl_account`/`gl_journal`/`gl_journal_line`). Rather
than re-architecting the GL into per-entity ledgers, this follows the same
scope discipline the P2-D multi-currency feature used: a new `company`
master, plus a nullable `company_id` tag added additively to `gl_account`
(NULL = shared account usable by every entity — "shared chart of accounts
with overrides", one of the two options the spec explicitly allows) and to
`gl_journal` (NULL = pre-existing/legacy journal).

Legacy `gl_journal`/`gl_account` rows are never backfilled with a real
company_id — historical journals don't "turn over" the way inventory does,
so there's no safe migration. Instead, one lazily-created `company` row
(`is_base_entity=True`, via `get_or_create_base_company`, same sentinel
spirit as `wms_core.get_or_create_unassigned_bin`) stands in for "all data
that predates this feature," and reports for that entity ask
`accounting_core` to also include `company_id IS NULL` rows via
`include_null_company=True`.

Company-scoped and consolidated statements are both just calls into the
existing, unmodified-in-structure `accounting_core.trial_balance` /
`income_statement` / `balance_sheet` (which gained optional `company_id`/
`include_null_company` kwargs for this feature) — consolidated means
"call them with company_id=None", which is exactly their pre-existing
default behavior since there's only one ledger. The one thing they can't
express is elimination: `consolidated_income_statement`/
`consolidated_balance_sheet` here subtract the known intercompany amount,
which is exact because both sides of an intercompany transaction post
equal-and-opposite amounts to the same account pair.

Intercompany account mapping reuses the existing `gl_account_map` table
(`costing_core.get_gl_account_map`) but not `costing_core.set_gl_account_map`
-- that setter validates against `costing_core.GL_CATEGORIES`, which is
exact-set-asserted by tests/test_costing_core.py and can't be extended.
`set_ic_account_map` here is a small local upsert against the same table
using its own `IC_GL_CATEGORIES`, coexisting in the same category
namespace without touching costing_core at all.

An intercompany transaction needs four distinct GL accounts, not two: the
billing entity records `ic_receivable` (Asset) against `ic_revenue`
(Revenue) in its own book; the billed entity records `ic_expense` (Expense)
against `ic_payable` (Liability) in its own — each journal individually
balances and belongs entirely to one company, which is what makes each
entity's own trial balance/P&L correct. Consolidation then eliminates the
same `amount` from both sides of each pair (Asset vs. Liability, Revenue
vs. Expense) — net income is unaffected since the revenue and expense
eliminations cancel, which is the correct effect for a pure internal
recharge with no external profit.

Every function takes an open connection; the caller owns the transaction
(same convention as blanket_po_core / wms_core).
"""

from __future__ import annotations

from datetime import datetime

from .log_utils import get_logger
from .accounting_core import (
    create_journal, post_journal, void_journal, income_statement, balance_sheet,
)
from .costing_core import get_gl_account_map

log = get_logger(__name__)

IC_GL_CATEGORIES = ('ic_receivable', 'ic_payable', 'ic_revenue', 'ic_expense')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_multi_entity_tables(conn) -> None:
    """Create company/company_user/intercompany_transaction tables and the
    additive company_id columns on gl_account/gl_journal. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company (
            id             SERIAL PRIMARY KEY,
            name           TEXT NOT NULL,
            legal_name     TEXT DEFAULT '',
            tax_id         TEXT DEFAULT '',
            currency_code  TEXT DEFAULT 'USD',
            address        TEXT DEFAULT '',
            is_base_entity BOOLEAN NOT NULL DEFAULT FALSE,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            notes          TEXT DEFAULT '',
            created_at     TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company_user (
            id         SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
            people_id  INTEGER NOT NULL,
            created_at TEXT DEFAULT '',
            UNIQUE (company_id, people_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intercompany_transaction (
            id               SERIAL PRIMARY KEY,
            from_company_id  INTEGER NOT NULL REFERENCES company(id),
            to_company_id    INTEGER NOT NULL REFERENCES company(id),
            description      TEXT DEFAULT '',
            amount           REAL DEFAULT 0,
            transaction_date TEXT DEFAULT '',
            from_journal_id  INTEGER,
            to_journal_id    INTEGER,
            status           TEXT DEFAULT 'posted',
            created_by       TEXT DEFAULT '',
            created_at       TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "ALTER TABLE gl_account ADD COLUMN IF NOT EXISTS company_id INTEGER")
    conn.execute(
        "ALTER TABLE gl_journal ADD COLUMN IF NOT EXISTS company_id INTEGER")


def get_or_create_base_company(conn) -> int:
    """Return the id of the sentinel 'base entity' company, creating it
    once if absent. Represents all pre-P3-F data (company_id IS NULL)."""
    row = conn.execute(
        "SELECT id FROM company WHERE is_base_entity = TRUE LIMIT 1"
    ).fetchone()
    if row:
        return row['id']
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO company (name, is_base_entity, is_active, created_at) "
        "VALUES (%s, TRUE, TRUE, %s) RETURNING id",
        ('Home Entity', now),
    ).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Company master
# ---------------------------------------------------------------------------

def list_companies(conn, active_only: bool = True) -> list:
    q = "SELECT * FROM company"
    if active_only:
        q += " WHERE is_active = TRUE"
    q += " ORDER BY is_base_entity DESC, name"
    rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def get_company(conn, company_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM company WHERE id = %s", (company_id,)
    ).fetchone()
    return dict(row) if row else None


def create_company(conn, name: str, legal_name: str, tax_id: str,
                    currency_code: str, address: str, notes: str) -> int:
    if not name or not name.strip():
        raise ValueError("Company name is required.")
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO company (name, legal_name, tax_id, currency_code, "
        "address, notes, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), legal_name or '', tax_id or '',
         currency_code or 'USD', address or '', notes or '', now),
    ).fetchone()
    return row['id']


def update_company(conn, company_id: int, name: str, legal_name: str,
                    tax_id: str, currency_code: str, address: str,
                    notes: str, is_active: bool = True) -> None:
    if not name or not name.strip():
        raise ValueError("Company name is required.")
    conn.execute(
        "UPDATE company SET name=%s, legal_name=%s, tax_id=%s, "
        "currency_code=%s, address=%s, notes=%s, is_active=%s WHERE id=%s",
        (name.strip(), legal_name or '', tax_id or '', currency_code or 'USD',
         address or '', notes or '', is_active, company_id),
    )


# ---------------------------------------------------------------------------
# User-to-company assignment
# ---------------------------------------------------------------------------

def list_user_companies(conn, people_id: int | None, full_access: bool = False) -> list:
    """Companies this person can access. Full-access roles (President, VP)
    bypass assignment and see every active company."""
    if full_access:
        return list_companies(conn)
    rows = conn.execute("""
        SELECT c.* FROM company c
        JOIN company_user cu ON cu.company_id = c.id
        WHERE cu.people_id = %s AND c.is_active = TRUE
        ORDER BY c.is_base_entity DESC, c.name
    """, (people_id,)).fetchall()
    return [dict(r) for r in rows]


def assign_user_company(conn, company_id: int, people_id: int) -> None:
    conn.execute(
        "INSERT INTO company_user (company_id, people_id, created_at) "
        "VALUES (%s,%s,%s) ON CONFLICT (company_id, people_id) DO NOTHING",
        (company_id, people_id, datetime.now().isoformat()),
    )


def revoke_user_company(conn, company_id: int, people_id: int) -> None:
    conn.execute(
        "DELETE FROM company_user WHERE company_id=%s AND people_id=%s",
        (company_id, people_id),
    )


def list_company_users(conn, company_id: int) -> list:
    rows = conn.execute("""
        SELECT cu.people_id, p.first_name, p.last_name, p.email
        FROM company_user cu
        JOIN people p ON p.id = cu.people_id
        WHERE cu.company_id = %s
        ORDER BY p.last_name, p.first_name
    """, (company_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Intercompany account mapping (own gl_account_map upsert — see module
# docstring for why this bypasses costing_core.set_gl_account_map)
# ---------------------------------------------------------------------------

def set_ic_account_map(conn, category: str, account_number: str) -> None:
    if category not in IC_GL_CATEGORIES:
        raise ValueError(f"Unknown intercompany GL category: {category!r}")
    conn.execute(
        "INSERT INTO gl_account_map (category, account_number, description) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (category) DO UPDATE "
        "SET account_number=EXCLUDED.account_number, is_active=TRUE",
        (category, account_number, 'Intercompany (P3-F)'),
    )


def _account_id_by_number(conn, account_number: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM gl_account WHERE account_number = %s", (account_number,)
    ).fetchone()
    return row['id'] if row else None


# ---------------------------------------------------------------------------
# Intercompany transactions
# ---------------------------------------------------------------------------

def list_intercompany_transactions(conn) -> list:
    rows = conn.execute("""
        SELECT ic.*, fc.name AS from_company_name, tc.name AS to_company_name
        FROM intercompany_transaction ic
        JOIN company fc ON fc.id = ic.from_company_id
        JOIN company tc ON tc.id = ic.to_company_id
        ORDER BY ic.id DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_intercompany_transaction(conn, ic_id: int) -> dict | None:
    row = conn.execute("""
        SELECT ic.*, fc.name AS from_company_name, tc.name AS to_company_name
        FROM intercompany_transaction ic
        JOIN company fc ON fc.id = ic.from_company_id
        JOIN company tc ON tc.id = ic.to_company_id
        WHERE ic.id = %s
    """, (ic_id,)).fetchone()
    return dict(row) if row else None


def create_intercompany_transaction(conn, from_company_id: int, to_company_id: int,
                                     description: str, amount: float,
                                     transaction_date: str, created_by: str) -> dict:
    """Record an intercompany transaction. If all four IC accounts
    (ic_receivable, ic_revenue, ic_expense, ic_payable) are mapped, posts
    two balanced journals: the billing entity's own book (DR ic_receivable
    / CR ic_revenue, tagged to from_company_id) and the billed entity's own
    book (DR ic_expense / CR ic_payable, tagged to to_company_id). Each
    journal belongs entirely to one company and balances on its own; the
    two together net to zero on consolidation. If any account is unmapped,
    the transaction is still recorded but left unposted — mirrors
    costing_core.post_po_receipt_gl's "skip with a warning" precedent.

    Returns {'id': ..., 'unposted': bool}.
    """
    if from_company_id == to_company_id:
        raise ValueError("From and to company must be different.")
    amount = float(amount or 0)
    if amount <= 0:
        raise ValueError("Amount must be positive.")

    account_map = get_gl_account_map(conn)
    account_ids = {}
    for category in IC_GL_CATEGORIES:
        number = account_map.get(category)
        account_ids[category] = _account_id_by_number(conn, number) if number else None

    from_journal_id = to_journal_id = None
    unposted = True
    if all(account_ids.values()):
        from_journal_id = create_journal(
            conn, transaction_date, f"IC-{from_company_id}-{to_company_id}",
            description, [(account_ids['ic_receivable'], amount, 0.0, description),
                           (account_ids['ic_revenue'], 0.0, amount, description)],
            created_by)
        conn.execute(
            "UPDATE gl_journal SET company_id=%s WHERE id=%s",
            (from_company_id, from_journal_id))
        post_journal(conn, from_journal_id)

        to_journal_id = create_journal(
            conn, transaction_date, f"IC-{to_company_id}-{from_company_id}",
            description, [(account_ids['ic_expense'], amount, 0.0, description),
                           (account_ids['ic_payable'], 0.0, amount, description)],
            created_by)
        conn.execute(
            "UPDATE gl_journal SET company_id=%s WHERE id=%s",
            (to_company_id, to_journal_id))
        post_journal(conn, to_journal_id)
        unposted = False

    now = datetime.now().isoformat()
    status = 'unposted' if unposted else 'posted'
    row = conn.execute(
        "INSERT INTO intercompany_transaction "
        "(from_company_id, to_company_id, description, amount, transaction_date, "
        "from_journal_id, to_journal_id, status, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (from_company_id, to_company_id, description or '', amount,
         transaction_date or '', from_journal_id, to_journal_id, status,
         created_by or '', now),
    ).fetchone()
    return {'id': row['id'], 'unposted': unposted}


def void_intercompany_transaction(conn, ic_id: int) -> None:
    ic = conn.execute(
        "SELECT * FROM intercompany_transaction WHERE id = %s", (ic_id,)
    ).fetchone()
    if not ic:
        raise ValueError("Intercompany transaction not found.")
    if ic['status'] != 'posted':
        raise ValueError(f"Already {ic['status']}.")
    if ic['from_journal_id']:
        void_journal(conn, ic['from_journal_id'])
    if ic['to_journal_id']:
        void_journal(conn, ic['to_journal_id'])
    conn.execute(
        "UPDATE intercompany_transaction SET status='voided' WHERE id=%s",
        (ic_id,))


# ---------------------------------------------------------------------------
# Consolidated financials (elimination)
# ---------------------------------------------------------------------------

def _elimination_total(conn, date_from: str | None = None,
                        date_to: str | None = None) -> float:
    """Sum of posted intercompany amounts in the period — exactly what nets
    to zero across each transaction's two equal-and-opposite journals (both
    the Asset/Liability pair and the Revenue/Expense pair)."""
    q = ("SELECT COALESCE(SUM(amount), 0) AS total FROM intercompany_transaction "
         "WHERE status = 'posted'")
    params = []
    if date_from and date_to:
        q += " AND transaction_date BETWEEN %s AND %s"
        params += [date_from, date_to]
    elif date_to:
        q += " AND transaction_date <= %s"
        params.append(date_to)
    row = conn.execute(q, params).fetchone()
    return float(row['total'] or 0.0)


def consolidated_income_statement(conn, date_from: str, date_to: str) -> dict:
    """Revenue and Expense each include the intercompany recharge amount
    (booked in different entities), so both are reduced by the same
    elimination — net income is unaffected, as it should be for a pure
    internal recharge with no external profit."""
    gross = income_statement(conn, date_from, date_to)
    elimination = _elimination_total(conn, date_from, date_to)
    gross['elimination'] = elimination
    gross['revenue_consolidated'] = gross['revenue'] - elimination
    gross['expenses_consolidated'] = gross['expenses'] - elimination
    gross['net_income_consolidated'] = gross['net_income']
    return gross


def consolidated_balance_sheet(conn, as_of: str | None = None) -> dict:
    """Assets and Liabilities each include the intercompany receivable/
    payable pair, so both are reduced by the same elimination amount —
    the balance sheet stays balanced (A - e = (L - e) + Equity)."""
    gross = balance_sheet(conn, as_of)
    elimination = _elimination_total(conn, date_to=as_of)
    gross['elimination'] = elimination
    gross['assets_consolidated'] = gross['assets'] - elimination
    gross['liabilities_consolidated'] = gross['liabilities'] - elimination
    return gross
