"""
capacity_planning_core.py — Qt-free finite capacity scheduling (P3-A).

Builds on top of routing_core's workcenter/routing/wo_operation model and
the P2-A Gantt scheduler's scheduled_start/scheduled_end columns, adding:

  workcenter calendar   — which days of the week a workcenter runs, plus
                          one-off exceptions (holidays, overtime days)
  forward_schedule_wo   — pack a WO's operations forward from a start date,
                          in operation_seq order, respecting workcenter
                          daily capacity
  backward_schedule_wo  — same, packed backward from a due date
  get_capacity_check    — booked vs. available hours per workcenter per day
  identify_bottlenecks  — workcenters ranked by utilization over a horizon
  suggest_load_leveling — greedy "delay this operation N days" suggestions
                          for over-capacity (workcenter, day) pairs

Deliberate simplifications (documented rather than silently assumed):
  - Scheduling is day-granular: an operation is packed into whichever
    days have free hours on its workcenter, without sub-day precision
    beyond the resulting clock time. There's no shift-start-time concept
    per workcenter — every working day is assumed to open at
    DEFAULT_WORKDAY_START_HOUR.
  - "Booked hours" for an *already*-scheduled operation (from a prior
    forward/backward run or a manual Gantt drag) are derived by evenly
    distributing its total std_hours across the calendar days its
    scheduled_start/scheduled_end span — there is no separate per-day
    allocation ledger, so this is an approximation for operations that
    were scheduled unevenly by some other path. This mirrors the same
    simplification get_planned_workcenter_load already makes (whole-window
    sums instead of a real ledger), just applied per-day.
  - Load leveling is a greedy heuristic (probe forward for the first day
    with enough slack), not a constraint solver — it proposes one move at
    a time and lets a human confirm via apply_load_leveling_suggestion.

Every function takes an open connection; the caller owns the transaction
(same convention as routing_core / mrp_web_core).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .routing_core import (
    ensure_routing_tables, list_workcenters, get_wo_operations,
    reschedule_operation,
)
from .work_orders_core import get_wo
from .log_utils import get_logger

log = get_logger(__name__)

DEFAULT_WORKDAY_START_HOUR = 8.0
MIN_OPERATION_HOURS = 0.05
MAX_HORIZON_DAYS = 365
_WEEKDAY_COLUMNS = (
    'works_mon', 'works_tue', 'works_wed', 'works_thu',
    'works_fri', 'works_sat', 'works_sun',
)


def ensure_capacity_tables(conn):
    """Add workcenter calendar columns/table if absent. Does not commit."""
    ensure_routing_tables(conn)
    for col in _WEEKDAY_COLUMNS[:5]:
        conn.execute(
            f"ALTER TABLE workcenter ADD COLUMN IF NOT EXISTS "
            f"{col} BOOLEAN NOT NULL DEFAULT TRUE"
        )
    for col in _WEEKDAY_COLUMNS[5:]:
        conn.execute(
            f"ALTER TABLE workcenter ADD COLUMN IF NOT EXISTS "
            f"{col} BOOLEAN NOT NULL DEFAULT FALSE"
        )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workcenter_calendar_exception (
            id               SERIAL PRIMARY KEY,
            workcenter_id    INTEGER NOT NULL REFERENCES workcenter(id),
            exception_date   DATE NOT NULL,
            hours_available  REAL NOT NULL DEFAULT 0.0,
            notes            TEXT NOT NULL DEFAULT '',
            UNIQUE (workcenter_id, exception_date)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS workcenter_calendar_exception_wc "
        "ON workcenter_calendar_exception(workcenter_id, exception_date)"
    )


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def list_calendar_exceptions(conn, workcenter_id, date_from=None, date_to=None):
    conds = ["workcenter_id = %s"]
    params = [workcenter_id]
    if date_from:
        conds.append("exception_date >= %s")
        params.append(date_from)
    if date_to:
        conds.append("exception_date <= %s")
        params.append(date_to)
    rows = conn.execute(
        f"SELECT * FROM workcenter_calendar_exception WHERE {' AND '.join(conds)} "
        f"ORDER BY exception_date",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def set_calendar_exception(conn, workcenter_id, exception_date, hours_available, notes=''):
    """Upsert a one-off calendar override (holiday closure = 0.0 hours,
    overtime day = a custom value). Does not commit. Returns the row id."""
    row = conn.execute(
        "INSERT INTO workcenter_calendar_exception "
        "(workcenter_id, exception_date, hours_available, notes) "
        "VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (workcenter_id, exception_date) "
        "DO UPDATE SET hours_available = EXCLUDED.hours_available, notes = EXCLUDED.notes "
        "RETURNING id",
        (workcenter_id, exception_date, max(0.0, hours_available), notes or ''),
    ).fetchone()
    return row['id']


def remove_calendar_exception(conn, exception_id):
    conn.execute(
        "DELETE FROM workcenter_calendar_exception WHERE id = %s", (exception_id,),
    )


def set_workcenter_calendar(conn, workcenter_id, **day_flags):
    """Update which days of the week a workcenter runs.

    day_flags keys are any of _WEEKDAY_COLUMNS ('works_mon', ..., 'works_sun');
    unknown keys are ignored. Does not commit."""
    cols = {k: bool(v) for k, v in day_flags.items() if k in _WEEKDAY_COLUMNS}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE workcenter SET {set_clause} WHERE id = %s",
        list(cols.values()) + [workcenter_id],
    )


def list_workcenters_with_calendar(conn):
    """Like routing_core.list_workcenters, plus the day-of-week working
    flags — for the workcenter admin page's calendar management UI."""
    rows = conn.execute(
        "SELECT id, name, dept, capacity_hours_per_day, labor_rate, notes, is_active, "
        + ", ".join(_WEEKDAY_COLUMNS) +
        " FROM workcenter ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def _load_workcenter_calendar(conn, workcenter_id, date_from, date_to):
    """{date: available_hours} for every day in [date_from, date_to]."""
    row = conn.execute(
        "SELECT capacity_hours_per_day, " + ", ".join(_WEEKDAY_COLUMNS) +
        " FROM workcenter WHERE id = %s",
        (workcenter_id,),
    ).fetchone()
    if not row:
        return {}
    row = dict(row)
    flags = [row[c] for c in _WEEKDAY_COLUMNS]
    exceptions = {
        r['exception_date']: r['hours_available']
        for r in conn.execute(
            "SELECT exception_date, hours_available "
            "FROM workcenter_calendar_exception "
            "WHERE workcenter_id = %s AND exception_date BETWEEN %s AND %s",
            (workcenter_id, date_from, date_to),
        ).fetchall()
    }
    calendar = {}
    d = date_from
    while d <= date_to:
        if d in exceptions:
            calendar[d] = exceptions[d]
        else:
            calendar[d] = row['capacity_hours_per_day'] if flags[d.weekday()] else 0.0
        d += timedelta(days=1)
    return calendar


def _to_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def get_booked_hours_by_day(conn, workcenter_id, date_from, date_to, exclude_wo_id=None):
    """{date: hours} of existing scheduled load on a workcenter, evenly
    distributing each operation's std_hours across the calendar days its
    scheduled window spans (see module docstring)."""
    sql = (
        "SELECT std_hours, scheduled_start, scheduled_end FROM wo_operation "
        "WHERE workcenter_id = %s AND status IN ('pending', 'in_progress') "
        "AND scheduled_start IS NOT NULL AND scheduled_end IS NOT NULL "
        "AND scheduled_start::date <= %s AND scheduled_end::date >= %s"
    )
    params = [workcenter_id, date_to, date_from]
    if exclude_wo_id is not None:
        sql += " AND wo_id != %s"
        params.append(exclude_wo_id)
    rows = conn.execute(sql, params).fetchall()

    booked: dict = {}
    for r in rows:
        start_d = _to_date(r['scheduled_start'])
        end_d = _to_date(r['scheduled_end'])
        span_days = max(1, (end_d - start_d).days + 1)
        per_day = (r['std_hours'] or 0.0) / span_days
        d = max(start_d, date_from)
        last = min(end_d, date_to)
        while d <= last:
            booked[d] = booked.get(d, 0.0) + per_day
            d += timedelta(days=1)
    return booked


# ---------------------------------------------------------------------------
# Forward / backward scheduling (pure packing helpers)
# ---------------------------------------------------------------------------

def _hour_to_datetime(day, hour):
    return datetime(day.year, day.month, day.day) + timedelta(hours=hour)


def _hour_of_day(dt):
    return dt.hour + dt.minute / 60 + dt.second / 3600


def _pack_forward(std_hours, start_day, available_hours_for_day, booked,
                  workday_start_hour=DEFAULT_WORKDAY_START_HOUR, not_before=None):
    """Pack std_hours of work forward starting no earlier than start_day.

    available_hours_for_day(day) -> total calendar capacity for that day
    (independent of what's booked). booked is a {date: hours} dict this
    function reads AND mutates in place as it consumes capacity, so
    scheduling several operations on the same workcenter in sequence (by
    reusing the same booked dict) correctly avoids double-booking.

    not_before: an optional datetime — the segment placed on start_day
    (only start_day; later spillover days are unaffected) cannot begin
    before this clock time. This is what makes operation N+1 respect
    operation N's actual finish time even when the two are on different
    workcenters (so their `booked` ledgers don't already overlap) — same-
    workcenter sequencing is already implied by sharing one `booked` dict,
    but a cross-workcenter handoff has no other link between the two.

    Returns (start_dt, end_dt). Raises ValueError if it can't fit within
    MAX_HORIZON_DAYS (e.g. a workcenter with an all-zero calendar).
    """
    remaining = max(std_hours, MIN_OPERATION_HOURS)
    day = start_day
    start_dt = end_dt = None
    for _ in range(MAX_HORIZON_DAYS):
        cap = available_hours_for_day(day)
        used = booked.get(day, 0.0)
        day_close = workday_start_hour + cap
        earliest = workday_start_hour + used
        if not_before is not None and day == start_day and _to_date(not_before) == day:
            earliest = max(earliest, _hour_of_day(not_before))
        free = day_close - earliest
        if free <= 1e-9:
            day += timedelta(days=1)
            continue
        consume = min(remaining, free)
        if start_dt is None:
            start_dt = _hour_to_datetime(day, earliest)
        end_dt = _hour_to_datetime(day, earliest + consume)
        booked[day] = used + consume
        remaining -= consume
        if remaining <= 1e-9:
            return start_dt, end_dt
        day += timedelta(days=1)
    raise ValueError(
        f"Could not fit {std_hours}h of work within {MAX_HORIZON_DAYS} days — "
        "check the workcenter's calendar"
    )


def _pack_backward(std_hours, end_day, available_hours_for_day, booked,
                   workday_start_hour=DEFAULT_WORKDAY_START_HOUR, not_after=None):
    """Mirror of _pack_forward: packs std_hours of work backward, ending
    no later than end_day. Each day's free slice is consumed from its
    tail end (latest hours first) working backward — so the segment ends
    at (workday_start_hour + cap - already_used) and starts `consume`
    hours earlier. Only the total hours booked per day matters for the
    capacity check; a forward-scheduled and a backward-scheduled segment
    sharing one day never overlap in placement logic because each only
    ever looks at the cumulative booked total, not the other's exact
    slice.

    not_after: an optional datetime — the segment placed on end_day (only
    end_day; earlier spillover days are unaffected) cannot finish after
    this clock time (the mirror of forward's not_before, for a downstream
    operation on a different workcenter than the one being packed here)."""
    remaining = max(std_hours, MIN_OPERATION_HOURS)
    day = end_day
    start_dt = end_dt = None
    for _ in range(MAX_HORIZON_DAYS):
        cap = available_hours_for_day(day)
        used = booked.get(day, 0.0)
        latest = workday_start_hour + cap - used
        if not_after is not None and day == end_day and _to_date(not_after) == day:
            latest = min(latest, _hour_of_day(not_after))
        free = latest - workday_start_hour
        if free <= 1e-9:
            day -= timedelta(days=1)
            continue
        consume = min(remaining, free)
        if end_dt is None:
            end_dt = _hour_to_datetime(day, latest)
        start_dt = _hour_to_datetime(day, latest - consume)
        booked[day] = used + consume
        remaining -= consume
        if remaining <= 1e-9:
            return start_dt, end_dt
        day -= timedelta(days=1)
    raise ValueError(
        f"Could not fit {std_hours}h of work within {MAX_HORIZON_DAYS} days — "
        "check the workcenter's calendar"
    )


def _iso_z(dt):
    return dt.isoformat() + 'Z'


def forward_schedule_wo(conn, wo_id, start_from=None):
    """Schedule every non-completed/non-skipped operation of a WO forward
    from start_from (default today), in operation_seq order — operation
    N+1 never starts before operation N's scheduled_end. Persists via
    reschedule_operation (does not commit; caller commits).

    Returns {'operations': [{id, operation_name, scheduled_start,
    scheduled_end}], 'computed_end_date': ISO date of the last operation's
    finish}. Raises ValueError if the WO has no schedulable operations.
    """
    ops = get_wo_operations(conn, wo_id)
    schedulable = [o for o in ops if o['status'] not in ('completed', 'skipped')]
    if not schedulable:
        raise ValueError(f'Work order {wo_id} has no schedulable operations')

    start_day = date.fromisoformat(start_from) if start_from else date.today()
    horizon_end = start_day + timedelta(days=MAX_HORIZON_DAYS)

    wc_ids = {o['workcenter_id'] for o in schedulable if o['workcenter_id']}
    calendars = {
        wc_id: _load_workcenter_calendar(conn, wc_id, start_day, horizon_end)
        for wc_id in wc_ids
    }
    booked = {
        wc_id: get_booked_hours_by_day(conn, wc_id, start_day, horizon_end, exclude_wo_id=wo_id)
        for wc_id in wc_ids
    }

    cursor_day = start_day
    not_before = None  # previous operation's actual finish — see _pack_forward
    results = []
    for op in schedulable:
        wc_id = op['workcenter_id']
        hours = op['std_hours'] or 0.0
        if wc_id is None:
            start_dt = _hour_to_datetime(cursor_day, DEFAULT_WORKDAY_START_HOUR)
            if not_before is not None and start_dt < not_before:
                start_dt = not_before
            end_dt = start_dt + timedelta(hours=max(hours, MIN_OPERATION_HOURS))
        else:
            cal = calendars[wc_id]
            start_dt, end_dt = _pack_forward(
                hours, cursor_day, lambda d, cal=cal: cal.get(d, 0.0), booked[wc_id],
                not_before=not_before,
            )
        reschedule_operation(conn, op['id'], _iso_z(start_dt), _iso_z(end_dt))
        results.append({
            'id': op['id'], 'operation_name': op['operation_name'],
            'workcenter_id': wc_id, 'workcenter_name': op.get('workcenter_name'),
            'scheduled_start': _iso_z(start_dt), 'scheduled_end': _iso_z(end_dt),
        })
        cursor_day = end_dt.date()
        not_before = end_dt

    return {'operations': results, 'computed_end_date': results[-1]['scheduled_end'][:10]}


def backward_schedule_wo(conn, wo_id, due_date=None):
    """Schedule every non-completed/non-skipped operation of a WO
    backward from due_date (default: the WO's own due_date — raises
    ValueError if neither is available), in REVERSE operation_seq order.
    Persists via reschedule_operation (does not commit; caller commits).

    Returns {'operations': [...] (restored to seq order), 'at_risk': True
    if the computed start falls before today (not enough combined
    capacity + lead time to hit the due date), 'computed_start_date'}.
    """
    ops = get_wo_operations(conn, wo_id)
    schedulable = [o for o in ops if o['status'] not in ('completed', 'skipped')]
    if not schedulable:
        raise ValueError(f'Work order {wo_id} has no schedulable operations')

    if due_date is None:
        wo = get_wo(conn, wo_id)
        due_date = wo.get('due_date') if wo else None
        if not due_date:
            raise ValueError(
                'No due date available — pass due_date or set the WO due date first'
            )

    end_day = date.fromisoformat(str(due_date)[:10])
    horizon_start = end_day - timedelta(days=MAX_HORIZON_DAYS)

    wc_ids = {o['workcenter_id'] for o in schedulable if o['workcenter_id']}
    calendars = {
        wc_id: _load_workcenter_calendar(conn, wc_id, horizon_start, end_day)
        for wc_id in wc_ids
    }
    booked = {
        wc_id: get_booked_hours_by_day(conn, wc_id, horizon_start, end_day, exclude_wo_id=wo_id)
        for wc_id in wc_ids
    }

    cursor_day = end_day
    not_after = None  # next operation's actual start — see _pack_backward
    results = []
    for op in reversed(schedulable):
        wc_id = op['workcenter_id']
        hours = max(op['std_hours'] or 0.0, MIN_OPERATION_HOURS)
        if wc_id is None:
            end_dt = _hour_to_datetime(cursor_day, DEFAULT_WORKDAY_START_HOUR + hours)
            if not_after is not None and end_dt > not_after:
                end_dt = not_after
            start_dt = end_dt - timedelta(hours=hours)
        else:
            cal = calendars[wc_id]
            start_dt, end_dt = _pack_backward(
                hours, cursor_day, lambda d, cal=cal: cal.get(d, 0.0), booked[wc_id],
                not_after=not_after,
            )
        reschedule_operation(conn, op['id'], _iso_z(start_dt), _iso_z(end_dt))
        results.append({
            'id': op['id'], 'operation_name': op['operation_name'],
            'workcenter_id': wc_id, 'workcenter_name': op.get('workcenter_name'),
            'scheduled_start': _iso_z(start_dt), 'scheduled_end': _iso_z(end_dt),
        })
        cursor_day = start_dt.date()
        not_after = start_dt

    results.reverse()
    computed_start_date = results[0]['scheduled_start'][:10]
    at_risk = date.fromisoformat(computed_start_date) < date.today()
    return {
        'operations': results, 'at_risk': at_risk,
        'computed_start_date': computed_start_date,
    }


# ---------------------------------------------------------------------------
# Capacity check / bottlenecks / load leveling
# ---------------------------------------------------------------------------

def get_capacity_check(conn, date_from, date_to):
    """Per active workcenter, per day in [date_from, date_to] (ISO date
    strings): booked vs. available hours. Returns
    [{workcenter_id, workcenter_name, days: [{date, available, booked,
    pct, over_capacity}]}]."""
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)
    result = []
    for wc in list_workcenters(conn, active_only=True):
        cal = _load_workcenter_calendar(conn, wc['id'], d_from, d_to)
        booked = get_booked_hours_by_day(conn, wc['id'], d_from, d_to)
        days = []
        d = d_from
        while d <= d_to:
            avail = cal.get(d, 0.0)
            used = booked.get(d, 0.0)
            pct = (used / avail * 100.0) if avail > 0 else (100.0 if used > 0 else 0.0)
            days.append({
                'date': d.isoformat(), 'available': avail, 'booked': used,
                'pct': pct, 'over_capacity': used > avail + 1e-9,
            })
            d += timedelta(days=1)
        result.append({
            'workcenter_id': wc['id'], 'workcenter_name': wc['name'], 'days': days,
        })
    return result


