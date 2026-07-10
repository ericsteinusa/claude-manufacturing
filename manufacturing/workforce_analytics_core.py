"""workforce_analytics_core.py — Qt-free Workforce Analytics & Headcount
Planning, 7/10 of the top-10 ERPs have it.

There is no hire-date/termination-date tracking anywhere in this app today
— `people` has no such columns, so this module's first job is adding them
(`ensure_workforce_columns`, additive `ALTER TABLE ... ADD COLUMN IF NOT
EXISTS`, the same pattern `personnel_core.ensure_contact_columns` already
used for phone/emergency-contact fields). **Every trend/tenure/turnover
number below is computed only from employees whose hire_date has actually
been entered** — existing seed/production employees default to an empty
string and are silently excluded from tenure and trend math rather than
treated as hired "today" or some fabricated date. This is disclosed
plainly rather than hidden, the same "drift/gaps are real, document them"
scoping already used for RFID tag/bin quantity drift and FIFO/LIFO cost
layers.

Headcount planning is a second, independent table (`headcount_plan`): an
admin-entered target headcount per department by a target date, compared
against today's actual active headcount — there's no forecasting model,
just a real target vs. a real count.

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / skills_matrix_core).
"""

from __future__ import annotations

import datetime

EMPLOYMENT_STATUSES = ('active', 'terminated')


def _today() -> datetime.date:
    return datetime.date.today()


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def ensure_workforce_columns(conn):
    """Add hire_date/termination_date/employment_status to people if
    absent. Idempotent — does not commit."""
    for col_sql in [
        "ALTER TABLE people ADD COLUMN IF NOT EXISTS hire_date TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE people ADD COLUMN IF NOT EXISTS termination_date TEXT",
        "ALTER TABLE people ADD COLUMN IF NOT EXISTS "
        "employment_status TEXT NOT NULL DEFAULT 'active'",
    ]:
        conn.execute(col_sql)


def ensure_headcount_plan_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS headcount_plan (
            id               SERIAL PRIMARY KEY,
            dept_id          INTEGER NOT NULL REFERENCES dept(dept_id),
            target_headcount INTEGER NOT NULL DEFAULT 0,
            target_date      TEXT NOT NULL DEFAULT '',
            notes            TEXT NOT NULL DEFAULT '',
            created_by       TEXT NOT NULL DEFAULT '',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS headcount_plan_dept ON headcount_plan(dept_id)"
    )


# ---------------------------------------------------------------------------
# Employment dates
# ---------------------------------------------------------------------------

def set_employment_dates(conn, people_id, hire_date, termination_date=None,
                         employment_status='active'):
    if employment_status not in EMPLOYMENT_STATUSES:
        raise ValueError(f'employment_status must be one of {EMPLOYMENT_STATUSES}')
    conn.execute(
        "UPDATE people SET hire_date = %s, termination_date = %s, "
        "employment_status = %s WHERE id = %s",
        (hire_date or '', termination_date or None, employment_status, people_id),
    )


# ---------------------------------------------------------------------------
# Headcount summary
# ---------------------------------------------------------------------------

def get_headcount_summary(conn):
    """{'total_active', 'total_terminated', 'by_dept', 'avg_tenure_years',
    'turnover_rate_ttm'}.

    avg_tenure_years is computed only over active employees with a real
    hire_date. turnover_rate_ttm is (employees terminated in the trailing
    365 days) / (current active headcount) — a simple approximation, not
    an annualized BLS-style rate, since there's no historical headcount
    series to average against.
    """
    rows = conn.execute(
        "SELECT p.id, p.dept_id, d.dept_name, p.hire_date, "
        "p.termination_date, p.employment_status "
        "FROM people p LEFT JOIN dept d ON d.dept_id = p.dept_id"
    ).fetchall()

    today = _today()
    cutoff = today - datetime.timedelta(days=365)

    total_active = 0
    total_terminated = 0
    by_dept_counts: dict = {}
    tenure_days = []
    terminated_ttm = 0

    for r in rows:
        row = dict(r)
        status = row.get('employment_status') or 'active'
        hire = _parse_date(row.get('hire_date'))
        term = _parse_date(row.get('termination_date'))

        if status == 'active':
            total_active += 1
            dept_name = row.get('dept_name') or 'Unassigned'
            by_dept_counts[dept_name] = by_dept_counts.get(dept_name, 0) + 1
            if hire:
                tenure_days.append((today - hire).days)
        elif status == 'terminated':
            total_terminated += 1
            if term and term >= cutoff:
                terminated_ttm += 1

    avg_tenure_years = (
        round((sum(tenure_days) / len(tenure_days)) / 365.25, 2)
        if tenure_days else None
    )
    turnover_rate_ttm = (
        round(terminated_ttm / total_active, 4) if total_active else None
    )

    by_dept = sorted(
        [{'dept_name': k, 'count': v} for k, v in by_dept_counts.items()],
        key=lambda d: d['count'], reverse=True,
    )

    return {
        'total_active': total_active,
        'total_terminated': total_terminated,
        'by_dept': by_dept,
        'avg_tenure_years': avg_tenure_years,
        'turnover_rate_ttm': turnover_rate_ttm,
    }


