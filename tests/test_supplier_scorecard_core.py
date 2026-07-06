"""Tests for supplier_scorecard_core — Supplier Performance Scorecard (P2-C).

No live database: a fake connection replays canned rows (or dispatches by a
SQL substring for functions that issue several different queries), so the
aggregation/scoring math is pinned down without Postgres.
"""

import json
from decimal import Decimal

from manufacturing.supplier_scorecard_core import (
    ON_TIME_WEIGHT, FILL_RATE_WEIGHT, QUALITY_WEIGHT,
    _supplier_display_name, _qa_supplier_table_exists, _composite_score,
    _on_time_by_supplier, _fill_rate_by_supplier, _quality_by_name_key,
    _monthly_trend, get_supplier_scorecards, get_supplier_scorecard_detail,
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
    """Returns canned rows based on a substring match against the SQL, so
    functions issuing several different queries can be faked regardless of
    call order (same pattern as test_atp_core.py's _DispatchConn)."""
    def __init__(self, routes):
        self.routes = routes  # [(substring, rows), ...] checked in order
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows)
        return _Cursor([])


# ── weights ──────────────────────────────────────────────────────────────

def test_weights_sum_to_one():
    assert round(ON_TIME_WEIGHT + FILL_RATE_WEIGHT + QUALITY_WEIGHT, 6) == 1.0


# ── _supplier_display_name ──────────────────────────────────────────────────

def test_display_name_prefers_company_name():
    assert _supplier_display_name(
        {'company_name': 'Acme Steel', 'first_name': 'Jo', 'last_name': 'Doe'}
    ) == 'Acme Steel'


def test_display_name_falls_back_to_person_name():
    assert _supplier_display_name(
        {'company_name': '', 'first_name': 'Jo', 'last_name': 'Doe'}
    ) == 'Jo Doe'


# ── _qa_supplier_table_exists ───────────────────────────────────────────────

def test_qa_supplier_table_exists_true():
    conn = _Conn(rows=[{'tbl_exists': True}])
    assert _qa_supplier_table_exists(conn) is True


def test_qa_supplier_table_exists_false():
    conn = _Conn(rows=[{'tbl_exists': False}])
    assert _qa_supplier_table_exists(conn) is False


# ── _composite_score ─────────────────────────────────────────────────────────

def test_composite_score_all_three_present():
    score = _composite_score(100.0, 100.0, 100.0)
    assert score == 100.0


def test_composite_score_weighted_average():
    score = _composite_score(90.0, 80.0, 70.0)
    expected = round(90.0 * ON_TIME_WEIGHT + 80.0 * FILL_RATE_WEIGHT
                      + 70.0 * QUALITY_WEIGHT, 1)
    assert score == expected


def test_composite_score_renormalizes_when_quality_missing():
    # No QA data: composite is a pure on-time/fill-rate blend, not penalized
    # by treating the missing metric as 0.
    score = _composite_score(100.0, 100.0, None)
    assert score == 100.0


def test_composite_score_none_when_nothing_available():
    assert _composite_score(None, None, None) is None


# ── _on_time_by_supplier ─────────────────────────────────────────────────────

def test_on_time_by_supplier_filters_received_with_dates():
    conn = _Conn(rows=[])
    _on_time_by_supplier(conn)
    sql = conn.last_sql
    assert "po.status = 'received'" in sql
    assert "po.expected_date IS NOT NULL" in sql
    assert "po.received_date IS NOT NULL" in sql
    assert "po.supplier_id IS NOT NULL" in sql


def test_on_time_by_supplier_applies_date_range_and_supplier_filter():
    conn = _Conn(rows=[])
    _on_time_by_supplier(conn, date_from='2026-01-01', date_to='2026-06-30',
                          supplier_id=7)
    assert conn.last_params == ['2026-01-01', '2026-06-30', 7]


def test_on_time_by_supplier_keys_result_by_supplier_id():
    rows = [{'supplier_id': 3, 'received_count': 4, 'on_time_count': 3}]
    conn = _Conn(rows=rows)
    result = _on_time_by_supplier(conn)
    assert result == {3: rows[0]}


# ── _fill_rate_by_supplier ───────────────────────────────────────────────────

def test_fill_rate_by_supplier_restricts_to_placed_statuses():
    conn = _Conn(rows=[])
    _fill_rate_by_supplier(conn)
    assert "po.status = ANY(%s)" in conn.last_sql
    assert conn.last_params[0] == ['sent', 'partial', 'received']


