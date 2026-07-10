"""Tests for cto_core — Configure-to-Order."""

import pytest

from manufacturing import cto_core
from manufacturing.cto_core import (
    create_option_group, add_option, is_configurable,
    create_configuration, set_selection, is_configuration_complete,
    generate_configured_bom, release_configured_wo,
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


# ── option groups / options ──────────────────────────────────────────────

def test_create_option_group_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    group_id = create_option_group(conn, 10, 'Frame Color')
    assert group_id == 1


def test_create_option_group_requires_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_option_group(conn, 10, '   ')


def test_add_option_requires_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_option(conn, 1, '  ', component_id=5)


def test_add_option_returns_id():
    conn = _Conn(rows=[{'id': 7}])
    option_id = add_option(conn, 1, 'Red', component_id=5, qty_required=2)
    assert option_id == 7


def test_is_configurable_true_false():
    conn = _Conn(rows=[{'id': 1}])
    assert is_configurable(conn, 10) is True
    conn2 = _Conn(rows=[])
    assert is_configurable(conn2, 10) is False


# ── configuration / selections ───────────────────────────────────────────

def test_create_configuration_returns_id_when_new():
    conn = _MultiConn([
        [],       # get_configuration -> None (no existing row)
        [{'id': 5}],  # INSERT INTO cto_configuration
    ])
    config_id = create_configuration(conn, so_item_id=1, product_id=10)
    assert config_id == 5


def test_create_configuration_idempotent_when_existing():
    conn = _MultiConn([
        [{'id': 9, 'so_item_id': 1, 'product_id': 10}],  # get_configuration finds existing
        [],  # selections lookup inside get_configuration
    ])
    config_id = create_configuration(conn, so_item_id=1, product_id=10)
    assert config_id == 9


def test_set_selection_rejects_option_not_in_group():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='does not belong'):
        set_selection(conn, configuration_id=1, group_id=2, option_id=99)


def test_set_selection_upserts_when_valid():
    conn = _MultiConn([
        [{'id': 99}],  # option belongs to group check
        [],            # the upsert insert
    ])
    set_selection(conn, configuration_id=1, group_id=2, option_id=99)
    upsert_calls = [c for c in conn.calls if 'INSERT INTO cto_configuration_selection' in c[0]]
    assert len(upsert_calls) == 1


def test_is_configuration_complete_true_with_no_groups():
    conn = _Conn(rows=[])
    assert is_configuration_complete(conn, configuration_id=1, product_id=10) is True


def test_is_configuration_complete_false_when_group_unselected(monkeypatch):
    monkeypatch.setattr(cto_core, 'list_option_groups', lambda conn, pid: [
        {'id': 1, 'options': []}, {'id': 2, 'options': []},
    ])
    conn = _Conn(rows=[{'group_id': 1}])
    assert is_configuration_complete(conn, configuration_id=1, product_id=10) is False


def test_is_configuration_complete_true_when_all_selected(monkeypatch):
    monkeypatch.setattr(cto_core, 'list_option_groups', lambda conn, pid: [
        {'id': 1, 'options': []}, {'id': 2, 'options': []},
    ])
    conn = _Conn(rows=[{'group_id': 1}, {'group_id': 2}])
    assert is_configuration_complete(conn, configuration_id=1, product_id=10) is True


# ── generate_configured_bom ──────────────────────────────────────────────

def test_generate_configured_bom_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(cto_core, 'get_configuration', lambda conn, so_item_id: None)
    conn = _Conn()
    with pytest.raises(ValueError, match='not been configured'):
        generate_configured_bom(conn, so_item_id=1)


def test_generate_configured_bom_swaps_option_slot_and_keeps_base(monkeypatch):
    monkeypatch.setattr(cto_core, 'get_configuration', lambda conn, so_item_id: {
        'id': 1, 'product_id': 10,
        'selections': [
            {'group_name': 'Frame Color', 'option_name': 'Red',
             'component_id': 42, 'qty_required': 1.0},
        ],
    })
    monkeypatch.setattr(cto_core, 'list_option_groups', lambda conn, pid: [
        {'id': 1, 'options': [
            {'component_id': 42}, {'component_id': 43},
        ]},
    ])
    monkeypatch.setattr(cto_core, 'get_bom', lambda conn, pid: [
        {'component_id': 42, 'component_name': 'Old Red Frame',
         'qty_required': 1.0, 'scrap_pct': 0.0},
        {'component_id': 99, 'component_name': 'Seat', 'qty_required': 1.0, 'scrap_pct': 0.0},
    ])
    resolved = generate_configured_bom(_Conn(), so_item_id=1)
    component_ids = {r['component_id'] for r in resolved}
    assert 99 in component_ids  # unaffected base line kept
    assert 42 in component_ids  # selected option's own component present
    # base BOM's slot line for component 42 should not appear twice
    assert sum(1 for r in resolved if r['component_id'] == 42) == 1


# ── release_configured_wo ────────────────────────────────────────────────

def test_release_configured_wo_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(cto_core, 'get_configuration', lambda conn, so_item_id: None)
    conn = _Conn()
    with pytest.raises(ValueError, match='not been configured'):
        release_configured_wo(conn, so_item_id=1, wo_number='WO-1', quantity=5)


def test_release_configured_wo_raises_when_incomplete(monkeypatch):
    monkeypatch.setattr(cto_core, 'get_configuration', lambda conn, so_item_id: {
        'id': 1, 'product_id': 10, 'selections': [],
    })
    monkeypatch.setattr(cto_core, 'is_configuration_complete', lambda conn, cid, pid: False)
    conn = _Conn()
    with pytest.raises(ValueError, match='missing a selection'):
        release_configured_wo(conn, so_item_id=1, wo_number='WO-1', quantity=5)


def test_release_configured_wo_creates_wo_and_materials(monkeypatch):
    monkeypatch.setattr(cto_core, 'get_configuration', lambda conn, so_item_id: {
        'id': 1, 'product_id': 10, 'selections': [],
    })
    monkeypatch.setattr(cto_core, 'is_configuration_complete', lambda conn, cid, pid: True)
    monkeypatch.setattr(cto_core, 'ensure_wo_tables', lambda conn: None)
    monkeypatch.setattr(cto_core, 'generate_configured_bom', lambda conn, so_item_id: [
        {'component_id': 5, 'qty_required': 2.0, 'scrap_pct': 0.0, 'source': 'base'},
    ])
    created_wo_args = {}

    def fake_create_wo(conn, wo_number, **kwargs):
        created_wo_args['wo_number'] = wo_number
        created_wo_args.update(kwargs)
        return 55

    added_materials = []

    def fake_add_wo_material(conn, wo_id, product_id, qty_required=1, notes=None):
        added_materials.append((wo_id, product_id, qty_required, notes))

    monkeypatch.setattr(cto_core, 'create_wo', fake_create_wo)
    monkeypatch.setattr(cto_core, 'add_wo_material', fake_add_wo_material)

    wo_id = release_configured_wo(_Conn(), so_item_id=1, wo_number='WO-2026-0099', quantity=3)
    assert wo_id == 55
    assert created_wo_args['product_id'] == 10
    assert added_materials == [(55, 5, 6.0, 'base')]
