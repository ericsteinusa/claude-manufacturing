"""
Tests for manufacturing/accounting_core.py — pure unit tests, no Qt, no DB.
"""

import pytest
from unittest.mock import MagicMock

from manufacturing.accounting_core import (
    INVOICE_STATUSES, PAYMENT_METHODS, ACCOUNT_TYPES, DEBIT_NORMAL,
    load_vendors, load_customers,
    get_ap_dashboard, list_ap_invoices, get_ap_invoice,
    create_ap_invoice, update_ap_invoice, set_ap_status,
    list_ap_payments, record_ap_payment,
    get_ar_dashboard, list_ar_invoices, get_ar_invoice,
    create_ar_invoice, update_ar_invoice, set_ar_status,
    record_ar_payment,
    list_accounts, get_account, create_account, update_account, account_balance,
    list_journals, get_journal, get_journal_lines,
    create_journal, post_journal, void_journal,
    trial_balance, income_statement, balance_sheet,
)


def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_invoice_statuses_has_open():
    assert 'open' in INVOICE_STATUSES

def test_invoice_statuses_has_paid():
    assert 'paid' in INVOICE_STATUSES

def test_payment_methods_has_check():
    assert 'Check' in PAYMENT_METHODS

def test_account_types_all_six():
    assert len(ACCOUNT_TYPES) == 6

def test_debit_normal_contains_asset():
    assert 'Asset' in DEBIT_NORMAL

def test_debit_normal_does_not_contain_revenue():
    assert 'Revenue' not in DEBIT_NORMAL


# ---------------------------------------------------------------------------
# Vendor / Customer label helpers
# ---------------------------------------------------------------------------

def _vendor_row(company='Acme', first='', last=''):
    return {'id': 1, 'company_name': company, 'first_name': first, 'last_name': last}


def test_load_vendors_returns_labels():
    conn = _conn(fetchall=[_vendor_row(company='Acme Corp')])
    result = load_vendors(conn)
    assert result[0]['label'] == 'Acme Corp'


def test_load_vendors_falls_back_to_name():
    conn = _conn(fetchall=[_vendor_row(company='', first='Bob', last='Smith')])
    result = load_vendors(conn)
    assert result[0]['label'] == 'Bob Smith'


def test_load_vendors_empty():
    assert load_vendors(_conn(fetchall=[])) == []


def test_load_customers_returns_labels():
    conn = _conn(fetchall=[{'id': 1, 'company_name': 'BuyerCo',
                            'first_name': '', 'last_name': ''}])
    result = load_customers(conn)
    assert result[0]['label'] == 'BuyerCo'


def test_load_customers_falls_back_to_name():
    conn = _conn(fetchall=[{'id': 1, 'company_name': '',
                            'first_name': 'Jane', 'last_name': 'Doe'}])
    result = load_customers(conn)
    assert result[0]['label'] == 'Jane Doe'


# ---------------------------------------------------------------------------
# Accounts Payable — Dashboard
# ---------------------------------------------------------------------------

def _ap_dash(**kw):
    base = {'open_count': 3, 'overdue_count': 1,
            'total_outstanding': 5000.0, 'total_invoiced': 10000.0,
            'total_invoices': 5}
    base.update(kw)
    return base


def test_get_ap_dashboard_returns_dict():
    conn = _conn(fetchone=_ap_dash())
    r = get_ap_dashboard(conn)
    assert r['open_count'] == 3


def test_get_ap_dashboard_fallback_on_none():
    conn = _conn(fetchone=None)
    r = get_ap_dashboard(conn)
    assert r['open_count'] == 0
    assert r['total_outstanding'] == 0.0


# ---------------------------------------------------------------------------
# Accounts Payable — Invoices
# ---------------------------------------------------------------------------

def _ap_inv(**kw):
    base = {'id': 1, 'vendor_id': 2, 'invoice_number': 'INV-001',
            'invoice_date': '2024-01-15', 'due_date': '2024-02-15',
            'amount': 1000.0, 'description': 'Parts', 'status': 'open',
            'created_by': 'user@co.com', 'company_name': 'Acme',
            'first_name': '', 'last_name': '', 'paid': 0.0}
    base.update(kw)
    return base


