"""Tests for multi_entity_core — Multi-Company / Multi-Entity (P3-F).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_blanket_po_core.py). Calls into
accounting_core/costing_core (create_journal, post_journal, void_journal,
get_gl_account_map, income_statement, balance_sheet) are patched at their
usage site so tests exercise this module's own logic in isolation.
"""

from unittest.mock import MagicMock, patch

import pytest

from manufacturing.multi_entity_core import (
    IC_GL_CATEGORIES, ensure_multi_entity_tables, get_or_create_base_company,
    list_companies, get_company, create_company, update_company,
    list_user_companies, assign_user_company, revoke_user_company,
    list_company_users, set_ic_account_map, _account_id_by_number,
    list_intercompany_transactions, get_intercompany_transaction,
    create_intercompany_transaction, void_intercompany_transaction,
    _elimination_total, consolidated_income_statement, consolidated_balance_sheet,
)


def _conn(fetchone_results=None, fetchall_results=None):
    """A MagicMock conn whose execute(...) returns one shared cursor mock;
    .fetchone()/.fetchall() replay the given results in call order."""
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── setup ────────────────────────────────────────────────────────────────

def test_ic_gl_categories_includes_all_expected():
    assert set(IC_GL_CATEGORIES) == {
        'ic_receivable', 'ic_payable', 'ic_revenue', 'ic_expense'}


def test_ensure_multi_entity_tables_creates_everything():
    conn = MagicMock()
    ensure_multi_entity_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS company (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS company_user (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS intercompany_transaction (' in c for c in calls)
    assert any('ALTER TABLE gl_account ADD COLUMN IF NOT EXISTS company_id' in c for c in calls)
    assert any('ALTER TABLE gl_journal ADD COLUMN IF NOT EXISTS company_id' in c for c in calls)


def test_get_or_create_base_company_creates_once_then_reuses():
    conn = _conn(fetchone_results=[None, {'id': 3}])
    bp_id = get_or_create_base_company(conn)
    assert bp_id == 3

    conn2 = _conn(fetchone_results=[{'id': 3}])
    bp_id_again = get_or_create_base_company(conn2)
    assert bp_id_again == 3
    assert conn2.execute.call_count == 1


# ── company master ───────────────────────────────────────────────────────

def test_list_companies_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'name': 'Acme US'}]])
    result = list_companies(conn)
    assert result == [{'id': 1, 'name': 'Acme US'}]


def test_get_company_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_company(conn, 999) is None


def test_create_company_raises_without_name():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_company(conn, '', 'Legal', '12-3456789', 'USD', '', '')
    assert conn.execute.call_count == 0


def test_create_company_inserts_and_returns_id():
    conn = _conn(fetchone_results=[{'id': 4}])
    cid = create_company(conn, 'Acme EU', 'Acme Europe GmbH', 'DE123', 'EUR', '1 Main St', 'note')
    assert cid == 4
    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO company' in insert_sql
    assert insert_params[0] == 'Acme EU'


def test_update_company_raises_without_name():
    conn = MagicMock()
    with pytest.raises(ValueError):
        update_company(conn, 1, '', 'Legal', '', 'USD', '', '')
    assert conn.execute.call_count == 0


def test_update_company_updates_row():
    conn = MagicMock()
    update_company(conn, 1, 'Acme EU', 'Acme Europe GmbH', 'DE123', 'EUR', '', '', is_active=False)
    update_sql, update_params = conn.execute.call_args_list[-1][0]
    assert 'UPDATE company SET' in update_sql
    assert update_params[-1] == 1
    assert update_params[-2] is False


# ── user-to-company assignment ──────────────────────────────────────────

def test_list_user_companies_full_access_bypasses_assignment():
    with patch('manufacturing.multi_entity_core.list_companies',
               return_value=[{'id': 1}, {'id': 2}]) as mock_list:
        conn = MagicMock()
        result = list_user_companies(conn, people_id=42, full_access=True)
        assert result == [{'id': 1}, {'id': 2}]
        mock_list.assert_called_once_with(conn)


def test_list_user_companies_filters_by_assignment():
    conn = _conn(fetchall_results=[[{'id': 2, 'name': 'Acme EU'}]])
    result = list_user_companies(conn, people_id=42, full_access=False)
    assert result == [{'id': 2, 'name': 'Acme EU'}]
    sql, params = conn.execute.call_args[0]
    assert 'company_user' in sql
    assert params == (42,)


def test_assign_user_company_inserts():
    conn = MagicMock()
    assign_user_company(conn, 1, 42)
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO company_user' in sql
    assert params[0] == 1 and params[1] == 42


