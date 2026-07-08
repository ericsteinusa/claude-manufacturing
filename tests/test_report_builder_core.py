"""Tests for report_builder_core — Custom Report Builder (P4-F).

No live database: a MagicMock connection stands in for psycopg2 (mirrors
tests/test_edi_core.py, tests/test_ecommerce_core.py). Most of this
module's logic (validate_definition, build_query) is pure and tested
directly against dicts; run_report/CRUD are tested against a fake conn.
"""

import datetime
import json
from unittest.mock import MagicMock

import pytest

from manufacturing.report_builder_core import (
    validate_definition, build_query, run_report, report_to_pdf_bytes,
    ensure_report_builder_tables, create_saved_report, update_saved_report,
    get_saved_report, list_saved_reports, delete_saved_report,
    _is_due, list_due_scheduled_reports, mark_report_run,
)


def _conn(fetchone_results=None, fetchall_results=None):
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── validate_definition ──────────────────────────────────────────────────

def test_validate_definition_rejects_unknown_table():
    with pytest.raises(ValueError):
        validate_definition('passwd', {'columns': ['id']})


def test_validate_definition_rejects_unknown_column():
    with pytest.raises(ValueError):
        validate_definition('sales_order', {'columns': ['nonexistent_col']})


def test_validate_definition_rejects_unknown_operator():
    with pytest.raises(ValueError):
        validate_definition('sales_order', {
            'columns': ['status'],
            'filters': [{'column': 'status', 'operator': 'nope', 'value': 'x'}],
        })


def test_validate_definition_rejects_non_numeric_aggregate():
    with pytest.raises(ValueError):
        validate_definition('sales_order', {
            'group_by': ['status'],
            'aggregates': [{'column': 'status', 'func': 'sum'}],
        })


def test_validate_definition_allows_count_on_any_column():
    validate_definition('sales_order', {
        'group_by': ['status'],
        'aggregates': [{'column': 'status', 'func': 'count'}],
    })


def test_validate_definition_rejects_sort_column_not_in_output():
    with pytest.raises(ValueError):
        validate_definition('sales_order', {
            'columns': ['status'],
            'sort': [{'column': 'order_date', 'direction': 'asc'}],
        })


def test_validate_definition_rejects_empty_selection():
    with pytest.raises(ValueError):
        validate_definition('sales_order', {})


def test_validate_definition_accepts_valid_flat_report():
    validate_definition('sales_order', {
        'columns': ['so_number', 'status'],
        'filters': [{'column': 'status', 'operator': '=', 'value': 'open'}],
        'sort': [{'column': 'status', 'direction': 'asc'}],
    })


def test_validate_definition_accepts_valid_grouped_report():
    validate_definition('so_item', {
        'group_by': ['product_id'],
        'aggregates': [{'column': 'qty', 'func': 'sum'}],
        'sort': [{'column': 'sum_qty', 'direction': 'desc'}],
    })


# ── build_query ───────────────────────────────────────────────────────────

def test_build_query_flat_report_with_filter():
    sql, params, output_fields = build_query('sales_order', {
        'columns': ['so_number', 'status'],
        'filters': [{'column': 'status', 'operator': '=', 'value': 'open'}],
    })
    assert 'SELECT so_number, status FROM sales_order' in sql
    assert 'WHERE status = %s' in sql
    assert params == ['open', 1000]
    assert output_fields == [('so_number', 'SO Number'), ('status', 'Status')]


def test_build_query_contains_filter_escapes_wildcards():
    sql, params, _ = build_query('sales_order', {
        'columns': ['status'],
        'filters': [{'column': 'notes', 'operator': 'contains', 'value': '100%_off'}],
    })
    assert 'notes ILIKE %s' in sql
    assert params[0] == r'%100\%\_off%'


def test_build_query_in_filter_expands_placeholders():
    sql, params, _ = build_query('sales_order', {
        'columns': ['status'],
        'filters': [{'column': 'status', 'operator': 'in', 'value': 'open, closed , draft'}],
    })
    assert 'status IN (%s, %s, %s)' in sql
    assert params[:3] == ['open', 'closed', 'draft']


def test_build_query_is_null_filter_has_no_param():
    sql, params, _ = build_query('sales_order', {
        'columns': ['status'],
        'filters': [{'column': 'notes', 'operator': 'is_null'}],
    })
    assert 'notes IS NULL' in sql
    assert params == [1000]


def test_build_query_grouped_aggregate_ignores_plain_columns():
    sql, params, output_fields = build_query('so_item', {
        'columns': ['description'],  # must be ignored
        'group_by': ['product_id'],
        'aggregates': [{'column': 'qty', 'func': 'sum'}],
    })
    assert 'SELECT product_id, SUM(qty) AS sum_qty FROM so_item' in sql
    assert 'GROUP BY product_id' in sql
    assert output_fields == [('product_id', 'Product ID'), ('sum_qty', 'SUM(Qty)')]


def test_build_query_sort_and_limit():
    sql, params, _ = build_query('sales_order', {
        'columns': ['status', 'so_number'],
        'sort': [{'column': 'status', 'direction': 'desc'}],
    }, limit=50)
    assert 'ORDER BY status DESC' in sql
    assert 'LIMIT %s' in sql
    assert params == [50]


