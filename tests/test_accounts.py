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
    totp_enrolled,
    create_password_reset_token,
    verify_password_reset_token,
    consume_password_reset_token,
    purge_expired_password_reset_tokens,
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


# ---------------------------------------------------------------------------
# totp_enrolled
#
# Used by views/_sso.py and views/_saml.py to gate SSO/SAML login through
# the same MFA challenge the password-login path uses -- see PR fixing the
# SSO/SAML TOTP bypass (both protocols used to call apply_sso_session()
# directly with no 2FA check at all).
# ---------------------------------------------------------------------------

def _ctx_conn(fetchone_return):
    """A MagicMock usable as a `with get_db_connection() as conn:` context
    manager, whose conn.execute(...).fetchone() returns *fetchone_return*."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = fetchone_return
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    return ctx


def test_totp_enrolled_true_when_secret_exists():
    ctx = _ctx_conn({'secret_b32': 'ABCDEFGH'})
    with patch.object(accounts, 'get_db_connection', return_value=ctx):
        assert totp_enrolled(42) is True


def test_totp_enrolled_false_when_no_secret():
    ctx = _ctx_conn(None)
    with patch.object(accounts, 'get_db_connection', return_value=ctx):
        assert totp_enrolled(42) is False


# ---------------------------------------------------------------------------
# Password reset tokens
#
# forgot_password/forgot_password_reset (views/__init__.py) used to treat
# "the visitor typed a registered email address" as the entire proof of
# ownership -- no emailed link, no token, no expiry. These back the real
# single-use, time-limited token that closed that account-takeover gap.
# ---------------------------------------------------------------------------

def test_create_password_reset_token_inserts_and_returns_token():
    conn = MagicMock()
    token = create_password_reset_token(conn, 42)
    assert isinstance(token, str)
    assert len(token) >= 32
    conn.execute.assert_called_once()
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO password_reset_token' in sql
    assert params[0] == token
    assert params[1] == 42


def test_create_password_reset_token_is_not_predictable():
    conn = MagicMock()
    t1 = create_password_reset_token(conn, 42)
    t2 = create_password_reset_token(conn, 42)
    assert t1 != t2


def test_verify_password_reset_token_returns_dict_for_valid_token():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {
        'people_id': 42, 'email': 'jane@example.com',
    }
    result = verify_password_reset_token(conn, 'sometoken')
    assert result == {'people_id': 42, 'email': 'jane@example.com'}


def test_verify_password_reset_token_returns_none_for_unknown_token():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert verify_password_reset_token(conn, 'badtoken') is None


def test_verify_password_reset_token_rejects_empty_token_without_query():
    conn = MagicMock()
    assert verify_password_reset_token(conn, '') is None
    conn.execute.assert_not_called()


def test_verify_password_reset_token_query_excludes_used_and_expired():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    verify_password_reset_token(conn, 'sometoken')
    sql = conn.execute.call_args[0][0]
    assert 'used = FALSE' in sql
    assert 'expires_at > NOW()' in sql


def test_consume_password_reset_token_marks_used():
    conn = MagicMock()
    consume_password_reset_token(conn, 'sometoken')
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE password_reset_token SET used = TRUE' in sql
    assert params == ('sometoken',)


def test_purge_expired_password_reset_tokens_returns_row_count():
    conn = MagicMock()
    conn.execute.return_value.rowcount = 3
    assert purge_expired_password_reset_tokens(conn) == 3


def test_purge_expired_password_reset_tokens_deletes_by_expiry():
    conn = MagicMock()
    conn.execute.return_value.rowcount = 0
    purge_expired_password_reset_tokens(conn, keep_minutes=120)
    sql, params = conn.execute.call_args[0]
    assert 'DELETE FROM password_reset_token' in sql
    assert 'expires_at' in sql
    assert params == (120,)
