"""Tests for routing_core — workcenter, product routing, and WO operations."""

from manufacturing.routing_core import (
    OP_STATUSES, OP_STATUS_COLORS,
    list_workcenters, create_workcenter, update_workcenter,
    get_routing, create_routing_step, update_routing_step,
    delete_routing_step, next_routing_seq,
    populate_wo_operations, get_wo_operations,
    start_wo_operation, complete_wo_operation, skip_wo_operation,
    get_wo_labor_cost, get_workcenter_load,
    _derive_operation_window, get_gantt_operations,
    get_planned_workcenter_load, reschedule_operation,
    ensure_routing_tables,
)


# ── fake DB infrastructure ────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)

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


def test_get_wo_operations_includes_scheduled_dates():
    """Regression test: the P3-A Auto-Schedule buttons on wo_detail.html
    display op.scheduled_start/scheduled_end, so this function must select
    them — they were missing here even though the Gantt scheduler (P2-A)
    added the columns, since Gantt reads via get_gantt_operations instead."""
    conn = _Conn(rows=[])
    get_wo_operations(conn, wo_id=7)
    assert "op.scheduled_start" in conn.last_sql
    assert "op.scheduled_end" in conn.last_sql


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


# ── Gantt scheduler (P2-A) ───────────────────────────────────────────────────

def test_op_status_colors_complete():
    assert set(OP_STATUS_COLORS.keys()) == set(OP_STATUSES)


def test_ensure_routing_tables_adds_scheduled_columns():
    conn = _Conn(rows=[])
    ensure_routing_tables(conn)
    sqls = [s for s, _ in conn.calls]
    assert any('scheduled_start' in s for s in sqls)
    assert any('scheduled_end' in s for s in sqls)


# -- _derive_operation_window --

def test_derive_operation_window_uses_scheduled_dates_when_present():
    bar_start, bar_end, is_fallback = _derive_operation_window(
        '2026-07-01T08:00:00', '2026-07-02T17:00:00',
        '2026-06-01', '2026-06-30', 0.0, 1.0,
    )
    assert bar_start == '2026-07-01'
    assert bar_end == '2026-07-02'
    assert is_fallback is False


def test_derive_operation_window_falls_back_when_scheduled_null():
    bar_start, bar_end, is_fallback = _derive_operation_window(
        None, None, '2026-07-01', '2026-07-11', 0.0, 0.5,
    )
    assert is_fallback is True
    assert bar_start is not None


def test_derive_operation_window_splits_proportionally():
    bar_start, bar_end, is_fallback = _derive_operation_window(
        None, None, '2026-07-01', '2026-07-11', 0.0, 0.5,
    )
    assert bar_start == '2026-07-01'
    assert bar_end == '2026-07-06'
    assert is_fallback is True


def test_derive_operation_window_handles_zero_span():
    bar_start, bar_end, is_fallback = _derive_operation_window(
        None, None, '2026-07-01', '2026-07-01', 0.0, 1.0,
    )
    assert bar_start == '2026-07-01'
    assert bar_end == '2026-07-01'
    assert is_fallback is True


def test_derive_operation_window_returns_none_when_wo_dates_missing():
    result = _derive_operation_window(None, None, None, '2026-07-11', 0.0, 0.5)
    assert result == (None, None, True)


def test_derive_operation_window_returns_none_on_unparseable_dates():
    result = _derive_operation_window(None, None, 'not-a-date', '2026-07-11', 0.0, 0.5)
    assert result == (None, None, True)


def test_derive_operation_window_forces_min_one_day_bar():
    bar_start, bar_end, is_fallback = _derive_operation_window(
        None, None, '2026-07-01', '2026-07-11', 0.1, 0.1,
    )
    from datetime import date as _date
    assert _date.fromisoformat(bar_end) > _date.fromisoformat(bar_start)


# -- get_gantt_operations --

def test_get_gantt_operations_excludes_skipped_status():
    conn = _Conn(rows=[])
    get_gantt_operations(conn)
    assert "op.status != 'skipped'" in conn.last_sql


def test_get_gantt_operations_excludes_cancelled_work_orders():
    conn = _Conn(rows=[])
    get_gantt_operations(conn)
    assert "wo.status != 'cancelled'" in conn.last_sql


def test_get_gantt_operations_filters_by_workcenter_id_after_fraction_calc():
    """workcenter_id must not be a SQL-level filter: it's applied in Python
    after fallback fractions are computed from the WO's full op set, or a
    filtered fetch would skew every other operation's fraction (see
    _derive_operation_window docstring in routing_core.py)."""
    conn = _Conn(rows=[])
    get_gantt_operations(conn, workcenter_id=4)
    assert "op.workcenter_id = %s" not in conn.last_sql
    assert 4 not in conn.last_params


