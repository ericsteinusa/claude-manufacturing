from unittest.mock import MagicMock

from manufacturing.production_core import (
    get_production_dashboard, get_daily_output_trend, get_wo_status_breakdown,
    get_wo_time_variance_report, get_labor_by_personnel_report,
    resolve_operation_owner,
)


def _wo_row(draft=0, open=0, in_progress=0, completed_today=0, overdue=0, total=0):
    return {
        'draft': draft,
        'open': open,
        'in_progress': in_progress,
        'completed_today': completed_today,
        'overdue': overdue,
        'total': total,
    }


def _inv_row(total_products=0, zero_stock=0, low_stock=0):
    return {
        'total_products': total_products,
        'zero_stock': zero_stock,
        'low_stock': low_stock,
    }


def _recent_row(id=1, wo_number='WO-2024-0001', description='desc',
                due_date='2024-01-01', status='open', product_name='Widget'):
    return {
        'id': id,
        'wo_number': wo_number,
        'description': description,
        'due_date': due_date,
        'status': status,
        'product_name': product_name,
    }


def _multi_conn(fetchone1, fetchone2, fetchall_rows):
    c = MagicMock()
    wo_mock = MagicMock()
    wo_mock.fetchone.return_value = fetchone1
    inv_mock = MagicMock()
    inv_mock.fetchone.return_value = fetchone2
    recent_mock = MagicMock()
    recent_mock.fetchall.return_value = fetchall_rows
    c.execute.side_effect = [wo_mock, inv_mock, recent_mock]
    return c


def _default_conn(wo=None, inv=None, recent=None):
    wo = wo if wo is not None else _wo_row(draft=1, open=2, in_progress=3,
                                            completed_today=4, overdue=5, total=15)
    inv = inv if inv is not None else _inv_row(total_products=10, zero_stock=2, low_stock=3)
    recent = recent if recent is not None else [_recent_row()]
    return _multi_conn(wo, inv, recent)


# 1. result has the three expected top-level keys
def test_dashboard_returns_three_keys():
    c = _default_conn()
    result = get_production_dashboard(c)
    assert set(result.keys()) == {'work_orders', 'inventory', 'recent_wos'}


