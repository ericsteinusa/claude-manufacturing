"""Tests for discount_core — promotion resolution and CRUD."""

import pytest

from manufacturing.discount_core import (
    _is_effective, _validate, apply_discount, find_applicable_promotions,
    get_best_price, get_promotion_tiers_for_customer, create_promotion,
    update_promotion,
)


# ── fake DB infrastructure (mirrors test_price_list_core.py) ───────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Simple fake connection that replays one set of rows for every execute."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)


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


# ── _is_effective / _validate ───────────────────────────────────────────────

def test_is_effective_no_dates_always_true():
    assert _is_effective({'start_date': None, 'end_date': None}, '2026-06-15')


def test_is_effective_before_start_date_false():
    assert not _is_effective(
        {'start_date': '2026-07-01', 'end_date': None}, '2026-06-15')


def test_is_effective_after_end_date_false():
    assert not _is_effective(
        {'start_date': None, 'end_date': '2026-06-01'}, '2026-06-15')


def test_validate_rejects_unknown_type():
    with pytest.raises(ValueError):
        _validate('unknown', 10)


def test_validate_rejects_negative_value():
    with pytest.raises(ValueError):
        _validate('percent', -5)


def test_validate_rejects_percent_over_100():
    with pytest.raises(ValueError):
        _validate('percent', 150)


def test_validate_allows_large_fixed_value():
    _validate('fixed', 500)  # no raise — a $500 fixed discount is legal


# ── apply_discount ───────────────────────────────────────────────────────

def test_apply_discount_percent():
    assert apply_discount(100.0, 'percent', 10) == 90.0


def test_apply_discount_fixed():
    assert apply_discount(100.0, 'fixed', 15) == 85.0


def test_apply_discount_fixed_floors_at_zero():
    assert apply_discount(10.0, 'fixed', 50) == 0.0


# ── find_applicable_promotions ──────────────────────────────────────────

def test_find_applicable_promotions_passes_qty_param():
    conn = _Conn(rows=[])
    find_applicable_promotions(conn, customer_id=None, product_id=None, qty=5)
    # qty is always the first bound param
    assert conn.calls[-1][1][0] == 5


def test_find_applicable_promotions_scopes_to_product_and_customer():
    conn = _Conn(rows=[{'id': 1, 'discount_type': 'percent', 'discount_value': 10}])
    result = find_applicable_promotions(conn, customer_id=5, product_id=10, qty=2)
    assert result == [{'id': 1, 'discount_type': 'percent', 'discount_value': 10}]
    assert 10 in conn.calls[-1][1]
    assert 5 in conn.calls[-1][1]


# ── get_best_price ───────────────────────────────────────────────────────

def test_get_best_price_no_promotions_returns_base():
    conn = _Conn(rows=[])
    price, promo = get_best_price(conn, 5, 10, 1, 100.0)
    assert price == 100.0
    assert promo is None


def test_get_best_price_picks_lowest_final_price():
    conn = _Conn(rows=[
        {'discount_type': 'percent', 'discount_value': 10, 'name': 'Ten Off'},
        {'discount_type': 'fixed', 'discount_value': 50, 'name': 'Fifty Off'},
    ])
    price, promo = get_best_price(conn, 5, 10, 1, 100.0)
    # 10% off -> 90.0, $50 off -> 50.0 -> fixed wins
    assert price == 50.0
    assert promo['name'] == 'Fifty Off'


# ── get_promotion_tiers_for_customer ────────────────────────────────────

def test_get_promotion_tiers_groups_general_promo_under_all_key():
    conn = _Conn(rows=[
        {'product_id': None, 'min_qty': 1.0, 'discount_type': 'percent',
         'discount_value': 5.0, 'name': 'Storewide'},
        {'product_id': 10, 'min_qty': 20.0, 'discount_type': 'fixed',
         'discount_value': 2.0, 'name': 'Bulk Deal'},
    ])
    tiers = get_promotion_tiers_for_customer(conn, 5)
    assert tiers['__all__'] == [(1.0, 'percent', 5.0, 'Storewide')]
    assert tiers[10] == [(20.0, 'fixed', 2.0, 'Bulk Deal')]


# ── CRUD basics ──────────────────────────────────────────────────────────

def test_create_promotion_returns_id():
    conn = _Conn(rows=[{'id': 9}])
    promo_id = create_promotion(conn, 'Spring Sale', discount_type='percent',
                                discount_value=15, created_by='eric')
    assert promo_id == 9


def test_create_promotion_rejects_bad_discount():
    conn = _Conn(rows=[{'id': 9}])
    with pytest.raises(ValueError):
        create_promotion(conn, 'Bad', discount_type='percent', discount_value=200)


def test_create_promotion_requires_name():
    conn = _Conn(rows=[{'id': 9}])
    with pytest.raises(ValueError):
        create_promotion(conn, '   ')


def test_update_promotion_validates_new_discount_value():
    conn = _MultiConn([
        [{'discount_type': 'percent', 'discount_value': 10}],  # get_promotion lookup
    ])
    with pytest.raises(ValueError):
        update_promotion(conn, 1, discount_value=250)


def test_update_promotion_ignores_unknown_fields():
    conn = _Conn(rows=[])
    update_promotion(conn, 1, bogus_field='x')
    assert conn.calls == []  # no-op, nothing to update
