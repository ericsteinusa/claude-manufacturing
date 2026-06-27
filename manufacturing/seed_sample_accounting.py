"""seed_sample_accounting.py — sample Accounting data.

Covers: Chart of Accounts (GL accounts), AP invoices + payments,
AR invoices + payments, and GL journal entries.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seed_sample_accounting            # add (idempotent)
    python -m manufacturing.seed_sample_accounting --reset     # remove + re-add
    python -m manufacturing.seed_sample_accounting --remove    # remove only
"""

import argparse
from datetime import date, datetime, timedelta

from .db_pg import get_db_connection

TAG = "SMPL-ACCT-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_account (
            id SERIAL PRIMARY KEY,
            account_number TEXT NOT NULL UNIQUE,
            account_name TEXT NOT NULL,
            account_type TEXT DEFAULT 'Expense',
            account_sub TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ap_invoice (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER,
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date TEXT DEFAULT '',
            due_date TEXT,
            amount REAL DEFAULT 0,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ap_payment (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL,
            payment_date TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'Check',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ar_invoice (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date TEXT DEFAULT '',
            due_date TEXT,
            amount REAL DEFAULT 0,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ar_payment (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL,
            payment_date TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'Check',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_journal (
            id SERIAL PRIMARY KEY,
            journal_date TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            description TEXT DEFAULT '',
            posted INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_journal_line (
            id SERIAL PRIMARY KEY,
            journal_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            memo TEXT DEFAULT ''
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------

ACCOUNTS = [
    # (account_number, account_name, account_type, account_sub)
    # Assets
    ("1000", "Checking Account",           "Asset",   "Current Asset"),
    ("1010", "Savings Account",            "Asset",   "Current Asset"),
    ("1100", "Accounts Receivable",        "Asset",   "Current Asset"),
    ("1200", "Inventory",                  "Asset",   "Current Asset"),
    ("1500", "Machinery & Equipment",      "Asset",   "Fixed Asset"),
    ("1510", "Accum. Depr. — Equipment",   "Asset",   "Fixed Asset"),
    # Liabilities
    ("2000", "Accounts Payable",           "Liability","Current Liability"),
    ("2100", "Accrued Payroll",            "Liability","Current Liability"),
    ("2200", "Sales Tax Payable",          "Liability","Current Liability"),
    ("2500", "Long-Term Debt",             "Liability","Long-Term Liability"),
    # Equity
    ("3000", "Common Stock",              "Equity",  "Equity"),
    ("3100", "Retained Earnings",         "Equity",  "Equity"),
    # Revenue
    ("4000", "Product Sales Revenue",     "Revenue", "Revenue"),
    ("4100", "Service Revenue",           "Revenue", "Revenue"),
    # COGS
    ("5000", "Direct Materials",          "COGS",    "COGS"),
    ("5100", "Direct Labor",              "COGS",    "COGS"),
    ("5200", "Manufacturing Overhead",    "COGS",    "COGS"),
    # Expenses
    ("6000", "Salaries & Wages",          "Expense", "Operating"),
    ("6100", "Rent Expense",              "Expense", "Operating"),
    ("6200", "Utilities",                 "Expense", "Operating"),
    ("6300", "Office Supplies",           "Expense", "Operating"),
    ("6400", "Depreciation Expense",      "Expense", "Operating"),
    ("6500", "Professional Services",     "Expense", "Operating"),
    ("6600", "Marketing & Advertising",   "Expense", "Operating"),
    ("6700", "Insurance Expense",         "Expense", "Operating"),
    ("6800", "Maintenance & Repairs",     "Expense", "Operating"),
]


def _seed_accounts(conn) -> dict:
    """Insert accounts and return {account_number: id} map."""
    ids = {}
    for acct_num, acct_name, acct_type, acct_sub in ACCOUNTS:
        existing = conn.execute(
            "SELECT id FROM gl_account WHERE account_number=%s", (acct_num,)
        ).fetchone()
        if existing:
            ids[acct_num] = existing["id"]
            continue
        row = conn.execute(
            "INSERT INTO gl_account (account_number, account_name, account_type, account_sub, is_active, notes)"
            " VALUES (%s,%s,%s,%s,1,'Sample data') RETURNING id",
            (acct_num, acct_name, acct_type, acct_sub),
        ).fetchone()
        ids[acct_num] = row["id"]
    conn.commit()
    return ids


def _remove_accounts(conn):
    conn.execute("DELETE FROM gl_account WHERE notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# AP Invoices + Payments
# ---------------------------------------------------------------------------

AP_INVOICES = [
    # (inv_num, vendor_desc, inv_ago, due_offset, amount, description, status)
    (f"{TAG}AP-2026-001", "Metal Fab Co.",        -25, 5,  12400.00, "Steel sheet order — Invoice MFC-4412",          "open"),
    (f"{TAG}AP-2026-002", "Allied Polymers",      -18, 12, 5850.00,  "ABS resin resupply — Invoice AP-8821",          "open"),
    (f"{TAG}AP-2026-003", "FastPro Supply",       -30, 0,  3200.00,  "Fastener batch — Invoice FPS-1199",             "overdue"),
    (f"{TAG}AP-2026-004", "Valley Hydraulics",    -40, -10,8900.00,  "Hydraulic hose order — Invoice VH-5532",        "paid"),
    (f"{TAG}AP-2026-005", "PaintTech Solutions",  -15, 15, 2750.00,  "Epoxy primer supply — Invoice PT-0034",         "open"),
    (f"{TAG}AP-2026-006", "Acme Electronics",     -50, -20,16500.00, "PCB assemblies Q1 — Invoice AE-2290",           "paid"),
    (f"{TAG}AP-2026-007", "New Era Bearings",     -8,  22, 4100.00,  "Bearing restock — Invoice NEB-0778",            "open"),
    (f"{TAG}AP-2026-008", "Apex Consulting LLC",  -60, -30,9500.00,  "Engineering consulting Q1 — Invoice AC-1100",   "paid"),
]

AP_PAYMENTS = [
    # (inv_num_suffix, pay_ago, amount, method, reference)
    ("004", -8,  8900.00, "ACH",   "ACH-20260618-VH"),
    ("006", -18, 16500.00,"Wire",  "WIRE-20260608-AE"),
    ("008", -28, 9500.00, "Check", "CHK-10042"),
]


def _seed_ap(conn):
    inv_ids = {}
    for inv_num, _, inv_ago, due_off, amount, desc, status in AP_INVOICES:
        existing = conn.execute("SELECT id FROM ap_invoice WHERE invoice_number=%s", (inv_num,)).fetchone()
        if existing:
            inv_ids[inv_num.split("-")[-1]] = existing["id"]
            continue
        row = conn.execute(
            "INSERT INTO ap_invoice (vendor_id, invoice_number, invoice_date, due_date,"
            " amount, description, status, created_by)"
            " VALUES (NULL,%s,%s,%s,%s,%s,%s,'seed') RETURNING id",
            (inv_num, _d(inv_ago), _d(inv_ago + due_off), amount, desc, status),
        ).fetchone()
        inv_ids[inv_num.split("-")[-1]] = row["id"]
    conn.commit()

    for suffix, pay_ago, amount, method, ref in AP_PAYMENTS:
        inv_id = inv_ids.get(suffix)
        if not inv_id:
            continue
        if conn.execute("SELECT 1 FROM ap_payment WHERE invoice_id=%s AND reference=%s",
                        (inv_id, ref)).fetchone():
            continue
        conn.execute(
            "INSERT INTO ap_payment (invoice_id, payment_date, amount, payment_method, reference, notes)"
            " VALUES (%s,%s,%s,%s,%s,'Sample data')",
            (inv_id, _d(pay_ago), amount, method, ref),
        )
    conn.commit()


def _remove_ap(conn):
    rows = conn.execute(
        "SELECT id FROM ap_invoice WHERE invoice_number LIKE %s", (f"{TAG}AP-%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM ap_payment WHERE invoice_id=%s", (r["id"],))
    conn.execute("DELETE FROM ap_invoice WHERE invoice_number LIKE %s", (f"{TAG}AP-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# AR Invoices + Payments
# ---------------------------------------------------------------------------

AR_INVOICES = [
    # (inv_num, customer_name, inv_ago, due_offset, amount, description, status)
    (f"{TAG}AR-2026-001", "Apex Manufacturing Inc.", -20, 10, 48500.00, "Valve assembly order — SO-2026-0142",     "open"),
    (f"{TAG}AR-2026-002", "Castillo Industries",     -35, -5, 31200.00, "Bearing products Q2 — SO-2026-0128",      "overdue"),
    (f"{TAG}AR-2026-003", "Greenfield Assembly",     -50, -20,22300.00, "Parts kit blanket order — SO-2026-0115",  "paid"),
    (f"{TAG}AR-2026-004", "BlueStar Engineering",    -10, 20, 118000.00,"Partnership supply contract — SO-2026-0155","partial"),
    (f"{TAG}AR-2026-005", "Harbor Engineering",      -5,  25, 4100.00,  "Trial order — SO-2026-0160",              "open"),
    (f"{TAG}AR-2026-006", "Delta Components Co.",    -45, -15,8400.00,  "Shaft collar batch — SO-2026-0108",       "paid"),
    (f"{TAG}AR-2026-007", "Evergreen Systems",       -3,  27, 67000.00, "Retrofit kit supply — SO-2026-0162",      "open"),
]

AR_PAYMENTS = [
    # (inv_num_suffix, pay_ago, amount, method, reference)
    ("003", -18, 22300.00, "ACH",   "ACH-20260608-GF"),
    ("006", -12, 8400.00,  "Check", "CHK-20260614-DC"),
    ("004", -3,  50000.00, "Wire",  "WIRE-20260623-BE"),  # partial
]


def _seed_ar(conn):
    inv_ids = {}
    # customer_id is NOT NULL — use the first customer in the table as a placeholder
    cust_row = conn.execute("SELECT id FROM customer LIMIT 1").fetchone()
    cust_id = cust_row["id"] if cust_row else 1
    for inv_num, _, inv_ago, due_off, amount, desc, status in AR_INVOICES:
        existing = conn.execute("SELECT id FROM ar_invoice WHERE invoice_number=%s", (inv_num,)).fetchone()
        if existing:
            inv_ids[inv_num.split("-")[-1]] = existing["id"]
            continue
        row = conn.execute(
            "INSERT INTO ar_invoice (customer_id, invoice_number, invoice_date, due_date,"
            " amount, description, status, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'seed') RETURNING id",
            (cust_id, inv_num, _d(inv_ago), _d(inv_ago + due_off), amount, desc, status),
        ).fetchone()
        inv_ids[inv_num.split("-")[-1]] = row["id"]
    conn.commit()

    for suffix, pay_ago, amount, method, ref in AR_PAYMENTS:
        inv_id = inv_ids.get(suffix)
        if not inv_id:
            continue
        if conn.execute("SELECT 1 FROM ar_payment WHERE invoice_id=%s AND reference=%s",
                        (inv_id, ref)).fetchone():
            continue
        conn.execute(
            "INSERT INTO ar_payment (invoice_id, payment_date, amount, payment_method, reference, notes)"
            " VALUES (%s,%s,%s,%s,%s,'Sample data')",
            (inv_id, _d(pay_ago), amount, method, ref),
        )
    conn.commit()


def _remove_ar(conn):
    rows = conn.execute(
        "SELECT id FROM ar_invoice WHERE invoice_number LIKE %s", (f"{TAG}AR-%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM ar_payment WHERE invoice_id=%s", (r["id"],))
    conn.execute("DELETE FROM ar_invoice WHERE invoice_number LIKE %s", (f"{TAG}AR-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# GL Journal Entries
# ---------------------------------------------------------------------------

def _seed_journals(conn, acct_ids: dict):
    """Insert sample posted journal entries that reference the seeded GL accounts."""
    JOURNALS = [
        # (ref, description, date_ago, lines: [(acct_num, debit, credit, memo)])
        (f"{TAG}JE-2026-001", "Record product sales — May",  -25, [
            ("4000", 0,       48500.00, "Product sales revenue"),
            ("1100", 48500.00, 0,       "AR — Apex Manufacturing"),
        ]),
        (f"{TAG}JE-2026-002", "Record AP — Metal Fab invoice", -25, [
            ("5000", 12400.00, 0,       "Steel sheet materials"),
            ("2000", 0,       12400.00, "AP — Metal Fab Co."),
        ]),
        (f"{TAG}JE-2026-003", "Monthly rent expense — June",   -1, [
            ("6100", 8500.00, 0,        "Office & plant rent"),
            ("1000", 0,       8500.00,  "Checking account"),
        ]),
        (f"{TAG}JE-2026-004", "Payroll — bi-weekly run",       -7, [
            ("6000", 62400.00, 0,       "Salaries & wages"),
            ("2100", 0,       62400.00, "Accrued payroll"),
        ]),
        (f"{TAG}JE-2026-005", "Payroll funding — ACH",         -5, [
            ("2100", 62400.00, 0,       "Clear accrued payroll"),
            ("1000", 0,       62400.00, "Checking account"),
        ]),
        (f"{TAG}JE-2026-006", "Monthly depreciation",         -30, [
            ("6400", 3800.00, 0,        "Depreciation expense"),
            ("1510", 0,       3800.00,  "Accum depr — equipment"),
        ]),
        (f"{TAG}JE-2026-007", "Insurance premium — Q2",       -60, [
            ("6700", 4200.00, 0,        "Insurance expense"),
            ("1000", 0,       4200.00,  "Checking account"),
        ]),
        (f"{TAG}JE-2026-008", "AR receipt — Greenfield",      -18, [
            ("1000", 22300.00, 0,       "Cash receipt"),
            ("1100", 0,       22300.00, "AR — Greenfield Assembly"),
        ]),
    ]

    for ref, desc, date_ago, lines in JOURNALS:
        if conn.execute("SELECT 1 FROM gl_journal WHERE reference=%s", (ref,)).fetchone():
            continue
        # Verify all accounts exist
        acct_line_ids = []
        valid = True
        for acct_num, dr, cr, memo in lines:
            acct_id = acct_ids.get(acct_num)
            if not acct_id:
                valid = False
                break
            acct_line_ids.append((acct_id, dr, cr, memo))
        if not valid:
            continue

        row = conn.execute(
            "INSERT INTO gl_journal (journal_date, reference, description, posted, created_by, created_at)"
            " VALUES (%s,%s,%s,1,'seed',%s) RETURNING id",
            (_d(date_ago), ref, desc, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ).fetchone()
        journal_id = row["id"]
        for acct_id, dr, cr, memo in acct_line_ids:
            conn.execute(
                "INSERT INTO gl_journal_line (journal_id, account_id, debit, credit, memo)"
                " VALUES (%s,%s,%s,%s,%s)",
                (journal_id, acct_id, dr, cr, memo),
            )
    conn.commit()


def _remove_journals(conn):
    rows = conn.execute(
        "SELECT id FROM gl_journal WHERE reference LIKE %s", (f"{TAG}JE-%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM gl_journal_line WHERE journal_id=%s", (r["id"],))
    conn.execute("DELETE FROM gl_journal WHERE reference LIKE %s", (f"{TAG}JE-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    acct_ids = _seed_accounts(conn)
    _seed_ap(conn)
    _seed_ar(conn)
    _seed_journals(conn, acct_ids)
    print("Accounting sample data seeded.")


def remove(conn):
    _remove_journals(conn)
    _remove_ar(conn)
    _remove_ap(conn)
    _remove_accounts(conn)
    print("Accounting sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Accounting sample data")
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
