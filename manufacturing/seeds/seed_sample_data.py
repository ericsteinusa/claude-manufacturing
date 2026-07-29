"""seed_sample_data.py — populate sample personnel across all departments.

Inserts ~50 sample employees, one or more per sub-department, so every
department and sub-department is staffed. Departments the app has menus
for but that lack ``dept`` rows (Finance, Legal, Risk Management,
Warehouse) are created first, so they get staffed too. Each person is
assigned the correct parent department, their sub-department, a
``position.job_title``
matching the sub-department title, and a role inferred from that title
(Manager -> Department Manager, Supervisor/Lead/Foreman -> Supervisor,
Personnel staff -> HR / Personnel, otherwise the general-staff role). It
also backfills ``dept_sub.dept_id`` so every sub-department is linked to
its parent department.

Each sample person also gets a ``passwd`` row with a shared, well-known
development password (``SAMPLE_PASSWORD``) so the accounts can be used to
log in through the web app.

Sample people are tagged with an ``@example.com`` email so the seed is
idempotent and fully reversible.

Usage::

    python -m manufacturing.seeds.seed_sample_data            # add sample data
    python -m manufacturing.seeds.seed_sample_data --reset    # remove + re-add
    python -m manufacturing.seeds.seed_sample_data --remove    # remove only

Lookups are by name (not hard-coded ids), so the script tolerates
differing primary keys; sub-departments or departments absent from the
database are skipped with a warning, except the NEW_DEPARTMENTS above,
which are created if missing. Those created dept/dept_sub rows are
structural and are left in place by ``--remove`` (only people are
removed); re-running is idempotent.
"""
import argparse
import sys

import bcrypt

from ..db_pg import get_db_connection
from ..schema import init_schema

SAMPLE_EMAIL_DOMAIN = "@example.com"

# Shared development password given to every sample account so they can log
# in through the web app. Sample data only — not for production use.
SAMPLE_PASSWORD = "Sample123!"

# Every sub-department mapped to its parent department (by name). Used both
# to backfill dept_sub.dept_id and to resolve a new hire's department.
SUB_PARENTS = {
    "Accounts payable": "Accounting",
    "Accounts receivable": "Accounting",
    "Accounts payable Supervisor": "Accounting",
    "Accounts receivable Supervisor": "Accounting",
    "Accounting Manager": "Accounting",
    "IT Technician": "Information Technologies",
    "IT Manager": "Information Technologies",
    "Customer Service Rep": "Customer Service",
    "Customer Service Lead": "Customer Service",
    "Customer Service Manager": "Customer Service",
    "Personnel Manager": "Personnel",
    "Personnel Assistant": "Personnel",
    "Engineer Manager": "Engineering",
    "Engineer": "Engineering",
    "Maintenance Manager": "Maintenance",
    "Maintenance Mechanic": "Maintenance",
    "Purchasing Manager": "Purchasing",
    "Purchasing Personnel": "Purchasing",
    "Quality Assurance Manager": "Quality Assurance",
    "Quality Assurance Lead": "Quality Assurance",
    "Quality Assurance Technician": "Quality Assurance",
    "Lab Manager": "Labs",
    "Lab Technician": "Labs",
    "Company President": "Company",
    "Company Vice President": "Company",
    "Marketing Manager": "Marketing",
    "Marketing Personnel": "Marketing",
    "Production Manager": "Production",
    "Production Foreman": "Production",
    "Production Personnel": "Production",
    "Sales Manager": "Sales",
    "Sales Personnel": "Sales",
    "Finance Manager": "Finance",
    "Finance Personnel": "Finance",
    "Legal Manager": "Legal",
    "Legal Personnel": "Legal",
    "Risk Manager": "Risk Management",
    "Risk Personnel": "Risk Management",
    "Warehouse Manager": "Warehouse",
    "Warehouse Personnel": "Warehouse",
}

