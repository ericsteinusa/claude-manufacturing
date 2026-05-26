import os
import psycopg2
import psycopg2.extras


def get_db_connection():
    kwargs = {
        'database': os.environ.get('DB_NAME', 'company_db'),
        'user': os.environ.get('DB_USER', '') or None,
        'password': os.environ.get('DB_PASSWORD', '') or None,
        'port': int(os.environ.get('DB_PORT', '5432')),
    }
    host = os.environ.get('DB_HOST', '')
    if host:
        kwargs['host'] = host
    conn = psycopg2.connect(**kwargs)
    return PgConnection(conn)


class PgConnection:
    """Thin psycopg2 wrapper providing a sqlite3-compatible API."""

    def __init__(self, conn):
        self._conn = conn

    # --- cursor factory -------------------------------------------------

    def cursor(self, cursor_factory=None):
        factory = cursor_factory or psycopg2.extras.DictCursor
        return self._conn.cursor(cursor_factory=factory)

    # --- sqlite3-style shortcut methods ---------------------------------

    def execute(self, sql, params=None):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.executemany(sql, params_list)
        return cur

    def executescript(self, script):
        """Execute multiple semicolon-separated SQL statements."""
        cur = self._conn.cursor()
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)

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
