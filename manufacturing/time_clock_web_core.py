"""Qt-free time clock extended data layer.

Adds overtime analysis and schedule views on top of the existing
time_clock_core.py functions.

All queries use the existing ``time_clock`` table:
  id, people_id, clock_in (TEXT), clock_out (TEXT),
  hours_worked (REAL), notes (TEXT), created_by (TEXT)
"""

from datetime import datetime, timedelta
from .time_clock_core import compute_hours, fmt_hours, _FMT

# Standard work hours per day / per week
STANDARD_DAILY_HOURS = 8.0
STANDARD_WEEKLY_HOURS = 40.0
OT_THRESHOLD_DAILY = 8.0    # hours/day beyond which = daily OT
OT_THRESHOLD_WEEKLY = 40.0  # hours/week beyond which = weekly OT


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.strptime(s, _FMT)


def _week_bounds(ref: datetime) -> tuple[str, str]:
    """Monday 00:00 – Sunday 23:59:59 containing ``ref``."""
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')


def _week_start(date_str: str) -> str:
    """Return the Monday of the week containing ``date_str`` (YYYY-MM-DD)."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime('%Y-%m-%d')


# ---------------------------------------------------------------------------
# Overtime computation
# ---------------------------------------------------------------------------

def compute_ot_for_entries(entries: list[dict]) -> dict:
    """Aggregate a list of enriched time-clock entries into OT metrics.

    ``entries`` must be pre-enriched (i.e. have 'hours', 'in_progress').
    Groups by calendar day, computes daily OT (> 8 h/day) and weekly
    OT (> 40 h/week).

    Returns:
        {
          'total_hours': float,
          'total_hours_fmt': str,
          'ot_hours': float,          # total overtime
          'ot_hours_fmt': str,
          'daily_ot': float,
          'weekly_ot': float,
          'by_day': list[{date, hours, ot_hours, ...}],
          'by_week': list[{week_start, hours, ot_hours}],
        }
    """
    by_day: dict[str, float] = {}
    by_week: dict[str, float] = {}

    for e in entries:
        day = e['clock_in'][:10] if e.get('clock_in') else ''
        if not day:
            continue
        h = e.get('hours', 0.0)
        by_day[day] = by_day.get(day, 0.0) + h
        week = _week_start(day)
        by_week[week] = by_week.get(week, 0.0) + h

    total = sum(by_day.values())
    daily_ot = sum(max(0.0, h - OT_THRESHOLD_DAILY) for h in by_day.values())
    weekly_ot = sum(max(0.0, h - OT_THRESHOLD_WEEKLY) for h in by_week.values())
    ot = max(daily_ot, weekly_ot)

    day_rows = sorted(
        [
            {
                'date': d,
                'hours': h,
                'hours_fmt': fmt_hours(h),
                'ot_hours': max(0.0, h - OT_THRESHOLD_DAILY),
                'ot_hours_fmt': fmt_hours(max(0.0, h - OT_THRESHOLD_DAILY)),
            }
            for d, h in by_day.items()
        ],
        key=lambda r: r['date'],
        reverse=True,
    )
    week_rows = sorted(
        [
            {
                'week_start': w,
                'hours': h,
                'hours_fmt': fmt_hours(h),
                'ot_hours': max(0.0, h - OT_THRESHOLD_WEEKLY),
                'ot_hours_fmt': fmt_hours(max(0.0, h - OT_THRESHOLD_WEEKLY)),
            }
            for w, h in by_week.items()
        ],
        key=lambda r: r['week_start'],
        reverse=True,
    )

    return {
        'total_hours': total,
        'total_hours_fmt': fmt_hours(total),
        'ot_hours': ot,
        'ot_hours_fmt': fmt_hours(ot),
        'daily_ot': daily_ot,
        'weekly_ot': weekly_ot,
        'by_day': day_rows,
        'by_week': week_rows,
    }


def get_ot_report(conn, people_id: int,
                  date_from: str | None = None,
                  date_to: str | None = None) -> dict:
    """Return an OT report for a single employee.

    ``date_from`` / ``date_to`` default to the current pay period (1st of
    month through today).
    """
    today = datetime.now()
    if not date_from:
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    conds = ['tc.people_id = %s',
             "SUBSTR(tc.clock_in, 1, 10) >= %s",
             "SUBSTR(tc.clock_in, 1, 10) <= %s"]
    params: list = [people_id, date_from, date_to]

    rows = conn.execute(
        "SELECT tc.id, tc.people_id, tc.clock_in, tc.clock_out, "
        "p.first_name, p.last_name "
        "FROM time_clock tc "
        "JOIN people p ON p.id = tc.people_id "
        "WHERE " + " AND ".join(conds) + " ORDER BY tc.clock_in DESC",
        params,
    ).fetchall()

    entries = []
    for r in rows:
        d = dict(r)
        d['hours'] = compute_hours(d['clock_in'], d.get('clock_out'))
        entries.append(d)

    result = compute_ot_for_entries(entries)
    result['date_from'] = date_from
    result['date_to'] = date_to
    result['entries'] = entries
    return result


def get_ot_report_all(conn,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      dept_id: int | None = None) -> list[dict]:
    """OT summary for all employees (or one dept), sorted by OT descending.

    Returns list of dicts:
      {people_id, first_name, last_name, dept_name,
       total_hours, total_hours_fmt, ot_hours, ot_hours_fmt}
    """
    today = datetime.now()
    if not date_from:
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    conds = [
        "SUBSTR(tc.clock_in, 1, 10) >= %s",
        "SUBSTR(tc.clock_in, 1, 10) <= %s",
    ]
    params: list = [date_from, date_to]
    if dept_id:
        conds.append("p.dept_id = %s")
        params.append(dept_id)

    rows = conn.execute(
        "SELECT tc.people_id, p.first_name, p.last_name, "
        "COALESCE(d.dept_name,'') AS dept_name, "
        "tc.clock_in, tc.clock_out "
        "FROM time_clock tc "
        "JOIN people p ON p.id = tc.people_id "
        "LEFT JOIN dept d ON d.dept_id = p.dept_id "
        "WHERE " + " AND ".join(conds) +
        " ORDER BY tc.people_id, tc.clock_in",
        params,
    ).fetchall()

    # Group by person
    people: dict[int, dict] = {}
    for r in rows:
        pid = r['people_id']
        if pid not in people:
            people[pid] = {
                'people_id': pid,
                'first_name': r['first_name'],
                'last_name': r['last_name'],
                'dept_name': r['dept_name'],
                'entries': [],
            }
        h = compute_hours(r['clock_in'], r.get('clock_out'))
        people[pid]['entries'].append({
            'clock_in': r['clock_in'],
            'clock_out': r.get('clock_out'),
            'hours': h,
        })

    results = []
    for pid, p in people.items():
        ot_data = compute_ot_for_entries(p['entries'])
        results.append({
            'people_id': pid,
            'first_name': p['first_name'],
            'last_name': p['last_name'],
            'dept_name': p['dept_name'],
            'total_hours': ot_data['total_hours'],
            'total_hours_fmt': ot_data['total_hours_fmt'],
            'ot_hours': ot_data['ot_hours'],
            'ot_hours_fmt': ot_data['ot_hours_fmt'],
        })

    results.sort(key=lambda r: r['ot_hours'], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Schedule / shift stubs
# ---------------------------------------------------------------------------

def get_schedule_summary(conn,
                         date_from: str | None = None,
                         date_to: str | None = None) -> dict:
    """Return attendance/hours summary for a date range (schedule view).

    Because this application does not yet have a dedicated shift-planning
    table, the schedule view is derived from actual time_clock punch data.

    Returns:
        {
          'date_from': str,
          'date_to': str,
          'total_present': int,
          'total_entries': int,
          'avg_daily_hours': float,
          'avg_daily_hours_fmt': str,
          'by_day': list[{date, present, entries, total_hours, total_hours_fmt}]
        }
    """
    today = datetime.now()
    if not date_from:
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        date_from = monday.strftime('%Y-%m-%d')
        date_to = sunday.strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    rows = conn.execute(
        "SELECT tc.people_id, tc.clock_in, tc.clock_out "
        "FROM time_clock tc "
        "WHERE SUBSTR(tc.clock_in, 1, 10) >= %s "
        "  AND SUBSTR(tc.clock_in, 1, 10) <= %s "
        "ORDER BY tc.clock_in",
        (date_from, date_to),
    ).fetchall()

    by_day: dict[str, dict] = {}
    for r in rows:
        day = r['clock_in'][:10]
        if day not in by_day:
            by_day[day] = {'people': set(), 'total_hours': 0.0}
        by_day[day]['people'].add(r['people_id'])
        by_day[day]['total_hours'] += compute_hours(r['clock_in'], r.get('clock_out'))

    day_rows = []
    for day in sorted(by_day.keys()):
        d = by_day[day]
        n_present = len(d['people'])
        total_h = d['total_hours']
        day_rows.append({
            'date': day,
            'present': n_present,
            'total_hours': total_h,
            'total_hours_fmt': fmt_hours(total_h),
            'avg_hours': total_h / n_present if n_present else 0.0,
            'avg_hours_fmt': fmt_hours(total_h / n_present) if n_present else '0:00',
        })

    total_present = sum(r['present'] for r in day_rows)
    total_entries_h = sum(r['total_hours'] for r in day_rows)
    n_days = len(day_rows)
    avg_daily = total_entries_h / n_days if n_days else 0.0

    return {
        'date_from': date_from,
        'date_to': date_to,
        'total_present': total_present,
        'total_entries': sum(len(by_day[d]['people']) for d in by_day),
        'avg_daily_hours': avg_daily,
        'avg_daily_hours_fmt': fmt_hours(avg_daily),
        'by_day': day_rows,
    }
