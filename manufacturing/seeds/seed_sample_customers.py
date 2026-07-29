"""seed_sample_customers.py — sample Customers and Credit department data.

Covers: customer master records, credit accounts, credit applications,
credit limit history, and collection activities.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_customers            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_customers --reset    # remove + re-add
    python -m manufacturing.seeds.seed_sample_customers --remove   # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-CUST-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id SERIAL PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            company_name TEXT,
            phone_number TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            email TEXT
        )
    """)
    try:
        conn.execute(
            "ALTER TABLE customer ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_account (
            id              SERIAL PRIMARY KEY,
            customer_id     INTEGER NOT NULL UNIQUE REFERENCES customer(id),
            credit_limit    REAL    NOT NULL DEFAULT 0.0,
            status          TEXT    NOT NULL DEFAULT 'good',
            terms           TEXT,
            opened_date     TEXT    NOT NULL,
            notes           TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_application (
            id               SERIAL PRIMARY KEY,
            customer_id      INTEGER NOT NULL REFERENCES customer(id),
            applied_date     TEXT    NOT NULL,
            requested_limit  REAL    NOT NULL DEFAULT 0.0,
            approved_limit   REAL,
            status           TEXT    NOT NULL DEFAULT 'pending',
            reviewed_by      TEXT,
            review_date      TEXT,
            notes            TEXT,
            created_by       TEXT
        )
    """)
    try:
        conn.execute(
            "ALTER TABLE credit_application"
            " ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_limit_history (
            id           SERIAL PRIMARY KEY,
            customer_id  INTEGER NOT NULL REFERENCES customer(id),
            changed_date TEXT    NOT NULL,
            old_limit    REAL,
            new_limit    REAL    NOT NULL,
            old_status   TEXT,
            new_status   TEXT,
            changed_by   TEXT,
            reason       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_activity (
            id              SERIAL PRIMARY KEY,
            customer_id     INTEGER NOT NULL REFERENCES customer(id),
            activity_date   TEXT    NOT NULL DEFAULT CURRENT_DATE,
            activity_type   TEXT    NOT NULL DEFAULT 'Call',
            contact_name    TEXT    DEFAULT '',
            notes           TEXT    DEFAULT '',
            amount_promised REAL    DEFAULT NULL,
            promise_date    TEXT    DEFAULT NULL,
            follow_up_date  TEXT    DEFAULT NULL,
            status          TEXT    NOT NULL DEFAULT 'Open',
            created_by      TEXT    DEFAULT ''
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

CUSTOMERS = [
    # (company_name, first_name, last_name, phone, address, city, state, zip, email)
    ("Apex Metalworks Inc.", "Bob", "Harrison", "555-210-1000",
     "100 Industrial Blvd", "Cleveland", "OH", "44101",
     "b.harrison@apexmetalworks.example.com"),
    ("Summit Fabricators LLC", "Alice", "Nguyen", "555-210-1001",
     "450 Commerce Dr", "Columbus", "OH", "43201",
     "a.nguyen@summitfab.example.com"),
    ("Pacific Rim Parts Co.", "James", "Chen", "555-210-1002",
     "800 Pacific Ave", "Cincinnati", "OH", "45201",
     "j.chen@pacificrimparts.example.com"),
    ("Allied Components Corp.", "Sandra", "Koch", "555-210-1003",
     "220 Allied Way", "Toledo", "OH", "43601",
     "s.koch@alliedcomponents.example.com"),
    ("Delta Precision Parts LLC", "Tom", "Briggs", "555-210-1004",
     "55 Delta Park", "Akron", "OH", "44301",
     "t.briggs@deltaprecision.example.com"),
    ("Crestview Industries LLC", "Mary", "Sullivan", "555-210-1005",
     "300 Crest Rd", "Dayton", "OH", "45401",
     "m.sullivan@crestviewind.example.com"),
    ("Ironworks Supply Co.", "Frank", "Russo", "555-210-1006",
     "110 Steel Mill Rd", "Youngstown", "OH", "44501",
     "f.russo@ironworkssupply.example.com"),
    ("Lakeside Manufacturing Inc.", "Karen", "Drake", "555-210-1007",
     "900 Lakeview Blvd", "Cleveland", "OH", "44102",
     "k.drake@lakesidemfg.example.com"),
    ("Blue Ridge Tooling Inc.", "Paul", "Whitfield", "555-210-1008",
     "75 Ridge Rd", "Canton", "OH", "44701",
     "p.whitfield@blueridgetooling.example.com"),
    ("Momentum Plastics LLC", "Diana", "Park", "555-210-1009",
     "610 Polymer Dr", "Lorain", "OH", "44052",
     "d.park@momentumplastics.example.com"),
]


def _seed_customers(conn):
    for (company, first, last, phone, address,
         city, state, zip_code, email) in CUSTOMERS:
        if conn.execute(
            "SELECT 1 FROM customer WHERE company_name=%s AND created_by=%s",
            (company, TAG),
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO customer"
            " (company_name, first_name, last_name, phone_number, address,"
            "  city, state, zip_code, email, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (company, first, last, phone, address,
             city, state, zip_code, email, TAG),
        )
    conn.commit()


def _remove_customers(conn):
    conn.execute("DELETE FROM customer WHERE created_by=%s", (TAG,))
    conn.commit()


# ---------------------------------------------------------------------------
# Credit Accounts
# ---------------------------------------------------------------------------

CREDIT_ACCOUNTS = [
    # (company_name, credit_limit, status, terms, opened_days_ago, notes)
    ("Apex Metalworks Inc.",        25000.0, "good",      "Net 30", -730,  None),
    ("Summit Fabricators LLC",      15000.0, "good",      "Net 45", -540,  None),
    ("Pacific Rim Parts Co.",       50000.0, "good",      "Net 30", -1095, None),
    ("Allied Components Corp.",     10000.0, "good",      "Net 45", -365,  None),
    ("Delta Precision Parts LLC",   20000.0, "hold",      "Net 30", -730,
     "Limit reduced; placed on hold pending balance resolution"),
    ("Crestview Industries LLC",    30000.0, "good",      "Net 60", -548,  None),
    ("Ironworks Supply Co.",         8000.0, "suspended", "COD",    -1095,
     "Suspended after chronic late payments"),
    ("Lakeside Manufacturing Inc.", 35000.0, "good",      "Net 30", -730,  None),
    ("Blue Ridge Tooling Inc.",     12000.0, "good",      "Net 45", -240,  None),
    ("Momentum Plastics LLC",        5000.0, "good",      "Net 30", -180,  None),
]


def _cust_id(conn, company_name):
    row = conn.execute(
        "SELECT id FROM customer WHERE company_name=%s AND created_by=%s",
        (company_name, TAG),
    ).fetchone()
    return row[0] if row else None


def _seed_credit_accounts(conn):
    for company, limit, status, terms, opened_ago, notes in CREDIT_ACCOUNTS:
        cid = _cust_id(conn, company)
        if cid is None:
            continue
        if conn.execute(
            "SELECT 1 FROM credit_account WHERE customer_id=%s", (cid,)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO credit_account"
            " (customer_id, credit_limit, status, terms, opened_date, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s)",
            (cid, limit, status, terms, _d(opened_ago), notes),
        )
    conn.commit()


def _remove_credit_accounts(conn):
    conn.execute(
        "DELETE FROM credit_account WHERE customer_id IN"
        " (SELECT id FROM customer WHERE created_by=%s)",
        (TAG,),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Credit Applications
# ---------------------------------------------------------------------------

APPLICATIONS = [
    # (company_name, applied_days_ago, requested_limit, approved_limit,
    #  status, reviewed_by, review_days_ago, notes)
    ("Apex Metalworks Inc.", -700, 25000.0, 25000.0, "approved",
     "Finance Dept", -695, "Initial credit line approved — strong trade references"),
    ("Summit Fabricators LLC", -520, 15000.0, 15000.0, "approved",
     "Finance Dept", -515, "Approved based on two-year trade references"),
    ("Pacific Rim Parts Co.", -1080, 50000.0, 50000.0, "approved",
     "Finance Dept", -1075, "High-volume account; limit approved with quarterly review"),
    ("Lakeside Manufacturing Inc.", -710, 35000.0, 35000.0, "approved",
     "Finance Dept", -705, "Approved after site visit and D&B report review"),
    ("Ironworks Supply Co.", -400, 15000.0, None, "denied",
     "Finance Dept", -395, "Denied — poor payment history with prior vendors"),
    ("Delta Precision Parts LLC", -500, 30000.0, None, "denied",
     "Finance Dept", -495,
     "Denied at requested amount; approved at $20,000 via separate review"),
    ("Crestview Industries LLC", -10, 40000.0, None, "pending",
     None, None, "Requesting increase from $30,000 to $40,000"),
    ("Momentum Plastics LLC", -5, 10000.0, None, "pending",
     None, None, "Initial credit application for new account"),
]


def _seed_applications(conn):
    for (company, applied_ago, req_limit, appr_limit,
         status, reviewer, review_ago, notes) in APPLICATIONS:
        cid = _cust_id(conn, company)
        if cid is None:
            continue
        # Keyed on notes (distinct per row) rather than applied_date: the
        # latter is TODAY + offset, so it drifts every day and a same-day
        # idempotency check would never match a row inserted on a prior day,
        # inserting a duplicate application on every non-reset re-run.
        if conn.execute(
            "SELECT 1 FROM credit_application"
            " WHERE customer_id=%s AND created_by=%s AND notes=%s",
            (cid, TAG, notes),
        ).fetchone():
            continue
        review_date = _d(review_ago) if review_ago is not None else None
        conn.execute(
            "INSERT INTO credit_application"
            " (customer_id, applied_date, requested_limit, approved_limit,"
            "  status, reviewed_by, review_date, notes, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, _d(applied_ago), req_limit, appr_limit,
             status, reviewer, review_date, notes, TAG),
        )
    conn.commit()


def _remove_applications(conn):
    conn.execute("DELETE FROM credit_application WHERE created_by=%s", (TAG,))
    conn.commit()


# ---------------------------------------------------------------------------
# Credit Limit History
# ---------------------------------------------------------------------------

LIMIT_HISTORY = [
    # (company_name, changed_days_ago, old_limit, new_limit,
    #  old_status, new_status, reason)
    ("Lakeside Manufacturing Inc.", -365, 20000.0, 35000.0,
     "good", "good", "Limit increased — two-year perfect payment record"),
    ("Delta Precision Parts LLC", -75, 30000.0, 20000.0,
     "good", "hold",
     "Overdue balance exceeded original limit — limit reduced and placed on hold"),
    ("Ironworks Supply Co.", -120, 15000.0, 8000.0,
     "good", "good", "Limit reduced due to chronic late payments"),
    ("Ironworks Supply Co.", -45, 8000.0, 8000.0,
     "good", "suspended", "Account suspended — balance outstanding > 90 days"),
]


def _seed_limit_history(conn):
    for (company, changed_ago, old_limit, new_limit,
         old_status, new_status, reason) in LIMIT_HISTORY:
        cid = _cust_id(conn, company)
        if cid is None:
            continue
        # Keyed on reason (distinct per row, and a customer can have more
        # than one history row) rather than changed_date -- see
        # _seed_applications for why the drifting-date key is wrong.
        if conn.execute(
            "SELECT 1 FROM credit_limit_history"
            " WHERE customer_id=%s AND changed_by=%s AND reason=%s",
            (cid, TAG, reason),
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO credit_limit_history"
            " (customer_id, changed_date, old_limit, new_limit,"
            "  old_status, new_status, changed_by, reason)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, _d(changed_ago), old_limit, new_limit,
             old_status, new_status, TAG, reason),
        )
    conn.commit()


def _remove_limit_history(conn):
    conn.execute("DELETE FROM credit_limit_history WHERE changed_by=%s", (TAG,))
    conn.commit()


# ---------------------------------------------------------------------------
# Collection Activity
# ---------------------------------------------------------------------------

COLLECTION_ACTIVITY = [
    # (company_name, activity_days_ago, activity_type, contact_name,
    #  amount_promised, promise_days_ago, follow_up_days_ago, status, notes)
    ("Delta Precision Parts LLC", -25, "Call", "Tom Briggs",
     4200.0, -18, -18, "Open",
     "Spoke with AP contact re $4,200 overdue balance; payment promised by end of week"),
    ("Delta Precision Parts LLC", -15, "Email", "Tom Briggs",
     None, None, -8, "Open",
     "Sent follow-up email; no payment received — escalating to formal demand"),
    ("Ironworks Supply Co.", -50, "Call", "Frank Russo",
     6800.0, -43, -43, "Open",
     "Reached owner; promised payment within 7 days — balance $6,800"),
    ("Ironworks Supply Co.", -35, "Letter", "Frank Russo",
     None, None, -21, "Open",
     "Formal collection letter sent; no payment received"),
    ("Ironworks Supply Co.", -10, "Call", "Frank Russo",
     None, None, -3, "Escalated",
     "No response to letter or prior calls; file transferred to collections agency"),
]


def _seed_collection_activity(conn):
    for (company, act_ago, act_type, contact,
         amt, promise_ago, followup_ago, status, notes) in COLLECTION_ACTIVITY:
        cid = _cust_id(conn, company)
        if cid is None:
            continue
        # Keyed on notes (distinct per row, and a customer can have several
        # activities of the same type) rather than activity_date -- see
        # _seed_applications for why the drifting-date key is wrong.
        if conn.execute(
            "SELECT 1 FROM collection_activity"
            " WHERE customer_id=%s AND created_by=%s"
            " AND activity_type=%s AND notes=%s",
            (cid, TAG, act_type, notes),
        ).fetchone():
            continue
        promise_date = _d(promise_ago) if promise_ago is not None else None
        followup_date = _d(followup_ago) if followup_ago is not None else None
        conn.execute(
            "INSERT INTO collection_activity"
            " (customer_id, activity_date, activity_type, contact_name,"
            "  notes, amount_promised, promise_date, follow_up_date,"
            "  status, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, _d(act_ago), act_type, contact,
             notes, amt, promise_date, followup_date, status, TAG),
        )
    conn.commit()


def _remove_collection_activity(conn):
    conn.execute("DELETE FROM collection_activity WHERE created_by=%s", (TAG,))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_customers(conn)
    _seed_credit_accounts(conn)
    _seed_applications(conn)
    _seed_limit_history(conn)
    _seed_collection_activity(conn)
    print("Customers and Credit sample data seeded.")


def remove(conn):
    _remove_collection_activity(conn)
    _remove_limit_history(conn)
    _remove_applications(conn)
    _remove_credit_accounts(conn)
    _remove_customers(conn)
    print("Customers and Credit sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed Customers and Credit sample data")
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


