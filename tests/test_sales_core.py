"""
Tests for manufacturing/sales_core.py — dashboard, quotes, targets.
SO/order functions are already covered by test_sales_orders_core.py.
"""

import pytest
from unittest.mock import MagicMock

from manufacturing.sales_core import (
    QUOTE_STATUSES, TARGET_STATUSES,
    get_sales_dashboard, get_revenue_by_month, get_sales_reports,
    get_sales_performance,
    list_quotes, get_quote, create_quote, update_quote, set_quote_status,
    list_targets, create_target, update_target,
)


def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_quote_statuses_has_draft():
    assert 'Draft' in QUOTE_STATUSES

def test_quote_statuses_has_won():
    assert 'Won' in QUOTE_STATUSES

def test_quote_statuses_has_five():
    assert len(QUOTE_STATUSES) == 5

def test_target_statuses_has_on_track():
    assert 'On Track' in TARGET_STATUSES

def test_target_statuses_has_three():
    assert len(TARGET_STATUSES) == 3


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _dash_row(**kw):
    return {'draft': 2, 'confirmed': 1, 'shipped': 0, 'invoiced': 3,
            'total': 6, 'total_value': 15000.0,
            'sent': 1, 'won': 2, 'won_value': 5000.0,
            'total_target': 20000.0, 'total_actual': 18000.0, **kw}


def test_get_sales_dashboard_returns_sections():
    conn = _conn(fetchone=_dash_row())
    result = get_sales_dashboard(conn)
    assert 'orders' in result
    assert 'quotes' in result
    assert 'targets' in result


def test_get_sales_dashboard_orders_confirmed():
    conn = _conn(fetchone=_dash_row(confirmed=4))
    result = get_sales_dashboard(conn)
    assert result['orders'].get('confirmed') == 4


def test_get_sales_dashboard_quotes_won_value():
    conn = _conn(fetchone=_dash_row(won_value=9500.0))
    result = get_sales_dashboard(conn)
    assert result['quotes'].get('won_value') == 9500.0


def test_get_sales_dashboard_targets_actual():
    conn = _conn(fetchone=_dash_row(total_actual=22000.0))
    result = get_sales_dashboard(conn)
    assert result['targets'].get('total_actual') == 22000.0


def test_get_sales_dashboard_handles_none():
    conn = _conn(fetchone=None)
    result = get_sales_dashboard(conn)
    assert result['orders'] == {}
    assert result['quotes'] == {}
    assert result['targets'] == {}


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

def _quote(**kw):
    base = {'id': 1, 'customer': 'Acme Corp', 'description': 'Widget order',
            'amount': 5000.0, 'owner': 'rep@co.com',
            'quote_date': '2024-01-15', 'valid_until': '2024-02-15',
            'status': 'Draft', 'notes': '', 'created_by': 'u@co.com'}
    base.update(kw)
    return base


def test_list_quotes_returns_rows():
    conn = _conn(fetchall=[_quote()])
    result = list_quotes(conn)
    assert result[0]['customer'] == 'Acme Corp'


