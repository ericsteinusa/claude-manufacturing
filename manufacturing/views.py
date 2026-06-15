"""Django HTTP handlers for login, navigation, and account management.

Menu data lives in :mod:`manufacturing.menus`; authentication and role
persistence live in :mod:`manufacturing.accounts`.
"""

import os
import sys
import subprocess

from django.shortcuts import render, redirect

from .log_utils import get_logger
from .schema import init_schema
from .db_pg import get_db_connection
from .purchase_orders_core import (
    PO_STATUSES, PO_STATUS_COLORS, list_pos, get_po, get_po_items,
)
from .menus import (
    DASHBOARD_DEPARTMENTS,
    MANAGER_MENU_KEYS,
    _walk_tree,
)
from .accounts import (
    READ_ONLY_ROLES,
    _ROLE_ADMIN_ROLES,
    _get_user_profile,
    _is_full_access,
    _verify_login,
    _email_exists,
    _create_user,
    _reset_password,
    _get_all_users_with_roles,
    _get_all_roles,
    _set_user_role,
    _remove_user_role,
)

log = get_logger(__name__)

# Menu leaves that are served as web pages rather than launched as a desktop
# Qt subprocess via run_script. Keyed by (dept, leaf_key) -> URL. The PO
# viewer (open/status/history) all land on the filterable list.
WEB_LEAF_URLS = {
    ('purchasing', 'open_pos'): '/po/',
    ('purchasing', 'po_status'): '/po/',
    ('purchasing', 'po_hist'): '/po/',
}


def _init_schema():
    """Create application tables if they don't exist.

    Thin wrapper around the canonical schema module, kept for the
    AppConfig.ready() hook in apps.py.
    """
    init_schema()


# ---------------------------------------------------------------------------
# Login / dashboard / logout
# ---------------------------------------------------------------------------


def home(request):
    # Schema and canonical roles are seeded once at startup by
    # AppConfig.ready() (-> _init_schema), so no per-request seeding here.
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        if not email or not password:
            return render(request, 'home.html', {
                'error': 'Please enter both email and password.',
                'email_value': email,
            })

        if _verify_login(email, password):
            request.session['user_email'] = email
            profile = _get_user_profile(email)
            request.session['user_role'] = profile.get('role_name', '')
            request.session['user_dept_key'] = profile.get('dept_key') or ''
            request.session['user_dept_name'] = profile.get('dept_name', '')
            request.session['user_full_access'] = _is_full_access(profile)
            request.session['user_is_manager'] = profile.get(
                'is_manager', False)
            if request.session['user_full_access']:
                return redirect('dashboard')
            dept_key = profile.get('dept_key')
            if dept_key:
                return redirect('dept_menu', dept=dept_key)
            return redirect('dashboard')

        return render(request, 'home.html', {
            'error': 'Invalid email or password.',
            'email_value': email,
        })

    if request.session.get('user_email'):
        return redirect('dashboard')

    return render(request, 'home.html', {})


def dashboard(request):
    email = request.session.get('user_email')
    if not email:
        return redirect('home')
    if not request.session.get('user_full_access'):
        dept_key = request.session.get('user_dept_key')
        if dept_key:
            return redirect('dept_menu', dept=dept_key)
    menu_items = [
        ('/dept/{}/'.format(key), label)
        for key, label in DASHBOARD_DEPARTMENTS
    ]
    return render(request, 'dashboard.html', {
        'email': email,
        'user_role': request.session.get('user_role', ''),
        'dept_name': request.session.get('user_dept_name', ''),
        'full_access': request.session.get('user_full_access', False),
        'menu_items': menu_items,
    })


def logout(request):
    email = request.session.get('user_email')
    request.session.flush()
    if email:
        log.info("User %s logged out", email)
    return redirect('home')


