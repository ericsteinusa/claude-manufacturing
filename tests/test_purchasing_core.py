"""
Tests for manufacturing/purchasing_core.py — pure unit tests, no Qt, no DB.
"""

from unittest.mock import MagicMock

from manufacturing.purchasing_core import get_purchasing_dashboard


def _conn(po_row, recent_rows):
    c = MagicMock()
    mock1 = MagicMock(); mock1.fetchone.return_value = po_row
    mock2 = MagicMock(); mock2.fetchall.return_value = recent_rows
    c.execute.side_effect = [mock1, mock2]
    return c


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_returns_dict_with_pos_key():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    result = get_purchasing_dashboard(conn)
    assert 'pos' in result


def test_returns_dict_with_recent_pos_key():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    result = get_purchasing_dashboard(conn)
    assert 'recent_pos' in result


# ---------------------------------------------------------------------------
# pos stat values
# ---------------------------------------------------------------------------

def _stats_conn(draft=0, pending_approval=0, sent=0, partial=0,
                received=0, open_=0, total=0):
    row = {
        'draft': draft,
        'pending_approval': pending_approval,
        'sent': sent,
        'partial': partial,
        'received': received,
        'open': open_,
        'total': total,
    }
    return _conn(row, [])


def test_pos_draft_value():
    conn = _stats_conn(draft=3)
    assert get_purchasing_dashboard(conn)['pos']['draft'] == 3


def test_pos_pending_approval_value():
    conn = _stats_conn(pending_approval=5)
    assert get_purchasing_dashboard(conn)['pos']['pending_approval'] == 5


def test_pos_sent_value():
    conn = _stats_conn(sent=7)
    assert get_purchasing_dashboard(conn)['pos']['sent'] == 7


def test_pos_partial_value():
    conn = _stats_conn(partial=2)
    assert get_purchasing_dashboard(conn)['pos']['partial'] == 2


def test_pos_received_value():
    conn = _stats_conn(received=10)
    assert get_purchasing_dashboard(conn)['pos']['received'] == 10


def test_pos_open_value():
    conn = _stats_conn(open_=8)
    assert get_purchasing_dashboard(conn)['pos']['open'] == 8


def test_pos_total_value():
    conn = _stats_conn(total=20)
    assert get_purchasing_dashboard(conn)['pos']['total'] == 20


# ---------------------------------------------------------------------------
# recent_pos list
# ---------------------------------------------------------------------------

def test_recent_pos_is_list():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    assert isinstance(get_purchasing_dashboard(conn)['recent_pos'], list)


def test_recent_pos_items_have_po_number():
    row = {'id': 1, 'po_number': 'PO-2026-0001', 'order_date': '2026-01-01',
           'expected_date': '2026-01-15', 'status': 'sent', 'supplier_name': 'Acme'}
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 1,
                  'partial': 0, 'received': 0, 'open': 1, 'total': 1}, [row])
    result = get_purchasing_dashboard(conn)
    assert result['recent_pos'][0]['po_number'] == 'PO-2026-0001'


def test_recent_pos_items_have_supplier_name():
    row = {'id': 1, 'po_number': 'PO-2026-0001', 'order_date': '2026-01-01',
           'expected_date': '2026-01-15', 'status': 'sent', 'supplier_name': 'Acme Corp'}
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 1,
                  'partial': 0, 'received': 0, 'open': 1, 'total': 1}, [row])
    result = get_purchasing_dashboard(conn)
    assert result['recent_pos'][0]['supplier_name'] == 'Acme Corp'


def test_recent_pos_items_have_status():
    row = {'id': 1, 'po_number': 'PO-2026-0001', 'order_date': '2026-01-01',
           'expected_date': '2026-01-15', 'status': 'partial', 'supplier_name': ''}
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 1, 'received': 0, 'open': 1, 'total': 1}, [row])
    result = get_purchasing_dashboard(conn)
    assert result['recent_pos'][0]['status'] == 'partial'


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_pos_empty_when_fetchone_returns_none():
    conn = _conn(None, [])
    result = get_purchasing_dashboard(conn)
    assert result['pos'] == {}


def test_recent_pos_empty_when_fetchall_returns_empty():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    result = get_purchasing_dashboard(conn)
    assert result['recent_pos'] == []


# ---------------------------------------------------------------------------
# SQL sanity checks
# ---------------------------------------------------------------------------

def test_execute_called_exactly_twice():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    get_purchasing_dashboard(conn)
    assert conn.execute.call_count == 2


def test_first_sql_references_purchase_order_table():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    get_purchasing_dashboard(conn)
    first_sql = conn.execute.call_args_list[0][0][0]
    assert 'purchase_order' in first_sql


def test_second_sql_uses_limit_8():
    conn = _conn({'draft': 0, 'pending_approval': 0, 'sent': 0,
                  'partial': 0, 'received': 0, 'open': 0, 'total': 0}, [])
    get_purchasing_dashboard(conn)
    second_sql = conn.execute.call_args_list[1][0][0]
    assert 'LIMIT 8' in second_sql
