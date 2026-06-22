"""Django HTTP handlers for login, navigation, and account management.

Menu data lives in :mod:`manufacturing.menus`; authentication and role
persistence live in :mod:`manufacturing.accounts`.
"""

import os
import sys
import subprocess
from datetime import date, timedelta

import psycopg2

from django.shortcuts import render, redirect

from .log_utils import get_logger
from .schema import init_schema
from .db_pg import get_db_connection
from .audit_core import get_recent, get_history, AUDITED_TABLES
from .approval_core import (
    needs_approval, request_approval, approve_po, reject_po,
    get_pending_approvals, count_pending, get_po_approval,
    APPROVAL_THRESHOLD, APPROVAL_ROLES,
)
from .bom_web_core import (
    list_products, get_product, get_bom, explode_bom,
    add_bom_line, update_bom_line, delete_bom_line,
    update_item_master, ITEM_TYPES,
)
from .mrp_web_core import (
    get_demand_details, get_scheduled_receipts_detail,
    run_mrp, release_plan as mrp_release_plan,
)
from .inventory_core import (
    TRANS_TYPES,
    list_products as inv_list_products,
    get_product as inv_get_product,
    get_transactions, get_alert_counts,
    load_suppliers as inv_load_suppliers,
    record_transaction, create_product as inv_create_product,
    update_product as inv_update_product,
)
from .contacts_core import (
    contact_label,
    list_customers, get_customer, create_customer, update_customer,
    get_customer_orders,
    list_suppliers as contacts_list_suppliers,
    get_supplier, create_supplier, update_supplier,
    get_supplier_orders,
)
from .cs_calls_core import (
    validate_call, PLAN_STATUSES,
    load_customers_for_cs,
    list_tickets, get_ticket, create_ticket, update_ticket, close_ticket,
    get_escalations, get_summary_stats, get_monthly_volume,
    list_plans, create_plan, update_plan,
)
from .period_locking_core import (
    is_period_locked, close_period, reopen_period,
    list_periods, recent_months, period_label, PERIOD_ADMIN_ROLES,
)
from .purchase_orders_core import (
    PO_STATUSES, PO_STATUS_COLORS, PO_STATUS_ACTION_LABELS,
    list_pos, get_po, get_po_items,
    next_po_number, load_suppliers, load_products,
    create_po, update_po, add_po_item, delete_po_item,
    allowed_transitions, can_transition, set_po_status, receive_po_item,
)
from .time_clock_core import (
    get_current_entry, clock_in as tc_clock_in, clock_out_entry,
    list_entries, total_hours as tc_total_hours,
    get_period_dates, get_attendance,
)
from .time_clock_poller_core import (
    DEVICE_TYPES, DEVICE_TYPE_LABELS,
    list_devices, get_device, create_device, update_device, delete_device,
    list_sync_log, poll_device,
)
from .personnel_core import (
    TIME_OFF_STATUSES, TIME_OFF_TYPES,
    list_people, get_person, get_person_by_email,
    create_person, update_person,
    load_depts, load_dept_subs,
    list_time_off_requests, get_time_off_request,
    create_time_off_request, set_time_off_status,
)
from .sales_orders_core import (
    SO_STATUSES, SO_STATUS_COLORS, SO_STATUS_ACTION_LABELS,
    list_sos, get_so, get_so_items,
    next_so_number, load_customers, load_products as load_so_products,
    create_so, update_so, add_so_item, delete_so_item,
    allowed_transitions as so_allowed_transitions,
    can_transition as so_can_transition,
    set_so_status,
)
from .work_orders_core import (
    WO_STATUSES, WO_STATUS_COLORS, WO_STATUS_ACTION_LABELS,
    list_wos, get_wo, get_wo_materials,
    next_wo_number, load_products as load_wo_products,
    create_wo, update_wo, add_wo_material, set_wo_status,
    can_transition as wo_can_transition,
    allowed_transitions as wo_allowed_transitions,
)
from .reports_core import (
    po_summary, wo_summary, inventory_alerts, cs_summary,
)
from .menus import (
    DASHBOARD_DEPARTMENTS,
    MANAGER_MENU_KEYS,
    _walk_tree,
)
from .accounts import (
    FULL_ACCESS_ROLES,
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
    ('purchasing', 'new_po'): '/po/new/',
    ('purchasing', 'open_pos'): '/po/',
    ('purchasing', 'po_status'): '/po/',
    ('purchasing', 'po_hist'): '/po/',
    ('reports', 'rpt_dashboard'): '/reports/',
    ('maintenance', 'create_wo'): '/wo/new/',
    ('maintenance', 'open_wo'): '/wo/?status=open',
    ('maintenance', 'inprog_wo'): '/wo/?status=in_progress',
    ('maintenance', 'comp_wo'): '/wo/?status=completed',
    ('production', 'create_wo'): '/wo/new/',
    ('production', 'open_wo'): '/wo/?status=open',
    ('production', 'inprog_wo'): '/wo/?status=in_progress',
    ('production', 'comp_wo'): '/wo/?status=completed',
    ('sales', 'new_order'): '/so/new/',
    ('sales', 'open_orders'): '/so/?status=confirmed',
    ('sales', 'order_hist'): '/so/',
    ('sales', 'order_stat'): '/so/',
    ('personnel', 'view_recs'): '/people/',
    ('personnel', 'new_emp'): '/people/new/',
    ('personnel', 'upd_rec'): '/people/',
    ('personnel', 'emp_hist'): '/people/',
    ('personnel', 'disp_dept'): '/people/',
    ('personnel', 'submit_req'): '/time-off/new/',
    ('personnel', 'pend_req'): '/time-off/?status=pending',
    ('personnel', 'appr_req'): '/time-off/?status=approved',
    ('personnel', 'req_hist'): '/time-off/',
    ('personnel', 'punch_in'): '/time-clock/',
    ('personnel', 'punch_out'): '/time-clock/',
    ('personnel', 'cur_status'): '/time-clock/',
    ('personnel', 'today_hrs'): '/time-clock/hours/',
    ('personnel', 'week_hrs'): '/time-clock/hours/?period=week',
    ('personnel', 'month_hrs'): '/time-clock/hours/?period=month',
    ('personnel', 'period_hrs'): '/time-clock/hours/?period=month',
    ('personnel', 'daily_att'): '/time-clock/attendance/',
    ('personnel', 'month_sum'): '/time-clock/attendance/?period=month',
    ('personnel', 'tard_rpt'): '/time-clock/attendance/',
    ('personnel', 'abs_rpt'): '/time-clock/attendance/',
    ('engineering', 'bom_list'): '/bom/',
    ('engineering', 'new_bom'): '/bom/',
    ('engineering', 'bom_rev'): '/bom/',
    ('engineering', 'bom_rpts'): '/bom/',
    ('production', 'bom_list'): '/bom/',
    ('production', 'mrp_home'): '/mrp/',
    ('production', 'run_mrp'): '/mrp/',
    ('production', 'mrp_demand'): '/mrp/',
    ('production', 'mrp_rpts'): '/mrp/',
    ('production', 'raw_mat'): '/inventory/?item_type=buy',
    ('production', 'fin_goods'): '/inventory/?item_type=make',
    ('production', 'wip_inv'): '/inventory/',
    ('production', 'inv_rpts'): '/inventory/',
    ('maintenance', 'view_inv'): '/inventory/',
    ('maintenance', 'parts_req'): '/inventory/',
    ('maintenance', 'reorder'): '/inventory/?filter=low',
    ('maintenance', 'parts_hist'): '/inventory/',
    # Customer Service tickets
    ('customer_service', 'cs_calls'): '/cs/',
    ('customer_service', 'all_tickets'): '/cs/',
    ('customer_service', 'my_tickets'): '/cs/?my=1',
    ('customer_service', 'hi_pri'): '/cs/escalations/',
    ('customer_service', 'tick_search'): '/cs/',
    ('customer_service', 'new_return'): '/cs/new/',
    # Customers
    ('customers', 'acct_list'): '/customers/',
    ('customers', 'new_acct'): '/customers/new/',
    ('customers', 'acct_det'): '/customers/',
    ('customers', 'acct_hist'): '/customers/',
    ('customer_service', 'cust_entry'): '/customers/new/',
    ('customer_service', 'acct_list'): '/customers/',
    ('customer_service', 'new_acct'): '/customers/new/',
    ('customer_service', 'acct_det'): '/customers/',
    ('customer_service', 'acct_hist'): '/customers/',
    ('sales', 'acct_list'): '/customers/',
    ('sales', 'new_acct'): '/customers/new/',
    ('sales', 'acct_det'): '/customers/',
    ('sales', 'acct_hist'): '/customers/',
    # Suppliers / Vendors
    ('customers', 'sup_entry'): '/suppliers/new/',
    ('customers', 'vend_list'): '/suppliers/',
    ('customers', 'new_vend'): '/suppliers/new/',
    ('purchasing', 'sup_entry'): '/suppliers/new/',
    ('purchasing', 'vend_list'): '/suppliers/',
    ('purchasing', 'new_vend'): '/suppliers/new/',
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
    pending_approvals = 0
    if request.session.get('user_role') in APPROVAL_ROLES:
        conn = get_db_connection()
        try:
            pending_approvals = count_pending(conn)
        finally:
            conn.close()
    return render(request, 'dashboard.html', {
        'email': email,
        'user_role': request.session.get('user_role', ''),
        'dept_name': request.session.get('user_dept_name', ''),
        'full_access': request.session.get('user_full_access', False),
        'menu_items': menu_items,
        'pending_approvals': pending_approvals,
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
                module_name = os.path.splitext(target)[0].replace('/', '.').replace(os.sep, '.')
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


def _po_access(request, write=False):
    """Gate PO pages: logged in, and either full access or Purchasing dept.

    With ``write=True`` also blocks ``READ_ONLY_ROLES`` from mutating (they may
    still view), mirroring the gating in :func:`run_script`. Returns a redirect
    response to send the user to, or ``None`` if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'purchasing':
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('po_list')
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
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/purchasing/purch/purch_orders/',
    ))


def po_detail(request, po_id):
    denied = _po_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        items = get_po_items(conn, po_id) if po else []
        products = load_products(conn) if (po and can_edit) else []
        approval = get_po_approval(conn, po_id) if po else None
    finally:
        conn.close()

    if not po:
        return redirect('po_list')

    po['status_color'] = PO_STATUS_COLORS.get(po['status'], '#ffffff')

    status_actions = [
        (target, PO_STATUS_ACTION_LABELS.get(target, target))
        for target in allowed_transitions(po['status'])
    ] if can_edit else []
    # Receiving is offered once the PO is out (sent/partial).
    can_receive = can_edit and po['status'] in ('sent', 'partial')

    return render(request, 'po_detail.html', _po_context(
        request,
        po=po,
        items=items,
        products=products,
        can_edit=can_edit,
        status_actions=status_actions,
        can_receive=can_receive,
        approval=approval,
        approval_threshold=APPROVAL_THRESHOLD,
        back_url='/po/',
    ))


# New POs may be created in either of these states; the rest of the workflow
# (sent -> partial -> received, cancelled) is driven by the status actions.
_PO_NEW_STATUSES = ('draft', 'sent')


def _int_or_none(value):
    """Coerce a form value to int, or None when blank/invalid (PO supplier and
    product columns are integer, so a text param would be rejected)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _po_header_form(request):
    """Pull + validate PO header fields from POST. Returns (data, error)."""
    po_number = (request.POST.get('po_number') or '').strip()
    status = request.POST.get('status') or 'draft'
    data = {
        'po_number': po_number,
        'supplier_id': _int_or_none(request.POST.get('supplier_id')),
        'order_date': (request.POST.get('order_date') or '').strip() or None,
        'expected_date':
            (request.POST.get('expected_date') or '').strip() or None,
        'status': status if status in _PO_NEW_STATUSES else 'draft',
        'notes': (request.POST.get('notes') or '').strip() or None,
    }
    if not po_number:
        return data, 'PO number is required.'
    return data, None


def po_new(request):
    denied = _po_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _po_header_form(request)
            if not error and is_period_locked(conn, data.get('order_date')):
                error = ("Period %s is closed."
                         % period_label(*map(int,
                             data['order_date'][:7].split('-'))))
            if not error:
                try:
                    po_id = create_po(
                        conn, **data,
                        created_by=request.session.get('user_email'))
                    conn.commit()
                    return redirect('po_detail', po_id=po_id)
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = ("PO number '%s' already exists."
                             % data['po_number'])
            suppliers = load_suppliers(conn)
            return render(request, 'po_form.html', _po_context(
                request, mode='new', error=error, form=data,
                suppliers=suppliers, statuses=_PO_NEW_STATUSES,
                back_url='/po/'))

        form = {
            'po_number': next_po_number(conn),
            'supplier_id': None,
            'order_date': date.today().isoformat(),
            'expected_date': (date.today() + timedelta(days=14)).isoformat(),
            'status': 'draft',
            'notes': '',
        }
        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    return render(request, 'po_form.html', _po_context(
        request, mode='new', form=form, suppliers=suppliers,
        statuses=_PO_NEW_STATUSES, back_url='/po/'))


def po_edit(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        if not po:
            return redirect('po_list')

        if request.method == 'POST':
            order_date = (request.POST.get('order_date') or '').strip() or None
            if is_period_locked(conn, order_date or po.get('order_date', '')):
                lbl = period_label(*map(int,
                    (order_date or po['order_date'])[:7].split('-')))
                suppliers = load_suppliers(conn)
                form = {
                    'po_number': po['po_number'],
                    'supplier_id': _int_or_none(
                        request.POST.get('supplier_id')),
                    'order_date': order_date or po['order_date'] or '',
                    'expected_date': (
                        request.POST.get('expected_date') or '').strip()
                        or po.get('expected_date') or '',
                    'status': po['status'],
                    'notes': (request.POST.get('notes') or '').strip()
                             or po.get('notes') or '',
                }
                return render(request, 'po_form.html', _po_context(
                    request, mode='edit', po=po, form=form,
                    suppliers=suppliers,
                    error="Period %s is closed." % lbl,
                    back_url='/po/%s/' % po_id))
            update_po(
                conn, po_id,
                supplier_id=_int_or_none(request.POST.get('supplier_id')),
                order_date=order_date,
                expected_date=(request.POST.get('expected_date') or '').strip()
                or None,
                notes=(request.POST.get('notes') or '').strip() or None,
            )
            conn.commit()
            return redirect('po_detail', po_id=po_id)

        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    # po_number/status are not editable here, but shown read-only.
    form = {
        'po_number': po['po_number'],
        'supplier_id': po['supplier_id'],
        'order_date': po['order_date'] or '',
        'expected_date': po['expected_date'] or '',
        'status': po['status'],
        'notes': po['notes'] or '',
    }
    return render(request, 'po_form.html', _po_context(
        request, mode='edit', po=po, form=form, suppliers=suppliers,
        back_url='/po/%s/' % po_id))


def po_add_item(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    description = (request.POST.get('description') or '').strip()
    product_id = _int_or_none(request.POST.get('product_id'))
    try:
        qty = int(request.POST.get('qty_ordered') or 1)
    except ValueError:
        qty = 1
    try:
        unit_price = float(request.POST.get('unit_price') or 0)
    except ValueError:
        unit_price = 0.0

    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        if po and description and qty >= 1 and unit_price >= 0:
            add_po_item(conn, po_id, description, product_id=product_id,
                        qty_ordered=qty, unit_price=unit_price)
            conn.commit()
    finally:
        conn.close()
    return redirect('po_detail', po_id=po_id)


def po_remove_item(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        if item_id:
            conn = get_db_connection()
            try:
                delete_po_item(conn, item_id, po_id=po_id)
                conn.commit()
            finally:
                conn.close()
    return redirect('po_detail', po_id=po_id)


def po_set_status(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        if po and can_transition(po['status'], target):
            if target == 'sent' and needs_approval(po.get('total', 0)):
                request_approval(
                    conn, po_id,
                    requested_by=request.session.get('user_email', ''),
                )
            else:
                set_po_status(conn, po_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('po_detail', po_id=po_id)


def po_receive_item(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    item_id = _int_or_none(request.POST.get('item_id'))
    qty = _int_or_none(request.POST.get('qty_received'))
    if item_id is not None and qty is not None and qty >= 0:
        conn = get_db_connection()
        try:
            # Clamp to the ordered quantity so receipts can't exceed the order.
            item = next((i for i in get_po_items(conn, po_id)
                         if i['id'] == item_id), None)
            if item is not None:
                qty = min(qty, item['qty_ordered'])
                receive_po_item(conn, item_id, qty, po_id=po_id)
                conn.commit()
        finally:
            conn.close()
    return redirect('po_detail', po_id=po_id)


# ---------------------------------------------------------------------------
# Reports dashboard (web)
# ---------------------------------------------------------------------------


def _reports_access(request):
    """Gate the reports dashboard: logged in + full access or reports dept."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'reports':
            return redirect('dashboard')
    return None


def reports_dashboard(request):
    denied = _reports_access(request)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        try:
            po = po_summary(conn)
        except Exception:
            po = None
        try:
            wo = wo_summary(conn)
        except Exception:
            wo = None
        try:
            inv = inventory_alerts(conn)
        except Exception:
            inv = None
        try:
            cs = cs_summary(conn)
        except Exception:
            cs = None
    finally:
        conn.close()

    def _status_pills(statuses_tuple, colors, by_status):
        return [
            (s.replace('_', ' ').title(), by_status.get(s, 0),
             colors.get(s, '#fff'))
            for s in statuses_tuple
        ]

    return render(request, 'reports_dashboard.html', {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'po': po,
        'wo': wo,
        'inv': inv,
        'cs': cs,
        'po_statuses': _status_pills(PO_STATUSES, PO_STATUS_COLORS,
                                     po['by_status'] if po else {}),
        'wo_statuses': _status_pills(WO_STATUSES, WO_STATUS_COLORS,
                                     wo['by_status'] if wo else {}),
    })


# ---------------------------------------------------------------------------
# Work orders (web)
# ---------------------------------------------------------------------------

_WO_DEPT_KEYS = {'maintenance', 'production'}
_WO_NEW_STATUSES = ('draft', 'open')


def _wo_access(request, write=False):
    """Gate WO pages: login + full_access or maintenance/production dept.

    With ``write=True`` also blocks READ_ONLY_ROLES from mutating.
    Returns a redirect or None if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _WO_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('wo_list')
    return None


def _wo_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def wo_list(request):
    denied = _wo_access(request)
    if denied:
        return denied

    status = request.GET.get('status') or None
    if status not in WO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        wos = list_wos(conn, status=status)
    finally:
        conn.close()

    for wo in wos:
        wo['status_color'] = WO_STATUS_COLORS.get(wo['status'], '#ffffff')
        wo['status_label'] = wo['status'].replace('_', ' ').title()

    dept = request.session.get('user_dept_key', 'production')
    back_url = (
        f'/dept/{dept}/work_orders/'
        if dept in _WO_DEPT_KEYS else '/dashboard/'
    )

    return render(request, 'wo_list.html', _wo_context(
        request,
        wos=wos,
        status=status,
        statuses=[(s, s.replace('_', ' ').title()) for s in WO_STATUSES],
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url=back_url,
    ))


def wo_detail(request, wo_id):
    denied = _wo_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        materials = get_wo_materials(conn, wo_id) if wo else []
        products = load_wo_products(conn) if (wo and can_edit) else []
    finally:
        conn.close()

    if not wo:
        return redirect('wo_list')

    wo['status_color'] = WO_STATUS_COLORS.get(wo['status'], '#ffffff')
    wo['status_label'] = wo['status'].replace('_', ' ').title()
    status_actions = [
        (target, WO_STATUS_ACTION_LABELS.get(target, target))
        for target in wo_allowed_transitions(wo['status'])
    ] if can_edit else []

    return render(request, 'wo_detail.html', _wo_context(
        request,
        wo=wo,
        materials=materials,
        products=products,
        can_edit=can_edit,
        status_actions=status_actions,
        back_url='/wo/',
    ))


def _wo_header_form(request):
    """Pull + validate WO header fields from POST. Returns (data, error)."""
    wo_number = (request.POST.get('wo_number') or '').strip()
    status = request.POST.get('status') or 'draft'
    try:
        quantity = int(request.POST.get('quantity') or 1)
        quantity = max(1, quantity)
    except ValueError:
        quantity = 1
    data = {
        'wo_number': wo_number,
        'product_id': _int_or_none(request.POST.get('product_id')),
        'description': (request.POST.get('description') or '').strip() or None,
        'quantity': quantity,
        'start_date': (request.POST.get('start_date') or '').strip() or None,
        'due_date': (request.POST.get('due_date') or '').strip() or None,
        'status': status if status in _WO_NEW_STATUSES else 'draft',
        'notes': (request.POST.get('notes') or '').strip() or None,
    }
    if not wo_number:
        return data, 'WO number is required.'
    return data, None


def wo_new(request):
    denied = _wo_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _wo_header_form(request)
            if not error and is_period_locked(conn, data.get('start_date')):
                error = ("Period %s is closed."
                         % period_label(*map(int,
                             data['start_date'][:7].split('-'))))
            if not error:
                try:
                    wo_id = create_wo(
                        conn, **data,
                        created_by=request.session.get('user_email'))
                    conn.commit()
                    return redirect('wo_detail', wo_id=wo_id)
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = ("WO number '%s' already exists."
                             % data['wo_number'])
            products = load_wo_products(conn)
            return render(request, 'wo_form.html', _wo_context(
                request, mode='new', error=error, form=data,
                products=products, statuses=_WO_NEW_STATUSES,
                back_url='/wo/'))

        form = {
            'wo_number': next_wo_number(conn),
            'product_id': None,
            'description': '',
            'quantity': 1,
            'start_date': date.today().isoformat(),
            'due_date': '',
            'status': 'draft',
            'notes': '',
        }
        products = load_wo_products(conn)
    finally:
        conn.close()

    return render(request, 'wo_form.html', _wo_context(
        request, mode='new', form=form, products=products,
        statuses=_WO_NEW_STATUSES, back_url='/wo/'))


def wo_edit(request, wo_id):
    denied = _wo_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        if not wo:
            return redirect('wo_list')

        if request.method == 'POST':
            try:
                quantity = int(request.POST.get('quantity') or 1)
                quantity = max(1, quantity)
            except ValueError:
                quantity = 1
            start_date = (request.POST.get('start_date') or '').strip() or None
            if is_period_locked(conn, start_date or wo.get('start_date', '')):
                lbl = period_label(*map(int,
                    (start_date or wo['start_date'])[:7].split('-')))
                products = load_wo_products(conn)
                form = {
                    'wo_number': wo['wo_number'],
                    'product_id': _int_or_none(
                        request.POST.get('product_id')),
                    'description': (
                        request.POST.get('description') or '').strip()
                        or wo.get('description') or '',
                    'quantity': quantity,
                    'start_date': start_date or wo.get('start_date') or '',
                    'due_date': (request.POST.get('due_date') or '').strip()
                                or wo.get('due_date') or '',
                    'status': wo['status'],
                    'notes': (request.POST.get('notes') or '').strip()
                             or wo.get('notes') or '',
                }
                return render(request, 'wo_form.html', _wo_context(
                    request, mode='edit', wo=wo, form=form,
                    products=products,
                    error="Period %s is closed." % lbl,
                    back_url='/wo/%s/' % wo_id))
            update_wo(
                conn, wo_id,
                product_id=_int_or_none(request.POST.get('product_id')),
                description=(request.POST.get('description') or '').strip()
                or None,
                quantity=quantity,
                start_date=start_date,
                due_date=(request.POST.get('due_date') or '').strip() or None,
                notes=(request.POST.get('notes') or '').strip() or None,
            )
            conn.commit()
            return redirect('wo_detail', wo_id=wo_id)

        products = load_wo_products(conn)
    finally:
        conn.close()

    form = {
        'wo_number': wo['wo_number'],
        'product_id': wo.get('product_id'),
        'description': wo.get('description') or '',
        'quantity': wo.get('quantity') or 1,
        'start_date': wo.get('start_date') or '',
        'due_date': wo.get('due_date') or '',
        'status': wo['status'],
        'notes': wo.get('notes') or '',
    }
    return render(request, 'wo_form.html', _wo_context(
        request, mode='edit', wo=wo, form=form, products=products,
        back_url='/wo/%s/' % wo_id))


def wo_add_material(request, wo_id):
    denied = _wo_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('wo_detail', wo_id=wo_id)

    product_id = _int_or_none(request.POST.get('product_id'))
    try:
        qty_required = int(request.POST.get('qty_required') or 1)
        qty_required = max(1, qty_required)
    except ValueError:
        qty_required = 1
    notes = (request.POST.get('notes') or '').strip() or None

    if product_id is not None:
        conn = get_db_connection()
        try:
            wo = get_wo(conn, wo_id)
            if wo:
                add_wo_material(conn, wo_id, product_id,
                                qty_required=qty_required, notes=notes)
                conn.commit()
        finally:
            conn.close()
    return redirect('wo_detail', wo_id=wo_id)


def wo_set_status(request, wo_id):
    denied = _wo_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('wo_detail', wo_id=wo_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        if wo and wo_can_transition(wo['status'], target):
            set_wo_status(conn, wo_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('wo_detail', wo_id=wo_id)


# ---------------------------------------------------------------------------
# Sales orders (web)
# ---------------------------------------------------------------------------

_SO_NEW_STATUSES = ('draft', 'confirmed')


def _so_access(request, write=False):
    """Gate SO pages: logged in, and either full access or Sales dept.

    With ``write=True`` also blocks ``READ_ONLY_ROLES`` from mutating.
    Returns a redirect or None if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'sales':
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('so_list')
    return None


def _so_context(request, **extra):
    """Toolbar context shared by the SO templates."""
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def _so_customer_name(so):
    return (
        so.get('company_name')
        or f"{so.get('first_name') or ''} {so.get('last_name') or ''}".strip()
        or '—'
    )


def so_list(request):
    denied = _so_access(request)
    if denied:
        return denied

    status = request.GET.get('status') or None
    if status not in SO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        sos = list_sos(conn, status=status)
    finally:
        conn.close()

    for so in sos:
        so['status_color'] = SO_STATUS_COLORS.get(so['status'], '#ffffff')
        so['customer_name'] = _so_customer_name(so)

    return render(request, 'so_list.html', _so_context(
        request,
        sos=sos,
        status=status,
        statuses=SO_STATUSES,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/sales/sales/sales_orders/',
    ))


def so_detail(request, so_id):
    denied = _so_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        items = get_so_items(conn, so_id) if so else []
        products = load_so_products(conn) if (so and can_edit) else []
    finally:
        conn.close()

    if not so:
        return redirect('so_list')

    so['status_color'] = SO_STATUS_COLORS.get(so['status'], '#ffffff')
    so['customer_name'] = _so_customer_name(so)

    status_actions = [
        (target, SO_STATUS_ACTION_LABELS.get(target, target))
        for target in so_allowed_transitions(so['status'])
    ] if can_edit else []

    return render(request, 'so_detail.html', _so_context(
        request,
        so=so,
        items=items,
        products=products,
        can_edit=can_edit,
        status_actions=status_actions,
        back_url='/so/',
    ))


def _so_header_form(request):
    """Pull + validate SO header fields from POST. Returns (data, error)."""
    so_number = (request.POST.get('so_number') or '').strip()
    status = request.POST.get('status') or 'draft'
    data = {
        'so_number': so_number,
        'customer_id': _int_or_none(request.POST.get('customer_id')),
        'order_date': (request.POST.get('order_date') or '').strip() or None,
        'ship_date': (request.POST.get('ship_date') or '').strip() or None,
        'status': status if status in _SO_NEW_STATUSES else 'draft',
        'notes': (request.POST.get('notes') or '').strip() or None,
    }
    if not so_number:
        return data, 'SO number is required.'
    return data, None


def so_new(request):
    denied = _so_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _so_header_form(request)
            if not error and is_period_locked(conn, data.get('order_date')):
                error = ("Period %s is closed."
                         % period_label(*map(int,
                             data['order_date'][:7].split('-'))))
            if not error:
                try:
                    so_id = create_so(
                        conn, **data,
                        created_by=request.session.get('user_email'))
                    conn.commit()
                    return redirect('so_detail', so_id=so_id)
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = ("SO number '%s' already exists."
                             % data['so_number'])
            customers = load_customers(conn)
            return render(request, 'so_form.html', _so_context(
                request, mode='new', error=error, form=data,
                customers=customers, statuses=_SO_NEW_STATUSES,
                back_url='/so/'))

        form = {
            'so_number': next_so_number(conn),
            'customer_id': None,
            'order_date': date.today().isoformat(),
            'ship_date': '',
            'status': 'draft',
            'notes': '',
        }
        customers = load_customers(conn)
    finally:
        conn.close()

    return render(request, 'so_form.html', _so_context(
        request, mode='new', form=form, customers=customers,
        statuses=_SO_NEW_STATUSES, back_url='/so/'))


def so_edit(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if not so:
            return redirect('so_list')

        if request.method == 'POST':
            order_date = (request.POST.get('order_date') or '').strip() or None
            if is_period_locked(conn, order_date or so.get('order_date', '')):
                lbl = period_label(*map(int,
                    (order_date or so['order_date'])[:7].split('-')))
                customers = load_customers(conn)
                form = {
                    'so_number': so['so_number'],
                    'customer_id': _int_or_none(
                        request.POST.get('customer_id')),
                    'order_date': order_date or so['order_date'] or '',
                    'ship_date': (
                        request.POST.get('ship_date') or '').strip()
                        or so.get('ship_date') or '',
                    'status': so['status'],
                    'notes': (request.POST.get('notes') or '').strip()
                             or so.get('notes') or '',
                }
                return render(request, 'so_form.html', _so_context(
                    request, mode='edit', so=so, form=form,
                    customers=customers,
                    error="Period %s is closed." % lbl,
                    back_url='/so/%s/' % so_id))
            update_so(
                conn, so_id,
                customer_id=_int_or_none(request.POST.get('customer_id')),
                order_date=order_date,
                ship_date=(request.POST.get('ship_date') or '').strip()
                or None,
                notes=(request.POST.get('notes') or '').strip() or None,
            )
            conn.commit()
            return redirect('so_detail', so_id=so_id)

        customers = load_customers(conn)
    finally:
        conn.close()

    form = {
        'so_number': so['so_number'],
        'customer_id': so['customer_id'],
        'order_date': so['order_date'] or '',
        'ship_date': so['ship_date'] or '',
        'status': so['status'],
        'notes': so['notes'] or '',
    }
    return render(request, 'so_form.html', _so_context(
        request, mode='edit', so=so, form=form, customers=customers,
        back_url='/so/%s/' % so_id))


def so_add_item(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('so_detail', so_id=so_id)

    description = (request.POST.get('description') or '').strip()
    product_id = _int_or_none(request.POST.get('product_id'))
    try:
        qty = int(request.POST.get('qty') or 1)
        qty = max(1, qty)
    except ValueError:
        qty = 1
    try:
        unit_price = float(request.POST.get('unit_price') or 0)
    except ValueError:
        unit_price = 0.0

    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if so and description and qty >= 1 and unit_price >= 0:
            add_so_item(conn, so_id, description, product_id=product_id,
                        qty=qty, unit_price=unit_price)
            conn.commit()
    finally:
        conn.close()
    return redirect('so_detail', so_id=so_id)


def so_remove_item(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        if item_id:
            conn = get_db_connection()
            try:
                delete_so_item(conn, item_id, so_id=so_id)
                conn.commit()
            finally:
                conn.close()
    return redirect('so_detail', so_id=so_id)


def so_set_status(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('so_detail', so_id=so_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if so and so_can_transition(so['status'], target):
            set_so_status(conn, so_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('so_detail', so_id=so_id)


# ---------------------------------------------------------------------------
# Personnel — employee directory + time-off requests (web)
# ---------------------------------------------------------------------------

_PERSONNEL_ROLES = {'HR / Personnel'}


def _people_access(request, write=False):
    """Gate personnel pages: logged in + full_access, HR/Personnel role, or
    personnel dept. With write=True also blocks READ_ONLY_ROLES.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        role = request.session.get('user_role', '')
        dept = request.session.get('user_dept_key', '')
        if role not in _PERSONNEL_ROLES and dept != 'personnel':
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('people_list')
    return None


def _people_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def _is_hr(request):
    """True if the user has personnel/HR access (can approve time-off etc.)."""
    return (
        request.session.get('user_full_access')
        or request.session.get('user_role') in _PERSONNEL_ROLES
        or request.session.get('user_dept_key') == 'personnel'
    )


def people_list(request):
    denied = _people_access(request)
    if denied:
        return denied

    dept_id = _int_or_none(request.GET.get('dept_id'))
    search = (request.GET.get('search') or '').strip() or None

    conn = get_db_connection()
    try:
        people = list_people(conn, dept_id=dept_id, search=search)
        depts = load_depts(conn)
    finally:
        conn.close()

    return render(request, 'people_list.html', _people_context(
        request,
        people=people,
        depts=depts,
        dept_id=dept_id,
        search=search or '',
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/personnel/pers_menu/emp_records/',
    ))


def people_detail(request, person_id):
    denied = _people_access(request)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        person = get_person(conn, person_id)
    finally:
        conn.close()

    if not person:
        return redirect('people_list')

    return render(request, 'people_detail.html', _people_context(
        request,
        person=person,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/people/',
    ))


def _people_form(request):
    """Pull + validate person fields from POST. Returns (data, error)."""
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    if not first_name or not last_name:
        data = {k: (request.POST.get(k) or '') for k in [
            'first_name', 'last_name', 'employee_id', 'email',
            'job_title', 'address', 'city', 'state', 'zip_code']}
        data['dept_id'] = _int_or_none(request.POST.get('dept_id'))
        data['dept_sub_id'] = _int_or_none(request.POST.get('dept_sub_id'))
        return data, 'First name and last name are required.'
    return {
        'first_name': first_name,
        'last_name': last_name,
        'employee_id': _int_or_none(request.POST.get('employee_id')) or 0,
        'email': (request.POST.get('email') or '').strip(),
        'job_title': (request.POST.get('job_title') or '').strip(),
        'address': (request.POST.get('address') or '').strip(),
        'city': (request.POST.get('city') or '').strip(),
        'state': (request.POST.get('state') or '').strip(),
        'zip_code': (request.POST.get('zip_code') or '').strip(),
        'dept_id': _int_or_none(request.POST.get('dept_id')),
        'dept_sub_id': _int_or_none(request.POST.get('dept_sub_id')),
    }, None


def people_new(request):
    denied = _people_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _people_form(request)
            if not error:
                person_id = create_person(
                    conn, **data,
                    created_by=request.session.get('user_email'))
                conn.commit()
                return redirect('people_detail', person_id=person_id)
            depts = load_depts(conn)
            dept_subs = load_dept_subs(conn)
            return render(request, 'people_form.html', _people_context(
                request, mode='new', error=error, form=data,
                depts=depts, dept_subs=dept_subs, back_url='/people/'))

        depts = load_depts(conn)
        dept_subs = load_dept_subs(conn)
    finally:
        conn.close()

    form = {
        'first_name': '', 'last_name': '', 'employee_id': '', 'email': '',
        'job_title': '', 'address': '', 'city': '', 'state': '',
        'zip_code': '', 'dept_id': None, 'dept_sub_id': None,
    }
    return render(request, 'people_form.html', _people_context(
        request, mode='new', form=form, depts=depts, dept_subs=dept_subs,
        back_url='/people/'))


def people_edit(request, person_id):
    denied = _people_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        person = get_person(conn, person_id)
        if not person:
            return redirect('people_list')

        if request.method == 'POST':
            data, error = _people_form(request)
            if not error:
                update_person(conn, person_id, **data)
                conn.commit()
                return redirect('people_detail', person_id=person_id)
            depts = load_depts(conn)
            dept_subs = load_dept_subs(conn)
            return render(request, 'people_form.html', _people_context(
                request, mode='edit', person=person, error=error, form=data,
                depts=depts, dept_subs=dept_subs,
                back_url='/people/%s/' % person_id))

        depts = load_depts(conn)
        dept_subs = load_dept_subs(conn)
    finally:
        conn.close()

    form = {
        'first_name': person['first_name'],
        'last_name': person['last_name'],
        'employee_id': person['employee_id'] or '',
        'email': person['email'] or '',
        'job_title': person['job_title'] or '',
        'address': person['address'] or '',
        'city': person['city'] or '',
        'state': person['state'] or '',
        'zip_code': person['zip_code'] or '',
        'dept_id': person['dept_id'],
        'dept_sub_id': person['dept_sub_id'],
    }
    return render(request, 'people_form.html', _people_context(
        request, mode='edit', person=person, form=form,
        depts=depts, dept_subs=dept_subs,
        back_url='/people/%s/' % person_id))


# --- Time-off requests ---

def time_off_list(request):
    if not request.session.get('user_email'):
        return redirect('home')

    status = request.GET.get('status') or None
    if status not in TIME_OFF_STATUSES:
        status = None

    is_hr_user = _is_hr(request)
    email = request.session.get('user_email', '')

    conn = get_db_connection()
    try:
        people_id = None
        if not is_hr_user:
            p = get_person_by_email(conn, email)
            people_id = p['id'] if p else -1
        requests = list_time_off_requests(conn, people_id=people_id,
                                          status=status)
    finally:
        conn.close()

    back_url = (
        '/dept/personnel/pers_menu/time_clock/time_off/'
        if request.session.get('user_dept_key') == 'personnel'
        else '/dashboard/'
    )
    return render(request, 'time_off_list.html', _people_context(
        request,
        requests=requests,
        status=status,
        statuses=TIME_OFF_STATUSES,
        is_hr=is_hr_user,
        back_url=back_url,
    ))


def time_off_new(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('time_off_list')

    email = request.session.get('user_email', '')

    if request.method == 'POST':
        start_date = (request.POST.get('start_date') or '').strip()
        end_date = (request.POST.get('end_date') or '').strip()
        request_type = request.POST.get('request_type') or 'Vacation'
        if request_type not in TIME_OFF_TYPES:
            request_type = 'Vacation'
        notes = (request.POST.get('notes') or '').strip() or None
        error = None
        if not start_date or not end_date:
            error = 'Start date and end date are required.'
        elif end_date < start_date:
            error = 'End date must be on or after start date.'
        if not error:
            conn = get_db_connection()
            try:
                p = get_person_by_email(conn, email)
                if not p:
                    error = 'Your employee record was not found.'
                else:
                    create_time_off_request(
                        conn, p['id'], start_date, end_date,
                        request_type=request_type, notes=notes,
                        created_by=email)
                    conn.commit()
                    return redirect('time_off_list')
            finally:
                conn.close()
        return render(request, 'time_off_form.html', _people_context(
            request, error=error,
            form={'start_date': start_date, 'end_date': end_date,
                  'request_type': request_type, 'notes': notes or ''},
            types=TIME_OFF_TYPES, back_url='/time-off/'))

    form = {
        'start_date': date.today().isoformat(),
        'end_date': '',
        'request_type': 'Vacation',
        'notes': '',
    }
    return render(request, 'time_off_form.html', _people_context(
        request, form=form, types=TIME_OFF_TYPES, back_url='/time-off/'))


def time_off_detail(request, req_id):
    if not request.session.get('user_email'):
        return redirect('home')

    is_hr_user = _is_hr(request)
    email = request.session.get('user_email', '')

    conn = get_db_connection()
    try:
        req = get_time_off_request(conn, req_id)
        if not req:
            return redirect('time_off_list')

        # Non-HR users may only view their own requests.
        if not is_hr_user:
            p = get_person_by_email(conn, email)
            if not p or p['id'] != req['people_id']:
                return redirect('time_off_list')

        if request.method == 'POST' and is_hr_user:
            new_status = request.POST.get('status')
            if new_status in TIME_OFF_STATUSES and new_status != 'pending':
                set_time_off_status(conn, req_id, new_status)
                conn.commit()
                return redirect('time_off_detail', req_id=req_id)
    finally:
        conn.close()

    return render(request, 'time_off_detail.html', _people_context(
        request,
        req=req,
        is_hr=is_hr_user,
        can_act=is_hr_user and req['status'] == 'pending',
        back_url='/time-off/',
    ))


# ---------------------------------------------------------------------------
# Time clock — punch in/out, hours, attendance (web)
# ---------------------------------------------------------------------------

_TC_BACK = '/dept/personnel/pers_menu/time_clock/'


def _tc_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def time_clock_status(request):
    """Punch in / punch out page and current status."""
    if not request.session.get('user_email'):
        return redirect('home')
    email = request.session.get('user_email', '')

    conn = get_db_connection()
    try:
        person = get_person_by_email(conn, email)
        if not person:
            return render(request, 'time_clock_status.html', _tc_context(
                request, error='Your employee record was not found.',
                current=None, today_entries=[], back_url=_TC_BACK))

        people_id = person['id']

        if request.method == 'POST':
            action = request.POST.get('action')
            current = get_current_entry(conn, people_id)
            if action == 'clock_in' and not current:
                tc_clock_in(conn, people_id, created_by=email)
                conn.commit()
            elif action == 'clock_out' and current:
                clock_out_entry(conn, current['id'])
                conn.commit()
            return redirect('time_clock_status')

        current = get_current_entry(conn, people_id)
        today = __import__('datetime').date.today().isoformat()
        today_entries = list_entries(conn, people_id,
                                     date_from=today, date_to=today)
        _, total_fmt = tc_total_hours(today_entries)
    finally:
        conn.close()

    return render(request, 'time_clock_status.html', _tc_context(
        request,
        current=current,
        today_entries=today_entries,
        total_fmt=total_fmt,
        back_url=_TC_BACK,
    ))


def time_clock_hours(request):
    """View personal hours for today / this week / this month."""
    if not request.session.get('user_email'):
        return redirect('home')
    email = request.session.get('user_email', '')

    period = request.GET.get('period', 'today')
    if period not in ('today', 'week', 'month'):
        period = 'today'
    date_from, date_to = get_period_dates(period)

    conn = get_db_connection()
    try:
        person = get_person_by_email(conn, email)
        if not person:
            return render(request, 'time_clock_hours.html', _tc_context(
                request, error='Your employee record was not found.',
                entries=[], period=period, total_fmt='0:00',
                back_url=_TC_BACK))
        entries = list_entries(conn, person['id'],
                               date_from=date_from, date_to=date_to)
        _, total_fmt = tc_total_hours(entries)
    finally:
        conn.close()

    return render(request, 'time_clock_hours.html', _tc_context(
        request,
        entries=entries,
        period=period,
        date_from=date_from,
        date_to=date_to,
        total_fmt=total_fmt,
        back_url=_TC_BACK,
    ))


def time_clock_attendance(request):
    """HR attendance view — all employees for a given date."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_hr(request):
        return redirect('time_clock_status')

    date_str = (request.GET.get('date') or '').strip()
    if not date_str:
        date_str = __import__('datetime').date.today().isoformat()

    conn = get_db_connection()
    try:
        attendance = get_attendance(conn, date_str)
    finally:
        conn.close()

    present = sum(1 for p in attendance if p['present'])
    absent = len(attendance) - present

    return render(request, 'time_clock_attendance.html', _tc_context(
        request,
        attendance=attendance,
        date_str=date_str,
        present=present,
        absent=absent,
        back_url=_TC_BACK,
    ))


# ── Time Clock Device Management ──────────────────────────────────────────

_DEV_BACK = '/time-clock/devices/'


def _dev_access(request):
    """Return True if the logged-in user can manage time clock devices."""
    return _is_hr(request)


def tc_device_list(request):
    """List all registered time clock terminals."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request):
        return redirect('time_clock_status')

    conn = get_db_connection()
    try:
        devices = list_devices(conn)
    finally:
        conn.close()

    return render(request, 'tc_device_list.html', _tc_context(
        request,
        devices=devices,
        device_type_labels=DEVICE_TYPE_LABELS,
        back_url='/time-clock/',
    ))


def tc_device_new(request):
    """Add a new time clock device — asks for type, then shows config fields."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request):
        return redirect('time_clock_status')

    error = ''
    form: dict = {
        'name': '', 'location': '', 'device_type': '',
        'ip_address': '', 'port': '', 'config_json': '{}',
    }

    if request.method == 'POST':
        form = {
            'name': request.POST.get('name', '').strip(),
            'location': request.POST.get('location', '').strip(),
            'device_type': request.POST.get('device_type', '').strip(),
            'ip_address': request.POST.get('ip_address', '').strip(),
            'port': request.POST.get('port', '').strip(),
            'config_json': request.POST.get('config_json', '{}').strip(),
        }
        if not form['name']:
            error = 'Name is required.'
        elif form['device_type'] not in DEVICE_TYPES:
            error = 'Please select a valid device type.'
        else:
            try:
                port = int(form['port']) if form['port'] else 0
            except ValueError:
                port = 0
            conn = get_db_connection()
            try:
                create_device(
                    conn,
                    name=form['name'],
                    location=form['location'],
                    device_type=form['device_type'],
                    ip_address=form['ip_address'],
                    port=port,
                    config_json=form['config_json'] or '{}',
                    created_by=request.session.get('user_email'),
                )
                conn.commit()
            finally:
                conn.close()
            return redirect('tc_device_list')

    return render(request, 'tc_device_form.html', _tc_context(
        request,
        form=form,
        error=error,
        device_types=DEVICE_TYPES,
        device_type_labels=DEVICE_TYPE_LABELS,
        is_new=True,
        back_url=_DEV_BACK,
    ))


def tc_device_detail(request, device_id: int):
    """Edit a device or view its sync log."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request):
        return redirect('time_clock_status')

    conn = get_db_connection()
    try:
        device = get_device(conn, device_id)
        if not device:
            return redirect('tc_device_list')

        error = ''
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            location = request.POST.get('location', '').strip()
            device_type = request.POST.get('device_type', '').strip()
            ip_address = request.POST.get('ip_address', '').strip()
            port_str = request.POST.get('port', '').strip()
            config_json = request.POST.get('config_json', '{}').strip()
            enabled = request.POST.get('enabled') == 'on'

            if not name:
                error = 'Name is required.'
            elif device_type not in DEVICE_TYPES:
                error = 'Please select a valid device type.'
            else:
                try:
                    port = int(port_str) if port_str else 0
                except ValueError:
                    port = 0
                update_device(conn, device_id,
                              name=name, location=location,
                              device_type=device_type,
                              ip_address=ip_address, port=port,
                              config_json=config_json or '{}',
                              enabled=enabled)
                conn.commit()
                return redirect('tc_device_detail', device_id=device_id)

            device = get_device(conn, device_id)

        sync_log = list_sync_log(conn, device_id=device_id, limit=20)
    finally:
        conn.close()

    return render(request, 'tc_device_form.html', _tc_context(
        request,
        form=device,
        error=error,
        device_types=DEVICE_TYPES,
        device_type_labels=DEVICE_TYPE_LABELS,
        is_new=False,
        device_id=device_id,
        sync_log=sync_log,
        back_url=_DEV_BACK,
    ))


def tc_device_poll(request, device_id: int):
    """Trigger an immediate poll of a device."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request) or request.method != 'POST':
        return redirect('tc_device_list')

    conn = get_db_connection()
    try:
        result = poll_device(conn, device_id)
        conn.commit()
    finally:
        conn.close()

    return redirect('tc_device_detail', device_id=device_id)


def tc_device_delete(request, device_id: int):
    """Delete a device and its sync log."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request) or request.method != 'POST':
        return redirect('tc_device_list')

    conn = get_db_connection()
    try:
        delete_device(conn, device_id)
        conn.commit()
    finally:
        conn.close()

    return redirect('tc_device_list')


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

_AUDIT_ROLES = FULL_ACCESS_ROLES | {'Auditor'}


def _audit_access(request):
    return request.session.get('user_role') in _AUDIT_ROLES


def audit_log(request):
    """Recent audit log entries, filterable by table and user."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _audit_access(request):
        return redirect('dashboard')

    table_filter = request.GET.get('table', '')
    user_filter = request.GET.get('user', '')
    entries = get_recent(
        limit=200,
        table_name=table_filter or None,
        changed_by=user_filter or None,
    )
    return render(request, 'audit_log.html', {
        'entries': entries,
        'audited_tables': sorted(AUDITED_TABLES),
        'table_filter': table_filter,
        'user_filter': user_filter,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


def audit_record(request, table_name: str, record_id: int):
    """Full history for a single record."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _audit_access(request):
        return redirect('dashboard')

    history = get_history(table_name, record_id)
    return render(request, 'audit_record.html', {
        'table_name': table_name,
        'record_id': record_id,
        'history': history,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


# ---------------------------------------------------------------------------
# Period locking management
# ---------------------------------------------------------------------------

def _periods_access(request, *, write: bool = False):
    """Return a redirect if the user may not access the periods page."""
    if not request.session.get('user_email'):
        return redirect('home')
    role = request.session.get('user_role', '')
    if write and role not in PERIOD_ADMIN_ROLES:
        return redirect('periods')
    if not write and role not in PERIOD_ADMIN_ROLES:
        return redirect('dashboard')
    return None


def periods(request):
    """List closed periods and show close/reopen controls."""
    denied = _periods_access(request)
    if denied:
        return denied

    error = None
    if request.method == 'POST':
        action = request.POST.get('action', '')
        conn = get_db_connection()
        try:
            if action == 'close':
                try:
                    year = int(request.POST.get('year', 0))
                    month = int(request.POST.get('month', 0))
                    notes = (request.POST.get('notes') or '').strip()
                    close_period(
                        conn, year, month,
                        closed_by=request.session.get('user_email', ''),
                        notes=notes,
                    )
                    conn.commit()
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
            elif action == 'reopen':
                try:
                    period_id = int(request.POST.get('period_id', 0))
                    reopen_period(
                        conn, period_id,
                        reopened_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
        finally:
            conn.close()
        if not error:
            return redirect('periods')

    closed = list_periods(limit=36)
    closed_keys = {(p['period_year'], p['period_month']): p
                   for p in closed}
    months = recent_months(13)
    calendar = []
    for year, month in months:
        entry = closed_keys.get((year, month))
        calendar.append({
            'year': year,
            'month': month,
            'label': period_label(year, month),
            'closed': entry is not None,
            'period_id': entry['id'] if entry else None,
            'closed_by': entry['closed_by'] if entry else '',
            'closed_at': entry['closed_at'] if entry else None,
            'notes': entry['notes'] if entry else '',
        })

    return render(request, 'periods.html', {
        'calendar': calendar,
        'error': error,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_write': request.session.get('user_role', '') in PERIOD_ADMIN_ROLES,
    })


# ---------------------------------------------------------------------------
# PO approval workflow
# ---------------------------------------------------------------------------

def _approval_access(request):
    """Redirect if the user is not authorised to approve/reject POs."""
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') not in APPROVAL_ROLES:
        return redirect('dashboard')
    return None


def po_approvals(request):
    """Queue of POs waiting for approval (President / VP only)."""
    denied = _approval_access(request)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        pending = get_pending_approvals(conn)
    finally:
        conn.close()

    return render(request, 'po_approvals.html', {
        'pending': pending,
        'threshold': APPROVAL_THRESHOLD,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


def po_approve(request, approval_id):
    """Approve a pending PO."""
    denied = _approval_access(request)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_approvals')

    notes = (request.POST.get('notes') or '').strip()
    conn = get_db_connection()
    try:
        approve_po(conn, approval_id,
                   decided_by=request.session.get('user_email', ''),
                   notes=notes)
        conn.commit()
    except ValueError:
        conn.rollback()
    finally:
        conn.close()
    return redirect('po_approvals')


def po_reject(request, approval_id):
    """Reject a pending PO, returning it to draft."""
    denied = _approval_access(request)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_approvals')

    notes = (request.POST.get('notes') or '').strip()
    conn = get_db_connection()
    try:
        reject_po(conn, approval_id,
                  decided_by=request.session.get('user_email', ''),
                  notes=notes)
        conn.commit()
    except ValueError:
        conn.rollback()
    finally:
        conn.close()
    return redirect('po_approvals')


# ---------------------------------------------------------------------------
# Bill of Materials (web)
# ---------------------------------------------------------------------------

_BOM_DEPT_KEYS = {'engineering', 'production'}


def _bom_access(request, write=False):
    """Gate BOM pages: logged in + full_access or engineering/production dept.

    With ``write=True`` also blocks READ_ONLY_ROLES from mutating.
    Returns a redirect or None if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _BOM_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('bom_list')
    return None


def _bom_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def bom_list(request):
    denied = _bom_access(request)
    if denied:
        return denied

    item_type = request.GET.get('item_type') or None
    if item_type not in ITEM_TYPES:
        item_type = None

    conn = get_db_connection()
    try:
        products = list_products(conn, item_type=item_type)
    finally:
        conn.close()

    dept = request.session.get('user_dept_key', 'engineering')
    back_url = (
        f'/dept/{dept}/eng_menu/bom/'
        if dept in _BOM_DEPT_KEYS else '/dashboard/'
    )

    return render(request, 'bom_list.html', _bom_context(
        request,
        products=products,
        item_type=item_type,
        item_types=ITEM_TYPES,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url=back_url,
    ))


def bom_detail(request, product_id):
    denied = _bom_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        product = get_product(conn, product_id)
        if not product:
            return redirect('bom_list')

        error = None
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')

            if action == 'update_item_master':
                update_item_master(
                    conn, product_id,
                    item_type=request.POST.get('item_type', 'buy'),
                    lead_time_days=_int_or_none(
                        request.POST.get('lead_time_days')) or 0,
                    uom=(request.POST.get('uom') or 'ea').strip() or 'ea',
                )
                conn.commit()
                return redirect('bom_detail', product_id=product_id)

            elif action == 'add_line':
                component_id = _int_or_none(request.POST.get('component_id'))
                try:
                    qty = float(request.POST.get('qty_required') or 1.0)
                    qty = max(0.0, qty)
                except ValueError:
                    qty = 1.0
                try:
                    scrap_pct = float(request.POST.get('scrap_pct') or 0.0)
                    scrap_pct = max(0.0, scrap_pct)
                except ValueError:
                    scrap_pct = 0.0
                unit = (request.POST.get('unit') or 'ea').strip() or 'ea'
                notes = (request.POST.get('notes') or '').strip()
                if component_id is None:
                    error = 'Please select a component.'
                else:
                    ok, msg = add_bom_line(
                        conn, product_id, component_id,
                        qty_required=qty, unit=unit,
                        notes=notes, scrap_pct=scrap_pct,
                    )
                    if ok:
                        conn.commit()
                        return redirect('bom_detail', product_id=product_id)
                    error = msg

            elif action == 'update_line':
                line_id = _int_or_none(request.POST.get('line_id'))
                try:
                    qty = float(request.POST.get('qty_required') or 1.0)
                    qty = max(0.0, qty)
                except ValueError:
                    qty = 1.0
                try:
                    scrap_pct = float(request.POST.get('scrap_pct') or 0.0)
                    scrap_pct = max(0.0, scrap_pct)
                except ValueError:
                    scrap_pct = 0.0
                unit = (request.POST.get('unit') or 'ea').strip() or 'ea'
                notes = (request.POST.get('notes') or '').strip()
                if line_id is not None:
                    update_bom_line(conn, line_id, qty_required=qty,
                                    unit=unit, notes=notes, scrap_pct=scrap_pct)
                    conn.commit()
                return redirect('bom_detail', product_id=product_id)

            elif action == 'delete_line':
                line_id = _int_or_none(request.POST.get('line_id'))
                if line_id is not None:
                    delete_bom_line(conn, line_id)
                    conn.commit()
                return redirect('bom_detail', product_id=product_id)

        lines = get_bom(conn, product_id)
        all_products = list_products(conn)
        used_ids = {line['component_id'] for line in lines} | {product_id}
        available_components = [p for p in all_products if p['id'] not in used_ids]
    finally:
        conn.close()

    return render(request, 'bom_detail.html', _bom_context(
        request,
        product=product,
        lines=lines,
        available_components=available_components,
        item_types=ITEM_TYPES,
        can_edit=can_edit,
        error=error,
        back_url='/bom/',
    ))


def bom_explode(request, product_id):
    denied = _bom_access(request)
    if denied:
        return denied

    try:
        qty = float(request.GET.get('qty') or 1.0)
        qty = max(0.0, qty)
    except ValueError:
        qty = 1.0

    conn = get_db_connection()
    try:
        product = get_product(conn, product_id)
        if not product:
            return redirect('bom_list')
        explosion = explode_bom(conn, product_id, qty=qty)
    finally:
        conn.close()

    return render(request, 'bom_explode.html', _bom_context(
        request,
        product=product,
        explosion=explosion,
        qty=qty,
        back_url=f'/bom/{product_id}/',
    ))


# ---------------------------------------------------------------------------
# Material Requirements Planning (web)
# ---------------------------------------------------------------------------

_MRP_DEPT_KEYS = {'production', 'engineering'}


def _mrp_access(request, write=False):
    """Gate MRP pages: logged-in + full_access or production/engineering dept."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _MRP_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('mrp_home')
    return None


def _mrp_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def mrp_home(request):
    denied = _mrp_access(request)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        demand_rows = get_demand_details(conn)
        scheduled = get_scheduled_receipts_detail(conn)
    finally:
        conn.close()

    # Annotate each demand row with scheduled receipts and net requirement.
    for row in demand_rows:
        row['scheduled'] = scheduled.get(row['id'], 0.0)
        row['net'] = max(0.0, row['demand_qty'] - row['on_hand'] - row['scheduled'])

    has_plan = 'mrp_plan' in request.session and bool(request.session['mrp_plan'])
    return render(request, 'mrp_home.html', _mrp_context(
        request,
        demand_rows=demand_rows,
        has_plan=has_plan,
    ))


def mrp_run(request):
    denied = _mrp_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('mrp_home')

    conn = get_db_connection()
    try:
        plan = run_mrp(conn)
    finally:
        conn.close()

    request.session['mrp_plan'] = plan
    return redirect('mrp_plan')


def mrp_plan(request):
    denied = _mrp_access(request)
    if denied:
        return denied

    plan = request.session.get('mrp_plan') or []
    if not plan:
        return redirect('mrp_home')

    make_count = sum(1 for p in plan if p['order_type'] == 'make')
    buy_count = sum(1 for p in plan if p['order_type'] == 'buy')

    return render(request, 'mrp_plan.html', _mrp_context(
        request,
        plan=enumerate(plan),
        plan_list=plan,
        make_count=make_count,
        buy_count=buy_count,
    ))


def mrp_release(request):
    denied = _mrp_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('mrp_plan')

    plan = request.session.get('mrp_plan') or []
    if not plan:
        return redirect('mrp_home')

    selected = request.POST.getlist('select')
    selected_indices = set()
    for v in selected:
        try:
            selected_indices.add(int(v))
        except ValueError:
            pass

    # Apply qty overrides from form
    items_to_release = []
    for i, item in enumerate(plan):
        if i not in selected_indices:
            continue
        override = request.POST.get(f'qty_{i}', '').strip()
        try:
            qty = float(override)
            if qty <= 0:
                qty = item['qty']
        except (ValueError, TypeError):
            qty = item['qty']
        items_to_release.append({**item, 'qty': qty})

    if not items_to_release:
        return redirect('mrp_plan')

    released_by = request.session.get('user_email', '')
    conn = get_db_connection()
    try:
        created_wos, created_pos = mrp_release_plan(conn, items_to_release, released_by)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Clear plan from session after release
    request.session.pop('mrp_plan', None)

    return render(request, 'mrp_release.html', _mrp_context(
        request,
        created_wos=created_wos,
        created_pos=created_pos,
    ))


# ---------------------------------------------------------------------------
# Inventory (web)
# ---------------------------------------------------------------------------

_INV_DEPT_KEYS = {'production', 'engineering', 'maintenance', 'purchasing'}


def _inv_access(request, write=False):
    """Gate inventory pages: logged-in + full_access or relevant dept."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _INV_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('inventory_list')
    return None


def _inv_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'trans_types': TRANS_TYPES,
    }
    ctx.update(extra)
    return ctx


def inventory_list(request):
    denied = _inv_access(request)
    if denied:
        return denied

    search = request.GET.get('search', '').strip()
    filter_status = request.GET.get('filter') or None
    if filter_status not in ('low', 'zero'):
        filter_status = None
    item_type = request.GET.get('item_type') or None
    if item_type not in ('make', 'buy'):
        item_type = None

    conn = get_db_connection()
    try:
        products = inv_list_products(conn, search=search,
                                     filter_status=filter_status,
                                     item_type=item_type)
        alerts = get_alert_counts(conn)
    finally:
        conn.close()

    return render(request, 'inventory_list.html', _inv_context(
        request,
        products=products,
        search=search,
        filter_status=filter_status,
        item_type=item_type,
        alert_zero=alerts['zero_count'],
        alert_low=alerts['low_count'],
    ))


def inventory_new(request):
    denied = _inv_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    error = None
    try:
        suppliers = inv_load_suppliers(conn)
        if request.method == 'POST':
            try:
                product_id = inv_create_product(
                    conn,
                    name=request.POST.get('name', ''),
                    supplier_id=_int_or_none(request.POST.get('supplier_id')),
                    bin_loc=request.POST.get('bin_loc', ''),
                    amount=float(request.POST.get('amount') or 0),
                    reorder_point=float(request.POST.get('reorder_point') or 0),
                    purchase_price=float(request.POST.get('purchase_price') or 0),
                    item_type=request.POST.get('item_type', 'buy'),
                    lead_time_days=int(request.POST.get('lead_time_days') or 0),
                    uom=request.POST.get('uom', 'ea'),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('inventory_detail', product_id=product_id)
            except (ValueError, Exception) as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    return render(request, 'inventory_new.html', _inv_context(
        request,
        suppliers=suppliers,
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


def inventory_detail(request, product_id):
    denied = _inv_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')

        suppliers = inv_load_suppliers(conn) if can_edit else []

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')

            if action == 'update':
                try:
                    inv_update_product(
                        conn, product_id,
                        name=request.POST.get('name', ''),
                        supplier_id=_int_or_none(request.POST.get('supplier_id')),
                        bin_loc=request.POST.get('bin_loc', ''),
                        reorder_point=float(request.POST.get('reorder_point') or 0),
                        purchase_price=float(request.POST.get('purchase_price') or 0),
                        item_type=request.POST.get('item_type', 'buy'),
                        lead_time_days=int(request.POST.get('lead_time_days') or 0),
                        uom=request.POST.get('uom', 'ea'),
                    )
                    conn.commit()
                    product = inv_get_product(conn, product_id)
                    success = 'Product updated.'
                except (ValueError, Exception) as e:
                    conn.rollback()
                    error = str(e)

        transactions = get_transactions(conn, product_id)
    finally:
        conn.close()

    amt = product['amount']
    rop = product['reorder_point']
    if amt <= 0:
        stock_status = 'zero'
    elif rop > 0 and amt <= rop:
        stock_status = 'low'
    else:
        stock_status = 'ok'

    return render(request, 'inventory_detail.html', _inv_context(
        request,
        product=product,
        suppliers=suppliers,
        transactions=transactions,
        stock_status=stock_status,
        error=error,
        success=success,
        can_edit=can_edit,
        back_url='/inventory/',
    ))


def inventory_transaction(request, product_id):
    """POST only — record a stock movement for a product."""
    denied = _inv_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('inventory_detail', product_id=product_id)

    conn = get_db_connection()
    try:
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')

        trans_type = request.POST.get('trans_type', '')
        qty_raw = request.POST.get('quantity', '').strip()
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = 0.0

        if trans_type in TRANS_TYPES and qty != 0:
            record_transaction(
                conn, product_id,
                trans_type=trans_type,
                quantity=qty,
                reference=request.POST.get('reference', '').strip(),
                notes=request.POST.get('notes', '').strip(),
                created_by=request.session.get('user_email', ''),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return redirect('inventory_detail', product_id=product_id)


# ---------------------------------------------------------------------------
# Customers (web)
# ---------------------------------------------------------------------------

_CUSTOMER_DEPT_KEYS = {'customers', 'customer_service', 'sales'}
_SUPPLIER_DEPT_KEYS = {'customers', 'purchasing', 'sales'}


def _customer_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _CUSTOMER_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('customer_list')
    return None


def _supplier_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _SUPPLIER_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('supplier_list')
    return None


def _contacts_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def customer_list(request):
    denied = _customer_access(request)
    if denied:
        return denied
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        customers = list_customers(conn, search=search or None)
    finally:
        conn.close()
    return render(request, 'contacts_list.html', _contacts_context(
        request,
        contacts=customers,
        search=search,
        contact_type='customer',
        contact_type_plural='customers',
        list_url='/customers/',
        new_url='/customers/new/',
        detail_base='/customers/',
    ))


def customer_new(request):
    denied = _customer_access(request, write=True)
    if denied:
        return denied
    error = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                cid = create_customer(
                    conn,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('customer_detail', customer_id=cid)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'contacts_new.html', _contacts_context(
        request,
        contact_type='customer',
        contact_type_plural='customers',
        list_url='/customers/',
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


def customer_detail(request, customer_id):
    denied = _customer_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        contact = get_customer(conn, customer_id)
        if not contact:
            return redirect('customer_list')
        if request.method == 'POST' and can_edit:
            try:
                update_customer(
                    conn, customer_id,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                )
                conn.commit()
                contact = get_customer(conn, customer_id)
                success = 'Customer updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        orders = get_customer_orders(conn, customer_id)
    finally:
        conn.close()
    return render(request, 'contacts_detail.html', _contacts_context(
        request,
        contact=contact,
        orders=orders,
        contact_type='customer',
        contact_type_plural='customers',
        list_url='/customers/',
        new_url='/customers/new/',
        order_label='Sales Order',
        order_url_prefix='/so/',
        error=error,
        success=success,
        can_edit=can_edit,
    ))


# ---------------------------------------------------------------------------
# Suppliers (web)
# ---------------------------------------------------------------------------

def supplier_list(request):
    denied = _supplier_access(request)
    if denied:
        return denied
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        suppliers = contacts_list_suppliers(conn, search=search or None)
    finally:
        conn.close()
    return render(request, 'contacts_list.html', _contacts_context(
        request,
        contacts=suppliers,
        search=search,
        contact_type='supplier',
        contact_type_plural='suppliers',
        list_url='/suppliers/',
        new_url='/suppliers/new/',
        detail_base='/suppliers/',
    ))


def supplier_new(request):
    denied = _supplier_access(request, write=True)
    if denied:
        return denied
    error = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                sid = create_supplier(
                    conn,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('supplier_detail', supplier_id=sid)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'contacts_new.html', _contacts_context(
        request,
        contact_type='supplier',
        contact_type_plural='suppliers',
        list_url='/suppliers/',
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


def supplier_detail(request, supplier_id):
    denied = _supplier_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        contact = get_supplier(conn, supplier_id)
        if not contact:
            return redirect('supplier_list')
        if request.method == 'POST' and can_edit:
            try:
                update_supplier(
                    conn, supplier_id,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                )
                conn.commit()
                contact = get_supplier(conn, supplier_id)
                success = 'Supplier updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        orders = get_supplier_orders(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'contacts_detail.html', _contacts_context(
        request,
        contact=contact,
        orders=orders,
        contact_type='supplier',
        contact_type_plural='suppliers',
        list_url='/suppliers/',
        new_url='/suppliers/new/',
        order_label='Purchase Order',
        order_url_prefix='/po/',
        error=error,
        success=success,
        can_edit=can_edit,
    ))


# ---------------------------------------------------------------------------
# Customer Service tickets (web)
# ---------------------------------------------------------------------------

_CS_DEPT_KEYS = {'customer_service', 'sales', 'customers'}


def _cs_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _CS_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('cs_ticket_list')
    return None


def _cs_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def cs_ticket_list(request):
    denied = _cs_access(request)
    if denied:
        return denied
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    my_only = request.GET.get('my', '') == '1'
    created_by = request.session.get('user_email', '') if my_only else None
    conn = get_db_connection()
    try:
        tickets = list_tickets(
            conn,
            search=search or None,
            status=status_filter or None,
            created_by=created_by,
        )
        open_count = sum(1 for t in tickets if t['status'] == 'open')
        overdue_count = sum(1 for t in tickets
                           if t['priority'] in ('high', 'critical'))
    finally:
        conn.close()
    return render(request, 'cs_list.html', _cs_context(
        request,
        tickets=tickets,
        open_count=open_count,
        overdue_count=overdue_count,
        search=search,
        status_filter=status_filter,
        my_only=my_only,
    ))


def cs_ticket_new(request):
    denied = _cs_access(request, write=True)
    if denied:
        return denied
    conn = get_db_connection()
    error = None
    customers = []
    try:
        customers = load_customers_for_cs(conn)
        if request.method == 'POST':
            cid_raw = request.POST.get('customer_id', '')
            try:
                customer_id = int(cid_raw)
            except (TypeError, ValueError):
                customer_id = None
            call_text = request.POST.get('call', '')
            errors = validate_call(customer_id, call_text)
            if errors:
                error = '; '.join(errors)
            else:
                import datetime as _dt
                today = _dt.date.today().isoformat()
                now_time = _dt.datetime.now().strftime('%H:%M')
                tid = create_ticket(
                    conn,
                    customer_id=customer_id,
                    call=call_text,
                    call_date=request.POST.get('call_date', '') or today,
                    call_time=request.POST.get('call_time', '') or now_time,
                    comments=request.POST.get('comments', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('cs_ticket_detail', ticket_id=tid)
    except Exception as e:
        conn.rollback()
        error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_new.html', _cs_context(
        request,
        customers=customers,
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


def cs_ticket_detail(request, ticket_id):
    denied = _cs_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    ticket = None
    customers = []
    try:
        ticket = get_ticket(conn, ticket_id)
        if not ticket:
            return redirect('cs_ticket_list')
        customers = load_customers_for_cs(conn) if can_edit else []

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'close':
                    close_ticket(conn, ticket_id,
                                 comments=request.POST.get('comments', ''))
                    conn.commit()
                    success = 'Ticket closed.'
                elif action == 'update':
                    try:
                        cid = int(request.POST.get('customer_id', 0))
                    except ValueError:
                        cid = ticket['customer_id']
                    update_ticket(
                        conn, ticket_id,
                        customer_id=cid,
                        call=request.POST.get('call', ''),
                        call_date=request.POST.get('call_date', ''),
                        call_time=request.POST.get('call_time', ''),
                        completion_date=request.POST.get('completion_date', ''),
                        completion_time=request.POST.get('completion_time', ''),
                        comments=request.POST.get('comments', ''),
                        completed=request.POST.get('completed') == '1',
                    )
                    conn.commit()
                    success = 'Ticket updated.'
                ticket = get_ticket(conn, ticket_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_detail.html', _cs_context(
        request,
        ticket=ticket,
        customers=customers,
        error=error,
        success=success,
        can_edit=can_edit,
    ))


def cs_escalations(request):
    denied = _cs_access(request)
    if denied:
        return denied
    conn = get_db_connection()
    try:
        tickets = get_escalations(conn)
        critical_count = sum(1 for t in tickets if t['priority'] == 'critical')
        high_count = sum(1 for t in tickets if t['priority'] == 'high')
    finally:
        conn.close()
    return render(request, 'cs_escalations.html', _cs_context(
        request,
        tickets=tickets,
        critical_count=critical_count,
        high_count=high_count,
    ))


def cs_reports(request):
    denied = _cs_access(request)
    if denied:
        return denied
    try:
        days = int(request.GET.get('days', 365))
    except ValueError:
        days = 365
    conn = get_db_connection()
    try:
        stats = get_summary_stats(conn, days)
        monthly = get_monthly_volume(conn, days)
        open_tickets = list_tickets(conn, status='open')
        overdue_count = sum(1 for t in open_tickets
                           if t['priority'] in ('high', 'critical'))
    finally:
        conn.close()
    return render(request, 'cs_reports.html', _cs_context(
        request,
        stats=stats,
        monthly=monthly,
        open_count=len(open_tickets),
        overdue_count=overdue_count,
        days=days,
    ))


def cs_plans(request):
    denied = _cs_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_filter = request.GET.get('status', '').strip()
    conn = get_db_connection()
    error = None
    success = None
    plans = []
    try:
        plans = list_plans(conn, status=status_filter or None)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'create':
                    create_plan(
                        conn,
                        title=request.POST.get('title', ''),
                        description=request.POST.get('description', ''),
                        owner=request.POST.get('owner', ''),
                        target_date=request.POST.get('target_date', ''),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Plan created.'
                elif action == 'update':
                    pid = int(request.POST.get('plan_id', 0))
                    update_plan(
                        conn, pid,
                        title=request.POST.get('title', ''),
                        description=request.POST.get('description', ''),
                        owner=request.POST.get('owner', ''),
                        target_date=request.POST.get('target_date', ''),
                        status=request.POST.get('status', 'Open'),
                    )
                    conn.commit()
                    success = 'Plan updated.'
                plans = list_plans(conn, status=status_filter or None)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_plans.html', _cs_context(
        request,
        plans=plans,
        plan_statuses=PLAN_STATUSES,
        status_filter=status_filter,
        error=error,
        success=success,
        can_edit=can_edit,
    ))
