"""seed_sample_quality.py — sample QA data.

Covers: NCRs, CAPAs, audits, supplier quality, inspections, and defects.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_quality            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_quality --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_quality --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-QA-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_ncr (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, source TEXT DEFAULT '',
            severity TEXT DEFAULT 'Minor', product TEXT DEFAULT '',
            detected_date TEXT DEFAULT '', disposition TEXT DEFAULT 'Pending',
            owner TEXT DEFAULT '', status TEXT DEFAULT 'Open',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT '',
            closed_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_capa (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            capa_type TEXT DEFAULT 'Corrective', ncr_ref TEXT DEFAULT '',
            owner TEXT DEFAULT '', due_date TEXT DEFAULT '',
            completed_date TEXT DEFAULT '', status TEXT DEFAULT 'Open',
            action_plan TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_audit (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            audit_type TEXT DEFAULT '', auditor TEXT DEFAULT '',
            scheduled_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            result TEXT DEFAULT '', status TEXT DEFAULT 'Scheduled',
            findings TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_supplier (
            id SERIAL PRIMARY KEY, supplier TEXT NOT NULL,
            material TEXT DEFAULT '', rating TEXT DEFAULT 'B',
            ppm TEXT DEFAULT '0', last_audit TEXT DEFAULT '',
            status TEXT DEFAULT 'Pending', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_inspection (
            id SERIAL PRIMARY KEY, insp_number TEXT NOT NULL UNIQUE,
            product_id INTEGER, wo_id INTEGER,
            insp_date TEXT DEFAULT '', inspector TEXT DEFAULT '',
            result TEXT DEFAULT 'pending', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_defect (
            id SERIAL PRIMARY KEY, insp_id INTEGER NOT NULL,
            defect_type TEXT DEFAULT '', severity TEXT DEFAULT 'minor',
            description TEXT NOT NULL, resolved INTEGER DEFAULT 0,
            created_by TEXT DEFAULT ''
        )
    """)
    for tbl in ("qa_ncr", "qa_capa", "qa_audit", "qa_supplier", "qa_inspection", "qa_defect"):
        conn.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.commit()


# ---------------------------------------------------------------------------
# Non-Conformance Reports
# ---------------------------------------------------------------------------

NCRS = [
    # (title, source, severity, product, det_ago, disposition, owner, status)
    ("Surface finish below spec on Frame Assembly",
     "In-Process", "Major", "Frame Assembly", -5, "Rework", "Maria Santos", "Under Review"),
    ("Dimensional deviation — Shaft Collar OD",
     "Final", "Minor", "Shaft Collar", -12, "Use As-Is", "James Kim", "Dispositioned"),
    ("Supplier delivered wrong grade fasteners",
     "Incoming", "Critical", "M10 Hex Bolt", -2, "Return", "Maria Santos", "Open"),
    ("Customer returned batch with paint defects",
     "Customer", "Major", "Painted Housing", -20, "Scrap", "James Kim", "Closed"),
    ("Weld porosity detected on bracket",
     "In-Process", "Minor", "Support Bracket", -7, "Rework", "Lisa Novak", "Under Review"),
    ("Missing certification docs on valve lot",
     "Incoming", "Minor", "Safety Valve", -3, "Pending", "Lisa Novak", "Open"),
    ("Gauge reading out of calibration tolerance",
     "Audit", "Major", "Gauge Assembly", -15, "Rework", "Maria Santos", "Closed"),
    ("Contamination found in lubrication oil batch",
     "In-Process", "Critical", "Hydraulic Oil", -1, "Scrap", "James Kim", "Open"),
]


def _seed_ncrs(conn):
    for title, source, severity, product, det_ago, disposition, owner, status in NCRS:
        if conn.execute(f"SELECT 1 FROM qa_ncr WHERE title=%s AND created_by='{TAG}'",
                        (title,)).fetchone():
            continue
        closed = _d(det_ago + 7) if status == 'Closed' else ''
        conn.execute(
            "INSERT INTO qa_ncr"
            " (title, source, severity, product, detected_date, disposition,"
            "  owner, status, notes, created_by, closed_date)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}',%s)",
            (title, source, severity, product, _d(det_ago),
             disposition, owner, status, closed),
        )
    conn.commit()


