"""Tests for Phase 3 additions to accounting_core and finance_core."""

import pytest

from manufacturing.accounting_core import (
    AR_AGING_BUCKETS,
    _aging_bucket,
    get_ar_aging, get_dso, get_dpo, generate_dunning_letter,
    list_cost_centers, create_cost_center, update_cost_center,
    get_pl_by_cost_center,
)
from manufacturing.finance_core import (
    get_budget_vs_actual,
    update_budget_line,
    import_bank_transactions,
    auto_match_transactions,
    manual_match_transaction,
    unmatch_transaction,
    get_reconciliation_status,
    get_unmatched_transactions,
    reconcile_statement,
    create_bank_statement,
)


# ── fake DB infrastructure ─────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


class _MultiConn:
    def __init__(self, responses):
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ═══════════════════════════════════════════════════════════════════════════
# 3A — AR Aging
# ═══════════════════════════════════════════════════════════════════════════

def test_aging_bucket_current():
    assert _aging_bucket(0) == 'current'
    assert _aging_bucket(-5) == 'current'


def test_aging_bucket_1_30():
    assert _aging_bucket(1) == '1_30'
    assert _aging_bucket(30) == '1_30'


def test_aging_bucket_31_60():
    assert _aging_bucket(31) == '31_60'
    assert _aging_bucket(60) == '31_60'


def test_aging_bucket_61_90():
    assert _aging_bucket(61) == '61_90'
    assert _aging_bucket(90) == '61_90'


def test_aging_bucket_over_90():
    assert _aging_bucket(91) == 'over_90'
    assert _aging_bucket(365) == 'over_90'


def test_aging_buckets_constant_covers_all_five():
    labels = [b[0] for b in AR_AGING_BUCKETS]
    assert set(labels) == {'current', '1_30', '31_60', '61_90', 'over_90'}


def test_get_ar_aging_returns_structure():
    conn = _Conn(rows=[])
    result = get_ar_aging(conn, as_of='2026-06-28')
    assert result['as_of'] == '2026-06-28'
    assert 'rows' in result
    assert 'totals' in result
    assert 'grand_total' in result
    assert set(result['totals'].keys()) == {b[0] for b, *_ in
                                              [(b,) for b in AR_AGING_BUCKETS]}


def test_get_ar_aging_skips_zero_balance():
    row = {
        'invoice_number': 'AR-001', 'due_date': '2026-05-01',
        'amount': 100.0, 'status': 'open',
        'company_name': 'Acme', 'first_name': '', 'last_name': '',
        'received': 100.0,   # fully paid → balance = 0
    }
    conn = _Conn(rows=[row])
    result = get_ar_aging(conn, as_of='2026-06-28')
    assert result['rows'] == []
    assert result['grand_total'] == 0.0


def test_get_ar_aging_buckets_overdue_invoice():
    # Invoice due 2026-05-28, as_of 2026-06-28 → 31 days overdue → '31_60'
    row = {
        'invoice_number': 'AR-002', 'due_date': '2026-05-28',
        'amount': 500.0, 'status': 'open',
        'company_name': 'Beta Corp', 'first_name': '', 'last_name': '',
        'received': 0.0,
    }
    conn = _Conn(rows=[row])
    result = get_ar_aging(conn, as_of='2026-06-28')
    assert len(result['rows']) == 1
    assert result['rows'][0]['bucket'] == '31_60'
    assert result['rows'][0]['days_overdue'] == 31
    assert result['totals']['31_60'] == 500.0
    assert result['grand_total'] == 500.0


def test_get_ar_aging_uses_company_name_preferentially():
    row = {
        'invoice_number': 'AR-003', 'due_date': '2026-06-28',
        'amount': 200.0, 'status': 'open',
        'company_name': 'Gamma LLC', 'first_name': 'John', 'last_name': 'Doe',
        'received': 0.0,
    }
    conn = _Conn(rows=[row])
    result = get_ar_aging(conn, as_of='2026-06-28')
    assert result['rows'][0]['customer_label'] == 'Gamma LLC'


def test_get_ar_aging_falls_back_to_person_name():
    row = {
        'invoice_number': 'AR-004', 'due_date': '2026-06-28',
        'amount': 200.0, 'status': 'open',
        'company_name': '', 'first_name': 'Jane', 'last_name': 'Smith',
        'received': 0.0,
    }
    conn = _Conn(rows=[row])
    result = get_ar_aging(conn, as_of='2026-06-28')
    assert result['rows'][0]['customer_label'] == 'Jane Smith'


# ── DSO / DPO ──────────────────────────────────────────────────────────────

def test_get_dso_returns_zero_when_no_revenue():
    responses = [
        [{'ar_balance': 10000.0}],
        [{'revenue': 0.0}],
    ]
    conn = _MultiConn(responses)
    assert get_dso(conn) == 0.0