def test_list_quotes_no_filter_no_where():
    conn = _conn(fetchall=[])
    list_quotes(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_list_quotes_status_filter():
    conn = _conn(fetchall=[])
    list_quotes(conn, status='Sent')
    sql = conn.execute.call_args[0][0]
    assert 'status' in sql
    params = conn.execute.call_args[0][1]
    assert 'Sent' in params


def test_list_quotes_search_filter():
    conn = _conn(fetchall=[])
    list_quotes(conn, search='widget')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_quote_returns_row():
    conn = _conn(fetchone=_quote())
    assert get_quote(conn, 1)['customer'] == 'Acme Corp'


def test_get_quote_returns_none():
    assert get_quote(_conn(fetchone=None), 99) is None


def test_create_quote_returns_id():
    conn = _conn(fetchone={'id': 7})
    qid = create_quote(conn, 'Acme', 'Widgets', 5000, 'rep@co.com',
                       '2024-01-15', '2024-02-15', '', 'u@co.com')
    assert qid == 7


def test_create_quote_rejects_empty_customer():
    with pytest.raises(ValueError):
        create_quote(_conn(), '', 'desc', 0, '', None, None, '', '')


def test_create_quote_sets_status_draft():
    conn = _conn(fetchone={'id': 1})
    create_quote(conn, 'Acme', '', 0, '', None, None, '', '')
    sql = conn.execute.call_args[0][0]
    assert "'Draft'" in sql


def test_create_quote_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_quote(conn, 'Acme', '', 0, '', None, None, '', '')
    conn.commit.assert_not_called()


def test_update_quote_executes_update():
    conn = _conn()
    update_quote(conn, 1, 'Acme', 'desc', 1000, 'rep@co.com',
                 '2024-01-15', None, 'Sent', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE sales_quote' in sql


def test_update_quote_rejects_empty_customer():
    with pytest.raises(ValueError):
        update_quote(_conn(), 1, '', '', 0, '', None, None, 'Draft', '')


def test_update_quote_corrects_bad_status():
    conn = _conn()
    update_quote(conn, 1, 'Acme', '', 0, '', None, None, 'bogus', '')
    params = conn.execute.call_args[0][1]
    assert 'Draft' in params


def test_update_quote_does_not_commit():
    conn = _conn()
    update_quote(conn, 1, 'Acme', '', 0, '', None, None, 'Draft', '')
    conn.commit.assert_not_called()


def test_set_quote_status_executes_update():
    conn = _conn()
    set_quote_status(conn, 1, 'Won')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE sales_quote' in sql


def test_set_quote_status_corrects_bad_status():
    conn = _conn()
    set_quote_status(conn, 1, 'bogus')
    params = conn.execute.call_args[0][1]
    assert 'Draft' in params


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

def _target(**kw):
    base = {'id': 1, 'rep': 'Alice', 'period': '2024-Q1',
            'target': 10000.0, 'actual': 8500.0, 'variance': -1500.0,
            'region': 'East', 'status': 'Behind', 'notes': '',
            'created_by': 'u@co.com'}
    base.update(kw)
    return base


def test_list_targets_returns_rows():
    conn = _conn(fetchall=[_target()])
    result = list_targets(conn)
    assert result[0]['rep'] == 'Alice'


def test_list_targets_no_filter():
    conn = _conn(fetchall=[])
    list_targets(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_list_targets_rep_filter():
    conn = _conn(fetchall=[])
    list_targets(conn, rep='Alice')
    params = conn.execute.call_args[0][1]
    assert 'Alice' in params


def test_list_targets_period_filter():
    conn = _conn(fetchall=[])
    list_targets(conn, period='2024-Q1')
    params = conn.execute.call_args[0][1]
    assert '2024-Q1' in params


def test_list_targets_variance_in_select():
    conn = _conn(fetchall=[])
    list_targets(conn)
    sql = conn.execute.call_args[0][0]
    assert 'variance' in sql


def test_create_target_returns_id():
    conn = _conn(fetchone={'id': 3})
    tid = create_target(conn, 'Alice', '2024-Q1', 10000, 8500,
                        'East', 'Behind', '', 'u@co.com')
    assert tid == 3


def test_create_target_rejects_empty_rep():
    with pytest.raises(ValueError):
        create_target(_conn(), '', '', 0, 0, '', 'On Track', '', '')


def test_create_target_corrects_bad_status():
    conn = _conn(fetchone={'id': 1})
    create_target(conn, 'Bob', '', 0, 0, '', 'bogus', '', '')
    params = conn.execute.call_args[0][1]
    assert 'On Track' in params


def test_create_target_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_target(conn, 'Bob', '', 0, 0, '', 'On Track', '', '')
    conn.commit.assert_not_called()


def test_update_target_executes_update():
    conn = _conn()
    update_target(conn, 1, 'Alice', '2024-Q1', 10000, 9500, 'East', 'On Track', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE sales_target' in sql


def test_update_target_rejects_empty_rep():
    with pytest.raises(ValueError):
        update_target(_conn(), 1, '', '', 0, 0, '', 'On Track', '')


def test_update_target_corrects_bad_status():
    conn = _conn()
    update_target(conn, 1, 'Alice', '', 0, 0, '', 'bogus', '')
    params = conn.execute.call_args[0][1]
    assert 'On Track' in params


def test_update_target_does_not_commit():
    conn = _conn()
    update_target(conn, 1, 'Alice', '', 0, 0, '', 'On Track', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Revenue by month
# ---------------------------------------------------------------------------

def test_get_revenue_by_month_returns_rows():
    rows = [{'month': '2026-05', 'revenue': 1000.0}, {'month': '2026-06', 'revenue': 2000.0}]
    conn = _conn(fetchall=rows)
    result = get_revenue_by_month(conn)
    assert result == rows


def test_get_revenue_by_month_empty():
    conn = _conn(fetchall=[])
    assert get_revenue_by_month(conn) == []


def test_get_revenue_by_month_queries_sales_order():
    conn = _conn(fetchall=[])
    get_revenue_by_month(conn, months=3)
    sql = conn.execute.call_args[0][0]
    assert 'sales_order' in sql and 'so_item' in sql


# ---------------------------------------------------------------------------
# Sales reports
# ---------------------------------------------------------------------------

def _reports_conn(totals=None, trend=None, top_customers=None, top_products=None):
    c = MagicMock()
    t = totals if totals is not None else {'order_count': 4, 'total_revenue': 4000.0}
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=t)),
        MagicMock(fetchall=MagicMock(return_value=trend or [])),
        MagicMock(fetchall=MagicMock(return_value=top_customers or [])),
        MagicMock(fetchall=MagicMock(return_value=top_products or [])),
    ]
    return c


def test_get_sales_reports_returns_dict_with_expected_keys():
    result = get_sales_reports(_reports_conn(), '2026-01-01', '2026-01-31')
    assert set(result.keys()) == {'totals', 'trend', 'top_customers', 'top_products'}

def test_get_sales_reports_totals_pass_through():
    result = get_sales_reports(_reports_conn(totals={'order_count': 4, 'total_revenue': 4000.0}),
                               '2026-01-01', '2026-01-31')
    assert result['totals']['order_count'] == 4
    assert result['totals']['total_revenue'] == 4000.0

def test_get_sales_reports_computes_avg_order_value():
    result = get_sales_reports(_reports_conn(totals={'order_count': 4, 'total_revenue': 4000.0}),
                               '2026-01-01', '2026-01-31')
    assert result['totals']['avg_order_value'] == 1000.0

def test_get_sales_reports_avg_order_value_zero_when_no_orders():
    result = get_sales_reports(_reports_conn(totals={'order_count': 0, 'total_revenue': 0}),
                               '2026-01-01', '2026-01-31')
    assert result['totals']['avg_order_value'] == 0

def test_get_sales_reports_trend_converts_to_dicts():
    trend = [{'day': '2026-01-01', 'revenue': 500.0}]
    result = get_sales_reports(_reports_conn(trend=trend), '2026-01-01', '2026-01-31')
    assert result['trend'] == trend

def test_get_sales_reports_top_customers_converts_to_dicts():
    rows = [{'customer': 'ACME', 'revenue': 2000.0}]
    result = get_sales_reports(_reports_conn(top_customers=rows), '2026-01-01', '2026-01-31')
    assert result['top_customers'] == rows

def test_get_sales_reports_top_products_converts_to_dicts():
    rows = [{'product': 'Widget', 'revenue': 1500.0}]
    result = get_sales_reports(_reports_conn(top_products=rows), '2026-01-01', '2026-01-31')
    assert result['top_products'] == rows

def test_get_sales_reports_totals_query_uses_date_range():
    conn = _reports_conn()
    get_sales_reports(conn, '2026-01-01', '2026-01-31')
    sql, params = conn.execute.call_args_list[0][0]
    assert 'sales_order' in sql and params == ('2026-01-01', '2026-01-31')

def test_get_sales_reports_trend_query_groups_by_day():
    conn = _reports_conn()
    get_sales_reports(conn, '2026-01-01', '2026-01-31')
    sql, _ = conn.execute.call_args_list[1][0]
    assert 'GROUP BY so.order_date::date' in sql


# ---------------------------------------------------------------------------
# Sales performance
# ---------------------------------------------------------------------------

def _performance_conn(rep_targets=None, rep_orders=None):
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchall=MagicMock(return_value=rep_targets or [])),
        MagicMock(fetchall=MagicMock(return_value=rep_orders or [])),
    ]
    return c

def test_get_sales_performance_returns_expected_keys():
    result = get_sales_performance(_performance_conn())
    assert set(result.keys()) == {'rep_targets', 'rep_orders'}

def test_get_sales_performance_rep_targets_pass_through():
    row = {'rep': 'Sam', 'total_target': 10000.0, 'total_actual': 8000.0,
           'variance': -2000.0, 'attainment_pct': 80.0}
    result = get_sales_performance(_performance_conn(rep_targets=[row]))
    assert result['rep_targets'] == [row]

def test_get_sales_performance_rep_orders_pass_through():
    row = {'sales_rep': 'sam@example.com', 'order_count': 3, 'revenue': 5000.0}
    result = get_sales_performance(_performance_conn(rep_orders=[row]))
    assert result['rep_orders'] == [row]

def test_get_sales_performance_orders_query_uses_created_by_not_sales_rep():
    # sales_order has no sales_rep column live — regression guard for that bug.
    conn = _performance_conn()
    get_sales_performance(conn)
    sql = conn.execute.call_args_list[1][0][0]
    assert 'so.created_by' in sql and 'so.sales_rep' not in sql
