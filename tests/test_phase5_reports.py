"""Tests for Phase 5A — Financial / Production / Inventory dashboards and exports."""

import pytest

from manufacturing.reports_core import (
    financial_dashboard,
    production_dashboard,
    inventory_dashboard,
    to_csv_bytes,
    financial_dashboard_csv,
    inventory_dashboard_csv,
    export_to_excel,
    daily_digest_text,
)


# ── Fake DB ────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


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


# ═══════════════════════════════════════════════════════════════════════════
# 5A — financial_dashboard
# ═══════════════════════════════════════════════════════════════════════════

def _make_fin_conn(
    cash=10000.0, ar_bal=5000.0, revenue=60000.0,
    ap_bal=3000.0, purchases=40000.0, ar_aging_rows=None,
    ap_week=1500.0, gm_rows=None,
):
    responses = [
        [{'cash': cash}],
        [{'b': ar_bal}],
        [{'r': revenue}],
        [{'b': ap_bal}],
        [{'p': purchases}],
        ar_aging_rows or [],
        [{'due': ap_week}],
        gm_rows or [],
    ]
    return _MultiConn(responses)


def test_financial_dashboard_returns_all_keys():
    conn = _make_fin_conn()
    result = financial_dashboard(conn, as_of='2026-06-28')
    for key in ('cash_position', 'dso', 'dpo',
                'ar_aging', 'ap_due_week', 'gross_margin_pct'):
        assert key in result


def test_financial_dashboard_cash_position():
    conn = _make_fin_conn(cash=25000.0)
    assert financial_dashboard(conn, '2026-06-28')['cash_position'] == 25000.0


def test_financial_dashboard_dso_calculation():
    # 30000 AR balance / 120000 revenue × 365 = 91.25
    conn = _make_fin_conn(ar_bal=30000.0, revenue=120000.0)
    result = financial_dashboard(conn, '2026-06-28')
    assert result['dso'] == 91.2


def test_financial_dashboard_dso_zero_when_no_revenue():
    conn = _make_fin_conn(revenue=0.0)
    assert financial_dashboard(conn, '2026-06-28')['dso'] == 0.0


def test_financial_dashboard_dpo_calculation():
    conn = _make_fin_conn(ap_bal=10000.0, purchases=73000.0)
    result = financial_dashboard(conn, '2026-06-28')
    assert result['dpo'] == round(10000 / 73000 * 365, 1)


def test_financial_dashboard_ar_aging_buckets():
    ar_rows = [
        {'balance': 1000.0, 'due_date': '2026-06-28'},  # same day → current
        {'balance': 500.0,  'due_date': '2026-05-28'},  # 31 days → 1_30 or 31_60 depending on as_of
    ]
    conn = _make_fin_conn(ar_aging_rows=ar_rows)
    result = financial_dashboard(conn, as_of='2026-06-28')
    # 2026-06-28 - 2026-06-28 = 0 days → current
    assert result['ar_aging']['current'] == 1000.0
    # 2026-06-28 - 2026-05-28 = 31 days → 31_60
    assert result['ar_aging']['31_60'] == 500.0


def test_financial_dashboard_gross_margin():
    gm = [
        {'account_type': 'Revenue', 'net': 100000.0},
        {'account_type': 'COGS',    'net': -60000.0},   # net is negative (debit > credit)
    ]
    conn = _make_fin_conn(gm_rows=gm)
    result = financial_dashboard(conn, '2026-06-28')
    # revenue=100000, cogs=-(-60000)=60000, margin=(100000-60000)/100000*100=40%
    assert result['gross_margin_pct'] == 40.0


def test_financial_dashboard_zero_gross_margin_when_no_gl():
    conn = _make_fin_conn(gm_rows=[])
    assert financial_dashboard(conn, '2026-06-28')['gross_margin_pct'] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 5A — production_dashboard
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULT_SCRAP = [{'sq': 12.5, 'rq': 3.0, 'sh': 100.0, 'ah': 80.0}]
_DEFAULT_STATUS = [
    {'status': 'open', 'n': 5},
    {'status': 'completed', 'n': 10},
    {'status': 'draft', 'n': 3},
]