def identify_bottlenecks(conn, date_from, date_to):
    """Active workcenters ranked by utilization % over the horizon
    (total booked / total available), descending — the workcenter(s) at
    the top, especially any over 100%, are constraining throughput."""
    result = []
    for c in get_capacity_check(conn, date_from, date_to):
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


def _ops_touching_workcenter_day(conn, workcenter_id, day):
    rows = conn.execute(
        "SELECT op.id, op.operation_name, op.std_hours, "
        "op.scheduled_start, op.scheduled_end, wo.wo_number, wo.id AS wo_id "
        "FROM wo_operation op JOIN work_order wo ON wo.id = op.wo_id "
        "WHERE op.workcenter_id = %s AND op.status IN ('pending', 'in_progress') "
        "AND op.scheduled_start IS NOT NULL AND op.scheduled_end IS NOT NULL "
        "AND op.scheduled_start::date <= %s AND op.scheduled_end::date >= %s "
        "ORDER BY op.scheduled_start DESC",
        (workcenter_id, day, day),
    ).fetchall()
    return [dict(r) for r in rows]


def suggest_load_leveling(conn, date_from, date_to, search_horizon_days=60):
    """For each over-capacity (workcenter, day), suggest delaying the
    latest-starting pending operation touching that day until the
    workcenter has enough slack. A greedy heuristic, not an optimizer —
    one suggestion per overloaded day; apply_load_leveling_suggestion
    persists a chosen suggestion.

    Returns [{workcenter_id, workcenter_name, date, over_by_hours, op_id,
    operation_name, wo_number, delay_to_date, delay_days}]. delay_to_date
    is None if no slack is found within search_horizon_days."""
    suggestions = []
    for c in get_capacity_check(conn, date_from, date_to):
        wc_id = c['workcenter_id']
        for day_info in c['days']:
            if not day_info['over_capacity']:
                continue
            day = date.fromisoformat(day_info['date'])
            candidates = _ops_touching_workcenter_day(conn, wc_id, day)
            if not candidates:
                continue
            op = candidates[0]
            start_d = _to_date(op['scheduled_start'])
            end_d = _to_date(op['scheduled_end'])
            span_days = max(1, (end_d - start_d).days + 1)
            per_day_hours = (op['std_hours'] or 0.0) / span_days

            probe_from = day + timedelta(days=1)
            probe_to = probe_from + timedelta(days=search_horizon_days)
            probe_cal = _load_workcenter_calendar(conn, wc_id, probe_from, probe_to)
            probe_booked = get_booked_hours_by_day(conn, wc_id, probe_from, probe_to)
            found = None
            probe = probe_from
            while probe <= probe_to:
                free = probe_cal.get(probe, 0.0) - probe_booked.get(probe, 0.0)
                if free >= per_day_hours:
                    found = probe
                    break
                probe += timedelta(days=1)

            suggestions.append({
                'workcenter_id': wc_id, 'workcenter_name': c['workcenter_name'],
                'date': day_info['date'], 'over_by_hours': day_info['booked'] - day_info['available'],
                'op_id': op['id'], 'operation_name': op['operation_name'],
                'wo_number': op['wo_number'],
                'delay_to_date': found.isoformat() if found else None,
                'delay_days': (found - day).days if found else None,
            })
    return suggestions


def apply_load_leveling_suggestion(conn, op_id, delay_days):
    """Shift one operation's scheduled window forward by delay_days
    (whole days), preserving its duration. Does not commit. Returns True
    if a row was updated (see reschedule_operation's guards)."""
    row = conn.execute(
        "SELECT scheduled_start, scheduled_end FROM wo_operation WHERE id = %s",
        (op_id,),
    ).fetchone()
    if not row or not row['scheduled_start'] or not row['scheduled_end']:
        raise ValueError(f'Operation {op_id} has no scheduled window to shift')
    delta = timedelta(days=delay_days)
    new_start = row['scheduled_start'] + delta
    new_end = row['scheduled_end'] + delta
    return reschedule_operation(conn, op_id, new_start.isoformat(), new_end.isoformat())
