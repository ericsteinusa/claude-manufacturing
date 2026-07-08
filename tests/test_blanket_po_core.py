"""Tests for blanket_po_core — Blanket Purchase Orders & Call-offs (P3-E).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_wms_core.py). Same-module
helper calls (``get_blanket_po``, ``list_releases``, ``_sync_status``) are
patched via unittest.mock.patch where isolating write-path validation logic
from the read-path query chain keeps a test focused.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from manufacturing.blanket_po_core import (
    ensure_blanket_po_tables, next_blanket_number, _sync_status,
    list_blanket_pos, get_blanket_po, list_releases,
    create_blanket_po, create_release, cancel_blanket_po,
)

YEAR = datetime.now().year


def _conn(fetchone_results=None, fetchall_results=None):
    """A MagicMock conn whose execute(...) returns one shared cursor mock;
    .fetchone()/.fetchall() replay the given results in call order."""
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── setup ────────────────────────────────────────────────────────────────

def test_ensure_blanket_po_tables_creates_both_tables():
    conn = MagicMock()
    ensure_blanket_po_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS blanket_po (' in c for c in calls)
    assert any('blanket_po_release' in c for c in calls)


# ── numbering ────────────────────────────────────────────────────────────

def test_next_blanket_number_first_of_year():
    conn = _conn(fetchall_results=[[]])
    assert next_blanket_number(conn) == f"BPO-{YEAR}-0001"


def test_next_blanket_number_increments_from_max_suffix():
    conn = _conn(fetchall_results=[[
        {'blanket_number': f'BPO-{YEAR}-0001'},
        {'blanket_number': f'BPO-{YEAR}-0003'},
    ]])
    assert next_blanket_number(conn) == f"BPO-{YEAR}-0004"


# ── create_blanket_po ────────────────────────────────────────────────────

def test_create_blanket_po_raises_without_total_value_or_qty():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_blanket_po(conn, 1, 'desc', 0, 0, '2026-01-01', '2026-12-31', '', 'eric')
    assert conn.execute.call_count == 0


def test_create_blanket_po_raises_bad_date_range():
    conn = MagicMock()
    with pytest.raises(ValueError):
        create_blanket_po(conn, 1, 'desc', 1000, 0, '2026-12-31', '2026-01-01', '', 'eric')
    assert conn.execute.call_count == 0


def test_create_blanket_po_inserts_and_returns_id():
    conn = _conn(fetchall_results=[[]], fetchone_results=[{'id': 5}])
    bp_id = create_blanket_po(
        conn, 1, 'Steel coil supply', 50000, 0,
        '2026-01-01', '2026-12-31', 'annual contract', 'eric')
    assert bp_id == 5
    insert_sql, insert_params = conn.execute.call_args_list[-1][0]
    assert 'INSERT INTO blanket_po' in insert_sql
    assert insert_params[0] == f"BPO-{YEAR}-0001"
    assert insert_params[1] == 1
    assert insert_params[3] == 50000.0
    assert insert_params[7] == 'open'


# ── _sync_status ─────────────────────────────────────────────────────────

def test_sync_status_closes_when_fully_released_by_value():
    conn = _conn(fetchone_results=[
        {'status': 'open', 'total_value': 100.0, 'total_qty': 0.0, 'end_date': ''},
        {'qty': 0.0, 'value': 100.0},
    ])
    assert _sync_status(conn, 1) == 'closed'
    update_calls = [c for c in conn.execute.call_args_list
                    if 'UPDATE blanket_po SET status' in c[0][0]]
    assert len(update_calls) == 1
    assert update_calls[0][0][1] == ('closed', 1)


def test_sync_status_closes_when_fully_released_by_qty():
    conn = _conn(fetchone_results=[
        {'status': 'open', 'total_value': 0.0, 'total_qty': 50.0, 'end_date': ''},
        {'qty': 60.0, 'value': 0.0},
    ])
    assert _sync_status(conn, 1) == 'closed'


def test_sync_status_expires_when_past_end_date():
    conn = _conn(fetchone_results=[
        {'status': 'open', 'total_value': 100.0, 'total_qty': 0.0, 'end_date': '2020-01-01'},
        {'qty': 0.0, 'value': 0.0},
    ])
    assert _sync_status(conn, 1) == 'expired'


def test_sync_status_noop_when_still_valid():
    conn = _conn(fetchone_results=[
        {'status': 'open', 'total_value': 100.0, 'total_qty': 0.0, 'end_date': '2099-01-01'},
        {'qty': 0.0, 'value': 10.0},
    ])
    assert _sync_status(conn, 1) == 'open'
    update_calls = [c for c in conn.execute.call_args_list
                    if 'UPDATE blanket_po SET status' in c[0][0]]
    assert len(update_calls) == 0


def test_sync_status_short_circuits_for_cancelled():
    conn = _conn(fetchone_results=[
        {'status': 'cancelled', 'total_value': 0.0, 'total_qty': 0.0, 'end_date': ''},
    ])
    assert _sync_status(conn, 1) == 'cancelled'
    assert conn.execute.call_count == 1


def test_sync_status_short_circuits_for_closed():
    conn = _conn(fetchone_results=[
        {'status': 'closed', 'total_value': 0.0, 'total_qty': 0.0, 'end_date': ''},
    ])
    assert _sync_status(conn, 1) == 'closed'
    assert conn.execute.call_count == 1


def test_sync_status_returns_empty_for_missing_blanket():
    conn = _conn(fetchone_results=[None])
    assert _sync_status(conn, 999) == ''


# ── read ─────────────────────────────────────────────────────────────────

def test_get_blanket_po_returns_balances():
    conn = _conn(fetchone_results=[
        {'status': 'open', 'total_value': 1000.0, 'total_qty': 0.0, 'end_date': '2099-01-01'},
        {'qty': 0.0, 'value': 300.0},
        {'id': 1, 'blanket_number': f'BPO-{YEAR}-0001', 'supplier_id': 2,
         'description': 'Widgets', 'total_value': 1000.0, 'total_qty': 0.0,
         'start_date': '2026-01-01', 'end_date': '2099-01-01', 'status': 'open',
         'notes': '', 'created_by': 'eric', 'created_at': 'now',
         'supplier_name': 'Acme Corp'},
        {'qty': 0.0, 'value': 300.0},
    ])
    bp = get_blanket_po(conn, 1)
    assert bp['status'] == 'open'
    assert bp['released_value'] == 300.0
    assert bp['remaining_value'] == 700.0


def test_get_blanket_po_returns_none_when_missing():
    conn = _conn(fetchone_results=[None, None])
    assert get_blanket_po(conn, 999) is None


def test_list_blanket_pos_filters_by_synced_status():
    with patch('manufacturing.blanket_po_core._sync_status',
               side_effect=lambda conn, bp_id: 'open' if bp_id == 1 else 'closed'), \
         patch('manufacturing.blanket_po_core._with_balances',
               side_effect=lambda conn, d: d):
        conn = _conn(fetchall_results=[[{'id': 1}, {'id': 2}]])
        result = list_blanket_pos(conn, status='open')
        assert [r['id'] for r in result] == [1]


def test_list_releases_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'release_number': 'REL-001'}]])
    assert list_releases(conn, 5) == [{'id': 1, 'release_number': 'REL-001'}]


# ── create_release ───────────────────────────────────────────────────────

def test_create_release_raises_if_blanket_not_found():
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=None):
        conn = MagicMock()
        with pytest.raises(ValueError):
            create_release(conn, 1, 10, 100.0, '2026-08-01', '', 'eric')


def test_create_release_raises_if_not_open():
    blanket = {'status': 'closed', 'total_value': 0.0, 'total_qty': 0.0,
               'remaining_value': 0.0, 'remaining_qty': 0.0}
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=blanket):
        conn = MagicMock()
        with pytest.raises(ValueError):
            create_release(conn, 1, 10, 100.0, '2026-08-01', '', 'eric')


def test_create_release_raises_if_exceeds_remaining_value():
    blanket = {'status': 'open', 'total_value': 1000.0, 'total_qty': 0.0,
               'remaining_value': 200.0, 'remaining_qty': 0.0}
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=blanket):
        conn = MagicMock()
        with pytest.raises(ValueError):
            create_release(conn, 1, 0, 500.0, '2026-08-01', '', 'eric')


def test_create_release_raises_if_exceeds_remaining_qty():
    blanket = {'status': 'open', 'total_value': 0.0, 'total_qty': 100.0,
               'remaining_value': 0.0, 'remaining_qty': 20.0}
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=blanket):
        conn = MagicMock()
        with pytest.raises(ValueError):
            create_release(conn, 1, 50, 0, '2026-08-01', '', 'eric')


def test_create_release_inserts_and_syncs_status():
    blanket = {'status': 'open', 'total_value': 1000.0, 'total_qty': 0.0,
               'remaining_value': 1000.0, 'remaining_qty': 0.0}
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=blanket), \
         patch('manufacturing.blanket_po_core.list_releases', return_value=[]), \
         patch('manufacturing.blanket_po_core._sync_status') as mock_sync:
        conn = _conn(fetchone_results=[{'id': 7}])
        release_id = create_release(conn, 1, 0, 250.0, '2026-08-01', 'note', 'eric')
        assert release_id == 7
        insert_sql, insert_params = conn.execute.call_args_list[-1][0]
        assert 'INSERT INTO blanket_po_release' in insert_sql
        assert insert_params[1] == 'REL-001'
        mock_sync.assert_called_once_with(conn, 1)


def test_create_release_numbers_sequentially():
    blanket = {'status': 'open', 'total_value': 1000.0, 'total_qty': 0.0,
               'remaining_value': 1000.0, 'remaining_qty': 0.0}
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=blanket), \
         patch('manufacturing.blanket_po_core.list_releases', return_value=[{}, {}]), \
         patch('manufacturing.blanket_po_core._sync_status'):
        conn = _conn(fetchone_results=[{'id': 9}])
        create_release(conn, 1, 0, 100.0, '2026-08-01', '', 'eric')
        insert_params = conn.execute.call_args_list[-1][0][1]
        assert insert_params[1] == 'REL-003'


# ── cancel_blanket_po ────────────────────────────────────────────────────

def test_cancel_blanket_po_success():
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value={'status': 'open'}):
        conn = MagicMock()
        cancel_blanket_po(conn, 1)
        update_sql, update_params = conn.execute.call_args_list[-1][0]
        assert 'UPDATE blanket_po SET status' in update_sql
        assert update_params == ('cancelled', 1)


def test_cancel_blanket_po_raises_if_not_open():
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value={'status': 'closed'}):
        conn = MagicMock()
        with pytest.raises(ValueError):
            cancel_blanket_po(conn, 1)


def test_cancel_blanket_po_raises_if_missing():
    with patch('manufacturing.blanket_po_core.get_blanket_po', return_value=None):
        conn = MagicMock()
        with pytest.raises(ValueError):
            cancel_blanket_po(conn, 1)
