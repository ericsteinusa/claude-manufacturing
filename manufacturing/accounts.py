"""User accounts: authentication, registration, and role persistence."""

import datetime as _dt
import os
import re
import secrets
import bcrypt
import psycopg2

from .db_pg import get_db as _get_db
from .log_utils import get_logger
from .menus import DEPT_MENU_KEY

log = get_logger(__name__)

# Reverse of DEPT_MENU_KEY (dept_name -> dept_key), for resolving an
# SSO provider's configured default_dept_key back to a real department
# name when auto-provisioning a first-time SSO login.
_DEPT_KEY_TO_NAME = {v: k for k, v in DEPT_MENU_KEY.items()}

# Password rotation window. A NULL password_changed_at (every account that
# existed before this policy shipped) is treated as not-yet-expired rather
# than immediately locking out every seeded/pre-existing user — rotation is
# only enforced going forward from whenever a password is actually set.
PASSWORD_MAX_AGE_DAYS = 90

# Environment variable used to propagate the logged-in user's email to every
# subprocess spawned from the session (set once by login_app.SessionWindow).
_USER_ENV_VAR = 'MFGAPP_USER'

# Environment variable used to propagate the selected location name to every
# subprocess spawned from the session (set once by login_app.SessionWindow).
_LOCATION_ENV_VAR = 'MFGAPP_LOCATION'


def get_current_user_email() -> str:
    """Return the email of the user who launched this process, or ''."""
    return os.environ.get(_USER_ENV_VAR, '')


def get_current_location() -> str:
    """Return the location name selected at login for this process, or ''."""
    return os.environ.get(_LOCATION_ENV_VAR, '')


def list_locations() -> list[dict]:
    """Return active locations as [{id, name, code}, ...] sorted by name."""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT id, name, code FROM location "
            "WHERE is_active ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_current_user_profile() -> dict:
    """Return the profile dict for the currently logged-in user, or {}."""
    email = get_current_user_email()
    return _get_user_profile(email) if email else {}


FULL_ACCESS_ROLES = {'President', 'Vice President'}

MANAGER_DEPT_SUB_IDS = set()

READ_ONLY_ROLES = {'Auditor'}

# Roles permitted to administer user_roles (President / Vice President).
_ROLE_ADMIN_ROLES = FULL_ACCESS_ROLES


def _get_user_profile(email: str) -> dict:
    conn = _get_db()
    row = conn.execute("""
        SELECT p.id, p.dept_id, p.dept_sub_id, d.dept_name,
               r.role_name,
               pos.job_title AS position
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        LEFT JOIN position pos ON pos.people_id = p.id
        WHERE p.email = %s
        ORDER BY (r.role_name IS NOT NULL) DESC, p.id
        LIMIT 1
    """, (email,)).fetchone()
    conn.close()
    if not row:
        return {}
    dept_name = row['dept_name'] or ''
    dept_key = DEPT_MENU_KEY.get(dept_name)
    role_name = row['role_name'] or ''
    dept_sub_id = row['dept_sub_id']
    is_manager = (
        dept_sub_id in MANAGER_DEPT_SUB_IDS
        or role_name in {'Department Manager'} | FULL_ACCESS_ROLES
    )
    return {
        'people_id': row['id'],
        'dept_name': dept_name,
        'dept_key': dept_key,
        'role_name': role_name,
        'position': row['position'] or '',
        'dept_sub_id': dept_sub_id,
        'is_manager': is_manager,
    }


def _is_full_access(profile: dict) -> bool:
    """President and Vice President roles see all departments."""
    return profile.get('role_name') in FULL_ACCESS_ROLES


def _verify_login(email: str, password: str) -> bool:
    conn = _get_db()
    row = conn.execute(
        "SELECT pw.id as pw_id, pw.password FROM passwd pw "
        "JOIN people p ON pw.people_id = p.id "
        "WHERE p.email = %s ORDER BY pw.id DESC LIMIT 1",
        (email,),
    ).fetchone()
    if row is None:
        conn.close()
        log.warning("Login failed for %s: no such account", email)
        return False
    stored = row["password"]
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        ok = bcrypt.checkpw(password.encode(), stored.encode())
    else:
        ok = (password == stored)
        if ok:
            hashed = bcrypt.hashpw(
                password.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                "UPDATE passwd SET password = %s WHERE id = %s",
                (hashed, row["pw_id"]))
            conn.commit()
            log.info("Rehashed legacy plain-text password for %s", email)
    conn.close()
    if ok:
        log.info("Login succeeded for %s", email)
    else:
        log.warning("Login failed for %s: incorrect password", email)
    return ok


def validate_password_strength(password: str) -> str | None:
    """Return a human-readable error if *password* fails policy, else None.

    Policy: at least 8 characters, one uppercase, one lowercase, one digit.
    Pure function — no DB access — so callers can check before touching
    the database.
    """
    if len(password) < 8:
        return 'Password must be at least 8 characters.'
    if not re.search(r'[A-Z]', password):
        return 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return 'Password must contain at least one digit.'
    return None


def ensure_password_policy_columns(conn) -> None:
    """Lazily add the column password rotation tracking needs."""
    conn.execute(
        "ALTER TABLE passwd ADD COLUMN IF NOT EXISTS "
        "password_changed_at TIMESTAMPTZ")


