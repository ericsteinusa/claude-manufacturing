from unittest.mock import MagicMock

from manufacturing.production_core import (
    get_production_dashboard, get_daily_output_trend, get_wo_status_breakdown,
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
