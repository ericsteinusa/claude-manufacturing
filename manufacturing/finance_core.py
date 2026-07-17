"""Qt-free Finance data layer — dashboard, budgets, audits, bank-rec, tax."""

import calendar
import datetime

from .accounting_core import get_ap_dashboard, get_ar_dashboard, income_statement

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUDGET_STATUSES = ('draft', 'approved', 'active', 'closed')

FIN_AUDIT_TYPES = (
    'Internal', 'External', 'Compliance', 'Operational',
    'Financial', 'IT', 'Tax', 'Other',
)
FIN_AUDIT_STATUSES = ('Scheduled', 'In Progress', 'Completed', 'Cancelled')
FINDING_SEVERITIES = ('Minor', 'Moderate', 'Major', 'Critical')
FINDING_STATUSES = ('Open', 'In Progress', 'Resolved', 'Closed')

TAX_TYPES = (
    'Federal Income', 'State Income', 'Sales Tax',
    'Payroll Tax', 'Property Tax', 'Excise Tax', 'Other',
)
TAX_FILING_STATUSES = ('Pending', 'Filed', 'Paid', 'Overdue', 'Amended')

BANK_STATEMENT_STATUSES = ('Open', 'In Progress', 'Reconciled')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_finance_dashboard(conn) -> dict:
    """Return dict with keys: ap, ar, recent_journals."""
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


