"""Tests for manufacturing.auth_decorators.

No Django URL conf or settings needed — redirect() is patched so tests only
verify which named URL (or path) is passed to it, not the resolved URL.
"""

from unittest.mock import patch, MagicMock

from manufacturing.auth_decorators import dept_required, login_required, role_required


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REDIRECT = MagicMock(name='redirect_response')


def _session(**kw):
    """Build a dict-based session with the keys login writes."""
    defaults = dict(user_email='', user_full_access=False,
                    user_dept_key='', user_role='')
    defaults.update(kw)
    return defaults


def _req(**session_kw):
    r = type('Req', (), {'session': _session(**session_kw)})()
    return r


def _sentinel(request, *a, **kw):
    return 'ok'


def _patched():
    """Context manager that patches redirect and returns the mock."""
    return patch('manufacturing.auth_decorators.redirect',
                 return_value=_REDIRECT)


# ---------------------------------------------------------------------------
# login_required
# ---------------------------------------------------------------------------

class TestLoginRequired:
    def test_allows_logged_in_user(self):
        view = login_required(_sentinel)
        assert view(_req(user_email='a@b.com')) == 'ok'

    def test_redirects_anonymous_to_home(self):
        view = login_required(_sentinel)
        with _patched() as mock_redir:
            view(_req())
            mock_redir.assert_called_once_with('home')

    def test_preserves_args_and_kwargs(self):
        def capture(request, pk, flag=False):
            return (pk, flag)
        view = login_required(capture)
        assert view(_req(user_email='a@b.com'), 42, flag=True) == (42, True)


# ---------------------------------------------------------------------------
# dept_required — login gate
# ---------------------------------------------------------------------------

class TestDeptRequiredLogin:
    def test_redirects_anonymous_to_home(self):
        view = dept_required('purchasing')(_sentinel)
        with _patched() as mock_redir:
            view(_req())
            mock_redir.assert_called_once_with('home')

    def test_allows_logged_in_user_in_dept(self):
        view = dept_required('purchasing')(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='purchasing')) == 'ok'


# ---------------------------------------------------------------------------
# dept_required — department gate
# ---------------------------------------------------------------------------

class TestDeptRequiredDeptGate:
    def test_blocks_wrong_dept(self):
        view = dept_required('purchasing')(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_dept_key='sales'))
            mock_redir.assert_called_once_with('dashboard')

    def test_full_access_bypasses_dept_check(self):
        view = dept_required('purchasing')(_sentinel)
        assert view(_req(user_email='a@b.com', user_full_access=True,
                         user_dept_key='sales')) == 'ok'

    def test_allows_any_key_in_multi_dept_set(self):
        view = dept_required({'maintenance', 'production'})(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='maintenance')) == 'ok'
        assert view(_req(user_email='a@b.com', user_dept_key='production')) == 'ok'

    def test_blocks_dept_not_in_set(self):
        view = dept_required({'maintenance', 'production'})(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_dept_key='sales'))
            mock_redir.assert_called_once_with('dashboard')

    def test_single_string_treated_as_one_element_set(self):
        view = dept_required('purchasing')(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='purchasing')) == 'ok'


# ---------------------------------------------------------------------------
# dept_required — write_redirect gate
# ---------------------------------------------------------------------------

class TestDeptRequiredWriteRedirect:
    def test_read_only_role_blocked_on_write_view(self):
        view = dept_required('purchasing', write_redirect='po_list')(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_dept_key='purchasing',
                      user_role='Auditor'))
            mock_redir.assert_called_once_with('po_list')

    def test_normal_role_passes_write_view(self):
        view = dept_required('purchasing', write_redirect='po_list')(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='purchasing',
                         user_role='Employee')) == 'ok'

    def test_no_write_redirect_allows_read_only_role(self):
        view = dept_required('purchasing')(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='purchasing',
                         user_role='Auditor')) == 'ok'

    def test_full_access_with_read_only_role_still_blocked_on_write(self):
        """Full-access bypasses dept check but not the write-role check."""
        view = dept_required('purchasing', write_redirect='po_list')(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_full_access=True,
                      user_role='Auditor'))
            mock_redir.assert_called_once_with('po_list')

    def test_full_access_normal_role_allowed_on_write(self):
        view = dept_required('purchasing', write_redirect='po_list')(_sentinel)
        assert view(_req(user_email='a@b.com', user_full_access=True,
                         user_role='President')) == 'ok'


