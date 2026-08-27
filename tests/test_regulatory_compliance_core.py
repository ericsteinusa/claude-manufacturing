"""Tests for regulatory_compliance_core — Regulatory Compliance Templates."""

import pytest

from manufacturing.regulatory_compliance_core import (
    create_template, add_template_item, create_checklist,
    update_checklist_item, get_checklist_progress, seed_default_templates,
    ITEM_STATUSES, _SEED_TEMPLATES,
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


# ── create_template / add_template_item ─────────────────────────────────

def test_create_template_returns_id():
    conn = _Conn(rows=[{'id': 1}])
    tpl_id = create_template(conn, 'ISO 9001:2015', 'ISO 9001:2015')
    assert tpl_id == 1


def test_create_template_requires_name():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_template(conn, '   ', 'ISO 9001')


def test_add_template_item_requires_text():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_template_item(conn, 1, '4.4', '   ')


def test_add_template_item_returns_id():
    conn = _Conn(rows=[{'id': 7}])
    item_id = add_template_item(conn, 1, '4.4', 'Processes are identified')
    assert item_id == 7


# ── create_checklist ─────────────────────────────────────────────────────

def test_create_checklist_requires_name():
    conn = _MultiConn([[{'id': 1, 'clause_ref': '4.4', 'requirement_text': 'x',
                          'category': '', 'sort_order': 0}]])
    with pytest.raises(ValueError, match='name is required'):
        create_checklist(conn, 1, '   ')


def test_create_checklist_raises_when_template_has_no_items():
    conn = _MultiConn([[]])  # list_template_items returns nothing
    with pytest.raises(ValueError, match='no requirement items'):
        create_checklist(conn, 1, 'Q3 Internal Audit')


def test_create_checklist_snapshots_items():
    conn = _MultiConn([
        [  # list_template_items
            {'id': 1, 'clause_ref': '4.4', 'requirement_text': 'req one',
             'category': 'Context', 'sort_order': 0},
            {'id': 2, 'clause_ref': '5.1', 'requirement_text': 'req two',
             'category': 'Leadership', 'sort_order': 1},
        ],
        [{'id': 10}],  # INSERT INTO compliance_checklist
        [],  # INSERT checklist_item 1
        [],  # INSERT checklist_item 2
    ])
    checklist_id = create_checklist(conn, 1, 'Q3 Internal Audit', owner='Dana')
    assert checklist_id == 10
    insert_calls = [c for c in conn.calls if 'INSERT INTO compliance_checklist_item' in c[0]]
    assert len(insert_calls) == 2


# ── update_checklist_item / progress rollup ──────────────────────────────

def test_update_checklist_item_validates_status():
    conn = _MultiConn([[{'checklist_id': 1}]])
    with pytest.raises(ValueError, match='status must be one of'):
        update_checklist_item(conn, 1, 'bogus_status')


def test_update_checklist_item_raises_if_missing():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError, match='No checklist item'):
        update_checklist_item(conn, 999, 'complete')


def test_all_item_statuses_accepted():
    for status in ITEM_STATUSES:
        conn = _MultiConn([
            [{'checklist_id': 1}],  # lookup
            [],  # UPDATE compliance_checklist_item
            [],  # list_checklist_items (for progress recompute)
            [],  # UPDATE compliance_checklist
        ])
        update_checklist_item(conn, 1, status)  # no raise


def test_get_checklist_progress_counts_and_percent():
    conn = _Conn(rows=[
        {'id': 1, 'status': 'complete'},
        {'id': 2, 'status': 'not_applicable'},
        {'id': 3, 'status': 'in_progress'},
        {'id': 4, 'status': 'not_started'},
    ])
    progress = get_checklist_progress(conn, 1)
    assert progress['total'] == 4
    assert progress['complete'] == 1
    assert progress['not_applicable'] == 1
    assert progress['percent'] == 50.0


def test_get_checklist_progress_empty_checklist_is_zero_percent():
    conn = _Conn(rows=[])
    progress = get_checklist_progress(conn, 1)
    assert progress['total'] == 0
    assert progress['percent'] == 0.0


# ── seed_default_templates ───────────────────────────────────────────────

def test_seed_default_templates_skips_existing():
    # Every seed template already exists -> no creation. One "exists"
    # response per template, matching _SEED_TEMPLATES' current length so
    # this doesn't need updating every time a template is added.
    conn = _MultiConn([[{'id': i}] for i in range(1, len(_SEED_TEMPLATES) + 1)])
    created = seed_default_templates(conn)
    assert created == 0


def test_seed_default_templates_creates_all_when_none_exist():
    # One "doesn't exist" response per template, then a create_template
    # response and one add_template_item response per item — built from
    # _SEED_TEMPLATES itself so this stays correct as templates are added.
    responses = []
    next_id = 1
    for tpl in _SEED_TEMPLATES:
        responses.append([])
        responses.append([{'id': next_id}])
        next_id += 1
        for _ in tpl['items']:
            responses.append([{'id': next_id}])
            next_id += 1
    conn = _MultiConn(responses)
    created = seed_default_templates(conn)
    assert created == len(_SEED_TEMPLATES)


def test_seed_templates_include_as9100d_and_iatf_16949():
    names = [tpl['name'] for tpl in _SEED_TEMPLATES]
    assert any('AS9100D' in n for n in names)
    assert any('IATF 16949' in n for n in names)


def test_vertical_pack_templates_have_multiple_items():
    for tpl in _SEED_TEMPLATES:
        if 'AS9100D' in tpl['name'] or 'IATF 16949' in tpl['name']:
            assert len(tpl['items']) >= 5
