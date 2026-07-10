"""Tests for batch_record_core — Batch Record Generation."""

import pytest

from manufacturing import batch_record_core
from manufacturing.batch_record_core import (
    generate_batch_record, next_batch_record_number, render_batch_record_pdf,
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


# ── next_batch_record_number ─────────────────────────────────────────────

def test_next_batch_record_number_starts_at_1():
    conn = _Conn(rows=[])
    num = next_batch_record_number(conn)
    assert num.startswith('BR-')
    assert num.endswith('-0001')


def test_next_batch_record_number_increments():
    conn = _Conn(rows=[{'batch_record_number': 'BR-2026-0003'},
                       {'batch_record_number': 'BR-2026-0001'}])
    num = next_batch_record_number(conn)
    assert num.endswith('-0004')


# ── generate_batch_record ────────────────────────────────────────────────

def test_generate_batch_record_raises_when_wo_missing(monkeypatch):
    monkeypatch.setattr(batch_record_core, 'get_wo', lambda conn, wid: None)
    with pytest.raises(ValueError, match='No work order'):
        generate_batch_record(_Conn(), wo_id=1)


def test_generate_batch_record_requires_completed_status(monkeypatch):
    monkeypatch.setattr(batch_record_core, 'get_wo', lambda conn, wid: {
        'id': wid, 'status': 'in_progress', 'wo_number': 'WO-1',
    })
    with pytest.raises(ValueError, match="'completed'"):
        generate_batch_record(_Conn(), wo_id=1)


def test_generate_batch_record_snapshots_materials_and_inspections(monkeypatch):
    monkeypatch.setattr(batch_record_core, 'get_wo', lambda conn, wid: {
        'id': wid, 'status': 'completed', 'wo_number': 'WO-2026-0001',
        'product_name': 'Widget', 'quantity': 100,
    })
    monkeypatch.setattr(batch_record_core, 'get_wo_materials', lambda conn, wid: [
        {'product_name': 'Bolt', 'qty_required': 400, 'qty_issued': 400},
    ])
    monkeypatch.setattr(batch_record_core, 'get_wo_cost_summary', lambda conn, wid: {
        'material_cost': 40.0, 'labor_cost': 100.0, 'total_cost': 140.0,
    })

    conn = _MultiConn([
        [{'insp_number': 'INSP-1', 'inspector': 'Dana', 'insp_date': '2026-07-10', 'result': 'pass'}],
        [],  # existing batch_record_number rows for numbering
        [{'id': 77}],  # INSERT INTO batch_record
        [],  # INSERT batch_record_material
        [],  # INSERT batch_record_inspection
    ])
    record_id = generate_batch_record(conn, wo_id=1, generated_by='op@example.com')
    assert record_id == 77

    insert_calls = [c for c in conn.calls if c[0].startswith('INSERT INTO batch_record ')]
    assert insert_calls[0][1][1] == 1  # wo_id
    assert insert_calls[0][1][4] == 100  # quantity

    material_calls = [c for c in conn.calls if 'INSERT INTO batch_record_material' in c[0]]
    assert len(material_calls) == 1
    assert material_calls[0][1] == [77, 'Bolt', 400, 400]

    inspection_calls = [c for c in conn.calls if 'INSERT INTO batch_record_inspection' in c[0]]
    assert len(inspection_calls) == 1
    assert inspection_calls[0][1] == [77, 'INSP-1', 'Dana', '2026-07-10', 'pass']


# ── render_batch_record_pdf ──────────────────────────────────────────────

def test_render_batch_record_pdf_returns_pdf_bytes():
    record = {
        'batch_record_number': 'BR-2026-0001', 'wo_number': 'WO-2026-0001',
        'product_name': 'Widget', 'quantity': 100, 'generated_at': '2026-07-10',
        'generated_by': 'op@example.com', 'material_cost': 40.0,
        'labor_cost': 100.0, 'total_cost': 140.0,
        'materials': [{'component_name': 'Bolt', 'qty_required': 400, 'qty_issued': 400}],
        'inspections': [{'insp_number': 'INSP-1', 'inspector': 'Dana',
                         'insp_date': '2026-07-10', 'result': 'pass'}],
    }
    pdf = render_batch_record_pdf(record)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b'%PDF')


def test_render_batch_record_pdf_handles_no_materials_or_inspections():
    record = {
        'batch_record_number': 'BR-2026-0002', 'wo_number': 'WO-2026-0002',
        'product_name': 'Widget', 'quantity': 50, 'generated_at': '2026-07-10',
        'generated_by': '', 'material_cost': 0.0, 'labor_cost': 0.0,
        'total_cost': 0.0, 'materials': [], 'inspections': [],
    }
    pdf = render_batch_record_pdf(record)
    assert pdf.startswith(b'%PDF')