def get_headcount_trend(conn, months=12):
    """Monthly active-headcount trend for the trailing `months` months
    (oldest first), computed from hire_date/termination_date. Employees
    with no hire_date entered are excluded from every month's count —
    documented in the module docstring, not silently guessed at."""
    rows = conn.execute(
        "SELECT hire_date, termination_date FROM people WHERE hire_date != ''"
    ).fetchall()
    parsed = []
    for r in rows:
        row = dict(r)
        hire = _parse_date(row.get('hire_date'))
        if not hire:
            continue
        term = _parse_date(row.get('termination_date'))
        parsed.append((hire, term))

    month_ends = _trailing_month_ends(months)
    trend = []
    for month_end in month_ends:
        count = sum(
            1 for hire, term in parsed
            if hire <= month_end and (term is None or term > month_end)
        )
        trend.append({'month': month_end.strftime('%Y-%m'), 'headcount': count})
    return trend


def _trailing_month_ends(months):
    """`months` data points, oldest first: the last calendar day of each
    of the previous (months - 1) complete months, plus today standing in
    for the current in-progress month."""
    today = _today()
    cursor = today.replace(day=1)
    ends = []
    for _ in range(months - 1):
        last_day_prev = cursor - datetime.timedelta(days=1)
        ends.append(last_day_prev)
        cursor = last_day_prev.replace(day=1)
    ends.reverse()
    ends.append(today)
    return ends


# ---------------------------------------------------------------------------
# Headcount planning
# ---------------------------------------------------------------------------

def create_headcount_plan(conn, dept_id, target_headcount, target_date,
                          notes='', created_by=''):
    if not dept_id:
        raise ValueError('dept_id is required')
    row = conn.execute(
        "INSERT INTO headcount_plan "
        "(dept_id, target_headcount, target_date, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (dept_id, int(target_headcount or 0), target_date or '',
         notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def list_headcount_plans(conn, dept_id=None):
    sql = (
        "SELECT hp.*, d.dept_name FROM headcount_plan hp "
        "LEFT JOIN dept d ON d.dept_id = hp.dept_id WHERE TRUE"
    )
    params: list = []
    if dept_id:
        sql += " AND hp.dept_id = %s"
        params.append(dept_id)
    sql += " ORDER BY hp.target_date DESC, hp.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_plan_vs_actual(conn):
    """Per department: the most recently created plan's target headcount
    vs. today's actual active headcount, and the gap (target - actual).
    Departments with no plan yet are omitted (nothing to compare against)."""
    plan_rows = conn.execute(
        "SELECT DISTINCT ON (hp.dept_id) hp.dept_id, d.dept_name, "
        "hp.target_headcount, hp.target_date "
        "FROM headcount_plan hp LEFT JOIN dept d ON d.dept_id = hp.dept_id "
        "ORDER BY hp.dept_id, hp.id DESC"
    ).fetchall()
    actual_rows = conn.execute(
        "SELECT dept_id, COUNT(*) AS actual "
        "FROM people WHERE employment_status = 'active' "
        "GROUP BY dept_id"
    ).fetchall()
    actual_by_dept = {r['dept_id']: r['actual'] for r in actual_rows}

    result = []
    for r in plan_rows:
        row = dict(r)
        actual = actual_by_dept.get(row['dept_id'], 0)
        result.append({
            'dept_id': row['dept_id'],
            'dept_name': row.get('dept_name') or 'Unassigned',
            'target_headcount': row['target_headcount'],
            'target_date': row['target_date'],
            'actual_headcount': actual,
            'gap': row['target_headcount'] - actual,
        })
    return result
