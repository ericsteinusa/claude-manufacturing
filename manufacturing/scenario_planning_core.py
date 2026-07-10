"""scenario_planning_core.py — Qt-free What-If Scenario Planning (8/10 of
the top-10 ERPs have it — the highest-adoption item remaining on the
"buildable now" list after Discount/CoA/Skills-Matrix shipped).

A scenario is a named set of hypothetical adjustments — extra demand for a
product, or a temporary capacity override on a workcenter — that gets
compared against the real baseline without ever touching real data:

  - Demand adjustments feed into ``mrp_web_core.run_mrp_dated``'s new
    ``extra_demand`` parameter (additive/opt-in, mirrors the P4-A
    ``include_forecast`` precedent exactly) — a plain in-memory merge, no
    row is ever written against a real Sales Order.
  - Capacity adjustments overlay a hypothetical per-day hours override on
    top of ``capacity_planning_core.get_capacity_check``'s real output,
    entirely in Python — the real ``workcenter``/``workcenter_calendar_
    exception`` tables are never written to.

run_scenario() returns baseline vs. scenario side by side for both MRP
volume and capacity/bottleneck pressure, so a planner can ask "what if we
added 500 units of demand for Product X" or "what if Workcenter 3 ran a
Saturday shift for the next two weeks" and see the answer without
committing to anything.

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / sampling_plan_core).
"""

from __future__ import annotations

import copy
import datetime

from .capacity_planning_core import get_capacity_check
from .mrp_web_core import run_mrp_dated

DEFAULT_CAPACITY_HORIZON_DAYS = 30


