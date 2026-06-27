"""seed_sample_legal.py — sample Legal data.

Covers: contracts, compliance items, and litigation cases.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seed_sample_legal            # add (idempotent)
    python -m manufacturing.seed_sample_legal --reset     # remove + re-add
    python -m manufacturing.seed_sample_legal --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from .db_pg import get_db_connection

TAG = "SMPL-LEGAL-"
TODAY = date.today()
YEAR = TODAY.year


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS legal_contract (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            counterparty TEXT DEFAULT '',
            contract_type TEXT DEFAULT '',
            value REAL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            owner TEXT DEFAULT '',
            status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS legal_compliance (
            id SERIAL PRIMARY KEY,
            requirement TEXT NOT NULL,
            regulation TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            due_date TEXT,
            completed_date TEXT,
            status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS legal_litigation (
            id SERIAL PRIMARY KEY,
            case_name TEXT NOT NULL,
            opposing_party TEXT DEFAULT '',
            court TEXT DEFAULT '',
            case_type TEXT DEFAULT '',
            filed_date TEXT,
            status TEXT DEFAULT 'Open',
            outcome TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

CONTRACTS = [
    # (title, counterparty, contract_type, value, start_ago, end_days, status, owner)
    (f"{TAG}Apex Manufacturing — Annual Supply Agreement",     "Apex Manufacturing Inc.",  "Service Agreement", 96000,   -365, 0,    "Active",   "Sandra Pierce"),
    (f"{TAG}Office Lease — Main Plant",                        "Realty Group LLC",         "Lease",             204000,  -730, 365,  "Active",   "Sandra Pierce"),
    (f"{TAG}Software License — ERP System",                    "TechCorp ERP",             "Licensing",         28500,   -365, 0,    "Active",   "Janet Flores"),
    (f"{TAG}NDA — Summit Fabricators",                         "Summit Fabricators",       "NDA",               0,       -30,  335,  "Active",   "Sandra Pierce"),
    (f"{TAG}Vendor Agreement — Metal Fab Co.",                  "Metal Fab Co.",           "Vendor",            0,       -180, 185,  "Active",   "Janet Flores"),
    (f"{TAG}NDA — Pacific Rim Parts",                          "Pacific Rim Parts",        "NDA",               0,       -10,  355,  "Active",   "Sandra Pierce"),
    (f"{TAG}Employment Contract — Engineering Director",       "Raj Patel",                "Employment",        145000,  -365, 0,    "Active",   "Janet Flores"),
    (f"{TAG}IT Services Agreement — TechSupport Co.",          "TechSupport Co.",          "Service Agreement", 18000,   -90,  -30,  "Expired",  "Janet Flores"),
    (f"{TAG}Partnership Agreement — Allied Components",        "Allied Components",        "Partnership",       55000,   -60,  305,  "Active",   "Sandra Pierce"),
    (f"{TAG}Consulting Services — Apex Consulting",            "Apex Consulting LLC",      "Service Agreement", 38000,   -120, -30,  "Expired",  "Sandra Pierce"),
    (f"{TAG}Renewal — ERP Software License",                   "TechCorp ERP",             "Licensing",         30000,   -1,   364,  "Draft",    "Janet Flores"),
    (f"{TAG}Confidentiality — Inova Systems",                  "Inova Systems",            "NDA",               0,       -5,   360,  "Active",   "Sandra Pierce"),
]


def _seed_contracts(conn):
    for title, counterparty, ctype, value, start_ago, end_off, status, owner in CONTRACTS:
        if conn.execute("SELECT 1 FROM legal_contract WHERE title=%s", (title,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO legal_contract"
            " (title, counterparty, contract_type, value, start_date, end_date, owner, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (title, counterparty, ctype, value, _d(start_ago),
             _d(start_ago + end_off), owner, status),
        )
    conn.commit()


def _remove_contracts(conn):
    conn.execute("DELETE FROM legal_contract WHERE title LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

COMPLIANCE = [
    # (requirement, regulation, owner, due_offset, comp_offset, status)
    ("OSHA 1910.147 Lockout/Tagout Annual Training",     "OSHA 29 CFR 1910.147",    "Janet Flores",   30,   None, "Pending"),
    ("EPA Tier II Hazardous Chemical Reporting",          "EPA EPCRA Sec. 312",      "Sandra Pierce",  60,   None, "In Progress"),
    ("GDPR Data Processing Agreement Review",             "GDPR Article 28",         "Janet Flores",   45,   None, "In Progress"),
    ("Annual ITAR Compliance Self-Assessment",            "22 CFR Part 120-130",     "Sandra Pierce",  90,   None, "Pending"),
    ("Workers Comp Insurance Renewal",                   "State Labor Code",        "Janet Flores",   30,   None, "Pending"),
    ("ISO 9001 Certificate Renewal",                     "ISO 9001:2015",           "Sandra Pierce",  180,  None, "Pending"),
    ("ADA Website Accessibility Audit",                  "ADA Title III",           "Janet Flores",   60,   None, "Pending"),
    ("OSHA 300 Log Annual Summary Posting",              "OSHA 29 CFR 1904.32",     "Sandra Pierce",  -30,  -28, "Complete"),
    ("PCI-DSS Payment Card Security Review",             "PCI-DSS v4.0",            "Janet Flores",   -60,  -55, "Complete"),
    ("State Sales Tax Nexus Review",                     "State Rev. Code",         "Sandra Pierce",  -15,  -10, "Complete"),
    ("Export Control Classification Review — New Parts", "EAR 15 CFR Part 730",     "Janet Flores",   14,   None, "In Progress"),
    ("Annual Employee Handbook Update",                  "State Employment Law",    "Sandra Pierce",  120,  None, "Pending"),
]


def _seed_compliance(conn):
    for req, regulation, owner, due_off, comp_off, status in COMPLIANCE:
        if conn.execute(
            "SELECT 1 FROM legal_compliance WHERE requirement=%s AND notes='Sample data'",
            (req,)
        ).fetchone():
            continue
        comp = _d(comp_off) if comp_off is not None else None
        conn.execute(
            "INSERT INTO legal_compliance"
            " (requirement, regulation, owner, due_date, completed_date, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,'Sample data')",
            (req, regulation, owner, _d(due_off), comp, status),
        )
    conn.commit()


def _remove_compliance(conn):
    conn.execute("DELETE FROM legal_compliance WHERE notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Litigation
# ---------------------------------------------------------------------------

LITIGATION = [
    # (case_name, opposing_party, court, case_type, filed_ago, status, outcome)
    (f"{TAG}Smith v. Company — Slip & Fall",          "Robert Smith",           "Ohio Court of Common Pleas",   "Civil",           -365, "Settled",     "Settlement — $18,500 paid; no admission of liability"),
    (f"{TAG}Patent Dispute — Valve Design",           "ValveTech Industries",   "Federal District Court N.D.",  "IP",              -180, "In Discovery","Discovery phase ongoing; hearing scheduled Q4"),
    (f"{TAG}Breach of Contract — Delta Components",  "Delta Components Co.",   "Ohio Court of Common Pleas",   "Contract Dispute", -90, "Open",        ""),
    (f"{TAG}Employment Claim — Former Employee",      "Mark Jennings",          "EEOC / Mediation",             "Employment",       -45, "Dismissed",   "EEOC dismissed claim; no probable cause found"),
    (f"{TAG}Regulatory Notice — EPA",                "U.S. EPA",               "Administrative",               "Regulatory",       -30, "Open",        "Response to EPA information request — in progress"),
]


def _seed_litigation(conn):
    for case_name, opposing, court, ctype, filed_ago, status, outcome in LITIGATION:
        if conn.execute("SELECT 1 FROM legal_litigation WHERE case_name=%s", (case_name,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO legal_litigation"
            " (case_name, opposing_party, court, case_type, filed_date, status, outcome, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (case_name, opposing, court, ctype, _d(filed_ago), status, outcome),
        )
    conn.commit()


def _remove_litigation(conn):
    conn.execute("DELETE FROM legal_litigation WHERE case_name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_contracts(conn)
    _seed_compliance(conn)
    _seed_litigation(conn)
    print("Legal sample data seeded.")


def remove(conn):
    _remove_litigation(conn)
    _remove_compliance(conn)
    _remove_contracts(conn)
    print("Legal sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Legal sample data")
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
