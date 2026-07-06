"""
Tests for manufacturing/payroll_core.py — pure unit tests, no Qt, no DB.
"""

import datetime
import pytest
from unittest.mock import MagicMock

from manufacturing.payroll_core import (
    SS_RATE, MEDICARE_RATE, FREQUENCIES, PAY_TYPES,
    DED_CATEGORIES, DED_METHODS,
    get_dashboard_counts, load_people,
    list_pay_rates, get_pay_rate, upsert_pay_rate, delete_pay_rate,
    list_deduction_types, get_deduction_type,
    create_deduction_type, update_deduction_type,
    list_employee_deductions, get_employee_deduction,
    create_employee_deduction, update_employee_deduction,
    delete_employee_deduction,
    list_payroll_runs, get_payroll_run, get_run_entries,
    get_pay_stub, get_stub_deductions, list_run_employees,
    list_pay_stubs_for_employee,
    get_ytd,
)


def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


def _today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_ss_rate():
    assert abs(SS_RATE - 0.062) < 1e-9


def test_medicare_rate():
    assert abs(MEDICARE_RATE - 0.0145) < 1e-9


def test_pay_types():
    assert 'hourly' in PAY_TYPES
    assert 'salary' in PAY_TYPES


def test_frequencies_four():
    assert len(FREQUENCIES) == 4
    assert 'Weekly' in FREQUENCIES


def test_ded_categories():
    assert 'Benefits' in DED_CATEGORIES
    assert 'Retirement' in DED_CATEGORIES


def test_ded_methods():
    assert 'flat' in DED_METHODS
    assert 'percent' in DED_METHODS


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def test_dashboard_counts_returns_dict():
    conn = _conn(fetchone={
        'total_runs': 5, 'emp_with_rates': 20, 'total_people': 25,
        'active_ded_types': 3, 'ytd_gross': 500000.0,
    })
    r = get_dashboard_counts(conn)
    assert r['total_runs'] == 5
    assert r['ytd_gross'] == 500000.0


def test_dashboard_counts_fallback_none():
    conn = _conn(fetchone=None)
    r = get_dashboard_counts(conn)
    assert r['total_runs'] == 0
    assert r['ytd_gross'] == 0.0


def test_dashboard_counts_passes_year():
    conn = _conn(fetchone={'total_runs': 0, 'emp_with_rates': 0,
                           'total_people': 0, 'active_ded_types': 0,
                           'ytd_gross': 0.0})
    get_dashboard_counts(conn)
    params = conn.execute.call_args[0][1]
    assert str(datetime.date.today().year) in params


# ---------------------------------------------------------------------------
# load_people
# ---------------------------------------------------------------------------

def test_load_people_returns_list():
    conn = _conn(fetchall=[{'id': 1, 'first_name': 'Bob', 'last_name': 'Smith',
                            'employee_id': 'E001'}])
    result = load_people(conn)
    assert len(result) == 1


def test_load_people_empty():
    assert load_people(_conn(fetchall=[])) == []


def test_load_people_orders_by_name():
    conn = _conn(fetchall=[])
    load_people(conn)
    sql = conn.execute.call_args[0][0]
    assert 'last_name' in sql and 'first_name' in sql


# ---------------------------------------------------------------------------
# Pay Rates
# ---------------------------------------------------------------------------

def test_list_pay_rates_returns_all():
    conn = _conn(fetchall=[{'people_id': 1, 'first_name': 'Bob', 'last_name': 'S',
                            'employee_id': 'E1', 'pay_type': 'hourly',
                            'pay_rate': 20.0, 'effective_date': '2024-01-01'}])
    result = list_pay_rates(conn)
    assert len(result) == 1


