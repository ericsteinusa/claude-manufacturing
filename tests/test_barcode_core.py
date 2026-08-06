"""Tests for barcode_core — scanner-input parsing/routing and Code 39 PDF
label generation.

parse_scan/PREFIXES are pure. The _lookup_*_url helpers do a lazy,
per-call `from .db_pg import get_db_connection` import, so they're patched
at their source (`manufacturing.db_pg.get_db_connection`) the same way
db_pg's own local-import consumers are patched elsewhere in this suite.
The PDF/image builders shell out to real `barcode`/`reportlab` calls with
no DB or Qt involved, so those are exercised for real and checked for the
expected file-format magic bytes; the per-record-type convenience builders
(wo_label_pdf etc.) are checked by patching generate_label_pdf and
asserting on the code/title/subtitle they assemble.
"""

from unittest.mock import patch

import pytest

from manufacturing.barcode_core import (
    PREFIXES, parse_scan, resolve_scan_url,
    _barcode_image_bytes, generate_label_pdf,
    wo_label_pdf, part_label_pdf, po_label_pdf, receiving_label_pdf,
    asset_label_pdf,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows=None):
        self.calls = []
        self._rows = rows or []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeCursor(self._rows)


class _RaisingConn:
    def execute(self, sql, params=None):
        raise RuntimeError("db is down")


def _patched(rows=None):
    return patch('manufacturing.db_pg.get_db_connection',
                 return_value=_FakeConn(rows))


# ── PREFIXES ──────────────────────────────────────────────────────────────

def test_prefixes_all_end_with_dash():
    assert all(p.endswith('-') for p in PREFIXES)


def test_prefixes_values_are_rtype_label_pairs():
    for rtype, label in PREFIXES.values():
        assert isinstance(rtype, str) and rtype
        assert isinstance(label, str) and label


# ── parse_scan ────────────────────────────────────────────────────────────

def test_parse_scan_matches_prefix_and_strips_key():
    assert parse_scan("WO-2024-001") == ("wo", "2024-001")


def test_parse_scan_case_insensitive_and_trims_whitespace():
    assert parse_scan("  wo-2024-001  ") == ("wo", "2024-001")


def test_parse_scan_unknown_prefix_returns_none():
    assert parse_scan("XYZ-123") is None


def test_parse_scan_empty_string_returns_none():
    assert parse_scan("") is None
    assert parse_scan("   ") is None


def test_parse_scan_distinguishes_similar_prefixes():
    # SO-, SHIP-, SUP- share a leading "S" but must not cross-match.
    assert parse_scan("SO-100") == ("so", "100")
    assert parse_scan("SHIP-100") == ("ship", "100")
    assert parse_scan("SUP-100") == ("sup", "100")


# ── resolve_scan_url: unrecognized input ────────────────────────────────────

def test_resolve_scan_url_unknown_prefix_returns_none():
    assert resolve_scan_url("NOPE-1") is None


# ── resolve_scan_url: simple digit-only record types (no DB) ───────────────

@pytest.mark.parametrize("scan,expected", [
    ("MWO-5", "/maint/wo/5/"),
    ("CS-5", "/cs/5/"),
    ("MIN-5", "/maint/inspections/5/"),
    ("PMS-5", "/maint/schedule/5/"),
    ("EQ-5", "/maint/equipment/5/"),
    ("SUP-5", "/qa/suppliers/5/"),
    ("EMP-5", "/people/5/"),
    ("CON-5", "/contacts/5/"),
])
def test_resolve_scan_url_digit_only_types(scan, expected):
    assert resolve_scan_url(scan) == expected


@pytest.mark.parametrize("scan", [
    "MWO-ABC", "CS-ABC", "MIN-ABC", "PMS-ABC",
    "EQ-ABC", "SUP-ABC", "EMP-ABC", "CON-ABC",
])
def test_resolve_scan_url_digit_only_types_reject_non_numeric(scan):
    assert resolve_scan_url(scan) is None


# ── resolve_scan_url: DB-backed record types ────────────────────────────────

@pytest.mark.parametrize("scan,expected_table,expected_col,url", [
    ("WO-2024-001", "work_order", "wo_number", "/wo/7/"),
    ("PO-2024-001", "purchase_order", "po_number", "/po/7/"),
    ("RCV-2024-001", "purchase_order", "po_number", "/po/7/"),  # routes to PO detail
    ("ASSET-A100", "it_asset", "asset_tag", "/it/assets/7/"),
    ("LOT-L100", "lot", "lot_number", "/lots/7/"),
    ("ENGP-E100", "eng_project", "project_number", "/eng/projects/7/"),
    ("INSP-I100", "qa_inspection", "insp_number", "/qa/inspections/7/"),
    ("SHIP-S100", "shipment", "ship_number", "/prod/shipping/7/"),
    ("SO-S100", "sales_order", "so_number", "/so/7/"),
])
def test_resolve_scan_url_db_backed_types_found(scan, expected_table, expected_col, url):
    with _patched(rows=[{'id': 7}]) as mock_conn:
        result = resolve_scan_url(scan)
    assert result == url
    conn = mock_conn.return_value
    sql, params = conn.calls[0]
    assert expected_table in sql
    assert expected_col in sql
    assert params == [scan.split('-', 1)[1]]