def test_get_dso_computes_correctly():
    # AR balance 30000, revenue 100000 over 90 days → DSO = 30000/100000×90 = 27
    responses = [
        [{'ar_balance': 30000.0}],
        [{'revenue': 100000.0}],
    ]
    conn = _MultiConn(responses)
    assert get_dso(conn, days=90) == 27.0


def test_get_dpo_returns_zero_when_no_purchases():
    responses = [
        [{'ap_balance': 5000.0}],
        [{'purchases': 0.0}],
    ]
    conn = _MultiConn(responses)
    assert get_dpo(conn) == 0.0


def test_get_dpo_computes_correctly():
    responses = [
        [{'ap_balance': 45000.0}],
        [{'purchases': 150000.0}],
    ]
    conn = _MultiConn(responses)
    assert get_dpo(conn, days=90) == 27.0


# ── Dunning letters ────────────────────────────────────────────────────────

def test_generate_dunning_letter_returns_none_for_paid():
    row = {
        'invoice_number': 'AR-001', 'due_date': '2026-05-01',
        'amount': 100.0, 'status': 'paid',
        'company_name': 'Acme', 'first_name': '', 'last_name': '',
        'received': 100.0,
    }
    conn = _Conn(rows=[row])
    assert generate_dunning_letter(conn, inv_id=1) is None


def test_generate_dunning_letter_returns_none_for_zero_balance():
    row = {
        'invoice_number': 'AR-001', 'due_date': '2026-05-01',
        'amount': 100.0, 'status': 'open',
        'company_name': 'Acme', 'first_name': '', 'last_name': '',
        'received': 100.0,
    }
    conn = _Conn(rows=[row])
    assert generate_dunning_letter(conn, inv_id=1) is None


def test_generate_dunning_letter_current():
    row = {
        'invoice_number': 'AR-005', 'due_date': '2026-06-30',
        'amount': 250.0, 'status': 'open',
        'company_name': 'Acme', 'first_name': '', 'last_name': '',
        'received': 0.0,
    }
    conn = _Conn(rows=[row])
    letter = generate_dunning_letter(conn, inv_id=5, as_of='2026-06-28')
    assert letter is not None
    assert 'AR-005' in letter
    assert '250.00' in letter
    assert 'reminder' in letter.lower()


def test_generate_dunning_letter_escalates_over_90():
    row = {
        'invoice_number': 'AR-006', 'due_date': '2026-03-01',
        'amount': 1000.0, 'status': 'overdue',
        'company_name': 'Late Co', 'first_name': '', 'last_name': '',
        'received': 0.0,
    }
    conn = _Conn(rows=[row])
    letter = generate_dunning_letter(conn, inv_id=6, as_of='2026-06-28')
    assert letter is not None
    assert 'FINAL' in letter or 'COLLECTIONS' in letter


# ═══════════════════════════════════════════════════════════════════════════
# 3B — Budget vs. Actual
# ═══════════════════════════════════════════════════════════════════════════

def test_get_budget_vs_actual_returns_empty_for_missing_budget():
    conn = _Conn(rows=[])
    result = get_budget_vs_actual(conn, budget_id=999,
                                   date_from='2026-01-01', date_to='2026-12-31')
    assert result == {}


def test_get_budget_vs_actual_structure():
    responses = [
        # get_budget
        [{'id': 1, 'budget_name': 'FY2026', 'fiscal_year': 2026,
          'status': 'active', 'notes': '', 'created_by': 'admin'}],
        # budget_line query
        [{'id': 1, 'category': 'Revenue', 'description': 'Sales',
          'budgeted_amount': 100000.0, 'gl_account_id': None,
          'account_type': None}],
        # (no GL lookup since gl_account_id is None)
    ]
    conn = _MultiConn(responses)
    result = get_budget_vs_actual(conn, budget_id=1,
                                   date_from='2026-01-01', date_to='2026-06-30')
    assert 'budget' in result
    assert 'lines' in result
    assert 'totals' in result
    assert len(result['lines']) == 1
    assert result['lines'][0]['actual_amount'] == 0.0
    assert result['totals']['budgeted'] == 100000.0


def test_get_budget_vs_actual_with_linked_account():
    responses = [
        # get_budget
        [{'id': 1, 'budget_name': 'FY2026', 'fiscal_year': 2026,
          'status': 'active', 'notes': '', 'created_by': 'admin'}],
        # budget lines with gl_account_id=5, account_type='Expense'
        [{'id': 2, 'category': 'Expense', 'description': 'Utilities',
          'budgeted_amount': 12000.0, 'gl_account_id': 5,
          'account_type': 'Expense'}],
        # GL balance query: debit=8500, credit=0 → actual=8500
        [{'d': 8500.0, 'c': 0.0}],
    ]
    conn = _MultiConn(responses)
    result = get_budget_vs_actual(conn, budget_id=1,
                                   date_from='2026-01-01', date_to='2026-06-30')
    line = result['lines'][0]
    assert line['actual_amount'] == 8500.0
    assert line['variance'] == 3500.0          # budgeted - actual
    assert line['pct_used'] == 70.8


