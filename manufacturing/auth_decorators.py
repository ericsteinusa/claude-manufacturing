"""Django view decorators for session-based auth enforcement."""

from functools import wraps

from django.shortcuts import redirect

from .accounts import READ_ONLY_ROLES


def login_required(view_func):
    """Redirect to 'home' if the request has no active session."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_email'):
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


def dept_required(dept_keys, *, role_keys=None, write_redirect=None,
                  deny_redirect='dashboard'):
    """Gate a view to logged-in users in the given department(s) or role(s).

    Full-access roles (President, Vice President) always bypass the check.

    Parameters
    ----------
    dept_keys:
        A dept key string or iterable of dept key strings that are allowed
        (matched against ``request.session['user_dept_key']``).
    role_keys:
        Optional role name(s) that also grant access regardless of dept,
        in addition to full-access roles.
    write_redirect:
        Named URL to redirect READ_ONLY_ROLES when a mutating view is hit.
        Omit for read-only views.
    deny_redirect:
        Named URL to redirect when the dept/role check fails. Defaults to
        ``'dashboard'``.
    """
    if isinstance(dept_keys, str):
        dept_keys = frozenset({dept_keys})
    else:
        dept_keys = frozenset(dept_keys)
    if role_keys is not None:
        if isinstance(role_keys, str):
            role_keys = frozenset({role_keys})
        else:
            role_keys = frozenset(role_keys)

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.session.get('user_email'):
                return redirect('home')
            if not request.session.get('user_full_access'):
                dept_ok = request.session.get('user_dept_key') in dept_keys
                role_ok = role_keys and request.session.get('user_role') in role_keys
                if not dept_ok and not role_ok:
                    return redirect(deny_redirect)
            if write_redirect and request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect(write_redirect)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def role_required(role_keys, *, deny_redirect='dashboard'):
    """Gate a view to logged-in users with one of the given roles.

    Parameters
    ----------
    role_keys:
        A role name string or iterable of role name strings
        (matched against ``request.session['user_role']``).
    deny_redirect:
        Named URL to redirect when the role check fails. Defaults to
        ``'dashboard'``.
    """
    if isinstance(role_keys, str):
        role_keys = frozenset({role_keys})
    else:
        role_keys = frozenset(role_keys)

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.session.get('user_email'):
                return redirect('home')
            if request.session.get('user_role') not in role_keys:
                return redirect(deny_redirect)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
