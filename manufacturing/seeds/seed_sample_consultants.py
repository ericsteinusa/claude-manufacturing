"""seed_sample_consultants.py — sample Consultant Time & Charges data.

Seeds three consultants exercising every link state the feature supports:
  1. External — linked to an existing `supplier` row (or a fallback one,
     created the same way `seed_sample_pos.py` does if no supplier exists
     yet). Carried through the full lifecycle: engagement -> itemized time
     & charges -> invoice cut -> submitted -> approved -> converted to a
     real `ap_invoice` -> partially paid.
  2. Internal-style — linked to an existing hourly `people` row (from
     `seed_sample_payroll`, if that seed has run) to demonstrate contract
     labor working alongside staff. Its invoice is cut and submitted but
     left pending, so the approval queue isn't empty on first login.
  3. Ad hoc — no supplier or people link, and deliberately no default rate
     anywhere in the fallback chain, so one of its time entries has no
     resolvable hourly rate. Left un-invoiced to demonstrate
     create_consultant_invoice's guard against silently billing $0 for
     real hours worked (this is the case verification step 4 covers).

Also seeds one `approval_rule` for entity_type='consultant_invoice'
(tagged via `notes`, following seed_sample_operations.py's own precedent
for seeding approval rules), since without one, submitting a consultant
invoice creates no approval_step and nothing to approve/reject.

Consultants and engagements are both tagged `created_by = 'SMPL-CONS'`.
Unlike `seed_sample_pos.py`'s `po_number`, `consultant_engagement`'s
auto-generated `engagement_number` (via `mrp_core.next_sequence_number`,
same as every other real engagement) has no room for a caller-supplied
prefix, so `created_by` is the idempotency key here instead of the number
column. Time entries, charges, invoices, and any resulting
`ap_invoice`/`ap_payment` rows are found and removed by walking down from
the tagged engagements, not by their own tags.

Run after `seed_sample_purchasing` (suppliers) and
`seed_sample_personnel`/`seed_sample_payroll` (people + hourly rates) —
if those haven't run yet, this seed still works, just with a fallback
supplier and an untethered "internal-style" consultant instead.

Usage::

    python -m manufacturing.seeds.seed_sample_consultants            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_consultants --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_consultants --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection
from ..consultants_core import (
    ensure_consultant_tables, create_consultant, create_engagement,
    activate_engagement, add_time_entry, add_charge,
    create_consultant_invoice, submit_consultant_invoice,
    get_consultant_invoice, get_invoice_lines,
    decide_consultant_invoice_via_workflow,
)
from ..approval_workflow_core import (
    ensure_approval_tables, create_approval_rule, get_entity_approval_status,
)
from ..accounting_core import record_ap_payment

TAG = "SMPL-CONS"
FALLBACK_SUPPLIER_TAG = "SMPL-CONS-FALLBACK"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_ap_tables(conn):
    """Defensive copy of ap_invoice/ap_payment DDL, matching
    seed_sample_accounting.py's own copy — this seed can run standalone
    before schema.py's init_schema (which normally creates these at
    Django startup) has had a chance to."""
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


def _first_supplier_id(conn):
    """Same fallback-supplier precedent as seed_sample_pos.py's
    _first_supplier_id: reuse the first existing supplier, or create a
    minimal one rather than leaving the external consultant unlinked.

    Unlike seed_sample_pos.py's version, this fills every column the live
    `supplier` table actually enforces NOT NULL on (first_name/last_name/
    phone_number/address/city/state/zip_code/email) — schema.py's DDL
    declares them nullable, but the live schema doesn't, per
    consultants_core._resolve_vendor_id's own fix for the same drift."""
    row = conn.execute("SELECT id FROM supplier ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO supplier (first_name, last_name, company_name,"
        " phone_number, address, city, state, zip_code, email, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        ('', '', "Sample Fallback Supplier", '', '', '', '', '',
         "fallback-supplier@example.com", FALLBACK_SUPPLIER_TAG),
    ).fetchone()["id"]


def _hourly_person(conn):
    """Return {'people_id', 'pay_rate', 'first_name', 'last_name'} for an
    arbitrary hourly employee (from seed_sample_payroll), or None if the
    payroll seed hasn't run yet — that's a valid precondition to be
    missing, so this returns None rather than raising."""
    try:
        row = conn.execute("""
            SELECT ep.people_id, ep.pay_rate, p.first_name, p.last_name
            FROM employee_pay ep JOIN people p ON p.id = ep.people_id
            WHERE ep.pay_type = 'hourly' ORDER BY ep.people_id LIMIT 1
        """).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _dept_id(conn, name_like):
    row = conn.execute(
        "SELECT dept_id FROM dept WHERE dept_name ILIKE %s LIMIT 1",
        (f"%{name_like}%",)).fetchone()
    if row:
        return row["dept_id"]
    row = conn.execute("SELECT dept_id FROM dept ORDER BY dept_id LIMIT 1").fetchone()
    return row["dept_id"] if row else None


