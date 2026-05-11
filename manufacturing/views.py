import os
import sys
import subprocess
import sqlite3
from django.shortcuts import render, redirect


DEPT_MENUS = {
    'accounting': {
        'title': 'Accounting Main Menu',
        'subdepts': [
            ('acct_pay',  'Accounts Payable',    'Accounts_payable.py'),
            ('acct_mgr',  'Accounting Manager',  'Accounting_manager.py'),
            ('acct_rcv',  'Accounts Receivable', 'Accounts_receivable.py'),
            ('credit',    'Credit Department',   'Credit_dept.py'),
            ('payroll',   'Payroll Department',  'Payroll_dept.py'),
        ],
    },
    'customer_service': {
        'title': 'Customer Service Main Menu',
        'subdepts': [
            ('cs_mgr',   'CS Manager Menu',        'cs_mgr_menu.py'),
            ('cs_menu',  'Customer Service Menu',  'cs_menu.py'),
            ('cs_calls', 'Customer Service Calls', 'cs_calls.py'),
        ],
    },
    'engineering': {
        'title': 'Engineering Main Menu',
        'subdepts': [
            ('eng_mgr',   'Engineering Manager', 'eng_mgr.py'),
            ('engineers', 'Engineers',            'engineer.py'),
        ],
    },
    'information_tech': {
        'title': 'Information Technology Main Menu',
        'subdepts': [
            ('it_mgr',  'IT Manager',    'IT_mgr.py'),
            ('it_tech', 'IT Technician', 'IT_technician.py'),
        ],
    },
    'maintenance': {
        'title': 'Maintenance Main Menu',
        'subdepts': [
            ('maint_mgr', 'Maintenance Manager', 'Maint_mgr_menu.py'),
            ('maint',     'Maintenance',          'Maint_Maint_menu.py'),
        ],
    },
    'marketing': {
        'title': 'Marketing Main Menu',
        'subdepts': [
            ('mkt_mgr',  'Marketing Manager Menu', 'marketing_mgr_menu.py'),
            ('mkt_menu', 'Marketing Menu',          'marketing_menu.py'),
        ],
    },
    'personnel': {
        'title': 'Personnel Main Menu',
        'subdepts': [
            ('pers_mgr',  'Personnel Manager Menu', 'personnel_mgr_menu.py'),
            ('pers_menu', 'Personnel Menu',          'personnel_menu.py'),
        ],
    },
    'production': {
        'title': 'Production Main Menu',
        'subdepts': [
            ('prod_mgr', 'Production Manager', 'prod_mgr_Menu.py'),
            ('prod',     'Production',          'prod_prod_menu.py'),
            ('shipping', 'Shipping',            'prod_ship_dept.py'),
        ],
    },
    'purchasing': {
        'title': 'Purchasing Main Menu',
        'subdepts': [
            ('purch_mgr', 'Purchasing Manager Menu', 'Purchasing_Mgr_menu.py'),
            ('purch',     'Purchasing Menu',          'Purchasing_menu.py'),
        ],
    },
    'quality_assurance': {
        'title': 'Quality Assurance Main Menu',
        'subdepts': [
            ('qa_mgr',  'QA Manager Menu',        'QA_Mgr_menu.py'),
            ('qa_menu', 'Quality Assurance Menu', 'Quality_Assurance_menu.py'),
        ],
    },
    'sales': {
        'title': 'Sales Main Menu',
        'subdepts': [
            ('sales_mgr', 'Sales Manager Menu', 'Sales_mgr_menu.py'),
            ('sales',     'Sales Menu',          'Sales_menu.py'),
        ],
    },
}


DB_PATH = os.path.join(os.path.dirname(__file__), 'company.db')


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _verify_login(email: str, password: str) -> bool:
    conn = _get_db()
    row = conn.execute(
        "SELECT pw.password FROM passwd pw JOIN people p ON pw.people_id = p.id WHERE p.email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return row is not None and password == row["password"]


def _email_exists(email: str) -> bool:
    conn = _get_db()
    found = conn.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone()
    conn.close()
    return found is not None


def _create_user(email, password, first_name='', last_name='',
                 address='', city='', state='', zip_code='', employee_id=0) -> bool:
    try:
        conn = _get_db()
        if conn.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone():
            conn.close()
            return False
        cursor = conn.execute(
            "INSERT INTO people (first_name, last_name, ID, address, city, state, zip_code, email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (first_name, last_name, employee_id, address, city, state, zip_code, email),
        )
        conn.execute(
            "INSERT INTO passwd (people_id, password) VALUES (?, ?)",
            (cursor.lastrowid, password),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def _reset_password(email: str, new_password: str) -> bool:
    conn = _get_db()
    row = conn.execute(
        "SELECT pw.id as pw_id FROM passwd pw JOIN people p ON pw.people_id = p.id WHERE p.email = ?",
        (email,),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("UPDATE passwd SET password = ? WHERE id = ?", (new_password, row["pw_id"]))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Login / dashboard / logout
# ---------------------------------------------------------------------------

def home(request):
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
    return render(request, 'dashboard.html', {'email': email})


def logout(request):
    request.session.flush()
    return redirect('home')


def dept_menu(request, dept):
    if not request.session.get('user_email'):
        return redirect('home')
    menu = DEPT_MENUS.get(dept)
    if not menu:
        return redirect('dashboard')
    subdepts = [(key, label) for key, label, _script in menu['subdepts']]
    return render(request, 'dept_menu.html', {
        'email': request.session['user_email'],
        'title': menu['title'],
        'dept': dept,
        'subdepts': subdepts,
    })


def launch_subdept(request, dept, subdept):
    if not request.session.get('user_email'):
        return redirect('home')
    menu = DEPT_MENUS.get(dept)
    if menu:
        for key, _label, script in menu['subdepts']:
            if key == subdept:
                manufacturing_dir = os.path.dirname(__file__)
                subprocess.Popen([sys.executable, os.path.join(manufacturing_dir, script)],
                                 cwd=manufacturing_dir)
                break
    return redirect('dept_menu', dept=dept)


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
            return render(request, 'register.html', {'error': error, 'form': request.POST})

        emp_id = int(emp_id_text) if emp_id_text else 0
        ok = _create_user(email, password, first, last, address, city, state, zip_code, emp_id)

        if ok:
            return render(request, 'home.html', {
                'success': f'Account created for {first} {last}. You can now log in.',
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

def _get_all_users_with_roles():
    conn = _get_db()
    rows = conn.execute("""
        SELECT p.id, p.first_name, p.last_name, p.email,
               r.id as role_id, r.role_name
        FROM people p
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        ORDER BY p.last_name, p.first_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_all_roles():
    conn = _get_db()
    rows = conn.execute("SELECT id, role_name FROM roles ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _set_user_role(people_id: int, role_id: int):
    conn = _get_db()
    conn.execute("""
        INSERT INTO user_roles (people_id, role_id) VALUES (?, ?)
        ON CONFLICT(people_id) DO UPDATE SET role_id = excluded.role_id
    """, (people_id, role_id))
    conn.commit()
    conn.close()


def _remove_user_role(people_id: int):
    conn = _get_db()
    conn.execute("DELETE FROM user_roles WHERE people_id = ?", (people_id,))
    conn.commit()
    conn.close()


def user_roles(request):
    if not request.session.get('user_email'):
        return redirect('home')

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
