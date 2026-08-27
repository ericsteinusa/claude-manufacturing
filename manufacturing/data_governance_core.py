"""data_governance_core.py — Qt-free GDPR-style data governance tooling.

Closes COMPETITIVE_GAP_ANALYSIS.md §6.4: right-to-erasure, per-subject data
export, and a retention-policy engine to auto-anonymize long-terminated
employees. "Erasure" here means anonymization, not row deletion — PII
columns on the person's own `people` row are overwritten with placeholders
and their login access is revoked, but every other table's people_id-
referencing history (time clock, payroll, reviews, notifications, etc.) is
left untouched, since deleting it would destroy financial/operational
records this app needs to keep. This is the same retain-history/redact-
identity tradeoff CLAUDE.md's gap-analysis notes already called for.

`people` is already one of audit_core.py's AUDITED_TABLES, so an
anonymize's own UPDATE is captured with full old/new JSONB values by the
existing DB-trigger audit trail for free. `erasure_log` below is a
lightweight, purpose-built index on top of that (fast "when was this
person erased, by whom, why" lookups) rather than a duplicate audit
mechanism.
"""
import datetime

from .api_auth import revoke_all_tokens, disable_totp

REDACTED_NAME = 'Redacted'

# Tables (other than `people` itself) that carry a people_id FK, joined for
# the "give me everything you have on me" subject-access export. Kept as an
# explicit list rather than introspected from information_schema so a
# newly added FK doesn't silently start or stop appearing in exports without
# a deliberate code change.
_SUBJECT_TABLES = [
    ('time_clock', 'people_id'),
    ('time_off_request', 'people_id'),
    ('time_off_balance', 'people_id'),
    ('position', 'people_id'),
    ('user_roles', 'people_id'),
    ('pers_review', 'people_id'),
    ('pers_training', 'people_id'),
    ('cs_training', 'people_id'),
    ('employee_skill', 'people_id'),
    ('employee_pay', 'people_id'),
    ('employee_deduction', 'people_id'),
    ('payroll_entry', 'people_id'),
    ('benefit_enrollment', 'people_id'),
    ('exit_interview', 'people_id'),
    ('offboarding_task', 'people_id'),
    ('termination_record', 'people_id'),
    ('notification', 'people_id'),
    ('consultant', 'people_id'),
    ('company_user', 'people_id'),
    ('api_token', 'people_id'),
    ('api_totp_secret', 'people_id'),
]


