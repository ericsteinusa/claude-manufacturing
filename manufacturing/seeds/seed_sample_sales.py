"""seed_sample_sales.py — sample Sales data.

Covers: quotes, targets, leads, contracts, forecasts, territories,
commission plans, and commissions.  All rows are tagged so they can be
removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_sales            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_sales --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_sales --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-SALES-"
TODAY = date.today()
YEAR = TODAY.year


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_quote (
            id SERIAL PRIMARY KEY,
            customer TEXT NOT NULL,
            description TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            owner TEXT DEFAULT '',
            quote_date TEXT DEFAULT '',
            valid_until TEXT DEFAULT '',
            status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_target (
            id SERIAL PRIMARY KEY,
            rep TEXT NOT NULL,
            period TEXT DEFAULT '',
            target REAL DEFAULT 0,
            actual REAL DEFAULT 0,
            region TEXT DEFAULT '',
            status TEXT DEFAULT 'On Track',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_lead (
            id SERIAL PRIMARY KEY,
            company TEXT NOT NULL,
            contact TEXT DEFAULT '',
            source TEXT DEFAULT '',
            status TEXT DEFAULT 'New',
            priority TEXT DEFAULT 'Medium',
            estimated_value REAL DEFAULT 0,
            owner TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_contract (
            id SERIAL PRIMARY KEY,
            customer TEXT NOT NULL,
            title TEXT DEFAULT '',
            value REAL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            renewal_date TEXT,
            status TEXT DEFAULT 'Draft',
            owner TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_forecast (
            id SERIAL PRIMARY KEY,
            rep TEXT DEFAULT '',
            period TEXT DEFAULT '',
            fiscal_year INTEGER,
            product_line TEXT DEFAULT '',
            expected_value REAL DEFAULT 0,
            probability INTEGER DEFAULT 0,
            weighted_value REAL DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_territory (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT DEFAULT '',
            assigned_rep TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_commission_plan (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            plan_type TEXT DEFAULT 'Flat Rate',
            rate REAL DEFAULT 0,
            description TEXT DEFAULT '',
            active BOOLEAN DEFAULT TRUE,
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_commission (
            id SERIAL PRIMARY KEY,
            rep TEXT NOT NULL,
            period TEXT DEFAULT '',
            plan_id INTEGER,
            sale_amount REAL DEFAULT 0,
            commission REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    # Older deployments created this table via create_missing_tables.py's
    # pre-plan_id schema (sales_amount/rate, no plan_id) — self-heal it.
    conn.execute(
        "ALTER TABLE sales_commission ADD COLUMN IF NOT EXISTS plan_id INTEGER")
    conn.execute(
        "ALTER TABLE sales_commission ADD COLUMN IF NOT EXISTS sale_amount REAL DEFAULT 0")
    conn.execute(
        "ALTER TABLE sales_commission ADD COLUMN IF NOT EXISTS created_date TEXT DEFAULT ''")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_coaching_note (
            id SERIAL PRIMARY KEY,
            rep TEXT NOT NULL,
            subject TEXT DEFAULT '',
            note TEXT DEFAULT '',
            status TEXT DEFAULT 'Open',
            coach TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_perf_review (
            id SERIAL PRIMARY KEY,
            rep TEXT NOT NULL,
            review_date TEXT DEFAULT '',
            period TEXT DEFAULT '',
            rating TEXT DEFAULT '',
            strengths TEXT DEFAULT '',
            improvements TEXT DEFAULT '',
            goals TEXT DEFAULT '',
            status TEXT DEFAULT 'Scheduled',
            reviewer TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    # Backfill created_by on pre-existing tables that may lack it
    for tbl in ("sales_quote", "sales_target", "sales_commission"):
        conn.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.commit()


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

QUOTES = [
    # (customer, description, amount, owner, date_ago, valid_days, status)
    # valid_days is a DURATION added to date_ago (valid_until = _d(date_ago +
    # valid_days)), not an absolute day count from today -- for an "Expired"/
    # "Lost" quote that lapsed N days ago, valid_days must be (N days ago) -
    # date_ago, not simply -N.
    ("Apex Manufacturing Inc.", "Annual valve assembly supply — 500 units",
     48500.00, "Karen Walsh", -10, 30, "Sent"),
    ("Bridgewater Tools LLC", "Custom fixture set for new product line",
     12750.00, "Tom Deluca", -5, 20, "Draft"),
    ("Castillo Industries", "Q3 bearing order — standard + heavy-duty mix",
     31200.00, "Karen Walsh", -20, 10, "Won"),
    ("Delta Components Co.", "Replacement shaft collar batch — 200 pcs",
     8400.00, "Tom Deluca", -45, 30, "Expired"),
    ("Evergreen Systems", "Retrofit kit supply — 12 machine installations",
     67000.00, "Karen Walsh", -2, 45, "Draft"),
    ("Falcon Precision Parts", "Emergency PO — hydraulic fittings",
     5900.00, "Tom Deluca", -30, 10, "Lost"),
    ("Greenfield Assembly", "Recurring Q4 parts kit — blanket order",
     22300.00, "Karen Walsh", -7, 60, "Sent"),
    ("Harbor Engineering", "New customer trial order — 50 units",
     4100.00, "Tom Deluca", -3, 30, "Draft"),
]


def _seed_quotes(conn):
    for customer, desc, amount, owner, date_ago, valid_days, status in QUOTES:
        if conn.execute(
            f"SELECT 1 FROM sales_quote WHERE customer=%s AND description=%s AND created_by='{TAG}'",
            (customer, desc)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO sales_quote"
            " (customer, description, amount, owner, quote_date, valid_until, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (customer, desc, amount, owner, _d(date_ago),
             _d(date_ago + valid_days), status),
        )
    conn.commit()


def _remove_quotes(conn):
    conn.execute(f"DELETE FROM sales_quote WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

TARGETS = [
    # (rep, period, target, actual, region, status)
    ("Karen Walsh",  f"Q1-{YEAR}", 180000, 192400, "Northeast", "Achieved"),
    ("Tom Deluca",   f"Q1-{YEAR}", 150000, 138200, "Southeast", "Behind"),
    ("Jenna Park",   f"Q1-{YEAR}", 165000, 171600, "Midwest",   "Achieved"),
    ("Ryan Torres",  f"Q1-{YEAR}", 130000, 125800, "West",      "Behind"),
    ("Karen Walsh",  f"Q2-{YEAR}", 195000, 148000, "Northeast", "Behind"),
    ("Tom Deluca",   f"Q2-{YEAR}", 160000, 162300, "Southeast", "On Track"),
    ("Jenna Park",   f"Q2-{YEAR}", 175000, 180100, "Midwest",   "Achieved"),
    ("Ryan Torres",  f"Q2-{YEAR}", 140000, 141500, "West",      "On Track"),
]


def _seed_targets(conn):
    for rep, period, target, actual, region, status in TARGETS:
        if conn.execute(
            f"SELECT 1 FROM sales_target WHERE rep=%s AND period=%s AND created_by='{TAG}'",
            (rep, period)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO sales_target (rep, period, target, actual, region, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (rep, period, target, actual, region, status),
        )
    conn.commit()


def _remove_targets(conn):
    conn.execute(f"DELETE FROM sales_target WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

LEADS = [
    # (company, contact, source, status, priority, est_value, owner)
    ("Summit Fabricators",    "Dan Cho",        "Trade Show",    "Qualified",  "High",   55000, "Karen Walsh"),
    ("Pacific Rim Parts",     "Aida Santos",    "Referral",      "Contacted",  "Medium", 28000, "Tom Deluca"),
    ("Northwest Tooling",     "Greg Burns",     "Cold Call",     "New",        "Low",    12000, "Tom Deluca"),
    ("Inova Systems",         "Chloe Kim",      "Website",       "Proposal",   "High",   94000, "Karen Walsh"),
    ("Precision Mold Inc.",   "Frank Obi",      "Email Campaign","Contacted",  "Medium", 31000, "Jenna Park"),
    ("Highline Assembly",     "Tara Mendez",    "Partner",       "Qualified",  "High",   72000, "Karen Walsh"),
    ("Central Machine Co.",   "Brian Lau",      "Cold Call",     "New",        "Low",     8500, "Ryan Torres"),
    ("BlueStar Engineering",  "Nina Sharma",    "Referral",      "Won",        "High",  118000, "Karen Walsh"),
    ("Allied Components",     "Paul Estes",     "Trade Show",    "Lost",       "Medium", 45000, "Tom Deluca"),
    ("Redstone Industries",   "Laura Chen",     "Website",       "Nurturing",  "Medium", 37500, "Ryan Torres"),
]


def _seed_leads(conn):
    for company, contact, source, status, priority, est_value, owner in LEADS:
        if conn.execute(
            f"SELECT 1 FROM sales_lead WHERE company=%s AND contact=%s AND created_by='{TAG}'",
            (company, contact)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO sales_lead"
            " (company, contact, source, status, priority, estimated_value,"
            "  owner, notes, created_by, created_date)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}',%s)",
            (company, contact, source, status, priority, est_value, owner,
             TODAY.isoformat()),
        )
    conn.commit()


def _remove_leads(conn):
    conn.execute(f"DELETE FROM sales_lead WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

CONTRACTS = [
    # (customer, title, value, start_ago, end_days, status, owner)
    # end_days is a DURATION added to start_ago, not an absolute day count
    # from today -- see the QUOTES comment above for why a negative value
    # meaning "ended N days ago" must be (N days ago) - start_ago.
    ("Apex Manufacturing Inc.", "Annual Supply Agreement — Valve Assemblies",
     96000, -365, 0, "Active", "Karen Walsh"),
    ("Castillo Industries", "Preferred Vendor Agreement",
     60000, -180, 185, "Active", "Karen Walsh"),
    ("Delta Components Co.", "One-Time Supply Contract Q4",
     16800, -90, 60, "Expired", "Tom Deluca"),
    ("Greenfield Assembly", "Blanket Order Agreement — Q3/Q4",
     44600, -60, 120, "Active", "Karen Walsh"),
    ("BlueStar Engineering", "Partnership Supply Contract",
     236000, -30, 335, "Active", "Karen Walsh"),
    ("Falcon Precision Parts", "Emergency Supply Agreement",
     11800, -120, 30, "Expired", "Tom Deluca"),
]


def _seed_contracts(conn):
    for customer, title, value, start_ago, end_off, status, owner in CONTRACTS:
        if conn.execute(
            f"SELECT 1 FROM sales_contract WHERE customer=%s AND title=%s AND created_by='{TAG}'",
            (customer, title)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO sales_contract"
            " (customer, title, value, start_date, end_date, renewal_date,"
            "  status, owner, notes, created_by, created_date)"
            f" VALUES (%s,%s,%s,%s,%s,NULL,%s,%s,'Sample data','{TAG}',%s)",
            (customer, title, value, _d(start_ago), _d(start_ago + end_off),
             status, owner, TODAY.isoformat()),
        )
    conn.commit()


def _remove_contracts(conn):
    conn.execute(f"DELETE FROM sales_contract WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------

FORECASTS = [
    # (rep, period, product_line, expected, probability, status)
    ("Karen Walsh",  "Q3",      "Valve Assemblies",   210000, 85, "Submitted"),
    ("Karen Walsh",  "Q3",      "Retrofit Kits",       78000, 70, "Submitted"),
    ("Tom Deluca",   "Q3",      "Shaft Collars",       95000, 60, "Draft"),
    ("Jenna Park",   "Q3",      "Bearing Products",   145000, 80, "Approved"),
    ("Ryan Torres",  "Q3",      "Custom Fixtures",     62000, 55, "Draft"),
    ("Karen Walsh",  "Q4",      "Valve Assemblies",   225000, 75, "Draft"),
    ("Jenna Park",   "Annual",  "All Product Lines",  680000, 72, "Approved"),
]


def _seed_forecasts(conn):
    for rep, period, product_line, expected, probability, status in FORECASTS:
        if conn.execute(
            f"SELECT 1 FROM sales_forecast WHERE rep=%s AND period=%s AND product_line=%s AND created_by='{TAG}'",
            (rep, period, product_line)
        ).fetchone():
            continue
        weighted = expected * probability / 100
        conn.execute(
            "INSERT INTO sales_forecast"
            " (rep, period, fiscal_year, product_line, expected_value,"
            "  probability, weighted_value, status, notes, created_by, created_date)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}',%s)",
            (rep, period, YEAR, product_line, expected, probability, weighted,
             status, TODAY.isoformat()),
        )
    conn.commit()


def _remove_forecasts(conn):
    conn.execute(f"DELETE FROM sales_forecast WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Territories
# ---------------------------------------------------------------------------

TERRITORIES = [
    # (name, region, assigned_rep, status)
    ("New England",     "Northeast", "Karen Walsh",  "Active"),
    ("Mid-Atlantic",    "Northeast", "Jenna Park",   "Active"),
    ("Southeast",       "Southeast", "Tom Deluca",   "Active"),
    ("Gulf Coast",      "Southeast", "",             "Under Review"),
    ("Great Lakes",     "Midwest",   "Jenna Park",   "Active"),
    ("Plains",          "Midwest",   "",             "Inactive"),
    ("Pacific Coast",   "West",      "Ryan Torres",  "Active"),
    ("Mountain West",   "West",      "Ryan Torres",  "Active"),
]


def _seed_territories(conn):
    for name, region, rep, status in TERRITORIES:
        if conn.execute(
            f"SELECT 1 FROM sales_territory WHERE name=%s AND created_by='{TAG}'",
            (name,)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO sales_territory"
            " (name, region, assigned_rep, status, notes, created_by, created_date)"
            f" VALUES (%s,%s,%s,%s,'Sample data','{TAG}',%s)",
            (name, region, rep, status, TODAY.isoformat()),
        )
    conn.commit()


def _remove_territories(conn):
    conn.execute(f"DELETE FROM sales_territory WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Commission Plans + Commissions
# ---------------------------------------------------------------------------

PLANS = [
    # (name, plan_type, rate, description)
    ("Standard Rep Plan",       "Flat Rate",   0.05, "5% flat commission on all closed sales"),
    ("Senior Rep Plan",         "Flat Rate",   0.07, "7% flat commission — for reps exceeding 150k/quarter"),
    ("Tiered Quota Plan",       "Tiered",      0.06, "6% base; 8% above 125% quota attainment"),
    ("Quota-Based Bonus",       "Quota-Based", 0.04, "4% + bonus on reaching 100%+ of quarterly quota"),
]

COMMISSIONS = [
    # (rep, period, plan_name, sale_amount, status)
    ("Karen Walsh",  f"Q1-{YEAR}", "Senior Rep Plan",   192400, "Paid"),
    ("Tom Deluca",   f"Q1-{YEAR}", "Standard Rep Plan", 138200, "Paid"),
    ("Jenna Park",   f"Q1-{YEAR}", "Standard Rep Plan", 171600, "Paid"),
    ("Ryan Torres",  f"Q1-{YEAR}", "Standard Rep Plan", 125800, "Paid"),
    ("Karen Walsh",  f"Q2-{YEAR}", "Senior Rep Plan",   148000, "Approved"),
    ("Tom Deluca",   f"Q2-{YEAR}", "Standard Rep Plan", 162300, "Approved"),
    ("Jenna Park",   f"Q2-{YEAR}", "Standard Rep Plan", 180100, "Approved"),
    ("Ryan Torres",  f"Q2-{YEAR}", "Standard Rep Plan", 141500, "Pending"),
]


def _seed_commissions(conn):
    plan_ids = {}
    plan_rates = {}
    for name, plan_type, rate, desc in PLANS:
        existing = conn.execute(
            "SELECT id, rate FROM sales_commission_plan WHERE name=%s", (name,)
        ).fetchone()
        if existing:
            plan_ids[name] = existing["id"]
            plan_rates[name] = existing["rate"]
            continue
        row = conn.execute(
            "INSERT INTO sales_commission_plan (name, plan_type, rate, description, active, created_by, created_date)"
            f" VALUES (%s,%s,%s,%s,TRUE,'{TAG}',%s) RETURNING id",
            (name, plan_type, rate, desc, TODAY.isoformat()),
        ).fetchone()
        plan_ids[name] = row["id"]
        plan_rates[name] = rate
    conn.commit()

    for rep, period, plan_name, sale_amount, status in COMMISSIONS:
        if conn.execute(
            f"SELECT 1 FROM sales_commission WHERE rep=%s AND period=%s AND created_by='{TAG}'",
            (rep, period)
        ).fetchone():
            continue
        plan_id = plan_ids.get(plan_name)
        rate = plan_rates.get(plan_name, 0.05)
        commission = round(sale_amount * rate, 2)
        conn.execute(
            "INSERT INTO sales_commission"
            " (rep, period, plan_id, sale_amount, commission, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (rep, period, plan_id, sale_amount, commission, status),
        )
    conn.commit()


def _remove_commissions(conn):
    conn.execute(f"DELETE FROM sales_commission WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.execute(f"DELETE FROM sales_commission_plan WHERE created_by='{TAG}'")
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_quotes(conn)
    _seed_targets(conn)
    _seed_leads(conn)
    _seed_contracts(conn)
    _seed_forecasts(conn)
    _seed_territories(conn)
    _seed_commissions(conn)
    print("Sales sample data seeded.")


def remove(conn):
    _remove_commissions(conn)
    _remove_territories(conn)
    _remove_forecasts(conn)
    _remove_contracts(conn)
    _remove_leads(conn)
    _remove_targets(conn)
    _remove_quotes(conn)
    print("Sales sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Sales sample data")
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


