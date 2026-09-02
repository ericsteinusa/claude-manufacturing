"""Tests for costing_core — standard cost roll-up, WO variance, GL posting."""

import pytest

from manufacturing.costing_core import (
    GL_CATEGORIES,
    ensure_costing_tables,
    get_gl_account_map, set_gl_account_map, list_gl_account_map,
    roll_standard_cost, get_standard_cost, list_cost_history,
    compute_wo_actual_cost, save_wo_actual_cost, get_wo_cost,
    post_po_receipt_gl, post_wo_material_issue_gl, post_wo_close_gl,
    _post_lines_on_conn,
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
    """Simple fake connection that replays one set of rows for every execute."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)

    def executemany(self, sql, data):
        for row in data:
            self.calls.append((sql, list(row)))

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


class _MultiConn:
    """Fake connection whose responses are driven by a queue of row-sets."""

    def __init__(self, responses):
        # responses: list of (rows | None)
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])

    def executemany(self, sql, data):
        for row in data:
            self.calls.append((sql, list(row)))

    @property
    def last_sql(self):
        return self.calls[-1][0]


# ── GL_CATEGORIES constant ────────────────────────────────────────────────

def test_gl_categories_includes_all_expected():
    expected = {'raw_material', 'wip', 'finished_goods', 'cogs',
                'material_variance', 'labor_variance', 'ap_payable'}
    assert set(GL_CATEGORIES) == expected


# ── ensure_costing_tables ────────────────────────────────────────────────

def test_ensure_costing_tables_self_heals_item_type_column():
    # A genuinely fresh product table (no seed_sample_products.py run) has no
    # item_type column — _get_bom_lines selects p.item_type, so this must
    # self-heal it the same way it already does for workcenter.overhead_rate.
    conn = _Conn(rows=[])
    ensure_costing_tables(conn)
    assert any(
        'ALTER TABLE product ADD COLUMN IF NOT EXISTS' in sql and 'item_type' in sql
        for sql, _ in conn.calls
    )


# ── GL account map ─────────────────────────────────────────────────────────

def test_get_gl_account_map_returns_dict():
    conn = _Conn(rows=[
        {'category': 'raw_material', 'account_number': '1300'},
        {'category': 'wip', 'account_number': '1310'},
    ])
    mapping = get_gl_account_map(conn)
    assert mapping == {'raw_material': '1300', 'wip': '1310'}


def test_get_gl_account_map_empty_when_no_rows():
    conn = _Conn(rows=[])
    assert get_gl_account_map(conn) == {}


def test_set_gl_account_map_inserts_upsert():
    conn = _Conn()
    set_gl_account_map(conn, 'wip', '1310', description='WIP account')
    assert 'INSERT INTO gl_account_map' in conn.last_sql
    assert 'ON CONFLICT' in conn.last_sql
    assert conn.last_params == ['wip', '1310', 'WIP account']


def test_set_gl_account_map_rejects_unknown_category():
    conn = _Conn()
    with pytest.raises(ValueError, match='Unknown GL category'):
        set_gl_account_map(conn, 'bogus_category', '9999')


def test_list_gl_account_map_returns_all_rows():
    conn = _Conn(rows=[
        {'id': 1, 'category': 'wip', 'account_number': '1310',
         'description': None, 'is_active': True},
    ])
    result = list_gl_account_map(conn)
    assert len(result) == 1
    assert result[0]['category'] == 'wip'


# ── Standard cost roll-up ──────────────────────────────────────────────────

def test_roll_standard_cost_buy_item_uses_purchase_price():
    # product query → buy item with purchase_price=50
    # BOM query → no lines (buy items have no BOM)
    # routing query → no rows
    # INSERT cost_roll
    conn = _MultiConn([
        [{'item_type': 'buy', 'purchase_price': 50.0}],  # product row
        [],                                               # INSERT cost_roll RETURNING (not used)
    ])
    result = roll_standard_cost(conn, product_id=1, created_by='test')
    assert result['std_material_cost'] == 50.0
    assert result['std_labor_cost'] == 0.0
    assert result['total_std_cost'] == 50.0
    insert_calls = [s for s, _ in conn.calls if 'INSERT INTO cost_roll' in s]
    assert len(insert_calls) == 1


def test_roll_standard_cost_make_item_sums_components():
    # product=2 is 'make'; it has 1 component (product=1, qty=2, scrap=0)
    # component product=1 is 'buy' with purchase_price=10 → child cost=10
    # routing for product=2 → labor=5, overhead=2
    responses = [
        # product_id=2: make item
        [{'item_type': 'make', 'purchase_price': 0.0}],
        # BOM lines for product 2
        [{'component_id': 1, 'qty_required': 2.0, 'scrap_pct': 0.0,
          'name': 'Part A', 'item_type': 'buy', 'purchase_price': 10.0}],
        # Recursive: product_id=1 is buy
        [{'item_type': 'buy', 'purchase_price': 10.0}],
        # Recursive INSERT cost_roll for product 1
        [],
        # routing for product 2
        [{'labor_cost': 5.0, 'overhead_cost': 2.0}],
        # INSERT cost_roll for product 2
        [],
    ]
    conn = _MultiConn(responses)
    result = roll_standard_cost(conn, product_id=2, created_by='test')
    # material = 2 × 10 (component cost × qty) = 20
    assert result['std_material_cost'] == 20.0
    assert result['std_labor_cost'] == 5.0
    assert result['std_overhead_cost'] == 2.0
    assert result['total_std_cost'] == 27.0


def test_roll_standard_cost_respects_scrap_pct():
    # 1 component, qty=1, scrap_pct=10%, component price=100
    # inflated qty = 1 × 1.1 = 1.1 → material cost = 110
    responses = [
        [{'item_type': 'make', 'purchase_price': 0.0}],
        [{'component_id': 5, 'qty_required': 1.0, 'scrap_pct': 10.0,
          'name': 'Part B', 'item_type': 'buy', 'purchase_price': 100.0}],
        [{'item_type': 'buy', 'purchase_price': 100.0}],
        [],
        [{'labor_cost': 0.0, 'overhead_cost': 0.0}],
        [],
    ]
    conn = _MultiConn(responses)
    result = roll_standard_cost(conn, product_id=3)
    assert abs(result['std_material_cost'] - 110.0) < 0.001


def test_roll_standard_cost_stops_at_cycle():
    # Cycle: product visits itself → should return zeros without infinite loop
    responses = [
        [{'item_type': 'make', 'purchase_price': 0.0}],
        [],   # BOM: no lines (or would create cycle — _visited guards it)
        [{'labor_cost': 0.0, 'overhead_cost': 0.0}],
        [],
    ]
    conn = _MultiConn(responses)
    _visited = {10}  # pretend product 10 is already in the call stack
    result = roll_standard_cost(conn, product_id=10, _visited=_visited)
    assert result['total_std_cost'] == 0.0


def test_roll_standard_cost_stops_at_max_depth():
    from manufacturing.costing_core import _MAX_DEPTH
    conn = _Conn()
    result = roll_standard_cost(conn, product_id=1, _depth=_MAX_DEPTH + 1)
    assert result['total_std_cost'] == 0.0
    assert conn.calls == []   # no DB queries when depth exceeded


def test_get_standard_cost_returns_latest():
    conn = _Conn(rows=[
        {'id': 5, 'product_id': 1, 'effective_date': '2026-06-28',
         'std_material_cost': 20.0, 'std_labor_cost': 5.0,
         'std_overhead_cost': 2.0, 'total_std_cost': 27.0,
         'created_by': 'test', 'created_at': None},
    ])
    row = get_standard_cost(conn, product_id=1)
    assert row is not None
    assert row['total_std_cost'] == 27.0
    assert 'ORDER BY effective_date DESC' in conn.last_sql


def test_get_standard_cost_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_standard_cost(conn, product_id=99) is None


def test_list_cost_history_orders_newest_first():
    conn = _Conn(rows=[])
    list_cost_history(conn, product_id=3)
    assert 'ORDER BY effective_date DESC' in conn.last_sql
    assert conn.last_params == [3]


# ── Actual cost computation ────────────────────────────────────────────────

def test_compute_wo_actual_cost_sums_materials_and_labor():
    responses = [
        [{'actual_material_cost': 80.0}],
        [{'actual_labor_cost': 30.0, 'actual_overhead_cost': 6.0}],
    ]
    conn = _MultiConn(responses)
    result = compute_wo_actual_cost(conn, wo_id=5)
    assert result['actual_material_cost'] == 80.0
    assert result['actual_labor_cost'] == 30.0
    assert result['actual_overhead_cost'] == 6.0
    assert result['total_actual_cost'] == 116.0


def test_compute_wo_actual_cost_returns_zeros_on_no_rows():
    conn = _MultiConn([[None], [None]])
    result = compute_wo_actual_cost(conn, wo_id=1)
    assert result['total_actual_cost'] == 0.0


def test_save_wo_actual_cost_raises_on_missing_wo():
    conn = _Conn(rows=[])  # work_order query returns nothing
    with pytest.raises(ValueError, match='not found'):
        save_wo_actual_cost(conn, wo_id=999)


def test_save_wo_actual_cost_computes_variance():
    # WO: product_id=2, qty=10
    # actual: material=120, labor=50, overhead=10 → total=180
    # std cost_roll: total=15 per unit × 10 = 150
    # variance = 180 - 150 = 30
    responses = [
        # work_order row
        [{'product_id': 2, 'quantity': 10}],
        # compute_wo_actual_cost: material sum
        [{'actual_material_cost': 120.0}],
        # compute_wo_actual_cost: labor/overhead sum
        [{'actual_labor_cost': 50.0, 'actual_overhead_cost': 10.0}],
        # get_standard_cost: cost_roll
        [{'id': 1, 'product_id': 2, 'effective_date': '2026-06-01',
          'std_material_cost': 10.0, 'std_labor_cost': 3.0,
          'std_overhead_cost': 2.0, 'total_std_cost': 15.0,
          'created_by': None, 'created_at': None}],
        # INSERT/ON CONFLICT DO UPDATE
        [],
    ]
    conn = _MultiConn(responses)
    result = save_wo_actual_cost(conn, wo_id=7, created_by='alice@example.com')
    assert result['total_actual_cost'] == 180.0
    assert result['std_cost'] == 150.0
    assert abs(result['total_variance'] - 30.0) < 0.001
    insert_calls = [s for s, _ in conn.calls if 'INSERT INTO wo_cost_actual' in s]
    assert len(insert_calls) == 1


def test_get_wo_cost_returns_none_when_absent():
    conn = _Conn(rows=[])
    assert get_wo_cost(conn, wo_id=1) is None


def test_get_wo_cost_returns_dict():
    conn = _Conn(rows=[{'id': 1, 'wo_id': 5, 'total_actual_cost': 150.0,
                        'std_cost': 120.0, 'total_variance': 30.0,
                        'material_variance': 20.0, 'labor_variance': 10.0,
                        'actual_material_cost': 100.0, 'actual_labor_cost': 40.0,
                        'actual_overhead_cost': 10.0, 'created_by': None,
                        'created_at': None}])
    result = get_wo_cost(conn, wo_id=5)
    assert result is not None
    assert result['total_variance'] == 30.0


# ── GL posting helpers ─────────────────────────────────────────────────────

def test_post_lines_on_conn_aborts_when_account_missing():
    conn = _Conn(rows=[])  # SELECT id FROM gl_account → no rows
    jid = _post_lines_on_conn(
        conn, '2026-06-28', 'REF-1', 'Test',
        [('9999', 100.0, 0.0, 'test')], 'System',
    )
    assert jid is None
    insert_calls = [s for s, _ in conn.calls if 'INSERT INTO gl_journal' in s]
    assert len(insert_calls) == 0


def test_post_lines_on_conn_inserts_journal_and_lines():
    responses = [
        [{'id': 10}],    # SELECT id FROM gl_account for first line
        [{'id': 11}],    # SELECT id FROM gl_account for second line
        [{'id': 42}],    # INSERT INTO gl_journal RETURNING id
        [],              # INSERT gl_journal_line (line 1)
        [],              # INSERT gl_journal_line (line 2)
    ]
    conn = _MultiConn(responses)
    jid = _post_lines_on_conn(
        conn, '2026-06-28', 'REF-1', 'Test',
        [
            ('1300', 500.0, 0.0, 'Inventory'),
            ('2000', 0.0, 500.0, 'AP'),
        ],
        'System',
    )
    assert jid == 42
    journal_inserts = [s for s, _ in conn.calls if 'INSERT INTO gl_journal' in s
                       and 'gl_journal_line' not in s]
    assert len(journal_inserts) == 1


def test_post_po_receipt_gl_skips_when_no_account_map():
    conn = _Conn(rows=[])  # get_gl_account_map returns {}
    jid = post_po_receipt_gl(conn, 'PO-2026-0001', 1000.0)
    assert jid is None


def test_post_po_receipt_gl_posts_dr_inventory_cr_ap():
    responses = [
        # get_gl_account_map
        [{'category': 'raw_material', 'account_number': '1300'},
         {'category': 'ap_payable', 'account_number': '2000'}],
        # _post_lines_on_conn: acct lookup × 2
        [{'id': 1}], [{'id': 2}],
        # INSERT gl_journal
        [{'id': 99}],
        # INSERT gl_journal_line × 2 (executemany hits execute twice in fake)
    ]
    conn = _MultiConn(responses)
    jid = post_po_receipt_gl(conn, 'PO-2026-0001', 1000.0, created_by='System')
    assert jid == 99
    # First post-map call should look up raw_material account
    acct_lookups = [p for s, p in conn.calls
                    if 'SELECT id FROM gl_account' in s]
    assert '1300' in acct_lookups[0]
    assert '2000' in acct_lookups[1]


def test_post_wo_material_issue_gl_skips_when_no_map():
    conn = _Conn(rows=[])
    jid = post_wo_material_issue_gl(conn, 'WO-2026-0001', 500.0)
    assert jid is None


def test_post_wo_close_gl_skips_when_no_cost_data():
    conn = _Conn(rows=[])  # get_wo_cost → None
    jid = post_wo_close_gl(conn, wo_id=1, wo_number='WO-2026-0001',
                           quantity=5)
    assert jid is None


def test_post_wo_close_gl_posts_fg_dr_wip_cr():
    cost_row = {
        'id': 1, 'wo_id': 3, 'actual_material_cost': 120.0,
        'actual_labor_cost': 50.0, 'actual_overhead_cost': 10.0,
        'total_actual_cost': 180.0, 'std_cost': 150.0,
        'material_variance': 20.0, 'labor_variance': 10.0,
        'total_variance': 30.0, 'created_by': None, 'created_at': None,
    }
    responses = [
        # get_wo_cost
        [cost_row],
        # get_gl_account_map
        [{'category': 'finished_goods', 'account_number': '1320'},
         {'category': 'wip', 'account_number': '1310'},
         {'category': 'material_variance', 'account_number': '5100'},
         {'category': 'labor_variance', 'account_number': '5110'}],
        # account lookups for 4 lines
        [{'id': 10}], [{'id': 11}], [{'id': 12}], [{'id': 13}],
        # INSERT gl_journal
        [{'id': 77}],
    ]
    conn = _MultiConn(responses)
    jid = post_wo_close_gl(conn, wo_id=3, wo_number='WO-2026-0003',
                           quantity=10, created_by='System')
    assert jid == 77
    # Verify FG account (1320) is DR'd
    journal_params = [p for s, p in conn.calls if 'INSERT INTO gl_journal' in s
                      and 'gl_journal_line' not in s]
    assert len(journal_params) == 1
    # WIP clearance line must credit total_actual_cost (material + labour +
    # overhead), not just actual_material_cost — otherwise the entry doesn't
    # balance against the full std_cost debited to Finished Goods.
    line_params = [p for s, p in conn.calls if 'INSERT INTO gl_journal_line' in s]
    wip_line = next(p for p in line_params if p[1] == 11)  # account_id 11 = WIP
    assert wip_line[3] == 180.0  # credit == total_actual_cost, not 120.0


def test_post_wo_close_gl_skips_small_variances():
    # variance < 0.01 should not generate variance lines
    cost_row = {
        'id': 1, 'wo_id': 4, 'actual_material_cost': 100.0,
        'actual_labor_cost': 0.0, 'actual_overhead_cost': 0.0,
        'total_actual_cost': 100.0, 'std_cost': 100.0,
        'material_variance': 0.005,  # below threshold
        'labor_variance': -0.003,    # below threshold
        'total_variance': 0.002, 'created_by': None, 'created_at': None,
    }
    responses = [
        [cost_row],
        [{'category': 'finished_goods', 'account_number': '1320'},
         {'category': 'wip', 'account_number': '1310'},
         {'category': 'material_variance', 'account_number': '5100'},
         {'category': 'labor_variance', 'account_number': '5110'}],
        # Only 2 account lookups (FG + WIP, no variance lines)
        [{'id': 1}], [{'id': 2}],
        [{'id': 55}],
    ]
    conn = _MultiConn(responses)
    jid = post_wo_close_gl(conn, wo_id=4, wo_number='WO-2026-0004', quantity=1)
    assert jid == 55
    # Only 2 account SELECT calls (for FG and WIP only — no variance accounts)
    acct_selects = [p for s, p in conn.calls if 'SELECT id FROM gl_account' in s]
    assert len(acct_selects) == 2


# ── import guard ── ensure _MAX_DEPTH constant is accessible ─────────────

def test_max_depth_constant_is_reasonable():
    from manufacturing.costing_core import _MAX_DEPTH
    assert 10 <= _MAX_DEPTH <= 20
