"""Tests for lot_core — lot and serial number tracking."""

import pytest

from manufacturing.lot_core import (
    LOT_STATUSES, SERIAL_STATUSES,
    next_lot_number,
    list_lots, get_lot, get_lot_by_number, get_lot_genealogy,
    create_lot, update_lot_status, consume_lot_qty, get_expiry_alerts,
    list_serials, create_serial, update_serial_status,
)


# ── fake DB infrastructure ────────────────────────────────────────────────

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

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ── constants ──────────────────────────────────────────────────────────────

def test_lot_statuses_complete():
    assert set(LOT_STATUSES) == {'available', 'quarantine', 'hold',
                                  'consumed', 'rejected'}


def test_serial_statuses_complete():
    assert set(SERIAL_STATUSES) == {'available', 'issued', 'scrapped', 'returned'}


# ── lot number generation ──────────────────────────────────────────────────

def test_next_lot_number_starts_at_001_when_empty():
    conn = _Conn(rows=[])
    num = next_lot_number(conn, product_id=5)
    assert num.endswith('-001')
    assert '-LOT-' in num
    assert num.startswith('5-LOT-')


def test_next_lot_number_increments_from_max():
    from datetime import date
    today = date.today().strftime('%Y%m%d')
    existing = [{'lot_number': f'5-LOT-{today}-001'},
                {'lot_number': f'5-LOT-{today}-003'}]
    conn = _Conn(rows=existing)
    num = next_lot_number(conn, product_id=5)
    assert num.endswith('-004')


def test_next_lot_number_ignores_malformed():
    conn = _Conn(rows=[{'lot_number': '5-LOT-20260101-ABC'}])
    num = next_lot_number(conn, product_id=5)
    assert num.endswith('-001')


# ── list_lots ──────────────────────────────────────────────────────────────

def test_list_lots_no_filter_adds_no_extra_conditions():
    conn = _Conn(rows=[])
    list_lots(conn)
    # The only WHERE condition should be the always-true sentinel "1=1"
    assert 'l.product_id = %s' not in conn.last_sql
    assert conn.last_params == []


def test_list_lots_product_filter():
    conn = _Conn(rows=[])
    list_lots(conn, product_id=7)
    assert 'l.product_id = %s' in conn.last_sql
    assert conn.last_params == [7]


def test_list_lots_status_filter():
    conn = _Conn(rows=[])
    list_lots(conn, status='quarantine')
    assert 'l.status = %s' in conn.last_sql
    assert conn.last_params == ['quarantine']


def test_list_lots_expiry_filter():
    conn = _Conn(rows=[])
    list_lots(conn, expiry_before='2026-12-31')
    assert 'l.expiry_date <= %s' in conn.last_sql
    assert '2026-12-31' in conn.last_params


def test_list_lots_combined_filters():
    conn = _Conn(rows=[])
    list_lots(conn, product_id=3, status='available')
    assert conn.last_params == [3, 'available']


# ── get_lot / get_lot_by_number ────────────────────────────────────────────

def test_get_lot_returns_dict():
    conn = _Conn(rows=[{'id': 1, 'lot_number': 'LOT-001', 'product_id': 2,
                        'product_name': 'Widget', 'qty': 100.0,
                        'received_date': '2026-01-01', 'expiry_date': None,
                        'status': 'available', 'notes': None,
                        'created_by': None, 'created_at': None}])
    lot = get_lot(conn, lot_id=1)
    assert lot is not None
    assert lot['lot_number'] == 'LOT-001'
    assert lot['qty'] == 100.0


def test_get_lot_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_lot(conn, lot_id=999) is None


def test_get_lot_by_number_queries_by_number():
    conn = _Conn(rows=[])
    get_lot_by_number(conn, 'LOT-001')
    assert 'l.lot_number = %s' in conn.last_sql
    assert conn.last_params == ['LOT-001']


# ── genealogy ──────────────────────────────────────────────────────────────

def test_get_lot_genealogy_with_no_wo_returns_empty_inputs():
    # Simulate: lot exists, but no receive transaction → no WO reference
    lot_row = {'id': 5, 'lot_number': 'FG-LOT-001', 'product_id': 1,
               'product_name': 'Finished Widget', 'qty': 50.0,
               'received_date': '2026-06-01', 'expiry_date': None,
               'status': 'available', 'notes': None,
               'created_by': None, 'created_at': None}
    call_count = [0]

    class _MultiConn:
        def __init__(self): self.calls = []
        def execute(self, sql, params=None):
            self.calls.append((sql, list(params or [])))
            call_count[0] += 1
            if call_count[0] == 1:
                return _Cursor([])  # no receive transaction
            return _Cursor([lot_row])

    conn = _MultiConn()
    result = get_lot_genealogy(conn, lot_id=5)
    assert result['input_lots'] == []
    assert result['lot']['lot_number'] == 'FG-LOT-001'


# ── create_lot ─────────────────────────────────────────────────────────────

