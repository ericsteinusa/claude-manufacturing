"""Tests for views._barcode.receive_scan — the receiving scan-session view.

Regression coverage for two lookup bugs neither the desktop-era tests nor
test_barcode_core.py (which only covers the separate scan_lookup/
resolve_scan_url code path used by the Scanner home page) ever exercised:

1. PO-/RCV- lookup: a genuinely printed PO-/RCV- label (po_label_pdf /
   receiving_label_pdf) encodes the routing tag plus the *full* po_number,
   which in this schema already carries its own leading prefix (e.g.
   "PO-2026-0001", "SMPL-PO-1") — so stripping just the tag recovers it,
   and that path already worked. But a user who types or scans the bare
   po_number as displayed everywhere else in the app (e.g. "PO-2026-0001",
   the same string shown in the page title) never had an extra tag to
   strip — the old code always stripped one regardless, looked up
   "2026-0001", and that never matches. Fixed by trying both the stripped
   and the raw candidate.

2. PART- lookup: part_label_pdf falls back to the bare product id when a
   product has no sku (the product table has no sku column in this
   schema at all, so this is always the case), but the old matching logic
   only compared the scanned key against item['sku']/item['description']
   — never item['product_id'], the field that's actually encoded on a
   real PART- label. Fixed by also matching on product_id.

get_db_connection, get_po, get_po_items, and receive_po_item are all
imported directly into manufacturing.views._barcode's own namespace, so
they're patched there — the same "patch at the module it was imported
into" convention used in test_api_views.py. render() is patched too, so
these tests exercise receive_scan's own lookup/session logic without
depending on real template rendering.
"""
from unittest.mock import patch

from django.test import RequestFactory

from manufacturing.views._barcode import receive_scan

rf = RequestFactory()


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Serves one canned response per conn.execute() call, in order —
    the same sequential-candidate-lookup mocking style used by
    test_barcode_core.py's PART- id-then-name fallback test."""

    def __init__(self, responses):
        self.calls = []
        self._responses = iter(responses)

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _FakeCursor(next(self._responses))


def _scan(conn_responses, q, session=None, get_po_ret=None, items_ret=None):
    request = rf.post("/scan/receive/", {"action": "scan", "q": q})
    request.session = dict(session or {})
    conn = _FakeConn(conn_responses)
    with patch("manufacturing.views._barcode.get_db_connection", return_value=conn), \
         patch("manufacturing.views._barcode.get_po", return_value=get_po_ret), \
         patch("manufacturing.views._barcode.get_po_items", return_value=items_ret or []), \
         patch("manufacturing.views._barcode.receive_po_item") as receive_item, \
         patch("manufacturing.views._barcode.render", return_value="RENDERED") as render:
        receive_scan(request)
    ctx = render.call_args[0][2]
    return request, conn, ctx, receive_item


# ── PO-/RCV- lookup ─────────────────────────────────────────────────────────

def test_scan_bare_po_number_matches_when_stored_verbatim():
    """A user types/scans the plain po_number shown elsewhere in the app
    (e.g. po_detail.html's own page title) — no extra "PO-" tag to strip."""
    request, conn, ctx, _ = _scan(
        conn_responses=[[], [{"id": 42, "po_number": "PO-2026-0001"}]],
        q="PO-2026-0001",
    )
    assert request.session["receive_po_id"] == 42
    assert "error" not in ctx
    assert "PO-2026-0001" in ctx["success"]
    assert len(conn.calls) == 2, "stripped candidate should miss, raw candidate should hit"


def test_scan_genuine_printed_po_barcode_still_matches():
    """A real po_label_pdf-generated barcode encodes "PO-" + the full
    po_number (itself already "PO-2026-0001"), so stripping the tag once
    recovers it on the very first try — this must keep working."""
    request, conn, ctx, _ = _scan(
        conn_responses=[[{"id": 42, "po_number": "PO-2026-0001"}]],
        q="PO-PO-2026-0001",
    )
    assert request.session["receive_po_id"] == 42
    assert len(conn.calls) == 1, "the stripped candidate should have matched immediately"


