"""
Tests for contacts_core.py — Qt-free customer and supplier data layer.
"""

from unittest.mock import MagicMock

from manufacturing.contacts_core import (
    contact_label,
    list_customers, get_customer, create_customer, update_customer,
    get_customer_orders,
    list_suppliers, get_supplier, create_supplier, update_supplier,
    get_supplier_orders,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


def _row(**kw):
    base = {
        'id': 1, 'first_name': 'Alice', 'last_name': 'Smith',
        'company_name': '', 'phone_number': '555-1234',
        'address': '1 Main St', 'city': 'Springfield',
        'state': 'IL', 'zip_code': '62701', 'email': 'alice@example.com',
        'created_by': 'test@example.com',
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# contact_label
# ---------------------------------------------------------------------------

def test_label_uses_company_when_set():
    assert contact_label({'company_name': 'ACME', 'first_name': 'Bob'}) == 'ACME'


def test_label_uses_name_when_no_company():
    assert contact_label({'company_name': '', 'first_name': 'Bob',
                           'last_name': 'Jones'}) == 'Bob Jones'


def test_label_first_only():
    assert contact_label({'company_name': None, 'first_name': 'Eve',
                           'last_name': ''}) == 'Eve'


def test_label_fallback_when_all_empty():
    assert contact_label({}) == '(unnamed)'


def test_label_strips_whitespace():
    assert contact_label({'company_name': '  ACME  '}) == 'ACME'


# ---------------------------------------------------------------------------
# list_customers
# ---------------------------------------------------------------------------

def test_list_customers_returns_rows():
    conn = _conn(fetchall=[_row()])
    result = list_customers(conn)
    assert len(result) == 1
    assert result[0]['first_name'] == 'Alice'


def test_list_customers_annotates_label():
    conn = _conn(fetchall=[_row(company_name='ACME')])
    result = list_customers(conn)
    assert result[0]['label'] == 'ACME'


def test_list_customers_empty():
    conn = _conn(fetchall=[])
    assert list_customers(conn) == []


def test_list_customers_search_uses_ilike():
    conn = _conn(fetchall=[])
    list_customers(conn, search='smith')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql
    params = conn.execute.call_args[0][1]
    assert '%smith%' in params


def test_list_customers_no_search_no_params():
    conn = _conn(fetchall=[])
    list_customers(conn)
    params = conn.execute.call_args[0][1]
    assert params == []


def test_list_customers_queries_customer_table():
    conn = _conn(fetchall=[])
    list_customers(conn)
    sql = conn.execute.call_args[0][0]
    assert 'customer' in sql.lower()


# ---------------------------------------------------------------------------
# get_customer
# ---------------------------------------------------------------------------

def test_get_customer_returns_dict():
    conn = _conn(fetchone=_row())
    result = get_customer(conn, 1)
    assert result is not None
    assert result['id'] == 1
    assert 'label' in result


def test_get_customer_returns_none_when_missing():
    conn = _conn(fetchone=None)
    assert get_customer(conn, 999) is None


def test_get_customer_passes_id_as_param():
    conn = _conn(fetchone=_row())
    get_customer(conn, 42)
    params = conn.execute.call_args[0][1]
    assert 42 in params


# ---------------------------------------------------------------------------
# create_customer
# ---------------------------------------------------------------------------

def test_create_customer_returns_id():
    conn = _conn(fetchone={'id': 7})
    cid = create_customer(conn, first_name='Bob', last_name='Jones',
                          created_by='u@e.com')
    assert cid == 7


def test_create_customer_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_customer(conn, first_name='X', created_by='u@e.com')
    conn.commit.assert_not_called()


def test_create_customer_strips_whitespace():
    conn = _conn(fetchone={'id': 1})
    create_customer(conn, first_name='  Bob  ', company_name='  ACME  ',
                    created_by='u@e.com')
    params = conn.execute.call_args[0][1]
    assert 'Bob' in params
    assert 'ACME' in params
    assert '  Bob  ' not in params


def test_create_customer_inserts_into_customer_table():
    conn = _conn(fetchone={'id': 1})
    create_customer(conn, created_by='u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'INSERT INTO customer' in sql


def test_create_customer_handles_missing_fields():
    conn = _conn(fetchone={'id': 1})
    # Should not raise even with no fields beyond created_by
    cid = create_customer(conn, created_by='u@e.com')
    assert cid == 1


# ---------------------------------------------------------------------------
# update_customer
# ---------------------------------------------------------------------------

def test_update_customer_executes_update():
    conn = _conn()
    update_customer(conn, 1, first_name='Bob', last_name='Smith',
                    company_name='', email='')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE customer' in sql.upper() or 'UPDATE' in sql


def test_update_customer_does_not_commit():
    conn = _conn()
    update_customer(conn, 1, first_name='Bob')
    conn.commit.assert_not_called()


def test_update_customer_passes_id():
    conn = _conn()
    update_customer(conn, 99, first_name='X')
    params = conn.execute.call_args[0][1]
    assert 99 in params


# ---------------------------------------------------------------------------
# get_customer_orders
# ---------------------------------------------------------------------------

def test_get_customer_orders_returns_list():
    conn = _conn(fetchall=[
        {'id': 10, 'so_number': 'SO-001', 'status': 'confirmed',
         'order_date': '2026-06-01', 'total': 250.0},
    ])
    result = get_customer_orders(conn, 1)
    assert len(result) == 1
    assert result[0]['so_number'] == 'SO-001'


def test_get_customer_orders_empty():
    conn = _conn(fetchall=[])
    assert get_customer_orders(conn, 1) == []


def test_get_customer_orders_passes_customer_id():
    conn = _conn(fetchall=[])
    get_customer_orders(conn, 42)
    params = conn.execute.call_args[0][1]
    assert 42 in params


def test_get_customer_orders_queries_sales_order():
    conn = _conn(fetchall=[])
    get_customer_orders(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'sales_order' in sql.lower()


# ---------------------------------------------------------------------------
# list_suppliers
# ---------------------------------------------------------------------------

def test_list_suppliers_returns_rows():
    conn = _conn(fetchall=[_row(company_name='GlobalParts Inc')])
    result = list_suppliers(conn)
    assert result[0]['label'] == 'GlobalParts Inc'


def test_list_suppliers_queries_supplier_table():
    conn = _conn(fetchall=[])
    list_suppliers(conn)
    sql = conn.execute.call_args[0][0]
    assert 'supplier' in sql.lower()


def test_list_suppliers_search_works():
    conn = _conn(fetchall=[])
    list_suppliers(conn, search='global')
    params = conn.execute.call_args[0][1]
    assert '%global%' in params


# ---------------------------------------------------------------------------
# get_supplier
# ---------------------------------------------------------------------------

def test_get_supplier_returns_dict():
    conn = _conn(fetchone=_row(company_name='Parts Co'))
    result = get_supplier(conn, 1)
    assert result is not None
    assert result['company_name'] == 'Parts Co'
    assert 'label' in result


def test_get_supplier_returns_none_when_missing():
    conn = _conn(fetchone=None)
    assert get_supplier(conn, 0) is None


# ---------------------------------------------------------------------------
# create_supplier / update_supplier
# ---------------------------------------------------------------------------

def test_create_supplier_returns_id():
    conn = _conn(fetchone={'id': 5})
    sid = create_supplier(conn, company_name='Parts Co', created_by='u@e.com')
    assert sid == 5


def test_create_supplier_inserts_into_supplier_table():
    conn = _conn(fetchone={'id': 1})
    create_supplier(conn, created_by='u@e.com')
    sql = conn.execute.call_args[0][0]
    assert 'INSERT INTO supplier' in sql


def test_create_supplier_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_supplier(conn, created_by='u@e.com')
    conn.commit.assert_not_called()


def test_update_supplier_executes_update():
    conn = _conn()
    update_supplier(conn, 3, company_name='New Name')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE' in sql.upper()


def test_update_supplier_does_not_commit():
    conn = _conn()
    update_supplier(conn, 3)
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# get_supplier_orders
# ---------------------------------------------------------------------------

def test_get_supplier_orders_returns_list():
    conn = _conn(fetchall=[
        {'id': 20, 'po_number': 'PO-001', 'status': 'open',
         'order_date': '2026-06-01', 'total': 1500.0},
    ])
    result = get_supplier_orders(conn, 1)
    assert len(result) == 1
    assert result[0]['po_number'] == 'PO-001'


def test_get_supplier_orders_empty():
    conn = _conn(fetchall=[])
    assert get_supplier_orders(conn, 1) == []


def test_get_supplier_orders_passes_supplier_id():
    conn = _conn(fetchall=[])
    get_supplier_orders(conn, 77)
    params = conn.execute.call_args[0][1]
    assert 77 in params


def test_get_supplier_orders_queries_purchase_order():
    conn = _conn(fetchall=[])
    get_supplier_orders(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'purchase_order' in sql.lower()