def test_get_gantt_operations_workcenter_filter_does_not_skew_other_ops_fractions():
    rows = [
        {'id': 1, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-11', 'product_name': 'Widget',
         'operation_seq': 10, 'operation_name': 'Cut', 'workcenter_id': 1,
         'workcenter_name': 'Saw', 'std_hours': 2.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
        {'id': 2, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-11', 'product_name': 'Widget',
         'operation_seq': 20, 'operation_name': 'Weld', 'workcenter_id': 2,
         'workcenter_name': 'Weld Cell', 'std_hours': 6.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
        {'id': 3, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-11', 'product_name': 'Widget',
         'operation_seq': 30, 'operation_name': 'Paint', 'workcenter_id': 1,
         'workcenter_name': 'Saw', 'std_hours': 2.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
    ]
    conn_unfiltered = _Conn(rows=rows)
    unfiltered = get_gantt_operations(conn_unfiltered)
    op3_unfiltered = next(o for o in unfiltered if o['id'] == 3)

    conn_filtered = _Conn(rows=rows)
    filtered = get_gantt_operations(conn_filtered, workcenter_id=1)
    op3_filtered = next(o for o in filtered if o['id'] == 3)

    assert {o['id'] for o in filtered} == {1, 3}
    assert op3_filtered['bar_start'] == op3_unfiltered['bar_start']
    assert op3_filtered['bar_end'] == op3_unfiltered['bar_end']


def test_get_gantt_operations_applies_date_filter_only_when_both_bounds_given():
    conn = _Conn(rows=[])
    get_gantt_operations(conn, date_from='2026-07-01')
    assert 'scheduled_start::date' not in conn.last_sql

    conn2 = _Conn(rows=[])
    get_gantt_operations(conn2, date_from='2026-07-01', date_to='2026-07-14')
    assert 'scheduled_start::date' in conn2.last_sql
    assert conn2.last_params == ['2026-07-14', '2026-07-01', '2026-07-01', '2026-07-14']


def test_get_gantt_operations_computes_fallback_and_filters_by_bar_window():
    rows = [
        {'id': 1, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-11', 'product_name': 'Widget',
         'operation_seq': 10, 'operation_name': 'Cut', 'workcenter_id': 1,
         'workcenter_name': 'Saw', 'std_hours': 5.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
        {'id': 2, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-11', 'product_name': 'Widget',
         'operation_seq': 20, 'operation_name': 'Weld', 'workcenter_id': 2,
         'workcenter_name': 'Weld Cell', 'std_hours': 5.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
    ]
    conn = _Conn(rows=rows)
    result = get_gantt_operations(conn, date_from='2026-07-01', date_to='2026-07-11')
    assert len(result) == 2
    assert result[0]['bar_start'] == '2026-07-01'
    assert result[1]['bar_end'] == '2026-07-11'

    # Op entirely outside the visible window is dropped
    conn2 = _Conn(rows=rows)
    result2 = get_gantt_operations(conn2, date_from='2026-08-01', date_to='2026-08-14')
    assert result2 == []


def test_get_gantt_operations_sorts_by_workcenter_then_wo_then_seq():
    rows = [
        {'id': 1, 'wo_id': 10, 'wo_number': 'WO-2', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-02', 'product_name': 'A',
         'operation_seq': 10, 'operation_name': 'Op', 'workcenter_id': 2,
         'workcenter_name': 'B-Cell', 'std_hours': 1.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
        {'id': 2, 'wo_id': 11, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-02', 'product_name': 'A',
         'operation_seq': 10, 'operation_name': 'Op', 'workcenter_id': 1,
         'workcenter_name': 'A-Cell', 'std_hours': 1.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
    ]
    conn = _Conn(rows=rows)
    result = get_gantt_operations(conn)
    assert [r['workcenter_name'] for r in result] == ['A-Cell', 'B-Cell']


# -- get_planned_workcenter_load --

def test_get_planned_workcenter_load_sums_pending_and_in_progress_only():
    ops_rows = [
        {'id': 1, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-02', 'product_name': 'A',
         'operation_seq': 10, 'operation_name': 'Op', 'workcenter_id': 1,
         'workcenter_name': 'Cell 1', 'std_hours': 4.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
        {'id': 2, 'wo_id': 11, 'wo_number': 'WO-2', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-02', 'product_name': 'A',
         'operation_seq': 10, 'operation_name': 'Op', 'workcenter_id': 1,
         'workcenter_name': 'Cell 1', 'std_hours': 100.0, 'status': 'completed',
         'scheduled_start': None, 'scheduled_end': None},
    ]
    wc_rows = [{'id': 1, 'name': 'Cell 1', 'capacity_hours_per_day': 8.0}]

    calls = {'n': 0}

    class _LoadConn:
        def execute(self, sql, params=None):
            calls['n'] += 1
            if 'wo_operation' in sql:
                return _Cursor(ops_rows)
            return _Cursor(wc_rows)

    conn = _LoadConn()
    result = get_planned_workcenter_load(conn, '2026-07-01', '2026-07-02')
    assert len(result) == 1
    assert result[0]['planned_hours'] == 4.0  # completed op's 100h excluded


def test_get_planned_workcenter_load_flags_over_capacity():
    ops_rows = [
        {'id': 1, 'wo_id': 10, 'wo_number': 'WO-1', 'wo_start_date': '2026-07-01',
         'wo_due_date': '2026-07-01', 'product_name': 'A',
         'operation_seq': 10, 'operation_name': 'Op', 'workcenter_id': 1,
         'workcenter_name': 'Cell 1', 'std_hours': 50.0, 'status': 'pending',
         'scheduled_start': None, 'scheduled_end': None},
    ]
    wc_rows = [{'id': 1, 'name': 'Cell 1', 'capacity_hours_per_day': 8.0}]

    class _LoadConn:
        def execute(self, sql, params=None):
            if 'wo_operation' in sql:
                return _Cursor(ops_rows)
            return _Cursor(wc_rows)

    conn = _LoadConn()
    result = get_planned_workcenter_load(conn, '2026-07-01', '2026-07-01')
    assert result[0]['over_capacity'] is True
    assert result[0]['pct'] > 100.0


def test_get_planned_workcenter_load_zero_capacity_does_not_divide_by_zero():
    wc_rows = [{'id': 1, 'name': 'Cell 1', 'capacity_hours_per_day': 0.0}]

    class _LoadConn:
        def execute(self, sql, params=None):
            if 'wo_operation' in sql:
                return _Cursor([])
            return _Cursor(wc_rows)

    conn = _LoadConn()
    result = get_planned_workcenter_load(conn, '2026-07-01', '2026-07-01')
    assert result[0]['pct'] == 0.0
    assert result[0]['over_capacity'] is False


def test_get_planned_workcenter_load_reuses_prefetched_ops_without_requerying():
    """Passing ops= must skip the wo_operation query entirely — the caller
    already ran it, and re-running it on every page load was wasted work."""
    wc_rows = [{'id': 1, 'name': 'Cell 1', 'capacity_hours_per_day': 8.0}]
    prefetched_ops = [
        {'workcenter_id': 1, 'std_hours': 4.0, 'status': 'pending'},
    ]

    class _LoadConn:
        def execute(self, sql, params=None):
            assert 'wo_operation' not in sql, "should not re-query wo_operation"
            return _Cursor(wc_rows)

    conn = _LoadConn()
    result = get_planned_workcenter_load(conn, '2026-07-01', '2026-07-01', ops=prefetched_ops)
    assert result[0]['planned_hours'] == 4.0


# -- reschedule_operation --

def test_reschedule_operation_updates_and_returns_true():
    conn = _Conn(rows=[{'id': 1}])
    updated = reschedule_operation(conn, 1, '2026-07-01T08:00:00', '2026-07-01T17:00:00')
    assert updated is True
    assert "UPDATE wo_operation AS op SET scheduled_start=%s, scheduled_end=%s" in conn.last_sql
    assert conn.last_params == ['2026-07-01T08:00:00', '2026-07-01T17:00:00', 1]


def test_reschedule_operation_guards_against_completed_skipped_and_cancelled_wo():
    conn = _Conn(rows=[{'id': 1}])
    reschedule_operation(conn, 1, '2026-07-01T08:00:00', '2026-07-01T17:00:00')
    assert "op.status NOT IN ('completed', 'skipped')" in conn.last_sql
    assert "wo.status != 'cancelled'" in conn.last_sql


def test_reschedule_operation_returns_false_when_not_found():
    conn = _Conn(rows=[])
    updated = reschedule_operation(conn, 999, '2026-07-01T08:00:00', '2026-07-01T17:00:00')
    assert updated is False


def test_reschedule_operation_rejects_end_before_start():
    conn = _Conn(rows=[])
    try:
        reschedule_operation(conn, 1, '2026-07-01T17:00:00', '2026-07-01T08:00:00')
        assert False, 'expected ValueError'
    except ValueError:
        pass
    assert conn.calls == []