def _make_prod_conn(status_rows=None, overdue=2, scrap_row=None):
    responses = [
        status_rows if status_rows is not None else _DEFAULT_STATUS,
        [{'n': overdue}],
        scrap_row if scrap_row is not None else _DEFAULT_SCRAP,
    ]
    return _MultiConn(responses)


def test_production_dashboard_returns_all_keys():
    conn = _make_prod_conn()
    result = production_dashboard(conn)
    for key in ('wos_by_status', 'overdue_count', 'total_scrap_qty',
                'total_rework_qty', 'avg_efficiency_pct', 'open_count'):
        assert key in result


def test_production_dashboard_wos_by_status():
    conn = _make_prod_conn()
    result = production_dashboard(conn)
    assert result['wos_by_status']['open'] == 5
    assert result['wos_by_status']['completed'] == 10


def test_production_dashboard_open_count_alias():
    conn = _make_prod_conn()
    result = production_dashboard(conn)
    assert result['open_count'] == result['wos_by_status'].get('open', 0)


def test_production_dashboard_overdue_count():
    conn = _make_prod_conn(overdue=7)
    assert production_dashboard(conn)['overdue_count'] == 7


def test_production_dashboard_scrap():
    conn = _make_prod_conn(scrap_row=[{'sq': 5.0, 'rq': 1.0, 'sh': 50.0, 'ah': 60.0}])
    result = production_dashboard(conn)
    assert result['total_scrap_qty'] == 5.0
    assert result['total_rework_qty'] == 1.0


def test_production_dashboard_efficiency():
    # std=100, actual=80 → 125%
    conn = _make_prod_conn(scrap_row=[{'sq': 0, 'rq': 0, 'sh': 100.0, 'ah': 80.0}])
    result = production_dashboard(conn)
    assert result['avg_efficiency_pct'] == 125.0


def test_production_dashboard_zero_efficiency_when_no_actual():
    conn = _make_prod_conn(scrap_row=[{'sq': 0, 'rq': 0, 'sh': 100.0, 'ah': 0.0}])
    assert production_dashboard(conn)['avg_efficiency_pct'] == 0.0


def test_production_dashboard_empty_wo_operations():
    conn = _make_prod_conn(scrap_row=[])
    result = production_dashboard(conn)
    assert result['total_scrap_qty'] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 5A — inventory_dashboard
# ═══════════════════════════════════════════════════════════════════════════

def _make_inv_conn(count=50, value=125000.0, alert_count=3,
                   zero_count=8, slow_rows=None, slow_count=4):
    responses = [
        [{'n': count}],
        [{'v': value}],
        [{'alert_count': alert_count, 'zero_count': zero_count}],
        slow_rows or [],
        [{'n': slow_count}],
    ]
    return _MultiConn(responses)


def test_inventory_dashboard_returns_all_keys():
    conn = _make_inv_conn()
    result = inventory_dashboard(conn)
    for key in ('total_sku_count', 'total_inventory_value',
                'alert_count', 'zero_stock_count',
                'slow_mover_count', 'slow_movers'):
        assert key in result


def test_inventory_dashboard_sku_count():
    conn = _make_inv_conn(count=42)
    assert inventory_dashboard(conn)['total_sku_count'] == 42


def test_inventory_dashboard_value():
    conn = _make_inv_conn(value=999999.99)
    assert inventory_dashboard(conn)['total_inventory_value'] == 999999.99


def test_inventory_dashboard_alerts():
    conn = _make_inv_conn(alert_count=5, zero_count=2)
    result = inventory_dashboard(conn)
    assert result['alert_count'] == 5
    assert result['zero_stock_count'] == 2


def test_inventory_dashboard_slow_movers():
    slow = [{'id': 1, 'name': 'Widget A', 'amount': 10.0, 'purchase_price': 5.0}]
    conn = _make_inv_conn(slow_rows=slow, slow_count=1)
    result = inventory_dashboard(conn)
    assert result['slow_mover_count'] == 1
    assert result['slow_movers'][0]['name'] == 'Widget A'