def test_fill_rate_by_supplier_applies_date_range_and_supplier_filter():
    conn = _Conn(rows=[])
    _fill_rate_by_supplier(conn, date_from='2026-01-01', date_to='2026-06-30',
                            supplier_id=7)
    assert conn.last_params == [
        ['sent', 'partial', 'received'], '2026-01-01', '2026-06-30', 7]


# ── _quality_by_name_key ─────────────────────────────────────────────────────

def test_quality_by_name_key_empty_when_table_absent():
    conn = _DispatchConn([("to_regclass", [{'tbl_exists': False}])])
    assert _quality_by_name_key(conn) == {}


def test_quality_by_name_key_built_from_rows_when_table_present():
    conn = _DispatchConn([
        ("to_regclass", [{'tbl_exists': True}]),
        ("FROM qa_supplier", [
            {'name_key': 'acme steel', 'avg_ppm': 5000, 'material_count': 2},
        ]),
    ])
    result = _quality_by_name_key(conn)
    assert result == {'acme steel': {
        'name_key': 'acme steel', 'avg_ppm': 5000, 'material_count': 2}}


# ── get_supplier_scorecards ──────────────────────────────────────────────────

def _scorecard_conn(supplier_rows, on_time_rows, fill_rows, qa_rows,
                     qa_exists=True):
    routes = [
        ("FROM supplier", supplier_rows),
        ("to_regclass", [{'tbl_exists': qa_exists}]),
        ("FROM purchase_order po\n        WHERE", on_time_rows),
        ("FROM po_item pi", fill_rows),
        ("FROM qa_supplier", qa_rows),
    ]
    return _DispatchConn(routes)


def test_get_supplier_scorecards_computes_percentages_and_composite():
    suppliers = [{'id': 1, 'first_name': '', 'last_name': '',
                  'company_name': 'Acme Steel'}]
    on_time = [{'supplier_id': 1, 'received_count': 4, 'on_time_count': 3}]
    fill = [{'supplier_id': 1, 'qty_ordered': 100, 'qty_received': 90}]
    qa = [{'name_key': 'acme steel', 'avg_ppm': 2000, 'material_count': 1}]
    conn = _scorecard_conn(suppliers, on_time, fill, qa)

    result = get_supplier_scorecards(conn)
    assert len(result) == 1
    row = result[0]
    assert row['supplier_id'] == 1
    assert row['supplier_name'] == 'Acme Steel'
    assert row['on_time_pct'] == 75.0          # 3/4
    assert row['fill_rate_pct'] == 90.0        # 90/100
    assert row['quality_reject_pct'] == 0.2    # 2000 ppm / 10000
    # Same helper _composite_score already pins the weighting formula down
    # (see the dedicated tests above) — reuse it here rather than
    # recomputing the formula, which is exact-float-boundary-fragile.
    assert row['composite_score'] == _composite_score(75.0, 90.0, 100.0 - 0.2)


def test_get_supplier_scorecards_supplier_with_no_activity_has_null_metrics():
    suppliers = [{'id': 2, 'first_name': 'Jo', 'last_name': 'Doe',
                  'company_name': ''}]
    conn = _scorecard_conn(suppliers, [], [], [], qa_exists=False)

    result = get_supplier_scorecards(conn)
    assert len(result) == 1
    row = result[0]
    assert row['on_time_pct'] is None
    assert row['fill_rate_pct'] is None
    assert row['quality_reject_pct'] is None
    assert row['composite_score'] is None


def test_get_supplier_scorecards_sorts_descending_with_none_last():
    suppliers = [
        {'id': 1, 'first_name': '', 'last_name': '', 'company_name': 'Low'},
        {'id': 2, 'first_name': '', 'last_name': '', 'company_name': 'High'},
        {'id': 3, 'first_name': '', 'last_name': '', 'company_name': 'None'},
    ]
    on_time = [
        {'supplier_id': 1, 'received_count': 10, 'on_time_count': 2},   # 20%
        {'supplier_id': 2, 'received_count': 10, 'on_time_count': 9},   # 90%
    ]
    conn = _scorecard_conn(suppliers, on_time, [], [], qa_exists=False)

    result = get_supplier_scorecards(conn)
    assert [r['supplier_name'] for r in result] == ['High', 'Low', 'None']
    assert result[-1]['composite_score'] is None


