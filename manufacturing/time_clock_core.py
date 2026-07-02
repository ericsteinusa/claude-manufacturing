"""Qt-free time clock data layer.

Uses the existing ``time_clock`` table:
  id, people_id, clock_in (TEXT), clock_out (TEXT),
  hours_worked (REAL), notes (TEXT), created_by (TEXT)

Dates and times are stored as ISO TEXT strings ('YYYY-MM-DD HH:MM:SS')
so they work on any Postgres version without timezone conversion.
"""
from collections import OrderedDict
from datetime import datetime, timedelta

_FMT = '%Y-%m-%d %H:%M:%S'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime(_FMT)


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.strptime(s, _FMT)


def compute_hours(clock_in: str, clock_out: str | None = None) -> float:
    """Hours between clock_in and clock_out (or now if still open)."""
    t_in = _parse(clock_in)
    if t_in is None:
        return 0.0
    t_out = (_parse(clock_out) if clock_out else None) or datetime.now()
    return max(0.0, (t_out - t_in).total_seconds() / 3600)


def fmt_hours(h: float) -> str:
    """Format decimal hours as 'H:MM'."""
    total = int(h * 60)
    return f"{total // 60}:{total % 60:02d}"


def get_period_dates(period: str) -> tuple[str, str]:
    """Return (date_from, date_to) for 'today', 'week', or 'month'."""
    today = datetime.now()
    if period == 'week':
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')
    if period == 'month':
        first = today.replace(day=1)
        return first.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    d = today.strftime('%Y-%m-%d')
    return d, d


# ---------------------------------------------------------------------------
# Clock in / out
# ---------------------------------------------------------------------------

def get_current_entry(conn, people_id: int):
    """Return the open entry (no clock_out) for this person, or None."""
    row = conn.execute(
        "SELECT * FROM time_clock WHERE people_id = %s AND clock_out IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (people_id,)
    ).fetchone()
    return dict(row) if row else None


def clock_in(conn, people_id: int, notes: str = '', created_by=None) -> int:
    """Insert a new clock-in record. Does not commit. Returns new id."""
    row = conn.execute(
        "INSERT INTO time_clock (people_id, clock_in, notes, created_by) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (people_id, _now(), notes or '', created_by)
    ).fetchone()
    return row['id']


def clock_out_entry(conn, entry_id: int):
    """Set clock_out and hours_worked on an open entry. Does not commit."""
    row = conn.execute(
        "SELECT clock_in FROM time_clock WHERE id = %s", (entry_id,)
    ).fetchone()
    if not row:
        return
    now = _now()
    hours = compute_hours(row['clock_in'], now)
    conn.execute(
        "UPDATE time_clock SET clock_out = %s, hours_worked = %s WHERE id = %s",
        (now, round(hours, 4), entry_id)
    )


# ---------------------------------------------------------------------------
# Entry lists
# ---------------------------------------------------------------------------

def _enrich(d: dict) -> dict:
    d['hours'] = compute_hours(d['clock_in'], d.get('clock_out'))
    d['hours_fmt'] = fmt_hours(d['hours'])
    d['in_progress'] = d.get('clock_out') is None
    return d


def list_entries(conn, people_id: int,
                 date_from: str | None = None,
                 date_to: str | None = None) -> list[dict]:
    """Return clock entries for one person, optionally filtered by date range."""
    conds = ["people_id = %s"]
    params: list = [people_id]
    if date_from:
        conds.append("SUBSTR(clock_in, 1, 10) >= %s")
        params.append(date_from)
    if date_to:
        conds.append("SUBSTR(clock_in, 1, 10) <= %s")
        params.append(date_to)
    rows = conn.execute(
        "SELECT * FROM time_clock WHERE " + " AND ".join(conds) +
        " ORDER BY clock_in DESC",
        params
    ).fetchall()
    return [_enrich(dict(r)) for r in rows]


def total_hours(entries: list[dict]) -> tuple[float, str]:
    """Sum hours across a list of enriched entries."""
    h = sum(e['hours'] for e in entries)
    return h, fmt_hours(h)


# ---------------------------------------------------------------------------
# Attendance (HR view)
# ---------------------------------------------------------------------------

def get_attendance(conn, date_str: str) -> list[dict]:
    """All people with their time_clock entries for a date (present and absent).

    People with empty first+last name are excluded (legacy blank rows).
    """
    rows = conn.execute("""
        SELECT p.id as people_id, p.first_name, p.last_name,
               p.dept_id, d.dept_name,
               tc.id as entry_id, tc.clock_in, tc.clock_out
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN time_clock tc
            ON tc.people_id = p.id
            AND SUBSTR(tc.clock_in, 1, 10) = %s
        WHERE (p.first_name != '' OR p.last_name != '')
        ORDER BY p.last_name, p.first_name, tc.clock_in
    """, (date_str,)).fetchall()

    people: dict = OrderedDict()
    for r in rows:
        pid = r['people_id']
        if pid not in people:
            people[pid] = {
                'people_id': pid,
                'first_name': r['first_name'],
                'last_name': r['last_name'],
                'dept_name': r['dept_name'] or '',
                'entries': [],
                'total_hours': 0.0,
                'total_hours_fmt': '0:00',
                'present': False,
            }
        if r['entry_id']:
            h = compute_hours(r['clock_in'], r['clock_out'])
            people[pid]['entries'].append({
                'entry_id': r['entry_id'],
                'clock_in': r['clock_in'],
                'clock_out': r['clock_out'],
                'hours_fmt': fmt_hours(h),
                'in_progress': r['clock_out'] is None,
            })
            people[pid]['total_hours'] += h
            people[pid]['present'] = True

    for p in people.values():
        p['total_hours_fmt'] = fmt_hours(p['total_hours'])

    return list(people.values())