# 2. work_orders['draft'] reflects the mock value
def test_dashboard_wo_draft_count():
    c = _multi_conn(_wo_row(draft=7), _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['work_orders']['draft'] == 7


# 3. work_orders['open']
def test_dashboard_wo_open_count():
    c = _multi_conn(_wo_row(open=4), _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['work_orders']['open'] == 4


# 4. work_orders['in_progress']
def test_dashboard_wo_in_progress():
    c = _multi_conn(_wo_row(in_progress=9), _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['work_orders']['in_progress'] == 9


# 5. work_orders['overdue']
def test_dashboard_wo_overdue():
    c = _multi_conn(_wo_row(overdue=3), _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['work_orders']['overdue'] == 3


# 6. work_orders['total']
def test_dashboard_wo_total():
    c = _multi_conn(_wo_row(total=42), _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['work_orders']['total'] == 42


# 7. inventory['total_products']
def test_dashboard_inv_total_products():
    c = _multi_conn(_wo_row(), _inv_row(total_products=50), [])
    result = get_production_dashboard(c)
    assert result['inventory']['total_products'] == 50


# 8. inventory['zero_stock']
def test_dashboard_inv_zero_stock():
    c = _multi_conn(_wo_row(), _inv_row(zero_stock=6), [])
    result = get_production_dashboard(c)
    assert result['inventory']['zero_stock'] == 6


# 9. inventory['low_stock']
def test_dashboard_inv_low_stock():
    c = _multi_conn(_wo_row(), _inv_row(low_stock=11), [])
    result = get_production_dashboard(c)
    assert result['inventory']['low_stock'] == 11


# 10. recent_wos is a list
def test_dashboard_recent_wos_list():
    c = _default_conn()
    result = get_production_dashboard(c)
    assert isinstance(result['recent_wos'], list)


# 11. correct number of rows returned
def test_dashboard_recent_wos_count():
    rows = [_recent_row(id=i, wo_number=f'WO-2024-{i:04d}') for i in range(1, 6)]
    c = _multi_conn(_wo_row(), _inv_row(), rows)
    result = get_production_dashboard(c)
    assert len(result['recent_wos']) == 5


# 12. each row has 'wo_number'
def test_dashboard_recent_wo_has_wo_number():
    rows = [_recent_row(wo_number='WO-2024-0099')]
    c = _multi_conn(_wo_row(), _inv_row(), rows)
    result = get_production_dashboard(c)
    assert result['recent_wos'][0]['wo_number'] == 'WO-2024-0099'


# 13. each row has 'product_name'
def test_dashboard_recent_wo_has_product_name():
    rows = [_recent_row(product_name='Sprocket')]
    c = _multi_conn(_wo_row(), _inv_row(), rows)
    result = get_production_dashboard(c)
    assert result['recent_wos'][0]['product_name'] == 'Sprocket'


# 14. wo fetchone returns None → work_orders == {}
def test_dashboard_wo_row_none_returns_empty_dict():
    c = _multi_conn(None, _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['work_orders'] == {}


# 15. inv fetchone returns None → inventory == {}
def test_dashboard_inv_row_none_returns_empty_dict():
    c = _multi_conn(_wo_row(), None, [])
    result = get_production_dashboard(c)
    assert result['inventory'] == {}


# 16. fetchall returns [] → recent_wos == []
def test_dashboard_empty_recent_wos():
    c = _multi_conn(_wo_row(), _inv_row(), [])
    result = get_production_dashboard(c)
    assert result['recent_wos'] == []


# 17. conn.execute called exactly three times
def test_dashboard_executes_three_queries():
    c = _default_conn()
    get_production_dashboard(c)
    assert c.execute.call_count == 3


# 18. first query references the work_order table
def test_dashboard_wo_query_references_work_order_table():
    c = _default_conn()
    get_production_dashboard(c)
    calls = c.execute.call_args_list
    wo_sql = calls[0][0][0]
    assert 'work_order' in wo_sql


# 19. second query references the product table
def test_dashboard_inv_query_references_product_table():
    c = _default_conn()
    get_production_dashboard(c)
    calls = c.execute.call_args_list
    inv_sql = calls[1][0][0]
    assert 'product' in inv_sql


# 20. third query uses LIMIT 8
def test_dashboard_recent_query_uses_limit_8():
    c = _default_conn()
    get_production_dashboard(c)
    calls = c.execute.call_args_list
    recent_sql = calls[2][0][0]
    assert 'LIMIT 8' in recent_sql


# ── get_daily_output_trend ────────────────────────────────────────────────

def _trend_conn(rows):
    c = MagicMock()
    m = MagicMock()
    m.fetchall.return_value = rows
    c.execute.return_value = m
    return c


def test_daily_output_trend_returns_list():
    c = _trend_conn([{'day': '2026-06-01', 'qty': 10}])
    result = get_daily_output_trend(c)
    assert result == [{'day': '2026-06-01', 'qty': 10}]


def test_daily_output_trend_empty():
    c = _trend_conn([])
    assert get_daily_output_trend(c) == []


def test_daily_output_trend_filters_completed_status():
    c = _trend_conn([])
    get_daily_output_trend(c, days=7)
    sql = c.execute.call_args_list[0][0][0]
    assert "status = 'completed'" in sql


# ── get_wo_status_breakdown ──────────────────────────────────────────────

def test_wo_status_breakdown_returns_list():
    c = _trend_conn([{'status': 'open', 'cnt': 3}, {'status': 'completed', 'cnt': 5}])
    result = get_wo_status_breakdown(c)
    assert result == [{'status': 'open', 'cnt': 3}, {'status': 'completed', 'cnt': 5}]


def test_wo_status_breakdown_empty():
    c = _trend_conn([])
    assert get_wo_status_breakdown(c) == []


# ── resolve_operation_owner (pure, no DB) ────────────────────────────────

def test_resolve_operation_owner_prefers_completed_by():
    assert resolve_operation_owner('a@example.com', 'Jane Doe') == 'a@example.com'


def test_resolve_operation_owner_falls_back_to_assigned_to():
    assert resolve_operation_owner('', 'Jane Doe') == 'Jane Doe'
    assert resolve_operation_owner(None, 'Jane Doe') == 'Jane Doe'


def test_resolve_operation_owner_blank_when_both_empty():
    assert resolve_operation_owner('', '') == ''
    assert resolve_operation_owner(None, None) == ''


def test_resolve_operation_owner_strips_whitespace():
    assert resolve_operation_owner('  a@example.com  ', '') == 'a@example.com'
    assert resolve_operation_owner('   ', 'Jane Doe') == 'Jane Doe'


# ── get_wo_time_variance_report ──────────────────────────────────────────

def _wo_variance_row(wo_id=1, wo_number='WO-2024-0001', product_name='Widget',
                     status='completed', due_date='2026-06-01',
                     std_hours=10.0, actual_hours=12.0, labor_cost=120.0):
    return {
        'wo_id': wo_id, 'wo_number': wo_number, 'product_name': product_name,
        'status': status, 'due_date': due_date,
        'std_hours': std_hours, 'actual_hours': actual_hours,
        'labor_cost': labor_cost,
    }


def test_wo_time_variance_report_computes_variance():
    c = _trend_conn([_wo_variance_row(std_hours=10.0, actual_hours=12.0)])
    result = get_wo_time_variance_report(c)
    assert result[0]['hours_variance'] == 2.0
    assert result[0]['variance_pct'] == 20.0


def test_wo_time_variance_report_no_filters_no_where():
    c = _trend_conn([])
    get_wo_time_variance_report(c)
    sql = c.execute.call_args_list[0][0][0]
    assert 'wo.due_date >=' not in sql
    assert 'wo.status =' not in sql


def test_wo_time_variance_report_date_and_status_filters():
    c = _trend_conn([])
    get_wo_time_variance_report(c, date_from='2026-01-01', date_to='2026-06-30',
                                status='completed')
    sql = c.execute.call_args_list[0][0][0]
    params = c.execute.call_args_list[0][0][1]
    assert 'wo.due_date >= %s' in sql
    assert 'wo.due_date <= %s' in sql
    assert 'wo.status = %s' in sql
    assert params == ['2026-01-01', '2026-06-30', 'completed']


def test_wo_time_variance_report_empty():
    c = _trend_conn([])
    assert get_wo_time_variance_report(c) == []


# ── get_labor_by_personnel_report ────────────────────────────────────────

def _labor_conn(op_rows, people_rows, pay_rows):
    c = MagicMock()
    op_mock, people_mock, pay_mock = MagicMock(), MagicMock(), MagicMock()
    op_mock.fetchall.return_value = op_rows
    people_mock.fetchall.return_value = people_rows
    pay_mock.fetchall.return_value = pay_rows
    c.execute.side_effect = [op_mock, people_mock, pay_mock]
    return c


def test_labor_by_personnel_matches_completed_by_email():
    c = _labor_conn(
        op_rows=[{'wo_id': 1, 'wo_number': 'WO-0001', 'wo_assigned_to': '',
                  'completed_by': 'a@example.com',
                  'std_hours': 4.0, 'actual_hours': 5.0}],
        people_rows=[{'id': 9, 'first_name': 'Ann', 'last_name': 'Lee',
                      'email': 'a@example.com'}],
        pay_rows=[{'people_id': 9, 'pay_type': 'hourly', 'pay_rate': 20.0}],
    )
    result = get_labor_by_personnel_report(c)
    assert len(result) == 1
    assert result[0]['person_name'] == 'Ann Lee'
    assert result[0]['wo_count'] == 1
    assert result[0]['actual_hours'] == 5.0
    assert result[0]['total_cost'] == 100.0
    assert result[0]['wos'][0]['cost'] == 100.0


def test_labor_by_personnel_falls_back_to_assigned_to_name():
    c = _labor_conn(
        op_rows=[{'wo_id': 1, 'wo_number': 'WO-0001', 'wo_assigned_to': 'Ann Lee',
                  'completed_by': '', 'std_hours': 4.0, 'actual_hours': 5.0}],
        people_rows=[{'id': 9, 'first_name': 'Ann', 'last_name': 'Lee',
                      'email': 'a@example.com'}],
        pay_rows=[],
    )
    result = get_labor_by_personnel_report(c)
    assert len(result) == 1
    assert result[0]['person_name'] == 'Ann Lee'


def test_labor_by_personnel_salaried_pay_type_gives_none_cost():
    c = _labor_conn(
        op_rows=[{'wo_id': 1, 'wo_number': 'WO-0001', 'wo_assigned_to': '',
                  'completed_by': 'a@example.com',
                  'std_hours': 4.0, 'actual_hours': 5.0}],
        people_rows=[{'id': 9, 'first_name': 'Ann', 'last_name': 'Lee',
                      'email': 'a@example.com'}],
        pay_rows=[{'people_id': 9, 'pay_type': 'salary', 'pay_rate': 60000.0}],
    )
    result = get_labor_by_personnel_report(c)
    assert result[0]['total_cost'] is None
    assert result[0]['wos'][0]['cost'] is None
    # hours are still tracked even without a usable hourly rate
    assert result[0]['actual_hours'] == 5.0


def test_labor_by_personnel_unmatched_owner_skipped():
    c = _labor_conn(
        op_rows=[{'wo_id': 1, 'wo_number': 'WO-0001', 'wo_assigned_to': '',
                  'completed_by': 'nobody@example.com',
                  'std_hours': 4.0, 'actual_hours': 5.0}],
        people_rows=[{'id': 9, 'first_name': 'Ann', 'last_name': 'Lee',
                      'email': 'a@example.com'}],
        pay_rows=[],
    )
    result = get_labor_by_personnel_report(c)
    assert result == []


def test_labor_by_personnel_empty_owner_skipped():
    c = _labor_conn(
        op_rows=[{'wo_id': 1, 'wo_number': 'WO-0001', 'wo_assigned_to': '',
                  'completed_by': '', 'std_hours': 4.0, 'actual_hours': 5.0}],
        people_rows=[],
        pay_rows=[],
    )
    result = get_labor_by_personnel_report(c)
    assert result == []


def test_labor_by_personnel_aggregates_multiple_wos():
    c = _labor_conn(
        op_rows=[
            {'wo_id': 1, 'wo_number': 'WO-0001', 'wo_assigned_to': '',
             'completed_by': 'a@example.com', 'std_hours': 4.0, 'actual_hours': 5.0},
            {'wo_id': 2, 'wo_number': 'WO-0002', 'wo_assigned_to': '',
             'completed_by': 'a@example.com', 'std_hours': 2.0, 'actual_hours': 1.0},
        ],
        people_rows=[{'id': 9, 'first_name': 'Ann', 'last_name': 'Lee',
                      'email': 'a@example.com'}],
        pay_rows=[{'people_id': 9, 'pay_type': 'hourly', 'pay_rate': 10.0}],
    )
    result = get_labor_by_personnel_report(c)
    assert result[0]['wo_count'] == 2
    assert result[0]['std_hours'] == 6.0
    assert result[0]['actual_hours'] == 6.0
    assert result[0]['total_cost'] == 60.0
