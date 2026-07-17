"""
Tests for inventory_core.py — Qt-free inventory data layer.
"""

import pytest
from unittest.mock import MagicMock

from manufacturing.inventory_core import (
    TRANS_TYPES,
    list_products,
    get_product,
    get_transactions,
    get_alert_counts,
    load_suppliers,
    record_transaction,
    create_product,
    update_product,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


def _product(**kw):
    base = {
        'id': 1, 'name': 'Widget', 'item_type': 'buy',
        'uom': 'ea', 'bin': 'A1', 'amount': 50.0, 'reorder_point': 20.0,
        'purchase_price': 5.0, 'lead_time_days': 7, 'supplier_name': 'ACME',
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# TRANS_TYPES
# ---------------------------------------------------------------------------

def test_trans_types_includes_receive():
    assert 'receive' in TRANS_TYPES

def test_trans_types_includes_issue():
    assert 'issue' in TRANS_TYPES

def test_trans_types_includes_adjust():
    assert 'adjust' in TRANS_TYPES

def test_trans_types_includes_return():
    assert 'return' in TRANS_TYPES


# ---------------------------------------------------------------------------
# list_products — status annotation
# ---------------------------------------------------------------------------

def test_list_products_ok_status():
    conn = _conn(fetchall=[_product(amount=50.0, reorder_point=20.0)])
    result = list_products(conn)
    assert result[0]['status'] == 'ok'


def test_list_products_low_status():
    conn = _conn(fetchall=[_product(amount=15.0, reorder_point=20.0)])
    result = list_products(conn)
    assert result[0]['status'] == 'low'


def test_list_products_zero_status():
    conn = _conn(fetchall=[_product(amount=0.0, reorder_point=20.0)])
    result = list_products(conn)
    assert result[0]['status'] == 'zero'


def test_list_products_no_reorder_point_is_ok():
    conn = _conn(fetchall=[_product(amount=5.0, reorder_point=0.0)])
    result = list_products(conn)
    assert result[0]['status'] == 'ok'


def test_list_products_filter_zero_excludes_ok_and_low():
    conn = _conn(fetchall=[
        _product(id=1, name='A', amount=0.0, reorder_point=10.0),
        _product(id=2, name='B', amount=5.0, reorder_point=10.0),
        _product(id=3, name='C', amount=100.0, reorder_point=10.0),
    ])
    result = list_products(conn, filter_status='zero')
    assert len(result) == 1
    assert result[0]['name'] == 'A'


def test_list_products_filter_low_includes_zero():
    conn = _conn(fetchall=[
        _product(id=1, name='A', amount=0.0, reorder_point=10.0),
        _product(id=2, name='B', amount=5.0, reorder_point=10.0),
        _product(id=3, name='C', amount=100.0, reorder_point=10.0),
    ])
    result = list_products(conn, filter_status='low')
    names = [r['name'] for r in result]
    assert 'A' in names  # zero
    assert 'B' in names  # low
    assert 'C' not in names  # ok


def test_list_products_item_type_filter_passed_to_sql():
    conn = _conn(fetchall=[])
    list_products(conn, item_type='make')
    sql = conn.execute.call_args[0][0]
    assert 'item_type' in sql


def test_list_products_search_passed_to_sql():
    conn = _conn(fetchall=[])
    list_products(conn, search='widget')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql
    params = conn.execute.call_args[0][1]
    assert '%widget%' in params


def test_list_products_empty_db():
    conn = _conn(fetchall=[])
    assert list_products(conn) == []


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------

def test_get_product_returns_dict():
    row = _product()
    row['supplier_id'] = 1
    row['created_by'] = 'test@example.com'
    conn = _conn(fetchone=row)
    result = get_product(conn, 1)
    assert result is not None
    assert result['name'] == 'Widget'


def test_get_product_returns_none_when_missing():
    conn = _conn(fetchone=None)
    assert get_product(conn, 999) is None


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------

def test_get_transactions_returns_list():
    conn = _conn(fetchall=[
        {'id': 1, 'trans_date': '2026-06-01', 'trans_type': 'receive',
         'quantity': 10.0, 'reference': 'PO-001', 'notes': '',
         'created_by': 'u@e.com'},
    ])
    result = get_transactions(conn, product_id=1)
    assert len(result) == 1
    assert result[0]['trans_type'] == 'receive'


def test_get_transactions_empty():
    conn = _conn(fetchall=[])
    assert get_transactions(conn, 1) == []


def test_get_transactions_passes_limit():
    conn = _conn(fetchall=[])
    get_transactions(conn, product_id=1, limit=10)
    params = conn.execute.call_args[0][1]
    assert 10 in params


# ---------------------------------------------------------------------------
# get_alert_counts
# ---------------------------------------------------------------------------

def test_get_alert_counts_returns_dict():
    conn = _conn(fetchone={'zero_count': 2, 'low_count': 5})
    result = get_alert_counts(conn)
    assert result['zero_count'] == 2
    assert result['low_count'] == 5


def test_get_alert_counts_fallback_when_none():
    conn = _conn(fetchone=None)
    result = get_alert_counts(conn)
    assert result == {'zero_count': 0, 'low_count': 0}


# ---------------------------------------------------------------------------
# load_suppliers
# ---------------------------------------------------------------------------

def test_load_suppliers_returns_list():
    conn = _conn(fetchall=[{'id': 1, 'label': 'ACME Corp'}])
    result = load_suppliers(conn)
    assert result[0]['label'] == 'ACME Corp'


def test_load_suppliers_empty():
    conn = _conn(fetchall=[])
    assert load_suppliers(conn) == []


# ---------------------------------------------------------------------------
# record_transaction — delta logic
# ---------------------------------------------------------------------------

def _record_conn(new_amount=40.0, reorder_point=0.0, name='Test Product'):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {
        'amount': new_amount, 'reorder_point': reorder_point, 'name': name,
    }
    return conn


def test_record_transaction_receive_adds_to_stock():
    conn = _record_conn(new_amount=60.0)
    new_qty = record_transaction(conn, 1, 'receive', 10.0, '', '', 'u@e.com')
    assert new_qty == 60.0
    # Check UPDATE delta is positive
    update_call = conn.execute.call_args_list[1]
    params = update_call[0][1]
    assert params[0] == pytest.approx(10.0)  # delta = +10


def test_record_transaction_issue_subtracts():
    conn = _record_conn(new_amount=40.0)
    record_transaction(conn, 1, 'issue', 10.0, '', '', 'u@e.com')
    update_params = conn.execute.call_args_list[1][0][1]
    assert update_params[0] == pytest.approx(-10.0)  # delta = -10


def test_record_transaction_return_adds():
    conn = _record_conn(new_amount=60.0)
    record_transaction(conn, 1, 'return', 10.0, '', '', 'u@e.com')
    update_params = conn.execute.call_args_list[1][0][1]
    assert update_params[0] == pytest.approx(10.0)


def test_record_transaction_adjust_positive():
    conn = _record_conn(new_amount=55.0)
    record_transaction(conn, 1, 'adjust', 5.0, '', '', 'u@e.com')
    update_params = conn.execute.call_args_list[1][0][1]
    assert update_params[0] == pytest.approx(5.0)


def test_record_transaction_adjust_negative():
    conn = _record_conn(new_amount=45.0)
    record_transaction(conn, 1, 'adjust', -5.0, '', '', 'u@e.com')
    update_params = conn.execute.call_args_list[1][0][1]
    assert update_params[0] == pytest.approx(-5.0)


def test_record_transaction_issue_with_negative_input_still_subtracts():
    """Issue: user accidentally enters -10 → still treated as deduction."""
    conn = _record_conn(new_amount=40.0)
    record_transaction(conn, 1, 'issue', -10.0, '', '', 'u@e.com')
    update_params = conn.execute.call_args_list[1][0][1]
    assert update_params[0] == pytest.approx(-10.0)  # abs then negate


def test_record_transaction_invalid_type_raises():
    conn = MagicMock()
    with pytest.raises(ValueError, match='Unknown trans_type'):
        record_transaction(conn, 1, 'steal', 5.0, '', '', 'u@e.com')


def test_record_transaction_inserts_row():
    conn = _record_conn()
    record_transaction(conn, 1, 'receive', 5.0, 'PO-1', 'note', 'u@e.com')
    insert_sql = conn.execute.call_args_list[0][0][0]
    assert 'INSERT INTO inventory_transaction' in insert_sql


def test_record_transaction_does_not_commit():
    conn = _record_conn()
    record_transaction(conn, 1, 'receive', 1.0, '', '', 'u@e.com')
    conn.commit.assert_not_called()


def test_record_transaction_returns_new_qty():
    conn = _record_conn(new_amount=77.5)
    result = record_transaction(conn, 1, 'receive', 10.0, '', '', 'u@e.com')
    assert result == pytest.approx(77.5)


# ---------------------------------------------------------------------------
# record_transaction — low-stock breach notification
# ---------------------------------------------------------------------------

def test_record_transaction_notifies_on_breach():
    # old_qty = 5 - (-20) = 25 > reorder_point(10) >= new_qty(5) → crossed into breach
    conn = _record_conn(new_amount=5.0, reorder_point=10.0, name='Widget')
    record_transaction(conn, 1, 'issue', 20.0, '', '', 'u@e.com')
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('INSERT INTO notification' in s for s in sqls)


def test_record_transaction_no_notification_when_still_above_reorder_point():
    # old_qty = 50 - (-5) = 55 > reorder_point(10), new_qty(50) still above too
    conn = _record_conn(new_amount=50.0, reorder_point=10.0, name='Widget')
    record_transaction(conn, 1, 'issue', 5.0, '', '', 'u@e.com')
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert not any('INSERT INTO notification' in s for s in sqls)


def test_record_transaction_no_notification_when_already_below_before_transaction():
    # old_qty = 3 - (-2) = 5, not > reorder_point(10) → was already low, no new breach event
    conn = _record_conn(new_amount=3.0, reorder_point=10.0, name='Widget')
    record_transaction(conn, 1, 'issue', 2.0, '', '', 'u@e.com')
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert not any('INSERT INTO notification' in s for s in sqls)


def test_record_transaction_no_notification_when_reorder_point_zero():
    conn = _record_conn(new_amount=0.0, reorder_point=0, name='Widget')
    record_transaction(conn, 1, 'issue', 10.0, '', '', 'u@e.com')
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert not any('INSERT INTO notification' in s for s in sqls)


def test_record_transaction_no_notification_on_receive():
    # A receive only ever increases stock, so it can never cross downward into breach.
    conn = _record_conn(new_amount=15.0, reorder_point=10.0, name='Widget')
    record_transaction(conn, 1, 'receive', 5.0, '', '', 'u@e.com')
    sqls = [c[0][0] for c in conn.execute.call_args_list]
    assert not any('INSERT INTO notification' in s for s in sqls)


def test_record_transaction_notification_targets_purchasing_dept():
    conn = _record_conn(new_amount=5.0, reorder_point=10.0, name='Widget')
    record_transaction(conn, 1, 'issue', 20.0, '', '', 'u@e.com')
    notify_call = next(
        c for c in conn.execute.call_args_list if 'INSERT INTO notification' in c[0][0])
    assert 'Purchasing' in notify_call[0][1]


# ---------------------------------------------------------------------------
# create_product
# ---------------------------------------------------------------------------

def test_create_product_returns_id():
    conn = _conn(fetchone={'id': 42})
    result = create_product(conn, 'Bolt', None, 'B3', 100.0, 50.0,
                            1.25, 'buy', 7, 'ea', 'u@e.com')
    assert result == 42


def test_create_product_rejects_empty_name():
    conn = MagicMock()
    with pytest.raises(ValueError, match='required'):
        create_product(conn, '  ', None, '', 0, 0, 0, 'buy', 0, 'ea', 'u@e.com')


def test_create_product_clamps_negative_amount():
    conn = _conn(fetchone={'id': 1})
    create_product(conn, 'X', None, '', -5.0, 0, 0, 'buy', 0, 'ea', 'u@e.com')
    params = conn.execute.call_args[0][1]
    amount_idx = 3  # INSERT: name, supplier_id, bin, amount, ...
    assert params[amount_idx] == 0.0


def test_create_product_invalid_item_type_defaults_to_buy():
    conn = _conn(fetchone={'id': 1})
    create_product(conn, 'X', None, '', 0, 0, 0, 'invalid', 0, 'ea', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'buy' in params


def test_create_product_empty_uom_defaults_to_ea():
    conn = _conn(fetchone={'id': 1})
    create_product(conn, 'X', None, '', 0, 0, 0, 'buy', 0, '', 'u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'ea' in params


def test_create_product_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_product(conn, 'X', None, '', 0, 0, 0, 'buy', 0, 'ea', 'u@e.com')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# update_product
# ---------------------------------------------------------------------------

def test_update_product_executes_update():
    conn = _conn()
    update_product(conn, 1, 'Bolt', None, 'B2', 25.0, 2.50, 'buy', 3, 'ea')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE product' in sql


def test_update_product_rejects_empty_name():
    conn = MagicMock()
    with pytest.raises(ValueError, match='required'):
        update_product(conn, 1, '', None, '', 0, 0, 'buy', 0, 'ea')


def test_update_product_clamps_negative_reorder():
    conn = _conn()
    update_product(conn, 1, 'X', None, '', -10, 0, 'buy', 0, 'ea')
    params = conn.execute.call_args[0][1]
    assert 0.0 in params


def test_update_product_does_not_commit():
    conn = _conn()
    update_product(conn, 1, 'X', None, '', 0, 0, 'buy', 0, 'ea')
    conn.commit.assert_not_called()
