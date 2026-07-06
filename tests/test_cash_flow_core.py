"""Tests for cash_flow_core — Cash Flow Statement & 13-Week Forecast (P2-D).

No live database: a fake connection replays canned rows (or dispatches by a
SQL substring for functions issuing several different queries), and
income_statement/get_cash_position are patched at their call sites so this
module's own logic is pinned down independent of accounting_core/
finance_core's internals.
"""

from unittest.mock import patch

from manufacturing.cash_flow_core import (
    FORECAST_WEEKS, INVENTORY_NOTE, FINANCING_NOTE,
    _ar_balance_as_of, _ap_balance_as_of, _depreciation_for_period,
    _capex_for_period, _week_index, _outstanding_by_week,
    get_cash_flow_statement, get_cash_forecast_13wk,
)


# ── fake DB infrastructure ──────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Single canned row-set returned for every execute() call."""
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


class _DispatchConn:
    """Returns canned rows based on a substring match against the SQL."""
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows)
        return _Cursor([])


# ── _ar_balance_as_of / _ap_balance_as_of ───────────────────────────────────

def test_ar_balance_as_of_nets_invoiced_and_paid():
    conn = _Conn(rows=[{'invoiced': 1000.0, 'paid': 400.0}])
    assert _ar_balance_as_of(conn, '2026-06-30') == 600.0
    assert conn.last_params == ['2026-06-30', '2026-06-30']


def test_ar_balance_as_of_excludes_cancelled():
    conn = _Conn(rows=[])
    _ar_balance_as_of(conn, '2026-06-30')
    assert "i.status != 'cancelled'" in conn.last_sql


def test_ap_balance_as_of_nets_invoiced_and_paid():
    conn = _Conn(rows=[{'invoiced': 500.0, 'paid': 500.0}])
    assert _ap_balance_as_of(conn, '2026-06-30') == 0.0


def test_balance_as_of_handles_no_row():
    conn = _Conn(rows=[])
    assert _ar_balance_as_of(conn, '2026-06-30') == 0.0


# ── _depreciation_for_period ─────────────────────────────────────────────────

def test_depreciation_prorates_by_period_fraction():
    asset = {
        'purchase_price': 3650.0, 'salvage_value': 0.0,
        'useful_life_years': 5, 'depreciation_method': 'Straight-Line',
    }
    conn = _Conn(rows=[asset])
    # Straight-line annual = (3650 - 0) / 5 = 730/yr = 2.0/day. A 365-day
    # window (full year) should addback the full annual figure.
    result = _depreciation_for_period(conn, '2026-01-01', '2026-12-31')
    assert result == 730.0


def test_depreciation_excludes_disposed_assets():
    conn = _Conn(rows=[])
    _depreciation_for_period(conn, '2026-01-01', '2026-12-31')
    assert "status != 'Disposed'" in conn.last_sql


def test_depreciation_zero_when_no_assets():
    conn = _Conn(rows=[])
    assert _depreciation_for_period(conn, '2026-01-01', '2026-12-31') == 0.0


# ── _capex_for_period ────────────────────────────────────────────────────────

def test_capex_sums_purchase_price_in_range():
    conn = _Conn(rows=[{'capex': 15000.0}])
    assert _capex_for_period(conn, '2026-01-01', '2026-03-31') == 15000.0
    assert conn.last_params == ['2026-01-01', '2026-03-31']


# ── _week_index ──────────────────────────────────────────────────────────────

def test_week_index_none_for_missing_date():
    assert _week_index(None, __import__('datetime').date(2026, 1, 1), 13) is None


def test_week_index_folds_overdue_into_week_zero():
    import datetime
    start = datetime.date(2026, 7, 6)
    overdue = '2026-06-01'
    assert _week_index(overdue, start, 13) == 0


def test_week_index_buckets_by_seven_day_window():
    import datetime
    start = datetime.date(2026, 7, 6)
    assert _week_index('2026-07-06', start, 13) == 0
    assert _week_index('2026-07-12', start, 13) == 0
    assert _week_index('2026-07-13', start, 13) == 1
    assert _week_index('2026-07-20', start, 13) == 2


def test_week_index_none_beyond_horizon():
    import datetime
    start = datetime.date(2026, 7, 6)
    far_future = (start + datetime.timedelta(days=7 * 13)).isoformat()
    assert _week_index(far_future, start, 13) is None


# ── _outstanding_by_week ─────────────────────────────────────────────────────

def test_outstanding_by_week_only_counts_open_statuses():
    conn = _Conn(rows=[])
    _outstanding_by_week(conn, 'ar_invoice', __import__('datetime').date(2026, 7, 6), 13)
    assert "i.status IN ('open', 'partial', 'overdue')" in conn.last_sql
    assert "ar_payment" in conn.last_sql


def test_outstanding_by_week_derives_ap_payment_table_name():
    conn = _Conn(rows=[])
    _outstanding_by_week(conn, 'ap_invoice', __import__('datetime').date(2026, 7, 6), 13)
    assert "ap_payment" in conn.last_sql


def test_outstanding_by_week_sums_into_correct_buckets():
    import datetime
    start = datetime.date(2026, 7, 6)
    rows = [
        {'due_date': '2026-07-06', 'balance': 100.0},   # week 0
        {'due_date': '2026-06-01', 'balance': 50.0},     # overdue -> week 0
        {'due_date': '2026-07-13', 'balance': 200.0},    # week 1
        {'due_date': '2026-07-06', 'balance': 0.0},      # zero balance, ignored
    ]
    conn = _Conn(rows=rows)
    by_week = _outstanding_by_week(conn, 'ar_invoice', start, 13)
    assert by_week[0] == 150.0
    assert by_week[1] == 200.0
    assert sum(by_week[2:]) == 0.0