def test_list_ap_invoices_returns_rows():
    conn = _conn(fetchall=[_ap_inv()])
    result = list_ap_invoices(conn)
    assert result[0]['invoice_number'] == 'INV-001'
    assert result[0]['balance'] == 1000.0


def test_list_ap_invoices_no_filter_no_where():
    conn = _conn(fetchall=[])
    list_ap_invoices(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql


def test_list_ap_invoices_status_filter():
    conn = _conn(fetchall=[])
    list_ap_invoices(conn, status='open')
    sql = conn.execute.call_args[0][0]
    assert 'status' in sql


def test_list_ap_invoices_vendor_filter():
    conn = _conn(fetchall=[])
    list_ap_invoices(conn, vendor_id=3)
    params = conn.execute.call_args[0][1]
    assert 3 in params


def test_list_ap_invoices_date_filter():
    conn = _conn(fetchall=[])
    list_ap_invoices(conn, date_from='2024-01-01', date_to='2024-12-31')
    params = conn.execute.call_args[0][1]
    assert '2024-01-01' in params
    assert '2024-12-31' in params


def test_list_ap_invoices_vendor_label_from_company():
    conn = _conn(fetchall=[_ap_inv(company_name='Acme', first_name='', last_name='')])
    result = list_ap_invoices(conn)
    assert result[0]['vendor_label'] == 'Acme'


def test_get_ap_invoice_returns_dict():
    conn = _conn(fetchone=_ap_inv())
    r = get_ap_invoice(conn, 1)
    assert r is not None
    assert r['invoice_number'] == 'INV-001'
    assert r['balance'] == 1000.0


def test_get_ap_invoice_returns_none():
    assert get_ap_invoice(_conn(fetchone=None), 99) is None


def test_create_ap_invoice_returns_id():
    conn = _conn(fetchone={'id': 5})
    rid = create_ap_invoice(conn, 1, 'INV-002', '2024-01-01', '2024-02-01', 500, 'test', 'u@e.com')
    assert rid == 5


def test_create_ap_invoice_rejects_empty_number():
    with pytest.raises(ValueError):
        create_ap_invoice(_conn(), None, '', '2024-01-01', None, 0, '', '')


def test_create_ap_invoice_defaults_status_open():
    conn = _conn(fetchone={'id': 1})
    create_ap_invoice(conn, None, 'INV-X', '', None, 0, '', '')
    sql = conn.execute.call_args[0][0]
    assert 'open' in sql


def test_create_ap_invoice_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_ap_invoice(conn, None, 'INV-X', '', None, 0, '', '')
    conn.commit.assert_not_called()


def test_update_ap_invoice_executes_update():
    conn = _conn()
    update_ap_invoice(conn, 1, None, 'INV-001', '2024-01-01', None, 1000, '', 'open')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE ap_invoice' in sql


def test_update_ap_invoice_rejects_empty_number():
    with pytest.raises(ValueError):
        update_ap_invoice(_conn(), 1, None, '', '', None, 0, '', 'open')


def test_update_ap_invoice_corrects_bad_status():
    conn = _conn()
    update_ap_invoice(conn, 1, None, 'INV-001', '', None, 0, '', 'bogus')
    params = conn.execute.call_args[0][1]
    assert 'open' in params


def test_update_ap_invoice_does_not_commit():
    conn = _conn()
    update_ap_invoice(conn, 1, None, 'INV-001', '', None, 0, '', 'open')
    conn.commit.assert_not_called()


def test_set_ap_status_executes_update():
    conn = _conn()
    set_ap_status(conn, 1, 'overdue')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE ap_invoice' in sql


def test_set_ap_status_corrects_bad_status():
    conn = _conn()
    set_ap_status(conn, 1, 'bogus')
    params = conn.execute.call_args[0][1]
    assert 'open' in params


# ---------------------------------------------------------------------------
# Accounts Payable — Payments
# ---------------------------------------------------------------------------

def test_list_ap_payments_returns_rows():
    conn = _conn(fetchall=[{'id': 1, 'invoice_id': 1, 'payment_date': '2024-02-01',
                            'amount': 500.0, 'payment_method': 'Check',
                            'reference': 'CHK-100', 'notes': ''}])
    result = list_ap_payments(conn, 1)
    assert result[0]['payment_method'] == 'Check'


def test_record_ap_payment_inserts_and_updates_status():
    calls = []
    def fake_execute(sql, params=None):
        calls.append((sql, params))
        m = MagicMock()
        if 'SUM' in sql:
            m.fetchone.return_value = {'total': 1000.0}
        elif 'SELECT amount' in sql:
            m.fetchone.return_value = {'amount': 1000.0}
        else:
            m.fetchone.return_value = {'id': 1}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    record_ap_payment(conn, 1, '2024-02-01', 1000.0, 'Check', 'CHK-100', '')
    sqls = [c[0] for c in calls]
    assert any('INSERT INTO ap_payment' in s for s in sqls)
    assert any('UPDATE ap_invoice' in s for s in sqls)


def test_record_ap_payment_partial_sets_partial():
    calls = []
    def fake_execute(sql, params=None):
        calls.append((sql, params))
        m = MagicMock()
        if 'SUM' in sql:
            m.fetchone.return_value = {'total': 500.0}
        elif 'SELECT amount' in sql:
            m.fetchone.return_value = {'amount': 1000.0}
        else:
            m.fetchone.return_value = {'id': 1}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    record_ap_payment(conn, 1, '2024-02-01', 500.0, 'Check', '', '')
    update_call = next(c for c in calls if 'UPDATE ap_invoice' in c[0])
    assert 'partial' in update_call[1]


def test_record_ap_payment_corrects_bad_method():
    calls = []
    def fake_execute(sql, params=None):
        calls.append((sql, params))
        m = MagicMock()
        m.fetchone.return_value = {'total': 0.0, 'amount': 1000.0, 'id': 1}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    record_ap_payment(conn, 1, '', 100.0, 'Bitcoin', '', '')
    insert_call = next(c for c in calls if 'INSERT INTO ap_payment' in c[0])
    assert 'Check' in insert_call[1]


def test_record_ap_payment_does_not_commit():
    conn = _conn(fetchone={'total': 0.0, 'amount': 1000.0})
    record_ap_payment(conn, 1, '', 100.0, 'Check', '', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Accounts Receivable — mirror AP tests
# ---------------------------------------------------------------------------

def _ar_inv(**kw):
    base = {'id': 1, 'customer_id': 2, 'invoice_number': 'AR-001',
            'invoice_date': '2024-01-15', 'due_date': '2024-02-15',
            'amount': 2000.0, 'description': 'Service', 'status': 'open',
            'created_by': 'u@co.com', 'company_name': 'BuyerCo',
            'first_name': '', 'last_name': '', 'received': 0.0}
    base.update(kw)
    return base


def test_get_ar_dashboard_returns_dict():
    conn = _conn(fetchone=_ap_dash(open_count=2))
    r = get_ar_dashboard(conn)
    assert r['open_count'] == 2


def test_list_ar_invoices_sets_customer_label():
    conn = _conn(fetchall=[_ar_inv(company_name='BuyerCo')])
    result = list_ar_invoices(conn)
    assert result[0]['customer_label'] == 'BuyerCo'


def test_list_ar_invoices_computes_balance():
    conn = _conn(fetchall=[_ar_inv(amount=2000.0, received=500.0)])
    result = list_ar_invoices(conn)
    assert abs(result[0]['balance'] - 1500.0) < 0.01


def test_get_ar_invoice_returns_dict():
    conn = _conn(fetchone=_ar_inv())
    r = get_ar_invoice(conn, 1)
    assert r is not None
    assert r['invoice_number'] == 'AR-001'


def test_get_ar_invoice_returns_none():
    assert get_ar_invoice(_conn(fetchone=None), 99) is None


def test_create_ar_invoice_rejects_empty_number():
    with pytest.raises(ValueError):
        create_ar_invoice(_conn(), None, '', '', None, 0, '', '')


def test_create_ar_invoice_returns_id():
    conn = _conn(fetchone={'id': 7})
    rid = create_ar_invoice(conn, 1, 'AR-002', '2024-01-01', None, 200, '', 'u@e.com')
    assert rid == 7


def test_update_ar_invoice_executes_update():
    conn = _conn()
    update_ar_invoice(conn, 1, None, 'AR-001', '', None, 0, '', 'open')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE ar_invoice' in sql


def test_set_ar_status_executes_update():
    conn = _conn()
    set_ar_status(conn, 1, 'paid')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE ar_invoice' in sql


def test_record_ar_payment_inserts():
    calls = []
    def fake_execute(sql, params=None):
        calls.append(sql)
        m = MagicMock()
        m.fetchone.return_value = {'total': 2000.0, 'amount': 2000.0, 'id': 1}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    record_ar_payment(conn, 1, '', 2000.0, 'ACH', '', '')
    assert any('INSERT INTO ar_payment' in s for s in calls)


# ---------------------------------------------------------------------------
# General Ledger — Chart of Accounts
# ---------------------------------------------------------------------------

def _acct(**kw):
    base = {'id': 1, 'account_number': '1000', 'account_name': 'Cash',
            'account_type': 'Asset', 'account_sub': 'Current',
            'is_active': 1, 'notes': ''}
    base.update(kw)
    return base


def test_list_accounts_returns_rows():
    conn = _conn(fetchall=[_acct()])
    result = list_accounts(conn)
    assert result[0]['account_name'] == 'Cash'


def test_list_accounts_active_only_filters():
    conn = _conn(fetchall=[])
    list_accounts(conn, active_only=True)
    sql = conn.execute.call_args[0][0]
    assert 'is_active' in sql


def test_list_accounts_type_filter():
    conn = _conn(fetchall=[])
    list_accounts(conn, acct_type='Asset')
    sql = conn.execute.call_args[0][0]
    assert 'account_type' in sql


def test_get_account_returns_row():
    conn = _conn(fetchone=_acct())
    assert get_account(conn, 1)['account_number'] == '1000'


def test_get_account_returns_none():
    assert get_account(_conn(fetchone=None), 99) is None


def test_create_account_returns_id():
    conn = _conn(fetchone={'id': 3})
    rid = create_account(conn, '2000', 'Accounts Payable', 'Liability', 'Current', '')
    assert rid == 3


def test_create_account_rejects_empty_number():
    with pytest.raises(ValueError):
        create_account(_conn(), '', 'Cash', 'Asset', '', '')


def test_create_account_rejects_empty_name():
    with pytest.raises(ValueError):
        create_account(_conn(), '1000', '', 'Asset', '', '')


def test_create_account_defaults_bad_type():
    conn = _conn(fetchone={'id': 1})
    create_account(conn, '9999', 'Misc', 'BadType', '', '')
    params = conn.execute.call_args[0][1]
    assert 'Expense' in params


def test_create_account_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_account(conn, '1000', 'Cash', 'Asset', '', '')
    conn.commit.assert_not_called()


def test_update_account_executes_update():
    conn = _conn()
    update_account(conn, 1, '1000', 'Cash', 'Asset', '', True, '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE gl_account' in sql


def test_update_account_rejects_empty_number():
    with pytest.raises(ValueError):
        update_account(_conn(), 1, '', 'Cash', 'Asset', '', True, '')


def test_account_balance_debit_normal():
    conn = _conn(fetchone={'total_debit': 1000.0, 'total_credit': 200.0})
    bal = account_balance(conn, 1, 'Asset')
    assert abs(bal - 800.0) < 0.01


def test_account_balance_credit_normal():
    conn = _conn(fetchone={'total_debit': 200.0, 'total_credit': 1000.0})
    bal = account_balance(conn, 1, 'Revenue')
    assert abs(bal - 800.0) < 0.01


def test_account_balance_with_as_of():
    conn = _conn(fetchone={'total_debit': 0.0, 'total_credit': 0.0})
    account_balance(conn, 1, 'Asset', as_of='2024-12-31')
    params = conn.execute.call_args[0][1]
    assert '2024-12-31' in params


# ---------------------------------------------------------------------------
# General Ledger — Journal Entries
# ---------------------------------------------------------------------------

def _journal(**kw):
    base = {'id': 1, 'journal_date': '2024-03-01', 'reference': 'JE-001',
            'description': 'Test entry', 'posted': 0,
            'created_by': 'u@co.com', 'created_at': '2024-03-01 10:00:00',
            'line_count': 2, 'total_debit': 1000.0}
    base.update(kw)
    return base


def test_list_journals_returns_rows():
    conn = _conn(fetchall=[_journal()])
    result = list_journals(conn)
    assert result[0]['reference'] == 'JE-001'


def test_list_journals_posted_filter():
    conn = _conn(fetchall=[])
    list_journals(conn, posted=True)
    sql = conn.execute.call_args[0][0]
    assert 'posted' in sql


def test_list_journals_date_filter():
    conn = _conn(fetchall=[])
    list_journals(conn, date_from='2024-01-01', date_to='2024-12-31')
    params = conn.execute.call_args[0][1]
    assert '2024-01-01' in params


def test_get_journal_returns_row():
    conn = _conn(fetchone=_journal())
    assert get_journal(conn, 1)['reference'] == 'JE-001'


def test_get_journal_returns_none():
    assert get_journal(_conn(fetchone=None), 99) is None


def test_get_journal_lines_joins_account():
    conn = _conn(fetchall=[{'id': 1, 'debit': 1000.0, 'credit': 0.0, 'memo': '',
                            'account_id': 1, 'account_number': '1000',
                            'account_name': 'Cash', 'account_type': 'Asset'}])
    lines = get_journal_lines(conn, 1)
    assert lines[0]['account_number'] == '1000'


def test_create_journal_rejects_empty_lines():
    with pytest.raises(ValueError, match='At least one'):
        create_journal(_conn(), '2024-01-01', '', '', [], 'u@e.com')


def test_create_journal_rejects_unbalanced():
    with pytest.raises(ValueError, match='balance'):
        create_journal(_conn(), '2024-01-01', '', '',
                       [(1, 1000.0, 0.0, ''), (2, 0.0, 500.0, '')], 'u@e.com')


def test_create_journal_balanced_returns_id():
    conn = _conn(fetchone={'id': 10})
    jid = create_journal(conn, '2024-01-01', 'JE-001', 'Test',
                         [(1, 1000.0, 0.0, ''), (2, 0.0, 1000.0, '')], 'u@e.com')
    assert jid == 10


def test_create_journal_inserts_lines():
    call_sqls = []
    def fake_execute(sql, params=None):
        call_sqls.append(sql)
        m = MagicMock()
        m.fetchone.return_value = {'id': 1}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    create_journal(conn, '2024-01-01', '', '', [(1, 500.0, 0.0, ''), (2, 0.0, 500.0, '')], '')
    assert sum(1 for s in call_sqls if 'gl_journal_line' in s) == 2


def test_post_journal_sets_posted():
    conn = _conn()
    post_journal(conn, 1)
    sql = conn.execute.call_args[0][0]
    assert 'posted=1' in sql


def test_void_journal_rejects_posted():
    conn = _conn(fetchone={'posted': 1})
    with pytest.raises(ValueError, match='Posted'):
        void_journal(conn, 1)


def test_void_journal_deletes_unposted():
    sqls = []
    def fake_execute(sql, params=None):
        sqls.append(sql)
        m = MagicMock()
        m.fetchone.return_value = {'posted': 0}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    void_journal(conn, 5)
    assert any('DELETE FROM gl_journal_line' in s for s in sqls)
    assert any('DELETE FROM gl_journal' in s for s in sqls)


def test_void_journal_noop_on_missing():
    conn = _conn(fetchone=None)
    void_journal(conn, 99)


# ---------------------------------------------------------------------------
# Financial Reports
# ---------------------------------------------------------------------------

def _acct_list():
    return [
        {'id': 1, 'account_number': '1000', 'account_name': 'Cash',
         'account_type': 'Asset', 'account_sub': '', 'is_active': 1},
        {'id': 2, 'account_number': '4000', 'account_name': 'Revenue',
         'account_type': 'Revenue', 'account_sub': '', 'is_active': 1},
    ]


def test_trial_balance_returns_dict():
    calls = {'n': 0}
    def fake_execute(sql, params=None):
        m = MagicMock()
        if 'gl_account' in sql:
            m.fetchall.return_value = _acct_list()
        else:
            calls['n'] += 1
            m.fetchone.return_value = {'total_debit': 1000.0, 'total_credit': 0.0}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    result = trial_balance(conn)
    assert 'rows' in result
    assert 'balanced' in result


def test_trial_balance_balanced_when_equal():
    def fake_execute(sql, params=None):
        m = MagicMock()
        if 'gl_account' in sql:
            m.fetchall.return_value = [
                {'id': 1, 'account_number': '1000', 'account_name': 'Cash',
                 'account_type': 'Asset'},
                {'id': 2, 'account_number': '3000', 'account_name': 'Equity',
                 'account_type': 'Equity'},
            ]
        else:
            m.fetchone.return_value = {'total_debit': 1000.0, 'total_credit': 1000.0}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    result = trial_balance(conn)
    assert result['balanced']


def test_income_statement_returns_sections():
    def fake_execute(sql, params=None):
        m = MagicMock()
        if 'account_type IN' in sql:
            m.fetchall.return_value = [
                {'id': 1, 'account_number': '4000', 'account_name': 'Sales',
                 'account_type': 'Revenue'},
                {'id': 2, 'account_number': '5000', 'account_name': 'COGS',
                 'account_type': 'COGS'},
            ]
        else:
            m.fetchone.return_value = {'d': 0.0, 'c': 5000.0}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    result = income_statement(conn, '2024-01-01', '2024-12-31')
    assert 'Revenue' in result['sections']
    assert 'net_income' in result


def test_income_statement_net_income_math():
    def fake_execute(sql, params=None):
        m = MagicMock()
        if 'account_type IN' in sql:
            m.fetchall.return_value = [
                {'id': 1, 'account_number': '4000', 'account_name': 'Sales',
                 'account_type': 'Revenue'},
                {'id': 2, 'account_number': '6000', 'account_name': 'Rent',
                 'account_type': 'Expense'},
            ]
        else:
            acct_id = params[0] if params else 0
            if acct_id == 1:
                m.fetchone.return_value = {'d': 0.0, 'c': 10000.0}
            else:
                m.fetchone.return_value = {'d': 3000.0, 'c': 0.0}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    result = income_statement(conn, '2024-01-01', '2024-12-31')
    assert abs(result['revenue'] - 10000.0) < 0.01
    assert abs(result['expenses'] - 3000.0) < 0.01
    assert abs(result['net_income'] - 7000.0) < 0.01


def test_balance_sheet_returns_sections():
    def fake_execute(sql, params=None):
        m = MagicMock()
        if 'account_type IN' in sql:
            m.fetchall.return_value = [
                {'id': 1, 'account_number': '1000', 'account_name': 'Cash',
                 'account_type': 'Asset'},
            ]
        else:
            m.fetchone.return_value = {'total_debit': 5000.0, 'total_credit': 0.0}
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    result = balance_sheet(conn)
    assert 'Asset' in result['sections']
    assert 'balanced' in result
