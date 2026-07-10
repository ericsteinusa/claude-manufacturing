"""Tests for recipe_core — Recipe / Formula Management."""

import pytest

from manufacturing import recipe_core
from manufacturing.recipe_core import (
    create_recipe, add_ingredient, activate_recipe, scale_recipe,
    release_batch_wo, RECIPE_STATUSES,
)


# ── fake DB infrastructure (mirrors test_skills_matrix_core.py) ────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
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


# ── create_recipe ────────────────────────────────────────────────────────

def test_create_recipe_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    recipe_id = create_recipe(conn, 10, 'Syrup Base', batch_size=500.0, batch_uom='kg')
    assert recipe_id == 1


def test_create_recipe_requires_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_recipe(conn, 10, '   ', batch_size=500.0)


def test_create_recipe_requires_positive_batch_size():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_recipe(conn, 10, 'Syrup Base', batch_size=0)


def test_create_recipe_validates_yield_pct_range():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_recipe(conn, 10, 'Syrup Base', batch_size=500.0, yield_pct=150)
    with pytest.raises(ValueError):
        create_recipe(conn, 10, 'Syrup Base', batch_size=500.0, yield_pct=0)


def test_create_recipe_defaults_full_yield():
    conn = _Conn(rows=[{'id': 1}])
    create_recipe(conn, 10, 'Syrup Base', batch_size=500.0)
    _, params = conn.calls[-1]
    assert params[-2] == 100.0  # yield_pct


# ── add_ingredient ───────────────────────────────────────────────────────

def test_add_ingredient_requires_positive_qty():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_ingredient(conn, 1, component_id=5, qty_per_batch=0)


def test_add_ingredient_returns_id():
    conn = _Conn(rows=[{'id': 9}])
    ing_id = add_ingredient(conn, 1, component_id=5, qty_per_batch=320.0, uom='kg')
    assert ing_id == 9


# ── activate_recipe ──────────────────────────────────────────────────────

def test_activate_recipe_raises_when_missing(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: None)
    with pytest.raises(ValueError, match='No recipe'):
        activate_recipe(_Conn(), recipe_id=1)


def test_activate_recipe_raises_when_no_ingredients(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 1, 'product_id': 10, 'ingredients': [],
    })
    with pytest.raises(ValueError, match='no ingredients'):
        activate_recipe(_Conn(), recipe_id=1)


def test_activate_recipe_supersedes_previous_active(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 2, 'product_id': 10, 'ingredients': [{'id': 1}],
    })
    conn = _Conn(rows=[])
    activate_recipe(conn, recipe_id=2)
    supersede_calls = [c for c in conn.calls if "SET status = 'superseded'" in c[0]]
    activate_calls = [c for c in conn.calls if "SET status = 'active'" in c[0]]
    assert len(supersede_calls) == 1
    assert supersede_calls[0][1] == [10, 2]
    assert len(activate_calls) == 1
    assert activate_calls[0][1] == [2]


# ── scale_recipe ─────────────────────────────────────────────────────────

def test_scale_recipe_raises_when_missing(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: None)
    with pytest.raises(ValueError, match='No recipe'):
        scale_recipe(_Conn(), recipe_id=1, target_qty=100)


def test_scale_recipe_requires_positive_target(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 1, 'batch_size': 500.0, 'yield_pct': 100.0, 'ingredients': [],
    })
    with pytest.raises(ValueError, match='greater than zero'):
        scale_recipe(_Conn(), recipe_id=1, target_qty=0)


def test_scale_recipe_full_yield_scales_linearly(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 1, 'batch_size': 500.0, 'yield_pct': 100.0,
        'ingredients': [
            {'component_id': 1, 'component_name': 'Sugar', 'qty_per_batch': 320.0, 'uom': 'kg'},
            {'component_id': 2, 'component_name': 'Water', 'qty_per_batch': 180.0, 'uom': 'kg'},
        ],
    })
    scaled = scale_recipe(_Conn(), recipe_id=1, target_qty=1000.0)  # 2x batch
    sugar = next(s for s in scaled if s['component_id'] == 1)
    water = next(s for s in scaled if s['component_id'] == 2)
    assert sugar['qty_needed'] == 640.0
    assert water['qty_needed'] == 360.0


def test_scale_recipe_accounts_for_yield_loss(monkeypatch):
    # 80% yield: to get 400 kg good output from a 500 kg batch recipe,
    # need MORE than one batch's worth of inputs (since 20% is lost).
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 1, 'batch_size': 500.0, 'yield_pct': 80.0,
        'ingredients': [
            {'component_id': 1, 'component_name': 'Sugar', 'qty_per_batch': 320.0, 'uom': 'kg'},
        ],
    })
    scaled = scale_recipe(_Conn(), recipe_id=1, target_qty=400.0)
    # batches_needed = 400 / (500 * 0.8) = 1.0 -> same as one full batch
    assert scaled[0]['qty_needed'] == 320.0

    scaled_more = scale_recipe(_Conn(), recipe_id=1, target_qty=500.0)
    # batches_needed = 500 / (500 * 0.8) = 1.25 -> more sugar than 1 batch
    assert scaled_more[0]['qty_needed'] == 400.0


# ── release_batch_wo ─────────────────────────────────────────────────────

def test_release_batch_wo_raises_when_missing(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: None)
    with pytest.raises(ValueError, match='No recipe'):
        release_batch_wo(_Conn(), recipe_id=1, wo_number='WO-1', target_qty=100)


def test_release_batch_wo_requires_active_status(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 1, 'product_id': 10, 'status': 'draft', 'name': 'Syrup', 'revision': 'A',
    })
    with pytest.raises(ValueError, match="'active'"):
        release_batch_wo(_Conn(), recipe_id=1, wo_number='WO-1', target_qty=100)


def test_release_batch_wo_creates_wo_and_materials(monkeypatch):
    monkeypatch.setattr(recipe_core, 'get_recipe', lambda conn, rid: {
        'id': 1, 'product_id': 10, 'status': 'active', 'name': 'Syrup',
        'revision': 'A', 'batch_uom': 'kg',
    })
    monkeypatch.setattr(recipe_core, 'scale_recipe', lambda conn, rid, qty: [
        {'component_id': 5, 'component_name': 'Sugar', 'qty_needed': 128.0, 'uom': 'kg'},
    ])
    monkeypatch.setattr(recipe_core, 'ensure_wo_tables', lambda conn: None)

    created_wo_args = {}

    def fake_create_wo(conn, wo_number, **kwargs):
        created_wo_args['wo_number'] = wo_number
        created_wo_args.update(kwargs)
        return 66

    added_materials = []

    def fake_add_wo_material(conn, wo_id, product_id, qty_required=1, notes=None):
        added_materials.append((wo_id, product_id, qty_required))

    monkeypatch.setattr(recipe_core, 'create_wo', fake_create_wo)
    monkeypatch.setattr(recipe_core, 'add_wo_material', fake_add_wo_material)

    wo_id = release_batch_wo(_Conn(), recipe_id=1, wo_number='WO-2026-0050', target_qty=200)
    assert wo_id == 66
    assert created_wo_args['product_id'] == 10
    assert added_materials == [(66, 5, 128.0)]


def test_all_recipe_statuses_defined():
    assert set(RECIPE_STATUSES) == {'draft', 'active', 'superseded'}
