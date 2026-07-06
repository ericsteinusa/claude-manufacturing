"""Tests for rfq_core — RFQ creation, quote entry, comparison, and
award-to-PO conversion."""

import pytest

from manufacturing.rfq_core import (
    STATUSES, next_rfq_number, get_comparison, award_items,
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


# ── constants / numbering ────────────────────────────────────────────────

def test_statuses():
    assert set(STATUSES) == {'open', 'awarded', 'closed'}


def test_next_rfq_number_starts_at_0001():
    conn = _MultiConn([[]])
    assert next_rfq_number(conn).endswith('-0001')


def test_next_rfq_number_increments_from_max():
    import datetime
    yr = datetime.date.today().year
    conn = _MultiConn([[{'rfq_number': f'RFQ-{yr}-0002'}]])
    assert next_rfq_number(conn) == f'RFQ-{yr}-0003'


# ── get_comparison ───────────────────────────────────────────────────────

def test_get_comparison_flags_lowest_quote():
    conn = _MultiConn([
        [{'id': 1, 'rfq_vendor_id': 10, 'company_name': 'Acme',
          'first_name': '', 'last_name': ''},
         {'id': 2, 'rfq_vendor_id': 11, 'company_name': 'Bolt Co',
          'first_name': '', 'last_name': ''}],           # list_rfq_vendors
        [{'id': 100, 'rfq_id': 5, 'description': 'Widget', 'product_id': None,
          'qty': 10, 'target_price': 5.0, 'awarded_vendor_id': None,
          'po_id': None, 'product_name': None}],          # list_rfq_items
        [{'id': 1000, 'rfq_item_id': 100, 'vendor_id': 1,
          'quoted_price': 4.5, 'lead_time_days': 7},
         {'id': 1001, 'rfq_item_id': 100, 'vendor_id': 2,
          'quoted_price': 4.0, 'lead_time_days': 10}],    # quotes for item 100
    ])
    comparison = get_comparison(conn, 5)
    assert [v['id'] for v in comparison['vendors']] == [1, 2]
    (item, vendor_cells) = comparison['rows'][0]
    assert item['description'] == 'Widget'
    (v1, cell1), (v2, cell2) = vendor_cells
    assert v1['id'] == 1 and cell1['quoted_price'] == 4.5 and cell1['is_lowest'] is False
    assert v2['id'] == 2 and cell2['quoted_price'] == 4.0 and cell2['is_lowest'] is True


def test_get_comparison_missing_quote_is_none_cell():
    conn = _MultiConn([
        [{'id': 1, 'rfq_vendor_id': 10, 'company_name': 'Acme',
          'first_name': '', 'last_name': ''}],
        [{'id': 100, 'rfq_id': 5, 'description': 'Widget', 'product_id': None,
          'qty': 10, 'target_price': 5.0, 'awarded_vendor_id': None,
          'po_id': None, 'product_name': None}],
        [],  # no quotes entered yet
    ])
    comparison = get_comparison(conn, 5)
    (item, vendor_cells) = comparison['rows'][0]
    assert len(vendor_cells) == 1
    vendor, cell = vendor_cells[0]
    assert vendor['id'] == 1 and cell is None


# ── award_items ──────────────────────────────────────────────────────────

def test_award_items_missing_rfq_raises():
    conn = _MultiConn([[]])
    with pytest.raises(ValueError):
        award_items(conn, 999, {1: 10}, 'eric')


def test_award_items_single_vendor_creates_one_po_with_quoted_price():
    conn = _MultiConn([
        [{'id': 5, 'rfq_number': 'RFQ-2026-0001', 'status': 'open'}],  # get_rfq
        [],                                    # next_po_number: existing numbers
        [{'id': 900}],                         # create_po insert returning id
        [{'id': 100, 'rfq_id': 5, 'description': 'Widget', 'product_id': None,
          'qty': 10, 'target_price': 5.0, 'awarded_vendor_id': None, 'po_id': None}],  # get_rfq_item
        [{'id': 1000, 'rfq_item_id': 100, 'vendor_id': 1,
          'quoted_price': 4.5, 'lead_time_days': 7}],  # get_quote
        [],                                    # add_po_item insert
        [],                                    # update rfq_item awarded
        [],                                    # update rfq status=awarded
    ])
    po_ids = award_items(conn, 5, {100: 1}, 'eric')
    assert po_ids == [900]
    # add_po_item call params: (po_id, description, product_id, qty_ordered, unit_price)
    add_po_item_call = conn.calls[5]
    assert add_po_item_call[1] == [900, 'Widget', None, 10, 4.5]


def test_award_items_falls_back_to_target_price_without_quote():
    conn = _MultiConn([
        [{'id': 5, 'rfq_number': 'RFQ-2026-0001', 'status': 'open'}],
        [],
        [{'id': 900}],
        [{'id': 100, 'rfq_id': 5, 'description': 'Widget', 'product_id': None,
          'qty': 10, 'target_price': 5.0, 'awarded_vendor_id': None, 'po_id': None}],
        [],  # get_quote: no quote found
        [],  # add_po_item
        [],  # update rfq_item
        [],  # update rfq status
    ])
    award_items(conn, 5, {100: 1}, 'eric')
    add_po_item_call = conn.calls[5]
    assert add_po_item_call[1] == [900, 'Widget', None, 10, 5.0]


def test_award_items_missing_item_raises():
    conn = _MultiConn([
        [{'id': 5, 'rfq_number': 'RFQ-2026-0001', 'status': 'open'}],
        [],
        [{'id': 900}],
        [],  # get_rfq_item returns nothing
    ])
    with pytest.raises(ValueError):
        award_items(conn, 5, {999: 1}, 'eric')


def test_award_items_groups_by_vendor_creates_multiple_pos():
    conn = _MultiConn([
        [{'id': 5, 'rfq_number': 'RFQ-2026-0001', 'status': 'open'}],  # get_rfq
        # vendor 1's PO
        [], [{'id': 900}],
        [{'id': 100, 'rfq_id': 5, 'description': 'Widget A', 'product_id': None,
          'qty': 5, 'target_price': 2.0, 'awarded_vendor_id': None, 'po_id': None}],
        [], [], [],
        # vendor 2's PO
        [], [{'id': 901}],
        [{'id': 101, 'rfq_id': 5, 'description': 'Widget B', 'product_id': None,
          'qty': 3, 'target_price': 3.0, 'awarded_vendor_id': None, 'po_id': None}],
        [], [], [],
        [],  # update rfq status=awarded
    ])
    po_ids = award_items(conn, 5, {100: 1, 101: 2}, 'eric')
    assert sorted(po_ids) == [900, 901]
