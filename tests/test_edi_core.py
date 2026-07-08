"""Tests for edi_core — EDI Integration (P4-D).

No live database: a MagicMock connection stands in for psycopg2, with
``execute(...).fetchone()``/``fetchall()`` return values queued via
``side_effect`` in call order (mirrors test_capable_to_promise_core.py).
Cross-module calls (create_so, add_so_item, get_so, get_shipment, etc.)
are patched at their usage site so tests exercise this module's own
parsing/generation logic in isolation.
"""

from unittest.mock import MagicMock, patch

import pytest

from manufacturing.edi_core import (
    ensure_edi_tables, set_trading_partner, get_trading_partner,
    set_item_xref, resolve_product_id, list_transaction_log,
    _split_segments, _split_elements, _x12_date,
    parse_850, create_so_from_850,
    generate_855, generate_856, generate_810,
)


SAMPLE_850 = """ISA*00*        *00*        *ZZ*SENDER   *ZZ*RECEIVER *260707*1200*U*00401*1*0*P*>~
GS*PO*SENDER*RECEIVER*20260707*1200*1*X*004010~
ST*850*0001~
BEG*00*NE*PO123456**20260707~
N1*ST*Acme Warehouse~
PO1*1*10*EA*25.50*PE*BP*PARTNER-SKU-1~
PID*F****Widget Deluxe~
PO1*2*5*EA*100.00*PE*BP*PARTNER-SKU-UNMAPPED~
CTT*2~
SE*9*0001~
GE*1*1~
IEA*1*000000001~"""


def _conn(fetchone_results=None, fetchall_results=None):
    conn = MagicMock()
    cursor = MagicMock()
    if fetchone_results is not None:
        cursor.fetchone.side_effect = fetchone_results
    if fetchall_results is not None:
        cursor.fetchall.side_effect = fetchall_results
    conn.execute.return_value = cursor
    return conn


# ── setup ────────────────────────────────────────────────────────────────

def test_ensure_edi_tables_creates_all_three():
    conn = MagicMock()
    ensure_edi_tables(conn)
    calls = [c[0][0] for c in conn.execute.call_args_list]
    assert any('CREATE TABLE IF NOT EXISTS edi_trading_partner (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS edi_partner_item_xref (' in c for c in calls)
    assert any('CREATE TABLE IF NOT EXISTS edi_transaction_log (' in c for c in calls)


# ── segment/element splitting ────────────────────────────────────────────

def test_split_segments_handles_tilde_delimited():
    result = _split_segments("ST*850*0001~BEG*00*NE*PO1~SE*2*0001~")
    assert result == ["ST*850*0001", "BEG*00*NE*PO1", "SE*2*0001"]


def test_split_segments_handles_one_per_line():
    result = _split_segments("ST*850*0001\nBEG*00*NE*PO1\nSE*2*0001")
    assert result == ["ST*850*0001", "BEG*00*NE*PO1", "SE*2*0001"]


def test_split_elements():
    assert _split_elements("PO1*1*10*EA*25.50") == ['PO1', '1', '10', 'EA', '25.50']


def test_x12_date_parses_yyyymmdd():
    assert _x12_date('20260707') == '2026-07-07'


def test_x12_date_returns_none_for_garbage():
    assert _x12_date('') is None
    assert _x12_date('notadate') is None


# ── trading partner / item xref ──────────────────────────────────────────

def test_set_trading_partner_upserts():
    conn = MagicMock()
    set_trading_partner(conn, 5, 'Acme Corp', 'SENDERID', 'RECEIVERID')
    sql, params = conn.execute.call_args[0]
    assert 'ON CONFLICT (customer_id) DO UPDATE' in sql
    assert params[:4] == (5, 'Acme Corp', 'SENDERID', 'RECEIVERID')


def test_get_trading_partner_returns_none_when_missing():
    conn = _conn(fetchone_results=[None])
    assert get_trading_partner(conn, 999) is None


def test_set_item_xref_raises_without_partner_item_number():
    conn = MagicMock()
    with pytest.raises(ValueError):
        set_item_xref(conn, 5, '', 10)
    assert conn.execute.call_count == 0


