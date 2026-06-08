"""
schema.py — Single source of truth for the application's database schema.

Historically the core tables (people, passwd, roles, user_roles, dept,
dept_sub, position) were created with divergent ``CREATE TABLE IF NOT EXISTS``
statements scattered across half a dozen modules. Because ``IF NOT EXISTS``
means whichever statement runs first wins, the live schema depended on import
order. This module centralizes the canonical definitions.

Usage:
    from schema import init_schema

    init_schema()   # idempotent: safe to call on every startup

``init_schema`` both creates any missing tables and reconciles existing
tables created from an older, narrower definition by adding any missing
columns (``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``).
"""

from .db_pg import get_db
from .log_utils import get_logger

log = get_logger(__name__)

# Ordered so a table is created before any table whose foreign keys
# reference it (people/dept/roles first).
_TABLES = [
    ("people", """
        CREATE TABLE IF NOT EXISTS people (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL DEFAULT '',
            last_name TEXT NOT NULL DEFAULT '',
            employee_id INTEGER NOT NULL DEFAULT 0,
            emp_id INTEGER,
            address TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '',
            zip_code TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            dept_id INTEGER,
            dept_sub_id INTEGER
        )
    """),
    ("dept", """
        CREATE TABLE IF NOT EXISTS dept (
            dept_id SERIAL PRIMARY KEY,
            dept_name TEXT NOT NULL UNIQUE
        )
    """),
    ("dept_sub", """
        CREATE TABLE IF NOT EXISTS dept_sub (
            dept_sub_id SERIAL PRIMARY KEY,
            dept_id INTEGER,
            dept_sub_name TEXT NOT NULL,
            FOREIGN KEY (dept_id) REFERENCES dept(dept_id)
        )
    """),
    ("roles", """
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            role_name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """),
    ("passwd", """
        CREATE TABLE IF NOT EXISTS passwd (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL UNIQUE,
            password TEXT NOT NULL,
            FOREIGN KEY (people_id) REFERENCES people(id)
        )
    """),
    ("user_roles", """
        CREATE TABLE IF NOT EXISTS user_roles (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL UNIQUE,
            role_id INTEGER NOT NULL,
            FOREIGN KEY (people_id) REFERENCES people(id),
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    """),
    ("position", """
        CREATE TABLE IF NOT EXISTS position (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL UNIQUE,
            job_title TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (people_id) REFERENCES people(id)
        )
    """),
]

# Columns backfilled onto pre-existing tables that may have been created from
# an older, narrower definition. Keyed by table; each entry is (name, def).
# Only additive columns are reconciled — constraints on existing tables are
# left untouched.
_RECONCILE = {
    "people": [
        ("first_name", "TEXT NOT NULL DEFAULT ''"),
        ("last_name", "TEXT NOT NULL DEFAULT ''"),
        ("employee_id", "INTEGER NOT NULL DEFAULT 0"),
        ("emp_id", "INTEGER"),
        ("address", "TEXT NOT NULL DEFAULT ''"),
        ("city", "TEXT NOT NULL DEFAULT ''"),
        ("state", "TEXT NOT NULL DEFAULT ''"),
        ("zip_code", "TEXT NOT NULL DEFAULT ''"),
        ("email", "TEXT NOT NULL DEFAULT ''"),
        ("dept_id", "INTEGER"),
        ("dept_sub_id", "INTEGER"),
    ],
    "dept_sub": [
        ("dept_id", "INTEGER"),
    ],
}


def init_schema():
    """Create and reconcile the application's core tables (idempotent)."""
    conn = get_db()
    try:
        for _name, ddl in _TABLES:
            conn.execute(ddl)
        for table, columns in _RECONCILE.items():
            for col, col_def in columns:
                conn.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN IF NOT EXISTS {col} {col_def}")
        conn.commit()
    finally:
        conn.close()
    log.debug("Schema initialized and reconciled (%d tables)", len(_TABLES))