def ensure_scenario_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenario (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            description  TEXT NOT NULL DEFAULT '',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenario_demand_adjustment (
            id           SERIAL PRIMARY KEY,
            scenario_id  INTEGER NOT NULL REFERENCES scenario(id),
            product_id   INTEGER NOT NULL REFERENCES product(id),
            qty          REAL NOT NULL DEFAULT 0.0,
            need_date    TEXT NOT NULL,
            notes        TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenario_capacity_adjustment (
            id             SERIAL PRIMARY KEY,
            scenario_id    INTEGER NOT NULL REFERENCES scenario(id),
            workcenter_id  INTEGER NOT NULL REFERENCES workcenter(id),
            date_from      TEXT NOT NULL,
            date_to        TEXT NOT NULL,
            hours_per_day  REAL NOT NULL DEFAULT 0.0,
            notes          TEXT NOT NULL DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Scenario CRUD
# ---------------------------------------------------------------------------

def list_scenarios(conn, search=None):
    sql = "SELECT * FROM scenario WHERE TRUE"
    params: list = []
    if search:
        sql += " AND name ILIKE %s"
        params.append(f"%{search}%")
    sql += " ORDER BY created_at DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_scenario(conn, scenario_id):
    row = conn.execute("SELECT * FROM scenario WHERE id = %s", (scenario_id,)).fetchone()
    return dict(row) if row else None


def create_scenario(conn, name, description='', created_by=''):
    if not name.strip():
        raise ValueError('Name is required.')
    row = conn.execute(
        "INSERT INTO scenario (name, description, created_by) "
        "VALUES (%s,%s,%s) RETURNING id",
        (name.strip(), description or '', created_by or ''),
    ).fetchone()
    return row['id']


def delete_scenario(conn, scenario_id):
    """Deletes the scenario and its adjustments — a scenario has no
    downstream effects on real data to clean up (see module docstring),
    so this is a plain cascade-by-hand delete, not a soft-delete."""
    conn.execute("DELETE FROM scenario_demand_adjustment WHERE scenario_id = %s", (scenario_id,))
    conn.execute("DELETE FROM scenario_capacity_adjustment WHERE scenario_id = %s", (scenario_id,))
    conn.execute("DELETE FROM scenario WHERE id = %s", (scenario_id,))


# ---------------------------------------------------------------------------
# Adjustments
# ---------------------------------------------------------------------------

def list_demand_adjustments(conn, scenario_id):
    rows = conn.execute("""
        SELECT sda.*, p.name AS product_name
        FROM scenario_demand_adjustment sda
        JOIN product p ON p.id = sda.product_id
        WHERE sda.scenario_id = %s
        ORDER BY sda.need_date, sda.id
    """, (scenario_id,)).fetchall()
    return [dict(r) for r in rows]


def add_demand_adjustment(conn, scenario_id, product_id, qty, need_date, notes=''):
    if qty <= 0:
        raise ValueError('Qty must be positive.')
    row = conn.execute(
        "INSERT INTO scenario_demand_adjustment "
        "(scenario_id, product_id, qty, need_date, notes) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (scenario_id, product_id, qty, need_date, notes or ''),
    ).fetchone()
    return row['id']


def remove_demand_adjustment(conn, adjustment_id):
    conn.execute("DELETE FROM scenario_demand_adjustment WHERE id = %s", (adjustment_id,))


def list_capacity_adjustments(conn, scenario_id):
    rows = conn.execute("""
        SELECT sca.*, wc.name AS workcenter_name
        FROM scenario_capacity_adjustment sca
        JOIN workcenter wc ON wc.id = sca.workcenter_id
        WHERE sca.scenario_id = %s
        ORDER BY sca.date_from, sca.id
    """, (scenario_id,)).fetchall()
    return [dict(r) for r in rows]


def add_capacity_adjustment(conn, scenario_id, workcenter_id, date_from, date_to,
                            hours_per_day, notes=''):
    if date_to < date_from:
        raise ValueError('date_to cannot be before date_from.')
    if hours_per_day < 0:
        raise ValueError('hours_per_day cannot be negative.')
    row = conn.execute(
        "INSERT INTO scenario_capacity_adjustment "
        "(scenario_id, workcenter_id, date_from, date_to, hours_per_day, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (scenario_id, workcenter_id, date_from, date_to, hours_per_day, notes or ''),
    ).fetchone()
    return row['id']


def remove_capacity_adjustment(conn, adjustment_id):
    conn.execute("DELETE FROM scenario_capacity_adjustment WHERE id = %s", (adjustment_id,))


# ---------------------------------------------------------------------------
# Comparison helpers (pure functions — no DB access, easy to unit test)
# ---------------------------------------------------------------------------

def summarize_mrp(planned_orders):
    """Aggregate counts/qty from a run_mrp_dated() result — the shape
    compared between baseline and scenario."""
    make_qty = sum(o['qty'] for o in planned_orders if o['order_type'] == 'make')
    buy_qty = sum(o['qty'] for o in planned_orders if o['order_type'] == 'buy')
    return {
        'order_count': len(planned_orders),
        'make_count': sum(1 for o in planned_orders if o['order_type'] == 'make'),
        'buy_count': sum(1 for o in planned_orders if o['order_type'] == 'buy'),
        'make_qty': make_qty,
        'buy_qty': buy_qty,
        'total_qty': make_qty + buy_qty,
    }


def apply_capacity_adjustments(capacity_check, adjustments):
    """Overlay hypothetical per-day hours onto a get_capacity_check()
    result. Never mutates the input — returns a deep copy so a caller can
    hold both the real baseline and the adjusted scenario side by side.
    An adjustment only affects the workcenter/date range it names; days
    outside every adjustment's window are left exactly as booked/available
    from the real data."""
    result = copy.deepcopy(capacity_check)
    by_wc: dict = {}
    for adj in adjustments:
        by_wc.setdefault(adj['workcenter_id'], []).append(adj)

    for wc_row in result:
        wc_adjustments = by_wc.get(wc_row['workcenter_id'])
        if not wc_adjustments:
            continue
        for day_info in wc_row['days']:
            for adj in wc_adjustments:
                if adj['date_from'] <= day_info['date'] <= adj['date_to']:
                    day_info['available'] = adj['hours_per_day']
                    day_info['pct'] = (
                        (day_info['booked'] / day_info['available'] * 100.0)
                        if day_info['available'] > 0
                        else (100.0 if day_info['booked'] > 0 else 0.0)
                    )
                    day_info['over_capacity'] = day_info['booked'] > day_info['available'] + 1e-9
                    break  # first matching adjustment for this day wins
    return result


def rank_bottlenecks(capacity_check):
    """Same ranking math as capacity_planning_core.identify_bottlenecks,
    but operating on an already-fetched capacity_check list (real or
    scenario-adjusted) instead of querying live — avoids duplicating the
    live SQL query for data that's already in memory."""
    result = []
    for c in capacity_check:
        total_avail = sum(d['available'] for d in c['days'])
        total_booked = sum(d['booked'] for d in c['days'])
        pct = (total_booked / total_avail * 100.0) if total_avail > 0 else (
            100.0 if total_booked > 0 else 0.0)
        result.append({
            'workcenter_id': c['workcenter_id'],
            'workcenter_name': c['workcenter_name'],
            'total_available': total_avail,
            'total_booked': total_booked,
            'utilization_pct': pct,
            'over_capacity_days': sum(1 for d in c['days'] if d['over_capacity']),
        })
    result.sort(key=lambda r: r['utilization_pct'], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run_scenario(conn, scenario_id, capacity_date_from=None, capacity_date_to=None):
    """Compare baseline vs. this scenario for both MRP demand and
    workcenter capacity. Raises ValueError if the scenario doesn't exist.
    Reads real data and computes in memory only — writes nothing."""
    scenario = get_scenario(conn, scenario_id)
    if not scenario:
        raise ValueError(f'No scenario with id {scenario_id}')

    demand_adjustments = list_demand_adjustments(conn, scenario_id)
    capacity_adjustments = list_capacity_adjustments(conn, scenario_id)

    extra_demand: dict = {}
    for adj in demand_adjustments:
        # need_date is stored as TEXT but mrp_web_core.get_demand_dated's real
        # SO-derived dates come back as datetime.date (DATE column) — sorting
        # a list that mixes str and date raises TypeError. Normalize here the
        # same way demand_forecast_core.get_forecast_demand_dated already does
        # for the same reason.
        need_date = adj['need_date']
        if isinstance(need_date, str):
            need_date = datetime.date.fromisoformat(need_date)
        extra_demand.setdefault(adj['product_id'], []).append((adj['qty'], need_date))

    baseline_planned = run_mrp_dated(conn)
    scenario_planned = (
        run_mrp_dated(conn, extra_demand=extra_demand) if extra_demand else baseline_planned
    )

    date_from = capacity_date_from or datetime.date.today().isoformat()
    date_to = capacity_date_to or (
        datetime.date.today() + datetime.timedelta(days=DEFAULT_CAPACITY_HORIZON_DAYS)
    ).isoformat()

    baseline_capacity = get_capacity_check(conn, date_from, date_to)
    scenario_capacity = (
        apply_capacity_adjustments(baseline_capacity, capacity_adjustments)
        if capacity_adjustments else baseline_capacity
    )

    return {
        'scenario': scenario,
        'demand_adjustments': demand_adjustments,
        'capacity_adjustments': capacity_adjustments,
        'mrp_baseline': summarize_mrp(baseline_planned),
        'mrp_scenario': summarize_mrp(scenario_planned),
        'capacity_baseline': baseline_capacity,
        'capacity_scenario': scenario_capacity,
        'bottlenecks_baseline': rank_bottlenecks(baseline_capacity),
        'bottlenecks_scenario': rank_bottlenecks(scenario_capacity),
    }
