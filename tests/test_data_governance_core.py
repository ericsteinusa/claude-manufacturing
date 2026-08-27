"""Tests for manufacturing/data_governance_core.py — GDPR-style erasure,
subject-access export, and retention-policy tooling. Qt-free, mocked DB."""

import datetime
from unittest.mock import MagicMock, patch

from manufacturing.data_governance_core import (
    REDACTED_NAME,
    anonymize_person,
    list_erasure_log,
    export_person_data,
    create_retention_policy,
    list_retention_policies,
    get_retention_policy,
    update_retention_policy,
    delete_retention_policy,
    find_retention_candidates,
    apply_retention_policies,
)


def _conn_with(sql_router):
    """A MagicMock connection whose .execute() result is picked by
    inspecting the SQL text via sql_router(sql) -> rows_or_row_or_None."""
    conn = MagicMock()

    def side_effect(sql, params=None):
        m = MagicMock()
        result = sql_router(sql, params)
        if isinstance(result, list):
            m.fetchall.return_value = result
        else:
            m.fetchone.return_value = result
        return m
    conn.execute.side_effect = side_effect
    return conn


# ---------------------------------------------------------------------------
# anonymize_person
# ---------------------------------------------------------------------------

def test_anonymize_person_overwrites_pii_and_logs():
    calls = []

    def router(sql, params):
        calls.append((sql, params))
        if sql.strip().startswith('SELECT first_name'):
            return {'first_name': 'Jane', 'last_name': 'Doe'}
        return None

    conn = _conn_with(router)
    with patch('manufacturing.data_governance_core.revoke_all_tokens') as mock_revoke, \
         patch('manufacturing.data_governance_core.disable_totp') as mock_totp:
        anonymize_person(conn, 42, 'admin@example.com', reason='Subject request')

    mock_revoke.assert_called_once_with(conn, 42)
    mock_totp.assert_called_once_with(conn, 42)

    update_calls = [c for c in calls if c[0].strip().startswith('UPDATE people')]
    assert len(update_calls) == 1
    assert update_calls[0][1][0] == REDACTED_NAME  # first_name
    assert update_calls[0][1][1] == REDACTED_NAME  # last_name
    assert 'redacted-42@' in update_calls[0][1][2]  # placeholder email

    delete_calls = [c for c in calls if c[0].strip().startswith('DELETE FROM passwd')]
    assert len(delete_calls) == 1
    assert delete_calls[0][1] == (42,)

    insert_calls = [c for c in calls if 'INSERT INTO erasure_log' in c[0]]
    assert len(insert_calls) == 1
    assert insert_calls[0][1] == (42, 'Jane Doe', 'Subject request', 'admin@example.com')


def test_anonymize_person_raises_for_missing_person():
    conn = _conn_with(lambda sql, params: None)
    with patch('manufacturing.data_governance_core.revoke_all_tokens'), \
         patch('manufacturing.data_governance_core.disable_totp'):
        try:
            anonymize_person(conn, 999, 'admin@example.com')
            assert False, 'expected ValueError'
        except ValueError:
            pass


def test_list_erasure_log_returns_dicts():
    rows = [{'id': 1, 'people_id': 42, 'person_name': 'Redacted Redacted',
             'reason': '', 'performed_by': 'admin@example.com', 'performed_at': 'now'}]
    conn = _conn_with(lambda sql, params: rows)
    result = list_erasure_log(conn)
    assert result == rows


# ---------------------------------------------------------------------------
# export_person_data
# ---------------------------------------------------------------------------

def test_export_person_data_includes_person_and_referencing_tables():
    def router(sql, params):
        if sql.strip().startswith('SELECT * FROM people'):
            return {'id': 42, 'first_name': 'Jane', 'email': 'jane@example.com'}
        if 'information_schema.tables' in sql:
            return [{'table_name': 'time_clock'}, {'table_name': 'position'}]
        if sql.strip().startswith('SELECT * FROM time_clock'):
            return [{'id': 1, 'people_id': 42, 'clock_in': '2026-01-01'}]
        if sql.strip().startswith('SELECT * FROM position'):
            return []
        return []

    conn = _conn_with(router)
    result = export_person_data(conn, 42)
    assert result['people']['email'] == 'jane@example.com'
    assert result['time_clock'] == [{'id': 1, 'people_id': 42, 'clock_in': '2026-01-01'}]
    assert 'position' not in result  # empty result sets are omitted


