"""Tests for manufacturing/accounts.py's password-policy helpers.

Qt-free, no live DB — password_needs_rotation is tested against a
MagicMock connection.
"""

import datetime as dt
from unittest.mock import MagicMock, patch

from manufacturing import accounts
from manufacturing.accounts import (
    validate_password_strength,
    password_needs_rotation,
    provision_sso_user,
    PASSWORD_MAX_AGE_DAYS,
)


# ---------------------------------------------------------------------------
# validate_password_strength
# ---------------------------------------------------------------------------

def test_valid_password_returns_none():
    assert validate_password_strength('Abcdef12') is None


def test_too_short_rejected():
    assert '8 characters' in validate_password_strength('Ab1defg')


def test_missing_uppercase_rejected():
    assert 'uppercase' in validate_password_strength('abcdefg1')


def test_missing_lowercase_rejected():
    assert 'lowercase' in validate_password_strength('ABCDEFG1')


def test_missing_digit_rejected():
    assert 'digit' in validate_password_strength('Abcdefgh')


def test_exactly_eight_chars_with_all_classes_passes():
    assert validate_password_strength('Aa1aaaaa') is None


# ---------------------------------------------------------------------------
# password_needs_rotation
# ---------------------------------------------------------------------------

def _conn(changed_at):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = (
        {'password_changed_at': changed_at} if changed_at is not None
        else {'password_changed_at': None}
    )
    return c


def test_no_row_does_not_need_rotation():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert password_needs_rotation(c, 'nobody@example.com') is False


def test_null_changed_at_does_not_need_rotation():
    c = _conn(None)
    assert password_needs_rotation(c, 'a@example.com') is False


def test_recent_password_does_not_need_rotation():
    recent = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=5)
    c = _conn(recent)
    assert password_needs_rotation(c, 'a@example.com') is False


def test_old_password_needs_rotation():
    old = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(
        days=PASSWORD_MAX_AGE_DAYS + 1)
    c = _conn(old)
    assert password_needs_rotation(c, 'a@example.com') is True


def test_exactly_at_boundary_needs_rotation():
    boundary = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(
        days=PASSWORD_MAX_AGE_DAYS)
    c = _conn(boundary)
    assert password_needs_rotation(c, 'a@example.com') is True


def test_ensure_columns_called_before_select():
    c = _conn(None)
    password_needs_rotation(c, 'a@example.com')
    first_sql = c.execute.call_args_list[0][0][0]
    assert 'ALTER TABLE passwd' in first_sql


# ---------------------------------------------------------------------------
# provision_sso_user
# ---------------------------------------------------------------------------

def test_unknown_dept_key_denied_without_touching_db():
    with patch.object(accounts, '_get_db') as mock_get_db:
        result = provision_sso_user(
            'new@example.com', {'given_name': 'Jane'}, 'not_a_real_dept')
    assert result is False
    mock_get_db.assert_not_called()


def test_dept_not_found_in_db_denied():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    with patch.object(accounts, '_get_db', return_value=conn):
        result = provision_sso_user(
            'new@example.com', {'given_name': 'Jane'}, 'sales')
    assert result is False


def test_creates_account_using_given_and_family_name_claims():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'dept_id': 7}
    with patch.object(accounts, '_get_db', return_value=conn), \
         patch.object(accounts, '_create_user', return_value=True) as mock_create:
        result = provision_sso_user(
            'jane@example.com',
            {'given_name': 'Jane', 'family_name': 'Doe'},
            'sales')
    assert result is True
    args, kwargs = mock_create.call_args
    assert args[0] == 'jane@example.com'
    assert args[2] == 'Jane'
    assert args[3] == 'Doe'
    assert kwargs['dept_id'] == 7


def test_falls_back_to_name_claim_when_no_given_family_name():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'dept_id': 7}
    with patch.object(accounts, '_get_db', return_value=conn), \
         patch.object(accounts, '_create_user', return_value=True) as mock_create:
        provision_sso_user(
            'jane@example.com', {'name': 'Jane Doe'}, 'sales')
    args, _kwargs = mock_create.call_args
    assert args[2] == 'Jane'
    assert args[3] == 'Doe'


def test_falls_back_to_email_prefix_when_no_name_claims_at_all():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'dept_id': 7}
    with patch.object(accounts, '_get_db', return_value=conn), \
         patch.object(accounts, '_create_user', return_value=True) as mock_create:
        provision_sso_user('jane@example.com', {}, 'sales')
    args, _kwargs = mock_create.call_args
    assert args[2] == 'jane'
    assert args[3] == ''


def test_generated_password_is_not_predictable():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'dept_id': 7}
    with patch.object(accounts, '_get_db', return_value=conn), \
         patch.object(accounts, '_create_user', return_value=True) as mock_create:
        provision_sso_user('jane@example.com', {'given_name': 'Jane'}, 'sales')
    password_arg = mock_create.call_args[0][1]
    assert len(password_arg) >= 32
    assert password_arg != 'jane@example.com'
