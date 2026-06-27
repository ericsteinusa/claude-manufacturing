"""seed_sample_it.py — sample IT data for help desk, assets, repairs, software, licenses, network, and tasks.

All rows are tagged with the ``SMPL-IT-`` prefix on their number/tag so they
can be identified and removed without touching real data.

Usage::

    python -m manufacturing.seed_sample_it            # add (idempotent)
    python -m manufacturing.seed_sample_it --reset     # remove + re-add
    python -m manufacturing.seed_sample_it --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from .db_pg import get_db_connection
from .it_core import (
    _ensure_repair_table, _ensure_software_table,
    _ensure_license_table, _ensure_network_table, _ensure_task_table,
)

TAG = "SMPL-IT-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


# ---------------------------------------------------------------------------
# Tickets  (it_ticket)
# ---------------------------------------------------------------------------

TICKETS = [
    # (suffix, requester, dept, issue_type, priority, status, submitted_ago, due_offset, assigned_to, description)
    ("TKT-001", "Linda Carter",   "Accounting",     "Software",           "high",     "open",        -2,  3,  "Mike Torres",   "Excel crashes on large pivot tables — latest update broke something"),
    ("TKT-002", "James Wu",       "Production",     "Hardware",           "critical", "in_progress", -1,  1,  "Sara Patel",    "CNC machine workstation won't power on after storm outage"),
    ("TKT-003", "Anna Kowalski",  "HR",             "Account",            "medium",   "open",        -3,  5,  "",              "New hire needs domain account and email setup"),
    ("TKT-004", "Bob Nguyen",     "Sales",          "Network",            "low",      "open",        -4,  7,  "",              "VPN drops every hour when working from home"),
    ("TKT-005", "Priya Sharma",   "Engineering",    "Printer",            "medium",   "resolved",    -10, -5, "Mike Torres",   "HP printer in lab won't accept jobs from macOS clients"),
    ("TKT-006", "Tom Bradley",    "Warehouse",      "Hardware",           "high",     "in_progress", -1,  2,  "Sara Patel",    "Barcode scanner keeps dropping Bluetooth connection"),
    ("TKT-007", "Rachel Green",   "Customer Svc",   "Email",              "medium",   "closed",      -14, -9, "Mike Torres",   "Outlook not syncing shared calendar with team"),
    ("TKT-008", "David Kim",      "Finance",        "Software",           "low",      "open",        -1,  5,  "",              "QuickBooks license expired — need renewal or replacement"),
    ("TKT-009", "Susan Park",     "Legal",          "Access / Permissions","medium",  "in_progress", -3,  2,  "Sara Patel",    "Cannot access contract management folder on share drive"),
    ("TKT-010", "Carlos Ruiz",    "Production",     "Hardware",           "critical", "open",        0,   1,  "",              "Monitor on assembly line PC showing color distortion"),
    ("TKT-011", "Janet Mills",    "Purchasing",     "Other",              "low",      "resolved",    -20, -15,"Mike Torres",   "Keyboard sticking on multiple keys — request replacement"),
    ("TKT-012", "Frank Deluca",   "IT",             "Network",            "high",     "open",        -1,  1,  "",              "Core switch log showing excessive CRC errors on port 24"),
]


def _ensure_ticket_columns(conn):
    for col, typ in [
        ("priority",       "TEXT DEFAULT 'medium'"),
        ("issue_type",     "TEXT DEFAULT ''"),
        ("description",    "TEXT DEFAULT ''"),
        ("assigned_to",    "TEXT DEFAULT ''"),
        ("created_by",     "TEXT DEFAULT ''"),
        ("resolved_date",  "DATE"),
    ]:
        try:
            conn.execute(
                f"ALTER TABLE it_ticket ADD COLUMN IF NOT EXISTS {col} {typ}"
            )
        except Exception:
            pass
    conn.commit()


def _seed_tickets(conn):
    _ensure_ticket_columns(conn)
    for (suffix, requester, dept, issue_type, priority, status,
         sub_ago, due_offset, assigned_to, description) in TICKETS:
        ticket_number = f"{TAG}{suffix}"
        existing = conn.execute(
            "SELECT id FROM it_ticket WHERE ticket_number = %s",
            (ticket_number,)
        ).fetchone()
        if existing:
            continue
        submitted = _d(sub_ago)
        due = _d(sub_ago + due_offset)
        resolved = _d(sub_ago + due_offset + 1) if status in ("resolved", "closed") else None
        conn.execute(
            "INSERT INTO it_ticket "
            "(ticket_number, requester, department, issue_type, description, "
            "priority, assigned_to, submitted_date, due_date, resolved_date, "
            "status, notes, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (ticket_number, requester, dept, issue_type, description,
             priority, assigned_to, submitted, due, resolved,
             status, "", "seed"),
        )
    conn.commit()


def _remove_tickets(conn):
    conn.execute(
        "DELETE FROM it_ticket WHERE ticket_number LIKE %s", (f"{TAG}TKT-%",)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Assets  (it_asset)
# ---------------------------------------------------------------------------

ASSETS = [
    # (tag, type, make, model, serial, assigned_to, dept, purchased_ago, warranty_years, status)
    ("ASSET-001", "Desktop",  "Dell",   "OptiPlex 7090",    "DL7090-001", "Linda Carter",  "Accounting",  -730, 3,  "active"),
    ("ASSET-002", "Laptop",   "HP",     "EliteBook 840",    "HP840-002",  "James Wu",      "Production",  -365, 3,  "active"),
    ("ASSET-003", "Laptop",   "Lenovo", "ThinkPad T14",     "LN14-003",   "Priya Sharma",  "Engineering", -180, 3,  "active"),
    ("ASSET-004", "Server",   "Dell",   "PowerEdge R750",   "DPE750-004", "",              "IT",          -900, 5,  "active"),
    ("ASSET-005", "Printer",  "HP",     "LaserJet Pro M428","HPLJ-005",   "",              "Production",  -400, 2,  "repair"),
    ("ASSET-006", "Desktop",  "HP",     "EliteDesk 800",    "HPED-006",   "Bob Nguyen",    "Sales",       -500, 3,  "active"),
    ("ASSET-007", "Monitor",  "Dell",   "UltraSharp U2722", "DU2722-007", "Anna Kowalski", "HR",          -200, 3,  "active"),
    ("ASSET-008", "Switch",   "Cisco",  "Catalyst 2960-X",  "CS2960-008", "",              "IT",          -1100,5,  "active"),
    ("ASSET-009", "Laptop",   "Apple",  "MacBook Pro 14",   "MBPRO-009",  "Rachel Green",  "Cust Svc",    -90,  3,  "active"),
    ("ASSET-010", "Desktop",  "Dell",   "OptiPlex 5090",    "DL5090-010", "Carlos Ruiz",   "Production",  -800, 3,  "active"),
    ("ASSET-011", "UPS",      "APC",    "Smart-UPS 1500",   "APC1500-011","",              "IT",          -600, 3,  "active"),
    ("ASSET-012", "Laptop",   "Dell",   "Latitude 5530",    "DL5530-012", "Susan Park",    "Legal",       -120, 3,  "active"),
    ("ASSET-013", "Phone",    "Cisco",  "IP Phone 8841",    "CIPH-013",   "David Kim",     "Finance",     -400, 3,  "active"),
    ("ASSET-014", "Desktop",  "HP",     "EliteDesk 705",    "HPED-014",   "",              "Warehouse",   -1200,3,  "retired"),
    ("ASSET-015", "Server",   "HP",     "ProLiant DL380",   "HPDL-015",   "",              "IT",          -500, 5,  "active"),
]


def _seed_assets(conn):
    for (tag, atype, make, model, serial, assigned_to,
         dept, purch_ago, warranty_yrs, status) in ASSETS:
        asset_tag = f"{TAG}{tag}"
        existing = conn.execute(
            "SELECT id FROM it_asset WHERE asset_tag = %s", (asset_tag,)
        ).fetchone()
        if existing:
            continue
        purchase_date = _d(purch_ago)
        warranty_exp = (TODAY + timedelta(days=purch_ago) +
                        timedelta(days=365 * warranty_yrs)).isoformat()
        conn.execute(
            "INSERT INTO it_asset "
            "(asset_tag, asset_type, make, model, serial_number, assigned_to, "
            "department, purchase_date, warranty_exp, status, notes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (asset_tag, atype, make, model, serial, assigned_to,
             dept, purchase_date, warranty_exp, status, "Sample data"),
        )
    conn.commit()


def _remove_assets(conn):
    conn.execute(
        "DELETE FROM it_asset WHERE asset_tag LIKE %s", (f"{TAG}ASSET-%",)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Hardware Repairs  (it_repair)
# ---------------------------------------------------------------------------

REPAIRS = [
    # (asset_tag_suffix, problem, reported_by, reported_ago, assigned_to, priority, status)
    ("ASSET-005", "Paper feed jam and roller worn out",         "Bob Nguyen",   -5,  "Mike Torres", "medium",   "in_progress"),
    ("ASSET-010", "Overheating — fan replaced, thermal paste",  "Carlos Ruiz",  -12, "Sara Patel",  "high",     "completed"),
    ("ASSET-002", "Cracked screen after drop, needs replacement","James Wu",    -2,  "Mike Torres", "high",     "open"),
    ("ASSET-014", "PSU failure on retired unit — for parts",    "IT Dept",      -30, "Sara Patel",  "low",      "cancelled"),
]


def _seed_repairs(conn):
    _ensure_repair_table(conn)
    for (asset_suffix, problem, reported_by, rep_ago, assigned_to, priority, status) in REPAIRS:
        asset_tag = f"{TAG}{asset_suffix}"
        existing = conn.execute(
            "SELECT id FROM it_repair WHERE asset_tag = %s AND problem_description = %s",
            (asset_tag, problem)
        ).fetchone()
        if existing:
            continue
        reported_date = _d(rep_ago)
        completed_date = _d(rep_ago + 7) if status == "completed" else None
        conn.execute(
            "INSERT INTO it_repair "
            "(asset_tag, problem_description, reported_by, reported_date, "
            "assigned_to, priority, status, completed_date, notes, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (asset_tag, problem, reported_by, reported_date,
             assigned_to, priority, status, completed_date, "Sample data", "seed"),
        )
    conn.commit()


def _remove_repairs(conn):
    conn.execute(
        "DELETE FROM it_repair WHERE asset_tag LIKE %s", (f"{TAG}ASSET-%",)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Software Installations  (it_software_install)
# ---------------------------------------------------------------------------

SOFTWARE = [
    # (asset_suffix, name, version, vendor, installed_ago, status, installed_by)
    ("ASSET-001", "Microsoft 365",       "2024",       "Microsoft",   -365, "installed", "Mike Torres"),
    ("ASSET-001", "Adobe Acrobat Pro",   "2024.1",     "Adobe",       -300, "installed", "Mike Torres"),
    ("ASSET-002", "Microsoft 365",       "2024",       "Microsoft",   -180, "installed", "Sara Patel"),
    ("ASSET-002", "AutoCAD LT",          "2024",       "Autodesk",    -180, "installed", "Sara Patel"),
    ("ASSET-003", "Microsoft 365",       "2024",       "Microsoft",   -90,  "installed", "Mike Torres"),
    ("ASSET-003", "SOLIDWORKS",          "2024 SP2",   "Dassault",    -90,  "installed", "Mike Torres"),
    ("ASSET-006", "Salesforce CRM",      "Winter 25",  "Salesforce",  -60,  "installed", "Sara Patel"),
    ("ASSET-006", "Microsoft 365",       "2024",       "Microsoft",   -500, "installed", "Mike Torres"),
    ("ASSET-009", "Microsoft 365",       "2024",       "Microsoft",   -89,  "installed", "Sara Patel"),
    ("ASSET-009", "Zoom",                "5.17",       "Zoom Video",  -89,  "installed", "Sara Patel"),
    ("ASSET-010", "MES Client",          "3.4.1",      "Internal",    -800, "installed", "Mike Torres"),
    ("ASSET-012", "Microsoft 365",       "2024",       "Microsoft",   -120, "installed", "Mike Torres"),
    ("ASSET-012", "DocuSign",            "23.4",       "DocuSign",    -30,  "installed", "Sara Patel"),
    ("ASSET-001", "Old ERP Client",      "7.1",        "Legacy Corp", -730, "removed",   "Mike Torres"),
]


def _seed_software(conn):
    _ensure_software_table(conn)
    for (asset_suffix, name, version, vendor, inst_ago, status, installed_by) in SOFTWARE:
        asset_tag = f"{TAG}{asset_suffix}"
        existing = conn.execute(
            "SELECT id FROM it_software_install "
            "WHERE asset_tag = %s AND software_name = %s AND version = %s",
            (asset_tag, name, version)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO it_software_install "
            "(asset_tag, software_name, version, vendor, install_date, "
            "status, installed_by, notes, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (asset_tag, name, version, vendor, _d(inst_ago),
             status, installed_by, "Sample data", "seed"),
        )
    conn.commit()


def _remove_software(conn):
    conn.execute(
        "DELETE FROM it_software_install WHERE asset_tag LIKE %s",
        (f"{TAG}ASSET-%",)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Software Licenses  (it_license)
# ---------------------------------------------------------------------------

LICENSES = [
    # (name, vendor, key, type, seats, used, purchased_ago, expiry_days, cost, status)
    ("Microsoft 365 Business",  "Microsoft",  "MS365-XXXX-YYYY",  "subscription", 50, 38, -365, 365,  12000.00, "active"),
    ("Adobe Creative Cloud",    "Adobe",      "ACC-XXXX-YYYY",    "subscription", 5,  3,  -180, 180,   3000.00, "active"),
    ("AutoCAD LT 2024",         "Autodesk",   "ACAD-XXXX-YYYY",   "subscription", 3,  2,  -90,  275,   2400.00, "active"),
    ("SOLIDWORKS Standard",     "Dassault",   "SW-XXXX-YYYY",     "perpetual",    2,  2,  -730, 99999, 8000.00, "active"),
    ("Salesforce Starter",      "Salesforce", "SF-XXXX-YYYY",     "subscription", 10, 6,  -60,  305,   6000.00, "active"),
    ("Zoom Business",           "Zoom",       "ZOOM-XXXX-YYYY",   "subscription", 25, 18, -89,  276,   4500.00, "active"),
    ("DocuSign Business Pro",   "DocuSign",   "DS-XXXX-YYYY",     "subscription", 5,  2,  -30,  335,   1500.00, "active"),
    ("Antivirus Enterprise",    "Bitdefender","BD-XXXX-YYYY",     "subscription", 60, 55, -365, 0,     1800.00, "expired"),
    ("Old MES License",         "Legacy Corp","MES-XXXX-YYYY",    "perpetual",    5,  1,  -1095,99999, 15000.00,"active"),
]


def _seed_licenses(conn):
    _ensure_license_table(conn)
    for (name, vendor, key, ltype, seats, used,
         purch_ago, expiry_days, cost, status) in LICENSES:
        existing = conn.execute(
            "SELECT id FROM it_license WHERE software_name = %s AND vendor = %s",
            (name, vendor)
        ).fetchone()
        if existing:
            continue
        purchase_date = _d(purch_ago)
        expiry_date = (TODAY + timedelta(days=purch_ago + expiry_days)).isoformat() \
            if expiry_days < 99999 else _d(purch_ago + 3650)
        conn.execute(
            "INSERT INTO it_license "
            "(software_name, vendor, license_key, license_type, seats, seats_used, "
            "purchase_date, expiry_date, cost, status, notes, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (name, vendor, key, ltype, seats, used,
             purchase_date, expiry_date, cost, status, "Sample data", "seed"),
        )
    conn.commit()


def _remove_licenses(conn):
    conn.execute(
        "DELETE FROM it_license WHERE created_by = 'seed' AND notes = 'Sample data'"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Network Devices  (it_network_device)
# ---------------------------------------------------------------------------

NETWORK_DEVICES = [
    # (hostname, ip, mac, type, manufacturer, model, location, status, last_seen_ago)
    ("core-sw-01",   "10.0.0.1",   "00:1A:2B:3C:4D:01", "Switch",       "Cisco",    "Catalyst 2960-X",   "Server Room",  "online",      0),
    ("core-sw-02",   "10.0.0.2",   "00:1A:2B:3C:4D:02", "Switch",       "Cisco",    "Catalyst 2960-X",   "Server Room",  "online",      0),
    ("fw-01",        "10.0.0.254", "00:1A:2B:3C:4D:FE", "Firewall",     "Fortinet", "FortiGate 200F",    "Server Room",  "online",      0),
    ("ap-floor1-01", "10.0.1.10",  "00:1A:2B:3C:4D:10", "Access Point", "Ubiquiti", "UniFi AP-AC-Pro",   "Floor 1",      "online",      0),
    ("ap-floor2-01", "10.0.2.10",  "00:1A:2B:3C:4D:20", "Access Point", "Ubiquiti", "UniFi AP-AC-Pro",   "Floor 2",      "online",      -1),
    ("nas-01",       "10.0.0.10",  "00:1A:2B:3C:4D:0A", "NAS",          "Synology", "DS1821+",           "Server Room",  "online",      0),
    ("srv-app-01",   "10.0.0.20",  "00:1A:2B:3C:4D:14", "Server",       "Dell",     "PowerEdge R750",    "Server Room",  "online",      0),
    ("srv-db-01",    "10.0.0.21",  "00:1A:2B:3C:4D:15", "Server",       "HP",       "ProLiant DL380",    "Server Room",  "online",      0),
    ("prt-acct-01",  "10.0.3.5",   "00:1A:2B:3C:4D:30", "Printer",      "HP",       "LaserJet Pro M428", "Accounting",   "offline",     -3),
    ("ap-wh-01",     "10.0.4.10",  "00:1A:2B:3C:4D:40", "Access Point", "Ubiquiti", "UniFi AP-HD",       "Warehouse",    "maintenance", -2),
]


def _seed_network(conn):
    _ensure_network_table(conn)
    for (hostname, ip, mac, dtype, mfr, model,
         location, status, last_ago) in NETWORK_DEVICES:
        existing = conn.execute(
            "SELECT id FROM it_network_device WHERE hostname = %s", (hostname,)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO it_network_device "
            "(hostname, ip_address, mac_address, device_type, manufacturer, "
            "model, location, status, last_seen, notes, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (hostname, ip, mac, dtype, mfr, model,
             location, status, _d(last_ago), "Sample data", "seed"),
        )
    conn.commit()


def _remove_network(conn):
    conn.execute(
        "DELETE FROM it_network_device WHERE created_by = 'seed' AND notes = 'Sample data'"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# IT Tasks  (it_task)
# ---------------------------------------------------------------------------

TASKS = [
    # (suffix, name, type, description, assigned_to, dept, priority, sched_ago, due_offset, status)
    ("TASK-001", "Patch Tuesday server updates",      "Maintenance",       "Apply June security patches to all servers",           "Mike Torres", "IT",          "high",     -1,  1,  "in_progress"),
    ("TASK-002", "Deploy new user workstations",      "Hardware Setup",    "Set up 3 desktops for new Accounting hires",           "Sara Patel",  "Accounting",  "medium",   -3,  4,  "pending"),
    ("TASK-003", "Firewall rule audit",               "Security",          "Review and clean up stale firewall rules",             "Mike Torres", "IT",          "high",     -7,  0,  "in_progress"),
    ("TASK-004", "Upgrade NAS firmware",              "Upgrade",           "Synology DSM upgrade to 7.2.1",                        "Sara Patel",  "IT",          "medium",   -14, -10,"completed"),
    ("TASK-005", "Configure new VoIP phones",         "Configuration",     "Set up 10 Cisco phones for Sales expansion",           "Mike Torres", "Sales",       "medium",   0,   5,  "pending"),
    ("TASK-006", "Wireless survey floor 3",           "Network",           "Site survey for AP placement on new floor",            "Sara Patel",  "IT",          "low",      -2,  10, "pending"),
    ("TASK-007", "Onboard new ERP module",            "Software Deployment","Install and configure procurement module on app server","Mike Torres","Production",  "high",     -5,  2,  "in_progress"),
    ("TASK-008", "Quarterly backup verification",     "Backup / Recovery", "Restore test from NAS to verify backup integrity",     "Sara Patel",  "IT",          "high",     -30, -25,"completed"),
    ("TASK-009", "Decommission old file server",      "Maintenance",       "Migrate remaining shares, wipe and retire srv-old-01", "Mike Torres", "IT",          "low",      0,   14, "pending"),
    ("TASK-010", "SSL certificate renewal",           "Security",          "Renew wildcard cert expiring in 45 days",              "Sara Patel",  "IT",          "critical", -1,  30, "in_progress"),
]


def _seed_tasks(conn):
    _ensure_task_table(conn)
    for (suffix, name, ttype, description, assigned_to, dept,
         priority, sched_ago, due_offset, status) in TASKS:
        task_number = f"{TAG}{suffix}"
        existing = conn.execute(
            "SELECT id FROM it_task WHERE task_number = %s", (task_number,)
        ).fetchone()
        if existing:
            continue
        scheduled_date = _d(sched_ago)
        due_date = _d(sched_ago + due_offset)
        completed_date = _d(sched_ago + due_offset + 1) if status == "completed" else None
        conn.execute(
            "INSERT INTO it_task "
            "(task_number, task_name, task_type, description, assigned_to, "
            "department, priority, scheduled_date, due_date, completed_date, "
            "status, notes, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (task_number, name, ttype, description, assigned_to, dept,
             priority, scheduled_date, due_date, completed_date,
             status, "Sample data", "seed"),
        )
    conn.commit()


def _remove_tasks(conn):
    conn.execute(
        "DELETE FROM it_task WHERE task_number LIKE %s", (f"{TAG}TASK-%",)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _seed_tickets(conn)
    _seed_assets(conn)
    _seed_repairs(conn)
    _seed_software(conn)
    _seed_licenses(conn)
    _seed_network(conn)
    _seed_tasks(conn)
    print("IT sample data seeded.")


def remove(conn):
    _remove_tickets(conn)
    _remove_assets(conn)
    _remove_repairs(conn)
    _remove_software(conn)
    _remove_licenses(conn)
    _remove_network(conn)
    _remove_tasks(conn)
    print("IT sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed IT sample data")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--reset",  action="store_true", help="Remove then re-add")
    grp.add_argument("--remove", action="store_true", help="Remove only")
    args = parser.parse_args()

    with get_db_connection() as conn:
        if args.remove:
            remove(conn)
        elif args.reset:
            remove(conn)
            seed(conn)
        else:
            seed(conn)
