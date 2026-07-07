"""Views: Multi-Company / Multi-Entity — company master, user-to-company
assignment, intercompany transactions, consolidated financials (P3-F)."""

import datetime as _dt

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required, role_required
from ..log_utils import get_logger
from ..accounts import FULL_ACCESS_ROLES, READ_ONLY_ROLES
from ..engineering_core import load_people

from ..multi_entity_core import (
    ensure_multi_entity_tables, get_or_create_base_company,
    list_companies, get_company, create_company,
    list_user_companies, assign_user_company, revoke_user_company,
    list_company_users, IC_GL_CATEGORIES, set_ic_account_map,
    list_intercompany_transactions, create_intercompany_transaction,
    void_intercompany_transaction,
    consolidated_income_statement, consolidated_balance_sheet,
)
from ..accounting_core import trial_balance, list_accounts
from ..costing_core import get_gl_account_map

log = get_logger(__name__)

_ACCOUNTING_DEPT_KEYS = {'accounting', 'finance'}


def _people_id_by_email(conn, email):
    row = conn.execute("SELECT id FROM people WHERE email = %s", (email,)).fetchone()
    return row['id'] if row else None


def _me_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
        'is_admin': role in FULL_ACCESS_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_ACCOUNTING_DEPT_KEYS)
def company_list(request):
    role = request.session.get('user_role', '')
    full_access = role in FULL_ACCESS_ROLES
    conn = get_db_connection()
    try:
        ensure_multi_entity_tables(conn)
        conn.commit()
        get_or_create_base_company(conn)
        conn.commit()
        people_id = _people_id_by_email(conn, request.session.get('user_email', ''))
        companies = list_user_companies(conn, people_id, full_access=full_access)
    finally:
        conn.close()
    return render(request, 'company_list.html', _me_ctx(request, companies=companies))


@role_required(FULL_ACCESS_ROLES)
def company_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_multi_entity_tables(conn)
        conn.commit()
        if request.method == 'POST':
            try:
                cid = create_company(
                    conn,
                    request.POST.get('name', '').strip(),
                    request.POST.get('legal_name', '').strip(),
                    request.POST.get('tax_id', '').strip(),
                    request.POST.get('currency_code', 'USD').strip(),
                    request.POST.get('address', '').strip(),
                    request.POST.get('notes', '').strip(),
                )
                conn.commit()
                return redirect('company_detail', company_id=cid)
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'company_new.html', _me_ctx(request, error=error))


@dept_required(_ACCOUNTING_DEPT_KEYS)
def company_detail(request, company_id):
    role = request.session.get('user_role', '')
    full_access = role in FULL_ACCESS_ROLES
    conn = get_db_connection()
    try:
        ensure_multi_entity_tables(conn)
        conn.commit()
        base_id = get_or_create_base_company(conn)
        conn.commit()
        people_id = _people_id_by_email(conn, request.session.get('user_email', ''))
        accessible_ids = {c['id'] for c in list_user_companies(conn, people_id, full_access=full_access)}
        company = get_company(conn, company_id) if company_id in accessible_ids else None
        if company:
            tb = trial_balance(conn, company_id=company_id,
                                include_null_company=(company_id == base_id))
            users = list_company_users(conn, company_id)
            people = load_people(conn)
        else:
            tb = None
            users = []
            people = []
    finally:
        conn.close()

    if not company:
        return redirect('company_list')

    return render(request, 'company_detail.html', _me_ctx(
        request, company=company, tb=tb, users=users, people=people,
        is_base=(company_id == base_id),
    ))


@role_required(FULL_ACCESS_ROLES)
def company_assign_user(request, company_id):
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            people_id = int(request.POST.get('people_id'))
            assign_user_company(conn, company_id, people_id)
            conn.commit()
        finally:
            conn.close()
    return redirect('company_detail', company_id=company_id)


@role_required(FULL_ACCESS_ROLES)
def company_revoke_user(request, company_id, people_id):
    if request.method == 'POST':
        conn = get_db_connection()
        try:
            revoke_user_company(conn, company_id, people_id)
            conn.commit()
        finally:
            conn.close()
    return redirect('company_detail', company_id=company_id)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def intercompany_list(request):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_multi_entity_tables(conn)
        conn.commit()
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            action = request.POST.get('action', '')
            try:
                if action == 'map_accounts':
                    for category in IC_GL_CATEGORIES:
                        number = request.POST.get(category, '').strip()
                        if number:
                            set_ic_account_map(conn, category, number)
                    conn.commit()
                    success = 'Account mapping saved.'
                elif action == 'void':
                    void_intercompany_transaction(conn, int(request.POST.get('ic_id')))
                    conn.commit()
                    success = 'Transaction voided.'
            except ValueError as e:
                conn.rollback()
                error = str(e)
        transactions = list_intercompany_transactions(conn)
        companies = list_companies(conn)
        account_map = get_gl_account_map(conn)
        accounts = list_accounts(conn)
    finally:
        conn.close()

    ic_mapping = [{'category': cat, 'account_number': account_map.get(cat, '')}
                  for cat in IC_GL_CATEGORIES]

    return render(request, 'intercompany_list.html', _me_ctx(
        request, transactions=transactions, companies=companies,
        ic_mapping=ic_mapping, accounts=accounts, error=error, success=success,
    ))


@dept_required(_ACCOUNTING_DEPT_KEYS, write_redirect='intercompany_list')
def intercompany_new(request):
    error = notice = None
    conn = get_db_connection()
    try:
        ensure_multi_entity_tables(conn)
        conn.commit()
        companies = list_companies(conn)
        if request.method == 'POST':
            try:
                result = create_intercompany_transaction(
                    conn,
                    int(request.POST.get('from_company_id')),
                    int(request.POST.get('to_company_id')),
                    request.POST.get('description', '').strip(),
                    float(request.POST.get('amount') or 0),
                    request.POST.get('transaction_date', '').strip(),
                    request.session.get('user_email', ''),
                )
                conn.commit()
                if result['unposted']:
                    notice = ('Transaction recorded but left unposted — map all four '
                              'IC accounts on the Intercompany page first.')
                else:
                    return redirect('intercompany_list')
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'intercompany_new.html', _me_ctx(
        request, companies=companies, error=error, notice=notice,
    ))


@dept_required(_ACCOUNTING_DEPT_KEYS)
def consolidated_financials(request):
    today = _dt.date.today()
    date_from = request.GET.get('date_from', f'{today.year}-01-01')
    date_to = request.GET.get('date_to', today.isoformat())
    conn = get_db_connection()
    try:
        ensure_multi_entity_tables(conn)
        conn.commit()
        income = consolidated_income_statement(conn, date_from, date_to)
        bs = consolidated_balance_sheet(conn, date_to)
    finally:
        conn.close()
    return render(request, 'consolidated_financials.html', _me_ctx(
        request, date_from=date_from, date_to=date_to, income=income, bs=bs,
    ))