def sample_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM consultant_engagement WHERE created_by = %s",
        (TAG,)).fetchone()[0] > 0


def remove_sample(conn):
    """Delete sample engagements and everything that hangs off them
    (time entries, charges, invoices, approval steps, and any resulting
    ap_invoice/ap_payment), then the sample consultants and approval
    rule. Returns (engagements, consultants) removed.

    Tagged via consultant_engagement.created_by, not engagement_number —
    create_engagement() always auto-generates an ENG-<year>-NNNN number
    with no room for a caller-supplied prefix, so (unlike po_number in
    seed_sample_pos.py, which is set directly via raw SQL) the number
    itself can't double as the idempotency key here."""
    eng_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM consultant_engagement WHERE created_by = %s",
        (TAG,)).fetchall()]

    cinv_rows = []
    if eng_ids:
        cinv_rows = conn.execute(
            "SELECT id, ap_invoice_id FROM consultant_invoice WHERE engagement_id = ANY(%s)",
            (eng_ids,)).fetchall()
    cinv_ids = [r["id"] for r in cinv_rows]
    ap_ids = [r["ap_invoice_id"] for r in cinv_rows if r["ap_invoice_id"]]

    if ap_ids:
        conn.execute("DELETE FROM ap_payment WHERE invoice_id = ANY(%s)", (ap_ids,))
        conn.execute("DELETE FROM ap_invoice WHERE id = ANY(%s)", (ap_ids,))
    if cinv_ids:
        conn.execute(
            "DELETE FROM approval_step WHERE entity_type = 'consultant_invoice'"
            " AND entity_id = ANY(%s)", (cinv_ids,))
    if eng_ids:
        conn.execute("DELETE FROM consultant_time_entry WHERE engagement_id = ANY(%s)", (eng_ids,))
        conn.execute("DELETE FROM consultant_charge WHERE engagement_id = ANY(%s)", (eng_ids,))
        conn.execute("DELETE FROM consultant_invoice WHERE engagement_id = ANY(%s)", (eng_ids,))
        conn.execute("DELETE FROM consultant_engagement WHERE id = ANY(%s)", (eng_ids,))

    n_cons = conn.execute(
        "DELETE FROM consultant WHERE created_by = %s", (TAG,)).rowcount
    conn.execute("DELETE FROM supplier WHERE created_by = %s", (FALLBACK_SUPPLIER_TAG,))
    conn.execute("DELETE FROM approval_rule WHERE notes = %s", (TAG,))
    return len(eng_ids), n_cons


def _seed_approval_rule(conn):
    exists = conn.execute(
        "SELECT 1 FROM approval_rule WHERE entity_type = 'consultant_invoice'"
        " AND notes = %s", (TAG,)).fetchone()
    if exists:
        return
    create_approval_rule(
        conn, 'consultant_invoice', 'Department Manager',
        seq=10, dept_key='', threshold_amount=0, notes=TAG,
    )


def _run_invoice_to_approved_and_paid(conn, engagement_id, period_start, period_end):
    """Cut an invoice, submit it, approve it (creates the real ap_invoice),
    then record a partial payment. Returns the ap_invoice_id."""
    cinv_id = create_consultant_invoice(
        conn, engagement_id, period_start, period_end, created_by=TAG)
    lines = get_invoice_lines(conn, cinv_id)
    submit_consultant_invoice(conn, cinv_id, TAG)
    approval = get_entity_approval_status(conn, 'consultant_invoice', cinv_id)
    pending = next((s for s in approval['steps'] if s['status'] == 'pending'), None)
    if pending:
        decide_consultant_invoice_via_workflow(
            conn, cinv_id, pending['id'], 'approved', TAG)
    cinv = get_consultant_invoice(conn, cinv_id)
    if cinv and cinv['ap_invoice_id']:
        record_ap_payment(
            conn, cinv['ap_invoice_id'], _d(0), round(lines['total'] / 2, 2),
            'ACH', TAG, TAG,
        )
    return cinv_id


def _run_invoice_to_submitted(conn, engagement_id, period_start, period_end):
    cinv_id = create_consultant_invoice(
        conn, engagement_id, period_start, period_end, created_by=TAG)
    submit_consultant_invoice(conn, cinv_id, TAG)
    return cinv_id


