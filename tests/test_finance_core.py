"""Tests for manufacturing/finance_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock, patch

from manufacturing.finance_core import get_finance_dashboard

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