def test_list_pay_rates_search_uses_ilike():
    conn = _conn(fetchall=[])
    list_pay_rates(conn, search='bob')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_list_pay_rates_no_search_no_where():
    conn = _conn(fetchall=[])
    list_pay_rates(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_get_pay_rate_returns_dict():
    conn = _conn(fetchone={'people_id': 1, 'pay_type': 'hourly', 'pay_rate': 20.0})
    r = get_pay_rate(conn, 1)
    assert r is not None
    assert r['pay_type'] == 'hourly'


def test_get_pay_rate_returns_none():
    assert get_pay_rate(_conn(fetchone=None), 99) is None


def test_upsert_pay_rate_uses_on_conflict():
    conn = _conn()
    upsert_pay_rate(conn, 1, 'hourly', 25.0, '2024-01-01')
    sql = conn.execute.call_args[0][0]
    assert 'ON CONFLICT' in sql
    assert 'employee_pay' in sql


def test_upsert_pay_rate_defaults_to_hourly_on_bad_type():
    conn = _conn()
    upsert_pay_rate(conn, 1, 'bogus', 25.0, '2024-01-01')
    params = conn.execute.call_args[0][1]
    assert 'hourly' in params


def test_upsert_pay_rate_uses_today_when_no_date():
    conn = _conn()
    upsert_pay_rate(conn, 1, 'hourly', 25.0, '')
    params = conn.execute.call_args[0][1]
    assert _today() in params


def test_upsert_pay_rate_does_not_commit():
    conn = _conn()
    upsert_pay_rate(conn, 1, 'hourly', 25.0, '2024-01-01')
    conn.commit.assert_not_called()


def test_delete_pay_rate_executes_delete():
    conn = _conn()
    delete_pay_rate(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'DELETE FROM employee_pay' in sql


def test_delete_pay_rate_does_not_commit():
    conn = _conn()
    delete_pay_rate(conn, 1)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Deduction Types
# ---------------------------------------------------------------------------

def test_list_deduction_types_returns_rows():
    conn = _conn(fetchall=[{'id': 1, 'name': 'Health', 'category': 'Benefits',
                            'is_pre_tax': 1, 'is_active': 1}])
    result = list_deduction_types(conn)
    assert result[0]['name'] == 'Health'


def test_list_deduction_types_active_only_filters():
    conn = _conn(fetchall=[])
    list_deduction_types(conn, active_only=True)
    sql = conn.execute.call_args[0][0]
    assert 'is_active=1' in sql


def test_list_deduction_types_no_filter():
    conn = _conn(fetchall=[])
    list_deduction_types(conn)
    sql = conn.execute.call_args[0][0]
    assert 'is_active' not in sql


def test_get_deduction_type_returns_dict():
    conn = _conn(fetchone={'id': 1, 'name': 'Health'})
    result = get_deduction_type(conn, 1)
    assert result is not None
    assert result['name'] == 'Health'


def test_get_deduction_type_returns_none():
    assert get_deduction_type(_conn(fetchone=None), 99) is None


def test_create_deduction_type_returns_id():
    conn = _conn(fetchone={'id': 3})
    did = create_deduction_type(conn, '401k', 'Retirement', True)
    assert did == 3


def test_create_deduction_type_rejects_empty_name():
    with pytest.raises(ValueError):
        create_deduction_type(_conn(), '  ', 'Other', True)


def test_create_deduction_type_defaults_other_on_bad_category():
    conn = _conn(fetchone={'id': 1})
    create_deduction_type(conn, 'Plan', 'BadCat', True)
    params = conn.execute.call_args[0][1]
    assert 'Other' in params


def test_create_deduction_type_is_active_defaults_to_1():
    conn = _conn(fetchone={'id': 1})
    create_deduction_type(conn, 'Plan', 'Benefits', True)
    sql = conn.execute.call_args[0][0]
    assert 'is_active' in sql


def test_create_deduction_type_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_deduction_type(conn, 'Plan', 'Benefits', True)
    conn.commit.assert_not_called()


def test_update_deduction_type_executes_update():
    conn = _conn()
    update_deduction_type(conn, 1, 'Health', 'Benefits', True, True)
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE payroll_deduction_type' in sql


def test_update_deduction_type_rejects_empty_name():
    with pytest.raises(ValueError):
        update_deduction_type(_conn(), 1, '', 'Benefits', True, True)


def test_update_deduction_type_does_not_commit():
    conn = _conn()
    update_deduction_type(conn, 1, 'Health', 'Benefits', True, True)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Employee Deductions
# ---------------------------------------------------------------------------

def test_list_employee_deductions_returns_rows():
    conn = _conn(fetchall=[{'id': 1, 'people_id': 1, 'first_name': 'Bob',
                            'last_name': 'S', 'ded_name': 'Health',
                            'category': 'Benefits', 'is_pre_tax': 1,
                            'calc_method': 'flat', 'amount': 100.0,
                            'is_active': 1, 'notes': ''}])
    result = list_employee_deductions(conn)
    assert result[0]['ded_name'] == 'Health'


def test_list_employee_deductions_filter_by_person():
    conn = _conn(fetchall=[])
    list_employee_deductions(conn, people_id=5)
    params = conn.execute.call_args[0][1]
    assert 5 in params


def test_list_employee_deductions_no_filter():
    conn = _conn(fetchall=[])
    list_employee_deductions(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_get_employee_deduction_returns_dict():
    conn = _conn(fetchone={'id': 1, 'calc_method': 'flat', 'amount': 100.0,
                           'is_active': 1, 'notes': '', 'people_id': 1,
                           'deduction_type_id': 2, 'effective_date': '',
                           'end_date': None, 'ded_name': 'Health',
                           'category': 'Benefits', 'ded_is_pre_tax': 1,
                           'first_name': 'Bob', 'last_name': 'S'})
    result = get_employee_deduction(conn, 1)
    assert result is not None
    assert result['id'] == 1


def test_get_employee_deduction_returns_none():
    assert get_employee_deduction(_conn(fetchone=None), 99) is None


def test_create_employee_deduction_returns_id():
    conn = _conn(fetchone={'id': 7})
    eid = create_employee_deduction(conn, 1, 2, 'flat', 100.0, True, 'notes')
    assert eid == 7


def test_create_employee_deduction_defaults_flat_on_bad_method():
    conn = _conn(fetchone={'id': 1})
    create_employee_deduction(conn, 1, 2, 'bogus', 0.0, True, '')
    params = conn.execute.call_args[0][1]
    assert 'flat' in params


def test_create_employee_deduction_stamps_today():
    conn = _conn(fetchone={'id': 1})
    create_employee_deduction(conn, 1, 2, 'flat', 0.0, True, '')
    params = conn.execute.call_args[0][1]
    assert _today() in params


def test_create_employee_deduction_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_employee_deduction(conn, 1, 2, 'flat', 0.0, True, '')
    conn.commit.assert_not_called()


def test_update_employee_deduction_executes_update():
    conn = _conn()
    update_employee_deduction(conn, 1, 2, 3, 'percent', 5.0, True, '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE employee_deduction' in sql


def test_update_employee_deduction_does_not_commit():
    conn = _conn()
    update_employee_deduction(conn, 1, 2, 3, 'flat', 0.0, True, '')
    conn.commit.assert_not_called()


def test_delete_employee_deduction_executes_delete():
    conn = _conn()
    delete_employee_deduction(conn, 5)
    sql = conn.execute.call_args[0][0]
    assert 'DELETE FROM employee_deduction' in sql


def test_delete_employee_deduction_does_not_commit():
    conn = _conn()
    delete_employee_deduction(conn, 5)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Payroll Runs
# ---------------------------------------------------------------------------

def _run(**kw):
    base = {'id': 1, 'run_date': '2024-06-15 10:00:00',
            'pay_period_start': '2024-06-01', 'pay_period_end': '2024-06-14',
            'status': 'processed', 'created_by': 'admin@e.com',
            'emp_count': 10, 'total_gross': 50000.0, 'total_net': 37000.0}
    base.update(kw)
    return base


def test_list_payroll_runs_returns_rows():
    conn = _conn(fetchall=[_run()])
    result = list_payroll_runs(conn)
    assert result[0]['id'] == 1


def test_list_payroll_runs_empty():
    assert list_payroll_runs(_conn(fetchall=[])) == []


def test_list_payroll_runs_orders_desc():
    conn = _conn(fetchall=[])
    list_payroll_runs(conn)
    sql = conn.execute.call_args[0][0]
    assert 'DESC' in sql


def test_get_payroll_run_returns_dict():
    conn = _conn(fetchone=_run())
    result = get_payroll_run(conn, 1)
    assert result is not None
    assert result['id'] == 1


def test_get_payroll_run_returns_none():
    assert get_payroll_run(_conn(fetchone=None), 99) is None


def test_get_run_entries_returns_rows():
    conn = _conn(fetchall=[{'id': 1, 'first_name': 'Bob', 'last_name': 'S',
                            'employee_id': 'E1', 'run_id': 1,
                            'people_id': 1, 'regular_hours': 80.0,
                            'overtime_hours': 0.0, 'gross_pay': 2000.0,
                            'federal_tax': 440.0, 'state_tax': 100.0,
                            'social_security': 124.0, 'medicare': 29.0,
                            'net_pay': 1307.0, 'pre_tax_deductions': 0.0,
                            'post_tax_deductions': 0.0}])
    result = get_run_entries(conn, 1)
    assert result[0]['gross_pay'] == 2000.0


def test_get_run_entries_filters_by_run():
    conn = _conn(fetchall=[])
    get_run_entries(conn, 5)
    params = conn.execute.call_args[0][1]
    assert 5 in params


# ---------------------------------------------------------------------------
# Pay Stubs
# ---------------------------------------------------------------------------

def _stub(**kw):
    base = {'id': 1, 'run_id': 1, 'people_id': 1,
            'first_name': 'Bob', 'last_name': 'Smith',
            'employee_id': 'E001',
            'pay_period_start': '2024-06-01', 'pay_period_end': '2024-06-14',
            'run_date': '2024-06-15 10:00:00', 'status': 'processed',
            'pay_type': 'hourly', 'pay_rate': 25.0,
            'regular_hours': 80.0, 'overtime_hours': 0.0,
            'gross_pay': 2000.0, 'federal_tax': 440.0, 'state_tax': 100.0,
            'social_security': 124.0, 'medicare': 29.0,
            'net_pay': 1307.0, 'pre_tax_deductions': 0.0,
            'post_tax_deductions': 0.0}
    base.update(kw)
    return base


def test_get_pay_stub_returns_dict():
    conn = _conn(fetchone=_stub())
    s = get_pay_stub(conn, 1)
    assert s is not None
    assert s['gross_pay'] == 2000.0


def test_get_pay_stub_returns_none():
    assert get_pay_stub(_conn(fetchone=None), 99) is None


def test_get_pay_stub_joins_people_and_run():
    conn = _conn(fetchone=_stub())
    get_pay_stub(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'people' in sql and 'payroll_run' in sql


def test_get_stub_deductions_returns_rows():
    conn = _conn(fetchall=[{'id': 1, 'entry_id': 1,
                            'deduction_name': 'Health', 'is_pre_tax': 1,
                            'amount': 100.0}])
    result = get_stub_deductions(conn, 1)
    assert result[0]['deduction_name'] == 'Health'


def test_get_stub_deductions_orders_pre_tax_first():
    conn = _conn(fetchall=[])
    get_stub_deductions(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'is_pre_tax' in sql


def test_list_run_employees_returns_rows():
    conn = _conn(fetchall=[{'entry_id': 1, 'first_name': 'Bob', 'last_name': 'S'}])
    result = list_run_employees(conn, 1)
    assert result[0]['first_name'] == 'Bob'


def test_list_run_employees_filters_by_run():
    conn = _conn(fetchall=[])
    list_run_employees(conn, 3)
    params = conn.execute.call_args[0][1]
    assert 3 in params


# ---------------------------------------------------------------------------
# list_pay_stubs_for_employee (Employee Self-Service, P2-G)
# ---------------------------------------------------------------------------

def test_list_pay_stubs_for_employee_returns_rows():
    conn = _conn(fetchall=[{'entry_id': 7, 'run_id': 2, 'gross_pay': 2000.0}])
    result = list_pay_stubs_for_employee(conn, 5)
    assert result[0]['entry_id'] == 7


def test_list_pay_stubs_for_employee_filters_by_people_id():
    conn = _conn(fetchall=[])
    list_pay_stubs_for_employee(conn, 5)
    sql, params = conn.execute.call_args[0]
    assert 'payroll_run' in sql
    assert list(params) == [5]


def test_list_pay_stubs_for_employee_orders_most_recent_first():
    conn = _conn(fetchall=[])
    list_pay_stubs_for_employee(conn, 5)
    sql = conn.execute.call_args[0][0]
    assert 'ORDER BY pr.run_date DESC' in sql


# ---------------------------------------------------------------------------
# YTD
# ---------------------------------------------------------------------------

def _ytd_row(**kw):
    base = {'first_name': 'Bob', 'last_name': 'S',
            'run_count': 5, 'reg_hrs': 400.0, 'ot_hrs': 10.0,
            'gross': 10000.0, 'pre_deds': 500.0, 'fed': 2200.0,
            'state_tax': 500.0, 'ss': 620.0, 'medicare': 145.0, 'net': 6035.0}
    base.update(kw)
    return base


def test_get_ytd_returns_rows():
    conn = _conn(fetchall=[_ytd_row()])
    result = get_ytd(conn, 2024)
    assert result[0]['gross'] == 10000.0


def test_get_ytd_passes_year():
    conn = _conn(fetchall=[])
    get_ytd(conn, 2023)
    params = conn.execute.call_args[0][1]
    assert '2023' in params


def test_get_ytd_filters_by_person():
    conn = _conn(fetchall=[])
    get_ytd(conn, 2024, people_id=7)
    params = conn.execute.call_args[0][1]
    assert 7 in params


def test_get_ytd_no_person_filter():
    conn = _conn(fetchall=[])
    get_ytd(conn, 2024)
    params = conn.execute.call_args[0][1]
    assert len(params) == 1


def test_get_ytd_uses_left_function_for_year():
    conn = _conn(fetchall=[])
    get_ytd(conn, 2024)
    sql = conn.execute.call_args[0][0]
    assert 'LEFT' in sql


def test_get_ytd_empty():
    assert get_ytd(_conn(fetchall=[]), 2024) == []
