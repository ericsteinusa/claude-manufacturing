"""Tests for routing_core — workcenter, product routing, and WO operations."""

from manufacturing.routing_core import (
    OP_STATUSES,
    list_workcenters, create_workcenter, update_workcenter,
    get_routing, create_routing_step, update_routing_step,
    delete_routing_step, next_routing_seq,
    populate_wo_operations, get_wo_operations,
    start_wo_operation, complete_wo_operation, skip_wo_operation,
    get_wo_labor_cost, get_workcenter_load,
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

def test_op_statuses_complete():
    assert set(OP_STATUSES) == {'pending', 'in_progress', 'completed', 'skipped'}


# ── workcenter ─────────────────────────────────────────────────────────────

def test_list_workcenters_active_only_adds_where():
    conn = _Conn(rows=[])
    list_workcenters(conn, active_only=True)
    assert "is_active = TRUE" in conn.last_sql


def test_list_workcenters_inactive_omits_where():
    conn = _Conn(rows=[])
    list_workcenters(conn, active_only=False)
    assert "WHERE" not in conn.last_sql


def test_create_workcenter_inserts_and_returns_id():
    conn = _Conn(rows=[{'id': 3}])
    wc_id = create_workcenter(conn, 'Welding', dept='Fabrication',
                              capacity_hours_per_day=8.0, labor_rate=25.0)
    assert wc_id == 3
    assert "INSERT INTO workcenter" in conn.last_sql
    assert conn.last_params == ['Welding', 'Fabrication', 8.0, 25.0, None]


def test_create_workcenter_clamps_negative_rate():
    conn = _Conn(rows=[{'id': 1}])
    create_workcenter(conn, 'Press', labor_rate=-5.0)
    # labor_rate should be clamped to 0.0
    assert conn.last_params[3] == 0.0


def test_update_workcenter_issues_update():
    conn = _Conn()
    update_workcenter(conn, 1, 'Welding', dept='Fab', capacity_hours_per_day=10.0,
                      labor_rate=30.0, is_active=True)
    assert conn.last_sql.strip().upper().startswith("UPDATE WORKCENTER")
    assert conn.last_params[-1] == 1  # WHERE id=%s


# ── product routing ────────────────────────────────────────────────────────

def test_get_routing_queries_by_product_id():
    conn = _Conn(rows=[])
    get_routing(conn, product_id=7)
    assert "WHERE r.product_id = %s" in conn.last_sql
    assert conn.last_params == [7]


def test_get_routing_orders_by_seq():
    conn = _Conn(rows=[])
    get_routing(conn, 7)
    assert "ORDER BY r.operation_seq" in conn.last_sql


def test_create_routing_step_returns_id():
    conn = _Conn(rows=[{'id': 5}])
    rid = create_routing_step(conn, product_id=2, operation_seq=10,
                              operation_name='Cut', workcenter_id=1,
                              std_hours=0.5)
    assert rid == 5
    assert "INSERT INTO routing" in conn.last_sql
    assert conn.last_params == [2, 10, 'Cut', 1, 0.5, None]


def test_create_routing_step_strips_name():
    conn = _Conn(rows=[{'id': 1}])
    create_routing_step(conn, 1, 10, '  Weld  ')
    assert conn.last_params[2] == 'Weld'


def test_create_routing_step_clamps_negative_hours():
    conn = _Conn(rows=[{'id': 1}])
    create_routing_step(conn, 1, 10, 'Grind', std_hours=-2.0)
    assert conn.last_params[4] == 0.0


def test_update_routing_step_issues_update():
    conn = _Conn()
    update_routing_step(conn, routing_id=3, operation_seq=20,
                        operation_name='Drill', workcenter_id=2,
                        std_hours=1.0)
    assert conn.last_sql.strip().upper().startswith("UPDATE ROUTING")
    assert conn.last_params[-1] == 3


def test_delete_routing_step_uses_id():
    conn = _Conn()
    delete_routing_step(conn, routing_id=4)
    assert "DELETE FROM routing WHERE id=%s" in conn.last_sql
    assert conn.last_params == [4]


def test_next_routing_seq_returns_ten_when_empty():
    conn = _Conn(rows=[{'mx': None}])
    assert next_routing_seq(conn, 1) == 10


def test_next_routing_seq_adds_ten_to_max():
    conn = _Conn(rows=[{'mx': 30}])
    assert next_routing_seq(conn, 1) == 40


# ── WO operations ──────────────────────────────────────────────────────────

def test_populate_wo_operations_skips_if_already_exists():
    conn = _Conn(rows=[{'n': 3}])  # existing = 3
    count = populate_wo_operations(conn, wo_id=1, product_id=5)
    assert count == 0
    # Only 1 query executed (the COUNT check)
    assert len(conn.calls) == 1


def test_populate_wo_operations_inserts_routing_steps():
    # First call returns n=0; subsequent calls return routing rows
    routing_rows = [
        {'id': 1, 'operation_seq': 10, 'operation_name': 'Cut',
         'workcenter_id': 1, 'std_hours': 0.5},
        {'id': 2, 'operation_seq': 20, 'operation_name': 'Weld',
         'workcenter_id': 2, 'std_hours': 1.0},
    ]

    call_index = [0]
    class _MultiConn:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params=None):
            self.calls.append((sql, list(params or [])))
            # First call: COUNT → 0; second: routing SELECT; rest: INSERTs
            if call_index[0] == 0:
                call_index[0] += 1
                return _Cursor([{'n': 0}])
            elif call_index[0] == 1:
                call_index[0] += 1
                return _Cursor(routing_rows)
            else:
                call_index[0] += 1
                return _Cursor([])

    conn = _MultiConn()
    count = populate_wo_operations(conn, wo_id=10, product_id=5)
    assert count == 2
    # Should have: 1 COUNT + 1 SELECT routing + 2 INSERTs
    assert len(conn.calls) == 4
    insert_sqls = [s for s, _ in conn.calls if 'INSERT INTO wo_operation' in s]
    assert len(insert_sqls) == 2


