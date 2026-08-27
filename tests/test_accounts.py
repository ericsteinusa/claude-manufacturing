"""Tests for manufacturing/accounts.py's password-policy helpers.

Qt-free, no live DB — password_needs_rotation is tested against a
MagicMock connection.
"""

import datetime as dt
from unittest.mock import MagicMock

from manufacturing.accounts import (
    validate_password_strength,
    password_needs_rotation,
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