def _remove_ncrs(conn):
    conn.execute(f"DELETE FROM qa_ncr WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# CAPAs
# ---------------------------------------------------------------------------

CAPAS = [
    # (title, capa_type, ncr_ref, owner, due_offset, action_plan, comp_offset, status)
    ("Update incoming inspection for fastener grade",
     "Corrective", "NCR-003", "Maria Santos", 14,
     "Revise incoming inspection checklist to verify material grade cert against PO.",
     None, "In Progress"),
    ("Re-train welding team on porosity prevention",
     "Corrective", "NCR-005", "Lisa Novak", 21,
     "Schedule hands-on training session; update weld procedure WP-07.",
     None, "Open"),
    ("Implement pre-shipment paint adhesion test",
     "Preventive", "NCR-004", "James Kim", 7,
     "Add adhesion pull test to pre-ship QC checklist and document results.",
     -3, "Closed"),
    ("Calibration frequency review for all gauges",
     "Preventive", "NCR-007", "Maria Santos", 30,
     "Audit all gauges; reduce calibration interval from 12 to 6 months.",
     None, "In Progress"),
    ("Supplier audit for Bolt Vendor — Grade Compliance",
     "Corrective", "NCR-003", "Lisa Novak", 45,
     "Schedule on-site audit; require updated material certs with every shipment.",
     None, "Open"),
    ("Review lubrication oil receiving procedure",
     "Corrective", "NCR-008", "James Kim", 5,
     "Add batch sampling to receiving; partner with lab for contamination testing.",
     None, "Open"),
]


def _seed_capas(conn):
    for title, ctype, ncr_ref, owner, due_off, plan, comp_off, status in CAPAS:
        if conn.execute(f"SELECT 1 FROM qa_capa WHERE title=%s AND created_by='{TAG}'",
                        (title,)).fetchone():
            continue
        completed = _d(comp_off) if comp_off is not None else ''
        conn.execute(
            "INSERT INTO qa_capa"
            " (title, capa_type, ncr_ref, owner, due_date, completed_date,"
            "  status, action_plan, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'{TAG}')",
            (title, ctype, ncr_ref, owner, _d(due_off), completed, status, plan),
        )
    conn.commit()


def _remove_capas(conn):
    conn.execute(f"DELETE FROM qa_capa WHERE created_by='{TAG}'")
    conn.commit()


# ---------------------------------------------------------------------------
# Quality Audits
# ---------------------------------------------------------------------------

AUDITS = [
    # (title, audit_type, auditor, sched_ago, comp_ago, result, status, findings)
    ("ISO 9001 Surveillance Audit Q2", "ISO 9001", "Apex Registrar",
     -60, -58, "Minor findings — 2 observations", "Closed",
     "Two observation-level findings on document control; no non-conformities."),
    ("Production Process Audit — CNC", "Process", "Lisa Novak",
     -30, -28, "Passed", "Closed",
     "Process adheres to work instructions; recommended updating WI-CNC-04."),
    ("Supplier Audit — Metal Fab Co.", "Supplier", "Maria Santos",
     -14, -12, "Conditional pass", "Follow-up",
     "3 minor findings; re-audit in 60 days."),
    ("Internal Audit — Receiving", "Internal", "James Kim",
     -7, -5, "Passed with comments", "Complete",
     "Process compliant; update inspection forms recommended."),
    ("Product Audit — Shaft Collar Lot", "Product", "Lisa Novak",
     -3, None, "", "In Progress", ""),
    ("Q3 ISO 9001 Internal Audit", "ISO 9001", "Maria Santos",
     10, None, "", "Scheduled", ""),
    ("Welding Process Audit", "Process", "James Kim",
     20, None, "", "Scheduled", ""),
]


def _seed_audits(conn):
    for title, atype, auditor, sched_ago, comp_ago, result, status, findings in AUDITS:
        if conn.execute(f"SELECT 1 FROM qa_audit WHERE title=%s AND created_by='{TAG}'",
                        (title,)).fetchone():
            continue
        comp = _d(comp_ago) if comp_ago is not None else ''
        conn.execute(
            "INSERT INTO qa_audit"
            " (title, audit_type, auditor, scheduled_date, completed_date,"
            "  result, status, findings, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'{TAG}')",
            (title, atype, auditor, _d(sched_ago), comp, result, status, findings),
        )
    conn.commit()


def _remove_audits(conn):
    conn.execute(f"DELETE FROM qa_audit WHERE created_by='{TAG}'")
    conn.commit()


# ---------------------------------------------------------------------------
# Supplier Quality
# ---------------------------------------------------------------------------

SUPPLIERS = [
    # (supplier, material, rating, ppm, last_audit_ago, status)
    ("Metal Fab Co.",        "Steel Sheet 1018",     "B", "850",  -14,  "Conditional"),
    ("FastPro Supply",       "M10 Hex Bolt Grade 8", "C", "3200", -5,   "Probation"),
    ("Allied Polymers",      "ABS Resin",            "A", "120",  -90,  "Approved"),
    ("Acme Electronics",     "PCB Assemblies",       "A", "45",   -180, "Approved"),
    ("PaintTech Solutions",  "Epoxy Primer",         "B", "650",  -45,  "Approved"),
    ("Valley Hydraulics",    "Hydraulic Hose",       "A", "200",  -60,  "Approved"),
    ("New Era Bearings",     "Ball Bearing 6205",    "B", "500",  -120, "Approved"),
    ("Generic Import Co.",   "Misc Hardware",        "D", "8500", -30,  "Disqualified"),
]


def _seed_suppliers(conn):
    for supplier, material, rating, ppm, audit_ago, status in SUPPLIERS:
        if conn.execute(f"SELECT 1 FROM qa_supplier WHERE supplier=%s AND material=%s AND created_by='{TAG}'",
                        (supplier, material)).fetchone():
            continue
        conn.execute(
            "INSERT INTO qa_supplier"
            " (supplier, material, rating, ppm, last_audit, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (supplier, material, rating, ppm, _d(audit_ago), status),
        )
    conn.commit()


def _remove_suppliers(conn):
    conn.execute(f"DELETE FROM qa_supplier WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Inspections + Defects
# ---------------------------------------------------------------------------

INSPECTIONS = [
    # (insp_num, insp_date_ago, inspector, result, notes)
    (f"{TAG}INS-001", -10, "Lisa Novak",   "passed",  "All dimensions within spec"),
    (f"{TAG}INS-002",  -8, "James Kim",    "failed",  "Two surface finish failures; see defects"),
    (f"{TAG}INS-003",  -5, "Maria Santos", "passed",  "Batch 2026-B lot acceptance inspection"),
    (f"{TAG}INS-004",  -3, "Lisa Novak",   "on_hold", "Awaiting material certification docs"),
    (f"{TAG}INS-005",  -1, "James Kim",    "pending", "In-process inspection — CNC run #48"),
    (f"{TAG}INS-006",   0, "Maria Santos", "pending", "Final inspection — Valve Assembly"),
]

DEFECTS = [
    # (insp_num_suffix, defect_type, severity, description, resolved)
    ("INS-002", "Surface Finish",  "major",    "Ra > 3.2 µm on inner bore — exceeds drawing tolerance",  1),
    ("INS-002", "Dimensional",     "minor",    "OD 0.003\" over nominal; within functional tolerance",    1),
    ("INS-004", "Documentation",   "minor",    "Missing heat number on material cert",                    0),
]


def _seed_inspections(conn):
    for insp_num, date_ago, inspector, result, notes in INSPECTIONS:
        if conn.execute("SELECT 1 FROM qa_inspection WHERE insp_number=%s", (insp_num,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO qa_inspection"
            " (insp_number, product_id, wo_id, insp_date, inspector, result, notes, created_by)"
            f" VALUES (%s,NULL,NULL,%s,%s,%s,%s,'{TAG}')",
            (insp_num, _d(date_ago), inspector, result, notes),
        )
    conn.commit()

    for suffix, dtype, severity, description, resolved in DEFECTS:
        insp_num = f"{TAG}{suffix}"
        row = conn.execute("SELECT id FROM qa_inspection WHERE insp_number=%s", (insp_num,)).fetchone()
        if not row:
            continue
        insp_id = row["id"]
        if conn.execute("SELECT 1 FROM qa_defect WHERE insp_id=%s AND description=%s",
                        (insp_id, description)).fetchone():
            continue
        conn.execute(
            "INSERT INTO qa_defect (insp_id, defect_type, severity, description, resolved, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,'{TAG}')",
            (insp_id, dtype, severity, description, resolved),
        )
    conn.commit()


def _remove_inspections(conn):
    rows = conn.execute(
        "SELECT id FROM qa_inspection WHERE insp_number LIKE %s", (f"{TAG}INS-%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM qa_defect WHERE insp_id=%s", (r["id"],))
    conn.execute("DELETE FROM qa_inspection WHERE insp_number LIKE %s", (f"{TAG}INS-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_ncrs(conn)
    _seed_capas(conn)
    _seed_audits(conn)
    _seed_suppliers(conn)
    _seed_inspections(conn)
    print("Quality sample data seeded.")


def remove(conn):
    _remove_inspections(conn)
    _remove_suppliers(conn)
    _remove_audits(conn)
    _remove_capas(conn)
    _remove_ncrs(conn)
    print("Quality sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Quality sample data")
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