def get_top_ar_customers(conn, limit: int = 8) -> list[dict]:
    """Return [{customer, balance}] — top open AR balances by customer."""
    rows = conn.execute("""
        SELECT COALESCE(c.company_name, 'Unknown') AS customer,
               COALESCE(SUM(i.amount), 0) AS balance
        FROM ar_invoice i
        LEFT JOIN customer c ON c.id = i.customer_id
        WHERE i.status IN ('open', 'partial', 'overdue')
        GROUP BY c.company_name ORDER BY balance DESC LIMIT %s
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_invoice_status_mix(conn) -> dict:
    """Return {ar: [{status, cnt}], ap: [{status, cnt}]} — invoice counts
    by status for AR and AP, used in a grouped-bar chart."""
    ar_rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM ar_invoice GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    ap_rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM ap_invoice GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    return {
        'ar': [dict(r) for r in ar_rows],
        'ap': [dict(r) for r in ap_rows],
    }


def get_revenue_expense_by_month(conn, months: int = 6) -> list[dict]:
    """Return [{month, revenue, expenses}] for the last ``months`` months,
    for a revenue-vs-expense chart. Loops accounting_core.income_statement
    per month — there is no existing monthly-grouped GL aggregate."""
    today = datetime.date.today()
    result = []
    for i in range(months - 1, -1, -1):
        year = today.year + (today.month - 1 - i) // 12
        month = (today.month - 1 - i) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        date_from = datetime.date(year, month, 1).isoformat()
        date_to = datetime.date(year, month, last_day).isoformat()
        stmt = income_statement(conn, date_from, date_to)
        result.append({
            'month': f"{year:04d}-{month:02d}",
            'revenue': stmt['revenue'],
            'expenses': stmt['expenses'],
        })
    return result


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def list_budgets(conn, status=None, fiscal_year=None, search=None) -> list:
    sql = (
        "SELECT id, budget_name, fiscal_year, status, notes, created_by "
        "FROM budget WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if fiscal_year:
        sql += " AND fiscal_year = %s"
        params.append(fiscal_year)
    if search:
        sql += " AND (budget_name ILIKE %s OR notes ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY fiscal_year DESC, budget_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_budget(conn, budget_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM budget WHERE id = %s", (budget_id,)
    ).fetchone()
    return dict(row) if row else None


def get_budget_lines(conn, budget_id: int) -> list:
    rows = conn.execute(
        "SELECT * FROM budget_line WHERE budget_id = %s ORDER BY id",
        (budget_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_budget(
    conn, budget_name: str, fiscal_year: int, status: str, notes: str,
    created_by: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO budget (budget_name, fiscal_year, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (budget_name, fiscal_year, status or 'draft', notes, created_by),
    )
    return cur.fetchone()[0]


def update_budget(conn, budget_id: int, **fields) -> None:
    allowed = {'budget_name', 'fiscal_year', 'status', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE budget SET {set_clause} WHERE id = %s",
        list(cols.values()) + [budget_id],
    )


def create_budget_line(
    conn, budget_id: int, category: str, description: str,
    budgeted_amount: float, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO budget_line (budget_id, category, description, budgeted_amount, notes) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (budget_id, category, description, budgeted_amount or 0, notes),
    )
    return cur.fetchone()[0]


def update_budget_line(
    conn, line_id: int, category: str, description: str,
    budgeted_amount: float, gl_account_id: int | None = None,
    notes: str = '',
) -> None:
    """Update a budget line, optionally linking it to a GL account. Does not commit."""
    conn.execute(
        "UPDATE budget_line SET category=%s, description=%s, "
        "budgeted_amount=%s, gl_account_id=%s, notes=%s WHERE id=%s",
        (category, description, budgeted_amount or 0,
         gl_account_id or None, notes, line_id),
    )


def delete_budget_line(conn, line_id: int) -> None:
    conn.execute("DELETE FROM budget_line WHERE id = %s", (line_id,))


# ---------------------------------------------------------------------------
# Budget vs. Actual  (Phase 3B)
# ---------------------------------------------------------------------------

def get_budget_vs_actual(conn, budget_id: int,
                         date_from: str, date_to: str) -> dict:
    """Compare budget lines to actual GL activity for a date range.

    Budget lines linked to a ``gl_account_id`` pull actuals from posted GL
    journal entries in the period.  Unlinked lines show 0 actual.

    Returns::

        {
          'budget': {id, budget_name, fiscal_year, ...},
          'lines': [{category, description, budgeted_amount,
                     actual_amount, variance, pct_used}, ...],
          'totals': {budgeted, actual, variance},
        }
    """
    budget = get_budget(conn, budget_id)
    if not budget:
        return {}

    lines = conn.execute(
        "SELECT bl.id, bl.category, bl.description, bl.budgeted_amount, "
        "bl.gl_account_id, a.account_type "
        "FROM budget_line bl "
        "LEFT JOIN gl_account a ON a.id = bl.gl_account_id "
        "WHERE bl.budget_id = %s ORDER BY bl.id",
        (budget_id,),
    ).fetchall()

    result_lines = []
    total_budgeted = total_actual = 0.0

    for line in lines:
        budgeted = float(line['budgeted_amount'] or 0)
        actual = 0.0

        if line['gl_account_id']:
            acct_type = line['account_type'] or 'Expense'
            gl_row = conn.execute("""
                SELECT COALESCE(SUM(jl.debit), 0)  AS d,
                       COALESCE(SUM(jl.credit), 0) AS c
                FROM gl_journal_line jl
                JOIN gl_journal j ON j.id = jl.journal_id
                WHERE jl.account_id = %s AND j.posted = 1
                  AND j.journal_date BETWEEN %s AND %s
            """, (line['gl_account_id'], date_from, date_to)).fetchone()
            if gl_row:
                d, c = float(gl_row['d']), float(gl_row['c'])
                from .accounting_core import DEBIT_NORMAL
                actual = (d - c) if acct_type in DEBIT_NORMAL else (c - d)

        variance = budgeted - actual
        pct_used = round((actual / budgeted * 100), 1) if budgeted else 0.0
        total_budgeted += budgeted
        total_actual += actual

        result_lines.append({
            'id': line['id'],
            'category': line['category'],
            'description': line['description'],
            'budgeted_amount': budgeted,
            'actual_amount': actual,
            'variance': variance,
            'pct_used': pct_used,
        })

    return {
        'budget': budget,
        'lines': result_lines,
        'totals': {
            'budgeted': total_budgeted,
            'actual': total_actual,
            'variance': total_budgeted - total_actual,
        },
    }


# ---------------------------------------------------------------------------
# Audits
# ---------------------------------------------------------------------------

def list_audits(conn, status=None, audit_type=None, search=None) -> list:
    sql = (
        "SELECT id, audit_name, audit_type, department, auditor, "
        "scheduled, completed, status "
        "FROM audit_schedule WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if audit_type:
        sql += " AND audit_type = %s"
        params.append(audit_type)
    if search:
        sql += " AND (audit_name ILIKE %s OR department ILIKE %s OR auditor ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY scheduled DESC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_audit_record(conn, audit_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM audit_schedule WHERE id = %s", (audit_id,)
    ).fetchone()
    return dict(row) if row else None


def get_audit_findings(conn, audit_id: int) -> list:
    rows = conn.execute(
        "SELECT * FROM audit_finding WHERE audit_id = %s ORDER BY found_date DESC, id DESC",
        (audit_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_audit(
    conn, audit_name: str, audit_type: str, department: str,
    auditor: str, scheduled: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO audit_schedule "
        "(audit_name, audit_type, department, auditor, scheduled, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (audit_name, audit_type, department, auditor,
         scheduled or None, status or 'Scheduled', notes),
    )
    return cur.fetchone()[0]


def update_audit_record(conn, audit_id: int, **fields) -> None:
    allowed = {
        'audit_name', 'audit_type', 'department', 'auditor',
        'scheduled', 'completed', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE audit_schedule SET {set_clause} WHERE id = %s",
        list(cols.values()) + [audit_id],
    )


def create_audit_finding(
    conn, audit_id: int, finding_ref: str, description: str,
    severity: str, department: str, found_date: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO audit_finding "
        "(audit_id, finding_ref, description, severity, department, found_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,'Open',%s) RETURNING id",
        (audit_id, finding_ref, description, severity or 'Minor',
         department, found_date or None, notes),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Bank Reconciliation
# ---------------------------------------------------------------------------

def list_bank_accounts(conn, search=None) -> list:
    sql = (
        "SELECT id, account_name, bank_name, account_number, is_active, notes "
        "FROM bank_account WHERE TRUE"
    )
    params: list = []
    if search:
        sql += " AND (account_name ILIKE %s OR bank_name ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY account_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_bank_account(conn, account_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM bank_account WHERE id = %s", (account_id,)
    ).fetchone()
    return dict(row) if row else None


def list_bank_statements(conn, account_id: int, status=None) -> list:
    sql = (
        "SELECT id, statement_date, beginning_balance, ending_balance, "
        "status, reconciled_by, reconciled_at "
        "FROM bank_statement WHERE bank_account_id = %s"
    )
    params: list = [account_id]
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY statement_date DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_cash_position(conn, as_of=None):
    """Total balance across active bank accounts: the latest bank_statement
    ending_balance per account (bank_account itself carries no balance
    column). Mirrors reports_core.financial_dashboard's inline cash query;
    exposed here as a standalone function since finance_core already owns
    bank-account CRUD and cash_flow_core.py needs it as its own value
    (calling the full financial_dashboard() for one field would run several
    unrelated DSO/DPO/aging queries just to discard them).

    as_of optionally restricts each account to its latest statement dated
    on or before that date (a historical snapshot); omit for the current
    balance (latest statement regardless of date).
    """
    sql = (
        "SELECT COALESCE(SUM(latest.ending_balance), 0) AS cash "
        "FROM bank_account ba "
        "JOIN LATERAL ( "
        "    SELECT ending_balance FROM bank_statement bs "
        "    WHERE bs.bank_account_id = ba.id "
    )
    params: list = []
    if as_of:
        sql += " AND bs.statement_date <= %s "
        params.append(as_of)
    sql += (
        "    ORDER BY bs.statement_date DESC, bs.id DESC LIMIT 1 "
        ") latest ON TRUE "
        "WHERE ba.is_active = 1"
    )
    row = conn.execute(sql, params).fetchone()
    return float(row['cash']) if row else 0.0


def create_bank_account(
    conn, account_name: str, bank_name: str, account_number: str,
    routing_number: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO bank_account "
        "(account_name, bank_name, account_number, routing_number, is_active, notes) "
        "VALUES (%s,%s,%s,%s,1,%s) RETURNING id",
        (account_name, bank_name, account_number, routing_number, notes),
    )
    return cur.fetchone()[0]


def update_bank_account(conn, account_id: int, **fields) -> None:
    allowed = {'account_name', 'bank_name', 'account_number', 'routing_number', 'is_active', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE bank_account SET {set_clause} WHERE id = %s",
        list(cols.values()) + [account_id],
    )


def create_bank_statement(
    conn, bank_account_id: int, statement_date: str,
    beginning_balance: float, ending_balance: float,
) -> int:
    """Insert a bank statement header and return its id. Does not commit."""
    row = conn.execute(
        "INSERT INTO bank_statement "
        "(bank_account_id, statement_date, beginning_balance, ending_balance, status) "
        "VALUES (%s,%s,%s,%s,'Open') RETURNING id",
        (bank_account_id, statement_date,
         float(beginning_balance), float(ending_balance)),
    ).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Bank Reconciliation Matching  (Phase 3C)
# ---------------------------------------------------------------------------

_AUTO_MATCH_DATE_WINDOW = 3  # days either side to consider a GL date match


def import_bank_transactions(
    conn, bank_account_id: int, statement_id: int | None,
    transactions: list[dict],
) -> int:
    """Bulk-insert bank transactions from a statement download.

    Each dict in ``transactions`` must have: trans_date, amount, description.
    Optional: ref_number, created_by.

    Returns the count of rows inserted.  Does not commit.
    """
    count = 0
    for txn in transactions:
        conn.execute(
            "INSERT INTO bank_transaction "
            "(bank_account_id, statement_id, trans_date, amount, "
            "description, ref_number, cleared, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,FALSE,%s)",
            (bank_account_id, statement_id or None,
             txn['trans_date'], float(txn['amount']),
             txn.get('description', ''), txn.get('ref_number', ''),
             txn.get('created_by', '')),
        )
        count += 1
    return count


def auto_match_transactions(conn, statement_id: int) -> dict:
    """Attempt to match uncleared bank transactions to GL journal lines.

    Matching rule: same amount (within $0.01) AND gl_journal.journal_date
    within ±3 days of the bank transaction date.  If exactly one GL line
    matches, the transaction is auto-matched; ambiguous or missing → skipped.

    Returns {'matched': int, 'skipped': int, 'ambiguous': int}.
    """
    unmatched = conn.execute(
        "SELECT id, trans_date, amount FROM bank_transaction "
        "WHERE statement_id = %s AND matched_gl_line_id IS NULL AND cleared = FALSE",
        (statement_id,),
    ).fetchall()

    matched = skipped = ambiguous = 0
    for txn in unmatched:
        amt = float(txn['amount'])
        # Bank: positive = deposit (credit to bank GL), negative = payment
        # GL line: match absolute amounts on either debit or credit side
        candidates = conn.execute("""
            SELECT jl.id
            FROM gl_journal_line jl
            JOIN gl_journal j ON j.id = jl.journal_id
            WHERE j.posted = 1
              AND ABS(jl.debit - jl.credit - %s) < 0.01
              AND j.journal_date BETWEEN
                  (%s::date - %s)::text AND (%s::date + %s)::text
              AND NOT EXISTS (
                  SELECT 1 FROM bank_transaction bt
                  WHERE bt.matched_gl_line_id = jl.id
              )
        """, (amt, txn['trans_date'], _AUTO_MATCH_DATE_WINDOW,
               txn['trans_date'], _AUTO_MATCH_DATE_WINDOW)).fetchall()

        if len(candidates) == 1:
            conn.execute(
                "UPDATE bank_transaction "
                "SET matched_gl_line_id=%s, cleared=TRUE WHERE id=%s",
                (candidates[0]['id'], txn['id']),
            )
            matched += 1
        elif len(candidates) > 1:
            ambiguous += 1
        else:
            skipped += 1

    return {'matched': matched, 'skipped': skipped, 'ambiguous': ambiguous}


def manual_match_transaction(conn, bank_txn_id: int,
                              gl_line_id: int) -> None:
    """Manually link a bank transaction to a GL journal line. Does not commit."""
    conn.execute(
        "UPDATE bank_transaction "
        "SET matched_gl_line_id=%s, cleared=TRUE WHERE id=%s",
        (gl_line_id, bank_txn_id),
    )


def unmatch_transaction(conn, bank_txn_id: int) -> None:
    """Clear a bank transaction's GL match. Does not commit."""
    conn.execute(
        "UPDATE bank_transaction "
        "SET matched_gl_line_id=NULL, cleared=FALSE WHERE id=%s",
        (bank_txn_id,),
    )


def get_reconciliation_status(conn, statement_id: int) -> dict:
    """Return matched/unmatched/total counts and amounts for a statement."""
    row = conn.execute("""
        SELECT
            COUNT(*)                                            AS total,
            COUNT(*) FILTER (WHERE cleared = TRUE)             AS cleared,
            COUNT(*) FILTER (WHERE cleared = FALSE)            AS uncleared,
            COALESCE(SUM(ABS(amount)), 0)                      AS total_amount,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE cleared),  0) AS cleared_amount
        FROM bank_transaction WHERE statement_id = %s
    """, (statement_id,)).fetchone()
    return dict(row) if row else {
        'total': 0, 'cleared': 0, 'uncleared': 0,
        'total_amount': 0.0, 'cleared_amount': 0.0,
    }


def get_unmatched_transactions(conn, statement_id: int) -> list[dict]:
    """Return bank transactions with no GL match (reconciliation exceptions)."""
    rows = conn.execute(
        "SELECT id, trans_date, amount, description, ref_number, cleared "
        "FROM bank_transaction "
        "WHERE statement_id=%s AND matched_gl_line_id IS NULL "
        "ORDER BY trans_date, id",
        (statement_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def reconcile_statement(conn, statement_id: int,
                        reconciled_by: str) -> bool:
    """Mark a statement as Reconciled if all transactions are cleared.

    Returns True on success, False if uncleared transactions remain.
    Does not commit.
    """
    status = get_reconciliation_status(conn, statement_id)
    if status['uncleared'] > 0:
        return False
    conn.execute(
        "UPDATE bank_statement "
        "SET status='Reconciled', reconciled_by=%s, reconciled_at=NOW() "
        "WHERE id=%s",
        (reconciled_by, statement_id),
    )
    return True


# ---------------------------------------------------------------------------
# Tax Filings
# ---------------------------------------------------------------------------

def list_tax_filings(conn, status=None, tax_type=None, search=None) -> list:
    sql = (
        "SELECT id, tax_type, jurisdiction, period, amount_due, amount_paid, "
        "filed_date, due_date, status, reference "
        "FROM tax_filing WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if tax_type:
        sql += " AND tax_type = %s"
        params.append(tax_type)
    if search:
        sql += " AND (tax_type ILIKE %s OR jurisdiction ILIKE %s OR period ILIKE %s OR reference ILIKE %s)"
        params.extend([f"%{search}%"] * 4)
    sql += " ORDER BY due_date DESC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_tax_filing(conn, filing_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM tax_filing WHERE id = %s", (filing_id,)
    ).fetchone()
    return dict(row) if row else None


def list_tax_calendar(conn, status=None) -> list:
    sql = "SELECT * FROM tax_calendar WHERE TRUE"
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY due_date ASC NULLS LAST"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_tax_filing(
    conn, tax_type: str, jurisdiction: str, period: str,
    amount_due: float, due_date: str, status: str, reference: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO tax_filing "
        "(tax_type, jurisdiction, period, amount_due, amount_paid, "
        "due_date, status, reference, notes) "
        "VALUES (%s,%s,%s,%s,0,%s,%s,%s,%s) RETURNING id",
        (tax_type, jurisdiction, period, amount_due or 0,
         due_date or None, status or 'Pending', reference, notes),
    )
    return cur.fetchone()[0]


def update_tax_filing(conn, filing_id: int, **fields) -> None:
    allowed = {
        'tax_type', 'jurisdiction', 'period', 'amount_due', 'amount_paid',
        'filed_date', 'due_date', 'status', 'reference', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE tax_filing SET {set_clause} WHERE id = %s",
        list(cols.values()) + [filing_id],
    )