def test_create_lot_inserts_and_returns_id():
    from datetime import date
    conn = _Conn(rows=[{'id': 11}])
    lot_id = create_lot(conn, product_id=3, qty=50.0,
                        lot_number='SUPPLIED-001',
                        received_date='2026-06-01',
                        created_by='alice@example.com')
    assert lot_id == 11
    assert 'INSERT INTO lot' in conn.last_sql
    assert 'SUPPLIED-001' in conn.last_params


def test_create_lot_auto_generates_number_when_none():
    call_count = [0]

    class _AutoConn:
        def __init__(self): self.calls = []
        def execute(self, sql, params=None):
            self.calls.append((sql, list(params or [])))
            call_count[0] += 1
            if call_count[0] == 1:
                return _Cursor([])          # next_lot_number LIKE query
            return _Cursor([{'id': 9}])    # INSERT RETURNING

    conn = _AutoConn()
    lot_id = create_lot(conn, product_id=2, qty=10.0)
    assert lot_id == 9
    # First call should be the LIKE query for auto-numbering
    assert 'LIKE' in conn.calls[0][0]


def test_create_lot_clamps_negative_qty():
    conn = _Conn(rows=[{'id': 1}])
    create_lot(conn, product_id=1, qty=-5.0, lot_number='L-001')
    # params order: lot_number, product_id, qty, received_date, expiry_date, notes, created_by
    insert_params = conn.calls[-1][1]
    assert insert_params[2] == 0.0


# ── update_lot_status ──────────────────────────────────────────────────────

def test_update_lot_status_issues_update():
    conn = _Conn()
    update_lot_status(conn, lot_id=3, status='quarantine')
    assert 'UPDATE lot SET status=%s' in conn.last_sql


def test_update_lot_status_rejects_invalid():
    conn = _Conn()
    with pytest.raises(ValueError, match='Unknown lot status'):
        update_lot_status(conn, lot_id=1, status='bogus')


# ── consume_lot_qty ────────────────────────────────────────────────────────

def test_consume_lot_qty_reduces_quantity():
    conn = _Conn(rows=[{'qty': 40.0}])
    new_qty = consume_lot_qty(conn, lot_id=2, qty=10.0)
    assert 'UPDATE lot SET qty' in conn.calls[0][0]
    assert new_qty == 40.0  # value returned by fake cursor


def test_consume_lot_qty_marks_consumed_when_zero():
    call_count = [0]

    class _ZeroConn:
        def __init__(self): self.calls = []
        def execute(self, sql, params=None):
            self.calls.append((sql, list(params or [])))
            call_count[0] += 1
            if call_count[0] == 1:
                return _Cursor([{'qty': 0.0}])   # UPDATE returns 0
            return _Cursor([])                    # UPDATE status=consumed

    conn = _ZeroConn()
    new_qty = consume_lot_qty(conn, lot_id=5, qty=20.0)
    assert new_qty == 0.0
    assert any("status='consumed'" in s for s, _ in conn.calls)


# ── expiry alerts ──────────────────────────────────────────────────────────

def test_get_expiry_alerts_filters_available_and_future():
    conn = _Conn(rows=[])
    get_expiry_alerts(conn, days_ahead=30)
    assert "status = 'available'" in conn.last_sql
    assert conn.last_params == [30]


# ── serial numbers ─────────────────────────────────────────────────────────

def test_list_serials_no_filter():
    conn = _Conn(rows=[])
    list_serials(conn)
    assert conn.last_params == []


def test_list_serials_product_filter():
    conn = _Conn(rows=[])
    list_serials(conn, product_id=5)
    assert 'sn.product_id = %s' in conn.last_sql
    assert conn.last_params == [5]


def test_list_serials_status_filter():
    conn = _Conn(rows=[])
    list_serials(conn, status='issued')
    assert 'sn.status = %s' in conn.last_sql
    assert conn.last_params == ['issued']


def test_create_serial_inserts_and_returns_id():
    conn = _Conn(rows=[{'id': 7}])
    sid = create_serial(conn, 'SN-WIDGET-001', product_id=4, lot_id=2,
                        created_by='bob@example.com')
    assert sid == 7
    assert 'INSERT INTO serial_number' in conn.last_sql
    assert conn.last_params == ['SN-WIDGET-001', 4, 2, None, 'bob@example.com']


def test_create_serial_strips_whitespace():
    conn = _Conn(rows=[{'id': 1}])
    create_serial(conn, '  SN-001  ', product_id=1)
    assert conn.last_params[0] == 'SN-001'


def test_update_serial_status_issues_update():
    conn = _Conn()
    update_serial_status(conn, serial_id=3, status='issued')
    assert 'UPDATE serial_number SET status=%s' in conn.last_sql


def test_update_serial_status_rejects_invalid():
    conn = _Conn()
    with pytest.raises(ValueError, match='Unknown serial status'):
        update_serial_status(conn, serial_id=1, status='broken')