# ── get_cash_flow_statement ──────────────────────────────────────────────────

_STMT = {'revenue': 5000.0, 'cogs': 2000.0, 'expenses': 1000.0,
         'gross_profit': 3000.0, 'net_income': 2000.0,
         'sections': {}, 'totals': {}}


def test_cash_flow_statement_operating_totals_net_income_and_adjustments():
    # ar_balance_as_of / ap_balance_as_of / depreciation / capex / cash_position
    # are all separately unit-tested above; here just verify the composition.
    # Production code calls _ar_balance_as_of(date_to) before (date_from) —
    # side_effect order below is [end, start]: AR 1000->1200, AP 500->700.
    with patch('manufacturing.cash_flow_core.income_statement', return_value=_STMT), \
         patch('manufacturing.cash_flow_core._ar_balance_as_of', side_effect=[1200.0, 1000.0]), \
         patch('manufacturing.cash_flow_core._ap_balance_as_of', side_effect=[700.0, 500.0]), \
         patch('manufacturing.cash_flow_core._depreciation_for_period', return_value=100.0), \
         patch('manufacturing.cash_flow_core._capex_for_period', return_value=3000.0), \
         patch('manufacturing.cash_flow_core.get_cash_position', side_effect=[8000.0, 6000.0]):
        result = get_cash_flow_statement(_DispatchConn([]), '2026-01-01', '2026-03-31')

    # ar_change = 1200-1000=200 (increase -> reduces cash, shown as -200)
    # ap_change = 700-500=200 (increase -> adds cash, shown as +200)
    assert result['operating']['ar_change'] == -200.0
    assert result['operating']['ap_change'] == 200.0
    assert result['operating']['net_income'] == 2000.0
    assert result['operating']['depreciation'] == 100.0
    # total = 2000 + 100 - 200 + 200 = 2100
    assert result['operating']['total'] == 2100.0
    assert result['investing']['capex'] == -3000.0
    assert result['investing']['total'] == -3000.0
    assert result['financing']['total'] == 0.0
    assert result['financing']['note'] == FINANCING_NOTE
    # net change = 2100 - 3000 + 0 = -900
    assert result['net_change_in_cash'] == -900.0
    assert result['cash_start'] == 8000.0
    assert result['cash_end'] == 6000.0
    assert result['inventory_note'] == INVENTORY_NOTE


def test_cash_flow_statement_calls_cash_position_with_each_boundary_date():
    with patch('manufacturing.cash_flow_core.income_statement', return_value=_STMT), \
         patch('manufacturing.cash_flow_core._ar_balance_as_of', return_value=0.0), \
         patch('manufacturing.cash_flow_core._ap_balance_as_of', return_value=0.0), \
         patch('manufacturing.cash_flow_core._depreciation_for_period', return_value=0.0), \
         patch('manufacturing.cash_flow_core._capex_for_period', return_value=0.0), \
         patch('manufacturing.cash_flow_core.get_cash_position') as mock_cash:
        mock_cash.side_effect = [111.0, 222.0]
        get_cash_flow_statement(_DispatchConn([]), '2026-01-01', '2026-03-31')

    calls = [c.kwargs.get('as_of') for c in mock_cash.call_args_list]
    assert calls == ['2026-01-01', '2026-03-31']


# ── get_cash_forecast_13wk ───────────────────────────────────────────────────

def test_forecast_returns_thirteen_weeks_starting_from_start_date():
    with patch('manufacturing.cash_flow_core._outstanding_by_week', return_value=[0.0] * 13), \
         patch('manufacturing.cash_flow_core.get_cash_position', return_value=1000.0):
        weeks = get_cash_forecast_13wk(_DispatchConn([]), start_date='2026-07-06')

    assert len(weeks) == FORECAST_WEEKS
    assert weeks[0]['week_start'] == '2026-07-06'
    assert weeks[0]['week_end'] == '2026-07-12'
    assert weeks[1]['week_start'] == '2026-07-13'
    # No activity: balance stays flat at the starting cash position.
    assert all(w['projected_balance'] == 1000.0 for w in weeks)


def test_forecast_accumulates_running_balance():
    ar = [500.0] + [0.0] * 12
    ap = [200.0, 100.0] + [0.0] * 11

    def _fake_outstanding(conn, table, start, total_weeks):
        return ar if table == 'ar_invoice' else ap

    with patch('manufacturing.cash_flow_core._outstanding_by_week',
               side_effect=_fake_outstanding), \
         patch('manufacturing.cash_flow_core.get_cash_position', return_value=1000.0):
        weeks = get_cash_forecast_13wk(_DispatchConn([]), start_date='2026-07-06')

    assert weeks[0]['net_cash_flow'] == 300.0     # 500 - 200
    assert weeks[0]['projected_balance'] == 1300.0
    assert weeks[1]['net_cash_flow'] == -100.0    # 0 - 100
    assert weeks[1]['projected_balance'] == 1200.0
    assert weeks[2]['projected_balance'] == 1200.0  # no further activity


def test_forecast_defaults_start_date_to_today():
    import datetime
    with patch('manufacturing.cash_flow_core._outstanding_by_week', return_value=[0.0] * 13), \
         patch('manufacturing.cash_flow_core.get_cash_position', return_value=0.0):
        weeks = get_cash_forecast_13wk(_DispatchConn([]))
    assert weeks[0]['week_start'] == datetime.date.today().isoformat()
