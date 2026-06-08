"""Tests for db_pg._adapt — the SQLite-dialect to PostgreSQL translation.

_adapt is a pure function (no DB connection), which makes it the most
valuable unit-test target in the data layer.
"""

import pytest

from manufacturing.db_pg import _adapt


@pytest.mark.parametrize("sql, expected", [
    # positional and named placeholders
    ("SELECT * FROM t WHERE id = ?", "SELECT * FROM t WHERE id = %s"),
    ("INSERT INTO t(a) VALUES(:a)", "INSERT INTO t(a) VALUES(%(a)s)"),
    # rowid -> id
    ("SELECT rowid, * FROM t", "SELECT id, * FROM t"),
    # AUTOINCREMENT -> SERIAL
    ("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, n TEXT)",
     "CREATE TABLE t (id SERIAL PRIMARY KEY, n TEXT)"),
    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
    ("INSERT OR IGNORE INTO t(a) VALUES(?)",
     "INSERT INTO t(a) VALUES(%s) ON CONFLICT DO NOTHING"),
    # date/time helpers
    ("SELECT datetime('now')", "SELECT CURRENT_TIMESTAMP"),
    ("SELECT date('now')", "SELECT CURRENT_DATE::text"),
    # julianday differences
    ("SELECT CAST(julianday('now')-julianday(due) AS INT) FROM t",
     "SELECT (CURRENT_DATE - (due)::date) FROM t"),
    ("SELECT julianday(a)-julianday(b) FROM t",
     "SELECT (a::date - b::date) FROM t"),
    # strftime month / year
    ("SELECT strftime('%Y-%m', d) FROM t",
     "SELECT TO_CHAR((d)::timestamp, 'YYYY-MM') FROM t"),
    ("SELECT strftime('%Y', d) FROM t",
     "SELECT TO_CHAR((d)::timestamp, 'YYYY') FROM t"),
])
def test_adapt_translations(sql, expected):
    assert _adapt(sql) == expected


def test_adapt_is_case_insensitive_for_autoincrement():
    out = _adapt("create table t (id integer primary key autoincrement)")
    assert "SERIAL PRIMARY KEY" in out


def test_adapt_translates_multiple_placeholders():
    assert _adapt("VALUES (?, ?, ?)") == "VALUES (%s, %s, %s)"


def test_adapt_leaves_plain_postgres_sql_untouched():
    sql = "SELECT id, name FROM people WHERE email = %s"
    assert _adapt(sql) == sql