# ---------------------------------------------------------------------------
# dept_required — view args passthrough
# ---------------------------------------------------------------------------

class TestDeptRequiredPassthrough:
    def test_args_and_kwargs_forwarded(self):
        def capture(request, pk, flag=False):
            return (pk, flag)
        view = dept_required('purchasing')(capture)
        assert view(_req(user_email='a@b.com', user_dept_key='purchasing'),
                    7, flag=True) == (7, True)

    def test_functools_wraps_preserves_name(self):
        def my_view(request):
            return 'ok'
        wrapped = dept_required('purchasing')(my_view)
        assert wrapped.__name__ == 'my_view'

    def test_login_required_wraps_preserves_name(self):
        def my_view(request):
            return 'ok'
        wrapped = login_required(my_view)
        assert wrapped.__name__ == 'my_view'


# ---------------------------------------------------------------------------
# dept_required — role_keys parameter
# ---------------------------------------------------------------------------

class TestDeptRequiredRoleKeys:
    def test_role_key_grants_access_without_dept(self):
        view = dept_required('personnel', role_keys={'HR / Personnel'})(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='sales',
                         user_role='HR / Personnel')) == 'ok'

    def test_dept_still_grants_access_without_role(self):
        view = dept_required('personnel', role_keys={'HR / Personnel'})(_sentinel)
        assert view(_req(user_email='a@b.com', user_dept_key='personnel',
                         user_role='Employee')) == 'ok'

    def test_neither_dept_nor_role_is_denied(self):
        view = dept_required('personnel', role_keys={'HR / Personnel'})(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_dept_key='sales', user_role='Employee'))
            mock_redir.assert_called_once_with('dashboard')

    def test_full_access_bypasses_both_checks(self):
        view = dept_required('personnel', role_keys={'HR / Personnel'})(_sentinel)
        assert view(_req(user_email='a@b.com', user_full_access=True,
                         user_dept_key='sales', user_role='Employee')) == 'ok'


# ---------------------------------------------------------------------------
# dept_required — deny_redirect parameter
# ---------------------------------------------------------------------------

class TestDeptRequiredDenyRedirect:
    def test_custom_deny_redirect_used_on_dept_fail(self):
        view = dept_required('personnel', deny_redirect='time_clock_status')(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_dept_key='sales'))
            mock_redir.assert_called_once_with('time_clock_status')

    def test_default_deny_redirect_is_dashboard(self):
        view = dept_required('personnel')(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_dept_key='sales'))
            mock_redir.assert_called_once_with('dashboard')


# ---------------------------------------------------------------------------
# role_required
# ---------------------------------------------------------------------------

class TestRoleRequired:
    def test_allows_matching_role(self):
        view = role_required({'President', 'Vice President'})(_sentinel)
        assert view(_req(user_email='a@b.com', user_role='President')) == 'ok'

    def test_blocks_non_matching_role(self):
        view = role_required({'President', 'Vice President'})(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_role='Employee'))
            mock_redir.assert_called_once_with('dashboard')

    def test_redirects_anonymous_to_home(self):
        view = role_required({'President'})(_sentinel)
        with _patched() as mock_redir:
            view(_req())
            mock_redir.assert_called_once_with('home')

    def test_single_string_role(self):
        view = role_required('Auditor')(_sentinel)
        assert view(_req(user_email='a@b.com', user_role='Auditor')) == 'ok'

    def test_custom_deny_redirect(self):
        view = role_required({'President'}, deny_redirect='po_list')(_sentinel)
        with _patched() as mock_redir:
            view(_req(user_email='a@b.com', user_role='Employee'))
            mock_redir.assert_called_once_with('po_list')

    def test_functools_wraps_preserves_name(self):
        def my_view(request):
            return 'ok'
        wrapped = role_required('President')(my_view)
        assert wrapped.__name__ == 'my_view'