# ── run_report ────────────────────────────────────────────────────────────

def test_run_report_returns_dict_rows():
    conn = _conn(fetchall_results=[[{'status': 'open', 'so_number': 'SO-1'}]])
    result = run_report(conn, 'sales_order', {'columns': ['status', 'so_number']})
    assert result['rows'] == [{'status': 'open', 'so_number': 'SO-1'}]
    assert result['output_fields'] == [('status', 'Status'), ('so_number', 'SO Number')]


def test_run_report_raises_on_invalid_definition_before_querying():
    conn = MagicMock()
    with pytest.raises(ValueError):
        run_report(conn, 'sales_order', {'columns': ['nope']})
    assert conn.execute.call_count == 0


# ── PDF export ────────────────────────────────────────────────────────────

def test_report_to_pdf_bytes_returns_valid_pdf():
    pdf = report_to_pdf_bytes('Test Report', [('status', 'Status')], [{'status': 'open'}])
    assert pdf.startswith(b'%PDF')
    assert len(pdf) > 100


# ── saved report CRUD ────────────────────────────────────────────────────

def test_ensure_report_builder_tables_creates_table():
    conn = MagicMock()
    ensure_report_builder_tables(conn)
    sql = conn.execute.call_args[0][0]
    assert 'CREATE TABLE IF NOT EXISTS saved_report (' in sql


def test_create_saved_report_rejects_empty_name():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_saved_report(conn, '', 'sales_order', {'columns': ['status']},
                             'private', 'a@example.com', 'sales', 'a@example.com')


def test_create_saved_report_rejects_bad_access_level():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_saved_report(conn, 'My Report', 'sales_order', {'columns': ['status']},
                             'public', 'a@example.com', 'sales', 'a@example.com')


def test_create_saved_report_rejects_invalid_definition():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_saved_report(conn, 'My Report', 'sales_order', {'columns': ['nope']},
                             'private', 'a@example.com', 'sales', 'a@example.com')


def test_create_saved_report_inserts_and_returns_id():
    conn = _conn(fetchone_results=[{'id': 7}])
    report_id = create_saved_report(
        conn, 'My Report', 'sales_order', {'columns': ['status']},
        'private', 'a@example.com', 'sales', 'a@example.com')
    assert report_id == 7
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO saved_report' in sql
    assert params[0] == 'My Report'
    assert json.loads(params[2]) == {'columns': ['status']}


def test_get_saved_report_parses_definition_json():
    conn = _conn(fetchone_results=[{
        'id': 1, 'table_name': 'sales_order',
        'definition': json.dumps({'columns': ['status']}),
    }])
    result = get_saved_report(conn, 1)
    assert result['definition'] == {'columns': ['status']}


def test_get_saved_report_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_saved_report(conn, 999) is None


def test_update_saved_report_validates_new_definition():
    conn = MagicMock()
    with pytest.raises(ValueError):
        update_saved_report(conn, 1, table_name='sales_order', definition={'columns': ['nope']})


def test_list_saved_reports_passes_filters():
    conn = _conn(fetchall_results=[[]])
    list_saved_reports(conn, 'a@example.com', 'sales', full_access=False)
    sql, params = conn.execute.call_args[0]
    assert 'access_level' in sql
    assert params == (False, 'sales', 'a@example.com')


def test_delete_saved_report():
    conn = MagicMock()
    delete_saved_report(conn, 5)
    sql, params = conn.execute.call_args[0]
    assert 'DELETE FROM saved_report' in sql
    assert params == (5,)


# ── scheduling ────────────────────────────────────────────────────────────

def test_is_due_never_run_is_always_due():
    assert _is_due('daily', None) is True


def test_is_due_daily():
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    assert _is_due('daily', today) is False
    assert _is_due('daily', yesterday) is True


def test_is_due_weekly():
    six_days_ago = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    assert _is_due('weekly', six_days_ago) is False
    assert _is_due('weekly', seven_days_ago) is True


def test_is_due_monthly():
    twenty_nine_days_ago = (datetime.date.today() - datetime.timedelta(days=29)).isoformat()
    thirty_days_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    assert _is_due('monthly', twenty_nine_days_ago) is False
    assert _is_due('monthly', thirty_days_ago) is True


def test_is_due_unknown_frequency_never_due():
    long_ago = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    assert _is_due('yearly', long_ago) is False


def test_list_due_scheduled_reports_filters_by_due():
    conn = _conn(fetchall_results=[[
        {'id': 1, 'schedule_frequency': 'daily', 'last_run_at': None,
         'definition': '{"columns": ["status"]}'},
        {'id': 2, 'schedule_frequency': 'daily',
         'last_run_at': datetime.date.today().isoformat(),
         'definition': '{"columns": ["status"]}'},
    ]])
    due = list_due_scheduled_reports(conn)
    assert len(due) == 1
    assert due[0]['id'] == 1
    assert due[0]['definition'] == {'columns': ['status']}


def test_mark_report_run_updates_last_run_at():
    conn = MagicMock()
    mark_report_run(conn, 3)
    sql, params = conn.execute.call_args[0]
    assert 'UPDATE saved_report SET last_run_at' in sql
    assert params[1] == 3
