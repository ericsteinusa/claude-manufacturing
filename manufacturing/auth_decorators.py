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


def dept_required(dept_keys, *, write_redirect=None):
    """Gate a view to logged-in users in the given department(s).

    Full-access roles (President, Vice President) bypass the dept check.

    Parameters
    ----------
    dept_keys:
        A dept key string or iterable of dept key strings that are allowed
        (matched against ``request.session['user_dept_key']``).
    write_redirect:
        Named URL to redirect READ_ONLY_ROLES when a mutating view is hit.
        Omit for read-only views.
    """
    if isinstance(dept_keys, str):
        dept_keys = frozenset({dept_keys})
    else:
        dept_keys = frozenset(dept_keys)

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.session.get('user_email'):
                return redirect('home')
            if not request.session.get('user_full_access'):
                if request.session.get('user_dept_key') not in dept_keys:
                    return redirect('dashboard')
            if write_redirect and request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect(write_redirect)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
