import os
import re
import sqlite3

_DB_PATH = os.path.join(os.path.dirname(__file__), 'company.db')


def get_db_connection():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return SqliteAdapter(conn)


class SqliteAdapter:
    """Wraps sqlite3.Connection with a psycopg2-compatible SQL API.

    Translates PostgreSQL syntax (SERIAL, %s, %(name)s, RETURNING id,
    ON CONFLICT DO NOTHING) to SQLite equivalents at execution time so
    callers don't need to know which backend is in use.
    """

    def __init__(self, conn):
        self._conn = conn

    # --- cursor factory -------------------------------------------------

    def cursor(self, cursor_factory=None):
        return SqliteAdapterCursor(self._conn.cursor())

    # --- shortcut methods -----------------------------------------------

    def execute(self, sql, params=None):
        has_returning = bool(re.search(r'\bRETURNING\b', sql, re.IGNORECASE))
        sql = _translate(sql, params)
        cur = self._conn.cursor()
        if params is not None:
            cur.execute(sql, _coerce(params))
        else:
            cur.execute(sql)
        return SqliteAdapterCursor(cur, returning_id=has_returning)

    def executemany(self, sql, params_list):
        sample = params_list[0] if params_list else None
        sql = _translate(sql, sample)
        cur = self._conn.cursor()
        cur.executemany(sql, [_coerce(p) for p in params_list])
        return SqliteAdapterCursor(cur)

    def executescript(self, script):
        cur = self._conn.cursor()
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                cur.execute(_translate(stmt))

    # --- transaction control --------------------------------------------

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


class SqliteAdapterCursor:
    def __init__(self, cur, returning_id=False):
        self._cur = cur
        self._returning_id = returning_id

    def fetchone(self):
        if self._returning_id:
            return {'id': self._cur.lastrowid}
        return self._cur.fetchone()  # sqlite3.Row: supports row["name"] and row[0]

    def fetchall(self):
        return self._cur.fetchall()  # list of sqlite3.Row

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def __iter__(self):
        return self

    def __next__(self):
        row = self._cur.fetchone()
        if row is None:
            raise StopIteration
        return row

    def __getitem__(self, key):
        return self._cur[key]


def _translate(sql, params=None):
    """Convert PostgreSQL SQL dialect to SQLite."""
    # SERIAL PRIMARY KEY → INTEGER PRIMARY KEY AUTOINCREMENT
    sql = re.sub(
        r'\bSERIAL\s+PRIMARY\s+KEY\b',
        'INTEGER PRIMARY KEY AUTOINCREMENT',
        sql, flags=re.IGNORECASE
    )
    # INSERT INTO x ... ON CONFLICT (...) DO NOTHING → INSERT OR IGNORE INTO x ...
    sql = re.sub(
        r'\bINSERT\s+INTO\b(.*?)\s+ON\s+CONFLICT\s*\([^)]*\)\s*DO\s+NOTHING',
        r'INSERT OR IGNORE INTO\1',
        sql, flags=re.IGNORECASE | re.DOTALL
    )
    # Strip RETURNING clause (lastrowid is used instead via returning_id flag)
    sql = re.sub(r'\s+RETURNING\s+\w+', '', sql, flags=re.IGNORECASE)
    # Named params: %(name)s → :name
    sql = re.sub(r'%\((\w+)\)s', r':\1', sql)
    # Positional params: %s → ?
    sql = sql.replace('%s', '?')
    return sql


def _coerce(params):
    """Ensure params are a tuple or dict (sqlite3 requirement)."""
    if isinstance(params, list):
        return tuple(params)
    return params
