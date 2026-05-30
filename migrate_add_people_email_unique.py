#!/usr/bin/env python3
"""
migrate_add_people_email_unique.py

Adds a UNIQUE constraint on people.email. Duplicate-email rows (created by the
registration flow) were the root cause of privileged users getting locked out
of the app — a role-less duplicate could shadow the real account in the
email-based profile lookup. This constraint prevents such duplicates at the
source.

Idempotent and safe:
  * Aborts (without changing anything) if duplicate or NULL/empty emails exist,
    printing the offending values so they can be resolved first.
  * No-ops if the constraint is already present.

Run from the project root:

    python migrate_add_people_email_unique.py
"""
from manufacturing.db_pg import get_db_connection  # native PG (no SQL translation)

CONSTRAINT = "people_email_unique"


def main():
    with get_db_connection() as conn:  # commits on success, rolls back on error
        # Already applied? -> no-op.
        exists = conn.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = %s", (CONSTRAINT,)
        ).fetchone()
        if exists:
            print(f"Constraint {CONSTRAINT} already present — nothing to do.")
            return

        # Pre-flight: a UNIQUE constraint can't be added if these exist.
        dups = conn.execute("""
            SELECT email, COUNT(*) AS n FROM people
            GROUP BY email HAVING COUNT(*) > 1 ORDER BY n DESC
        """).fetchall()
        blanks = conn.execute(
            "SELECT COUNT(*) AS n FROM people WHERE email IS NULL OR TRIM(email) = ''"
        ).fetchone()["n"]
        if dups or blanks:
            print("ABORT — resolve these before adding the constraint:")
            for r in dups:
                print(f"  duplicate email {r['email']!r} x{r['n']}")
            if blanks:
                print(f"  {blanks} row(s) with NULL/empty email")
            raise SystemExit(1)

        conn.execute(
            f"ALTER TABLE people ADD CONSTRAINT {CONSTRAINT} UNIQUE (email)")
        print(f"Added UNIQUE constraint {CONSTRAINT} on people.email.")


if __name__ == "__main__":
    main()
