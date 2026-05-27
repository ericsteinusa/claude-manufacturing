import re
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'company',
    'user': 'postgres',
    'password': '***REMOVED***',
    'port': 5432,
}

_RE_AUTOINCREMENT = re.compile(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', re.IGNORECASE)
_RE_INSERT_IGNORE = re.compile(r'INSERT\s+OR\s+IGNORE\s+INTO', re.IGNORECASE)
_RE_ROWID_STAR = re.compile(r'SELECT\s+rowid\s*,\s*\*', re.IGNORECASE)
_RE_NAMED_PARAM = re.compile(r':([A-Za-z_]\w*)')
_RE_DATETIME_NOW = re.compile(r"datetime\s*\(\s*'now'\s*\)", re.IGNORECASE)
_RE_DATE_NOW = re.compile(r"\bdate\s*\(\s*'now'\s*\)", re.IGNORECASE)
# CAST(julianday('now')-julianday(X) AS INT) -> (CURRENT_DATE - X::date)
_RE_JULIANDAY_DIFF_NOW = re.compile(
    r"CAST\s*\(\s*julianday\s*\(\s*'now'\s*\)\s*-\s*julianday\s*\(([^)]+)\)\s*AS\s+INT\s*\)",
    re.IGNORECASE)
# julianday(X) - julianday(Y) -> (X::date - Y::date)
_RE_JULIANDAY_DIFF = re.compile(
    r"julianday\s*\(([^)]+)\)\s*-\s*julianday\s*\(([^)]+)\)",
    re.IGNORECASE)
# strftime('%Y-%m', col) -> TO_CHAR(col::timestamp, 'YYYY-MM')
_RE_STRFTIME_YM = re.compile(r"strftime\s*\(\s*'%Y-%m'\s*,\s*([^,)]+)\)", re.IGNORECASE)
# strftime('%Y', col) -> TO_CHAR(col::timestamp, 'YYYY')
_RE_STRFTIME_Y = re.compile(r"strftime\s*\(\s*'%Y'\s*,\s*([^,)]+)\)", re.IGNORECASE)


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
        lambda m: f"({m.group(1).strip()}::date - {m.group(2).strip()}::date)", sql)
    sql = _RE_STRFTIME_YM.sub(
        lambda m: f"TO_CHAR(({m.group(1).strip()})::timestamp, 'YYYY-MM')", sql)
    sql = _RE_STRFTIME_Y.sub(
        lambda m: f"TO_CHAR(({m.group(1).strip()})::timestamp, 'YYYY')", sql)
    return sql


class _Cursor:
    def __init__(self, raw, conn):
        self._cur = raw
        self._conn = conn
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        sql = _adapt(sql)
        self._cur.execute(sql, params)
        self.rowcount = self._cur.rowcount
        if sql.strip().upper().startswith('INSERT'):
            try:
                tmp = self._conn.cursor()
                tmp.execute('SELECT lastval()')
                self.lastrowid = tmp.fetchone()[0]
                tmp.close()
            except Exception:
                self.lastrowid = None
        return self

    def executemany(self, sql, params_seq):
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
    def __init__(self):
        self._conn = psycopg2.connect(**DB_CONFIG)

    def cursor(self):
        raw = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return _Cursor(raw, self._conn)

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql, params_seq):
        cur = self.cursor()
        return cur.executemany(sql, params_seq)

    def executescript(self, script):
        cur = self.cursor()
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()


def get_db():
    return PgConnection()
