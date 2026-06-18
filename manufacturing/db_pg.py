import os
import re
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from .log_utils import get_logger

load_dotenv()

log = get_logger(__name__)

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'dbname':   os.environ.get('DB_NAME', 'company_db'),
    'user':     os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'port':     int(os.environ.get('DB_PORT', '5432')),
}

_RE_AUTOINCREMENT = re.compile(
    r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
     re.IGNORECASE)
_RE_INSERT_IGNORE = re.compile(r'INSERT\s+OR\s+IGNORE\s+INTO', re.IGNORECASE)
_RE_ROWID_STAR = re.compile(r'SELECT\s+rowid\s*,\s*\*', re.IGNORECASE)
_RE_NAMED_PARAM = re.compile(r':([A-Za-z_]\w*)')
_RE_DATETIME_NOW = re.compile(r"datetime\s*\(\s*'now'\s*\)", re.IGNORECASE)
_RE_DATE_NOW = re.compile(r"\bdate\s*\(\s*'now'\s*\)", re.IGNORECASE)
# CAST(julianday('now')-julianday(X) AS INT) -> (CURRENT_DATE - X::date)
_RE_JULIANDAY_DIFF_NOW = re.compile(
    r"CAST\s*\(\s*julianday\s*\(\s*'now'\s*\)\s*-\s*julianday\s*\(([^)]+)\)\s*AS\s+INT\s*\)",  # noqa: E501
    re.IGNORECASE)
# julianday(X) - julianday(Y) -> (X::date - Y::date)
_RE_JULIANDAY_DIFF = re.compile(
    r"julianday\s*\(([^)]+)\)\s*-\s*julianday\s*\(([^)]+)\)",
    re.IGNORECASE)
# strftime('%Y-%m', col) -> TO_CHAR(col::timestamp, 'YYYY-MM')
_RE_STRFTIME_YM = re.compile(
    r"strftime\s*\(\s*'%Y-%m'\s*,\s*([^,)]+)\)",
     re.IGNORECASE)
# strftime('%Y', col) -> TO_CHAR(col::timestamp, 'YYYY')
_RE_STRFTIME_Y = re.compile(
    r"strftime\s*\(\s*'%Y'\s*,\s*([^,)]+)\)",
     re.IGNORECASE)


def _adapt(sql):
    sql = _RE_ROWID_STAR.sub('SELECT id, *', sql)
    sql = re.sub(r'\browid\b', 'id', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\boid\b', 'id', sql, flags=re.IGNORECASE)
    sql = sql.replace('?', '%s')
    sql = _RE_NAMED_PARAM.sub(r'%(\1)s', sql)
    if _RE_INSERT_IGNORE.search(sql):
        sql = _RE_INSERT_IGNORE.sub('INSERT INTO', sql)
        sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    sql = _RE_AUTOINCREMENT.sub('SERIAL PRIMARY KEY', sql)
    sql = _RE_DATETIME_NOW.sub('CURRENT_TIMESTAMP', sql)
    sql = _RE_DATE_NOW.sub("CURRENT_DATE::text", sql)
    sql = _RE_JULIANDAY_DIFF_NOW.sub(
        lambda m: f"(CURRENT_DATE - ({m.group(1).strip()})::date)", sql)
    sql = _RE_JULIANDAY_DIFF.sub(
        lambda m: f"({m.group(1).strip()}::date - {m.group(2).strip()}::date)", sql)  # noqa: E501
    sql = _RE_STRFTIME_YM.sub(
        lambda m: f"TO_CHAR(({m.group(1).strip()})::timestamp, 'YYYY-MM')", sql)  # noqa: E501
    sql = _RE_STRFTIME_Y.sub(
        lambda m: f"TO_CHAR(({m.group(1).strip()})::timestamp, 'YYYY')", sql)
    return sql


class _Cursor:
    def __init__(self, raw, conn, adapt=True):
        self._cur = raw
        self._conn = conn
        self._adapt = adapt
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        if self._adapt:
            sql = _adapt(sql)
        self._cur.execute(sql, params)
        self.rowcount = self._cur.rowcount
        if self._adapt and sql.strip().upper().startswith('INSERT'):
            try:
                tmp = self._conn.cursor()
                tmp.execute('SAVEPOINT _lastval')
                try:
                    tmp.execute('SELECT lastval()')
                    self.lastrowid = tmp.fetchone()[0]
                    tmp.execute('RELEASE SAVEPOINT _lastval')
                except Exception:
                    log.debug(
                        "lastval() unavailable after INSERT; "
                        "lastrowid left unset", exc_info=True)
                    tmp.execute('ROLLBACK TO SAVEPOINT _lastval')
                    tmp.execute('RELEASE SAVEPOINT _lastval')
                    self.lastrowid = None
                tmp.close()
            except Exception:
                log.debug(
                    "Could not determine lastrowid for INSERT", exc_info=True)
                self.lastrowid = None
        return self

    def executemany(self, sql, params_seq):
        if self._adapt:
            sql = _adapt(sql)
        self._cur.executemany(sql, params_seq)
        self.rowcount = self._cur.rowcount
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    def close(self):
        self._cur.close()


class PgConnection:
    """psycopg2 wrapper exposing a sqlite3-compatible API.

    When ``adapt`` is True (the default), SQL passed to ``execute`` is
    translated from SQLite dialect to PostgreSQL via :func:`_adapt`. Callers
    that already write native PostgreSQL should construct it with
    ``adapt=False`` (see :func:`get_db_connection`) so their SQL — e.g.
    ``%s`` placeholders and ``::type`` casts — is passed through untouched.
    """

    def __init__(self, adapt=True):
        self._adapt = adapt
        try:
            self._conn = psycopg2.connect(**DB_CONFIG)
        except Exception:
            log.error(
                "Failed to connect to database %s on %s:%s",
                DB_CONFIG['dbname'], DB_CONFIG['host'], DB_CONFIG['port'],
                exc_info=True)
            raise
        log.debug(
            "Connected to database %s on %s:%s (adapt=%s)",
            DB_CONFIG['dbname'], DB_CONFIG['host'], DB_CONFIG['port'], adapt)

    def cursor(self):
        raw = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return _Cursor(raw, self._conn, adapt=self._adapt)

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql, params_seq):
        cur = self.cursor()
        return cur.executemany(sql, params_seq)

    def executescript(self, script):
        cur = self.cursor()
        count = 0
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
                count += 1
        self._conn.commit()
        log.debug("executescript ran %d statement(s)", count)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            log.warning(
                "Rolling back transaction due to %s", exc_type.__name__,
                exc_info=(exc_type, exc_val, exc_tb))
            self._conn.rollback()
        self._conn.close()


def get_db():
    """Connection for SQLite-dialect SQL (translated to PostgreSQL)."""
    return PgConnection(adapt=True)


def get_db_connection():
    """Connection for code that already writes native PostgreSQL.

    SQL is passed through without dialect translation.
    """
    return PgConnection(adapt=False)
