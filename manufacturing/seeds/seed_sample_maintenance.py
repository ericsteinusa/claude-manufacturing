"""seed_sample_maintenance.py — sample data for Maintenance.

Covers: mechanics, equipment, PM schedules, work orders, inspections,
downtime events, and spare parts.  All rows are tagged with the ``SMPL-MAINT-``
prefix so they can be removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_maintenance            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_maintenance --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_maintenance --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-MAINT-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_mechanic (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, trade TEXT DEFAULT '',
            shift TEXT DEFAULT 'Day', phone TEXT DEFAULT '',
            status TEXT DEFAULT 'Active', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_equipment (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, asset_tag TEXT DEFAULT '',
            location TEXT DEFAULT '', manufacturer TEXT DEFAULT '',
            install_date TEXT DEFAULT '', last_service TEXT DEFAULT '',
            status TEXT DEFAULT 'Operational', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_work_order (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, equipment TEXT DEFAULT '',
            work_type TEXT DEFAULT '', priority TEXT DEFAULT 'Medium',
            assigned_to TEXT DEFAULT '', requested_date TEXT DEFAULT '',
            due_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            status TEXT DEFAULT 'Open', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_schedule (
            id SERIAL PRIMARY KEY, task TEXT NOT NULL, equipment TEXT DEFAULT '',
            frequency TEXT DEFAULT '', assigned_to TEXT DEFAULT '',
            last_done TEXT DEFAULT '', next_due TEXT DEFAULT '',
            status TEXT DEFAULT 'Scheduled', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_inspection (
            id SERIAL PRIMARY KEY, area TEXT NOT NULL,
            inspection_type TEXT DEFAULT '', inspector TEXT DEFAULT '',
            scheduled_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            result TEXT DEFAULT '', status TEXT DEFAULT 'Scheduled',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_downtime (
            id SERIAL PRIMARY KEY, equipment TEXT NOT NULL,
            reason TEXT DEFAULT '', category TEXT DEFAULT '',
            down_date TEXT DEFAULT '', hours TEXT DEFAULT '',
            cost REAL DEFAULT 0, status TEXT DEFAULT 'Ongoing',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maint_part (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            part_number TEXT DEFAULT '', category TEXT DEFAULT '',
            location TEXT DEFAULT '', quantity TEXT DEFAULT '0',
            reorder_level TEXT DEFAULT '5', unit_cost REAL DEFAULT 0,
            status TEXT DEFAULT 'In Stock', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """)
    # Backfill created_by on pre-existing tables that may lack it
    for tbl in ("maint_mechanic", "maint_equipment", "maint_work_order",
                "maint_schedule", "maint_inspection", "maint_downtime", "maint_part"):
        conn.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.commit()


# ---------------------------------------------------------------------------
# Mechanics
# ---------------------------------------------------------------------------

MECHANICS = [
    # (name, trade, shift, phone, status)
    ("SMPL-MAINT-Bob Harmon",    "Mechanical",  "Day",   "555-2101", "Active"),
    ("SMPL-MAINT-Denise Fowler", "Electrical",  "Day",   "555-2102", "Active"),
    ("SMPL-MAINT-Carlos Vega",   "Hydraulics",  "Swing", "555-2103", "Active"),
    ("SMPL-MAINT-Tim Okafor",    "HVAC",        "Day",   "555-2104", "Active"),
    ("SMPL-MAINT-Lynn Marsh",    "Welding",     "Night", "555-2105", "Active"),
    ("SMPL-MAINT-Ed Paulson",    "General",     "Day",   "555-2106", "On Leave"),
]