def test_set_item_xref_upserts():
    conn = MagicMock()
    set_item_xref(conn, 5, 'PARTNER-SKU-1', 10)
    sql, params = conn.execute.call_args[0]
    assert 'ON CONFLICT (customer_id, partner_item_number) DO UPDATE' in sql
    assert params == (5, 'PARTNER-SKU-1', 10)


def test_resolve_product_id_mapped():
    conn = _conn(fetchone_results=[{'product_id': 42}])
    assert resolve_product_id(conn, 5, 'PARTNER-SKU-1') == 42


def test_resolve_product_id_unmapped():
    conn = _conn(fetchone_results=[None])
    assert resolve_product_id(conn, 5, 'UNKNOWN-SKU') is None


def test_list_transaction_log_returns_rows():
    conn = _conn(fetchall_results=[[{'id': 1, 'doc_type': '850'}]])
    result = list_transaction_log(conn)
    assert result == [{'id': 1, 'doc_type': '850'}]


# ── parse_850 ─────────────────────────────────────────────────────────────

def test_parse_850_extracts_header_fields():
    conn = _conn(fetchone_results=[{'product_id': 42}, None])
    result = parse_850(SAMPLE_850, customer_id=1, conn=conn)
    assert result['po_number'] == 'PO123456'
    assert result['order_date'] == '2026-07-07'
    assert result['ship_to'] == 'Acme Warehouse'


def test_parse_850_extracts_lines_with_mapped_and_unmapped_items():
    conn = _conn(fetchone_results=[{'product_id': 42}, None])
    result = parse_850(SAMPLE_850, customer_id=1, conn=conn)
    lines = result['lines']
    assert len(lines) == 2

    mapped = lines[0]
    assert mapped['partner_item_number'] == 'PARTNER-SKU-1'
    assert mapped['product_id'] == 42
    assert mapped['description'] == 'Widget Deluxe'
    assert mapped['qty'] == 10.0
    assert mapped['unit_price'] == 25.50

    unmapped = lines[1]
    assert unmapped['partner_item_number'] == 'PARTNER-SKU-UNMAPPED'
    assert unmapped['product_id'] is None
    assert unmapped['description'] == 'Item PARTNER-SKU-UNMAPPED'

    assert result['unmapped_count'] == 1


# ── create_so_from_850 ───────────────────────────────────────────────────

def test_create_so_from_850_calls_existing_so_creation_functions():
    parsed = {
        'po_number': 'PO123456', 'order_date': '2026-07-07', 'ship_to': 'Acme',
        'lines': [
            {'partner_item_number': 'X1', 'product_id': 42,
             'description': 'Widget', 'qty': 10.0, 'unit_price': 25.5},
            {'partner_item_number': 'X2', 'product_id': None,
             'description': 'Unmapped Item', 'qty': 5.0, 'unit_price': 100.0},
        ],
        'unmapped_count': 1,
    }
    with patch('manufacturing.edi_core.parse_850', return_value=parsed), \
         patch('manufacturing.edi_core.next_so_number', return_value='SO-2026-0001'), \
         patch('manufacturing.edi_core.create_so', return_value=7) as mock_create_so, \
         patch('manufacturing.edi_core.add_so_item') as mock_add_item:
        conn = MagicMock()
        result = create_so_from_850(conn, customer_id=1, raw_edi=SAMPLE_850, created_by='eric')

    assert result == {'so_id': 7, 'so_number': 'SO-2026-0001',
                      'unmapped_count': 1, 'line_count': 2}
    mock_create_so.assert_called_once()
    _, kwargs = mock_create_so.call_args
    assert kwargs['customer_id'] == 1
    assert kwargs['order_date'] == '2026-07-07'
    assert 'PO123456' in kwargs['notes']

    assert mock_add_item.call_count == 2
    first_call = mock_add_item.call_args_list[0]
    assert first_call[0][2] == 'Widget'
    assert first_call[1]['product_id'] == 42
    assert first_call[1]['qty'] == 10.0
    assert first_call[1]['unit_price'] == 25.5

    # transaction was logged
    log_calls = [c for c in conn.execute.call_args_list
                 if 'INSERT INTO edi_transaction_log' in c[0][0]]
    assert len(log_calls) == 1


