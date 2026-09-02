"""Views: Credit Department (accounts, applications, limit history, collections).

The menu leaf ('accounting', 'credit') existed since the desktop-app days
(customers/Credit_dept.py, retired) but its web equivalent was never
built — WEB_LEAF_URLS silently routed it to General Ledger instead. This
module is the real thing, against the same credit_account/
credit_application/credit_limit_history/collection_activity tables the
Customers & Credit sample seed already populates.
"""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..contacts_core import list_customers

from ..credit_core import (
    get_credit_dashboard,
    list_credit_accounts, get_credit_account, get_credit_account_by_customer,
    customers_without_credit_account, create_credit_account, update_credit_account,
    list_limit_history,
    list_credit_applications, get_credit_application,
    create_credit_application, decide_credit_application,
    list_collection_activities, get_collection_activity,
    create_collection_activity, update_collection_activity,
    CREDIT_STATUSES, APPLICATION_STATUSES, COLLECTION_STATUSES, ACTIVITY_TYPES,
)

log = get_logger(__name__)

_CREDIT_DEPT_KEYS = {'accounting', 'customers', 'finance'}


def _opt_float(post, key):
    val = post.get(key)
    return float(val) if val else None


def _credit_ctx(request, **extra):
    return {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        **extra,
    }


@dept_required(_CREDIT_DEPT_KEYS)
def credit_dashboard(request):
    with get_db_connection() as conn:
        data = get_credit_dashboard(conn)
        recent_accounts = list_credit_accounts(conn)[:8]
        recent_applications = [
            a for a in list_credit_applications(conn) if a['status'] == 'pending'
        ][:8]
        recent_collections = [
            c for c in list_collection_activities(conn)
            if c['status'] in ('Open', 'In Progress', 'Escalated')
        ][:8]
    return render(request, 'credit_dashboard.html', _credit_ctx(
        request, **data, recent_accounts=recent_accounts,
        recent_applications=recent_applications,
        recent_collections=recent_collections,
    ))


