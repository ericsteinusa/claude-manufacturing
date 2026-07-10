"""apm_core.py — Qt-free Asset Performance Management (APM), 6/10 of the
top-10 ERPs have it.

Reliability math already exists in this app: `maintenance_core.get_mtbf`
computes MTBF/MTTR/availability from real `maint_downtime` records, and
`predictive_maintenance_core` computes rolling failure probability from
sensor data. APM doesn't reimplement either — it's the missing layer on
*top* of them: a per-asset **criticality** rating (how much this asset
actually matters to the business, admin-set since no formula can infer
that), combined with the existing availability data and this asset's
total downtime *cost* (already tracked on `maint_downtime.cost`, just
never rolled up per asset before) into a single health score and a
repair-vs-replace recommendation.

`equipment` is referenced by name (TEXT) throughout `maintenance_core`,
not by a foreign key to `maint_equipment` — `asset_criticality` follows
that same existing convention rather than introducing a new join pattern
this module alone would need.

Every function takes an open connection; the caller owns the transaction
(same convention as skills_matrix_core / fmea_core).
"""

from __future__ import annotations

from .maintenance_core import get_mtbf

CRITICALITY_LEVELS = ('low', 'medium', 'high', 'critical')
_CRITICALITY_WEIGHT = {'low': 1, 'medium': 2, 'high': 3, 'critical': 5}

RECOMMENDATIONS = ('monitor', 'schedule_maintenance', 'consider_replacement')


def ensure_apm_tables(conn):
    """Create asset_criticality if absent. Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asset_criticality (
            id                SERIAL PRIMARY KEY,
            equipment         TEXT NOT NULL UNIQUE,
            criticality       TEXT NOT NULL DEFAULT 'medium',
            replacement_cost  REAL NOT NULL DEFAULT 0.0,
            notes             TEXT NOT NULL DEFAULT '',
            created_by        TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


# ---------------------------------------------------------------------------
# Criticality
# ---------------------------------------------------------------------------

def list_asset_criticality(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM asset_criticality ORDER BY "
        "CASE criticality WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
        "WHEN 'medium' THEN 3 ELSE 4 END, equipment"
    ).fetchall()]


def get_asset_criticality(conn, equipment):
    row = conn.execute(
        "SELECT * FROM asset_criticality WHERE equipment = %s", (equipment,)
    ).fetchone()
    if row:
        return dict(row)
    return {'equipment': equipment, 'criticality': 'medium',
            'replacement_cost': 0.0, 'notes': ''}


def set_asset_criticality(conn, equipment, criticality, replacement_cost=0.0,
                          notes='', created_by=''):
    if not equipment or not equipment.strip():
        raise ValueError('equipment is required')
    if criticality not in CRITICALITY_LEVELS:
        raise ValueError(f'criticality must be one of {CRITICALITY_LEVELS}')
    conn.execute(
        "INSERT INTO asset_criticality (equipment, criticality, replacement_cost, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (equipment) DO UPDATE SET "
        "criticality = EXCLUDED.criticality, "
        "replacement_cost = EXCLUDED.replacement_cost, "
        "notes = EXCLUDED.notes",
        (equipment.strip(), criticality, float(replacement_cost or 0.0),
         notes or '', created_by or ''),
    )


# ---------------------------------------------------------------------------
# Health scoring
# ---------------------------------------------------------------------------

def _lifecycle_cost(conn, equipment, months):
    row = conn.execute(
        "SELECT COALESCE(SUM(cost), 0) AS total_cost FROM maint_downtime "
        "WHERE equipment ILIKE %s "
        "AND down_date >= (CURRENT_DATE - (%s * INTERVAL '1 month'))::text",
        (equipment, months),
    ).fetchone()
    return float(row['total_cost']) if row else 0.0


def get_asset_health(conn, equipment, months=12):
    """{'equipment', 'criticality', 'availability_pct', 'failure_count',
    'lifecycle_cost', 'health_score', 'recommendation'}.

    health_score starts from availability_pct (100 if no downtime history
    at all) and is penalized by failure_count, scaled by how critical the
    asset is — the same failure count matters a lot more on a critical
    asset than a low-priority one. Recommendation crosses to
    'consider_replacement' at a lower score threshold for higher-
    criticality assets, since the cost of being wrong is higher.
    """
    criticality_row = get_asset_criticality(conn, equipment)
    criticality = criticality_row['criticality']
    weight = _CRITICALITY_WEIGHT[criticality]

    reliability = get_mtbf(conn, equipment, months=months)
    availability = reliability['availability_pct']
    availability = availability if availability is not None else 100.0
    failure_count = reliability['failure_count']

    penalty = failure_count * weight * 2
    health_score = max(0.0, min(100.0, availability - penalty))

    if criticality in ('critical', 'high'):
        replace_threshold, monitor_threshold = 60, 85
    else:
        replace_threshold, monitor_threshold = 40, 75

    if health_score < replace_threshold:
        recommendation = 'consider_replacement'
    elif health_score < monitor_threshold:
        recommendation = 'schedule_maintenance'
    else:
        recommendation = 'monitor'

    return {
        'equipment': equipment,
        'criticality': criticality,
        'availability_pct': availability,
        'failure_count': failure_count,
        'lifecycle_cost': _lifecycle_cost(conn, equipment, months),
        'health_score': round(health_score, 1),
        'recommendation': recommendation,
    }


def get_apm_dashboard(conn, months=12):
    """Health-ranked list (worst first) across every equipment name with
    either a criticality rating or downtime history in the period."""
    names = set()
    for r in conn.execute("SELECT equipment FROM asset_criticality").fetchall():
        names.add(r['equipment'])
    for r in conn.execute(
        "SELECT DISTINCT equipment FROM maint_downtime "
        "WHERE down_date >= (CURRENT_DATE - (%s * INTERVAL '1 month'))::text",
        (months,),
    ).fetchall():
        names.add(r['equipment'])

    results = [get_asset_health(conn, name, months=months) for name in names]
    results.sort(key=lambda h: h['health_score'])
    return results
