"""seed_sample_purchasing.py — sample Purchasing department data.

Covers: supplier contacts (8 companies) and purchase requisitions
spanning every workflow status (draft, submitted, dept_approved,
dept_denied, approved, denied, cancelled) with line items and approval
history.

Suppliers are tagged ``created_by = 'SMPL-PURCH-'`` for safe removal.
Requisitions are identified by the ``req_number`` prefix ``SMPL-REQ-``.

Usage::

    python -m manufacturing.seeds.seed_sample_purchasing            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_purchasing --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_purchasing --remove    # remove only

Run seed_sample_data first so department and people records exist.
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection
from ..purchase_orders_core import ensure_po_tables

TAG = "SMPL-PURCH-"
REQ_PREFIX = "SMPL-REQ-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supplier (
            id           SERIAL PRIMARY KEY,
            first_name   TEXT NOT NULL,
            last_name    TEXT NOT NULL,
            company_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            address      TEXT NOT NULL,
            city         TEXT NOT NULL,
            state        TEXT NOT NULL,
            zip_code     TEXT NOT NULL,
            email        TEXT NOT NULL
        )
    """)
    conn.execute("ALTER TABLE supplier ADD COLUMN IF NOT EXISTS created_by TEXT")
    ensure_po_tables(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requisition (
            id            SERIAL PRIMARY KEY,
            req_number    TEXT NOT NULL UNIQUE,
            requester_id  INTEGER,
            dept_id       INTEGER,
            dept_sub_id   INTEGER,
            needed_date   TEXT,
            justification TEXT,
            status        TEXT DEFAULT 'draft',
            created_date  TEXT,
            po_id         INTEGER
        )
    """)
    conn.execute(
        "ALTER TABLE purchase_requisition "
        "ADD COLUMN IF NOT EXISTS po_id INTEGER")
    conn.execute(
        "ALTER TABLE purchase_requisition "
        "ADD COLUMN IF NOT EXISTS dept_sub_id INTEGER")
    conn.execute(
        "ALTER TABLE purchase_requisition "
        "ADD COLUMN IF NOT EXISTS created_by TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requisition_item (
            id             SERIAL PRIMARY KEY,
            req_id         INTEGER NOT NULL REFERENCES purchase_requisition(id),
            description    TEXT NOT NULL,
            product_id     INTEGER,
            qty            INTEGER DEFAULT 1,
            est_unit_price REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requisition_approval (
            id           SERIAL PRIMARY KEY,
            req_id       INTEGER NOT NULL REFERENCES purchase_requisition(id),
            level        TEXT,
            approver_id  INTEGER,
            decision     TEXT,
            comment      TEXT,
            decided_date TEXT
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

# (first_name, last_name, company_name, phone, address, city, state, zip, email)
SUPPLIERS = [
    ("John",     "Smith",    "Acme Steel Supplies",
     "555-100-0001", "100 Industrial Blvd", "Detroit",      "MI", "48201",
     "orders@acmesteel.example.com"),
    ("Maria",    "Garcia",   "Pacific Rim Components",
     "555-100-0002", "250 Harbor Way",      "Long Beach",   "CA", "90802",
     "sales@pacificrim.example.com"),
    ("Robert",   "Johnson",  "Midwest Paint & Coatings",
     "555-100-0003", "775 Paint Ave",       "Chicago",      "IL", "60601",
     "info@midwestpaint.example.com"),
    ("Linda",    "Williams", "Eastern Fastener Corp",
     "555-100-0004", "400 Bolt St",         "Newark",       "NJ", "07101",
     "orders@efastener.example.com"),
    ("David",    "Lee",      "Southern Rubber & Tire",
     "555-100-0005", "1200 Rubber Rd",      "Memphis",      "TN", "38101",
     "orders@srubber.example.com"),
    ("Patricia", "Brown",    "Northern Tube & Pipe",
     "555-100-0006", "88 Pipe Lane",        "Minneapolis",  "MN", "55401",
     "sales@ntubepipe.example.com"),
    ("James",    "Wilson",   "Apex Electronics Supply",
     "555-100-0007", "2020 Circuit Dr",     "Austin",       "TX", "78701",
     "supply@apexelec.example.com"),
    ("Sandra",   "Miller",   "Global Office Solutions",
     "555-100-0008", "300 Commerce St",     "Atlanta",      "GA", "30301",
     "orders@globalofc.example.com"),
]


def _seed_suppliers(conn):
    n = 0
    for (fn, ln, co, ph, addr, city, st, zp, em) in SUPPLIERS:
        if conn.execute(
            "SELECT 1 FROM supplier WHERE company_name=%s AND created_by=%s",
            (co, TAG)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO supplier (first_name, last_name, company_name,"
            " phone_number, address, city, state, zip_code, email, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (fn, ln, co, ph, addr, city, st, zp, em, TAG),
        )
        n += 1
    conn.commit()
    return n


def _remove_suppliers(conn):
    cur = conn.execute("DELETE FROM supplier WHERE created_by=%s", (TAG,))
    conn.commit()
    return cur.rowcount


def _suppliers_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM supplier WHERE created_by=%s", (TAG,)
    ).fetchone()[0] > 0


# ---------------------------------------------------------------------------
# Purchase requisitions
# ---------------------------------------------------------------------------

def _person_by_sub_dept(conn, sub_dept_name):
    """Return first person in sub_dept_name as a row with id/dept_id/dept_sub_id."""
    return conn.execute("""
        SELECT p.id, p.dept_id, p.dept_sub_id
        FROM people p
        JOIN dept_sub ds ON ds.dept_sub_id = p.dept_sub_id
        WHERE ds.dept_sub_name = %s
        ORDER BY p.id
        LIMIT 1
    """, (sub_dept_name,)).fetchone()


# (suffix, requester_sub_dept, needed_offset, created_offset, justification,
#  status,
#  items=[(desc, qty, est_unit_price)],
#  approvals=[(level, approver_sub_dept, decision, comment)])
REQUISITIONS = [
    (
        "001", "IT Technician", +14, 0,
        "New workstation components for expanding helpdesk team",
        "draft",
        [
            ("16-port managed network switch",  2, 450.00),
            ("USB-C docking stations",          5,  89.99),
        ],
        [],
    ),
    (
        "002", "Maintenance Mechanic", +7, -3,
        "Replacement bearings for main conveyor line",
        "submitted",
        [
            ("6205 deep-groove ball bearings (box of 10)", 20,  4.75),
            ("SAE 30 machine oil, 5-gallon drum",           4, 28.50),
        ],
        [],
    ),
    (
        "003", "Production Foreman", +10, -7,
        "Raw material restock for Q3 production schedule",
        "dept_approved",
        [
            ("Steel tube 1-inch OD, 12-ft lengths",  200, 3.50),
            ("Paint cans — gloss blue, 1-quart",      50, 12.00),
        ],
        [
            ("dept", "Production Manager", "approved",
             "Budget confirmed; forward to Purchasing for supplier selection."),
        ],
    ),
    (
        "004", "Engineer", +21, -5,
        "Prototype tooling for new lightweight frame design",
        "dept_denied",
        [
            ("CNC carbide cutting insert set (10-pack)", 3, 185.00),
            ("Precision calibration fixture",             1, 620.00),
        ],
        [
            ("dept", "Engineer Manager", "denied",
             "Prototype budget exhausted for Q2; resubmit in Q4."),
        ],
    ),
    (
        "005", "Customer Service Rep", +5, -10,
        "Ergonomic furniture for CS team expansion — 6 new hires",
        "approved",
        [
            ("Ergonomic office chair, mesh back",  6, 219.99),
            ("Adjustable dual-monitor arm",        6,  49.99),
        ],
        [
            ("dept",       "Customer Service Manager", "approved",
             "Headcount confirmed; furniture needed before new hires start."),
            ("purchasing", "Purchasing Manager",       "approved",
             "Sourced from Global Office Solutions; PO to follow."),
        ],
    ),
    (
        "006", "IT Technician", +3, -8,
        "Printer toner emergency restock — all floors below minimum",
        "denied",
        [
            ("HP LaserJet toner cartridge — black", 12, 38.50),
            ("HP LaserJet toner cartridge — color",  6, 54.00),
        ],
        [
            ("dept",       "IT Manager",        "approved",
             "Routine consumable; approved to proceed."),
            ("purchasing", "Purchasing Manager", "denied",
             "Consolidate with Q2 office supply blanket order; resubmit next cycle."),
        ],
    ),
    (
        "007", "Maintenance Mechanic", +30, -2,
        "Annual safety equipment refresh per OSHA inspection findings",
        "cancelled",
        [
            ("Safety harness, ANSI-rated full-body",   10, 89.00),
            ("Winter hard-hat liner, universal fit",   20, 12.50),
            ("High-vis safety vest, XL",               15,  8.75),
        ],
        [],
    ),
]


def _seed_requisitions(conn):
    req_n = item_n = appr_n = 0
    for (suffix, req_sub_dept, needed_off, created_off, justification,
         status, items, approvals) in REQUISITIONS:
        req_number = REQ_PREFIX + suffix
        if conn.execute(
            "SELECT 1 FROM purchase_requisition WHERE req_number=%s",
            (req_number,)
        ).fetchone():
            continue

        requester = _person_by_sub_dept(conn, req_sub_dept)
        if requester:
            req_id_val = requester["id"]
            dept_id = requester["dept_id"]
            dept_sub_id = requester["dept_sub_id"]
        else:
            req_id_val = dept_id = dept_sub_id = None

        row = conn.execute(
            "INSERT INTO purchase_requisition (req_number, requester_id,"
            " dept_id, dept_sub_id, needed_date, justification, status,"
            " created_date, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " RETURNING id",
            (req_number, req_id_val, dept_id, dept_sub_id,
             _d(needed_off), justification, status, _d(created_off), TAG),
        ).fetchone()
        rid = row["id"]
        req_n += 1

        for (desc, qty, est_price) in items:
            conn.execute(
                "INSERT INTO requisition_item (req_id, description, qty,"
                " est_unit_price) VALUES (%s,%s,%s,%s)",
                (rid, desc, qty, est_price),
            )
            item_n += 1

        for (level, approver_sub_dept, decision, comment) in approvals:
            approver = _person_by_sub_dept(conn, approver_sub_dept)
            approver_id = approver["id"] if approver else None
            conn.execute(
                "INSERT INTO requisition_approval (req_id, level, approver_id,"
                " decision, comment, decided_date) VALUES (%s,%s,%s,%s,%s,%s)",
                (rid, level, approver_id, decision, comment, _d(-1)),
            )
            appr_n += 1

    conn.commit()
    return req_n, item_n, appr_n


def _remove_requisitions(conn):
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM purchase_requisition WHERE req_number LIKE %s",
        (REQ_PREFIX + "%",)
    ).fetchall()]
    appr_n = item_n = req_n = 0
    if ids:
        appr_n = conn.execute(
            "DELETE FROM requisition_approval WHERE req_id = ANY(%s)", (ids,)
        ).rowcount
        item_n = conn.execute(
            "DELETE FROM requisition_item WHERE req_id = ANY(%s)", (ids,)
        ).rowcount
        req_n = conn.execute(
            "DELETE FROM purchase_requisition WHERE id = ANY(%s)", (ids,)
        ).rowcount
    conn.commit()
    return req_n, item_n, appr_n


def _requisitions_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM purchase_requisition WHERE req_number LIKE %s",
        (REQ_PREFIX + "%",)
    ).fetchone()[0] > 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed sample Purchasing department data.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample data, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample data only (no seeding)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        _ensure_tables(conn)

        if args.remove or args.reset:
            req_n, item_n, appr_n = _remove_requisitions(conn)
            sup_n = _remove_suppliers(conn)
            print(f"removed {req_n} requisitions ({item_n} items,"
                  f" {appr_n} approvals), {sup_n} suppliers")
            if args.remove:
                return

        if _suppliers_present(conn):
            print("Suppliers already present; use --reset to recreate.")
        else:
            sup_n = _seed_suppliers(conn)
            print(f"inserted {sup_n} suppliers")

        if _requisitions_present(conn):
            print("Requisitions already present; use --reset to recreate.")
        else:
            req_n, item_n, appr_n = _seed_requisitions(conn)
            print(f"inserted {req_n} requisitions ({item_n} items,"
                  f" {appr_n} approvals)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