@dept_required(_CREDIT_DEPT_KEYS)
def credit_dashboard_kpis_fragment(request):
    """htmx polling target for credit_dashboard's KPI rows + accounts/applications/collections tables."""
    with get_db_connection() as conn:
        data = get_credit_dashboard(conn)
        recent_accounts = list_credit_accounts(conn)[:8]
        recent_applications = [
            a for a in list_credit_applications(conn) if a['status'] == 'pending'
        ][:8]
        recent_collections = [
            c for c in list_collection_activities(conn)
            if c['status'] in ('Open', 'In Progress', 'Escalated')
        ][:8]
    return render(request, 'credit_dashboard_kpis.html', {
        **data, 'recent_accounts': recent_accounts,
        'recent_applications': recent_applications,
        'recent_collections': recent_collections,
    })


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@dept_required(_CREDIT_DEPT_KEYS, write_redirect='credit_account_list')
def credit_account_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                aid = create_credit_account(
                    conn,
                    customer_id=int(request.POST.get('customer_id', 0)),
                    credit_limit=float(request.POST.get('credit_limit', 0) or 0),
                    status=request.POST.get('status', 'good'),
                    terms=request.POST.get('terms', ''),
                    opened_date=request.POST.get('opened_date', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('credit_account_detail', account_id=aid)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
        accounts = list_credit_accounts(conn, status=status_f or None, search=search or None)
        available_customers = customers_without_credit_account(conn)
    finally:
        conn.close()
    return render(request, 'credit_account_list.html', _credit_ctx(
        request, accounts=accounts, status_filter=status_f, search=search,
        credit_statuses=CREDIT_STATUSES, available_customers=available_customers,
        error=error, success=success,
    ))


@dept_required(_CREDIT_DEPT_KEYS, write_redirect='credit_account_list')
def credit_account_detail(request, account_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    account = None
    try:
        account = get_credit_account(conn, account_id)
        if not account:
            return redirect('credit_account_list')
        if request.method == 'POST' and can_edit:
            try:
                update_credit_account(
                    conn, account_id,
                    credit_limit=float(request.POST.get('credit_limit', 0) or 0),
                    status=request.POST.get('status', 'good'),
                    terms=request.POST.get('terms', ''),
                    notes=request.POST.get('notes', ''),
                    changed_by=request.session.get('user_email', ''),
                    reason=request.POST.get('reason', '').strip(),
                )
                conn.commit()
                success = 'Account updated.'
                account = get_credit_account(conn, account_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
        history = list_limit_history(conn, account['customer_id'])
        applications = list_credit_applications(conn)
        applications = [a for a in applications if a['customer_id'] == account['customer_id']]
        collections = list_collection_activities(conn, customer_id=account['customer_id'])
    finally:
        conn.close()
    return render(request, 'credit_account_detail.html', _credit_ctx(
        request, account=account, history=history, applications=applications,
        collections=collections, can_edit=can_edit, credit_statuses=CREDIT_STATUSES,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@dept_required(_CREDIT_DEPT_KEYS, write_redirect='credit_application_list')
def credit_application_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                app_id = create_credit_application(
                    conn,
                    customer_id=int(request.POST.get('customer_id', 0)),
                    applied_date=request.POST.get('applied_date', ''),
                    requested_limit=float(request.POST.get('requested_limit', 0) or 0),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('credit_application_detail', app_id=app_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
        applications = list_credit_applications(conn, status=status_f or None, search=search or None)
        customers = list_customers(conn)
    finally:
        conn.close()
    return render(request, 'credit_application_list.html', _credit_ctx(
        request, applications=applications, status_filter=status_f, search=search,
        application_statuses=APPLICATION_STATUSES, customers=customers,
        error=error, success=success,
    ))


@dept_required(_CREDIT_DEPT_KEYS, write_redirect='credit_application_list')
def credit_application_detail(request, app_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    application = None
    try:
        application = get_credit_application(conn, app_id)
        if not application:
            return redirect('credit_application_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action in ('approved', 'denied'):
                    approved_limit = request.POST.get('approved_limit', '')
                    decide_credit_application(
                        conn, app_id, action,
                        float(approved_limit) if approved_limit else None,
                        reviewed_by=request.session.get('user_email', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    conn.commit()
                    success = f'Application {action}.'
                    application = get_credit_application(conn, app_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
        existing_account = get_credit_account_by_customer(conn, application['customer_id'])
    finally:
        conn.close()
    return render(request, 'credit_application_detail.html', _credit_ctx(
        request, application=application, existing_account=existing_account,
        can_edit=can_edit, error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@dept_required(_CREDIT_DEPT_KEYS, write_redirect='credit_collections_list')
def credit_collections_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                act_id = create_collection_activity(
                    conn,
                    customer_id=int(request.POST.get('customer_id', 0)),
                    activity_date=request.POST.get('activity_date', ''),
                    activity_type=request.POST.get('activity_type', 'Call'),
                    contact_name=request.POST.get('contact_name', ''),
                    notes=request.POST.get('notes', ''),
                    amount_promised=_opt_float(request.POST, 'amount_promised'),
                    promise_date=request.POST.get('promise_date') or None,
                    follow_up_date=request.POST.get('follow_up_date') or None,
                    status=request.POST.get('status', 'Open'),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('credit_collections_detail', activity_id=act_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
        activities = list_collection_activities(conn, status=status_f or None, search=search or None)
        customers = list_customers(conn)
    finally:
        conn.close()
    return render(request, 'credit_collections_list.html', _credit_ctx(
        request, activities=activities, status_filter=status_f, search=search,
        collection_statuses=COLLECTION_STATUSES, activity_types=ACTIVITY_TYPES,
        customers=customers, error=error, success=success,
    ))


@dept_required(_CREDIT_DEPT_KEYS, write_redirect='credit_collections_list')
def credit_collections_detail(request, activity_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    activity = None
    try:
        activity = get_collection_activity(conn, activity_id)
        if not activity:
            return redirect('credit_collections_list')
        if request.method == 'POST' and can_edit:
            try:
                update_collection_activity(
                    conn, activity_id,
                    activity_type=request.POST.get('activity_type', 'Call'),
                    contact_name=request.POST.get('contact_name', ''),
                    notes=request.POST.get('notes', ''),
                    amount_promised=_opt_float(request.POST, 'amount_promised'),
                    promise_date=request.POST.get('promise_date') or None,
                    follow_up_date=request.POST.get('follow_up_date') or None,
                    status=request.POST.get('status', 'Open'),
                )
                conn.commit()
                success = 'Activity updated.'
                activity = get_collection_activity(conn, activity_id)
            except (ValueError, TypeError) as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'credit_collections_detail.html', _credit_ctx(
        request, activity=activity, can_edit=can_edit,
        collection_statuses=COLLECTION_STATUSES, activity_types=ACTIVITY_TYPES,
        error=error, success=success,
    ))