# ── generate_855 / generate_856 / generate_810 ──────────────────────────

def test_generate_855_reflects_so_lines():
    so = {'id': 1, 'so_number': 'SO-2026-0001', 'customer_id': 5}
    items = [{'id': 1, 'description': 'Widget', 'product_id': 10,
              'product_name': 'Widget', 'qty': 3, 'unit_price': 9.99}]
    with patch('manufacturing.edi_core.get_so', return_value=so), \
         patch('manufacturing.edi_core.get_so_items', return_value=items), \
         patch('manufacturing.edi_core.get_trading_partner', return_value=None):
        conn = MagicMock()
        content = generate_855(conn, 1, created_by='eric')

    assert 'ST*855*0001' in content
    assert 'SO-2026-0001' in content
    assert 'PO1*1*3*EA*9.99' in content
    assert content.count('~') == content.count('\n') + 1  # one segment per line, tilde-terminated


def test_generate_855_raises_when_so_missing():
    with patch('manufacturing.edi_core.get_so', return_value=None):
        with pytest.raises(ValueError):
            generate_855(MagicMock(), 999)


def test_generate_856_reflects_shipment_and_tracking():
    shipment = {'id': 1, 'ship_number': 'SH-2026-0001', 'so_id': 1,
                'carrier': 'UPS', 'tracking_number': '1Z999AA1', 'status': 'shipped'}
    items = [{'id': 1, 'description': 'Widget', 'qty': 3, 'product_name': 'Widget'}]
    so = {'id': 1, 'so_number': 'SO-2026-0001', 'customer_id': 5}
    with patch('manufacturing.edi_core.get_shipment', return_value=shipment), \
         patch('manufacturing.edi_core.get_shipment_items', return_value=items), \
         patch('manufacturing.edi_core.get_so', return_value=so), \
         patch('manufacturing.edi_core.get_trading_partner', return_value=None):
        conn = MagicMock()
        content = generate_856(conn, 1, created_by='eric')

    assert 'ST*856*0001' in content
    assert 'SH-2026-0001' in content
    assert 'UPS' in content
    assert '1Z999AA1' in content
    assert 'SN1*1*3*EA' in content


def test_generate_856_raises_when_shipment_missing():
    with patch('manufacturing.edi_core.get_shipment', return_value=None):
        with pytest.raises(ValueError):
            generate_856(MagicMock(), 999)


def test_generate_810_reflects_invoice_amount():
    invoice = {'id': 1, 'customer_id': 5, 'invoice_number': 'INV-0001',
               'invoice_date': '2026-07-07', 'amount': 150.0, 'description': 'Widgets'}
    with patch('manufacturing.edi_core.get_ar_invoice', return_value=invoice), \
         patch('manufacturing.edi_core.get_trading_partner', return_value=None):
        conn = MagicMock()
        content = generate_810(conn, 1, created_by='eric')

    assert 'ST*810*0001' in content
    assert 'INV-0001' in content
    assert '150.0' in content
    assert 'Widgets' in content


def test_generate_810_raises_when_invoice_missing():
    with patch('manufacturing.edi_core.get_ar_invoice', return_value=None):
        with pytest.raises(ValueError):
            generate_810(MagicMock(), 999)


def test_generate_855_se_segment_count_matches_transaction_segments():
    so = {'id': 1, 'so_number': 'SO-1', 'customer_id': 5}
    items = []
    with patch('manufacturing.edi_core.get_so', return_value=so), \
         patch('manufacturing.edi_core.get_so_items', return_value=items), \
         patch('manufacturing.edi_core.get_trading_partner', return_value=None):
        content = generate_855(MagicMock(), 1)

    segments = [s.strip() for s in content.split('~') if s.strip()]
    # ST, BAK, CTT (no PO1 lines) = 3, plus SE itself = 4
    se_segment = next(s for s in segments if s.startswith('SE*'))
    assert se_segment == 'SE*4*0001'
