"""Token management for the mobile REST API.

Tokens are stored in the ``api_token`` table (TEXT UUID → people_id).
No expiry by default; call revoke_token on logout.
"""
import uuid
from datetime import datetime

from .menus import DEPT_MENU_KEY

_FULL_ACCESS = {'President', 'Vice President'}
_MANAGERS = {'Department Manager', 'Supervisor', 'President', 'Vice President'}


def ensure_api_token_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_token (
            token      TEXT PRIMARY KEY,
            people_id  INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT
        )
    """)
    conn.commit()


def create_token(conn, people_id: int) -> str:
    """Insert a new random token for people_id and return it. Does not commit."""
    token = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO api_token (token, people_id, created_at)"
        " VALUES (%s, %s, %s)",
        (token, people_id, datetime.now().isoformat()),
    )
    return token


def verify_token(conn, token: str) -> dict | None:
    """Return user info dict for a valid token, or None.

    Dict keys: id, email, role, dept_id, dept_name, dept_key,
               full_access, is_manager.
    """
    row = conn.execute("""
        SELECT at.people_id, p.email, d.dept_id, d.dept_name,
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


def revoke_token(conn, token: str) -> None:
    """Delete a token (logout). Does not commit."""
    conn.execute("DELETE FROM api_token WHERE token = %s", (token,))