def test_scan_genuine_printed_rcv_barcode_still_matches():
    """Same as above for receiving_label_pdf's "RCV-" + po_number encoding."""
    request, conn, ctx, _ = _scan(
        conn_responses=[[{"id": 42, "po_number": "PO-2026-0001"}]],
        q="RCV-PO-2026-0001",
    )
    assert request.session["receive_po_id"] == 42
    assert len(conn.calls) == 1


def test_scan_bare_po_number_with_non_po_prefixed_number_matches():
    """Some seed data's po_number doesn't start with "PO-" at all (e.g.
    "SMPL-PO-1") — typing it in bare must still work via the raw-candidate
    fallback, even though it never enters the "PO-"/"RCV-" branch's
    stripped-candidate path the same way."""
    request, conn, ctx, _ = _scan(
        conn_responses=[[], [{"id": 9, "po_number": "PO-CORRECTNESS-CHECK-1"}]],
        q="PO-CORRECTNESS-CHECK-1",
    )
    assert request.session["receive_po_id"] == 9
    assert "PO-CORRECTNESS-CHECK-1" in ctx["success"]


def test_scan_po_truly_not_found_reports_raw_input():
    request, conn, ctx, _ = _scan(
        conn_responses=[[], []],
        q="PO-9999-9999",
    )
    assert "receive_po_id" not in request.session
    assert ctx["error"] == "PO not found: PO-9999-9999"


# ── PART- lookup ─────────────────────────────────────────────────────────

def test_scan_part_matches_by_product_id_when_no_sku():
    """part_label_pdf falls back to the bare product id when a product has
    no sku (there is no sku column on product in this schema at all), so
    the scanned key is a numeric product id — it must match
    item['product_id'], not just the unrelated sku/description fields."""
    items = [{"id": 501, "product_id": 7, "sku": None,
              "description": "Bicycle Tire", "qty_ordered": 10, "qty_received": 0}]
    request, conn, ctx, receive_item = _scan(
        conn_responses=[],
        q="PART-7",
        session={"receive_po_id": 5},
        get_po_ret={"id": 5, "po_number": "PO-2026-0001"},
        items_ret=items,
    )
    receive_item.assert_called_once_with(conn, 501, 10, po_id=5)
    assert "error" not in ctx
    assert "Bicycle Tire" in ctx["success"]


def test_scan_part_still_matches_by_sku_when_present():
    """Regression guard: if a sku ever is populated, matching on it must
    keep working alongside the new product_id check."""
    items = [{"id": 501, "product_id": 7, "sku": "TIRE-26",
              "description": "Bicycle Tire", "qty_ordered": 10, "qty_received": 4}]
    request, conn, ctx, receive_item = _scan(
        conn_responses=[],
        q="PART-TIRE-26",
        session={"receive_po_id": 5},
        get_po_ret={"id": 5, "po_number": "PO-2026-0001"},
        items_ret=items,
    )
    receive_item.assert_called_once_with(conn, 501, 6, po_id=5)


def test_scan_part_not_on_po_reports_error():
    items = [{"id": 501, "product_id": 7, "sku": None,
              "description": "Bicycle Tire", "qty_ordered": 10, "qty_received": 0}]
    request, conn, ctx, receive_item = _scan(
        conn_responses=[],
        q="PART-999",
        session={"receive_po_id": 5},
        get_po_ret={"id": 5, "po_number": "PO-2026-0001"},
        items_ret=items,
    )
    receive_item.assert_not_called()
    assert ctx["error"] == "Part 999 not on this PO."


def test_scan_part_already_fully_received():
    items = [{"id": 501, "product_id": 7, "sku": None,
              "description": "Bicycle Tire", "qty_ordered": 10, "qty_received": 10}]
    request, conn, ctx, receive_item = _scan(
        conn_responses=[],
        q="PART-7",
        session={"receive_po_id": 5},
        get_po_ret={"id": 5, "po_number": "PO-2026-0001"},
        items_ret=items,
    )
    receive_item.assert_not_called()
    assert ctx["info"] == "7 already fully received."