def test_revoke_user_company_deletes():
    conn = MagicMock()
    revoke_user_company(conn, 1, 42)
    sql, params = conn.execute.call_args[0]
    assert 'DELETE FROM company_user' in sql
    assert params == (1, 42)


def test_list_company_users_returns_rows():
    conn = _conn(fetchall_results=[[{'people_id': 42, 'first_name': 'Eric'}]])
    result = list_company_users(conn, 1)
    assert result == [{'people_id': 42, 'first_name': 'Eric'}]


# ── IC account mapping ───────────────────────────────────────────────────

def test_set_ic_account_map_raises_for_unknown_category():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_ic_account_map(conn, 'raw_material', '1300')
    assert conn.execute.call_count == 0


def test_set_ic_account_map_upserts():
    conn = MagicMock()
    set_ic_account_map(conn, 'ic_receivable', '1300')
    sql, params = conn.execute.call_args[0]
    assert 'INSERT INTO gl_account_map' in sql
    assert params[0] == 'ic_receivable'
    assert params[1] == '1300'


def test_account_id_by_number_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert _account_id_by_number(conn, '9999') is None


# ── intercompany transactions ────────────────────────────────────────────

def test_create_intercompany_transaction_raises_same_company():
    conn = MagicMock()
    with patch('manufacturing.multi_entity_core.get_gl_account_map') as mock_map:
        with pytest.raises(ValueError):
            create_intercompany_transaction(conn, 1, 1, 'desc', 100.0, '2026-07-01', 'eric')
        mock_map.assert_not_called()


def test_create_intercompany_transaction_raises_nonpositive_amount():
    conn = MagicMock()
    with patch('manufacturing.multi_entity_core.get_gl_account_map') as mock_map:
        with pytest.raises(ValueError):
            create_intercompany_transaction(conn, 1, 2, 'desc', 0, '2026-07-01', 'eric')
        mock_map.assert_not_called()


def test_create_intercompany_transaction_posts_both_journals_when_mapped():
    conn = _conn(fetchone_results=[
        {'id': 10},  # ic_receivable account id
        {'id': 11},  # ic_payable account id
        {'id': 12},  # ic_revenue account id
        {'id': 13},  # ic_expense account id
        {'id': 99},  # final INSERT ... RETURNING id
    ])
    with patch('manufacturing.multi_entity_core.get_gl_account_map', return_value={
            'ic_receivable': '1300', 'ic_payable': '2300',
            'ic_revenue': '4900', 'ic_expense': '6900'}), \
         patch('manufacturing.multi_entity_core.create_journal',
               side_effect=[501, 502]) as mock_cj, \
         patch('manufacturing.multi_entity_core.post_journal') as mock_pj:
        result = create_intercompany_transaction(
            conn, 1, 2, 'Shared IT costs', 500.0, '2026-07-01', 'eric')

    assert result == {'id': 99, 'unposted': False}
    assert mock_cj.call_count == 2
    assert mock_pj.call_args_list[0][0] == (conn, 501)
    assert mock_pj.call_args_list[1][0] == (conn, 502)

    # from-company journal: DR ic_receivable / CR ic_revenue
    from_lines = mock_cj.call_args_list[0][0][4]
    assert from_lines == [(10, 500.0, 0.0, 'Shared IT costs'),
                           (12, 0.0, 500.0, 'Shared IT costs')]
    # to-company journal: DR ic_expense / CR ic_payable
    to_lines = mock_cj.call_args_list[1][0][4]
    assert to_lines == [(13, 500.0, 0.0, 'Shared IT costs'),
                         (11, 0.0, 500.0, 'Shared IT costs')]

    update_calls = [c for c in conn.execute.call_args_list
                    if 'UPDATE gl_journal SET company_id' in c[0][0]]
    assert len(update_calls) == 2
    assert update_calls[0][0][1] == (1, 501)
    assert update_calls[1][0][1] == (2, 502)

    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO intercompany_transaction' in insert_sql
    assert insert_params[7] == 'posted'


def test_create_intercompany_transaction_stays_unposted_when_unmapped():
    conn = _conn(fetchone_results=[{'id': 55}])
    with patch('manufacturing.multi_entity_core.get_gl_account_map', return_value={}), \
         patch('manufacturing.multi_entity_core.create_journal') as mock_cj, \
         patch('manufacturing.multi_entity_core.post_journal') as mock_pj:
        result = create_intercompany_transaction(
            conn, 1, 2, 'desc', 100.0, '2026-07-01', 'eric')

    assert result == {'id': 55, 'unposted': True}
    mock_cj.assert_not_called()
    mock_pj.assert_not_called()
    insert_params = conn.execute.call_args_list[-1][0][1]
    assert insert_params[5] is None and insert_params[6] is None
    assert insert_params[7] == 'unposted'


