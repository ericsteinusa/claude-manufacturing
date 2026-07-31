"""Views: payroll domain."""

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..csv_export import export_response

import json

from ..payroll_core import (
    SS_RATE, MEDICARE_RATE, FREQUENCIES,
    PAY_TYPES, DED_CATEGORIES, DED_METHODS,
    get_dashboard_counts as payroll_get_dashboard_counts,
    get_payroll_monthly_gross, get_payroll_dept_breakdown,
    load_people as payroll_load_people,
    list_pay_rates, upsert_pay_rate, delete_pay_rate,
    list_deduction_types, create_deduction_type, update_deduction_type,
    list_employee_deductions, create_employee_deduction, delete_employee_deduction,
    list_payroll_runs, get_payroll_run, get_run_entries, process_payroll,
    get_pay_stub, get_stub_deductions, get_ytd,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

_PAYROLL_DEPT_KEYS = {'payroll', 'accounting', 'finance'}


def _payroll_ctx(request, **extra):
    return {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': (
            request.session.get('user_full_access')
            or request.session.get('user_dept_key') in _PAYROLL_DEPT_KEYS
        ) and request.session.get('user_role') not in READ_ONLY_ROLES,
        **extra,
    }


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_dashboard(request):
    conn = get_db_connection()
    try:
        counts = payroll_get_dashboard_counts(conn)
        runs = list_payroll_runs(conn)[:5]
        monthly_gross = get_payroll_monthly_gross(conn)
        dept_breakdown = get_payroll_dept_breakdown(conn)
    finally:
        conn.close()
    return render(request, 'payroll_dashboard.html', _payroll_ctx(
        request, counts=counts, recent_runs=runs,
        monthly_gross_json=json.dumps(monthly_gross),
        dept_breakdown_json=json.dumps(dept_breakdown),
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_pay_rates(request):
    can_edit = _payroll_ctx(request)['can_edit']
    search = request.GET.get('search', '').strip()
    success = error = ''

    if request.method == 'POST' and can_edit:
        action = request.POST.get('action', '')
        conn = get_db_connection()
        try:
            if action == 'upsert':
                pid = int(request.POST.get('people_id', 0))
                pay_type = request.POST.get('pay_type', 'hourly')
                try:
                    pay_rate = float(request.POST.get('pay_rate', '0') or '0')
                except ValueError:
                    pay_rate = 0.0
                eff_date = request.POST.get('effective_date', '').strip()
                upsert_pay_rate(conn, pid, pay_type, pay_rate, eff_date)
                conn.commit()
                success = 'Pay rate saved.'
            elif action == 'delete':
                pid = int(request.POST.get('people_id', 0))
                delete_pay_rate(conn, pid)
                conn.commit()
                success = 'Pay rate removed.'
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    conn = get_db_connection()
    try:
        employees = list_pay_rates(conn, search=search or None)
        people = payroll_load_people(conn)
    finally:
        conn.close()
    return render(request, 'payroll_pay_rates.html', _payroll_ctx(
        request, employees=employees, people=people,
        pay_types=PAY_TYPES, search=search,
        success=success, error=error,
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_deductions(request):
    can_edit = _payroll_ctx(request)['can_edit']
    people_filter = request.GET.get('people_id', '').strip()
    success = error = ''

    if request.method == 'POST' and can_edit:
        action = request.POST.get('action', '')
        conn = get_db_connection()
        try:
            if action == 'create_type':
                name = request.POST.get('name', '').strip()
                cat = request.POST.get('category', 'Other')
                is_pre = request.POST.get('is_pre_tax') == '1'
                create_deduction_type(conn, name, cat, is_pre)
                conn.commit()
                success = 'Deduction type added.'
            elif action == 'update_type':
                did = int(request.POST.get('ded_id', 0))
                name = request.POST.get('name', '').strip()
                cat = request.POST.get('category', 'Other')
                is_pre = request.POST.get('is_pre_tax') == '1'
                is_act = request.POST.get('is_active') == '1'
                update_deduction_type(conn, did, name, cat, is_pre, is_act)
                conn.commit()
                success = 'Deduction type updated.'
            elif action == 'assign':
                pid = int(request.POST.get('people_id', 0))
                tid = int(request.POST.get('deduction_type_id', 0))
                method = request.POST.get('calc_method', 'flat')
                try:
                    amt = float(request.POST.get('amount', '0') or '0')
                except ValueError:
                    amt = 0.0
                is_act = request.POST.get('is_active', '1') == '1'
                notes = request.POST.get('notes', '')
                create_employee_deduction(conn, pid, tid, method, amt, is_act, notes)
                conn.commit()
                success = 'Deduction assigned.'
            elif action == 'remove_assign':
                eid = int(request.POST.get('emp_ded_id', 0))
                delete_employee_deduction(conn, eid)
                conn.commit()
                success = 'Assignment removed.'
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    conn = get_db_connection()
    try:
        ded_types = list_deduction_types(conn)
        active_types = list_deduction_types(conn, active_only=True)
        pid = int(people_filter) if people_filter else None
        emp_deds = list_employee_deductions(conn, people_id=pid)
        people = payroll_load_people(conn)
    finally:
        conn.close()
    return render(request, 'payroll_deductions.html', _payroll_ctx(
        request, ded_types=ded_types, active_types=active_types,
        emp_deds=emp_deds, people=people,
        ded_categories=DED_CATEGORIES, ded_methods=DED_METHODS,
        people_filter=people_filter,
        success=success, error=error,
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_history(request):
    conn = get_db_connection()
    try:
        runs = list_payroll_runs(conn)
    finally:
        conn.close()
    return render(request, 'payroll_history.html', _payroll_ctx(
        request, runs=runs,
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_history_export(request):
    conn = get_db_connection()
    try:
        runs = list_payroll_runs(conn)
    finally:
        conn.close()

    return export_response(request, 'payroll_runs', [
        ('run_date', 'Run Date'), ('pay_period_start', 'Period Start'),
        ('pay_period_end', 'Period End'), ('emp_count', 'Employees'),
        ('total_gross', 'Total Gross'), ('total_net', 'Total Net'),
        ('status', 'Status'),
    ], runs)


@dept_required(_PAYROLL_DEPT_KEYS, write_redirect='payroll_history')
def payroll_run_new(request):
    can_edit = _payroll_ctx(request)['can_edit']
    error = ''
    if request.method == 'POST' and can_edit:
        conn = get_db_connection()
        try:
            try:
                fed_pct = float(request.POST.get('federal_tax_pct', '0') or '0')
                state_pct = float(request.POST.get('state_tax_pct', '0') or '0')
            except ValueError:
                fed_pct = state_pct = 0.0
            run_id = process_payroll(
                conn,
                pay_period_start=request.POST.get('pay_period_start', '').strip(),
                pay_period_end=request.POST.get('pay_period_end', '').strip(),
                pay_frequency=request.POST.get('pay_frequency', 'Bi-Weekly'),
                federal_tax_rate=fed_pct / 100.0,
                state_tax_rate=state_pct / 100.0,
                created_by=request.session.get('user_email', ''),
            )
            conn.commit()
            return redirect('payroll_run_detail', run_id=run_id)
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()
    return render(request, 'payroll_run_new.html', _payroll_ctx(
        request, frequencies=FREQUENCIES, error=error,
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_run_detail(request, run_id):
    conn = get_db_connection()
    try:
        run = get_payroll_run(conn, run_id)
        if not run:
            return redirect('/payroll/history/')
        entries = get_run_entries(conn, run_id)
    finally:
        conn.close()
    total_gross = sum(e.get('gross_pay') or 0 for e in entries)
    total_net   = sum(e.get('net_pay') or 0 for e in entries)
    return render(request, 'payroll_run_detail.html', _payroll_ctx(
        request, run=run, entries=entries,
        total_gross=total_gross, total_net=total_net,
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_stub_detail(request, entry_id):
    conn = get_db_connection()
    try:
        stub = get_pay_stub(conn, entry_id)
        if not stub:
            return redirect('/payroll/history/')
        deds = get_stub_deductions(conn, entry_id)
    finally:
        conn.close()
    pre_tax  = [d for d in deds if d.get('is_pre_tax')]
    post_tax = [d for d in deds if not d.get('is_pre_tax')]
    total_tax = (
        (stub.get('federal_tax') or 0)
        + (stub.get('state_tax') or 0)
        + (stub.get('social_security') or 0)
        + (stub.get('medicare') or 0)
    )
    return render(request, 'payroll_stub_detail.html', _payroll_ctx(
        request, stub=stub, pre_tax=pre_tax, post_tax=post_tax,
        total_tax=total_tax,
        ss_rate=SS_RATE, medicare_rate=MEDICARE_RATE,
    ))


@dept_required(_PAYROLL_DEPT_KEYS)
def payroll_ytd(request):
    import datetime as _dt
    cur_year = _dt.date.today().year
    try:
        year = int(request.GET.get('year', cur_year))
    except ValueError:
        year = cur_year
    people_id_str = request.GET.get('people_id', '').strip()
    pid = int(people_id_str) if people_id_str else None

    conn = get_db_connection()
    try:
        rows = get_ytd(conn, year, pid)
        people = payroll_load_people(conn)
    finally:
        conn.close()

    totals = {k: 0.0 for k in
              ('reg_hrs', 'ot_hrs', 'gross', 'pre_deds',
               'fed', 'state_tax', 'ss', 'medicare', 'net')}
    run_count_total = 0
    for r in rows:
        for k in totals:
            totals[k] += r.get(k) or 0.0
        run_count_total += r.get('run_count') or 0

    years = list(range(cur_year, cur_year - 6, -1))
    return render(request, 'payroll_ytd.html', _payroll_ctx(
        request, rows=rows, totals=totals,
        run_count_total=run_count_total,
        year=year, years=years,
        people=people, people_id=pid,
    ))


