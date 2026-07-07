"""
predictive_maintenance_core.py — Qt-free Predictive Maintenance (P4-B).

MTBF/MTTR already exist ("Phase 6B", `maintenance_core.get_mtbf` /
`get_equipment_reliability_report`) but as a **period aggregate**:
``mtbf_hours = (period_hours - total_downtime_hours) / failure_count``,
derived from *counting* breakdown events and *summing* their hours over a
fixed window. That formula can't say "time since last failure" or trend
per equipment because it never looks at individual failure dates. This
module adds that: **rolling, interval-based MTBF** computed from the
actual gaps between consecutive 'Breakdown'-category ``maint_downtime``
records, which is also what "alert when interval since last failure
approaches MTBF x 0.8" and a maintenance risk score both need.

``get_mtbf``'s query is exact-SQL-pinned (``tests/test_phase6.py``
asserts ``"category = 'Breakdown'" in conn.last_sql``) — this module
doesn't modify it, it adds new queries using the same
``equipment ILIKE %s AND category = 'Breakdown'`` predicate to pull raw
dates instead of an aggregate.

Failure-probability is the standard exponential/Poisson-process
approximation for "probability of at least one failure in the next N
days" given only a mean interval: ``1 - exp(-N / mtbf_days)``. This is a
documented simplifying assumption (no failure-time-distribution fitting;
`math.exp` is stdlib, no new dependency) — reasonable when the only input
available is a mean interval, not full survival data.

There is no sensor/IoT concept anywhere in this codebase. The
vibration/temperature bullet is a manual/simulated substitute for real
hardware — a technician (or a future integration) logs readings against a
per-equipment/reading-type threshold; there is no actual sensor
connectivity, mirroring the documented-stub precedent used for P3-C's
Stripe integration.

Alerts here are computed live on every read, never persisted — matching
every other alert function in this codebase (`lot_core.get_expiry_alerts`,
`inventory_core.get_alert_counts`, `maintenance_core.get_pm_alerts`).

Every function taking ``conn`` takes an open connection; the caller owns
the transaction (same convention as demand_forecast_core / shop_floor_core).
"""

from __future__ import annotations

import math
from datetime import datetime, date

from .log_utils import get_logger
from .maintenance_core import list_equipment

log = get_logger(__name__)

SENSOR_READING_TYPES = ('vibration', 'temperature')

RISK_THRESHOLDS = {'low': 0.25, 'medium': 0.60}  # upper bound of each bucket


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_predictive_maintenance_tables(conn) -> None:
    """Create equipment_sensor_reading/threshold if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipment_sensor_reading (
            id           SERIAL PRIMARY KEY,
            equipment    TEXT NOT NULL,
            reading_type TEXT NOT NULL,
            value        REAL NOT NULL,
            unit         TEXT DEFAULT '',
            recorded_at  TEXT DEFAULT '',
            created_by   TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS equipment_sensor_threshold (
            id            SERIAL PRIMARY KEY,
            equipment     TEXT NOT NULL,
            reading_type  TEXT NOT NULL,
            warning_max   REAL NOT NULL,
            critical_max  REAL NOT NULL,
            UNIQUE (equipment, reading_type)
        )
    """)


# ---------------------------------------------------------------------------
# Rolling MTBF
# ---------------------------------------------------------------------------

def _breakdown_dates(conn, equipment: str, months: int = 24) -> list:
    """Ordered list of 'Breakdown'-category down_dates for one equipment,
    trailing `months`. Same predicate as the pinned get_mtbf, but returns
    individual dates instead of an aggregate."""
    rows = conn.execute("""
        SELECT down_date FROM maint_downtime
        WHERE equipment ILIKE %s
          AND category = 'Breakdown'
          AND down_date >= (CURRENT_DATE - (%s * INTERVAL '1 month'))::text
        ORDER BY down_date
    """, (equipment, months)).fetchall()
    out = []
    for r in rows:
        d = r['down_date']
        out.append(date.fromisoformat(d) if isinstance(d, str) else d)
    return out


def get_rolling_mtbf(conn, equipment: str, months: int = 24) -> dict:
    """Interval-based MTBF: the mean gap (days) between consecutive
    breakdowns, plus time since the last one. Needs >= 2 breakdown events
    to compute an interval; mtbf_days is None otherwise (insufficient
    data, not a misleading number from a single data point)."""
    dates = _breakdown_dates(conn, equipment, months)
    failure_count = len(dates)

    mtbf_days = None
    if failure_count >= 2:
        intervals = [(dates[i] - dates[i - 1]).days for i in range(1, failure_count)]
        mtbf_days = sum(intervals) / len(intervals)

    last_failure_date = dates[-1] if dates else None
    days_since_last_failure = (date.today() - last_failure_date).days if last_failure_date else None

    return {
        'equipment': equipment,
        'failure_count': failure_count,
        'mtbf_days': round(mtbf_days, 1) if mtbf_days is not None else None,
        'last_failure_date': last_failure_date.isoformat() if last_failure_date else None,
        'days_since_last_failure': days_since_last_failure,
    }


def _failure_probability(mtbf_days, horizon_days: int = 30):
    """P(>=1 failure in the next horizon_days), exponential/Poisson-process
    approximation from a mean interval. None when mtbf_days is unknown."""
    if not mtbf_days or mtbf_days <= 0:
        return None
    return 1.0 - math.exp(-horizon_days / mtbf_days)