def _seed_mechanics(conn):
    for name, trade, shift, phone, status in MECHANICS:
        if conn.execute("SELECT 1 FROM maint_mechanic WHERE name=%s", (name,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO maint_mechanic (name, trade, shift, phone, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (name, trade, shift, phone, status),
        )
    conn.commit()


def _remove_mechanics(conn):
    conn.execute("DELETE FROM maint_mechanic WHERE name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

EQUIPMENT = [
    # (name, asset_tag, location, manufacturer, install_ago, last_svc_ago, status)
    ("CNC Mill #1",        f"{TAG}EQ-001", "Shop Floor A", "Haas",      -1825, -30,  "Operational"),
    ("Hydraulic Press",    f"{TAG}EQ-002", "Shop Floor B", "Enerpac",   -1460, -90,  "Operational"),
    ("Air Compressor",     f"{TAG}EQ-003", "Mechanical Rm","Ingersoll",  -730, -14,  "Needs Service"),
    ("Conveyor Belt #1",   f"{TAG}EQ-004", "Assembly Line","Hytrol",    -1095, -60,  "Operational"),
    ("MIG Welder",         f"{TAG}EQ-005", "Fab Room",     "Miller",     -365,  -7,  "Operational"),
    ("Laser Cutter",       f"{TAG}EQ-006", "Shop Floor A", "Trumpf",    -2190, -45,  "Under Repair"),
    ("Overhead Crane",     f"{TAG}EQ-007", "Warehouse",    "Gorbel",    -2920, -120, "Operational"),
    ("Industrial Chiller", f"{TAG}EQ-008", "Mechanical Rm","Carrier",    -548, -20,  "Down"),
    ("Injection Molder",   f"{TAG}EQ-009", "Shop Floor B", "Arburg",    -1642, -30,  "Operational"),
    ("Paint Booth",        f"{TAG}EQ-010", "Finishing",    "Binks",      -912, -180, "Needs Service"),
]


def _seed_equipment(conn):
    for name, tag, loc, mfr, inst_ago, svc_ago, status in EQUIPMENT:
        if conn.execute("SELECT 1 FROM maint_equipment WHERE asset_tag=%s", (tag,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO maint_equipment "
            "(name, asset_tag, location, manufacturer, install_date, last_service, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (name, tag, loc, mfr, _d(inst_ago), _d(svc_ago), status),
        )
    conn.commit()


def _remove_equipment(conn):
    conn.execute("DELETE FROM maint_equipment WHERE asset_tag LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------

WORK_ORDERS = [
    # (title, equipment, work_type, priority, assigned_to,
    #  req_ago, due_offset, completed_offset, status)
    # due_offset/completed_offset are DURATIONS added to req_ago, not
    # absolute day counts from today -- for a "Completed" WO whose due/
    # completed date is N days ago, the offset must be (N days ago) -
    # req_ago, not simply -N.
    ("Replace worn bearings on CNC Mill #1", "CNC Mill #1", "Replacement", "High",
     "SMPL-MAINT-Bob Harmon", -3, 4, None, "In Progress"),
    ("Quarterly PM — Hydraulic Press", "Hydraulic Press", "Preventive", "Medium",
     "SMPL-MAINT-Carlos Vega", -7, 0, None, "Assigned"),
    ("Air compressor pressure relief check", "Air Compressor", "Inspection", "High",
     "SMPL-MAINT-Denise Fowler", -1, 2, None, "Open"),
    ("Laser cutter alignment & calibration", "Laser Cutter", "Calibration", "Critical",
     "SMPL-MAINT-Bob Harmon", -2, 1, None, "In Progress"),
    ("Industrial chiller coil cleaning", "Industrial Chiller", "Cleaning", "Critical",
     "SMPL-MAINT-Tim Okafor", -1, 1, None, "Assigned"),
    ("Conveyor belt tension adjustment", "Conveyor Belt #1", "Repair", "Medium",
     "SMPL-MAINT-Bob Harmon", -14, 4, 5, "Completed"),
    ("Paint booth filter replacement", "Paint Booth", "Replacement", "Medium",
     "SMPL-MAINT-Ed Paulson", -5, 3, None, "On Hold"),
    ("Annual overhead crane inspection", "Overhead Crane", "Inspection", "High",
     "SMPL-MAINT-Lynn Marsh", -30, 3, 4, "Completed"),
    ("MIG welder electrode tip replacement", "MIG Welder", "Replacement", "Low",
     "SMPL-MAINT-Carlos Vega", -2, 5, None, "Open"),
    ("Injection molder hydraulic fluid flush", "Injection Molder", "Preventive", "Medium",
     "SMPL-MAINT-Carlos Vega", -10, 5, 6, "Completed"),
]


def _seed_work_orders(conn):
    for (title, equip, wtype, priority, assigned, req_ago, due_off,
         comp_off, status) in WORK_ORDERS:
        if conn.execute(f"SELECT 1 FROM maint_work_order WHERE title=%s AND created_by='{TAG}'",
                        (title,)).fetchone():
            continue
        completed_date = _d(req_ago + comp_off) if comp_off is not None else ''
        conn.execute(
            "INSERT INTO maint_work_order "
            "(title, equipment, work_type, priority, assigned_to, requested_date,"
            " due_date, completed_date, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (title, equip, wtype, priority, assigned, _d(req_ago),
             _d(req_ago + due_off), completed_date, status),
        )
    conn.commit()


def _remove_work_orders(conn):
    conn.execute(f"DELETE FROM maint_work_order WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# PM Schedules
# ---------------------------------------------------------------------------

SCHEDULES = [
    # (task, equipment, frequency, assigned_to, last_ago, next_offset, status)
    # next_offset is a DURATION added to last_ago, not an absolute day count
    # from today -- for an "Overdue" schedule whose next-due date is N days
    # ago, next_offset must be (N days ago) - last_ago, not simply -N.
    ("Lubricate spindle bearings", "CNC Mill #1", "Monthly",
     "SMPL-MAINT-Bob Harmon", -28, 2, "Scheduled"),
    ("Check hydraulic fluid level", "Hydraulic Press", "Weekly",
     "SMPL-MAINT-Carlos Vega", -7, 0, "Due"),
    ("Inspect air filters", "Air Compressor", "Monthly",
     "SMPL-MAINT-Tim Okafor", -45, 30, "Overdue"),
    ("Calibrate laser optics", "Laser Cutter", "Quarterly",
     "SMPL-MAINT-Bob Harmon", -90, 2, "Scheduled"),
    ("Test crane load limit switch", "Overhead Crane", "Semi-Annual",
     "SMPL-MAINT-Lynn Marsh", -180, 1, "Due"),
    ("Replace conveyor belt lacing", "Conveyor Belt #1", "Annual",
     "SMPL-MAINT-Bob Harmon", -365, 5, "Scheduled"),
    ("Clean paint booth exhaust filters", "Paint Booth", "Monthly",
     "SMPL-MAINT-Denise Fowler", -10, 20, "Scheduled"),
    ("Inspect MIG welder gas lines", "MIG Welder", "Weekly",
     "SMPL-MAINT-Carlos Vega", -4, 3, "Scheduled"),
    ("Check chiller refrigerant level", "Industrial Chiller", "Quarterly",
     "SMPL-MAINT-Tim Okafor", -20, 70, "Scheduled"),
    ("Inspect injection molder clamps", "Injection Molder", "Monthly",
     "SMPL-MAINT-Carlos Vega", -30, 0, "Due"),
]


def _seed_schedules(conn):
    for task, equip, freq, assigned, last_ago, next_off, status in SCHEDULES:
        if conn.execute(f"SELECT 1 FROM maint_schedule WHERE task=%s AND created_by='{TAG}'",
                        (task,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO maint_schedule"
            " (task, equipment, frequency, assigned_to, last_done, next_due, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (task, equip, freq, assigned, _d(last_ago), _d(last_ago + next_off), status),
        )
    conn.commit()


def _remove_schedules(conn):
    conn.execute(f"DELETE FROM maint_schedule WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------

INSPECTIONS = [
    # (area, insp_type, inspector, sched_ago, comp_ago, result, status)
    ("Press Area", "Machine Guarding", "SMPL-MAINT-Denise Fowler",
     -30, -29, "All guards in place", "Passed"),
    ("Electrical Panel #3", "Electrical", "SMPL-MAINT-Denise Fowler",
     -14, -13, "Panel overheating", "Failed"),
    ("Welding Station", "Fire Safety", "SMPL-MAINT-Tim Okafor",
     -60, -59, "Passed", "Passed"),
    ("Paint Booth", "Environmental", "SMPL-MAINT-Tim Okafor",
     -7, -6, "Passed with minor notes", "Follow-up"),
    ("Crane Bay", "Lockout/Tagout", "SMPL-MAINT-Lynn Marsh",
     -3, None, "", "Scheduled"),
    ("Assembly Floor", "General", "SMPL-MAINT-Bob Harmon",
     5, None, "", "Scheduled"),
]


def _seed_inspections(conn):
    for area, itype, inspector, sched_ago, comp_ago, result, status in INSPECTIONS:
        if conn.execute(f"SELECT 1 FROM maint_inspection WHERE area=%s AND inspection_type=%s AND created_by='{TAG}'",
                        (area, itype)).fetchone():
            continue
        comp = _d(comp_ago) if comp_ago is not None else ''
        conn.execute(
            "INSERT INTO maint_inspection"
            " (area, inspection_type, inspector, scheduled_date, completed_date,"
            "  result, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (area, itype, inspector, _d(sched_ago), comp, result, status),
        )
    conn.commit()


def _remove_inspections(conn):
    conn.execute(f"DELETE FROM maint_inspection WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Downtime
# ---------------------------------------------------------------------------

DOWNTIME = [
    # (equipment, reason, category, down_ago, hours, cost, status)
    ("Laser Cutter", "Optics misaligned after power surge", "Breakdown",
     -2, "6.5", 1200.00, "Investigating"),
    ("Industrial Chiller", "Refrigerant leak detected", "Breakdown",
     -1, "10.0", 2500.00, "Ongoing"),
    ("CNC Mill #1", "Bearing failure", "Breakdown",
     -30, "8.0", 950.00, "Resolved"),
    ("Conveyor Belt #1", "Scheduled changeover to new product", "Changeover",
     -45, "2.0", 0.00, "Resolved"),
    ("Air Compressor", "Pressure valve failure", "Breakdown",
     -15, "4.0", 480.00, "Resolved"),
    ("Paint Booth", "Exhaust fan motor overheating", "Breakdown",
     -5, "3.0", 320.00, "Investigating"),
]


def _seed_downtime(conn):
    for equip, reason, category, down_ago, hours, cost, status in DOWNTIME:
        if conn.execute(f"SELECT 1 FROM maint_downtime WHERE equipment=%s AND reason=%s AND created_by='{TAG}'",
                        (equip, reason)).fetchone():
            continue
        conn.execute(
            "INSERT INTO maint_downtime"
            " (equipment, reason, category, down_date, hours, cost, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (equip, reason, category, _d(down_ago), hours, cost, status),
        )
    conn.commit()


def _remove_downtime(conn):
    conn.execute(f"DELETE FROM maint_downtime WHERE created_by='{TAG}' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Spare Parts
# ---------------------------------------------------------------------------

PARTS = [
    # (name, part_number, category, location, qty, reorder, unit_cost, status)
    ("V-Belt A78",              f"{TAG}PRT-001", "Belts",      "Bin A-12", "6",  "3",   12.50,  "In Stock"),
    ("Ball Bearing 6205",       f"{TAG}PRT-002", "Bearings",   "Bin B-05", "12", "6",   18.75,  "In Stock"),
    ("Oil Filter OF-220",       f"{TAG}PRT-003", "Filters",    "Bin C-03", "8",  "4",    9.00,  "In Stock"),
    ("5 HP Motor 3-Phase",      f"{TAG}PRT-004", "Motors",     "Shelf D",  "1",  "2", 385.00,  "Low Stock"),
    ("Fuse 20A 600V",           f"{TAG}PRT-005", "Electrical", "Bin E-01", "50", "20",   1.25,  "In Stock"),
    ("Hydraulic Hose 3/4\"",    f"{TAG}PRT-006", "Hydraulics", "Shelf F",  "3",  "2",   48.00,  "In Stock"),
    ("M10 Hex Bolt (50pk)",     f"{TAG}PRT-007", "Fasteners",  "Bin G-08", "10", "5",    8.50,  "In Stock"),
    ("ISO 46 Hydraulic Oil",    f"{TAG}PRT-008", "Lubricants", "Shelf H",  "2",  "2",   42.00,  "Low Stock"),
    ("Laser Focusing Lens",     f"{TAG}PRT-009", "Other",      "Safe Box", "0",  "1", 620.00,  "Out of Stock"),
    ("Air Compressor Belt B56", f"{TAG}PRT-010", "Belts",      "Bin A-15", "4",  "3",   15.00,  "In Stock"),
]


def _seed_parts(conn):
    for name, pnum, cat, loc, qty, reorder, cost, status in PARTS:
        if conn.execute("SELECT 1 FROM maint_part WHERE part_number=%s", (pnum,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO maint_part"
            " (name, part_number, category, location, quantity, reorder_level,"
            "  unit_cost, status, notes, created_by)"
            f" VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Sample data','{TAG}')",
            (name, pnum, cat, loc, qty, reorder, cost, status),
        )
    conn.commit()


def _remove_parts(conn):
    conn.execute("DELETE FROM maint_part WHERE part_number LIKE %s", (f"{TAG}PRT-%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_mechanics(conn)
    _seed_equipment(conn)
    _seed_work_orders(conn)
    _seed_schedules(conn)
    _seed_inspections(conn)
    _seed_downtime(conn)
    _seed_parts(conn)
    print("Maintenance sample data seeded.")


def remove(conn):
    _remove_parts(conn)
    _remove_downtime(conn)
    _remove_inspections(conn)
    _remove_schedules(conn)
    _remove_work_orders(conn)
    _remove_equipment(conn)
    _remove_mechanics(conn)
    print("Maintenance sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Maintenance sample data")
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