# Every department (and its sub-departments) referenced by SUB_PARENTS
# above. On a database with years of ad-hoc manual use (the assumption this
# seed script was originally written under), these already existed as
# ``dept``/``dept_sub`` rows -- but a genuinely fresh database (e.g. a new
# Docker deployment following DEPLOYMENT.md's own Quick Start) has none of
# them, so every hire in HIRES got silently skipped except the four
# departments below that a past bug report had already flagged as missing
# (Finance/Legal/Risk Management/Warehouse) -- a fresh install ended up with
# only those 12 people and, critically, no President/Vice President account
# at all, since "Company" was never in this list either.
# ``ensure_departments`` creates whichever of these are missing
# (idempotently) before seeding people, so this now covers every department
# HIRES actually hires into, not just the four that were noticed before.
NEW_DEPARTMENTS = {
    "Company": ["Company President", "Company Vice President"],
    "Accounting": [
        "Accounts payable", "Accounts receivable",
        "Accounts payable Supervisor", "Accounts receivable Supervisor",
        "Accounting Manager",
    ],
    "Information Technologies": ["IT Technician", "IT Manager"],
    "Customer Service": [
        "Customer Service Rep", "Customer Service Lead",
        "Customer Service Manager",
    ],
    "Personnel": ["Personnel Manager", "Personnel Assistant"],
    "Engineering": ["Engineer Manager", "Engineer"],
    "Maintenance": ["Maintenance Manager", "Maintenance Mechanic"],
    "Purchasing": ["Purchasing Manager", "Purchasing Personnel"],
    "Quality Assurance": [
        "Quality Assurance Manager", "Quality Assurance Lead",
        "Quality Assurance Technician",
    ],
    "Labs": ["Lab Manager", "Lab Technician"],
    "Marketing": ["Marketing Manager", "Marketing Personnel"],
    "Production": [
        "Production Manager", "Production Foreman", "Production Personnel",
    ],
    "Sales": ["Sales Manager", "Sales Personnel"],
    "Finance": ["Finance Manager", "Finance Personnel"],
    "Legal": ["Legal Manager", "Legal Personnel"],
    "Risk Management": ["Risk Manager", "Risk Personnel"],
    "Warehouse": ["Warehouse Manager", "Warehouse Personnel"],
}

# How many sample hires to add per sub-department (sums to 54). Weighted so
# previously-empty departments/sub-departments and thin teams get covered.
HIRES = {
    # A President and Vice President each give a sample full-access account
    # (President / Vice President are FULL_ACCESS_ROLES) for testing the
    # all-departments dashboard, not just a single department menu.
    "Company President": 1,
    "Company Vice President": 1,
    "Quality Assurance Manager": 1,
    "Quality Assurance Lead": 1,
    "Quality Assurance Technician": 3,
    "Marketing Manager": 1,
    "Marketing Personnel": 3,
    "Production Manager": 1,
    "Production Foreman": 2,
    "Production Personnel": 4,
    "Accounting Manager": 1,
    "IT Manager": 1,
    "Customer Service Lead": 1,
    "Sales Manager": 1,
    "IT Technician": 2,
    "Customer Service Rep": 2,
    "Engineer": 2,
    "Maintenance Mechanic": 2,
    "Lab Technician": 2,
    "Sales Personnel": 2,
    "Purchasing Personnel": 1,
    "Personnel Assistant": 1,
    "Accounts payable": 1,
    "Accounts receivable": 1,
    "Accounts payable Supervisor": 1,
    "Accounts receivable Supervisor": 1,
    "Customer Service Manager": 1,
    "Engineer Manager": 1,
    "Finance Manager": 1,
    "Finance Personnel": 2,
    "Legal Manager": 1,
    "Legal Personnel": 2,
    "Risk Manager": 1,
    "Risk Personnel": 2,
    "Warehouse Manager": 1,
    "Warehouse Personnel": 2,
}

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel",
    "Nancy", "Matthew", "Lisa", "Anthony", "Betty", "Mark", "Margaret",
    "Donald", "Sandra", "Steven", "Ashley", "Paul", "Kimberly", "Andrew",
    "Emily", "Joshua", "Donna", "Kenneth", "Michelle",
]
LAST_NAMES = [
    "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips",
    "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Sanchez",
    "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell", "Murphy", "Bailey",
    "Rivera", "Cooper", "Richardson", "Cox", "Howard", "Ward", "Torres",
    "Peterson", "Gray", "Ramirez", "James", "Watson", "Brooks", "Kelly",
    "Sanders", "Price", "Bennett", "Wood", "Barnes",
]


