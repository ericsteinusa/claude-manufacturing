"""repetitive_core.py — Qt-free Repetitive Manufacturing, 7/10 of the
top-10 ERPs have it.

Discrete manufacturing in this app plans and tracks production through
individual Work Orders (``work_orders_core``) — each one its own
number, quantity, and material-issue lifecycle. Repetitive/flow
manufacturing is different on purpose: a production line runs a **rate**
(units/day) against a schedule rather than a series of discrete orders,
and material consumption is **backflushed** — computed from the BOM and
deducted automatically when output is logged, rather than issued
line-by-line against a WO. This module models that directly instead of
creating a WO per day of output, which would just be discrete
manufacturing wearing a rate-based costume.

A ``repetitive_schedule`` is a planned rate (units/day) for one product on
one workcenter over a date range. ``log_production`` records one day's
actual output against a schedule and immediately backflushes: it computes
the BOM-derived component quantities for the units completed (reusing
``bom_web_core.get_bom`` + ``bom_core.explode_quantity`` — no forked BOM
logic) and posts them through ``inventory_core.record_transaction`` — an
'issue' for each component and a 'receive' for the finished product —
the same audited transaction path every other inventory movement in this
app goes through. Scrapped units are logged but not backflushed (no
component consumption or output credit for units that didn't ship).

Every function takes an open connection; the caller owns the transaction
(same convention as skills_matrix_core / fmea_core).
"""

from __future__ import annotations

import datetime

from .bom_core import explode_quantity
from .bom_web_core import get_bom
from .inventory_core import record_transaction

SCHEDULE_STATUSES = ('active', 'inactive')


def _today() -> str:
    return datetime.date.today().isoformat()


