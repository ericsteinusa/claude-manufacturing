"""Tests for Phase 6 — Quality SPC and Maintenance Asset Hierarchy."""

import pytest

from manufacturing.quality_core import (
    SPC_SUBGROUP_SIZES,
    _A2, _D3, _D4,
    create_control_limit,
    list_control_limits,
    get_control_limit,
    update_control_limit,
    log_measurement,
    get_measurements,
    compute_xbar_r_chart,
    compute_cpk,
    get_spc_alerts,
)
from manufacturing.maintenance_core import (
    set_equipment_parent,
    get_equipment_children,
    get_equipment_roots,
    get_equipment_tree,
    link_part_to_equipment,
    get_parts_for_equipment,
    get_mtbf,
    get_equipment_reliability_report,
    get_pm_alerts,
)


# ── Fake DB ────────────────────────────────────────────────────────────────

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

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


# ═══════════════════════════════════════════════════════════════════════════
# 6A — SPC constants and table helpers
# ═══════════════════════════════════════════════════════════════════════════

def test_spc_subgroup_sizes_range():
    assert min(SPC_SUBGROUP_SIZES) == 2
    assert max(SPC_SUBGROUP_SIZES) == 10


def test_chart_constants_defined_for_all_sizes():
    for n in SPC_SUBGROUP_SIZES:
        assert n in _A2
        assert n in _D3
        assert n in _D4