def test_get_wo_operations_filters_by_wo_id():
    conn = _Conn(rows=[])
    get_wo_operations(conn, wo_id=7)
    assert "WHERE op.wo_id=%s" in conn.last_sql
    assert conn.last_params == [7]


def test_start_wo_operation_sets_in_progress():
    conn = _Conn()
    start_wo_operation(conn, op_id=3)
    assert "status='in_progress'" in conn.last_sql
    assert conn.last_params == [3]


def test_complete_wo_operation_records_hours():
    conn = _Conn()
    complete_wo_operation(conn, op_id=4, actual_hours=2.5,
                          completed_by='bob@example.com', scrap_qty=0.1)
    assert "status='completed'" in conn.last_sql
    assert conn.last_params[0] == 2.5   # actual_hours
    assert conn.last_params[1] == 0.1   # scrap_qty
    assert conn.last_params[3] == 'bob@example.com'
    assert conn.last_params[-1] == 4    # WHERE id=%s


def test_complete_wo_operation_clamps_negative_hours():
    conn = _Conn()
    complete_wo_operation(conn, op_id=1, actual_hours=-1.0,
                          completed_by='x@example.com')
    assert conn.last_params[0] == 0.0


def test_skip_wo_operation_sets_skipped():
    conn = _Conn()
    skip_wo_operation(conn, op_id=5, notes='not required')
    assert "status='skipped'" in conn.last_sql
    assert conn.last_params == ['not required', 5]


# ── labor cost ─────────────────────────────────────────────────────────────

def test_get_wo_labor_cost_returns_zeros_on_no_rows():
    conn = _Conn(rows=[None])
    result = get_wo_labor_cost(conn, wo_id=1)
    assert result == {'total_std_hours': 0,
                      'total_actual_hours': 0, 'labor_cost': 0.0}


def test_get_wo_labor_cost_returns_computed_values():
    conn = _Conn(rows=[{
        'total_std_hours': 4.0,
        'total_actual_hours': 4.5,
        'labor_cost': 112.50,
    }])
    result = get_wo_labor_cost(conn, wo_id=2)
    assert result['labor_cost'] == 112.50
    assert result['total_actual_hours'] == 4.5
    assert "WHERE op.wo_id=%s AND op.status='completed'" in conn.last_sql


def test_get_workcenter_load_queries_date_range():
    conn = _Conn(rows=[])
    get_workcenter_load(conn, '2026-06-01', '2026-06-30')
    assert conn.last_params == ['2026-06-01', '2026-06-30']