def test_update_budget_line_includes_gl_account_id():
    conn = _Conn()
    update_budget_line(conn, line_id=3, category='Expense',
                       description='Rent', budgeted_amount=5000.0,
                       gl_account_id=7)
    assert 'gl_account_id' in conn.last_sql
    assert conn.last_params[3] == 7


# ═══════════════════════════════════════════════════════════════════════════
# 3C — Bank Reconciliation
# ═══════════════════════════════════════════════════════════════════════════

def test_create_bank_statement_inserts():
    conn = _Conn(rows=[{'id': 4}])
    sid = create_bank_statement(conn, bank_account_id=1,
                                statement_date='2026-06-30',
                                beginning_balance=10000.0,
                                ending_balance=12500.0)
    assert sid == 4
    assert 'INSERT INTO bank_statement' in conn.last_sql


def test_import_bank_transactions_inserts_all():
    conn = _Conn()
    txns = [
        {'trans_date': '2026-06-01', 'amount': 1000.0, 'description': 'Payment'},
        {'trans_date': '2026-06-02', 'amount': -500.0, 'description': 'Check'},
    ]
    count = import_bank_transactions(conn, bank_account_id=1,
                                      statement_id=2, transactions=txns)
    assert count == 2
    inserts = [s for s, _ in conn.calls if 'INSERT INTO bank_transaction' in s]
    assert len(inserts) == 2


def test_import_bank_transactions_returns_zero_on_empty():
    conn = _Conn()
    count = import_bank_transactions(conn, 1, None, [])
    assert count == 0
    assert conn.calls == []


def test_auto_match_transactions_matches_single_candidate():
    # 1 unmatched txn; GL candidate query returns exactly 1 result
    responses = [
        # unmatched transactions
        [{'id': 10, 'trans_date': '2026-06-05', 'amount': 500.0}],
        # GL candidates (exactly 1)
        [{'id': 99}],
        # UPDATE bank_transaction
        [],
    ]
    conn = _MultiConn(responses)
    result = auto_match_transactions(conn, statement_id=2)
    assert result['matched'] == 1
    assert result['skipped'] == 0
    assert result['ambiguous'] == 0
    update_calls = [s for s, _ in conn.calls if 'UPDATE bank_transaction' in s]
    assert len(update_calls) == 1


def test_auto_match_transactions_skips_when_no_candidates():
    responses = [
        [{'id': 10, 'trans_date': '2026-06-05', 'amount': 500.0}],
        [],   # no GL candidates
    ]
    conn = _MultiConn(responses)
    result = auto_match_transactions(conn, statement_id=2)
    assert result['skipped'] == 1
    assert result['matched'] == 0


def test_auto_match_transactions_marks_ambiguous_when_multiple():
    responses = [
        [{'id': 10, 'trans_date': '2026-06-05', 'amount': 500.0}],
        [{'id': 99}, {'id': 100}],   # 2 candidates → ambiguous
    ]
    conn = _MultiConn(responses)
    result = auto_match_transactions(conn, statement_id=2)
    assert result['ambiguous'] == 1
    assert result['matched'] == 0


def test_manual_match_transaction():
    conn = _Conn()
    manual_match_transaction(conn, bank_txn_id=5, gl_line_id=88)
    assert 'matched_gl_line_id=%s' in conn.last_sql
    assert conn.last_params == [88, 5]


def test_unmatch_transaction_clears_match():
    conn = _Conn()
    unmatch_transaction(conn, bank_txn_id=5)
    assert 'matched_gl_line_id=NULL' in conn.last_sql
    assert 'cleared=FALSE' in conn.last_sql
    assert conn.last_params == [5]


def test_get_reconciliation_status_returns_counts():
    conn = _Conn(rows=[{
        'total': 10, 'cleared': 7, 'uncleared': 3,
        'total_amount': 5000.0, 'cleared_amount': 3500.0,
    }])
    status = get_reconciliation_status(conn, statement_id=1)
    assert status['total'] == 10
    assert status['cleared'] == 7
    assert status['uncleared'] == 3


def test_get_reconciliation_status_returns_zeros_on_no_rows():
    conn = _Conn(rows=[])
    status = get_reconciliation_status(conn, statement_id=999)
    assert status['total'] == 0
    assert status['cleared'] == 0