def password_needs_rotation(conn, email: str,
                            max_age_days: int = PASSWORD_MAX_AGE_DAYS) -> bool:
    """True if this account's password is older than max_age_days.

    An account with no recorded change date (every account that predates
    this policy) is treated as not expired.
    """
    ensure_password_policy_columns(conn)
    row = conn.execute(
        "SELECT pw.password_changed_at FROM passwd pw "
        "JOIN people p ON pw.people_id = p.id "
        "WHERE p.email = %s ORDER BY pw.id DESC LIMIT 1",
        (email,),
    ).fetchone()
    if not row or not row['password_changed_at']:
        return False
    changed_at = row['password_changed_at']
    age_days = (_dt.datetime.now(tz=_dt.timezone.utc) - changed_at).days
    return age_days >= max_age_days


def _email_exists(email: str) -> bool:
    conn = _get_db()
    found = conn.execute(
        "SELECT id FROM people WHERE email = %s", (email,)).fetchone()
    conn.close()
    return found is not None


def _create_user(email, password, first_name='', last_name='',
                 address='', city='', state='', zip_code='',
                 employee_id=0, dept_id=None) -> bool:
    conn = _get_db()
    try:
        if conn.execute("SELECT id FROM people WHERE email = %s",
                        (email,)).fetchone():
            conn.close()
            log.warning("User creation rejected: %s already exists", email)
            return False
        cursor = conn.execute(
            "INSERT INTO people (first_name, last_name, "
            "employee_id, address, city, state, zip_code, email, dept_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (first_name, last_name, employee_id,
             address, city, state, zip_code, email, dept_id),
        )
        people_id = cursor.fetchone()['id']
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        ensure_password_policy_columns(conn)
        conn.execute(
            "INSERT INTO passwd (people_id, password, password_changed_at) "
            "VALUES (%s, %s, NOW())",
            (people_id, hashed),
        )
        conn.commit()
        conn.close()
        log.info("Created user %s (people_id=%s)", email, people_id)
        return True
    except psycopg2.IntegrityError:
        log.warning(
            "User creation failed for %s: integrity error", email,
            exc_info=True)
        conn.close()
        return False


def provision_sso_user(email: str, claims: dict, dept_key: str) -> bool:
    """Create a new account for a first-time SSO login that has no existing
    people row, in the department named by *dept_key*, with no role row —
    the same least-privilege state an existing roleless account already has
    in this app (whole-view access scoped to their own department only,
    never full-access). Returns False (denying the login) if dept_key
    doesn't resolve to a real department, rather than creating an orphaned
    account with no department at all.

    Deliberately does NOT attempt to map arbitrary IdP group/role claims
    onto a role — that mapping is customer-tenant-specific and unverifiable
    without a real tenant's actual claim shape (see sso_core.py's module
    docstring). What this closes is narrower and safer: the account gets
    created automatically instead of requiring an admin to pre-create it,
    always landing in one fixed, admin-configured department with no
    elevated access.

    The created account gets a random password nobody knows (a real
    passwd row is still required elsewhere in this schema) — it exists
    only so the account is well-formed; the account is only reachable via
    SSO unless the owner later resets it through the normal
    forgot-password flow.
    """
    dept_name = _DEPT_KEY_TO_NAME.get(dept_key)
    if not dept_name:
        log.error(
            "SSO auto-provision denied for %s: unknown dept_key %r",
            email, dept_key)
        return False

    conn = _get_db()
    dept_row = conn.execute(
        "SELECT dept_id FROM dept WHERE dept_name = %s", (dept_name,)
    ).fetchone()
    conn.close()
    if not dept_row:
        log.error(
            "SSO auto-provision denied for %s: department %r not found",
            email, dept_name)
        return False

    first = claims.get('given_name', '') or ''
    last = claims.get('family_name', '') or ''
    if not first and not last:
        full_name = (claims.get('name') or '').strip()
        parts = full_name.split(' ', 1) if full_name else []
        first = parts[0] if parts else email.split('@')[0]
        last = parts[1] if len(parts) > 1 else ''

    ok = _create_user(
        email, secrets.token_urlsafe(32), first, last,
        dept_id=dept_row['dept_id'])
    if ok:
        log.info(
            "SSO auto-provisioned new account for %s in dept %r",
            email, dept_name)
    return ok


def _reset_password(email: str, new_password: str) -> bool:
    conn = _get_db()
    row = conn.execute(
        "SELECT pw.id as pw_id FROM passwd pw "
        "JOIN people p ON pw.people_id = p.id "
        "WHERE p.email = %s ORDER BY pw.id DESC LIMIT 1",
        (email,),
    ).fetchone()
    if row is None:
        conn.close()
        log.warning("Password reset failed for %s: no such account", email)
        return False
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    ensure_password_policy_columns(conn)
    conn.execute(
        "UPDATE passwd SET password = %s, password_changed_at = NOW() "
        "WHERE id = %s",
        (hashed, row["pw_id"]))
    conn.commit()
    conn.close()
    log.info("Password reset for %s", email)
    return True


def _get_all_users_with_roles():
    conn = _get_db()
    rows = conn.execute("""
        SELECT p.id, p.first_name, p.last_name, p.email,
               d.dept_name,
               r.id as role_id, r.role_name
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        ORDER BY d.dept_name, p.last_name, p.first_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_all_roles():
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, role_name FROM roles ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _set_user_role(people_id: int, role_id: int):
    conn = _get_db()
    conn.execute("""
        INSERT INTO user_roles (people_id, role_id) VALUES (%s, %s)
        ON CONFLICT(people_id) DO UPDATE SET role_id = excluded.role_id
    """, (people_id, role_id))
    conn.commit()
    conn.close()
    log.info("Set role_id=%s for people_id=%s", role_id, people_id)


def _remove_user_role(people_id: int):
    conn = _get_db()
    cur = conn.execute(
        "DELETE FROM user_roles WHERE people_id = %s", (people_id,))
    removed = cur.rowcount
    conn.commit()
    conn.close()
    if removed:
        log.info("Removed role for people_id=%s", people_id)
