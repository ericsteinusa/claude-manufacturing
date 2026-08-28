"""Token management for the mobile REST API.

Tokens are stored in the ``api_token`` table (TEXT UUID → people_id).
Tokens expire after TOKEN_LIFETIME_HOURS (default 8) and can be refreshed
via refresh_token().  Rate limiting prevents brute-force login attempts.
Optional TOTP (RFC 6238) can be enabled per user.
"""
import base64
import hashlib
import hmac
import os
import struct
import time
import uuid
from datetime import datetime, timedelta, timezone

from .menus import DEPT_MENU_KEY

_FULL_ACCESS = {'President', 'Vice President'}
_MANAGERS = {'Department Manager', 'Supervisor', 'President', 'Vice President'}

TOKEN_LIFETIME_HOURS = 8
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_MINUTES = 15

# Per-endpoint API rate limiting (distinct from the login-attempt lockout
# above): caps how many requests one authenticated user can make against
# one endpoint in a rolling window, applied to every @api_required view.
API_RATE_LIMIT_MAX_REQUESTS = 120
API_RATE_LIMIT_WINDOW_SECONDS = 60


# ---------------------------------------------------------------------------
# Table DDL
# ---------------------------------------------------------------------------

def ensure_api_token_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_token (
            token      TEXT PRIMARY KEY,
            people_id  INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_login_attempt (
            id          SERIAL PRIMARY KEY,
            identifier  TEXT NOT NULL,
            attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            success     BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS api_login_attempt_ident
        ON api_login_attempt(identifier, attempted_at DESC)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_request_log (
            id           SERIAL PRIMARY KEY,
            identifier   TEXT NOT NULL,
            endpoint     TEXT NOT NULL,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS api_request_log_ident
        ON api_request_log(identifier, endpoint, requested_at DESC)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_totp_secret (
            people_id  INTEGER PRIMARY KEY,
            secret_b32 TEXT NOT NULL,
            enabled    BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # audit_core.AUDITED_TABLES requires every audited table to have an
    # integer `id` column (its generic trigger reads NEW.id/OLD.id) —
    # api_totp_secret's natural key is people_id, so add a plain id
    # column purely to satisfy that invariant. ADD COLUMN IF NOT EXISTS
    # for tables that already exist from before this was caught.
    conn.execute(
        "ALTER TABLE api_totp_secret ADD COLUMN IF NOT EXISTS id SERIAL")
    conn.commit()


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------

def _expires_at() -> str:
    return (datetime.now(tz=timezone.utc)
            + timedelta(hours=TOKEN_LIFETIME_HOURS)).isoformat()


def create_token(conn, people_id: int) -> str:
    """Insert a new token valid for TOKEN_LIFETIME_HOURS and return it."""
    token = uuid.uuid4().hex
    exp = _expires_at()
    conn.execute(
        "INSERT INTO api_token (token, people_id, created_at, expires_at)"
        " VALUES (%s, %s, %s, %s)",
        (token, people_id, datetime.now(tz=timezone.utc).isoformat(), exp),
    )
    return token


def verify_token(conn, token: str) -> dict | None:
    """Return user info dict for a valid, non-expired token, or None."""
    row = conn.execute("""
        SELECT at.people_id, at.expires_at,
               p.email, d.dept_id, d.dept_name,
               r.role_name
        FROM api_token at
        JOIN people p ON p.id = at.people_id
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE at.token = %s
        ORDER BY (r.role_name IS NOT NULL) DESC
        LIMIT 1
    """, (token,)).fetchone()
    if not row:
        return None
    # Enforce expiry
    if row['expires_at']:
        exp = datetime.fromisoformat(row['expires_at'])
        now = datetime.now(tz=timezone.utc)
        # Make both offset-aware for comparison
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            return None
    role = row['role_name'] or ''
    dept_name = row['dept_name'] or ''
    return {
        'id': row['people_id'],
        'email': row['email'],
        'role': role,
        'dept_id': row['dept_id'],
        'dept_name': dept_name,
        'dept_key': DEPT_MENU_KEY.get(dept_name),
        'full_access': role in _FULL_ACCESS,
        'is_manager': role in _MANAGERS,
    }


def refresh_token(conn, token: str) -> bool:
    """Extend an existing token's expiry by TOKEN_LIFETIME_HOURS.

    Returns True if the token existed (expired or not), False if not found.
    Does not commit.
    """
    row = conn.execute(
        "SELECT token FROM api_token WHERE token = %s", (token,)
    ).fetchone()
    if not row:
        return False
    conn.execute(
        "UPDATE api_token SET expires_at = %s WHERE token = %s",
        (_expires_at(), token),
    )
    return True


def revoke_token(conn, token: str) -> None:
    """Delete a token (logout). Does not commit."""
    conn.execute("DELETE FROM api_token WHERE token = %s", (token,))


def revoke_all_tokens(conn, people_id: int) -> None:
    """Revoke all tokens for a user (e.g. on password change). Does not commit."""
    conn.execute(
        "DELETE FROM api_token WHERE people_id = %s", (people_id,)
    )


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def record_login_attempt(conn, identifier: str, success: bool) -> None:
    """Log a login attempt keyed by email or IP address. Does not commit."""
    conn.execute(
        "INSERT INTO api_login_attempt (identifier, success) VALUES (%s, %s)",
        (identifier, success),
    )


def is_rate_limited(conn, identifier: str,
                    max_attempts: int = _LOGIN_MAX_ATTEMPTS,
                    window_minutes: int = _LOGIN_WINDOW_MINUTES) -> bool:
    """Return True if *identifier* has too many failed attempts in the window."""
    row = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM api_login_attempt
        WHERE identifier = %s
          AND success = FALSE
          AND attempted_at > NOW() - (%s * INTERVAL '1 minute')
    """, (identifier, window_minutes)).fetchone()
    return (row['cnt'] if row else 0) >= max_attempts


def purge_old_attempts(conn, keep_minutes: int = 60) -> int:
    """Delete attempts older than keep_minutes. Returns row count deleted."""
    cur = conn.execute(
        "DELETE FROM api_login_attempt "
        "WHERE attempted_at < NOW() - (%s * INTERVAL '1 minute')",
        (keep_minutes,),
    )
    return cur.rowcount if hasattr(cur, 'rowcount') else 0


# ---------------------------------------------------------------------------
# Per-endpoint API rate limiting
#
# Distinct from the failed-login-attempt lockout above: this counts *every*
# request (successful or not) a given user makes against a given endpoint,
# so an authenticated client hammering one endpoint gets throttled even
# though every individual call succeeds. Applied automatically to every
# @api_required view (see api_decorators.py) rather than opt-in per view.
# ---------------------------------------------------------------------------

def record_api_request(conn, identifier: str, endpoint: str) -> None:
    """Log one API request. Does not commit."""
    conn.execute(
        "INSERT INTO api_request_log (identifier, endpoint) VALUES (%s, %s)",
        (identifier, endpoint),
    )


def is_api_rate_limited(conn, identifier: str, endpoint: str,
                        max_requests: int = API_RATE_LIMIT_MAX_REQUESTS,
                        window_seconds: int = API_RATE_LIMIT_WINDOW_SECONDS) -> bool:
    """Return True if *identifier* has made >= max_requests calls to
    *endpoint* within the last window_seconds."""
    row = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM api_request_log
        WHERE identifier = %s
          AND endpoint = %s
          AND requested_at > NOW() - (%s * INTERVAL '1 second')
    """, (identifier, endpoint, window_seconds)).fetchone()
    return (row['cnt'] if row else 0) >= max_requests


def purge_old_api_requests(conn, keep_minutes: int = 60) -> int:
    """Delete request-log rows older than keep_minutes. Returns row count deleted."""
    cur = conn.execute(
        "DELETE FROM api_request_log "
        "WHERE requested_at < NOW() - (%s * INTERVAL '1 minute')",
        (keep_minutes,),
    )
    return cur.rowcount if hasattr(cur, 'rowcount') else 0


# ---------------------------------------------------------------------------
# TOTP  (RFC 6238, SHA-1, 6-digit, 30-second window)
# ---------------------------------------------------------------------------

def generate_totp_secret() -> str:
    """Return a random 32-char base32 secret suitable for Google Authenticator."""
    return base64.b32encode(os.urandom(20)).decode()


def _hotp(key_bytes: bytes, counter: int, digits: int = 6) -> str:
    msg = struct.pack('>Q', counter)
    h = hmac.new(key_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0f
    code = struct.unpack('>I', h[offset:offset + 4])[0] & 0x7fffffff
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp_code(secret_b32: str, code: str, window: int = 1) -> bool:
    """Return True if *code* matches the current TOTP for *secret_b32*.

    Allows ±window steps (±30 s each) to account for clock skew.
    """
    try:
        key = base64.b32decode(secret_b32.upper().replace(' ', ''))
    except Exception:
        return False
    t = int(time.time()) // 30
    for delta in range(-window, window + 1):
        if _hotp(key, t + delta) == str(code).strip():
            return True
    return False


def set_totp_secret(conn, people_id: int, secret_b32: str) -> None:
    """Upsert a TOTP secret for a user. Does not commit."""
    conn.execute(
        "INSERT INTO api_totp_secret (people_id, secret_b32, enabled) "
        "VALUES (%s, %s, TRUE) "
        "ON CONFLICT (people_id) DO UPDATE "
        "SET secret_b32 = EXCLUDED.secret_b32, enabled = TRUE",
        (people_id, secret_b32),
    )


def get_totp_secret(conn, people_id: int) -> str | None:
    """Return the active base32 secret for a user, or None if not enrolled."""
    row = conn.execute(
        "SELECT secret_b32 FROM api_totp_secret "
        "WHERE people_id = %s AND enabled = TRUE",
        (people_id,),
    ).fetchone()
    return row['secret_b32'] if row else None


def disable_totp(conn, people_id: int) -> None:
    """Disable TOTP for a user without deleting the secret. Does not commit."""
    conn.execute(
        "UPDATE api_totp_secret SET enabled = FALSE WHERE people_id = %s",
        (people_id,),
    )


def verify_totp_for_user(conn, people_id: int, code: str) -> bool:
    """Return True if *code* is a valid current TOTP for this user.

    Returns True (bypass) when the user has no TOTP enrolled/enabled.
    """
    secret = get_totp_secret(conn, people_id)
    if secret is None:
        return True
    return verify_totp_code(secret, code)