def test_get_supplier_scorecards_matches_quality_case_insensitively():
    suppliers = [{'id': 1, 'first_name': '', 'last_name': '',
                  'company_name': 'Acme Steel'}]
    qa = [{'name_key': 'acme steel', 'avg_ppm': 1000, 'material_count': 1}]
    conn = _scorecard_conn(suppliers, [], [], qa)

    result = get_supplier_scorecards(conn)
    assert result[0]['quality_reject_pct'] == 0.1
    assert result[0]['quality_sample'] == 1


# ── _monthly_trend ───────────────────────────────────────────────────────────

def test_monthly_trend_param_order():
    conn = _Conn(rows=[])
    _monthly_trend(conn, supplier_id=9, date_from='2026-01-01',
                    date_to='2026-06-30')
    assert conn.last_params == [
        ['sent', 'partial', 'received'], ['sent', 'partial', 'received'],
        9, '2026-01-01', '2026-06-30']


def test_monthly_trend_computes_percentages_per_month():
    rows = [{
        'month': '2026-05', 'po_count': 2,
        'on_time_eligible': 2, 'on_time_count': 1,
        'qty_ordered': 50, 'qty_received': 25,
    }]
    conn = _Conn(rows=rows)
    trend = _monthly_trend(conn, supplier_id=9, date_from=None, date_to=None)
    assert trend == [{
        'month': '2026-05', 'po_count': 2,
        'on_time_pct': 50.0, 'fill_rate_pct': 50.0,
    }]


def test_monthly_trend_fill_rate_is_json_serializable_even_from_decimal_rows():
    """Regression test: re-aggregating an already-summed subquery column
    (item_totals.qty_ordered/qty_received) through an outer SUM()...FILTER
    comes back from psycopg2 as Decimal on the real DB even though the
    underlying columns are plain INTEGER (confirmed against Postgres — a
    single-level SUM doesn't do this, see _fill_rate_by_supplier). The
    trend feeds a Chart.js <script> tag via json.dumps(), which raises
    TypeError on a raw Decimal."""
    rows = [{
        'month': '2026-06', 'po_count': 17,
        'on_time_eligible': 1, 'on_time_count': 1,
        'qty_ordered': Decimal('616'), 'qty_received': Decimal('280'),
    }]
    conn = _Conn(rows=rows)
    trend = _monthly_trend(conn, supplier_id=1, date_from=None, date_to=None)
    assert trend[0]['fill_rate_pct'] == round(280 / 616 * 100, 1)
    json.dumps(trend)  # must not raise


def test_monthly_trend_handles_zero_denominators():
    rows = [{
        'month': '2026-05', 'po_count': 1,
        'on_time_eligible': 0, 'on_time_count': 0,
        'qty_ordered': 0, 'qty_received': 0,
    }]
    conn = _Conn(rows=rows)
    trend = _monthly_trend(conn, supplier_id=9, date_from=None, date_to=None)
    assert trend[0]['on_time_pct'] is None
    assert trend[0]['fill_rate_pct'] is None


# ── get_supplier_scorecard_detail ────────────────────────────────────────────

def test_get_supplier_scorecard_detail_returns_none_for_missing_supplier():
    conn = _scorecard_conn([], [], [], [], qa_exists=False)
    assert get_supplier_scorecard_detail(conn, supplier_id=999) is None


def test_get_supplier_scorecard_detail_applies_default_trend_window():
    suppliers = [{'id': 1, 'first_name': '', 'last_name': '',
                  'company_name': 'Acme Steel'}]
    conn = _scorecard_conn(suppliers, [], [], [], qa_exists=False)

    result = get_supplier_scorecard_detail(conn, supplier_id=1)
    assert result is not None
    assert result['date_from'] is not None
    assert result['date_to'] is not None
    assert result['trend'] == []


def test_get_supplier_scorecard_detail_headline_and_trend_share_same_window():
    """The headline metrics must be computed over the same date window as
    the trend chart, not an all-time figure sitting next to it."""
    suppliers = [{'id': 1, 'first_name': '', 'last_name': '',
                  'company_name': 'Acme Steel'}]
    conn = _scorecard_conn(suppliers, [], [], [], qa_exists=False)
    result = get_supplier_scorecard_detail(conn, supplier_id=1)

    on_time_call_params = next(
        params for sql, params in conn.calls
        if "FROM purchase_order po\n        WHERE" in sql)
    # First two bound params on the on-time query are date_from/date_to (the
    # third is supplier_id) — must match the same window returned alongside
    # the trend.
    assert on_time_call_params[:2] == [result['date_from'], result['date_to']]