def _risk_level(probability) -> str:
    if probability is None:
        return 'unknown'
    if probability <= RISK_THRESHOLDS['low']:
        return 'low'
    if probability <= RISK_THRESHOLDS['medium']:
        return 'medium'
    return 'high'


def get_predictive_maintenance_report(conn, months: int = 24,
                                       threshold_ratio: float = 0.8,
                                       horizon_days: int = 30) -> list:
    """One row per active equipment: rolling MTBF, days since last
    failure, whether that's approaching threshold_ratio x MTBF, a 30-day
    failure probability/risk level, and the latest sensor alert status.
    Combines all four P4-B spec bullets into one dashboard-feeding call."""
    sensor_status = {(a['equipment'], a['reading_type']): a['status']
                      for a in get_sensor_alerts(conn)}

    out = []
    for eq in list_equipment(conn, status='Operational'):
        name = eq['name']
        mtbf = get_rolling_mtbf(conn, name, months)
        mtbf_days = mtbf['mtbf_days']
        days_since = mtbf['days_since_last_failure']

        threshold_days = round(mtbf_days * threshold_ratio, 1) if mtbf_days else None
        approaching_threshold = bool(
            mtbf_days and days_since is not None and days_since >= threshold_days
        )
        probability = _failure_probability(mtbf_days, horizon_days)

        sensor_statuses = [
            sensor_status[(name, rt)] for rt in SENSOR_READING_TYPES
            if (name, rt) in sensor_status
        ]

        out.append({
            **mtbf,
            'equipment_id': eq['id'],
            'threshold_days': threshold_days,
            'approaching_threshold': approaching_threshold,
            'failure_probability_30d': round(probability, 3) if probability is not None else None,
            'risk_level': _risk_level(probability),
            'sensor_statuses': sensor_statuses,
        })
    return out


# ---------------------------------------------------------------------------
# Sensor readings / thresholds (manual/simulated IoT stub)
# ---------------------------------------------------------------------------

def record_sensor_reading(conn, equipment: str, reading_type: str, value: float,
                           unit: str, created_by: str) -> int:
    if reading_type not in SENSOR_READING_TYPES:
        raise ValueError(f"Unknown sensor reading type: {reading_type!r}")
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO equipment_sensor_reading "
        "(equipment, reading_type, value, unit, recorded_at, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (equipment, reading_type, float(value), unit or '', now, created_by or ''),
    ).fetchone()
    return row['id']


def set_sensor_threshold(conn, equipment: str, reading_type: str,
                          warning_max: float, critical_max: float) -> None:
    if reading_type not in SENSOR_READING_TYPES:
        raise ValueError(f"Unknown sensor reading type: {reading_type!r}")
    warning_max = float(warning_max)
    critical_max = float(critical_max)
    if warning_max >= critical_max:
        raise ValueError("Warning threshold must be lower than critical threshold.")
    conn.execute(
        "INSERT INTO equipment_sensor_threshold "
        "(equipment, reading_type, warning_max, critical_max) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (equipment, reading_type) DO UPDATE "
        "SET warning_max=EXCLUDED.warning_max, critical_max=EXCLUDED.critical_max",
        (equipment, reading_type, warning_max, critical_max),
    )


def list_sensor_readings(conn, equipment: str, reading_type: str, limit: int = 50) -> list:
    rows = conn.execute(
        "SELECT * FROM equipment_sensor_reading "
        "WHERE equipment = %s AND reading_type = %s "
        "ORDER BY recorded_at DESC LIMIT %s",
        (equipment, reading_type, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_sensor_alerts(conn, equipment: str | None = None) -> list:
    """Latest reading per (equipment, reading_type), compared to its
    threshold. status: 'ok' | 'warning' | 'critical' | 'no_threshold' |
    'no_reading'."""
    reading_q = """
        SELECT DISTINCT ON (equipment, reading_type)
               equipment, reading_type, value, unit, recorded_at
        FROM equipment_sensor_reading
    """
    params: list = []
    if equipment:
        reading_q += " WHERE equipment = %s"
        params.append(equipment)
    reading_q += " ORDER BY equipment, reading_type, recorded_at DESC"
    readings = {(r['equipment'], r['reading_type']): dict(r)
                for r in conn.execute(reading_q, params).fetchall()}

    threshold_q = "SELECT * FROM equipment_sensor_threshold"
    t_params: list = []
    if equipment:
        threshold_q += " WHERE equipment = %s"
        t_params.append(equipment)
    thresholds = {(t['equipment'], t['reading_type']): dict(t)
                  for t in conn.execute(threshold_q, t_params).fetchall()}

    keys = set(readings) | set(thresholds)
    out = []
    for key in keys:
        eq, rt = key
        reading = readings.get(key)
        threshold = thresholds.get(key)
        if not reading:
            status = 'no_reading'
            value = None
        elif not threshold:
            status = 'no_threshold'
            value = reading['value']
        elif reading['value'] >= threshold['critical_max']:
            status = 'critical'
            value = reading['value']
        elif reading['value'] >= threshold['warning_max']:
            status = 'warning'
            value = reading['value']
        else:
            status = 'ok'
            value = reading['value']
        out.append({
            'equipment': eq, 'reading_type': rt, 'value': value,
            'status': status,
            'recorded_at': reading['recorded_at'] if reading else None,
            'warning_max': threshold['warning_max'] if threshold else None,
            'critical_max': threshold['critical_max'] if threshold else None,
        })
    return out
