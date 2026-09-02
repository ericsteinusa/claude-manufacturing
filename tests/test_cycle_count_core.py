"""Tests for cycle_count_core — generate sheet, count entry, variance
approval, and auto-post workflow."""

from manufacturing.cycle_count_core import (
    GROUP_BY_OPTIONS, ABC_CLASSES,
    ensure_cycle_count_tables,
    _next_count_number, compute_abc_classes, list_group_values,
    generate_sheet, enter_counts, decide_cycle_count, post_cycle_count,
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
    """Fake connection whose responses are driven by a queue of row-sets."""

    def __init__(self, responses):
        self._queue = list(responses)
        self._idx = 0
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        rows = self._queue[self._idx] if self._idx < len(self._queue) else []
        self._idx += 1
        return _Cursor(rows or [])


# ── constants ────────────────────────────────────────────────────────────

def test_group_by_options():
    assert set(GROUP_BY_OPTIONS) == {'bin', 'item_type', 'abc'}


def test_abc_classes():
    assert set(ABC_CLASSES) == {'A', 'B', 'C'}


# ── ensure_cycle_count_tables ────────────────────────────────────────────

def test_ensure_cycle_count_tables_self_heals_item_type_and_uom():
    # A genuinely fresh product table (no seed_sample_products.py run) has
    # neither column — generate_sheet() filters on item_type and
    # get_cycle_count_lines() selects p.uom, so both must self-heal here.
    conn = _MultiConn([])
    ensure_cycle_count_tables(conn)
    sqls = [sql for sql, _ in conn.calls]
    assert any(
        'ALTER TABLE product ADD COLUMN IF NOT EXISTS' in s and 'item_type' in s
        for s in sqls
    )
    assert any(
        'ALTER TABLE product ADD COLUMN IF NOT EXISTS' in s and 'uom' in s
        for s in sqls
    )


# ── numbering ────────────────────────────────────────────────────────────

def test_next_count_number_starts_at_0001():
    conn = _MultiConn([[]])
    assert _next_count_number(conn).endswith('-0001')


def test_next_count_number_increments_from_max():
    import datetime
    yr = datetime.date.today().year
    conn = _MultiConn([[{'count_number': f'CC-{yr}-0003'},
                         {'count_number': f'CC-{yr}-0001'}]])
    assert _next_count_number(conn) == f'CC-{yr}-0004'


# ── ABC classification ───────────────────────────────────────────────────

def test_compute_abc_classes_buckets_by_percentile():
    conn = _MultiConn([[
        {'id': 1, 'value': 100},
        {'id': 2, 'value': 80},
        {'id': 3, 'value': 60},
        {'id': 4, 'value': 40},
        {'id': 5, 'value': 20},
    ]])
    classes = compute_abc_classes(conn)
    assert classes == {1: 'A', 2: 'B', 3: 'C', 4: 'C', 5: 'C'}


def test_compute_abc_classes_empty_products():
    conn = _MultiConn([[]])
    assert compute_abc_classes(conn) == {}


# ── list_group_values ────────────────────────────────────────────────────

def test_list_group_values_item_type():
    conn = _MultiConn([[]])
    assert list_group_values(conn, 'item_type') == ['make', 'buy']


def test_list_group_values_abc():
    conn = _MultiConn([[]])
    assert list_group_values(conn, 'abc') == ['A', 'B', 'C']


def test_list_group_values_bin():
    conn = _MultiConn([[{'bin': 'A1'}, {'bin': 'B2'}]])
    assert list_group_values(conn, 'bin') == ['A1', 'B2']


def test_list_group_values_invalid_raises():
    import pytest
    conn = _MultiConn([[]])
    with pytest.raises(ValueError):
        list_group_values(conn, 'nope')


# ── generate_sheet ───────────────────────────────────────────────────────

def test_generate_sheet_by_bin_snapshots_qty():
    conn = _MultiConn([
        [{'id': 1, 'amount': 10.0}, {'id': 2, 'amount': 5.0}],  # matching products
        [],                                                      # existing count numbers
        [{'id': 42}],                                            # header insert
        [],                                                      # line insert 1
        [],                                                      # line insert 2
    ])
    count_id = generate_sheet(conn, 'bin', 'A1', 'eric')
    assert count_id == 42
    # header insert params: (count_number, group_by, group_value, created_by)
    header_call = conn.calls[2]
    assert header_call[1][1:] == ['bin', 'A1', 'eric']


def test_generate_sheet_by_abc_filters_to_matching_class():
    conn = _MultiConn([
        [  # compute_abc_classes: 5 products, id=1 is the sole 'A'
            {'id': 1, 'value': 100}, {'id': 2, 'value': 80}, {'id': 3, 'value': 60},
            {'id': 4, 'value': 40}, {'id': 5, 'value': 20},
        ],
        [{'id': 1, 'amount': 7.0}],  # products matching class 'A' (id=1 only)
        [],                          # existing count numbers
        [{'id': 99}],                # header insert
        [],                          # line insert
    ])
    count_id = generate_sheet(conn, 'abc', 'A', 'eric')
    assert count_id == 99
    # the WHERE id = ANY(%s) query should have been called with only id 1
    products_query_params = conn.calls[1][1]
    assert products_query_params == [[1]]


def test_generate_sheet_by_abc_no_matches_skips_product_query():
    conn = _MultiConn([
        [{'id': 1, 'value': 100}],  # single product, always buckets to 'C'
        [],                          # existing count numbers
        [{'id': 7}],                 # header insert
    ])
    count_id = generate_sheet(conn, 'abc', 'A', 'eric')
    assert count_id == 7


def test_generate_sheet_invalid_group_by_raises():
    import pytest
    conn = _MultiConn([[]])
    with pytest.raises(ValueError):
        generate_sheet(conn, 'nope', 'x', 'eric')


# ── enter_counts ─────────────────────────────────────────────────────────

def test_enter_counts_no_variance_auto_posts():
    conn = _MultiConn([
        [{'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': None,
          'variance_qty': None, 'posted': False, 'product_name': 'Widget',
          'bin': 'A1', 'uom': 'ea'}],           # get_cycle_count_lines
        [],                                      # update line (counted=5, variance=0)
        [],                                      # update cycle_count status=submitted
        # -- post_cycle_count (auto) --
        [{'id': 3, 'count_number': 'CC-2026-0001'}],  # get_cycle_count
        [{'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': 5.0,
          'variance_qty': 0.0, 'posted': False, 'product_name': 'Widget',
          'bin': 'A1', 'uom': 'ea'}],           # get_cycle_count_lines (no variance -> skipped)
        [],                                      # update cycle_count status=posted
    ])
    status = enter_counts(conn, 3, {1: 5.0}, 'eric')
    assert status == 'posted'


def test_enter_counts_with_variance_and_no_rule_fails_open_and_posts():
    conn = _MultiConn([
        [{'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': None,
          'variance_qty': None, 'posted': False, 'product_name': 'Widget',
          'bin': 'A1', 'uom': 'ea'}],           # get_cycle_count_lines
        [],                                      # update line (counted=8, variance=3)
        [{'price': 2.0}],                        # price lookup for variance value
        [],                                      # update cycle_count status=submitted
        [],                                      # submit_for_approval: existing steps (none)
        [],                                      # submit_for_approval: get_applicable_rules (none configured)
        # -- fail-open auto post --
        [{'id': 3, 'count_number': 'CC-2026-0001'}],  # get_cycle_count
        [{'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': 8.0,
          'variance_qty': 3.0, 'posted': False, 'product_name': 'Widget',
          'bin': 'A1', 'uom': 'ea'}],           # get_cycle_count_lines
        [],                                      # record_transaction: insert inventory_transaction
        [{'amount': 8.0, 'reorder_point': 0, 'name': 'Widget'}],  # record_transaction: update product returning amount
        [],                                      # update cycle_count_line posted=TRUE
        [],                                      # update cycle_count status=posted
    ])
    status = enter_counts(conn, 3, {1: 8.0}, 'eric')
    assert status == 'posted'


def test_enter_counts_with_variance_and_matching_rule_stays_pending():
    conn = _MultiConn([
        [{'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': None,
          'variance_qty': None, 'posted': False, 'product_name': 'Widget',
          'bin': 'A1', 'uom': 'ea'}],           # get_cycle_count_lines
        [],                                      # update line
        [{'price': 2.0}],                        # price lookup
        [],                                      # update cycle_count status=submitted
        [],                                      # submit_for_approval: existing steps (none)
        [{'id': 5, 'entity_type': 'cycle_count', 'dept_key': '', 'threshold_amount': 1.0,
          'approver_role': 'Department Manager', 'seq': 10, 'escalate_after_hours': 24.0}],
        [],                                      # ensure_notification_table: CREATE TABLE
        [],                                      # ensure_notification_table: CREATE INDEX
        [{'id': 900}],                            # insert approval_step returning id
        [],                                      # notify fan-out to Department Manager role
    ])
    status = enter_counts(conn, 3, {1: 8.0}, 'eric')
    assert status == 'submitted'


# ── decide_cycle_count ───────────────────────────────────────────────────

def test_decide_cycle_count_approve_posts():
    conn = _MultiConn([
        [{'id': 900, 'entity_type': 'cycle_count', 'entity_id': 3, 'seq': 10,
          'status': 'pending'}],                 # decide_step: step lookup
        [],                                       # decide_step: prior-steps check (none pending)
        [],                                       # decide_step: update step
        [],                                       # decide_step: remaining pending count -> 0 -> approved
        [{'id': 3, 'count_number': 'CC-2026-0001'}],  # post_cycle_count: get_cycle_count
        [{'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': 8.0,
          'variance_qty': 3.0, 'posted': False, 'product_name': 'Widget',
          'bin': 'A1', 'uom': 'ea'}],           # get_cycle_count_lines
        [],                                       # record_transaction insert
        [{'amount': 8.0, 'reorder_point': 0, 'name': 'Widget'}],  # record_transaction update returning
        [],                                       # update line posted
        [],                                       # update cycle_count status=posted
    ])
    status = decide_cycle_count(conn, 3, 900, 'approved', 'manager@example.com')
    assert status == 'posted'


def test_decide_cycle_count_reject_sets_rejected():
    conn = _MultiConn([
        [{'id': 900, 'entity_type': 'cycle_count', 'entity_id': 3, 'seq': 10,
          'status': 'pending'}],                 # decide_step: step lookup
        [],                                       # decide_step: prior-steps check
        [],                                       # decide_step: update step
        [],                                       # update cycle_count status=rejected
    ])
    status = decide_cycle_count(conn, 3, 900, 'rejected', 'manager@example.com')
    assert status == 'rejected'


# ── post_cycle_count ─────────────────────────────────────────────────────

def test_post_cycle_count_skips_already_posted_and_zero_variance_lines():
    conn = _MultiConn([
        [{'id': 3, 'count_number': 'CC-2026-0001'}],  # get_cycle_count
        [
            {'id': 1, 'product_id': 10, 'system_qty': 5.0, 'counted_qty': 5.0,
             'variance_qty': 0.0, 'posted': False, 'product_name': 'A', 'bin': '', 'uom': 'ea'},
            {'id': 2, 'product_id': 20, 'system_qty': 5.0, 'counted_qty': 5.0,
             'variance_qty': 3.0, 'posted': True, 'product_name': 'B', 'bin': '', 'uom': 'ea'},
        ],
        [],                                        # update cycle_count status=posted
    ])
    post_cycle_count(conn, 3, 'eric')
    # neither line should have triggered record_transaction (zero variance / already posted)
    assert len(conn.calls) == 3


def test_post_cycle_count_posts_variance_line_with_signed_delta():
    conn = _MultiConn([
        [{'id': 3, 'count_number': 'CC-2026-0001'}],  # get_cycle_count
        [{'id': 2, 'product_id': 20, 'system_qty': 5.0, 'counted_qty': 8.0,
          'variance_qty': 3.0, 'posted': False, 'product_name': 'B', 'bin': '', 'uom': 'ea'}],
        [],                                        # record_transaction ALTER (self-heal)
        [],                                        # record_transaction insert
        [{'amount': 8.0, 'reorder_point': 0, 'name': 'Widget'}],  # record_transaction update returning
        [],                                        # update line posted
        [],                                        # update cycle_count status=posted
    ])
    post_cycle_count(conn, 3, 'eric')
    update_product_call = conn.calls[4]
    assert update_product_call[1] == [3.0, 20]  # delta, product_id


def test_post_cycle_count_missing_sheet_raises():
    import pytest
    conn = _MultiConn([[]])
    with pytest.raises(ValueError):
        post_cycle_count(conn, 999, 'eric')