def ensure_repetitive_tables(conn):
    """Create repetitive_schedule / repetitive_production_log if absent.
    Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repetitive_schedule (
            id                SERIAL PRIMARY KEY,
            product_id        INTEGER NOT NULL REFERENCES product(id),
            workcenter_id     INTEGER REFERENCES workcenter(id),
            rate_per_day      REAL NOT NULL DEFAULT 0.0,
            effective_start   TEXT NOT NULL DEFAULT '',
            effective_end     TEXT,
            status            TEXT NOT NULL DEFAULT 'active',
            created_by        TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repetitive_production_log (
            id                SERIAL PRIMARY KEY,
            schedule_id       INTEGER NOT NULL REFERENCES repetitive_schedule(id),
            production_date   TEXT NOT NULL,
            qty_completed     REAL NOT NULL DEFAULT 0.0,
            qty_scrapped      REAL NOT NULL DEFAULT 0.0,
            created_by        TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS repetitive_production_log_schedule "
        "ON repetitive_production_log(schedule_id)"
    )


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

def list_schedules(conn, product_id=None, status=None):
    sql = (
        "SELECT s.*, p.name AS product_name, w.name AS workcenter_name "
        "FROM repetitive_schedule s "
        "JOIN product p ON p.id = s.product_id "
        "LEFT JOIN workcenter w ON w.id = s.workcenter_id "
        "WHERE TRUE"
    )
    params: list = []
    if product_id:
        sql += " AND s.product_id = %s"
        params.append(product_id)
    if status:
        sql += " AND s.status = %s"
        params.append(status)
    sql += " ORDER BY s.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_schedule(conn, schedule_id):
    row = conn.execute(
        "SELECT s.*, p.name AS product_name, w.name AS workcenter_name "
        "FROM repetitive_schedule s "
        "JOIN product p ON p.id = s.product_id "
        "LEFT JOIN workcenter w ON w.id = s.workcenter_id "
        "WHERE s.id = %s",
        (schedule_id,),
    ).fetchone()
    return dict(row) if row else None


def create_schedule(conn, product_id, workcenter_id, rate_per_day,
                    effective_start=None, effective_end=None, created_by=''):
    if rate_per_day is None or float(rate_per_day) <= 0:
        raise ValueError('rate_per_day must be greater than zero')
    row = conn.execute(
        "INSERT INTO repetitive_schedule "
        "(product_id, workcenter_id, rate_per_day, effective_start, effective_end, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (product_id, workcenter_id, float(rate_per_day),
         effective_start or _today(), effective_end or None, created_by or ''),
    ).fetchone()
    return row['id']


def set_schedule_status(conn, schedule_id, status):
    if status not in SCHEDULE_STATUSES:
        raise ValueError(f'status must be one of {SCHEDULE_STATUSES}')
    conn.execute(
        "UPDATE repetitive_schedule SET status = %s WHERE id = %s",
        (status, schedule_id),
    )


# ---------------------------------------------------------------------------
# Production logging + backflush
# ---------------------------------------------------------------------------

def list_production_log(conn, schedule_id, date_from=None, date_to=None):
    sql = "SELECT * FROM repetitive_production_log WHERE schedule_id = %s"
    params: list = [schedule_id]
    if date_from:
        sql += " AND production_date >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND production_date <= %s"
        params.append(date_to)
    sql += " ORDER BY production_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def log_production(conn, schedule_id, production_date, qty_completed,
                   qty_scrapped=0.0, created_by=''):
    """Record one day's output against a schedule and backflush materials
    for the completed (non-scrapped) units: an 'issue' transaction per BOM
    component, then a 'receive' transaction for the finished product.
    Returns the new log row id."""
    schedule = get_schedule(conn, schedule_id)
    if not schedule:
        raise ValueError(f'No schedule with id {schedule_id}')
    qty_completed = float(qty_completed or 0.0)
    qty_scrapped = float(qty_scrapped or 0.0)
    if qty_completed < 0 or qty_scrapped < 0:
        raise ValueError('Quantities cannot be negative.')

    row = conn.execute(
        "INSERT INTO repetitive_production_log "
        "(schedule_id, production_date, qty_completed, qty_scrapped, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (schedule_id, production_date, qty_completed, qty_scrapped, created_by or ''),
    ).fetchone()
    log_id = row['id']

    if qty_completed > 0:
        reference = f'Repetitive log #{log_id}'
        for line in get_bom(conn, schedule['product_id']):
            needed = explode_quantity(line['qty_required'], qty_completed, line['scrap_pct'])
            record_transaction(
                conn, line['component_id'], 'issue', needed, reference,
                f"Backflush for schedule #{schedule_id}", created_by,
            )
        record_transaction(
            conn, schedule['product_id'], 'receive', qty_completed, reference,
            f"Repetitive production, schedule #{schedule_id}", created_by,
        )
    return log_id


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def get_schedule_summary(conn, schedule_id, date_from, date_to):
    """{'planned_qty', 'actual_qty', 'scrapped_qty', 'attainment_pct'} over
    a date range. planned_qty is rate_per_day x the number of calendar days
    in the range (inclusive) — a simple planning approximation, not
    calendar-aware of weekends/holidays."""
    schedule = get_schedule(conn, schedule_id)
    if not schedule:
        raise ValueError(f'No schedule with id {schedule_id}')

    days = (
        datetime.date.fromisoformat(date_to) - datetime.date.fromisoformat(date_from)
    ).days + 1
    planned_qty = schedule['rate_per_day'] * max(days, 0)

    row = conn.execute(
        "SELECT COALESCE(SUM(qty_completed), 0) AS actual, "
        "COALESCE(SUM(qty_scrapped), 0) AS scrapped "
        "FROM repetitive_production_log "
        "WHERE schedule_id = %s AND production_date >= %s AND production_date <= %s",
        (schedule_id, date_from, date_to),
    ).fetchone()
    actual_qty = row['actual'] if row else 0.0
    scrapped_qty = row['scrapped'] if row else 0.0
    attainment_pct = round(100.0 * actual_qty / planned_qty, 1) if planned_qty else None

    return {
        'planned_qty': planned_qty,
        'actual_qty': actual_qty,
        'scrapped_qty': scrapped_qty,
        'attainment_pct': attainment_pct,
    }
