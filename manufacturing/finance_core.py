"""Qt-free Finance data layer — dashboard, budgets, audits, bank-rec, tax."""

from .accounting_core import get_ap_dashboard, get_ar_dashboard

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUDGET_STATUSES = ('draft', 'approved', 'active', 'closed')

AUDIT_TYPES = (
    'Internal', 'External', 'Compliance', 'Operational',
    'Financial', 'IT', 'Tax', 'Other',
)
AUDIT_STATUSES = ('Scheduled', 'In Progress', 'Completed', 'Cancelled')
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


def delete_budget_line(conn, line_id: int) -> None:
    conn.execute("DELETE FROM budget_line WHERE id = %s", (line_id,))


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
