"""seed_sample_personnel.py — sample Personnel data.

Covers: job titles (position table) for all 46 sample employees, and
four weeks of time-clock entries for hourly staff (used by Payroll).
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_personnel            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_personnel --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_personnel --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-PERS-"
TODAY = date.today()


def _working_days_back(n):
    """Return n most-recent working days (Mon–Fri) in chronological order."""
    days = []
    d = TODAY - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def _ensure_tables(conn):
    conn.execute("ALTER TABLE position ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.execute("ALTER TABLE time_clock ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.commit()


# ---------------------------------------------------------------------------
# Job titles  (position)
# ---------------------------------------------------------------------------

# (employee_id_num, job_title)
POSITIONS = [
    (1001, "Chief Executive Officer"),
    (1002, "Quality Assurance Manager"),
    (1003, "Quality Control Inspector"),
    (1004, "Marketing Director"),
    (1005, "Marketing Specialist"),
    (1006, "Marketing Coordinator"),
    (1007, "Digital Marketing Analyst"),
    (1008, "Production Manager"),
    (1009, "Production Supervisor"),
    (1010, "CNC Machinist"),
    (1011, "Quality Inspector"),
    (1012, "Machine Operator"),
    (1013, "Assembly Operator"),
    (1014, "Assembly Operator"),
    (1015, "Accounts Receivable Specialist"),
    (1016, "IT Systems Administrator"),
    (1017, "Customer Service Representative"),
    (1018, "Sales Representative"),
    (1019, "Customer Service Representative"),
    (1020, "Customer Service Lead"),
    (1021, "Mechanical Engineer"),
    (1022, "Design Engineer"),
    (1023, "Maintenance Mechanic"),
    (1024, "Maintenance Technician"),
    (1025, "Account Executive"),
    (1026, "Sales Representative"),
    (1027, "Purchasing Manager"),
    (1028, "HR Generalist"),
    (1029, "Accounts Payable Specialist"),
    (1030, "Staff Accountant"),
    (1031, "Senior Accountant"),
    (1032, "Accounting Clerk"),
    (1033, "Customer Service Representative"),
    (1034, "Product Design Engineer"),
    (1035, "Financial Analyst"),
    (1036, "Finance Manager"),
    (1037, "Budget Analyst"),
    (1038, "Legal Counsel"),
    (1039, "Paralegal"),
    (1040, "Compliance Officer"),
    (1041, "Risk Manager"),
    (1042, "Risk Analyst"),
    (1043, "Risk Analyst"),
    (1044, "Warehouse Manager"),
    (1045, "Warehouse Supervisor"),
    (1046, "Warehouse Associate"),
]


def _seed_positions(conn):
    for emp_id_num, title in POSITIONS:
        row = conn.execute(
            "SELECT id FROM people WHERE employee_id=%s", (emp_id_num,)
        ).fetchone()
        if not row:
            continue
        pid = row["id"]
        existing = conn.execute(
            "SELECT created_by FROM position WHERE people_id=%s", (pid,)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            f"INSERT INTO position (people_id, job_title, created_by) VALUES (%s,%s,'{TAG}')",
            (pid, title),
        )
    conn.commit()


def _remove_positions(conn):
    conn.execute(f"DELETE FROM position WHERE created_by='{TAG}'")
    conn.commit()


# ---------------------------------------------------------------------------
# Time clock entries  (time_clock)
# ---------------------------------------------------------------------------

# (employee_id_num, clock_in_hhmm, clock_out_hhmm)
HOURLY_STAFF = [
    (1009, "07:02", "15:35"),
    (1010, "07:15", "15:48"),
    (1011, "07:08", "15:42"),
    (1012, "07:20", "15:55"),
    (1013, "07:05", "15:38"),
    (1015, "07:30", "16:02"),
    (1016, "07:25", "16:00"),
    (1023, "07:10", "15:45"),
    (1024, "07:18", "15:50"),
    (1029, "07:28", "16:05"),
]


def _seed_timeclock(conn):
    work_days = _working_days_back(20)

    for emp_id_num, ci_time, co_time in HOURLY_STAFF:
        row = conn.execute(
            "SELECT id FROM people WHERE employee_id=%s", (emp_id_num,)
        ).fetchone()
        if not row:
            continue
        pid = row["id"]
        ci_h, ci_m = int(ci_time[:2]), int(ci_time[3:])
        co_h, co_m = int(co_time[:2]), int(co_time[3:])
        hours = round((co_h * 60 + co_m - ci_h * 60 - ci_m) / 60, 2)

        for work_day in work_days:
            ds = work_day.isoformat()
            ci_str = f"{ds} {ci_time}:00"
            co_str = f"{ds} {co_time}:00"
            if conn.execute(
                "SELECT 1 FROM time_clock WHERE people_id=%s AND clock_in=%s",
                (pid, ci_str)
            ).fetchone():
                continue
            conn.execute(
                "INSERT INTO time_clock"
                " (people_id, clock_in, clock_out, hours_worked, notes, created_by)"
                f" VALUES (%s,%s,%s,%s,'Sample data','{TAG}')",
                (pid, ci_str, co_str, hours),
            )
    conn.commit()


def _remove_timeclock(conn):
    conn.execute(
        f"DELETE FROM time_clock WHERE created_by='{TAG}' AND notes='Sample data'"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_positions(conn)
    _seed_timeclock(conn)
    print("Personnel sample data seeded.")


def remove(conn):
    _remove_timeclock(conn)
    _remove_positions(conn)
    print("Personnel sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Personnel sample data")
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


