"""
Tests for period_locking_core.py.

Uses a fake connection that stubs out .execute().fetchone() without
touching the real database.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock

from manufacturing.period_locking_core import (
    is_period_locked,
    period_label,
    close_period,
    reopen_period,
    recent_months,
    PERIOD_ADMIN_ROLES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(fetchone_result=None):
    """Return a minimal fake connection whose execute().fetchone() returns result."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = fetchone_result
    return conn


# ---------------------------------------------------------------------------
# period_label
# ---------------------------------------------------------------------------

def test_period_label_june():
    assert period_label(2026, 6) == 'June 2026'


def test_period_label_january():
    assert period_label(2025, 1) == 'January 2025'


def test_period_label_december():
    assert period_label(2024, 12) == 'December 2024'


# ---------------------------------------------------------------------------
# is_period_locked
# ---------------------------------------------------------------------------

def test_locked_when_row_returned():
    conn = _conn(fetchone_result=('1',))
    assert is_period_locked(conn, '2026-06-15') is True


def test_open_when_no_row():
    conn = _conn(fetchone_result=None)
    assert is_period_locked(conn, '2026-06-15') is False


def test_empty_date_never_locked():
    conn = _conn()
    assert is_period_locked(conn, '') is False
    conn.execute.assert_not_called()


def test_none_date_never_locked():
    conn = _conn()
    assert is_period_locked(conn, None) is False
    conn.execute.assert_not_called()


def test_invalid_date_never_locked():
    conn = _conn()
    assert is_period_locked(conn, 'not-a-date') is False
    conn.execute.assert_not_called()


def test_checks_correct_year_month():
    conn = _conn(fetchone_result=None)
    is_period_locked(conn, '2025-03-31')
    conn.execute.assert_called_once()
    args = conn.execute.call_args[0]
    assert args[1] == (2025, 3)


def test_truncates_to_date_portion():
    """Timestamps with time components should still parse."""
    conn = _conn(fetchone_result=None)
    is_period_locked(conn, '2026-01-15T12:30:00')
    args = conn.execute.call_args[0]
    assert args[1] == (2026, 1)


# ---------------------------------------------------------------------------
# close_period
# ---------------------------------------------------------------------------

def test_close_period_inserts_when_open():
    conn = _conn(fetchone_result=None)
    close_period(conn, 2026, 5, 'admin@example.com', notes='Q2 close')
    assert conn.execute.call_count == 2  # SELECT then INSERT
    insert_call = conn.execute.call_args_list[1]
    sql, params = insert_call[0]
    assert 'INSERT INTO closed_periods' in sql
    assert params[:3] == (2026, 5, 'admin@example.com')


def test_close_period_raises_if_already_closed():
    conn = _conn(fetchone_result=('1',))
    with pytest.raises(ValueError, match='already closed'):
        close_period(conn, 2026, 5, 'admin@example.com')


def test_close_period_default_empty_notes():
    conn = _conn(fetchone_result=None)
    close_period(conn, 2026, 3, 'user@example.com')
    insert_call = conn.execute.call_args_list[1]
    _, params = insert_call[0]
    assert params[3] == ''


# ---------------------------------------------------------------------------
# reopen_period
# ---------------------------------------------------------------------------

def test_reopen_period_deletes():
    conn = _conn()
    reopen_period(conn, 42, 'admin@example.com')
    conn.execute.assert_called_once()
    sql, params = conn.execute.call_args[0]
    assert 'DELETE FROM closed_periods' in sql
    assert params == (42,)


# ---------------------------------------------------------------------------
# recent_months
# ---------------------------------------------------------------------------

def test_recent_months_length():
    months = recent_months(13)
    assert len(months) == 13


def test_recent_months_first_is_current():
    today = date.today()
    months = recent_months(3)
    assert months[0] == (today.year, today.month)


def test_recent_months_descending():
    months = recent_months(4)
    for i in range(len(months) - 1):
        y1, m1 = months[i]
        y2, m2 = months[i + 1]
        assert (y1 * 12 + m1) > (y2 * 12 + m2)


def test_recent_months_wraps_year():
    months = recent_months(14)
    years = {y for y, _ in months}
    assert len(years) >= 2


# ---------------------------------------------------------------------------
# PERIOD_ADMIN_ROLES
# ---------------------------------------------------------------------------

def test_president_is_admin():
    assert 'President' in PERIOD_ADMIN_ROLES


def test_vp_is_admin():
    assert 'Vice President' in PERIOD_ADMIN_ROLES


def test_auditor_not_admin():
    assert 'Auditor' not in PERIOD_ADMIN_ROLES
