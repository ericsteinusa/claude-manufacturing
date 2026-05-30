#!/usr/bin/env python3
"""
migrate_people_dept_cleanup.py

One-off data migration that records the people/department cleanup applied to
company_db on 2026-05-30. Every step is idempotent, so re-running it is safe
and leaves the database in the same final state (already-applied steps become
no-ops). The whole migration runs in a single transaction — it either fully
applies or rolls back.

Run from the project root:

    python migrate_people_dept_cleanup.py

What it does:
  1. Remove the leftover test account 'newuser@test.com' (people.id=0 + its
     passwd credential) created by the registration flow.
  2. Remove the thin duplicate "Eric Steinman" (people.id=21 + its passwd) that
     had no roles/position/department links; the canonical Eric is people.id=1.
  3. Assign / reconcile the canonical Eric (id=1) to Information Technologies /
     IT Technician (dept_id=5, dept_sub_id=6) and fix his position job title.
  4. Repopulate the redundant `department` table from `people` so it mirrors the
     canonical per-person assignment (it had drifted for 8 of 9 rows).
  5. Fix the misspelled "Technition" sub-department names (IT, QA, Lab).
"""
from manufacturing.db_pg import get_db


def run(conn):
    # 1. Remove leftover test account (guarded by its identifying email so the
    #    DELETE can't touch an unrelated id=0 row on another database).
    conn.execute("DELETE FROM passwd WHERE people_id = 0")
    conn.execute("DELETE FROM people WHERE id = 0 AND email = 'newuser@test.com'")

    # 2. Remove the duplicate Eric Steinman (id=21); canonical record is id=1.
    conn.execute("DELETE FROM passwd WHERE people_id = 21")
    conn.execute("DELETE FROM people WHERE id = 21 AND email = 'eric@steinman.com'")

    # 3. Assign + reconcile the canonical Eric to IT / IT Technician.
    conn.execute(
        "UPDATE people SET dept_id = 5, dept_sub_id = 6 "
        "WHERE id = 1 AND email = 'eric@steinman.com'")
    conn.execute(
        "UPDATE position SET job_title = 'IT Technician' WHERE people_id = 1")

    # 4. Repopulate the `department` table from `people` (one row per person,
    #    mirroring the canonical dept assignment). Nothing references
    #    department.id, so a clean rebuild is safe.
    conn.execute("TRUNCATE department RESTART IDENTITY")
    conn.execute(
        "INSERT INTO department (people_id, dept_id, dept_sub_id) "
        "SELECT id, dept_id, dept_sub_id FROM people ORDER BY id")

    # 5. Fix misspelled sub-department names ("Technition" -> "Technician").
    conn.execute("UPDATE dept_sub SET dept_sub_name = 'IT Technician' WHERE dept_sub_id = 6")
    conn.execute("UPDATE dept_sub SET dept_sub_name = 'Quality Assurance Technician' WHERE dept_sub_id = 21")
    conn.execute("UPDATE dept_sub SET dept_sub_name = 'Lab Technician' WHERE dept_sub_id = 23")


def verify(conn):
    """Post-conditions — all should be zero / clean after a successful run."""
    checks = {
        "people w/ no department":
            "SELECT COUNT(*) FROM people WHERE dept_id IS NULL OR dept_sub_id IS NULL",
        "department rows mismatching people":
            "SELECT COUNT(*) FROM department dp JOIN people p ON dp.people_id = p.id "
            "WHERE dp.dept_id IS DISTINCT FROM p.dept_id "
            "OR dp.dept_sub_id IS DISTINCT FROM p.dept_sub_id",
        "people missing a department row":
            "SELECT COUNT(*) FROM people p "
            "WHERE NOT EXISTS (SELECT 1 FROM department dp WHERE dp.people_id = p.id)",
        "remaining 'Technition' misspellings":
            "SELECT COUNT(*) FROM dept_sub WHERE dept_sub_name ILIKE '%technit%'",
        "leftover test/duplicate rows":
            "SELECT COUNT(*) FROM people WHERE id IN (0, 21)",
    }
    ok = True
    for label, sql in checks.items():
        n = conn.execute(sql).fetchone()[0]
        flag = "ok" if n == 0 else "FAIL"
        if n != 0:
            ok = False
        print(f"  [{flag}] {label}: {n}")
    return ok


def main():
    with get_db() as conn:  # commits on success, rolls back on exception
        run(conn)
        # verify() reads inside the same transaction, before commit
        print("Post-migration checks:")
        if not verify(conn):
            raise SystemExit("Verification failed — rolling back.")
    print("Data cleanup migration applied successfully.")


if __name__ == "__main__":
    main()