def _role_for(dept_name, sub_name):
    """Infer a role name from the sub-department title and department."""
    n = sub_name.lower()
    if "vice president" in n:
        return "Vice President"
    if "president" in n:
        return "President"
    if "manager" in n:
        return "Department Manager"
    if any(k in n for k in ("supervisor", "lead", "foreman")):
        return "Supervisor"
    if dept_name == "Personnel":
        return "HR / Personnel"
    return "Supervisor"            # general-staff role used elsewhere


def _name_pool():
    """Yield distinct (first, last) names, adding a suffix once exhausted."""
    i = 0
    while True:
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[i % len(LAST_NAMES)]
        # After the first full pass, disambiguate with a numeric suffix.
        suffix = "" if i < len(LAST_NAMES) else str(i // len(LAST_NAMES) + 1)
        yield first, last + suffix
        i += 1


def _lookup_ids(conn):
    depts = {r["dept_name"]: r["dept_id"]
             for r in conn.execute(
                 "SELECT dept_id, dept_name FROM dept").fetchall()}
    subs = {r["dept_sub_name"]: r["dept_sub_id"]
            for r in conn.execute(
                "SELECT dept_sub_id, dept_sub_name FROM dept_sub").fetchall()}
    roles = {r["role_name"]: r["id"]
             for r in conn.execute(
                 "SELECT id, role_name FROM roles").fetchall()}
    return depts, subs, roles


def ensure_departments(conn):
    """Create dept/dept_sub rows for NEW_DEPARTMENTS if absent.

    Idempotent: resolves by name and inserts only what's missing, so the
    departments the app already has menus for (Finance, Legal, Risk
    Management, Warehouse) exist and can be staffed. Returns
    ``(depts_created, subs_created)``.
    """
    # Existing dept/dept_sub rows were inserted with explicit ids, leaving the
    # SERIAL sequences behind, so assign ids by MAX+1 (as seed() does for
    # employee_id) rather than relying on the sequence default.
    next_dept = conn.execute(
        "SELECT COALESCE(MAX(dept_id), 0) FROM dept").fetchone()[0] + 1
    next_sub = conn.execute(
        "SELECT COALESCE(MAX(dept_sub_id), 0) FROM dept_sub").fetchone()[0] + 1
    depts_created = subs_created = 0
    for dept_name, sub_names in NEW_DEPARTMENTS.items():
        row = conn.execute(
            "SELECT dept_id FROM dept WHERE dept_name=%s",
            (dept_name,)).fetchone()
        if row:
            dept_id = row["dept_id"]
        else:
            dept_id = next_dept
            next_dept += 1
            conn.execute(
                "INSERT INTO dept (dept_id, dept_name) VALUES (%s,%s)",
                (dept_id, dept_name))
            depts_created += 1
        for sub_name in sub_names:
            exists = conn.execute(
                "SELECT 1 FROM dept_sub WHERE dept_sub_name=%s AND dept_id=%s",
                (sub_name, dept_id)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO dept_sub (dept_sub_id, dept_id, "
                    "dept_sub_name) VALUES (%s,%s,%s)",
                    (next_sub, dept_id, sub_name))
                next_sub += 1
                subs_created += 1
    return depts_created, subs_created


def link_sub_departments(conn, depts, subs):
    """Backfill dept_sub.dept_id from SUB_PARENTS. Returns count linked."""
    linked = 0
    for sub_name, dept_name in SUB_PARENTS.items():
        if sub_name in subs and dept_name in depts:
            conn.execute(
                "UPDATE dept_sub SET dept_id=%s WHERE dept_sub_id=%s",
                (depts[dept_name], subs[sub_name]))
            linked += 1
    return linked


def sample_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM people WHERE email LIKE %s",
        ("%" + SAMPLE_EMAIL_DOMAIN,)).fetchone()[0]


def remove_sample(conn):
    """Delete sample people (roles + positions too). Returns count removed."""
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM people WHERE email LIKE %s",
        ("%" + SAMPLE_EMAIL_DOMAIN,)).fetchall()]
    for pid in ids:
        conn.execute("DELETE FROM passwd WHERE people_id=%s", (pid,))
        conn.execute("DELETE FROM user_roles WHERE people_id=%s", (pid,))
        conn.execute("DELETE FROM position WHERE people_id=%s", (pid,))
        conn.execute("DELETE FROM people WHERE id=%s", (pid,))
    return len(ids)


