import os
import sys
import subprocess
import sqlite3
from django.shortcuts import render, redirect


# Each item: (key, label, target)
# target is a script filename (str = leaf) or a dict (sub-menu node).
_TIME_CLOCK_MENU = {
    'title': 'Time Clock Menu',
    'items': [
        ('clock_in_out',  'Clock In/Out',       {'title': 'Clock In/Out',       'items': []}),
        ('view_hours',    'View Hours',          {'title': 'View Hours',         'items': []}),
        ('time_off',      'Time Off Requests',   {'title': 'Time Off Requests',  'items': []}),
        ('schedules',     'Schedules',           {'title': 'Schedules',          'items': []}),
        ('ot_reports',    'Overtime Reports',    {'title': 'Overtime Reports',   'items': []}),
        ('attend_reports','Attendance Reports',  {'title': 'Attendance Reports', 'items': []}),
        ('shift_mgmt',    'Shift Management',    {'title': 'Shift Management',   'items': []}),
    ],
}
_MAINT_MENU = {
    'title': 'Maintenance Menu',
    'items': [
        ('work_orders',    'Work Orders',           {'title': 'Work Orders',           'items': []}),
        ('maint_schedule', 'Maintenance Schedule',  {'title': 'Maintenance Schedule',  'items': []}),
        ('equip_maint',    'Equipment Maintenance', {'title': 'Equipment Maintenance', 'items': []}),
        ('parts_inv',      'Parts Inventory',       {'title': 'Parts Inventory',       'items': []}),
        ('maint_reports',  'Maintenance Reports',   {'title': 'Maintenance Reports',   'items': []}),
        ('safety_insp',    'Safety Inspections',    {'title': 'Safety Inspections',    'items': []}),
        ('prev_maint',     'Preventive Maintenance',{'title': 'Preventive Maintenance','items': []}),
    ],
}
_MKT_MENU = {
    'title': 'Marketing Menu',
    'items': [
        ('campaigns',    'Campaigns',         {'title': 'Campaigns',         'items': []}),
        ('mkt_research', 'Market Research',   {'title': 'Market Research',   'items': []}),
        ('advertising',  'Advertising',       {'title': 'Advertising',       'items': []}),
        ('analytics',    'Analytics',         {'title': 'Analytics',         'items': []}),
        ('content_mgmt', 'Content Management',{'title': 'Content Management','items': []}),
        ('social_media', 'Social Media',      {'title': 'Social Media',      'items': []}),
        ('email_mkt',    'Email Marketing',   {'title': 'Email Marketing',   'items': []}),
    ],
}
_SALES_MENU = {
    'title': 'Sales Menu',
    'items': [
        ('sales_orders',  'Sales Orders',      {'title': 'Sales Orders',      'items': []}),
        ('cust_accounts', 'Customer Accounts', {'title': 'Customer Accounts', 'items': []}),
        ('sales_reports', 'Sales Reports',     {'title': 'Sales Reports',     'items': []}),
        ('quotes',        'Quotes',            {'title': 'Quotes',            'items': []}),
    ],
}
_PROD_MENU = {
    'title': 'Production Menu',
    'items': [
        ('work_orders',   'Work Orders',          {'title': 'Work Orders',          'items': []}),
        ('prod_schedule', 'Production Schedule',  {'title': 'Production Schedule',  'items': []}),
        ('inventory',     'Inventory',            {'title': 'Inventory',            'items': []}),
        ('equip_status',  'Equipment Status',     {'title': 'Equipment Status',     'items': []}),
    ],
}
_SHIP_MENU = {
    'title': 'Shipping Department',
    'items': [
        ('ship_orders',   'Shipment Orders',    {'title': 'Shipment Orders',    'items': []}),
        ('ship_schedule', 'Shipping Schedule',  {'title': 'Shipping Schedule',  'items': []}),
        ('receiving',     'Receiving',          {'title': 'Receiving',          'items': []}),
        ('carrier_mgmt',  'Carrier Management', {'title': 'Carrier Management', 'items': []}),
    ],
}
_QA_LAB_MENU = {
    'title': 'QA Laboratory Menu',
    'items': [
        ('test_requests',  'Test Requests',      {'title': 'Test Requests',      'items': []}),
        ('lab_results',    'Lab Results',        {'title': 'Lab Results',        'items': []}),
        ('insp_reports',   'Inspection Reports', {'title': 'Inspection Reports', 'items': []}),
        ('non_conformance','Non-Conformance',    {'title': 'Non-Conformance',    'items': []}),
        ('calibration',    'Calibration',        {'title': 'Calibration',        'items': []}),
        ('sample_mgmt',    'Sample Management',  {'title': 'Sample Management',  'items': []}),
        ('lab_reports',    'Lab Reports',        {'title': 'Lab Reports',        'items': []}),
    ],
}
_QA_MENU = {
    'title': 'Quality Assurance Menu',
    'items': [
        ('qa_lab', 'QA Laboratory Menu', _QA_LAB_MENU),
    ],
}
_PERS_MENU = {
    'title': 'Personnel Menu',
    'items': [
        ('pers_crm',    'Personnel CRM',       'personnel_crm.py'),
        ('reg_form',    'Registration Form',   'registration_form.py'),
        ('upd_pass',    'Update Password',     'update_users.py'),
        ('disp_dept',   'Display Department',  'display_people_department.py'),
        ('dept_entry',  'Dept Entry',          'dept_entry.py'),
        ('dept_sub',    'Dept Sub Entry',      'dept_sub_entry.py'),
        ('time_clock',  'Time Clock',          _TIME_CLOCK_MENU),
        ('emp_records', 'Employee Records',    {'title': 'Employee Records',    'items': []}),
        ('benefits',    'Benefits',            {'title': 'Benefits',            'items': []}),
        ('perf_review', 'Performance Reviews', {'title': 'Performance Reviews', 'items': []}),
    ],
}
_CS_MENU = {
    'title': 'Customer Service Menu',
    'items': [
        ('cs_calls',   'Customer Service Calls', 'cs_calls.py'),
        ('cust_entry', 'Customer Entry Screen',  'customer_entry.py'),
        ('open_tickets',  'Open Tickets',      {'title': 'Open Tickets',      'items': []}),
        ('cust_accounts', 'Customer Accounts', {'title': 'Customer Accounts', 'items': []}),
        ('returns',       'Returns & Refunds', {'title': 'Returns & Refunds', 'items': []}),
    ],
}
_IT_TECH = {
    'title': 'IT Technician',
    'items': [
        ('it_calls',    'IT Support Calls',  'it_calls.py'),
        ('it_tasks',    'IT Tasks',          'IT_Tasks.py'),
        ('help_desk',   'Help Desk Tickets', {'title': 'Help Desk Tickets', 'items': []}),
        ('asset_mgmt',  'Asset Management',  {'title': 'Asset Management',  'items': []}),
        ('net_status',  'Network Status',    {'title': 'Network Status',    'items': []}),
    ],
}
_PURCH_MENU = {
    'title': 'Purchasing Menu',
    'items': [
        ('prod_entry',    'Product Entry',    'product_entry_screen.py'),
        ('sup_entry',     'Supplier Entry',   'Supplier_entry.py'),
        ('purch_orders',  'Purchase Orders',  {'title': 'Purchase Orders',  'items': []}),
        ('vendor_mgmt',   'Vendor Management',{'title': 'Vendor Management','items': []}),
        ('purch_reports', 'Purchase Reports', {'title': 'Purchase Reports', 'items': []}),
    ],
}

