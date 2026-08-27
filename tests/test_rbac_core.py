"""Tests for manufacturing/rbac_core.py — pure unit tests, no Qt, no DB."""

from manufacturing.rbac_core import (
    is_privileged, owned_scope, owns_row, owned_scope_strict, owns_row_strict,
)


class _FakeRequest:
    def __init__(self, session=None):
        self.session = session or {}


# ---------------------------------------------------------------------------
# is_privileged
# ---------------------------------------------------------------------------

def test_full_access_is_privileged():
    req = _FakeRequest({'user_full_access': True})
    assert is_privileged(req) is True


def test_manager_is_privileged():
    req = _FakeRequest({'user_is_manager': True})
    assert is_privileged(req) is True


def test_regular_staff_is_not_privileged():
    req = _FakeRequest({'user_full_access': False, 'user_is_manager': False})
    assert is_privileged(req) is False


def test_no_session_flags_is_not_privileged():
    req = _FakeRequest({})
    assert is_privileged(req) is False


# ---------------------------------------------------------------------------
# owned_scope
# ---------------------------------------------------------------------------

def test_owned_scope_unrestricted_for_privileged_user():
    req = _FakeRequest({'user_full_access': True})
    sql, params = owned_scope(req, 'created_by')
    assert sql == 'TRUE'
    assert params == []


def test_owned_scope_restricted_for_regular_user():
    req = _FakeRequest({'user_email': 'rep@example.com'})
    sql, params = owned_scope(req, 'created_by')
    assert sql == 'created_by = %s'
    assert params == ['rep@example.com']


def test_owned_scope_uses_custom_session_key():
    req = _FakeRequest({'user_people_id': 42})
    sql, params = owned_scope(req, 'people_id', session_key='user_people_id')
    assert sql == 'people_id = %s'
    assert params == [42]


def test_owned_scope_manager_bypasses_restriction():
    req = _FakeRequest({'user_is_manager': True, 'user_email': 'mgr@example.com'})
    sql, params = owned_scope(req, 'created_by')
    assert sql == 'TRUE'
    assert params == []


# ---------------------------------------------------------------------------
# owns_row
# ---------------------------------------------------------------------------

def test_owns_row_true_for_matching_owner():
    req = _FakeRequest({'user_email': 'rep@example.com'})
    record = {'created_by': 'rep@example.com'}
    assert owns_row(req, record, 'created_by') is True


def test_owns_row_false_for_different_owner():
    req = _FakeRequest({'user_email': 'rep@example.com'})
    record = {'created_by': 'other@example.com'}
    assert owns_row(req, record, 'created_by') is False


def test_owns_row_true_for_privileged_regardless_of_owner():
    req = _FakeRequest({'user_full_access': True, 'user_email': 'exec@example.com'})
    record = {'created_by': 'someone-else@example.com'}
    assert owns_row(req, record, 'created_by') is True


def test_owns_row_two_blank_values_never_match():
    req = _FakeRequest({'user_email': ''})
    record = {'created_by': ''}
    assert owns_row(req, record, 'created_by') is False


def test_owns_row_missing_column_is_false():
    req = _FakeRequest({'user_email': 'rep@example.com'})
    record = {}
    assert owns_row(req, record, 'created_by') is False


# ---------------------------------------------------------------------------
# owned_scope_strict / owns_row_strict (no privilege bypass — ESS)
# ---------------------------------------------------------------------------

def test_owned_scope_strict_ignores_privilege():
    req = _FakeRequest({'user_full_access': True, 'user_people_id': 7})
    sql, params = owned_scope_strict(req, 'people_id', 'user_people_id')
    assert sql == 'people_id = %s'
    assert params == [7]


def test_owns_row_strict_true_for_own_record_even_if_privileged():
    req = _FakeRequest({'user_full_access': True, 'user_people_id': 7})
    record = {'people_id': 7}
    assert owns_row_strict(req, record, 'people_id', 'user_people_id') is True


def test_owns_row_strict_false_for_someone_elses_record_even_if_privileged():
    req = _FakeRequest({'user_full_access': True, 'user_people_id': 7})
    record = {'people_id': 99}
    assert owns_row_strict(req, record, 'people_id', 'user_people_id') is False


def test_owns_row_strict_false_when_session_key_missing():
    req = _FakeRequest({})
    record = {'people_id': None}
    assert owns_row_strict(req, record, 'people_id', 'user_people_id') is False