def test_create_intercompany_transaction_stays_unposted_when_partially_mapped():
    conn = _conn(fetchone_results=[
        {'id': 10},  # ic_receivable mapped
        {'id': 11},  # ic_payable mapped
        {'id': 77},  # final insert id
    ])
    with patch('manufacturing.multi_entity_core.get_gl_account_map', return_value={
            'ic_receivable': '1300', 'ic_payable': '2300'}), \
         patch('manufacturing.multi_entity_core.create_journal') as mock_cj:
        result = create_intercompany_transaction(
            conn, 1, 2, 'desc', 100.0, '2026-07-01', 'eric')
    assert result == {'id': 77, 'unposted': True}
    mock_cj.assert_not_called()


def test_list_intercompany_transactions_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'from_company_name': 'A'}]])
    assert list_intercompany_transactions(conn) == [{'id': 1, 'from_company_name': 'A'}]


def test_get_intercompany_transaction_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_intercompany_transaction(conn, 999) is None


# ── void ─────────────────────────────────────────────────────────────────

def test_void_intercompany_transaction_voids_both_journals():
    conn = _conn(fetchone_results=[
        {'status': 'posted', 'from_journal_id': 501, 'to_journal_id': 502},
    ])
    with patch('manufacturing.multi_entity_core.void_journal') as mock_vj:
        void_intercompany_transaction(conn, 1)
    assert mock_vj.call_args_list[0][0] == (conn, 501)
    assert mock_vj.call_args_list[1][0] == (conn, 502)
    update_calls = [c for c in conn.execute.call_args_list
                    if "status='voided'" in c[0][0]]
    assert len(update_calls) == 1


def test_void_intercompany_transaction_raises_if_missing():
    conn = _conn(fetchone_results=[None])
    with pytest.raises(ValueError):
        void_intercompany_transaction(conn, 999)


def test_void_intercompany_transaction_raises_if_already_voided():
    conn = _conn(fetchone_results=[
        {'status': 'voided', 'from_journal_id': None, 'to_journal_id': None},
    ])
    with pytest.raises(ValueError):
        void_intercompany_transaction(conn, 1)


# ── elimination / consolidated statements ───────────────────────────────

def test_elimination_total_sums_posted_only():
    conn = _conn(fetchone_results=[{'total': 250.0}])
    assert _elimination_total(conn) == 250.0
    sql = conn.execute.call_args[0][0]
    assert "status = 'posted'" in sql
    assert 'BETWEEN' not in sql


def test_elimination_total_with_date_range():
    conn = _conn(fetchone_results=[{'total': 0.0}])
    _elimination_total(conn, '2026-01-01', '2026-12-31')
    sql, params = conn.execute.call_args[0]
    assert 'BETWEEN' in sql
    assert params == ['2026-01-01', '2026-12-31']


def test_consolidated_income_statement_eliminates_revenue_and_expense():
    with patch('manufacturing.multi_entity_core.income_statement', return_value={
            'sections': {}, 'totals': {}, 'revenue': 1000.0, 'cogs': 200.0,
            'expenses': 300.0, 'gross_profit': 800.0, 'net_income': 500.0}), \
         patch('manufacturing.multi_entity_core._elimination_total', return_value=150.0):
        conn = MagicMock()
        result = consolidated_income_statement(conn, '2026-01-01', '2026-12-31')

    assert result['elimination'] == 150.0
    assert result['revenue_consolidated'] == 850.0
    assert result['expenses_consolidated'] == 150.0
    assert result['net_income_consolidated'] == 500.0


def test_consolidated_balance_sheet_eliminates_assets_and_liabilities():
    with patch('manufacturing.multi_entity_core.balance_sheet', return_value={
            'sections': {}, 'totals': {}, 'assets': 2000.0,
            'liabilities': 800.0, 'equity': 1200.0, 'balanced': True}), \
         patch('manufacturing.multi_entity_core._elimination_total', return_value=300.0):
        conn = MagicMock()
        result = consolidated_balance_sheet(conn, '2026-12-31')

    assert result['elimination'] == 300.0
    assert result['assets_consolidated'] == 1700.0
    assert result['liabilities_consolidated'] == 500.0