@pytest.mark.parametrize("scan", [
    "WO-2024-001", "PO-2024-001", "RCV-2024-001", "ASSET-A100", "LOT-L100",
    "ENGP-E100", "INSP-I100", "SHIP-S100", "SO-S100",
])
def test_resolve_scan_url_db_backed_types_not_found(scan):
    with _patched(rows=[]):
        assert resolve_scan_url(scan) is None


@pytest.mark.parametrize("scan", [
    "WO-2024-001", "PO-2024-001", "ASSET-A100", "LOT-L100",
    "ENGP-E100", "INSP-I100", "SHIP-S100", "SO-S100",
])
def test_resolve_scan_url_db_backed_types_swallow_db_errors(scan):
    with patch('manufacturing.db_pg.get_db_connection', side_effect=RuntimeError("boom")):
        assert resolve_scan_url(scan) is None


# ── resolve_scan_url: PART- (two-step id-then-name lookup) ─────────────────

def test_resolve_scan_url_part_numeric_key_found_by_id():
    with _patched(rows=[{'id': 3}]) as mock_conn:
        result = resolve_scan_url("PART-3")
    assert result == "/inventory/3/"
    sql, params = mock_conn.return_value.calls[0]
    assert "id = %s" in sql
    assert params == [3]


def test_resolve_scan_url_part_numeric_key_falls_back_to_name_when_id_not_found():
    conn = _FakeConn(rows=[])
    responses = iter([[], [{'id': 9}]])

    def execute(sql, params=None):
        conn.calls.append((sql, list(params or [])))
        return _FakeCursor(next(responses))

    conn.execute = execute
    with patch('manufacturing.db_pg.get_db_connection', return_value=conn):
        result = resolve_scan_url("PART-9")
    assert result == "/inventory/9/"
    assert len(conn.calls) == 2
    assert "UPPER(name)" in conn.calls[1][0]


def test_resolve_scan_url_part_non_numeric_key_looked_up_by_name():
    with _patched(rows=[{'id': 4}]) as mock_conn:
        result = resolve_scan_url("PART-WIDGET")
    assert result == "/inventory/4/"
    sql, params = mock_conn.return_value.calls[0]
    assert "UPPER(name)" in sql
    assert params == ["WIDGET"]


def test_resolve_scan_url_part_not_found_returns_none():
    with _patched(rows=[]):
        assert resolve_scan_url("PART-NOPE") is None


# ── _barcode_image_bytes / generate_label_pdf (real generation) ────────────

def test_barcode_image_bytes_returns_png():
    data = _barcode_image_bytes("WO-2024-001")
    assert isinstance(data, bytes)
    assert data.startswith(b"\x89PNG")


def test_generate_label_pdf_returns_pdf_bytes():
    data = generate_label_pdf("WO-2024-001", "Work Order: WO-2024-001", "A widget")
    assert isinstance(data, bytes)
    assert data.startswith(b"%PDF")


def test_generate_label_pdf_without_subtitle_still_returns_pdf():
    data = generate_label_pdf("PO-2024-001", "Purchase Order: PO-2024-001")
    assert data.startswith(b"%PDF")


# ── convenience builders ─────────────────────────────────────────────────

def test_wo_label_pdf_builds_code_title_and_description():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        wo_label_pdf({'wo_number': '2024-001', 'description': 'Assemble frame'})
    gen.assert_called_once_with(
        "WO-2024-001", "Work Order: 2024-001", "Assemble frame")


def test_wo_label_pdf_defaults_missing_description_to_empty():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        wo_label_pdf({'wo_number': '2024-001'})
    assert gen.call_args[0][2] == ""


def test_part_label_pdf_uses_sku_when_present():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        part_label_pdf({'id': 5, 'sku': 'SKU-9', 'name': 'Widget'})
    gen.assert_called_once_with("PART-SKU-9", "Part: SKU-9", "Widget")


def test_part_label_pdf_falls_back_to_id_when_no_sku():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        part_label_pdf({'id': 5, 'name': 'Widget'})
    gen.assert_called_once_with("PART-5", "Part: 5", "Widget")


def test_po_label_pdf_builds_code_title_and_notes():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        po_label_pdf({'po_number': '2024-001', 'notes': 'Rush order'})
    gen.assert_called_once_with(
        "PO-2024-001", "Purchase Order: 2024-001", "Rush order")


def test_receiving_label_pdf_uses_rcv_prefix():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        receiving_label_pdf({'po_number': '2024-001', 'notes': ''})
    gen.assert_called_once_with(
        "RCV-2024-001", "Receiving: 2024-001", "")


def test_asset_label_pdf_combines_make_and_model():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        asset_label_pdf({'asset_tag': 'A100', 'make': 'Dell', 'model': 'XPS'})
    gen.assert_called_once_with("ASSET-A100", "Asset: A100", "Dell XPS")


def test_asset_label_pdf_strips_when_make_or_model_missing():
    with patch('manufacturing.barcode_core.generate_label_pdf') as gen:
        gen.return_value = b"PDF"
        asset_label_pdf({'asset_tag': 'A100', 'model': 'XPS'})
    assert gen.call_args[0][2] == "XPS"
