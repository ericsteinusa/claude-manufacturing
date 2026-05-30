#!/usr/bin/env python3
"""
migrate_company_db_state.py

Comprehensive, idempotent migration recording all of the direct company_db
changes made during the data/role cleanup work. Re-running it is safe and
converges on the same final state. Everything runs in a single transaction
(commits on success, rolls back on error) and is checked by verify().

Run from the project root:

    python migrate_company_db_state.py

Covers, in order:
  1. Remove the leftover test account (newuser@test.com) + its credential.
  2. Remove the duplicate "Eric Steinman" (people.id=21) + its credential;
     the canonical Eric is people.id=1.
  3. Reconcile people/department assignments:
       - Eric Steinman (id=1)  -> Information Technologies / IT Technician
       - Steve Smith  (id=6)  -> Sales / Sales Personnel  (was a 2nd
         "Company President" seat; John Smith id=9 is the sole President)
       - fix job title 'IT Technitian' -> 'IT Technician'
  4. Fix misspelled sub-department names ('Technition' -> 'Technician').
  5. Repopulate the `department` table from `people` (one row per person).
  6. Add UNIQUE(people.email) so duplicate-email rows can't be created.
  7. Assign access roles to everyone:
       - eric@steinman.com, john@smith.com -> President
       - steve@target.com                  -> Vice President
       - any '* Manager' seat               -> Department Manager
       - everyone else                      -> Supervisor
"""
from manufacturing.db_pg import get_db_connection  # native PG, no SQL translation

EMAIL_UNIQUE = "people_email_unique"

PRESIDENT_EMAILS = {"eric@steinman.com", "john@smith.com"}
VP_EMAILS = {"steve@target.com"}


def run(conn):
    # 1. Remove leftover test account (guarded by its identifying email).
    conn.execute("DELETE FROM passwd WHERE people_id = 0")
    conn.execute("DELETE FROM people WHERE id = 0 AND email = 'newuser@test.com'")

    # 2. Remove the duplicate Eric Steinman (canonical is id=1).
    conn.execute("DELETE FROM passwd WHERE people_id = 21")
    conn.execute("DELETE FROM people WHERE id = 21 AND email = 'eric@steinman.com'")

    # 3. Reconcile people -> department / position assignments.
    conn.execute("UPDATE people SET dept_id = 5, dept_sub_id = 6 "
                 "WHERE id = 1 AND email = 'eric@steinman.com'")           # Eric -> IT / IT Technician
    conn.execute("UPDATE people SET dept_id = 12, dept_sub_id = 32 "
                 "WHERE id = 6 AND email = 'steve@smith.com'")             # Steve Smith -> Sales / Sales Personnel
    conn.execute("UPDATE position SET job_title = 'IT Technician' WHERE people_id = 1")

    # 4. Fix misspelled sub-department names.
    conn.execute("UPDATE dept_sub SET dept_sub_name = 'IT Technician' WHERE dept_sub_id = 6")
    conn.execute("UPDATE dept_sub SET dept_sub_name = 'Quality Assurance Technician' WHERE dept_sub_id = 21")
    conn.execute("UPDATE dept_sub SET dept_sub_name = 'Lab Technician' WHERE dept_sub_id = 23")

    # 5. Repopulate `department` from `people` (after all people.dept changes).
    conn.execute("TRUNCATE department RESTART IDENTITY")
    conn.execute("INSERT INTO department (people_id, dept_id, dept_sub_id) "
                 "SELECT id, dept_id, dept_sub_id FROM people ORDER BY id")

    # 6. Add UNIQUE(people.email) if not already present.
    if not conn.execute("SELECT 1 FROM pg_constraint WHERE conname = %s",
                        (EMAIL_UNIQUE,)).fetchone():
        conn.execute(f"ALTER TABLE people ADD CONSTRAINT {EMAIL_UNIQUE} UNIQUE (email)")

    # 7. Assign access roles to every person (idempotent upsert).
    roles = {r["role_name"]: r["id"] for r in
             conn.execute("SELECT id, role_name FROM roles").fetchall()}
    people = conn.execute("""
        SELECT p.id, p.email, s.dept_sub_name AS seat
        FROM people p LEFT JOIN dept_sub s ON p.dept_sub_id = s.dept_sub_id
    """).fetchall()
    for p in people:
        email = (p["email"] or "").lower()
        seat = (p["seat"] or "").lower()
        if email in PRESIDENT_EMAILS:
            role = "President"
        elif email in VP_EMAILS:
            role = "Vice President"
        elif "manager" in seat:
            role = "Department Manager"
        else:
            role = "Supervisor"
        conn.execute(
            "INSERT INTO user_roles (people_id, role_id) VALUES (%s, %s) "
            "ON CONFLICT (people_id) DO UPDATE SET role_id = excluded.role_id",
            (p["id"], roles[role]),
        )


def verify(conn):
    checks = {
        "leftover test/duplicate rows (id 0,21)":
            "SELECT COUNT(*) FROM people WHERE id IN (0, 21)",
        "people with no department":
            "SELECT COUNT(*) FROM people WHERE dept_id IS NULL OR dept_sub_id IS NULL",
        "department rows mismatching people":
            "SELECT COUNT(*) FROM department dp JOIN people p ON dp.people_id = p.id "
            "WHERE dp.dept_id IS DISTINCT FROM p.dept_id OR dp.dept_sub_id IS DISTINCT FROM p.dept_sub_id",
        "people missing a department row":
            "SELECT COUNT(*) FROM people p "
            "WHERE NOT EXISTS (SELECT 1 FROM department dp WHERE dp.people_id = p.id)",
        "'Technition' misspellings":
            "SELECT COUNT(*) FROM dept_sub WHERE dept_sub_name ILIKE '%technit%'",
        "missing email UNIQUE constraint":
            f"SELECT (SELECT COUNT(*) FROM pg_constraint WHERE conname = '{EMAIL_UNIQUE}') = 0",
        "people with no role":
            "SELECT COUNT(*) FROM people p LEFT JOIN user_roles ur ON ur.people_id = p.id "
            "WHERE ur.people_id IS NULL",
        "Company President seat holders (want 1)":
            "SELECT COUNT(*) - 1 FROM people p JOIN dept_sub s ON p.dept_sub_id = s.dept_sub_id "
            "WHERE s.dept_sub_name = 'Company President'",
    }
    ok = True
    for label, sql in checks.items():
        val = conn.execute(sql).fetchone()[0]
        bad = bool(val) if isinstance(val, bool) else (val != 0)
        print(f"  [{'FAIL' if bad else 'ok'}] {label}: {val}")
        ok = ok and not bad
    return ok


def main():
    with get_db_connection() as conn:  # commits on success, rolls back on exception
        run(conn)
        print("Post-migration checks:")
        if not verify(conn):
            raise SystemExit("Verification failed — rolling back.")
    print("company_db state migration applied successfully.")


if __name__ == "__main__":
    main()