MENU_TREE = {
    'accounting': {
        'title': 'Accounting Main Menu',
        'items': [
            ('acct_pay',    'Accounts Payable',    'Accounts_payable.py'),
            ('acct_mgr',    'Accounting Manager', {
                'title': 'Accounting Manager',
                'items': [
                    ('ap',          'Accounts Payable',    'Accounts_payable.py'),
                    ('rcv',         'Accounts Receivable', 'Accounts_receivable.py'),
                    ('credit',      'Credit Department',   'Credit_dept.py'),
                    ('pay',         'Payroll Department',  'Payroll_dept.py'),
                    ('fin_reports', 'Financial Reports',   {'title': 'Financial Reports',   'items': []}),
                    ('budget_mgmt', 'Budget Management',   {'title': 'Budget Management',   'items': []}),
                    ('audit_mgmt',  'Audit Management',    {'title': 'Audit Management',    'items': []}),
                ],
            }),
            ('acct_rcv',    'Accounts Receivable', 'Accounts_receivable.py'),
            ('credit',      'Credit Department',   'Credit_dept.py'),
            ('payroll',     'Payroll Department',  'Payroll_dept.py'),
            ('gen_ledger',  'General Ledger',      {'title': 'General Ledger',      'items': []}),
            ('budget_mgmt', 'Budget Management',   {'title': 'Budget Management',   'items': []}),
            ('fin_reports', 'Financial Reports',   {'title': 'Financial Reports',   'items': []}),
        ],
    },
    'customer_service': {
        'title': 'Customer Service Main Menu',
        'items': [
            ('cs_mgr', 'CS Manager Menu', {
                'title': 'CS Manager Menu',
                'items': [
                    ('cs_menu',    'Customer Service Menu',  _CS_MENU),
                    ('ticket_rpts','Ticket Reports',         {'title': 'Ticket Reports',         'items': []}),
                    ('staff_mgmt', 'Staff Management',       {'title': 'Staff Management',       'items': []}),
                    ('cust_sat',   'Customer Satisfaction',  {'title': 'Customer Satisfaction',  'items': []}),
                    ('escalations','Escalations',            {'title': 'Escalations',            'items': []}),
                ],
            }),
            ('cs_menu',  'Customer Service Menu',  _CS_MENU),
            ('cs_calls', 'Customer Service Calls', 'cs_calls.py'),
        ],
    },
    'engineering': {
        'title': 'Engineering Main Menu',
        'items': [
            ('eng_mgr', 'Engineering Manager', {
                'title': 'Engineering Manager',
                'items': [
                    ('engineers',  'Engineers',           'engineer.py'),
                    ('proj_appr',  'Project Approvals',   {'title': 'Project Approvals',   'items': []}),
                    ('resource',   'Resource Management', {'title': 'Resource Management', 'items': []}),
                    ('budget',     'Budget Management',   {'title': 'Budget Management',   'items': []}),
                    ('eng_reports','Engineering Reports', {'title': 'Engineering Reports', 'items': []}),
                ],
            }),
            ('engineers',   'Engineers',          'engineer.py'),
            ('proj_mgmt',   'Project Management', {'title': 'Project Management', 'items': []}),
            ('design_docs', 'Design Documents',   {'title': 'Design Documents',   'items': []}),
            ('bom',         'Bill of Materials',  {'title': 'Bill of Materials',  'items': []}),
            ('chg_orders',  'Change Orders',      {'title': 'Change Orders',      'items': []}),
        ],
    },
    'information_tech': {
        'title': 'Information Technology Main Menu',
        'items': [
            ('it_mgr', 'IT Manager', {
                'title': 'IT Manager',
                'items': [
                    ('it_tech',    'IT Technician',       _IT_TECH),
                    ('budget',     'Budget & Procurement', {'title': 'Budget & Procurement', 'items': []}),
                    ('vendor_con', 'Vendor Contracts',     {'title': 'Vendor Contracts',     'items': []}),
                    ('it_projects','IT Projects',          {'title': 'IT Projects',          'items': []}),
                    ('security',   'Security Management',  {'title': 'Security Management',  'items': []}),
                ],
            }),
            ('it_tech', 'IT Technician', _IT_TECH),
        ],
    },
    'maintenance': {
        'title': 'Maintenance Main Menu',
        'items': [
            ('maint_mgr', 'Maintenance Manager', {
                'title': 'Maintenance Manager',
                'items': [
                    ('maint',       'Maintenance',         _MAINT_MENU),
                    ('wo_approvals','Work Order Approvals',{'title': 'Work Order Approvals','items': []}),
                    ('budget_mgmt', 'Budget Management',   {'title': 'Budget Management',   'items': []}),
                    ('maint_rpts',  'Maintenance Reports', {'title': 'Maintenance Reports', 'items': []}),
                ],
            }),
            ('maint', 'Maintenance', _MAINT_MENU),
        ],
    },
    'marketing': {
        'title': 'Marketing Main Menu',
        'items': [
            ('mkt_mgr', 'Marketing Manager Menu', {
                'title': 'Marketing Manager Menu',
                'items': [
                    ('mkt_menu',   'Marketing Menu',     _MKT_MENU),
                    ('mkt_budget', 'Marketing Budget',   {'title': 'Marketing Budget',   'items': []}),
                    ('camp_appr',  'Campaign Approvals', {'title': 'Campaign Approvals', 'items': []}),
                    ('mkt_reports','Marketing Reports',  {'title': 'Marketing Reports',  'items': []}),
                ],
            }),
            ('mkt_menu', 'Marketing Menu', _MKT_MENU),
        ],
    },
    'personnel': {
        'title': 'Personnel Main Menu',
        'items': [
            ('pers_mgr', 'Personnel Manager Menu', {
                'title': 'Personnel Manager Menu',
                'items': [
                    ('pers_menu', 'Personnel Menu',      _PERS_MENU),
                    ('hiring',    'Hiring & Recruitment',{'title': 'Hiring & Recruitment','items': []}),
                    ('term',      'Terminations',        {'title': 'Terminations',        'items': []}),
                    ('salary',    'Salary Management',   {'title': 'Salary Management',   'items': []}),
                    ('hr_reports','HR Reports',          {'title': 'HR Reports',          'items': []}),
                ],
            }),
            ('pers_menu', 'Personnel Menu', _PERS_MENU),
        ],
    },
    'production': {
        'title': 'Production Main Menu',
        'items': [
            ('prod_mgr', 'Production Manager', {
                'title': 'Production Manager',
                'items': [
                    ('prod',        'Production',         _PROD_MENU),
                    ('shipping',    'Shipping',           _SHIP_MENU),
                    ('prod_reports','Production Reports', {'title': 'Production Reports', 'items': []}),
                    ('resource',    'Resource Management',{'title': 'Resource Management','items': []}),
                    ('budget',      'Budget Management',  {'title': 'Budget Management',  'items': []}),
                ],
            }),
            ('prod',     'Production', _PROD_MENU),
            ('shipping', 'Shipping',   _SHIP_MENU),
        ],
    },
    'purchasing': {
        'title': 'Purchasing Main Menu',
        'items': [
            ('purch_mgr', 'Purchasing Manager Menu', {
                'title': 'Purchasing Manager Menu',
                'items': [
                    ('purch',      'Purchasing Menu',          _PURCH_MENU),
                    ('po_approvals','PO Approvals',            {'title': 'PO Approvals',            'items': []}),
                    ('budget',     'Budget Management',        {'title': 'Budget Management',        'items': []}),
                    ('vendor_mgmt','Vendor Management',        {'title': 'Vendor Management',        'items': []}),
                    ('purch_rpts', 'Purchasing Reports',       {'title': 'Purchasing Reports',       'items': []}),
                    ('contracts',  'Contract Management',      {'title': 'Contract Management',      'items': []}),
                ],
            }),
            ('purch', 'Purchasing Menu', _PURCH_MENU),
        ],
    },
    'quality_assurance': {
        'title': 'Quality Assurance Main Menu',
        'items': [
            ('qa_mgr', 'QA Manager Menu', {
                'title': 'QA Manager Menu',
                'items': [
                    ('qa_menu',    'Quality Assurance Menu', _QA_MENU),
                    ('audit_mgmt', 'Audit Management',   {'title': 'Audit Management',   'items': []}),
                    ('compliance', 'Compliance',          {'title': 'Compliance',          'items': []}),
                    ('corr_action','Corrective Actions',  {'title': 'Corrective Actions',  'items': []}),
                    ('qa_reports', 'QA Reports',          {'title': 'QA Reports',          'items': []}),
                    ('supp_qual',  'Supplier Quality',    {'title': 'Supplier Quality',    'items': []}),
                    ('cust_comp',  'Customer Complaints', {'title': 'Customer Complaints', 'items': []}),
                    ('doc_control','Document Control',    {'title': 'Document Control',    'items': []}),
                ],
            }),
            ('qa_menu', 'Quality Assurance Menu', _QA_MENU),
        ],
    },
    'sales': {
        'title': 'Sales Main Menu',
        'items': [
            ('sales_mgr', 'Sales Manager Menu', {
                'title': 'Sales Manager Menu',
                'items': [
                    ('sales',        'Sales Menu',            _SALES_MENU),
                    ('sales_targets','Sales Targets',         {'title': 'Sales Targets',         'items': []}),
                    ('territory',    'Territory Management',  {'title': 'Territory Management',  'items': []}),
                    ('commission',   'Commission Tracking',   {'title': 'Commission Tracking',   'items': []}),
                    ('staff_perf',   'Staff Performance',     {'title': 'Staff Performance',     'items': []}),
                ],
            }),
            ('sales', 'Sales Menu', _SALES_MENU),
        ],
    },
}