def generic_menu(request, dept, subpath=''):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        user_dept = request.session.get('user_dept_key', '')
        if not user_dept:
            return redirect('dashboard')
        if dept != user_dept:
            return redirect('dept_menu', dept=user_dept)
    parts = [p for p in subpath.split('/') if p]
    node = _walk_tree(dept, parts)
    if node is None:
        return redirect('dashboard')

    is_manager = request.session.get('user_is_manager', False)
    items = []
    for key, label, target in node['items']:
        if key in MANAGER_MENU_KEYS and not is_manager:
            continue
        new_parts = parts + [key]
        if isinstance(target, dict):
            url = '/dept/{}/{}/'.format(dept, '/'.join(new_parts))
        elif (dept, key) in WEB_LEAF_URLS:
            # Served as a real web page instead of launching a desktop window.
            url = WEB_LEAF_URLS[(dept, key)]
        else:
            url = '/run/{}/{}/'.format(dept, '/'.join(new_parts))
        items.append((url, label))

    if parts:
        parent = parts[:-1]
        if parent:
            back_url = '/dept/{}/{}/'.format(dept, '/'.join(parent))
        else:
            back_url = '/dept/{}/'.format(dept)
    else:
        back_url = '/dashboard/'

    return render(request, 'dept_menu.html', {
        'email': request.session['user_email'],
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'title': node['title'],
        'menu_items': items,
        'back_url': back_url,
    })