def test_inventory_dashboard_empty_slow_movers():
    conn = _make_inv_conn(slow_rows=[], slow_count=0)
    assert inventory_dashboard(conn)['slow_movers'] == []


# ═══════════════════════════════════════════════════════════════════════════
# 5B — CSV export
# ═══════════════════════════════════════════════════════════════════════════

def test_to_csv_bytes_returns_bytes():
    result = to_csv_bytes(['A', 'B'], [['1', '2'], ['3', '4']])
    assert isinstance(result, bytes)


def test_to_csv_bytes_contains_header():
    result = to_csv_bytes(['Name', 'Value'], [['Foo', '100']]).decode('utf-8')
    assert 'Name' in result
    assert 'Value' in result
    assert 'Foo' in result


def test_financial_dashboard_csv_returns_bytes():
    conn = _make_fin_conn()
    result = financial_dashboard_csv(conn, '2026-06-28')
    assert isinstance(result, bytes)
    text = result.decode('utf-8')
    assert 'Cash Position' in text


def test_inventory_dashboard_csv_returns_bytes():
    conn = _make_inv_conn()
    result = inventory_dashboard_csv(conn)
    assert isinstance(result, bytes)
    assert b'Total SKUs' in result


def test_export_to_excel_returns_bytes():
    sheets = {
        'Summary': (['Name', 'Value'], [['Cash', '10000'], ['DSO', '30']]),
    }
    result = export_to_excel(sheets)
    assert isinstance(result, bytes)
    assert len(result) > 0   # non-empty XLSX


def test_export_to_excel_multiple_sheets():
    sheets = {
        'Financial': (['Metric', 'Value'], [['Cash', '5000']]),
        'Inventory': (['Product', 'Qty'], [['Widget', '100']]),
    }
    result = export_to_excel(sheets)
    # XLSX files start with PK (zip header)
    assert result[:2] == b'PK'


# ═══════════════════════════════════════════════════════════════════════════
# 5B — Daily digest text
# ═══════════════════════════════════════════════════════════════════════════

def _make_digest_conn():
    """Build a MultiConn that satisfies all queries in daily_digest_text."""
    # financial_dashboard: 8 queries
    fin = [
        [{'cash': 50000.0}],
        [{'b': 10000.0}],
        [{'r': 120000.0}],
        [{'b': 8000.0}],
        [{'p': 80000.0}],
        [],   # ar aging rows
        [{'due': 2500.0}],
        [{'account_type': 'Revenue', 'net': 120000.0},
         {'account_type': 'COGS', 'net': -80000.0}],
    ]
    # production_dashboard: 3 queries
    prod = [
        [{'status': 'open', 'n': 3}],
        [{'n': 1}],
        [{'sq': 5.0, 'rq': 0.0, 'sh': 40.0, 'ah': 50.0}],
    ]
    # inventory_dashboard: 5 queries
    inv = [
        [{'n': 100}],
        [{'v': 250000.0}],
        [{'alert_count': 2, 'zero_count': 1}],
        [],
        [{'n': 3}],
    ]
    # po_summary: 3 queries
    po = [
        [{'status': 'open', 'n': 5}, {'status': 'sent', 'n': 2}],
        [{'total': 45000.0}],
        [{'n': 1}],
    ]
    return _MultiConn(fin + prod + inv + po)


def test_daily_digest_text_returns_string():
    conn = _make_digest_conn()
    text = daily_digest_text(conn)
    assert isinstance(text, str)


def test_daily_digest_contains_sections():
    conn = _make_digest_conn()
    text = daily_digest_text(conn)
    assert 'FINANCIAL' in text
    assert 'PRODUCTION' in text
    assert 'INVENTORY' in text
    assert 'PURCHASING' in text


def test_daily_digest_contains_cash_position():
    conn = _make_digest_conn()
    text = daily_digest_text(conn)
    assert '50,000.00' in text


def test_daily_digest_contains_date():
    import datetime
    conn = _make_digest_conn()
    text = daily_digest_text(conn)
    assert datetime.date.today().isoformat() in text