def _walk_tree(dept, parts):
    """Walk MENU_TREE by dept + list of key parts. Returns the node dict, or None."""
    node = MENU_TREE.get(dept)
    if node is None:
        return None
    for part in parts:
        found = None
        for key, _label, target in node.get('items', []):
            if key == part:
                found = target
                break
        if not isinstance(found, dict):
            return None
        node = found
    return node


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


def generic_menu(request, dept, subpath=''):
    if not request.session.get('user_email'):
        return redirect('home')
    parts = [p for p in subpath.split('/') if p]
    node = _walk_tree(dept, parts)
    if node is None:
        return redirect('dashboard')

    items = []
    for key, label, target in node['items']:
        new_parts = parts + [key]
        if isinstance(target, dict):
            url = '/dept/{}/{}/'.format(dept, '/'.join(new_parts))
        else:
            url = '/run/{}/{}/'.format(dept, '/'.join(new_parts))
        items.append((url, label))

    if parts:
        parent = parts[:-1]
        back_url = '/dept/{}/{}/'.format(dept, '/'.join(parent)) if parent else '/dept/{}/'.format(dept)
    else:
        back_url = '/dashboard/'

    return render(request, 'dept_menu.html', {
        'email': request.session['user_email'],
        'title': node['title'],
        'items': items,
        'back_url': back_url,
    })


def run_script(request, dept, subpath):
    if not request.session.get('user_email'):
        return redirect('home')
    parts = [p for p in subpath.split('/') if p]
    if not parts:
        return redirect('dashboard')
    parent_parts, leaf_key = parts[:-1], parts[-1]
    node = _walk_tree(dept, parent_parts)
    if node:
        for key, _label, target in node['items']:
            if key == leaf_key and isinstance(target, str):
                mfg_dir = os.path.dirname(__file__)
                subprocess.Popen([sys.executable, os.path.join(mfg_dir, target)], cwd=mfg_dir)
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