def run_script(request, dept, subpath):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('dept_menu', dept=dept)
    if not request.session.get('user_full_access'):
        user_dept = request.session.get('user_dept_key', '')
        if not user_dept:
            return redirect('dashboard')
        if dept != user_dept:
            return redirect('dept_menu', dept=user_dept)
    parts = [p for p in subpath.split('/') if p]
    if not parts:
        return redirect('dashboard')
    parent_parts, leaf_key = parts[:-1], parts[-1]
    node = _walk_tree(dept, parent_parts)
    if node:
        for key, _label, target in node['items']:
            if key == leaf_key and isinstance(target, str):
                mfg_dir = os.path.dirname(__file__)
                module_name = os.path.splitext(target)[0]
                project_dir = os.path.dirname(mfg_dir)
                log.info(
                    "User %s launching manufacturing.%s (%s/%s)",
                    request.session.get('user_email'), module_name,
                    dept, subpath)
                try:
                    subprocess.Popen(
                        [sys.executable, '-m',
                            f'manufacturing.{module_name}', leaf_key],
                        cwd=project_dir,
                    )
                except Exception:
                    log.error(
                        "Failed to launch manufacturing.%s", module_name,
                        exc_info=True)
                    raise
                break
    if parent_parts:
        return redirect('/dept/{}/{}/'.format(dept, '/'.join(parent_parts)))
    return redirect('/dept/{}/'.format(dept))


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register(request):
    if request.method == 'POST':
        first = request.POST.get('first_name', '').strip()
        last = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')
        emp_id_text = request.POST.get('employee_id', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()

        error = None
        if not first or not last:
            error = 'First and last name are required.'
        elif not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif emp_id_text and not emp_id_text.isdigit():
            error = 'Employee ID must be a number.'

        if error:
            return render(request, 'register.html', {
                          'error': error, 'form': request.POST})

        emp_id = int(emp_id_text) if emp_id_text else 0
        ok = _create_user(email, password, first, last,
                          address, city, state, zip_code, emp_id)

        if ok:
            return render(request, 'home.html', {
                'success': f'Account created for {first} {last}. '
                'You can now log in.',
            })
        return render(request, 'register.html', {
            'error': 'That email address is already registered.',
            'form': request.POST,
        })

    return render(request, 'register.html', {})


# ---------------------------------------------------------------------------
# Forgot password (two-step: verify email, then reset)
# ---------------------------------------------------------------------------

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        if not email or '@' not in email:
            return render(request, 'forgot_password.html', {
                'error': 'Please enter a valid email address.',
                'email_value': email,
            })

        if not _email_exists(email):
            return render(request, 'forgot_password.html', {
                'error': 'No account found for that email address.',
                'email_value': email,
            })

        request.session['reset_email'] = email
        return redirect('forgot_password_reset')

    return render(request, 'forgot_password.html', {})


def forgot_password_reset(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == 'POST':
        new_pw = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        if len(new_pw) < 8:
            return render(request, 'forgot_password_reset.html', {
                'error': 'Password must be at least 8 characters.',
                'email': email,
            })
        if new_pw != confirm:
            return render(request, 'forgot_password_reset.html', {
                'error': 'Passwords do not match.',
                'email': email,
            })

        ok = _reset_password(email, new_pw)
        if ok:
            del request.session['reset_email']
            return render(request, 'home.html', {
                'success': 'Your password has been reset. You can now log in.',
            })
        return render(request, 'forgot_password_reset.html', {
            'error': 'Password reset failed. Please try again.',
            'email': email,
        })

    return render(request, 'forgot_password_reset.html', {'email': email})


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------

def change_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        current = request.POST.get('current_password', '')
        new_pw = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        error = None
        if not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif not current:
            error = 'Please enter your current password.'
        elif len(new_pw) < 8:
            error = 'New password must be at least 8 characters.'
        elif new_pw != confirm:
            error = 'New passwords do not match.'
        elif new_pw == current:
            error = 'New password must differ from your current password.'

        if error:
            return render(request, 'change_password.html', {
                'error': error,
                'email_value': email,
            })

        if not _verify_login(email, current):
            log.warning(
                "Password change denied for %s: current password incorrect",
                email)
            return render(request, 'change_password.html', {
                'error': 'Incorrect email or current password.',
                'email_value': email,
            })

        _reset_password(email, new_pw)
        return render(request, 'home.html', {
            'success': 'Your password has been changed. You can now log in.',
        })

    return render(request, 'change_password.html', {})


# ---------------------------------------------------------------------------
# User roles
# ---------------------------------------------------------------------------


def user_roles(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') not in _ROLE_ADMIN_ROLES:
        return redirect('dashboard')

    roles = _get_all_roles()

    if request.method == 'POST':
        users = _get_all_users_with_roles()
        for user in users:
            key = f"role_{user['id']}"
            value = request.POST.get(key, '').strip()
            if value:
                _set_user_role(user['id'], int(value))
            else:
                _remove_user_role(user['id'])
        return redirect('user_roles')

    users = _get_all_users_with_roles()
    return render(request, 'user_roles.html', {'users': users, 'roles': roles})


# ---------------------------------------------------------------------------
# Purchase orders (web)
# ---------------------------------------------------------------------------


def _po_access(request):
    """Gate PO pages: logged in, and either full access or Purchasing dept.

    Returns a redirect response to send the user to, or ``None`` if allowed.
    Mirrors the dept gating in :func:`generic_menu`.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'purchasing':
            return redirect('dashboard')
    return None


def _po_context(request, **extra):
    """Toolbar context shared by the PO templates (matches base.html)."""
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def po_list(request):
    denied = _po_access(request)
    if denied:
        return denied

    status = request.GET.get('status') or None
    if status not in PO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        pos = list_pos(conn, status=status)
    finally:
        conn.close()

    for po in pos:
        po['status_color'] = PO_STATUS_COLORS.get(po['status'], '#ffffff')

    return render(request, 'po_list.html', _po_context(
        request,
        pos=pos,
        status=status,
        statuses=PO_STATUSES,
        back_url='/dept/purchasing/purch/purch_orders/',
    ))


def po_detail(request, po_id):
    denied = _po_access(request)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        items = get_po_items(conn, po_id) if po else []
    finally:
        conn.close()

    if not po:
        return redirect('po_list')

    po['status_color'] = PO_STATUS_COLORS.get(po['status'], '#ffffff')

    return render(request, 'po_detail.html', _po_context(
        request,
        po=po,
        items=items,
        back_url='/po/',
    ))