def seed(conn):
    """Insert the sample hires. Returns count added."""
    depts, subs, roles = _lookup_ids(conn)
    base = conn.execute(
        "SELECT COALESCE(MAX(employee_id), 0) FROM people").fetchone()[0]
    emp_id = max(1000, base) + 1

    # All sample accounts share one password; hash it once and reuse.
    hashed_pw = bcrypt.hashpw(
        SAMPLE_PASSWORD.encode(), bcrypt.gensalt()).decode()

    names = _name_pool()
    added = 0
    for sub_name, count in HIRES.items():
        dept_name = SUB_PARENTS.get(sub_name)
        if sub_name not in subs or dept_name not in depts:
            print(f"  skip (missing): {sub_name!r}", file=sys.stderr)
            continue
        role_name = _role_for(dept_name, sub_name)
        role_id = roles.get(role_name)
        for _ in range(count):
            first, last = next(names)
            email = f"{first.lower()}.{last.lower()}{SAMPLE_EMAIL_DOMAIN}"
            pid = conn.execute(
                "INSERT INTO people (first_name, last_name, employee_id, "
                "email, dept_id, dept_sub_id, address, city, state, zip_code)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (first, last, emp_id, email, depts[dept_name],
                 subs[sub_name], "", "", "", "")).fetchone()["id"]
            if role_id is not None:
                conn.execute(
                    "INSERT INTO user_roles (people_id, role_id) "
                    "VALUES (%s,%s)", (pid, role_id))
            # Job title mirrors the sub-department title.
            conn.execute(
                "INSERT INTO position (people_id, job_title) VALUES (%s,%s)",
                (pid, sub_name))
            # Credentials so the sample account can log in.
            conn.execute(
                "INSERT INTO passwd (people_id, password) VALUES (%s,%s)",
                (pid, hashed_pw))
            emp_id += 1
            added += 1
    return added


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed sample personnel.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample people, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample people only (no seeding)")
    args = parser.parse_args(argv)

    init_schema()
    conn = get_db_connection()
    try:
        if args.remove or args.reset:
            removed = remove_sample(conn)
            print(f"removed {removed} sample people")
            if args.remove:
                conn.commit()
                return

        if sample_present(conn):
            print("Sample people already present; use --reset to recreate.")
            return

        dept_n, sub_n = ensure_departments(conn)
        depts, subs, _ = _lookup_ids(conn)
        linked = link_sub_departments(conn, depts, subs)
        added = seed(conn)
        conn.commit()
        print(f"created {dept_n} departments, {sub_n} sub-departments")
        print(f"linked {linked} sub-departments; inserted {added} people")
        print(f"sample login password: {SAMPLE_PASSWORD!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