def test_a2_decreases_with_subgroup_size():
    sizes = sorted(SPC_SUBGROUP_SIZES)
    a2_vals = [_A2[n] for n in sizes]
    assert a2_vals == sorted(a2_vals, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════
# 6A — create_control_limit / list / get / update
# ═══════════════════════════════════════════════════════════════════════════

def test_create_control_limit_inserts():
    conn = _Conn(rows=[{'id': 1}])
    cid = create_control_limit(conn, product_id=5, characteristic='diameter',
                               ucl=10.5, lcl=9.5, target=10.0, subgroup_size=5)
    assert cid == 1
    assert 'INSERT INTO spc_control_limit' in conn.last_sql


def test_create_control_limit_rejects_ucl_lte_lcl():
    conn = _Conn()
    with pytest.raises(ValueError, match='ucl must be greater than lcl'):
        create_control_limit(conn, 1, 'dia', ucl=9.0, lcl=10.0)


def test_create_control_limit_rejects_bad_subgroup_size():
    conn = _Conn()
    with pytest.raises(ValueError, match='subgroup_size'):
        create_control_limit(conn, 1, 'dia', ucl=11.0, lcl=9.0, subgroup_size=1)


def test_create_control_limit_rejects_empty_characteristic():
    conn = _Conn()
    with pytest.raises(ValueError, match='characteristic'):
        create_control_limit(conn, 1, '  ', ucl=11.0, lcl=9.0)


def test_list_control_limits_active_only():
    conn = _Conn(rows=[])
    list_control_limits(conn, active_only=True)
    assert 'is_active = TRUE' in conn.last_sql


def test_list_control_limits_filters_product():
    conn = _Conn(rows=[])
    list_control_limits(conn, product_id=3)
    assert 'product_id = %s' in conn.last_sql
    assert 3 in conn.last_params


def test_get_control_limit_returns_dict():
    conn = _Conn(rows=[{'id': 1, 'ucl': 10.5, 'lcl': 9.5,
                        'characteristic': 'dia', 'product_id': 5}])
    result = get_control_limit(conn, 5, 'dia')
    assert result is not None
    assert result['ucl'] == 10.5


def test_get_control_limit_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_control_limit(conn, 5, 'nonexistent') is None


def test_update_control_limit_rejects_invalid_range():
    conn = _Conn()
    with pytest.raises(ValueError, match='ucl must be greater than lcl'):
        update_control_limit(conn, 1, ucl=5.0, lcl=6.0)


def test_update_control_limit_issues_update():
    conn = _Conn()
    update_control_limit(conn, 1, ucl=11.0, lcl=9.0, target=10.0, subgroup_size=5)
    assert 'UPDATE spc_control_limit' in conn.last_sql
    assert conn.last_params[-1] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 6A — log_measurement
# ═══════════════════════════════════════════════════════════════════════════

def _cl_row(ucl=10.5, lcl=9.5):
    return {'id': 1, 'ucl': ucl, 'lcl': lcl, 'is_active': True,
            'characteristic': 'dia', 'product_id': 5}


def test_log_measurement_within_limits():
    # get_control_limit → returns limit row; INSERT measurement → id=10
    conn = _MultiConn([[_cl_row()], [{'id': 10}]])
    result = log_measurement(conn, 5, 'dia', measured_value=10.0,
                              measured_by='tech1')
    assert result['in_control'] is True
    assert result['action'] == 'OK'
    assert result['id'] == 10


def test_log_measurement_above_ucl():
    conn = _MultiConn([[_cl_row(ucl=10.5, lcl=9.5)], [{'id': 11}]])
    result = log_measurement(conn, 5, 'dia', measured_value=11.0)
    assert result['in_control'] is False
    assert result['action'] == 'ABOVE_UCL'


def test_log_measurement_below_lcl():
    conn = _MultiConn([[_cl_row(ucl=10.5, lcl=9.5)], [{'id': 12}]])
    result = log_measurement(conn, 5, 'dia', measured_value=9.0)
    assert result['in_control'] is False
    assert result['action'] == 'BELOW_LCL'


def test_log_measurement_no_limits():
    # get_control_limit → no row → no_limits
    conn = _MultiConn([[], [{'id': 13}]])
    result = log_measurement(conn, 5, 'dia', measured_value=10.0)
    assert result['in_control'] is True
    assert result['action'] == 'NO_LIMITS'
    assert result['ucl'] is None


def test_log_measurement_at_ucl_boundary():
    conn = _MultiConn([[_cl_row(ucl=10.5, lcl=9.5)], [{'id': 14}]])
    result = log_measurement(conn, 5, 'dia', measured_value=10.5)
    assert result['in_control'] is True


def test_log_measurement_at_lcl_boundary():
    conn = _MultiConn([[_cl_row(ucl=10.5, lcl=9.5)], [{'id': 15}]])
    result = log_measurement(conn, 5, 'dia', measured_value=9.5)
    assert result['in_control'] is True


# ═══════════════════════════════════════════════════════════════════════════
# 6A — get_measurements
# ═══════════════════════════════════════════════════════════════════════════

def test_get_measurements_queries_by_product_and_char():
    conn = _Conn(rows=[])
    get_measurements(conn, 5, 'diameter', limit=50)
    assert 'm.characteristic = %s' in conn.last_sql
    assert 5 in conn.last_params
    assert 'diameter' in conn.last_params


# ═══════════════════════════════════════════════════════════════════════════
# 6A — compute_xbar_r_chart
# ═══════════════════════════════════════════════════════════════════════════

def _meas_rows(values):
    return [{'measured_value': v, 'measured_by': 'tech',
             'measured_at': '2026-06-01', 'in_control': True,
             'wo_id': None, 'lot_id': None, 'notes': '', 'id': i + 1}
            for i, v in enumerate(values)]


def test_compute_xbar_r_chart_rejects_bad_subgroup_size():
    conn = _Conn(rows=[])
    with pytest.raises(ValueError, match='subgroup_size'):
        compute_xbar_r_chart(conn, 1, 'dia', subgroup_size=1)


def test_compute_xbar_r_chart_returns_empty_when_insufficient_data():
    # Only 3 measurements for subgroup_size=5 → not enough
    cl_row = [_cl_row()]
    meas = _meas_rows([10.0, 10.1, 9.9])
    conn = _MultiConn([meas, cl_row])
    result = compute_xbar_r_chart(conn, 5, 'dia', subgroup_size=5)
    assert result['n_subgroups'] == 0
    assert result['subgroups'] == []


def test_compute_xbar_r_chart_computes_two_subgroups():
    values = [10.0, 10.2, 9.8, 10.1, 9.9,   # subgroup 1: mean=10.0, range=0.4
              10.3, 10.0, 9.7, 10.2, 9.8]    # subgroup 2: mean=10.0, range=0.6
    meas = _meas_rows(values)
    cl_row = [_cl_row(ucl=11.0, lcl=9.0)]
    conn = _MultiConn([meas, cl_row])
    result = compute_xbar_r_chart(conn, 5, 'dia', subgroup_size=5)
    assert result['n_subgroups'] == 2
    assert len(result['subgroups']) == 2
    assert result['grand_mean'] is not None
    assert result['grand_range'] is not None
    assert result['ucl_xbar'] > result['grand_mean']
    assert result['lcl_xbar'] < result['grand_mean']
    # R chart: UCL_R = D4 × R̄ = 2.114 × 0.5 ≈ 1.057
    assert result['ucl_r'] > 0


def test_compute_xbar_r_chart_uses_a2_constant():
    # Verify UCL_xbar = grand_mean + A2[5] * grand_range
    values = [10.0] * 10   # all same → range=0, grand_mean=10
    meas = _meas_rows(values)
    cl_row = [_cl_row()]
    conn = _MultiConn([meas, cl_row])
    result = compute_xbar_r_chart(conn, 5, 'dia', subgroup_size=5)
    # All ranges are 0 → grand_range=0 → UCL_xbar = LCL_xbar = grand_mean
    assert result['ucl_xbar'] == result['lcl_xbar'] == result['grand_mean']


def test_compute_xbar_r_chart_marks_out_of_control_subgroup():
    # Introduce an outlier subgroup
    values = (
        [10.0, 10.0, 10.0, 10.0, 10.0] * 4  # 4 normal subgroups
        + [20.0, 20.0, 20.0, 20.0, 20.0]     # 1 extreme outlier subgroup
    )
    meas = _meas_rows(values)
    cl_row = [_cl_row(ucl=11.0, lcl=9.0)]
    conn = _MultiConn([meas, cl_row])
    result = compute_xbar_r_chart(conn, 5, 'dia', subgroup_size=5)
    # The last subgroup mean of 20.0 should be flagged out of control
    last_sg = result['subgroups'][-1]
    assert last_sg['xbar_oc'] is True


def test_compute_xbar_r_chart_spec_limits_included():
    meas = _meas_rows([10.0] * 10)
    cl_row = [_cl_row(ucl=11.0, lcl=9.0)]
    conn = _MultiConn([meas, cl_row])
    result = compute_xbar_r_chart(conn, 5, 'dia', subgroup_size=5)
    assert result['spec_ucl'] == 11.0
    assert result['spec_lcl'] == 9.0


# ═══════════════════════════════════════════════════════════════════════════
# 6A — compute_cpk
# ═══════════════════════════════════════════════════════════════════════════

def test_compute_cpk_returns_error_when_no_limits():
    conn = _MultiConn([[], []])   # get_control_limit → []
    result = compute_cpk(conn, 5, 'dia')
    assert result['cpk'] is None
    assert 'error' in result


def test_compute_cpk_returns_error_when_insufficient_measurements():
    cl = [_cl_row(ucl=11.0, lcl=9.0)]
    meas = _meas_rows([10.0])   # only 1 measurement
    conn = _MultiConn([cl, meas])
    result = compute_cpk(conn, 5, 'dia')
    assert result['cpk'] is None
    assert 'Need at least 2' in result['error']


def test_compute_cpk_returns_error_when_zero_variance():
    cl = [_cl_row(ucl=11.0, lcl=9.0)]
    meas = _meas_rows([10.0, 10.0, 10.0])   # all identical
    conn = _MultiConn([cl, meas])
    result = compute_cpk(conn, 5, 'dia')
    assert result['cpk'] is None
    assert 'Zero variance' in result['error']


def test_compute_cpk_centered_process():
    # μ=10, σ=0.333, UCL=11, LCL=9
    # Cpu = (11-10)/(3×0.333) ≈ 1.0, Cpl = (10-9)/(3×0.333) ≈ 1.0 → Cpk ≈ 1.0
    import statistics as _stat
    vals = [9.7, 9.9, 10.0, 10.1, 10.3]
    cl = [_cl_row(ucl=11.0, lcl=9.0)]
    meas = _meas_rows(vals)
    conn = _MultiConn([cl, meas])
    result = compute_cpk(conn, 5, 'dia')
    assert result['cpk'] is not None
    assert result['cpk'] > 0
    assert result['n'] == 5
    assert 'cpu' in result and 'cpl' in result
    assert result['cpk'] == min(result['cpu'], result['cpl'])


def test_compute_cpk_off_center_process():
    # μ close to UCL → Cpk limited by Cpu
    vals = [10.8, 10.9, 10.7, 10.8, 10.9]
    cl = [_cl_row(ucl=11.0, lcl=9.0)]
    meas = _meas_rows(vals)
    conn = _MultiConn([cl, meas])
    result = compute_cpk(conn, 5, 'dia')
    assert result['cpk'] == result['cpu']   # Cpu is the limiting term
    assert result['cpl'] > result['cpu']


# ═══════════════════════════════════════════════════════════════════════════
# 6A — get_spc_alerts
# ═══════════════════════════════════════════════════════════════════════════

def test_get_spc_alerts_queries_out_of_control():
    conn = _Conn(rows=[])
    get_spc_alerts(conn, limit=25)
    assert 'in_control = FALSE' in conn.last_sql
    assert 25 in conn.last_params


def test_get_spc_alerts_returns_list_of_dicts():
    row = {'id': 1, 'product_id': 5, 'characteristic': 'dia',
           'measured_value': 12.0, 'measured_by': 'tech',
           'measured_at': '2026-06-28', 'in_control': False,
           'wo_id': None, 'lot_id': None, 'product_name': 'Widget',
           'ucl': 11.0, 'lcl': 9.0}
    conn = _Conn(rows=[row])
    alerts = get_spc_alerts(conn)
    assert len(alerts) == 1
    assert alerts[0]['characteristic'] == 'dia'


# ═══════════════════════════════════════════════════════════════════════════
# 6B — Asset hierarchy
# ═══════════════════════════════════════════════════════════════════════════

def test_set_equipment_parent_updates():
    conn = _Conn()
    set_equipment_parent(conn, eq_id=5, parent_id=1)
    assert 'UPDATE maint_equipment' in conn.last_sql
    assert conn.last_params == [1, 5]


def test_set_equipment_parent_allows_none():
    conn = _Conn()
    set_equipment_parent(conn, eq_id=5, parent_id=None)
    assert conn.last_params == [None, 5]


def test_set_equipment_parent_rejects_self_reference():
    conn = _Conn()
    with pytest.raises(ValueError, match="own parent"):
        set_equipment_parent(conn, eq_id=3, parent_id=3)


def test_get_equipment_children_queries_by_parent():
    conn = _Conn(rows=[])
    get_equipment_children(conn, parent_id=2)
    assert 'parent_id = %s' in conn.last_sql
    assert conn.last_params == [2]


def test_get_equipment_roots_filters_null_parent():
    conn = _Conn(rows=[])
    get_equipment_roots(conn)
    assert 'parent_id IS NULL' in conn.last_sql


def test_get_equipment_tree_builds_hierarchy():
    # 3 equipment: root (id=1), child1 (id=2, parent=1), child2 (id=3, parent=1)
    rows = [
        {'id': 1, 'name': 'Plant', 'parent_id': None, 'status': 'Operational'},
        {'id': 2, 'name': 'Line A', 'parent_id': 1, 'status': 'Operational'},
        {'id': 3, 'name': 'Line B', 'parent_id': 1, 'status': 'Operational'},
    ]
    conn = _Conn(rows=rows)
    tree = get_equipment_tree(conn)
    assert len(tree) == 1
    root = tree[0]
    assert root['name'] == 'Plant'
    assert len(root['children']) == 2
    child_names = {c['name'] for c in root['children']}
    assert child_names == {'Line A', 'Line B'}


def test_get_equipment_tree_empty():
    conn = _Conn(rows=[])
    assert get_equipment_tree(conn) == []


def test_get_equipment_tree_leaf_has_empty_children():
    rows = [{'id': 1, 'name': 'Machine', 'parent_id': None, 'status': 'Operational'}]
    conn = _Conn(rows=rows)
    tree = get_equipment_tree(conn)
    assert tree[0]['children'] == []


def test_link_part_to_equipment_updates():
    conn = _Conn()
    link_part_to_equipment(conn, part_id=10, equipment_id=5)
    assert 'UPDATE maint_part' in conn.last_sql
    assert conn.last_params == [5, 10]


def test_get_parts_for_equipment_queries_by_equipment():
    conn = _Conn(rows=[])
    get_parts_for_equipment(conn, equipment_id=7)
    assert 'equipment_id = %s' in conn.last_sql
    assert conn.last_params == [7]


# ═══════════════════════════════════════════════════════════════════════════
# 6B — MTBF / MTTR
# ═══════════════════════════════════════════════════════════════════════════

def test_get_mtbf_no_failures():
    conn = _Conn(rows=[{'failure_count': 0, 'total_hours': 0.0}])
    result = get_mtbf(conn, 'Lathe A', months=12)
    assert result['failure_count'] == 0
    assert result['mtbf_hours'] is None
    assert result['mttr_hours'] is None


def test_get_mtbf_computes_correctly():
    # period = 12 months × 30 days × 24 h = 8640 h
    # 3 failures, 60 h downtime
    conn = _Conn(rows=[{'failure_count': 3, 'total_hours': 60.0}])
    result = get_mtbf(conn, 'Press #1')
    assert result['failure_count'] == 3
    assert result['total_downtime_hours'] == 60.0
    # MTBF = (8640 - 60) / 3 = 2860.0
    assert result['mtbf_hours'] == 2860.0
    # MTTR = 60 / 3 = 20.0
    assert result['mttr_hours'] == 20.0
    # Availability = (8640 - 60) / 8640 × 100 ≈ 99.3%
    assert result['availability_pct'] == round((8640 - 60) / 8640 * 100, 1)


def test_get_mtbf_queries_breakdown_category():
    conn = _Conn(rows=[{'failure_count': 0, 'total_hours': 0.0}])
    get_mtbf(conn, 'Conveyor', months=6)
    assert "category = 'Breakdown'" in conn.last_sql
    assert 'Conveyor' in conn.last_params


def test_get_equipment_reliability_report_returns_list():
    conn = _Conn(rows=[
        {'equipment': 'Lathe A', 'failure_count': 2, 'total_hours': 40.0},
        {'equipment': 'Press #1', 'failure_count': 0, 'total_hours': 0.0},
    ])
    result = get_equipment_reliability_report(conn)
    assert len(result) == 2
    lathe = result[0]
    assert lathe['equipment'] == 'Lathe A'
    assert lathe['failure_count'] == 2
    assert lathe['mtbf_hours'] is not None
    assert lathe['mttr_hours'] == 20.0

    press = result[1]
    assert press['mtbf_hours'] is None   # no failures


# ═══════════════════════════════════════════════════════════════════════════
# 6B — PM Alerts
# ═══════════════════════════════════════════════════════════════════════════

def test_get_pm_alerts_returns_list():
    import datetime
    yesterday = (datetime.date.today()
                 - datetime.timedelta(days=1)).isoformat()
    tomorrow = (datetime.date.today()
                + datetime.timedelta(days=1)).isoformat()
    conn = _Conn(rows=[
        {'id': 1, 'task': 'Oil change', 'equipment': 'Lathe',
         'next_due': yesterday, 'status': 'Due', 'frequency': 'Monthly'},
        {'id': 2, 'task': 'Filter replace', 'equipment': 'Press',
         'next_due': tomorrow, 'status': 'Scheduled', 'frequency': 'Quarterly'},
    ])
    alerts = get_pm_alerts(conn, days_ahead=14)
    assert len(alerts) == 2
    # Yesterday's task is overdue
    overdue = next(a for a in alerts if a['id'] == 1)
    assert overdue['urgency'] == 'overdue'


def test_get_pm_alerts_queries_correct_cutoff():
    import datetime
    conn = _Conn(rows=[])
    get_pm_alerts(conn, days_ahead=7)
    assert "next_due != ''" in conn.last_sql
    assert "NOT IN ('Completed', 'Skipped')" in conn.last_sql


def test_get_pm_alerts_urgency_due_soon():
    import datetime
    in_2_days = (datetime.date.today()
                 + datetime.timedelta(days=2)).isoformat()
    conn = _Conn(rows=[{
        'id': 3, 'task': 'Safety check', 'equipment': 'Crane',
        'next_due': in_2_days, 'status': 'Scheduled', 'frequency': 'Weekly',
    }])
    alerts = get_pm_alerts(conn)
    assert alerts[0]['urgency'] == 'due_soon'


def test_get_pm_alerts_urgency_due():
    import datetime
    in_10_days = (datetime.date.today()
                  + datetime.timedelta(days=10)).isoformat()
    conn = _Conn(rows=[{
        'id': 4, 'task': 'Inspection', 'equipment': 'Boiler',
        'next_due': in_10_days, 'status': 'Scheduled', 'frequency': 'Annual',
    }])
    alerts = get_pm_alerts(conn)
    assert alerts[0]['urgency'] == 'due'
