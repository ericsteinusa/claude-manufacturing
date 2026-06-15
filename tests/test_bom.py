"""Tests for bom.would_create_cycle (the BOM cycle guard).

Pure-logic tests — no database. The function operates on an edge list of
``(parent_id, component_id)`` pairs describing existing "parent is built from
component" relationships, and answers whether adding one more edge would close
a cycle.
"""

import pytest

from manufacturing.bom_core import would_create_cycle, explode_quantity


def test_self_reference_is_a_cycle():
    assert would_create_cycle([], 1, 1) is True


def test_empty_graph_allows_any_edge():
    assert would_create_cycle([], 1, 2) is False


def test_direct_reverse_edge_is_a_cycle():
    # 2 is already built from 1; adding 1 built-from 2 closes the loop.
    assert would_create_cycle([(2, 1)], 1, 2) is True


def test_indirect_reverse_edge_is_a_cycle():
    # 1 -> 2 -> 3 exists; adding 3 -> 1 would loop back to the top.
    edges = [(1, 2), (2, 3)]
    assert would_create_cycle(edges, 3, 1) is True


def test_shared_component_is_not_a_cycle():
    # Both 1 and 2 use component 3; 1 may also use 2 — still a DAG.
    edges = [(1, 3), (2, 3)]
    assert would_create_cycle(edges, 1, 2) is False


def test_new_leaf_component_is_allowed():
    edges = [(1, 2), (2, 3)]
    assert would_create_cycle(edges, 3, 4) is False


def test_diamond_does_not_false_positive():
    # 1 -> 2, 1 -> 3, 2 -> 4, 3 -> 4 (diamond). Adding 1 -> 4 is still acyclic.
    edges = [(1, 2), (1, 3), (2, 4), (3, 4)]
    assert would_create_cycle(edges, 1, 4) is False


# ── explode_quantity ────────────────────────────────────────────────────

def test_explode_no_scrap_scales_by_order_qty():
    assert explode_quantity(2.0, 10, 0.0) == 20.0


def test_explode_scrap_inflates_requirement():
    # 5% scrap on 100 units of 1-per = 105.
    assert explode_quantity(1.0, 100, 5.0) == pytest.approx(105.0)


def test_explode_none_scrap_treated_as_zero():
    assert explode_quantity(3.0, 4, None) == 12.0


def test_explode_fractional_qty_per():
    assert explode_quantity(0.5, 3, 0.0) == pytest.approx(1.5)