def test_get_unmatched_transactions_filters_by_statement():
    conn = _Conn(rows=[])
    get_unmatched_transactions(conn, statement_id=3)
    assert 'statement_id=%s' in conn.last_sql
    assert 'matched_gl_line_id IS NULL' in conn.last_sql
    assert conn.last_params == [3]


def test_reconcile_statement_returns_false_when_uncleared_remain():
    # get_reconciliation_status returns 3 uncleared
    conn = _Conn(rows=[{
        'total': 5, 'cleared': 2, 'uncleared': 3,
        'total_amount': 1000.0, 'cleared_amount': 400.0,
    }])
    result = reconcile_statement(conn, statement_id=1,
                                  reconciled_by='admin@example.com')
    assert result is False
    update_calls = [s for s, _ in conn.calls if 'UPDATE bank_statement' in s]
    assert len(update_calls) == 0


def test_reconcile_statement_marks_reconciled_when_all_cleared():
    responses = [
        [{'total': 5, 'cleared': 5, 'uncleared': 0,
          'total_amount': 1000.0, 'cleared_amount': 1000.0}],
        [],   # UPDATE bank_statement
    ]
    conn = _MultiConn(responses)
    result = reconcile_statement(conn, statement_id=2,
                                  reconciled_by='admin@example.com')
    assert result is True
    update_calls = [s for s, _ in conn.calls if 'UPDATE bank_statement' in s]
    assert len(update_calls) == 1
    assert 'Reconciled' in conn.last_sql


# ═══════════════════════════════════════════════════════════════════════════
# 3D — GL Segment Codes / Cost Centers
# ═══════════════════════════════════════════════════════════════════════════

def test_list_cost_centers_active_only_adds_where():
    conn = _Conn(rows=[])
    list_cost_centers(conn, active_only=True)
    assert 'is_active = TRUE' in conn.last_sql


def test_list_cost_centers_all_omits_where():
    conn = _Conn(rows=[])
    list_cost_centers(conn, active_only=False)
    assert 'WHERE' not in conn.last_sql


def test_create_cost_center_uppercases_code():
    conn = _Conn(rows=[{'id': 1}])
    create_cost_center(conn, code='mfg', name='Manufacturing')
    assert conn.last_params[0] == 'MFG'


def test_create_cost_center_requires_code_and_name():
    conn = _Conn()
    with pytest.raises(ValueError):
        create_cost_center(conn, code='', name='Test')
    with pytest.raises(ValueError):
        create_cost_center(conn, code='TEST', name='')


def test_create_cost_center_returns_id():
    conn = _Conn(rows=[{'id': 7}])
    cc_id = create_cost_center(conn, 'ADMIN', 'Administration', dept_key='admin')
    assert cc_id == 7
    assert 'INSERT INTO cost_center' in conn.last_sql
    assert conn.last_params == ['ADMIN', 'Administration', 'admin']


def test_update_cost_center_requires_code_and_name():
    conn = _Conn()
    with pytest.raises(ValueError):
        update_cost_center(conn, 1, code='', name='X')


def test_update_cost_center_issues_update():
    conn = _Conn()
    update_cost_center(conn, cc_id=3, code='eng', name='Engineering',
                       dept_key='engineering', is_active=True)
    assert conn.last_sql.strip().upper().startswith('UPDATE COST_CENTER')
    assert conn.last_params[0] == 'ENG'
    assert conn.last_params[-1] == 3


def test_get_pl_by_cost_center_queries_period():
    conn = _Conn(rows=[])
    get_pl_by_cost_center(conn, '2026-01-01', '2026-06-30')
    assert conn.last_params == ['2026-01-01', '2026-06-30']
    assert 'cost_center' in conn.last_sql.lower()


def test_get_pl_by_cost_center_computes_net_income():
    rows = [
        {'cc_code': 'MFG', 'cc_name': 'Manufacturing',
         'account_type': 'Revenue', 'total_debit': 0.0, 'total_credit': 50000.0},
        {'cc_code': 'MFG', 'cc_name': 'Manufacturing',
         'account_type': 'COGS', 'total_debit': 30000.0, 'total_credit': 0.0},
        {'cc_code': 'MFG', 'cc_name': 'Manufacturing',
         'account_type': 'Expense', 'total_debit': 8000.0, 'total_credit': 0.0},
    ]
    conn = _Conn(rows=rows)
    result = get_pl_by_cost_center(conn, '2026-01-01', '2026-06-30')
    assert len(result) == 1
    seg = result[0]
    assert seg['revenue'] == 50000.0
    assert seg['cogs'] == 30000.0
    assert seg['gross_profit'] == 20000.0
    assert seg['net_income'] == 12000.0   # 20000 - 8000
