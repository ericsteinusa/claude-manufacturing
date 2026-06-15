"""Tests for the pure MRP planning core (mrp.compute_levels / plan_orders).

No database: the engine's math is exercised with plain dicts/lists so netting,
BOM explosion (single- and multi-level), scrap inflation and order-type
derivation are pinned down deterministically.
"""

import pytest

from manufacturing.mrp import compute_levels, plan_orders


def _by_id(planned):
    return {p["product_id"]: p for p in planned}


# ── compute_levels ──────────────────────────────────────────────────────

def test_levels_simple_chain():
    levels = compute_levels([1, 2, 3], [(1, 2), (2, 3)])
    assert levels == {1: 0, 2: 1, 3: 2}


def test_levels_diamond_takes_longest_path():
    # 1->2, 1->3, 2->4, 3->4: item 4 sits at level 2 (one below 2 and 3).
    levels = compute_levels([1, 2, 3, 4], [(1, 2), (1, 3), (2, 4), (3, 4)])
    assert levels[4] == 2
    assert levels[1] == 0


def test_levels_default_zero_for_isolated_item():
    assert compute_levels([9], []) == {9: 0}


# ── plan_orders: netting ────────────────────────────────────────────────

def test_buy_order_is_net_of_on_hand():
    products = {1: {"item_type": "buy", "lead_time_days": 5}}
    planned = plan_orders(products, {}, {1: 10}, {1: 3}, {}, {})
    assert len(planned) == 1
    assert planned[0]["product_id"] == 1
    assert planned[0]["order_type"] == "buy"
    assert planned[0]["qty"] == pytest.approx(7)
    assert planned[0]["lead_time_days"] == 5


def test_no_order_when_on_hand_covers_demand():
    products = {1: {"item_type": "buy"}}
    assert plan_orders(products, {}, {1: 10}, {1: 10}, {}, {}) == []


def test_safety_stock_triggers_order():
    products = {1: {"item_type": "buy"}}
    planned = plan_orders(products, {}, {1: 0}, {1: 2}, {}, {1: 5})
    assert _by_id(planned)[1]["qty"] == pytest.approx(3)


def test_scheduled_receipts_reduce_net():
    products = {1: {"item_type": "buy"}}
    planned = plan_orders(products, {}, {1: 10}, {1: 0}, {1: 6}, {})
    assert _by_id(planned)[1]["qty"] == pytest.approx(4)


# ── plan_orders: explosion ──────────────────────────────────────────────

def test_make_item_explodes_to_component_demand():
    products = {
        1: {"item_type": "make", "lead_time_days": 2},
        2: {"item_type": "buy", "lead_time_days": 7},
    }
    bom_lines = {1: [(2, 3.0, 0.0)]}  # one of #1 needs three of #2
    planned = plan_orders(products, bom_lines, {1: 5}, {}, {}, {})
    by = _by_id(planned)
    # Parent planned first, as a make order.
    assert planned[0]["product_id"] == 1
    assert by[1]["order_type"] == "make"
    assert by[1]["qty"] == pytest.approx(5)
    # Component demand = 3 * 5 = 15, bought.
    assert by[2]["order_type"] == "buy"
    assert by[2]["qty"] == pytest.approx(15)


def test_multi_level_explosion_cascades():
    products = {
        1: {"item_type": "make"},
        2: {"item_type": "make"},
        3: {"item_type": "buy"},
    }
    bom_lines = {1: [(2, 2.0, 0.0)], 2: [(3, 4.0, 0.0)]}
    planned = plan_orders(products, bom_lines, {1: 10}, {}, {}, {})
    by = _by_id(planned)
    assert by[1]["qty"] == pytest.approx(10)
    assert by[2]["qty"] == pytest.approx(20)   # 2 * 10
    assert by[3]["qty"] == pytest.approx(80)   # 4 * 20
    assert by[3]["order_type"] == "buy"


def test_explosion_uses_net_not_gross():
    # On-hand of the parent reduces what must be made, and therefore what
    # must be bought for its component.
    products = {1: {"item_type": "make"}, 2: {"item_type": "buy"}}
    bom_lines = {1: [(2, 1.0, 0.0)]}
    planned = plan_orders(products, bom_lines, {1: 10}, {1: 4}, {}, {})
    by = _by_id(planned)
    assert by[1]["qty"] == pytest.approx(6)
    assert by[2]["qty"] == pytest.approx(6)


def test_scrap_inflates_component_demand():
    products = {1: {"item_type": "make"}, 2: {"item_type": "buy"}}
    bom_lines = {1: [(2, 1.0, 10.0)]}  # 10% scrap
    planned = plan_orders(products, bom_lines, {1: 100}, {}, {}, {})
    assert _by_id(planned)[2]["qty"] == pytest.approx(110)


# ── plan_orders: order-type derivation ──────────────────────────────────

def test_item_with_bom_is_make_even_if_flagged_buy():
    products = {1: {"item_type": "buy"}, 2: {"item_type": "buy"}}
    bom_lines = {1: [(2, 1.0, 0.0)]}
    planned = plan_orders(products, bom_lines, {1: 1}, {}, {}, {})
    assert _by_id(planned)[1]["order_type"] == "make"


def test_make_flag_without_bom_still_makes_no_explosion():
    products = {1: {"item_type": "make"}}
    planned = plan_orders(products, {}, {1: 5}, {}, {}, {})
    assert len(planned) == 1
    assert planned[0]["order_type"] == "make"
