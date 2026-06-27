"""seed_sample_finance.py — sample Finance data.

Covers: budgets, audit schedules, bank accounts, bank statements, and tax filings.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seed_sample_finance            # add (idempotent)
    python -m manufacturing.seed_sample_finance --reset     # remove + re-add
    python -m manufacturing.seed_sample_finance --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from .db_pg import get_db_connection

TAG = "SMPL-FIN-"
TODAY = date.today()
YEAR = TODAY.year


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id SERIAL PRIMARY KEY,
            budget_name TEXT NOT NULL,
            fiscal_year INTEGER,
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget_line (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL,
            category TEXT DEFAULT '',
            description TEXT DEFAULT '',
            budgeted_amount REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_schedule (
            id SERIAL PRIMARY KEY,
            audit_name TEXT NOT NULL,
            audit_type TEXT DEFAULT '',
            department TEXT DEFAULT '',
            auditor TEXT DEFAULT '',
            scheduled TEXT,
            completed TEXT,
            status TEXT DEFAULT 'Scheduled',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_finding (
            id SERIAL PRIMARY KEY,
            audit_id INTEGER NOT NULL,
            finding_ref TEXT DEFAULT '',
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'Minor',
            department TEXT DEFAULT '',
            found_date TEXT,
            status TEXT DEFAULT 'Open',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_account (
            id SERIAL PRIMARY KEY,
            account_name TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            account_number TEXT DEFAULT '',
            routing_number TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_statement (
            id SERIAL PRIMARY KEY,
            bank_account_id INTEGER NOT NULL,
            statement_date TEXT NOT NULL,
            beginning_balance REAL DEFAULT 0,
            ending_balance REAL DEFAULT 0,
            status TEXT DEFAULT 'Open',
            reconciled_by TEXT DEFAULT '',
            reconciled_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_filing (
            id SERIAL PRIMARY KEY,
            tax_type TEXT NOT NULL,
            jurisdiction TEXT DEFAULT '',
            period TEXT DEFAULT '',
            amount_due REAL DEFAULT 0,
            amount_paid REAL DEFAULT 0,
            filed_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_calendar (
            id SERIAL PRIMARY KEY,
            tax_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT ''
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Budgets + Lines
# ---------------------------------------------------------------------------

BUDGETS = [
    # (budget_name, fiscal_year, status, notes)
    (f"{TAG}Operating Budget {YEAR}",          YEAR,     "active",   "Full-year approved operating budget"),
    (f"{TAG}Capital Expenditure Budget {YEAR}", YEAR,     "active",   "Approved CapEx — equipment & facilities"),
    (f"{TAG}Marketing Budget {YEAR}",           YEAR,     "active",   "Marketing department budget"),
    (f"{TAG}Operating Budget {YEAR - 1}",       YEAR - 1, "closed",   "Prior year operating budget — closed"),
    (f"{TAG}Draft Budget {YEAR + 1}",           YEAR + 1, "draft",    "Preliminary next-year planning budget"),
]

BUDGET_LINES = {
    f"{TAG}Operating Budget {YEAR}": [
        ("Personnel",    "Salaries & Benefits — All Departments",  1850000),
        ("Facilities",   "Rent, Utilities, Maintenance",            420000),
        ("Materials",    "Raw Materials & Supplies",                680000),
        ("IT",           "Software Licenses, Hardware, Support",     95000),
        ("Legal",        "Legal Fees & Compliance",                  55000),
        ("Insurance",    "Property, Liability, Workers Comp",        72000),
        ("Travel",       "Business Travel & Entertainment",          38000),
        ("Training",     "Employee Development & Training",          24000),
    ],
    f"{TAG}Capital Expenditure Budget {YEAR}": [
        ("Equipment",    "CNC Mill Replacement",                    185000),
        ("Equipment",    "Laser Cutter Upgrade",                    220000),
        ("Facilities",   "Warehouse HVAC Replacement",               48000),
        ("IT",           "Server Refresh — Data Center",             65000),
        ("Vehicles",     "Forklift Replacement",                     42000),
    ],
    f"{TAG}Marketing Budget {YEAR}": [
        ("Advertising",  "Digital Advertising — Search & Social",    58000),
        ("Events",       "Trade Shows & Industry Events",            65000),
        ("Content",      "Content Creation & Design",                22000),
        ("PR",           "Public Relations Agency",                  18000),
        ("Research",     "Market Research Studies",                  12000),
    ],
}


def _seed_budgets(conn):
    budget_ids = {}
    for budget_name, fiscal_year, status, notes in BUDGETS:
        existing = conn.execute(
            "SELECT id FROM budget WHERE budget_name=%s", (budget_name,)
        ).fetchone()
        if existing:
            budget_ids[budget_name] = existing["id"]
            continue
        row = conn.execute(
            "INSERT INTO budget (budget_name, fiscal_year, status, notes, created_by)"
            " VALUES (%s,%s,%s,%s,'seed') RETURNING id",
            (budget_name, fiscal_year, status, notes),
        ).fetchone()
        budget_ids[budget_name] = row["id"]
    conn.commit()

    for budget_name, lines in BUDGET_LINES.items():
        bid = budget_ids.get(budget_name)
        if not bid:
            continue
        existing_count = conn.execute(
            "SELECT COUNT(*) FROM budget_line WHERE budget_id=%s", (bid,)
        ).fetchone()[0]
        if existing_count:
            continue
        for category, description, amount in lines:
            conn.execute(
                "INSERT INTO budget_line (budget_id, category, description, budgeted_amount, notes)"
                " VALUES (%s,%s,%s,%s,'Sample data')",
                (bid, category, description, amount),
            )
    conn.commit()
    return budget_ids


def _remove_budgets(conn):
    rows = conn.execute(
        "SELECT id FROM budget WHERE budget_name LIKE %s", (f"{TAG}%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM budget_line WHERE budget_id=%s", (r["id"],))
    conn.execute("DELETE FROM budget WHERE budget_name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Audit Schedules + Findings
# ---------------------------------------------------------------------------

AUDITS = [
    # (audit_name, audit_type, department, auditor, sched_ago, comp_ago, status)
    (f"{TAG}Q1 Financial Review", "Financial", "Finance", "External CPA", -90, -80, "Completed"),
    (f"{TAG}IT Systems Compliance Audit", "IT", "IT", "Sarah Moore CPA", -45, -40, "Completed"),
    (f"{TAG}Payroll Tax Compliance Q1", "Tax", "Finance", "External CPA", -60, -55, "Completed"),
    (f"{TAG}Internal Controls Review Q2", "Internal", "All Depts", "Sarah Moore CPA", -15, None, "In Progress"),
    (f"{TAG}Mid-Year Operational Audit", "Operational", "Production", "External CPA", 15, None, "Scheduled"),
    (f"{TAG}Year-End Financial Audit", "Financial", "Finance", "External CPA", 180, None, "Scheduled"),
    (f"{TAG}Tax Preparation Review H2", "Tax", "Finance", "Sarah Moore CPA", 120, None, "Scheduled"),
]

FINDINGS = [
    # (audit_name_suffix, finding_ref, description, severity, dept, found_ago)
    ("Q1 Financial Review", f"{TAG}F-001",
     "Invoice approval threshold not consistently followed", "Minor", "Finance", -82),
    ("Q1 Financial Review", f"{TAG}F-002",
     "Two GL entries posted without dual approval", "Moderate", "Finance", -81),
    ("IT Systems Compliance Audit", f"{TAG}F-003",
     "User access review overdue by 45 days", "Minor", "IT", -42),
    ("IT Systems Compliance Audit", f"{TAG}F-004",
     "Backup restoration test not completed Q1", "Major", "IT", -41),
]


def _seed_audits(conn):
    audit_ids = {}
    for audit_name, atype, dept, auditor, sched_ago, comp_ago, status in AUDITS:
        existing = conn.execute(
            "SELECT id FROM audit_schedule WHERE audit_name=%s", (audit_name,)
        ).fetchone()
        if existing:
            audit_ids[audit_name] = existing["id"]
            continue
        comp = _d(comp_ago) if comp_ago is not None else None
        row = conn.execute(
            "INSERT INTO audit_schedule (audit_name, audit_type, department, auditor,"
            " scheduled, completed, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data') RETURNING id",
            (audit_name, atype, dept, auditor, _d(sched_ago), comp, status),
        ).fetchone()
        audit_ids[audit_name] = row["id"]
    conn.commit()

    for audit_suffix, ref, desc, severity, dept, found_ago in FINDINGS:
        audit_name = f"{TAG}{audit_suffix}"
        audit_id = audit_ids.get(audit_name)
        if not audit_id:
            continue
        if conn.execute(
            "SELECT 1 FROM audit_finding WHERE audit_id=%s AND finding_ref=%s",
            (audit_id, ref)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO audit_finding (audit_id, finding_ref, description, severity,"
            " department, found_date, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,'Open','Sample data')",
            (audit_id, ref, desc, severity, dept, _d(found_ago)),
        )
    conn.commit()


def _remove_audits(conn):
    rows = conn.execute(
        "SELECT id FROM audit_schedule WHERE audit_name LIKE %s", (f"{TAG}%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM audit_finding WHERE audit_id=%s", (r["id"],))
    conn.execute("DELETE FROM audit_schedule WHERE audit_name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Bank Accounts + Statements
# ---------------------------------------------------------------------------

BANK_ACCOUNTS = [
    # (account_name, bank_name, account_number, routing_number)
    (f"{TAG}Main Checking",     "First National Bank",  "****4821", "021000089"),
    (f"{TAG}Payroll Checking",  "First National Bank",  "****3310", "021000089"),
    (f"{TAG}Operating Savings", "Midwest Credit Union", "****7750", "281078056"),
    (f"{TAG}Reserve Account",   "Midwest Credit Union", "****9012", "281078056"),
]

STATEMENTS = [
    # (account_name_suffix, stmt_date_ago, beg_bal, end_bal, status, rec_by)
    ("Main Checking",     -60, 284500.00, 312180.00, "Reconciled", "David Kim"),
    ("Main Checking",     -30, 312180.00, 298450.00, "Reconciled", "David Kim"),
    ("Main Checking",       0, 298450.00, 271300.00, "In Progress", ""),
    ("Payroll Checking",  -30, 12000.00,  11800.00,  "Reconciled", "David Kim"),
    ("Operating Savings", -30, 520000.00, 522100.00, "Reconciled", "David Kim"),
]


def _seed_bank(conn):
    bank_ids = {}
    for acct_name, bank_name, acct_num, routing in BANK_ACCOUNTS:
        existing = conn.execute(
            "SELECT id FROM bank_account WHERE account_name=%s", (acct_name,)
        ).fetchone()
        if existing:
            bank_ids[acct_name] = existing["id"]
            continue
        row = conn.execute(
            "INSERT INTO bank_account (account_name, bank_name, account_number, routing_number, is_active, notes)"
            " VALUES (%s,%s,%s,%s,1,'Sample data') RETURNING id",
            (acct_name, bank_name, acct_num, routing),
        ).fetchone()
        bank_ids[acct_name] = row["id"]
    conn.commit()

    for acct_suffix, stmt_ago, beg, end, status, rec_by in STATEMENTS:
        acct_name = f"{TAG}{acct_suffix}"
        acct_id = bank_ids.get(acct_name)
        if not acct_id:
            continue
        stmt_date = _d(stmt_ago)
        if conn.execute(
            "SELECT 1 FROM bank_statement WHERE bank_account_id=%s AND statement_date=%s",
            (acct_id, stmt_date)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO bank_statement"
            " (bank_account_id, statement_date, beginning_balance, ending_balance,"
            "  status, reconciled_by, reconciled_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,'')",
            (acct_id, stmt_date, beg, end, status, rec_by),
        )
    conn.commit()


def _remove_bank(conn):
    rows = conn.execute(
        "SELECT id FROM bank_account WHERE account_name LIKE %s", (f"{TAG}%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM bank_statement WHERE bank_account_id=%s", (r["id"],))
    conn.execute("DELETE FROM bank_account WHERE account_name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Tax Filings + Calendar
# ---------------------------------------------------------------------------

TAX_FILINGS = [
    # (tax_type, jurisdiction, period, amount_due, due_ago, filed_ago, amount_paid, status, reference)
    ("Federal Income", "IRS", f"Q1 {YEAR}", 28500.00, -60, -55, 28500.00, "Paid", f"{TAG}IRS-Q1-{YEAR}"),
    ("Payroll Tax", "IRS", f"Apr {YEAR}", 14200.00, -45, -44, 14200.00, "Paid", f"{TAG}IRS-PR-APR"),
    ("Payroll Tax", "IRS", f"May {YEAR}", 14600.00, -15, -14, 14600.00, "Paid", f"{TAG}IRS-PR-MAY"),
    ("Payroll Tax", "IRS", f"Jun {YEAR}", 14800.00, 15, None, 0.00, "Pending", f"{TAG}IRS-PR-JUN"),
    ("Sales Tax", "State of Ohio", f"Q1 {YEAR}", 8900.00, -60, -58, 8900.00, "Paid", f"{TAG}OH-SALES-Q1"),
    ("Sales Tax", "State of Ohio", f"Q2 {YEAR}", 9400.00, 15, None, 0.00, "Pending", f"{TAG}OH-SALES-Q2"),
    ("Property Tax", "County Assessor", f"{YEAR}", 12300.00, -365, -360, 12300.00, "Paid", f"{TAG}PROP-{YEAR}"),
    ("Federal Income", "IRS", f"Q2 {YEAR}", 31200.00, 15, None, 0.00, "Pending", f"{TAG}IRS-Q2-{YEAR}"),
]

TAX_CALENDAR = [
    # (tax_type, description, due_offset, status)
    ("Payroll Tax",    "IRS Form 941 — Q2 Payroll Taxes Due",         15,  "Pending"),
    ("Federal Income", "IRS Estimated Tax Payment Q2",                15,  "Pending"),
    ("Sales Tax",      "Ohio Sales Tax Q2 Return",                    15,  "Pending"),
    ("Payroll Tax",    "IRS Form 941 — Q3 Payroll Taxes Due",        105,  "Pending"),
    ("Federal Income", "IRS Estimated Tax Payment Q3",               105,  "Pending"),
    ("Federal Income", "Corporate Tax Return Extension Deadline",     290, "Pending"),
]


def _seed_taxes(conn):
    for ttype, jurisdiction, period, amount_due, due_ago, filed_ago, paid, status, ref in TAX_FILINGS:
        if conn.execute("SELECT 1 FROM tax_filing WHERE reference=%s", (ref,)).fetchone():
            continue
        filed = _d(filed_ago) if filed_ago is not None else None
        conn.execute(
            "INSERT INTO tax_filing"
            " (tax_type, jurisdiction, period, amount_due, amount_paid,"
            "  filed_date, due_date, status, reference, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (ttype, jurisdiction, period, amount_due, paid, filed,
             _d(due_ago), status, ref),
        )
    conn.commit()

    for ttype, desc, due_off, status in TAX_CALENDAR:
        if conn.execute(
            "SELECT 1 FROM tax_calendar WHERE description=%s", (desc,)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO tax_calendar (tax_type, description, due_date, status, notes)"
            " VALUES (%s,%s,%s,%s,'Sample data')",
            (ttype, desc, _d(due_off), status),
        )
    conn.commit()


def _remove_taxes(conn):
    conn.execute("DELETE FROM tax_filing WHERE reference LIKE %s", (f"{TAG}%",))
    conn.execute("DELETE FROM tax_calendar WHERE notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_budgets(conn)
    _seed_audits(conn)
    _seed_bank(conn)
    _seed_taxes(conn)
    print("Finance sample data seeded.")


def remove(conn):
    _remove_taxes(conn)
    _remove_bank(conn)
    _remove_audits(conn)
    _remove_budgets(conn)
    print("Finance sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Finance sample data")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--reset",  action="store_true", help="Remove then re-add")
    grp.add_argument("--remove", action="store_true", help="Remove only")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.remove:
            remove(conn)
        elif args.reset:
            remove(conn)
            seed(conn)
        else:
            seed(conn)
    finally:
        conn.close()
