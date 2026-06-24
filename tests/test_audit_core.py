"""Tests for audit_core — Qt-free, no live database.

Uses a fake connection to verify that install_triggers issues the right SQL
and that the query helpers (get_recent, get_history) build correct queries.
"""

from unittest.mock import patch

from manufacturing.audit_core import (
    AUDITED_TABLES,
    install_triggers,
    set_audit_user,
    get_recent,
    get_history,
)


class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows=None):
        self.calls: list[tuple] = []
        self._rows = rows or []
        self.committed = False
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((sql.strip(), params))
        return _FakeCursor(self._rows)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# AUDITED_TABLES
# ---------------------------------------------------------------------------

def test_audited_tables_nonempty():
    assert len(AUDITED_TABLES) > 0


def test_audited_tables_includes_core_entities():
    core = {'purchase_order', 'work_order', 'sales_order',
            'people', 'user_roles', 'product'}
    assert core.issubset(set(AUDITED_TABLES))


# ---------------------------------------------------------------------------
# install_triggers
# ---------------------------------------------------------------------------

def test_install_triggers_creates_function():
    conn = _FakeConn()
    install_triggers(conn)
    sqls = [sql for sql, _ in conn.calls]
    assert any('CREATE OR REPLACE FUNCTION _audit_trigger' in s for s in sqls)


def test_install_triggers_drops_and_creates_trigger_per_table():
    conn = _FakeConn()
    install_triggers(conn)
    sqls = [sql for sql, _ in conn.calls]
    for table in AUDITED_TABLES:
        assert any(f'DROP TRIGGER IF EXISTS _audit ON {table}' in s
                   for s in sqls), f"missing DROP TRIGGER for {table}"
        assert any('CREATE TRIGGER _audit' in s and table in s
                   for s in sqls), f"missing CREATE TRIGGER for {table}"


def test_install_triggers_commits():
    conn = _FakeConn()
    install_triggers(conn)
    assert conn.committed


def test_install_triggers_covers_insert_update_delete():
    conn = _FakeConn()
    install_triggers(conn)
    sqls = ' '.join(sql for sql, _ in conn.calls)
    assert 'INSERT OR UPDATE OR DELETE' in sqls


# ---------------------------------------------------------------------------
# set_audit_user
# ---------------------------------------------------------------------------

def test_set_audit_user_calls_set_config():
    conn = _FakeConn()
    set_audit_user(conn, 'alice@example.com')
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert 'set_config' in sql
    assert params == ('alice@example.com',)


def test_set_audit_user_empty_string_on_none():
    conn = _FakeConn()
    set_audit_user(conn, '')
    _, params = conn.calls[0]
    assert params == ('',)


# ---------------------------------------------------------------------------
# get_recent
# ---------------------------------------------------------------------------

def test_get_recent_no_filters():
    rows = [{'id': 1, 'table_name': 'purchase_order', 'record_id': 5,
             'action': 'INSERT', 'changed_by': 'x@y.com',
             'changed_at': '2026-01-01'}]

    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn(rows)
        mock_conn.return_value = conn
        result = get_recent(limit=10)

    sql, params = conn.calls[0]
    assert 'FROM audit_log' in sql
    assert 'ORDER BY changed_at DESC' in sql
    assert params[-1] == 10
    assert result == rows


def test_get_recent_table_filter():
    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn([])
        mock_conn.return_value = conn
        get_recent(table_name='work_order')

    sql, params = conn.calls[0]
    assert 'table_name = %s' in sql
    assert 'work_order' in params


def test_get_recent_user_filter():
    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn([])
        mock_conn.return_value = conn
        get_recent(changed_by='alice')

    sql, params = conn.calls[0]
    assert 'changed_by ILIKE %s' in sql
    assert any('alice' in str(p) for p in params)


def test_get_recent_closes_connection():
    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn([])
        mock_conn.return_value = conn
        get_recent()
    assert conn.closed


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

def test_get_history_queries_by_table_and_id():
    rows = [{'id': 1, 'action': 'UPDATE', 'changed_by': 'x@y.com',
             'changed_at': '2026-01-01', 'old_values': '{}',
             'new_values': '{}'}]

    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn(rows)
        mock_conn.return_value = conn
        result = get_history('purchase_order', 42)

    sql, params = conn.calls[0]
    assert 'WHERE table_name = %s AND record_id = %s' in sql
    assert params == ('purchase_order', 42)
    assert result == rows


def test_get_history_ordered_newest_first():
    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn([])
        mock_conn.return_value = conn
        get_history('work_order', 1)

    sql, _ = conn.calls[0]
    assert 'ORDER BY changed_at DESC' in sql


def test_get_history_closes_connection():
    with patch('manufacturing.audit_core.get_db_connection') as mock_conn:
        conn = _FakeConn([])
        mock_conn.return_value = conn
        get_history('product', 1)
    assert conn.closed
