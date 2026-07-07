"""
shop_floor_core.py — Qt-free OEE Live Shop Floor Dashboard (P3-G).

An earlier feature (P1-C, ``oee_core.py``) already computes OEE, but only as
a **date-range report** derived from completed ``wo_operation`` rows and
``maint_downtime`` — there is no shift concept anywhere in this codebase and
no data-entry screen at all (its only UI is a read-only report under
Maintenance). This module adds the missing piece: operators log production
counts and downtime directly against a workcenter/shift/date, and OEE is
computed live from those entries — a parallel, shift-granular calculation,
not a replacement for ``oee_core``'s period-level reporting.

``oee_core._oee_from_totals`` isn't reused because its Performance formula
(``std_hours / actual_hours``) assumes a linked work-order operation, which
a shift's manual qty/scrap tally doesn't have. Performance here is
``qty_produced / planned_qty`` instead — the same number the spec's
"planned vs. actual output" shift-summary bullet asks for, so one
calculation serves both needs.

Two deliberate simplifying assumptions (no shift-window or shift-length
concept exists anywhere else to derive these from):
  - Every shift is treated as a fixed ``SHIFT_LENGTH_HOURS`` (8h) scheduled
    window, regardless of ``workcenter.capacity_hours_per_day``.
  - ``SHIFT_WINDOWS`` fixes wall-clock hours per shift name, used only to
    default the live dashboard/TV display to "right now's" shift.

Every function takes an open connection; the caller owns the transaction
(same convention as blanket_po_core / multi_entity_core).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .log_utils import get_logger
from .maintenance_core import DOWNTIME_CATEGORIES
from .routing_core import list_workcenters

log = get_logger(__name__)

SHIFTS = ('Day', 'Swing', 'Night')
SHIFT_LENGTH_HOURS = 8

# (start_hour, end_hour) in 24h wall-clock time; Night wraps past midnight.
SHIFT_WINDOWS = {
    'Day': (6, 14),
    'Swing': (14, 22),
    'Night': (22, 6),
}


def current_shift_for_now(now: datetime | None = None) -> tuple:
    """Return (shift_name, entry_date) for the shift covering ``now``
    (defaults to the current time). Night wraps past midnight, so the hours
    from 00:00-06:00 belong to the Night shift that started the *previous*
    calendar day."""
    now = now or datetime.now()
    hour = now.hour
    for shift, (start, end) in SHIFT_WINDOWS.items():
        if start < end:
            if start <= hour < end:
                return shift, now.date()
        else:  # wraps past midnight (Night)
            if hour >= start:
                return shift, now.date()
            if hour < end:
                return shift, now.date() - timedelta(days=1)
    return SHIFTS[0], now.date()


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_shop_floor_tables(conn) -> None:
    """Create shop_floor_* tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shop_floor_production (
            id            SERIAL PRIMARY KEY,
            workcenter_id INTEGER NOT NULL REFERENCES workcenter(id),
            shift         TEXT NOT NULL,
            entry_date    DATE NOT NULL,
            qty_produced  REAL NOT NULL DEFAULT 0,
            qty_scrapped  REAL NOT NULL DEFAULT 0,
            created_by    TEXT DEFAULT '',
            created_at    TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shop_floor_downtime (
            id              SERIAL PRIMARY KEY,
            workcenter_id   INTEGER NOT NULL REFERENCES workcenter(id),
            shift           TEXT NOT NULL,
            entry_date      DATE NOT NULL,
            reason_category TEXT NOT NULL,
            notes           TEXT DEFAULT '',
            minutes         REAL NOT NULL DEFAULT 0,
            created_by      TEXT DEFAULT '',
            created_at      TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shop_floor_shift_plan (
            id            SERIAL PRIMARY KEY,
            workcenter_id INTEGER NOT NULL REFERENCES workcenter(id),
            shift         TEXT NOT NULL,
            entry_date    DATE NOT NULL,
            planned_qty   REAL NOT NULL DEFAULT 0,
            created_by    TEXT DEFAULT '',
            created_at    TEXT DEFAULT '',
            UNIQUE (workcenter_id, shift, entry_date)
        )
    """)


# ---------------------------------------------------------------------------
# Write: production / downtime / plan
# ---------------------------------------------------------------------------

def record_production(conn, workcenter_id: int, shift: str, entry_date: str,
                       qty_produced: float, qty_scrapped: float,
                       created_by: str) -> int:
    if shift not in SHIFTS:
        raise ValueError(f"Unknown shift: {shift!r}")
    qty_produced = float(qty_produced or 0)
    qty_scrapped = float(qty_scrapped or 0)
    if qty_produced < 0 or qty_scrapped < 0:
        raise ValueError("Quantities cannot be negative.")
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO shop_floor_production "
        "(workcenter_id, shift, entry_date, qty_produced, qty_scrapped, "
        "created_by, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (workcenter_id, shift, entry_date, qty_produced, qty_scrapped,
         created_by or '', now),
    ).fetchone()
    return row['id']


def record_downtime(conn, workcenter_id: int, shift: str, entry_date: str,
                     reason_category: str, notes: str, minutes: float,
                     created_by: str) -> int:
    if shift not in SHIFTS:
        raise ValueError(f"Unknown shift: {shift!r}")
    if reason_category not in DOWNTIME_CATEGORIES:
        raise ValueError(f"Unknown downtime reason category: {reason_category!r}")
    minutes = float(minutes or 0)
    if minutes <= 0:
        raise ValueError("Downtime minutes must be positive.")
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO shop_floor_downtime "
        "(workcenter_id, shift, entry_date, reason_category, notes, minutes, "
        "created_by, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (workcenter_id, shift, entry_date, reason_category, notes or '',
         minutes, created_by or '', now),
    ).fetchone()
    return row['id']


def set_shift_plan(conn, workcenter_id: int, shift: str, entry_date: str,
                    planned_qty: float, created_by: str) -> None:
    if shift not in SHIFTS:
        raise ValueError(f"Unknown shift: {shift!r}")
    planned_qty = float(planned_qty or 0)
    if planned_qty < 0:
        raise ValueError("Planned quantity cannot be negative.")
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO shop_floor_shift_plan "
        "(workcenter_id, shift, entry_date, planned_qty, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (workcenter_id, shift, entry_date) DO UPDATE "
        "SET planned_qty=EXCLUDED.planned_qty, created_by=EXCLUDED.created_by, "
        "created_at=EXCLUDED.created_at",
        (workcenter_id, shift, entry_date, planned_qty, created_by or '', now),
    )


# ---------------------------------------------------------------------------
# Read / OEE calculation
# ---------------------------------------------------------------------------

def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def _shift_totals(conn, workcenter_id: int, shift: str, entry_date: str) -> tuple:
    row = conn.execute(
        "SELECT COALESCE(SUM(qty_produced), 0) AS qty_produced, "
        "COALESCE(SUM(qty_scrapped), 0) AS qty_scrapped "
        "FROM shop_floor_production "
        "WHERE workcenter_id = %s AND shift = %s AND entry_date = %s",
        (workcenter_id, shift, entry_date),
    ).fetchone()
    down_row = conn.execute(
        "SELECT COALESCE(SUM(minutes), 0) AS minutes FROM shop_floor_downtime "
        "WHERE workcenter_id = %s AND shift = %s AND entry_date = %s",
        (workcenter_id, shift, entry_date),
    ).fetchone()
    return (float(row['qty_produced'] or 0.0), float(row['qty_scrapped'] or 0.0),
            float(down_row['minutes'] or 0.0))


def _get_plan(conn, workcenter_id: int, shift: str, entry_date: str):
    row = conn.execute(
        "SELECT planned_qty FROM shop_floor_shift_plan "
        "WHERE workcenter_id = %s AND shift = %s AND entry_date = %s",
        (workcenter_id, shift, entry_date),
    ).fetchone()
    return float(row['planned_qty']) if row else None


def get_shift_oee(conn, workcenter_id: int, shift: str, entry_date: str) -> dict:
    """Live OEE for one workcenter/shift/date, computed from operator
    entries rather than a date-range report (see module docstring)."""
    qty_produced, qty_scrapped, downtime_minutes = _shift_totals(
        conn, workcenter_id, shift, entry_date)
    planned_qty = _get_plan(conn, workcenter_id, shift, entry_date)
    has_plan = planned_qty is not None and planned_qty > 0

    scheduled_minutes = SHIFT_LENGTH_HOURS * 60
    availability = _clamp((scheduled_minutes - downtime_minutes) / scheduled_minutes)

    if has_plan:
        performance = _clamp(qty_produced / planned_qty)
    else:
        # No target to compare against -- not the same as "nothing
        # happened," so this deliberately does NOT default to 0.0 the way
        # oee_core does for an empty period (see module docstring).
        performance = 1.0

    quality = (
        _clamp((qty_produced - qty_scrapped) / qty_produced)
        if qty_produced > 0 else 1.0
    )
    oee = availability * performance * quality

    return {
        'workcenter_id': workcenter_id,
        'shift': shift,
        'entry_date': str(entry_date),
        'qty_produced': qty_produced,
        'qty_scrapped': qty_scrapped,
        'downtime_minutes': downtime_minutes,
        'planned_qty': planned_qty,
        'has_plan': has_plan,
        'availability_pct': round(availability * 100, 1),
        'performance_pct': round(performance * 100, 1),
        'quality_pct': round(quality * 100, 1),
        'oee_pct': round(oee * 100, 1),
    }


def list_live_shift_oee(conn, shift: str, entry_date: str) -> list:
    """Live OEE for every active workcenter, for one shift/date."""
    workcenters = list_workcenters(conn, active_only=True)
    out = []
    for wc in workcenters:
        result = get_shift_oee(conn, wc['id'], shift, entry_date)
        result['workcenter_name'] = wc['name']
        out.append(result)
    return out


def list_downtime_entries(conn, workcenter_id: int, shift: str, entry_date: str) -> list:
    rows = conn.execute(
        "SELECT * FROM shop_floor_downtime "
        "WHERE workcenter_id = %s AND shift = %s AND entry_date = %s "
        "ORDER BY id DESC",
        (workcenter_id, shift, entry_date),
    ).fetchall()
    return [dict(r) for r in rows]
