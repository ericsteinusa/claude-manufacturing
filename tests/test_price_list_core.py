"""Tests for price_list_core — tiered pricing and customer price resolution."""

from manufacturing.price_list_core import (
    _is_effective, get_price_for_product, get_customer_price,
    get_customer_price_tiers, get_price_tiers_for_price_list,
    create_price_list, add_price_list_line, assign_customer_price_list,
)


# ── fake DB infrastructure (mirrors test_costing_core.py's _MultiConn) ──────

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


class _Conn:
    """Simple fake connection that replays one set of rows for every execute."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)


# ── _is_effective ────────────────────────────────────────────────────────

def test_is_effective_no_dates_always_true():
    assert _is_effective({'effective_date': None, 'expiry_date': None}, '2026-06-15')


def test_is_effective_before_effective_date_false():
    assert not _is_effective(
        {'effective_date': '2026-07-01', 'expiry_date': None}, '2026-06-15')


def test_is_effective_after_expiry_date_false():
    assert not _is_effective(
        {'effective_date': None, 'expiry_date': '2026-06-01'}, '2026-06-15')


def test_is_effective_within_window_true():
    assert _is_effective(
        {'effective_date': '2026-01-01', 'expiry_date': '2026-12-31'}, '2026-06-15')


# ── get_price_for_product (tiered lookup) ───────────────────────────────

def test_get_price_for_product_picks_largest_qualifying_tier():
    conn = _Conn(rows=[{'unit_price': 9.0}])
    price = get_price_for_product(conn, 1, 10, qty=75)
    assert price == 9.0
    # ORDER BY min_qty DESC LIMIT 1 with min_qty <= qty is left to SQL;
    # confirm the qty param was passed through correctly
    assert conn.calls[-1][1] == [1, 10, 75]


def test_get_price_for_product_no_qualifying_tier_returns_none():
    conn = _Conn(rows=[])
    assert get_price_for_product(conn, 1, 10, qty=0.5) is None


# ── get_price_tiers_for_price_list ───────────────────────────────────────

def test_get_price_tiers_groups_by_product_sorted_desc():
    conn = _Conn(rows=[
        {'product_id': 10, 'min_qty': 100.0, 'unit_price': 8.0},
        {'product_id': 10, 'min_qty': 50.0, 'unit_price': 9.0},
        {'product_id': 10, 'min_qty': 1.0, 'unit_price': 10.0},
        {'product_id': 20, 'min_qty': 1.0, 'unit_price': 5.0},
    ])
    tiers = get_price_tiers_for_price_list(conn, 1)
    assert tiers[10] == [(100.0, 8.0), (50.0, 9.0), (1.0, 10.0)]
    assert tiers[20] == [(1.0, 5.0)]


# ── get_customer_price / get_customer_price_tiers ───────────────────────

def test_get_customer_price_no_assignment_returns_none():
    conn = _MultiConn([[]])  # customer/price_list join finds nothing
    assert get_customer_price(conn, 5, 10, qty=1) is None


def test_get_customer_price_with_effective_list_resolves_tier():
    conn = _MultiConn([
        [{'id': 1, 'is_active': True, 'effective_date': None, 'expiry_date': None}],
        [{'unit_price': 10.0}],
    ])
    price = get_customer_price(conn, 5, 10, qty=1)
    assert price == 10.0


def test_get_customer_price_expired_list_returns_none():
    conn = _MultiConn([
        [{'id': 1, 'is_active': True, 'effective_date': None,
          'expiry_date': '2020-01-01'}],
    ])
    price = get_customer_price(conn, 5, 10, qty=1)
    assert price is None


def test_get_customer_price_tiers_no_assignment_returns_empty():
    conn = _MultiConn([[]])
    assert get_customer_price_tiers(conn, 5) == {}


def test_get_customer_price_tiers_with_effective_list():
    conn = _MultiConn([
        [{'id': 1, 'is_active': True, 'effective_date': None, 'expiry_date': None}],
        [{'product_id': 10, 'min_qty': 1.0, 'unit_price': 10.0}],
    ])
    tiers = get_customer_price_tiers(conn, 5)
    assert tiers == {10: [(1.0, 10.0)]}


# ── CRUD basics ──────────────────────────────────────────────────────────

def test_create_price_list_returns_id():
    conn = _Conn(rows=[{'id': 7}])
    pl_id = create_price_list(conn, 'Wholesale', currency='USD', created_by='eric')
    assert pl_id == 7


def test_add_price_list_line_returns_id():
    conn = _Conn(rows=[{'id': 42}])
    line_id = add_price_list_line(conn, 7, 10, unit_price=9.5, min_qty=50)
    assert line_id == 42
    assert conn.calls[-1][1] == [7, 10, 50, 9.5]


def test_assign_customer_price_list_updates_customer():
    conn = _Conn(rows=[])
    assign_customer_price_list(conn, 5, 7)
    assert conn.calls[-1][1] == [7, 5]


def test_assign_customer_price_list_none_unassigns():
    conn = _Conn(rows=[])
    assign_customer_price_list(conn, 5, None)
    assert conn.calls[-1][1] == [None, 5]
