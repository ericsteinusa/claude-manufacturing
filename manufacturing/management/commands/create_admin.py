"""Django management command — bootstrap a brand-new database's first
full-access admin account.

There is no other way to get a working login on a fresh customer database:
/register/ creates a `people`/`passwd` row but assigns no role, and the
User Roles admin page that assigns roles itself requires an existing role
to access. This command creates the account and grants it a role
(President, by default) in one step, so a new customer instance has
someone who can actually log in and use the app.

Usage:
    python manage.py create_admin --email admin@customer.com \\
        --first-name Jane --last-name Doe

    # Provide your own password instead of generating one:
    python manage.py create_admin --email admin@customer.com \\
        --first-name Jane --last-name Doe --password 'Correct-Horse-1'

    # Grant a role other than the President default:
    python manage.py create_admin --email vp@customer.com \\
        --first-name Sam --last-name Lee --role 'Vice President'
"""

import secrets

from django.core.management.base import BaseCommand, CommandError

from manufacturing.accounts import (
    _create_user, _email_exists, _get_all_roles, _get_db,
    _set_user_role, validate_password_strength,
)

DEFAULT_ROLE = 'President'


class Command(BaseCommand):
    help = "Create a full-access admin account for a brand-new customer database."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--first-name', required=True, dest='first_name')
        parser.add_argument('--last-name', required=True, dest='last_name')
        parser.add_argument(
            '--password', default='',
            help='If omitted, a random password is generated and printed once.',
        )
        parser.add_argument(
            '--role', default=DEFAULT_ROLE,
            help=f'Role to grant (default: {DEFAULT_ROLE}).',
        )

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        first_name = options['first_name'].strip()
        last_name = options['last_name'].strip()
        role_name = options['role'].strip()
        password = options['password'] or secrets.token_urlsafe(12)
        password_was_generated = not options['password']

        if not email or '@' not in email:
            raise CommandError('A valid --email is required.')
        if _email_exists(email):
            raise CommandError(f'{email} already has an account.')

        error = validate_password_strength(password)
        if error:
            raise CommandError(f'Password policy: {error}')

        roles = {r['role_name']: r['id'] for r in _get_all_roles()}
        if role_name not in roles:
            raise CommandError(
                f'Role {role_name!r} not found. Available roles: '
                f'{", ".join(sorted(roles)) or "(none seeded yet)"}'
            )

        if not _create_user(email, password, first_name, last_name):
            raise CommandError(
                'Account creation failed — check the logs (this usually '
                'means a race with another process creating the same email).'
            )

        conn = _get_db()
        try:
            person = conn.execute(
                "SELECT id FROM people WHERE email = %s", (email,),
            ).fetchone()
        finally:
            conn.close()

        _set_user_role(person['id'], roles[role_name])

        self.stdout.write(self.style.SUCCESS(
            f"Created {role_name!r} account for {email} "
            f"(people_id={person['id']})."
        ))
        if password_was_generated:
            self.stdout.write(
                f"Generated password (shown once, not logged): {password}\n"
                "Hand this to the customer through a secure channel and have "
                "them change it on first login."
            )
