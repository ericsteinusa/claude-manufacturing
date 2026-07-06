"""Tests for atp_core — Available-to-Promise (ATP) calculations."""

from datetime import date, timedelta

from manufacturing.atp_core import (
    _committed_demand_rows, _open_po_supply_rows, _walk_earliest_available,
    get_atp, get_atp_qty_for_products, check_so_atp,
)


# ── fake DB infrastructure ────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)

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
    functions that issue several different queries (get_atp, check_so_atp)
    can be faked without depending on call order."""
    def __init__(self, routes):
        # routes: [(substring, rows), ...] checked in order
        self.routes = routes
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows)
        return _Cursor([])


TODAY = date(2026, 7, 6)


# ── _committed_demand_rows ──────────────────────────────────────────────────

def test_committed_demand_rows_filters_confirmed():
    conn = _Conn(rows=[])
    _committed_demand_rows(conn, product_id=5)
    assert "so.status = 'confirmed'" in conn.last_sql
    assert conn.last_params[1] == 5


def test_committed_demand_rows_uses_today_plus_30_fallback():
    conn = _Conn(rows=[])
    _committed_demand_rows(conn, product_id=5)
    fallback_param = conn.last_params[0]
    expected = (date.today() + timedelta(days=30)).isoformat()
    assert fallback_param == expected


def test_committed_demand_rows_parses_dates_and_qty():
    conn = _Conn(rows=[{'qty': 4, 'need_date': '2026-07-10'}])
    rows = _committed_demand_rows(conn, product_id=5)
    assert rows == [(date(2026, 7, 10), 4.0)]


# ── _open_po_supply_rows ─────────────────────────────────────────────────────

def test_open_po_supply_rows_filters_sent_partial_and_requires_expected_date():
    conn = _Conn(rows=[])
    _open_po_supply_rows(conn, product_id=5)
    assert "status IN ('sent', 'partial')" in conn.last_sql
    assert "expected_date IS NOT NULL" in conn.last_sql


def test_open_po_supply_rows_drops_zero_or_negative_qty():
    conn = _Conn(rows=[
        {'qty': 0, 'expected_date': '2026-07-10'},
        {'qty': -2, 'expected_date': '2026-07-11'},
        {'qty': 5, 'expected_date': '2026-07-12'},
    ])
    rows = _open_po_supply_rows(conn, product_id=5)
    assert rows == [(date(2026, 7, 12), 5.0)]


# ── _walk_earliest_available ────────────────────────────────────────────────

def test_walk_earliest_available_finds_first_qualifying_date():
    req_d = TODAY
    demand_rows = [(TODAY + timedelta(days=5), 3.0)]
    supply_rows = [(TODAY + timedelta(days=2), 10.0)]
    # on_hand=0, requested=8: at day+2, supply=10, committed=0 -> atp=10 >= 8
    result = _walk_earliest_available(req_d, 0.0, 8.0, demand_rows, supply_rows)
    assert result == (TODAY + timedelta(days=2)).isoformat()


def test_walk_earliest_available_accounts_for_demand_before_supply():
    req_d = TODAY
    demand_rows = [(TODAY + timedelta(days=1), 6.0)]
    supply_rows = [(TODAY + timedelta(days=2), 10.0)]
    # on_hand=0, requested=8: at day+1, atp = 0 + 0 - 6 = -6 (insufficient)
    # at day+2, atp = 0 + 10 - 6 = 4 (still insufficient)
    result = _walk_earliest_available(req_d, 0.0, 8.0, demand_rows, supply_rows)
    assert result is None


def test_walk_earliest_available_returns_none_past_horizon():
    req_d = TODAY
    supply_rows = [(TODAY + timedelta(days=200), 100.0)]
    result = _walk_earliest_available(req_d, 0.0, 8.0, [], supply_rows)
    assert result is None


def test_walk_earliest_available_ignores_dates_at_or_before_req_d():
    req_d = TODAY
    supply_rows = [(TODAY, 10.0)]  # same day as req_d, not "after"
    result = _walk_earliest_available(req_d, 0.0, 8.0, [], supply_rows)
    assert result is None


# ── get_atp ──────────────────────────────────────────────────────────────────

def test_get_atp_formula():
    conn = _DispatchConn([
        ("FROM product WHERE id", [{'on_hand': 10}]),
        ("FROM so_item si JOIN sales_order", [{'qty': 4, 'need_date': '2026-07-01'}]),
        ("FROM po_item pi JOIN purchase_order", [{'qty': 6, 'expected_date': '2026-07-01'}]),
    ])
    result = get_atp(conn, product_id=1, requested_qty=5, requested_date='2026-07-05')
    assert result['on_hand'] == 10
    assert result['committed_qty'] == 4
    assert result['open_po_qty'] == 6
    assert result['atp_qty'] == 12
    assert result['sufficient'] is True


def test_get_atp_insufficient_returns_earliest_available_date():
    conn = _DispatchConn([
        ("FROM product WHERE id", [{'on_hand': 0}]),
        ("FROM so_item si JOIN sales_order", []),
        ("FROM po_item pi JOIN purchase_order",
         [{'qty': 20, 'expected_date': '2026-07-10'}]),
    ])
    result = get_atp(conn, product_id=1, requested_qty=15, requested_date='2026-07-05')
    assert result['sufficient'] is False
    assert result['earliest_available_date'] == '2026-07-10'


def test_get_atp_no_on_hand_row_defaults_to_zero():
    conn = _DispatchConn([
        ("FROM product WHERE id", []),
        ("FROM so_item si JOIN sales_order", []),
        ("FROM po_item pi JOIN purchase_order", []),
    ])
    result = get_atp(conn, product_id=999, requested_qty=1, requested_date='2026-07-05')
    assert result['on_hand'] == 0.0
    assert result['sufficient'] is False


# ── get_atp_qty_for_products ────────────────────────────────────────────────

def test_get_atp_qty_for_products_issues_three_queries():
    conn = _DispatchConn([
        ("FROM product", [{'id': 1, 'on_hand': 5}, {'id': 2, 'on_hand': 0}]),
        ("FROM so_item si JOIN sales_order", [{'product_id': 1, 'qty': 2}]),
        ("FROM po_item pi JOIN purchase_order", [{'product_id': 2, 'qty': 7}]),
    ])
    result = get_atp_qty_for_products(conn, requested_date='2026-07-05')
    assert len(conn.calls) == 3
    assert result[1]['on_hand'] == 5
    assert result[1]['committed_qty'] == 2
    assert result[1]['open_po_qty'] == 0
    assert result[1]['atp_qty'] == 3
    assert result[2]['on_hand'] == 0
    assert result[2]['open_po_qty'] == 7
    assert result[2]['atp_qty'] == 7


def test_get_atp_qty_for_products_merges_product_only_in_demand_or_supply():
    # product 3 has no row in the base product scan (edge case fallback via
    # setdefault) but does show up in the committed-demand aggregate.
    conn = _DispatchConn([
        ("FROM product", [{'id': 1, 'on_hand': 5}]),
        ("FROM so_item si JOIN sales_order", [{'product_id': 3, 'qty': 9}]),
        ("FROM po_item pi JOIN purchase_order", []),
    ])
    result = get_atp_qty_for_products(conn)
    assert result[3]['committed_qty'] == 9
    assert result[3]['on_hand'] == 0.0


# ── check_so_atp ─────────────────────────────────────────────────────────────

class _SoAtpConn:
    """Fakes get_so / get_so_items / get_atp's underlying queries by
    dispatching on SQL substrings, for the check_so_atp integration test.

    Order matters: get_so's query joins `customer` but also contains two
    `FROM so_item si` subqueries (item_count/total), so the more specific
    patterns must be checked before the more general ones."""
    def __init__(self, so_row, item_rows, product_atp):
        self.so_row = so_row
        self.item_rows = item_rows
        self.product_atp = product_atp  # {product_id: on_hand}
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        if 'LEFT JOIN customer' in sql:
            return _Cursor([self.so_row] if self.so_row else [])
        if 'LEFT JOIN product p ON p.id = si.product_id' in sql:
            return _Cursor(self.item_rows)
        if 'FROM product WHERE id' in sql:
            pid = params[0]
            on_hand = self.product_atp.get(pid, 0)
            return _Cursor([{'on_hand': on_hand}])
        if 'so_item si JOIN sales_order' in sql:
            return _Cursor([])
        if 'po_item pi JOIN purchase_order' in sql:
            return _Cursor([])
        return _Cursor([])


def test_check_so_atp_returns_shortfalls_only_for_short_lines():
    so_row = {'id': 1, 'status': 'draft', 'ship_date': '2026-07-10',
              'customer_id': 1, 'total': 0.0, 'item_count': 2}
    item_rows = [
        {'id': 100, 'description': 'Widget', 'product_id': 1,
         'product_name': 'Widget', 'qty': 5, 'unit_price': 1.0, 'line_total': 5.0},
        {'id': 101, 'description': 'Gadget', 'product_id': 2,
         'product_name': 'Gadget', 'qty': 3, 'unit_price': 1.0, 'line_total': 3.0},
    ]
    conn = _SoAtpConn(so_row, item_rows, product_atp={1: 100, 2: 0})
    shortfalls = check_so_atp(conn, so_id=1)
    assert len(shortfalls) == 1
    assert shortfalls[0]['product_id'] == 2
    assert shortfalls[0]['shortfall'] == 3


def test_check_so_atp_skips_lines_without_product_id():
    so_row = {'id': 1, 'status': 'draft', 'ship_date': '2026-07-10',
              'customer_id': 1, 'total': 0.0, 'item_count': 2}
    item_rows = [
        {'id': 100, 'description': 'Custom labor', 'product_id': None,
         'product_name': None, 'qty': 1, 'unit_price': 50.0, 'line_total': 50.0},
    ]
    conn = _SoAtpConn(so_row, item_rows, product_atp={})
    shortfalls = check_so_atp(conn, so_id=1)
    assert shortfalls == []


def test_check_so_atp_returns_empty_when_so_not_found():
    conn = _SoAtpConn(None, [], product_atp={})
    assert check_so_atp(conn, so_id=999) == []