def seed_consultants(conn):
    """Insert the three sample consultants and their engagements.
    Returns (consultants, engagements)."""
    ensure_consultant_tables(conn)
    ensure_approval_tables(conn)
    _ensure_ap_tables(conn)
    _seed_approval_rule(conn)

    consultants = engagements = 0

    # --- Consultant A: external, full lifecycle through to a paid AP invoice ---
    supplier_id = _first_supplier_id(conn)
    a_id = create_consultant(
        conn, "Meridian Consulting Group", supplier_id=supplier_id,
        default_hourly_rate=175.00, specialty="ERP Implementation",
        email="engagements@meridianconsulting.example",
        phone_number="555-0142", created_by=TAG,
    )
    consultants += 1
    eng_a = create_engagement(
        conn, a_id, dept_id=_dept_id(conn, "Information"),
        title="Q3 ERP Migration Support",
        purpose="Data migration and cutover support for the ERP rollout.",
        start_date=_d(-60), end_date=_d(0), default_hourly_rate=None,
        requested_by=TAG, created_by=TAG,
    )
    engagements += 1
    activate_engagement(conn, eng_a)
    add_time_entry(conn, eng_a, _d(-50), 8, description="Cutover planning workshop", created_by=TAG)
    add_time_entry(conn, eng_a, _d(-40), 6, description="Legacy data mapping", created_by=TAG)
    add_time_entry(conn, eng_a, _d(-30), 5, description="Go-live support", created_by=TAG)
    add_charge(conn, eng_a, _d(-50), "Travel", 450.00, "Flights + mileage", created_by=TAG)
    add_charge(conn, eng_a, _d(-40), "Materials", 120.00, "Printed training materials", created_by=TAG)
    add_charge(conn, eng_a, _d(-30), "Software/Tools", 89.99, "Migration utility license", created_by=TAG)
    _run_invoice_to_approved_and_paid(conn, eng_a, _d(-60), _d(0))

    # --- Consultant B: internal-style contract labor, invoice left pending ---
    hourly = _hourly_person(conn)
    if hourly:
        b_name = f"{hourly['first_name']} {hourly['last_name']} (Contract)"
        b_people_id = hourly['people_id']
        b_rate = round((hourly['pay_rate'] or 40.0) + 15, 2)
    else:
        b_name = "Contract Labor — Unassigned"
        b_people_id = None
        b_rate = 95.00
    b_id = create_consultant(
        conn, b_name, people_id=b_people_id, default_hourly_rate=b_rate,
        specialty="Production Support", email="", phone_number="",
        notes=("Linked to an existing hourly employee." if hourly else
               "No hourly employee found — run seed_sample_payroll first"
               " to link this to a real person."),
        created_by=TAG,
    )
    consultants += 1
    eng_b = create_engagement(
        conn, b_id, dept_id=_dept_id(conn, "Production"),
        title="Production Line Changeover Support",
        purpose="Extra shop-floor hands during the Q3 line changeover.",
        start_date=_d(-20), end_date=_d(-5), default_hourly_rate=None,
        requested_by=TAG, created_by=TAG,
    )
    engagements += 1
    activate_engagement(conn, eng_b)
    add_time_entry(conn, eng_b, _d(-18), 8, hourly_rate=b_rate,
                    description="Line reconfiguration", created_by=TAG)
    add_time_entry(conn, eng_b, _d(-17), 4, hourly_rate=b_rate,
                    description="Operator training", created_by=TAG)
    add_charge(conn, eng_b, _d(-18), "Lodging", 150.00, "Overnight stay near plant", created_by=TAG)
    _run_invoice_to_submitted(conn, eng_b, _d(-20), _d(-5))

    # --- Consultant C: ad hoc, no linked supplier/people, no default rate
    # anywhere — one time entry has no resolvable rate, left un-invoiced to
    # demonstrate create_consultant_invoice's guard. ---
    c_id = create_consultant(
        conn, "Independent Contractor — J. Whitfield",
        specialty="Safety & Compliance", created_by=TAG,
    )
    consultants += 1
    eng_c = create_engagement(
        conn, c_id, dept_id=_dept_id(conn, "Quality"),
        title="Facility Safety Audit",
        purpose="Independent third-party safety audit of the main facility.",
        start_date=_d(-10), end_date=_d(0),
        requested_by=TAG, created_by=TAG,
    )
    engagements += 1
    activate_engagement(conn, eng_c)
    add_time_entry(conn, eng_c, _d(-9), 6, hourly_rate=90.00,
                    description="On-site walkthrough (rate agreed by email)", created_by=TAG)
    add_time_entry(conn, eng_c, _d(-8), 3,
                    description="Report writing — rate not yet agreed", created_by=TAG)
    add_charge(conn, eng_c, _d(-9), "Other", 75.00, "PPE rental", created_by=TAG)

    return consultants, engagements


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed sample Consultant Time & Charges data.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample data, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample data only (no seeding)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        ensure_consultant_tables(conn)
        if args.remove or args.reset:
            eng_n, cons_n = remove_sample(conn)
            conn.commit()
            print(f"removed {eng_n} sample engagements ({cons_n} consultants)")
            if args.remove:
                return

        if sample_present(conn):
            print("Sample consultant data already present; use --reset to recreate.")
            return

        cons_n, eng_n = seed_consultants(conn)
        conn.commit()
        print(f"inserted {cons_n} consultants, {eng_n} engagements")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
