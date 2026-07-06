"""oee_core.py — Qt-free Overall Equipment Effectiveness (OEE) calculations.

OEE = Availability x Performance x Quality, computed per workcenter (the
production-side resource tracked by routing_core), not per maint_equipment —
the two tables have no foreign-key link, only a best-effort name match used
here to fold maintenance downtime into Availability. See
COMPETITIVE_GAP_ANALYSIS.md P1-C.

  Availability = (scheduled_hours - downtime_hours) / scheduled_hours
    scheduled_hours = workcenter.capacity_hours_per_day x calendar days in period
    downtime_hours  = SUM(maint_downtime.hours) where equipment name matches
                       the workcenter name (0 if no match)
  Performance  = std_hours / actual_hours, from completed wo_operation rows
                 at this workcenter in the period
  Quality      = (total_qty - total_scrap) / total_qty
    total_qty/total_scrap summed from each completed wo_operation's parent
    work_order.quantity and the operation's scrap_qty (a WO routed through
    the same workcenter more than once will count its quantity more than
    once — an accepted approximation given no per-operation output field)

Each ratio is clamped to [0, 1]; an empty period (no completed operations)
yields 0.0 for performance and therefore 0.0 overall, matching the
convention that "no run time" is 0% OEE for that period.
"""

import datetime


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def _downtime_hours(conn, equipment_name, start_date, end_date):
    row = conn.execute("""
        SELECT COALESCE(SUM(
            CASE WHEN hours ~ E'^[0-9]+(\\.[0-9]+)?$' THEN hours::real ELSE 0 END
        ), 0) AS total_hours
        FROM maint_downtime
        WHERE equipment ILIKE %s
          AND down_date BETWEEN %s AND %s
    """, (equipment_name, start_date, end_date)).fetchone()
    return float(row['total_hours']) if row else 0.0


def _period_days(start_date, end_date):
    s = datetime.date.fromisoformat(str(start_date))
    e = datetime.date.fromisoformat(str(end_date))
    return max((e - s).days + 1, 1)


def _oee_from_totals(capacity_hours_per_day, days, downtime_hours,
                      std_hours, actual_hours, total_qty, total_scrap):
    scheduled_hours = capacity_hours_per_day * days
    availability = (
        _clamp((scheduled_hours - downtime_hours) / scheduled_hours)
        if scheduled_hours > 0 else 0.0
    )
    performance = _clamp(std_hours / actual_hours) if actual_hours > 0 else 0.0
    quality = _clamp((total_qty - total_scrap) / total_qty) if total_qty > 0 else 1.0
    oee = availability * performance * quality
    return {
        'availability_pct': round(availability * 100, 1),
        'performance_pct': round(performance * 100, 1),
        'quality_pct': round(quality * 100, 1),
        'oee_pct': round(oee * 100, 1),
        'scheduled_hours': round(scheduled_hours, 1),
        'downtime_hours': round(downtime_hours, 1),
        'actual_hours': round(actual_hours, 1),
        'total_qty': total_qty,
        'total_scrap': total_scrap,
    }


def _workcenter_op_totals(conn, workcenter_id, start_date, end_date):
    """Sum std/actual hours and qty/scrap from completed ops in the period."""
    row = conn.execute("""
        SELECT COALESCE(SUM(op.std_hours), 0)    AS total_std_hours,
               COALESCE(SUM(op.actual_hours), 0)  AS total_actual_hours,
               COALESCE(SUM(wo.quantity), 0)      AS total_qty,
               COALESCE(SUM(op.scrap_qty), 0)     AS total_scrap
        FROM wo_operation op
        JOIN work_order wo ON wo.id = op.wo_id
        WHERE op.workcenter_id = %s
          AND op.status = 'completed'
          AND op.completed_at::date BETWEEN %s AND %s
    """, (workcenter_id, start_date, end_date)).fetchone()
    return (float(row['total_std_hours']), float(row['total_actual_hours']),
            float(row['total_qty']), float(row['total_scrap']))


def get_workcenter_oee(conn, workcenter_id, start_date, end_date):
    """Return the OEE breakdown for one workcenter over ``[start_date, end_date]``."""
    wc = conn.execute(
        "SELECT id, name, capacity_hours_per_day FROM workcenter WHERE id = %s",
        (workcenter_id,),
    ).fetchone()
    if not wc:
        return None

    std_hours, actual_hours, total_qty, total_scrap = _workcenter_op_totals(
        conn, workcenter_id, start_date, end_date)
    downtime_hours = _downtime_hours(conn, wc['name'], start_date, end_date)
    days = _period_days(start_date, end_date)

    result = _oee_from_totals(
        wc['capacity_hours_per_day'], days, downtime_hours,
        std_hours, actual_hours, total_qty, total_scrap,
    )
    result['workcenter_id'] = wc['id']
    result['workcenter_name'] = wc['name']
    return result


def list_workcenter_oee(conn, start_date, end_date):
    """Return the OEE breakdown for every active workcenter over the period."""
    workcenters = conn.execute(
        "SELECT id FROM workcenter WHERE is_active ORDER BY name"
    ).fetchall()
    return [
        get_workcenter_oee(conn, wc['id'], start_date, end_date)
        for wc in workcenters
    ]


def get_overall_oee(conn, start_date, end_date):
    """Return OEE aggregated across every active workcenter for one period.

    Sums hours/qty/downtime across workcenters first, then applies the OEE
    formula once (rather than averaging per-workcenter percentages), so
    workcenters with more throughput are weighted accordingly.
    """
    workcenters = conn.execute(
        "SELECT id, name, capacity_hours_per_day FROM workcenter WHERE is_active"
    ).fetchall()
    if not workcenters:
        return _oee_from_totals(0, _period_days(start_date, end_date), 0, 0, 0, 0, 0)

    days = _period_days(start_date, end_date)
    total_capacity = total_downtime = 0.0
    total_std = total_actual = total_qty = total_scrap = 0.0
    for wc in workcenters:
        std_hours, actual_hours, qty, scrap = _workcenter_op_totals(
            conn, wc['id'], start_date, end_date)
        total_capacity += wc['capacity_hours_per_day'] * days
        total_downtime += _downtime_hours(conn, wc['name'], start_date, end_date)
        total_std += std_hours
        total_actual += actual_hours
        total_qty += qty
        total_scrap += scrap

    return _oee_from_totals(
        total_capacity / days, days, total_downtime,
        total_std, total_actual, total_qty, total_scrap,
    )


def get_oee_trend(conn, end_date=None, weeks=8):
    """Return overall (all-workcenter) OEE for each of the last ``weeks`` weeks."""
    end = (datetime.date.fromisoformat(str(end_date)) if end_date
           else datetime.date.today())

    trend = []
    for i in range(weeks - 1, -1, -1):
        week_end = end - datetime.timedelta(days=7 * i)
        week_start = week_end - datetime.timedelta(days=6)
        week = get_overall_oee(conn, week_start.isoformat(), week_end.isoformat())
        trend.append({
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'oee_pct': week['oee_pct'],
        })
    return trend
