"""Tests for manufacturing/finance_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock, patch

from manufacturing.finance_core import (
    get_finance_dashboard, get_revenue_expense_by_month, get_cash_position,
)

_AP = {
    'open_count': 3, 'overdue_count': 1,
    'total_outstanding': 5000.0, 'total_invoiced': 8000.0, 'total_invoices': 5,
}
_AR = {
    'open_count': 2, 'overdue_count': 0,
    'total_outstanding': 3200.0, 'total_invoiced': 6000.0, 'total_invoices': 4,
}
_JOURNAL_ROW = {
    'id': 1, 'journal_date': '2026-06-01', 'reference': 'JE-001',
    'description': 'Opening entry', 'posted': 1,
    'line_count': 2, 'total_debit': 1000.0,
}


def _conn(journal_rows=None):
    c = MagicMock()
    mock_q = MagicMock()
    mock_q.fetchall.return_value = journal_rows or []
    c.execute.return_value = mock_q
    return c


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_returns_dict():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn())
    assert isinstance(result, dict)


def test_has_ap_key():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn())
    assert 'ap' in result


def test_has_ar_key():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn())
    assert 'ar' in result


def test_has_recent_journals_key():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn())
    assert 'recent_journals' in result


# ---------------------------------------------------------------------------
# AP / AR passthrough
# ---------------------------------------------------------------------------

def test_ap_values_passed_through():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn())
    assert result['ap']['open_count'] == 3
    assert result['ap']['overdue_count'] == 1
    assert result['ap']['total_outstanding'] == 5000.0


def test_ar_values_passed_through():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn())
    assert result['ar']['open_count'] == 2
    assert result['ar']['total_outstanding'] == 3200.0


# ---------------------------------------------------------------------------
# recent_journals
# ---------------------------------------------------------------------------

def test_recent_journals_is_list():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn([_JOURNAL_ROW]))
    assert isinstance(result['recent_journals'], list)


def test_recent_journals_items_are_dicts():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn([_JOURNAL_ROW]))
    assert isinstance(result['recent_journals'][0], dict)


def test_recent_journals_have_journal_date():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn([_JOURNAL_ROW]))
    assert result['recent_journals'][0]['journal_date'] == '2026-06-01'


def test_recent_journals_have_posted_flag():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn([_JOURNAL_ROW]))
    assert result['recent_journals'][0]['posted'] == 1


def test_recent_journals_have_total_debit():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn([_JOURNAL_ROW]))
    assert result['recent_journals'][0]['total_debit'] == 1000.0


def test_recent_journals_empty_when_no_rows():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        result = get_finance_dashboard(_conn([]))
    assert result['recent_journals'] == []


# ---------------------------------------------------------------------------
# SQL sanity
# ---------------------------------------------------------------------------

def test_sql_queries_gl_journal():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        c = _conn()
        get_finance_dashboard(c)
    sql = c.execute.call_args[0][0]
    assert 'gl_journal' in sql


def test_sql_uses_limit_8():
    with patch('manufacturing.finance_core.get_ap_dashboard', return_value=_AP), \
         patch('manufacturing.finance_core.get_ar_dashboard', return_value=_AR):
        c = _conn()
        get_finance_dashboard(c)
    sql = c.execute.call_args[0][0]
    assert 'LIMIT 8' in sql


# ---------------------------------------------------------------------------
# get_revenue_expense_by_month
# ---------------------------------------------------------------------------

_STMT = {'revenue': 1000.0, 'expenses': 400.0, 'cogs': 0.0,
         'gross_profit': 1000.0, 'net_income': 600.0,
         'sections': {}, 'totals': {}}


def test_revenue_expense_returns_requested_number_of_months():
    with patch('manufacturing.finance_core.income_statement', return_value=_STMT):
        result = get_revenue_expense_by_month(_conn(), months=4)
    assert len(result) == 4


def test_revenue_expense_months_ascending():
    with patch('manufacturing.finance_core.income_statement', return_value=_STMT):
        result = get_revenue_expense_by_month(_conn(), months=3)
    months = [r['month'] for r in result]
    assert months == sorted(months)


def test_revenue_expense_passes_through_values():
    with patch('manufacturing.finance_core.income_statement', return_value=_STMT):
        result = get_revenue_expense_by_month(_conn(), months=1)
    assert result[0]['revenue'] == 1000.0
    assert result[0]['expenses'] == 400.0


def test_revenue_expense_calls_income_statement_once_per_month():
    with patch('manufacturing.finance_core.income_statement',
               return_value=_STMT) as mock_stmt:
        get_revenue_expense_by_month(_conn(), months=5)
    assert mock_stmt.call_count == 5


# ---------------------------------------------------------------------------
# get_cash_position
# ---------------------------------------------------------------------------

class _RecordingConn:
    def __init__(self, cash=0.0):
        self.cash = cash
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        q = MagicMock()
        q.fetchone.return_value = {'cash': self.cash}
        return q

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


def test_cash_position_sums_latest_statement_per_active_account():
    conn = _RecordingConn(cash=12500.0)
    result = get_cash_position(conn)
    assert result == 12500.0
    assert "WHERE ba.is_active = 1" in conn.last_sql
    assert "ORDER BY bs.statement_date DESC, bs.id DESC LIMIT 1" in conn.last_sql


def test_cash_position_no_as_of_omits_date_filter():
    conn = _RecordingConn()
    get_cash_position(conn)
    assert "bs.statement_date <= %s" not in conn.last_sql
    assert conn.last_params == []


def test_cash_position_as_of_adds_date_filter():
    conn = _RecordingConn()
    get_cash_position(conn, as_of='2026-06-30')
    assert "bs.statement_date <= %s" in conn.last_sql
    assert conn.last_params == ['2026-06-30']


def test_cash_position_defaults_to_zero_when_no_row():
    conn = MagicMock()
    q = MagicMock()
    q.fetchone.return_value = None
    conn.execute.return_value = q
    assert get_cash_position(conn) == 0.0