def ensure_data_governance_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS erasure_log (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL,
            person_name TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            performed_by TEXT NOT NULL DEFAULT '',
            performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS retention_policy (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            months_after_termination INTEGER NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Right to erasure
# ---------------------------------------------------------------------------

def anonymize_person(conn, person_id: int, performed_by: str, reason: str = '') -> None:
    """Overwrite this person's PII on `people` with placeholders and revoke
    their login access (deletes their passwd row, revokes API tokens,
    disables TOTP). Every other table's people_id-referencing rows are left
    exactly as they are — see module docstring. Idempotent: anonymizing an
    already-anonymized person just re-writes the same placeholders.
    """
    ensure_data_governance_tables(conn)
    row = conn.execute(
        "SELECT first_name, last_name FROM people WHERE id = %s", (person_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f'No person with id {person_id}')
    person_name = f"{row['first_name']} {row['last_name']}".strip()

    placeholder_email = f'redacted-{person_id}@example.invalid'
    conn.execute(
        "UPDATE people SET first_name = %s, last_name = %s, address = '', "
        "city = '', state = '', zip_code = '', email = %s, phone = '', "
        "emergency_contact_name = '', emergency_contact_phone = '', "
        "emergency_contact_relationship = '' WHERE id = %s",
        (REDACTED_NAME, REDACTED_NAME, placeholder_email, person_id),
    )
    conn.execute("DELETE FROM passwd WHERE people_id = %s", (person_id,))
    revoke_all_tokens(conn, person_id)
    disable_totp(conn, person_id)
    conn.execute(
        "INSERT INTO erasure_log (people_id, person_name, reason, performed_by) "
        "VALUES (%s, %s, %s, %s)",
        (person_id, person_name, reason, performed_by),
    )


def list_erasure_log(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, people_id, person_name, reason, performed_by, performed_at "
        "FROM erasure_log ORDER BY performed_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Subject data export ("give me everything you have on me")
# ---------------------------------------------------------------------------

def _existing_tables(conn, table_names: list[str]) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (table_names,),
    ).fetchall()
    return {r['table_name'] for r in rows}


def export_person_data(conn, person_id: int) -> dict:
    """Return {'people': {...}, '<table>': [rows...], ...} covering every
    table that references this person by people_id. Column set per table is
    whatever the row actually has — deliberately unfiltered, since the point
    of a subject-access export is completeness, not curation. Tables that
    don't exist yet on this DB (several are lazily created on first write)
    are silently skipped rather than erroring.
    """
    person = conn.execute(
        "SELECT * FROM people WHERE id = %s", (person_id,)
    ).fetchone()
    if person is None:
        raise ValueError(f'No person with id {person_id}')

    result = {'people': dict(person)}
    existing = _existing_tables(conn, [t for t, _ in _SUBJECT_TABLES])
    for table, column in _SUBJECT_TABLES:
        if table not in existing:
            continue
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {column} = %s", (person_id,)
        ).fetchall()
        if rows:
            result[table] = [dict(r) for r in rows]
    return result


# ---------------------------------------------------------------------------
# Retention policy engine
# ---------------------------------------------------------------------------

def create_retention_policy(conn, name: str, months_after_termination: int,
                            is_active: bool = True) -> int:
    row = conn.execute(
        "INSERT INTO retention_policy (name, months_after_termination, is_active) "
        "VALUES (%s, %s, %s) RETURNING id",
        (name, months_after_termination, is_active),
    ).fetchone()
    return row['id']


def list_retention_policies(conn, active_only: bool = False) -> list[dict]:
    sql = ("SELECT id, name, months_after_termination, is_active, created_at "
           "FROM retention_policy")
    if active_only:
        sql += " WHERE is_active = TRUE"
    sql += " ORDER BY id"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_retention_policy(conn, policy_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, name, months_after_termination, is_active, created_at "
        "FROM retention_policy WHERE id = %s", (policy_id,)
    ).fetchone()
    return dict(row) if row else None


def update_retention_policy(conn, policy_id: int, name=None,
                            months_after_termination=None, is_active=None) -> None:
    conn.execute(
        "UPDATE retention_policy SET "
        "name = COALESCE(%s, name), "
        "months_after_termination = COALESCE(%s, months_after_termination), "
        "is_active = COALESCE(%s, is_active) "
        "WHERE id = %s",
        (name, months_after_termination, is_active, policy_id),
    )


def delete_retention_policy(conn, policy_id: int) -> None:
    conn.execute("DELETE FROM retention_policy WHERE id = %s", (policy_id,))


def find_retention_candidates(conn, policy: dict) -> list[dict]:
    """People whose termination_date is old enough to qualify for this
    policy's auto-anonymize cutoff. Skips anyone already anonymized (name
    already the redacted placeholder) and anyone with no parseable
    termination_date — the same silent-exclusion-over-fabrication choice
    workforce_analytics_core already makes for missing hire dates.
    """
    rows = conn.execute(
        "SELECT id, first_name, last_name, termination_date FROM people "
        "WHERE employment_status = 'terminated' AND first_name != %s",
        (REDACTED_NAME,),
    ).fetchall()
    cutoff = datetime.date.today() - datetime.timedelta(
        days=30 * policy['months_after_termination'])
    candidates = []
    for row in rows:
        term = _parse_date(row['termination_date'])
        if term and term <= cutoff:
            candidates.append(dict(row))
    return candidates


def apply_retention_policies(conn, performed_by: str = 'system:retention_policy') -> list[int]:
    """Run every active retention policy, anonymizing every matching person.
    Returns the list of people_ids anonymized. Commits once per person
    (rather than this codebase's usual "caller controls the transaction"
    convention) since this runs unattended as a scheduled batch job — one
    bad row shouldn't roll back everyone else already processed in the same
    run.
    """
    ensure_data_governance_tables(conn)
    anonymized = []
    for policy in list_retention_policies(conn, active_only=True):
        for person in find_retention_candidates(conn, policy):
            anonymize_person(
                conn, person['id'], performed_by,
                reason=f"Retention policy: {policy['name']}",
            )
            conn.commit()
            anonymized.append(person['id'])
    return anonymized
