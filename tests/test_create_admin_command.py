"""Tests for the create_admin management command — bootstraps a brand-new
database's first full-access account (see the command's own docstring for
why this exists: /register/ + the User Roles page can't do this alone).

No live DB: manufacturing.accounts's DB-touching helpers are patched where
they're imported into the command module's own namespace (the command does
``from manufacturing.accounts import X``, so patches target
``manufacturing.management.commands.create_admin.X``, not
``manufacturing.accounts.X``).
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

CMD = 'manufacturing.management.commands.create_admin'


def _run(**kwargs):
    out = io.StringIO()
    call_command('create_admin', stdout=out, **kwargs)
    return out.getvalue()


@patch(f'{CMD}._set_user_role')
@patch(f'{CMD}._get_db')
@patch(f'{CMD}._create_user')
@patch(f'{CMD}._get_all_roles')
@patch(f'{CMD}._email_exists')
def test_creates_account_and_grants_default_role(
    mock_exists, mock_roles, mock_create, mock_get_db, mock_set_role,
):
    mock_exists.return_value = False
    mock_roles.return_value = [
        {'id': 1, 'role_name': 'President'}, {'id': 2, 'role_name': 'Auditor'},
    ]
    mock_create.return_value = True
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 42}
    mock_get_db.return_value = conn

    output = _run(
        email='Admin@Customer.com', first_name='Jane', last_name='Doe',
        password='Correct-Horse-1',
    )

    mock_create.assert_called_once_with(
        'admin@customer.com', 'Correct-Horse-1', 'Jane', 'Doe')
    mock_set_role.assert_called_once_with(42, 1)
    assert "Created 'President' account for admin@customer.com" in output
    assert 'people_id=42' in output
    assert 'Generated password' not in output


@patch(f'{CMD}._set_user_role')
@patch(f'{CMD}._get_db')
@patch(f'{CMD}._create_user')
@patch(f'{CMD}._get_all_roles')
@patch(f'{CMD}._email_exists')
def test_generates_and_prints_password_when_omitted(
    mock_exists, mock_roles, mock_create, mock_get_db, mock_set_role,
):
    mock_exists.return_value = False
    mock_roles.return_value = [{'id': 1, 'role_name': 'President'}]
    mock_create.return_value = True
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 7}
    mock_get_db.return_value = conn

    output = _run(email='new@customer.com', first_name='Sam', last_name='Lee')

    assert 'Generated password (shown once, not logged):' in output
    # the password actually used should match the strength policy
    used_password = mock_create.call_args[0][1]
    assert len(used_password) >= 8


@patch(f'{CMD}._email_exists')
def test_rejects_invalid_email(mock_exists):
    with pytest.raises(CommandError, match='valid --email'):
        _run(email='not-an-email', first_name='A', last_name='B')
    mock_exists.assert_not_called()


@patch(f'{CMD}._email_exists')
def test_rejects_existing_email(mock_exists):
    mock_exists.return_value = True
    with pytest.raises(CommandError, match='already has an account'):
        _run(email='dup@customer.com', first_name='A', last_name='B')


@patch(f'{CMD}._email_exists')
def test_rejects_weak_password(mock_exists):
    mock_exists.return_value = False
    with pytest.raises(CommandError, match='Password policy'):
        _run(email='weak@customer.com', first_name='A', last_name='B',
             password='abc')


@patch(f'{CMD}._get_all_roles')
@patch(f'{CMD}._email_exists')
def test_rejects_unknown_role(mock_exists, mock_roles):
    mock_exists.return_value = False
    mock_roles.return_value = [{'id': 1, 'role_name': 'President'}]
    with pytest.raises(CommandError, match="Role 'CEO' not found"):
        _run(email='x@customer.com', first_name='A', last_name='B',
             password='Correct-Horse-1', role='CEO')


@patch(f'{CMD}._create_user')
@patch(f'{CMD}._get_all_roles')
@patch(f'{CMD}._email_exists')
def test_create_user_failure_raises(mock_exists, mock_roles, mock_create):
    mock_exists.return_value = False
    mock_roles.return_value = [{'id': 1, 'role_name': 'President'}]
    mock_create.return_value = False
    with pytest.raises(CommandError, match='Account creation failed'):
        _run(email='x@customer.com', first_name='A', last_name='B',
             password='Correct-Horse-1')


@patch(f'{CMD}._set_user_role')
@patch(f'{CMD}._get_db')
@patch(f'{CMD}._create_user')
@patch(f'{CMD}._get_all_roles')
@patch(f'{CMD}._email_exists')
def test_can_grant_a_non_default_role(
    mock_exists, mock_roles, mock_create, mock_get_db, mock_set_role,
):
    mock_exists.return_value = False
    mock_roles.return_value = [
        {'id': 1, 'role_name': 'President'},
        {'id': 5, 'role_name': 'Vice President'},
    ]
    mock_create.return_value = True
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'id': 9}
    mock_get_db.return_value = conn

    output = _run(email='vp@customer.com', first_name='Sam', last_name='Lee',
                  password='Correct-Horse-1', role='Vice President')

    mock_set_role.assert_called_once_with(9, 5)
    assert "Created 'Vice President' account for vp@customer.com" in output