def test_export_person_data_skips_nonexistent_tables():
    def router(sql, params):
        if sql.strip().startswith('SELECT * FROM people'):
            return {'id': 7}
        if 'information_schema.tables' in sql:
            return []  # none of the subject tables exist on this DB yet
        return []

    conn = _conn_with(router)
    result = export_person_data(conn, 7)
    assert result == {'people': {'id': 7}}


def test_export_person_data_raises_for_missing_person():
    conn = _conn_with(lambda sql, params: None)
    try:
        export_person_data(conn, 999)
        assert False, 'expected ValueError'
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Retention policy CRUD
# ---------------------------------------------------------------------------

def test_create_retention_policy_returns_id():
    conn = _conn_with(lambda sql, params: {'id': 5})
    assert create_retention_policy(conn, 'Terminated 7yr', 84) == 5


def test_list_retention_policies_active_only_filters_sql():
    conn = _conn_with(lambda sql, params: [])
    list_retention_policies(conn, active_only=True)
    sql = conn.execute.call_args[0][0]
    assert 'is_active = TRUE' in sql


def test_get_retention_policy_returns_none_when_missing():
    conn = _conn_with(lambda sql, params: None)
    assert get_retention_policy(conn, 999) is None


def test_update_retention_policy_uses_coalesce():
    conn = _conn_with(lambda sql, params: None)
    update_retention_policy(conn, 5, name='New name')
    sql = conn.execute.call_args[0][0]
    assert 'COALESCE' in sql


def test_delete_retention_policy():
    conn = _conn_with(lambda sql, params: None)
    delete_retention_policy(conn, 5)
    sql, params = conn.execute.call_args[0]
    assert 'DELETE FROM retention_policy' in sql
    assert params == (5,)


# ---------------------------------------------------------------------------
# find_retention_candidates / apply_retention_policies
# ---------------------------------------------------------------------------

def test_find_retention_candidates_matches_old_terminations():
    old_date = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
    recent_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    rows = [
        {'id': 1, 'first_name': 'Old', 'last_name': 'Timer', 'termination_date': old_date},
        {'id': 2, 'first_name': 'Recent', 'last_name': 'Leaver', 'termination_date': recent_date},
        {'id': 3, 'first_name': 'No', 'last_name': 'Date', 'termination_date': ''},
    ]
    conn = _conn_with(lambda sql, params: rows)
    policy = {'months_after_termination': 6}
    candidates = find_retention_candidates(conn, policy)
    assert [c['id'] for c in candidates] == [1]


def test_find_retention_candidates_excludes_already_redacted():
    conn = _conn_with(lambda sql, params: [])
    find_retention_candidates(conn, {'months_after_termination': 6})
    sql, params = conn.execute.call_args[0]
    assert params == (REDACTED_NAME,)


def test_apply_retention_policies_anonymizes_and_commits_per_person():
    old_date = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()

    def router(sql, params):
        if 'FROM retention_policy' in sql and 'WHERE' in sql:
            return [{'id': 1, 'name': 'Old leavers', 'months_after_termination': 6,
                     'is_active': True, 'created_at': 'now'}]
        if sql.strip().startswith('SELECT id, first_name, last_name, termination_date'):
            return [{'id': 10, 'first_name': 'Old', 'last_name': 'Timer',
                     'termination_date': old_date}]
        if sql.strip().startswith('SELECT first_name'):
            return {'first_name': 'Old', 'last_name': 'Timer'}
        return None

    conn = _conn_with(router)
    with patch('manufacturing.data_governance_core.revoke_all_tokens'), \
         patch('manufacturing.data_governance_core.disable_totp'):
        anonymized = apply_retention_policies(conn)

    assert anonymized == [10]
    conn.commit.assert_called_once()
