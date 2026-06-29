"""seed_sample_engineering.py — sample Engineering data.

Covers: projects, tasks, design reviews (ECRs), and engineering standards.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_engineering            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_engineering --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_engineering --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-ENG-"
TODAY = date.today()
YEAR = TODAY.year


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_project (
            id SERIAL PRIMARY KEY,
            project_number TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            product_id INTEGER,
            engineer TEXT DEFAULT '',
            start_date TEXT DEFAULT '',
            due_date TEXT,
            status TEXT DEFAULT 'planning',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_task (
            id SERIAL PRIMARY KEY,
            project_id INTEGER,
            task_name TEXT NOT NULL,
            assigned_to TEXT DEFAULT '',
            due_date TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_design_review (
            id SERIAL PRIMARY KEY,
            ecr_number TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            product_id INTEGER,
            project_id INTEGER,
            requested_by TEXT DEFAULT '',
            review_date TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_standard (
            id SERIAL PRIMARY KEY,
            standard_number TEXT DEFAULT '',
            title TEXT NOT NULL,
            category TEXT DEFAULT '',
            version TEXT DEFAULT '',
            status TEXT DEFAULT 'Active',
            review_date TEXT,
            description TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

PROJECTS = [
    # (proj_num, title, engineer, start_ago, due_offset, status)
    (f"{TAG}PROJ-{YEAR}-0001", "Next-Gen Drive Shaft Redesign",       "Sarah Chen",     -120, 60,  "in_progress"),
    (f"{TAG}PROJ-{YEAR}-0002", "Weight Reduction Initiative — Frame",  "Raj Patel",      -90,  30,  "in_progress"),
    (f"{TAG}PROJ-{YEAR}-0003", "Automated Assembly Fixture Design",    "Sarah Chen",     -45,  90,  "planning"),
    (f"{TAG}PROJ-{YEAR}-0004", "Hydraulic System Upgrade v2",         "Wei Zhang",      -180, -10, "on_hold"),
    (f"{TAG}PROJ-{YEAR}-0005", "Laser Cutter Integration Study",      "Raj Patel",      -200, -30, "completed"),
    (f"{TAG}PROJ-{YEAR}-0006", "New Product Line — Compact Module",   "Wei Zhang",       -30, 120, "planning"),
]


def _seed_projects(conn):
    for pnum, title, engineer, start_ago, due_off, status in PROJECTS:
        if conn.execute("SELECT 1 FROM eng_project WHERE project_number=%s", (pnum,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO eng_project"
            " (project_number, title, product_id, engineer, start_date, due_date, status, notes)"
            " VALUES (%s,%s,NULL,%s,%s,%s,%s,'Sample data')",
            (pnum, title, engineer, _d(start_ago), _d(start_ago + due_off), status),
        )
    conn.commit()


def _remove_projects(conn):
    rows = conn.execute(
        "SELECT id FROM eng_project WHERE project_number LIKE %s", (f"{TAG}PROJ-%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM eng_task WHERE project_id=%s AND notes='Sample data'", (r["id"],))
        conn.execute("DELETE FROM eng_design_review WHERE project_id=%s AND notes='Sample data'", (r["id"],))
    conn.execute("DELETE FROM eng_project WHERE project_number LIKE %s", (f"{TAG}PROJ-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TASKS = [
    # (proj_num_suffix, task_name, assigned_to, due_offset, priority, status)
    ("0001", "Literature review — shaft fatigue analysis",       "Sarah Chen",  -80,  "high",     "completed"),
    ("0001", "FEA model — torsional stress under peak load",     "Sarah Chen",  -50,  "critical", "completed"),
    ("0001", "Prototype drawing release to shop",                "Raj Patel",    10,  "high",     "in_progress"),
    ("0001", "Material selection sign-off",                      "Wei Zhang",    20,  "medium",   "open"),
    ("0002", "Topology optimization — frame cross-member",       "Raj Patel",   -30,  "high",     "completed"),
    ("0002", "Weight budget review with management",             "Sarah Chen",   15,  "medium",   "in_progress"),
    ("0002", "Supplier RFQ for aluminum extrusions",             "Wei Zhang",    25,  "medium",   "open"),
    ("0003", "Fixture concept sketches",                         "Sarah Chen",   30,  "low",      "in_progress"),
    ("0003", "Interference check with existing tooling",         "Raj Patel",    60,  "medium",   "open"),
    ("0005", "Site survey — laser integration points",           "Wei Zhang",  -190,  "high",     "completed"),
    ("0005", "Integration report final draft",                   "Wei Zhang",  -150,  "high",     "completed"),
]


def _seed_tasks(conn):
    for proj_suffix, task_name, assigned_to, due_off, priority, status in TASKS:
        proj_num = f"{TAG}PROJ-{YEAR}-{proj_suffix}"
        proj = conn.execute(
            "SELECT id FROM eng_project WHERE project_number=%s", (proj_num,)
        ).fetchone()
        if not proj:
            continue
        if conn.execute(
            "SELECT 1 FROM eng_task WHERE project_id=%s AND task_name=%s",
            (proj["id"], task_name)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO eng_task"
            " (project_id, task_name, assigned_to, due_date, priority, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,'Sample data')",
            (proj["id"], task_name, assigned_to, _d(due_off), priority, status),
        )
    conn.commit()


def _remove_tasks(conn):
    conn.execute("DELETE FROM eng_task WHERE notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Engineering Design Reviews (ECRs)
# ---------------------------------------------------------------------------

ECRS = [
    # (ecr_num, title, proj_suffix, requested_by, review_ago, status)
    (f"{TAG}ECR-{YEAR}-0001", "ECR: Drive Shaft Material Change to 4340 Steel",
     "0001", "Sarah Chen", -60, "approved"),
    (f"{TAG}ECR-{YEAR}-0002", "ECR: Frame Wall Thickness Reduction",
     "0002", "Raj Patel", -45, "pending"),
    (f"{TAG}ECR-{YEAR}-0003", "ECR: Fixture Quick-Change Clamp Design",
     "0003", "Sarah Chen", -7, "draft"),
    (f"{TAG}ECR-{YEAR}-0004", "ECR: Hydraulic Pump Relocation",
     "0004", "Wei Zhang", -30, "rejected"),
    (f"{TAG}ECR-{YEAR}-0005", "ECR: Laser Safety Interlock Wiring Revision",
     "0005", "Wei Zhang", -180, "approved"),
    (f"{TAG}ECR-{YEAR}-0006", "ECR: Add RFID Tracking to Compact Module",
     "0006", "Raj Patel", -2, "draft"),
]


def _seed_ecrs(conn):
    for ecr_num, title, proj_suffix, requested_by, review_ago, status in ECRS:
        if conn.execute("SELECT 1 FROM eng_design_review WHERE ecr_number=%s", (ecr_num,)).fetchone():
            continue
        proj_num = f"{TAG}PROJ-{YEAR}-{proj_suffix}"
        proj = conn.execute(
            "SELECT id FROM eng_project WHERE project_number=%s", (proj_num,)
        ).fetchone()
        proj_id = proj["id"] if proj else None
        conn.execute(
            "INSERT INTO eng_design_review"
            " (ecr_number, title, product_id, project_id, requested_by, review_date, status, notes)"
            " VALUES (%s,%s,NULL,%s,%s,%s,%s,'Sample data')",
            (ecr_num, title, proj_id, requested_by, _d(review_ago), status),
        )
    conn.commit()


def _remove_ecrs(conn):
    conn.execute("DELETE FROM eng_design_review WHERE ecr_number LIKE %s", (f"{TAG}ECR-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Engineering Standards
# ---------------------------------------------------------------------------

STANDARDS = [
    # (std_num, title, category, version, status, review_ago)
    ("ISO 9001:2015", "Quality Management Systems — Requirements", "ISO", "2015", "Active", -365),
    ("ANSI B11.1-2009", "Safety Requirements for Mechanical Power Presses", "ANSI", "2009", "Active", -180),
    ("ASME Y14.5-2018", "Dimensioning and Tolerancing (GD&T)", "ASME", "2018", "Active", -90),
    ("IEEE 519-2014", "Harmonic Control in Electric Power Systems", "IEEE", "2014", "Active", -270),
    ("OSHA 1910.147", "Lockout/Tagout — Control of Hazardous Energy", "OSHA", "2019", "Active", -60),
    ("INT-WI-CNC-04", "CNC Machining Work Instruction — Setup & Operation", "Internal", "Rev 3", "Active", -30),
    ("INT-QP-INS-01", "Incoming Inspection Procedure", "Internal", "Rev 7", "Under Review", -15),
    ("ANSI B11.19-2019", "Performance Requirements for Safeguarding Machinery", "ANSI", "2019", "Active", -120),
]


def _seed_standards(conn):
    for std_num, title, cat, version, status, review_ago in STANDARDS:
        if conn.execute(
            "SELECT 1 FROM eng_standard WHERE standard_number=%s AND created_by='seed'",
            (std_num,)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO eng_standard"
            " (standard_number, title, category, version, status,"
            "  review_date, description, notes, created_by, created_date)"
            " VALUES (%s,%s,%s,%s,%s,%s,'',' Sample data','seed',%s)",
            (std_num, title, cat, version, status, _d(review_ago), TODAY.isoformat()),
        )
    conn.commit()


def _remove_standards(conn):
    conn.execute("DELETE FROM eng_standard WHERE created_by='seed'")
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_projects(conn)
    _seed_tasks(conn)
    _seed_ecrs(conn)
    _seed_standards(conn)
    print("Engineering sample data seeded.")


def remove(conn):
    _remove_ecrs(conn)
    _remove_tasks(conn)
    _remove_projects(conn)
    _remove_standards(conn)
    print("Engineering sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Engineering sample data")
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


