"""technician_routing_core.py — Qt-free Technician Routing & Scheduling,
6/10 of the top-10 ERPs have it.

`maint_work_order.assigned_to` is a free-text field — enough to say *who*
is assigned, but nothing tracks an ordered daily plan across a mechanic's
several open work orders, or lets a dispatcher see one mechanic's whole
day at a glance. A `technician_route` is that daily plan: one mechanic,
one date, an ordered list of `technician_route_stop` rows each pointing at
a real `maint_work_order`. Completing a stop reuses
`maintenance_core.complete_work_order` rather than forking WO completion —
the route layer only ever adds a schedule/sequence on top of the existing
CMMS work order lifecycle, it never duplicates it.

Every function takes an open connection; the caller owns the transaction
(same convention as skills_matrix_core / fmea_core).
"""

from __future__ import annotations

import datetime

from .maintenance_core import complete_work_order, get_work_order

ROUTE_STATUSES = ('planned', 'in_progress', 'completed')
STOP_STATUSES = ('pending', 'in_progress', 'completed', 'skipped')


def _today() -> str:
    return datetime.date.today().isoformat()


def ensure_routing_tables(conn):
    """Create technician_route / technician_route_stop if absent.
    Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS technician_route (
            id           SERIAL PRIMARY KEY,
            mechanic_id  INTEGER NOT NULL REFERENCES maint_mechanic(id),
            route_date   TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'planned',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS technician_route_stop (
            id                 SERIAL PRIMARY KEY,
            route_id           INTEGER NOT NULL REFERENCES technician_route(id),
            wo_id              INTEGER NOT NULL REFERENCES maint_work_order(id),
            sequence           INTEGER NOT NULL DEFAULT 0,
            estimated_minutes  INTEGER NOT NULL DEFAULT 30,
            status             TEXT NOT NULL DEFAULT 'pending',
            notes              TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS technician_route_stop_route "
        "ON technician_route_stop(route_id)"
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def list_routes(conn, mechanic_id=None, route_date=None, status=None):
    sql = (
        "SELECT r.*, m.name AS mechanic_name, "
        "(SELECT COUNT(*) FROM technician_route_stop s WHERE s.route_id = r.id) AS stop_count, "
        "(SELECT COUNT(*) FROM technician_route_stop s WHERE s.route_id = r.id "
        " AND s.status = 'completed') AS completed_count "
        "FROM technician_route r "
        "JOIN maint_mechanic m ON m.id = r.mechanic_id "
        "WHERE TRUE"
    )
    params: list = []
    if mechanic_id:
        sql += " AND r.mechanic_id = %s"
        params.append(mechanic_id)
    if route_date:
        sql += " AND r.route_date = %s"
        params.append(route_date)
    if status:
        sql += " AND r.status = %s"
        params.append(status)
    sql += " ORDER BY r.route_date DESC, r.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_route(conn, route_id):
    row = conn.execute(
        "SELECT r.*, m.name AS mechanic_name FROM technician_route r "
        "JOIN maint_mechanic m ON m.id = r.mechanic_id WHERE r.id = %s",
        (route_id,),
    ).fetchone()
    if not row:
        return None
    route = dict(row)
    route['stops'] = list_stops(conn, route_id)
    return route


def create_route(conn, mechanic_id, route_date, created_by=''):
    row = conn.execute(
        "INSERT INTO technician_route (mechanic_id, route_date, created_by) "
        "VALUES (%s,%s,%s) RETURNING id",
        (mechanic_id, route_date or _today(), created_by or ''),
    ).fetchone()
    return row['id']


def set_route_status(conn, route_id, status):
    if status not in ROUTE_STATUSES:
        raise ValueError(f'status must be one of {ROUTE_STATUSES}')
    conn.execute(
        "UPDATE technician_route SET status = %s WHERE id = %s", (status, route_id)
    )


# ---------------------------------------------------------------------------
# Stops
# ---------------------------------------------------------------------------

def list_stops(conn, route_id):
    rows = conn.execute(
        "SELECT s.*, w.title, w.equipment, w.priority, w.status AS wo_status "
        "FROM technician_route_stop s "
        "JOIN maint_work_order w ON w.id = s.wo_id "
        "WHERE s.route_id = %s ORDER BY s.sequence, s.id",
        (route_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_stop(conn, route_id, wo_id, estimated_minutes=30, notes=''):
    """Append a stop at the end of this route's sequence. Raises if the
    work order is already on this route."""
    existing = conn.execute(
        "SELECT id FROM technician_route_stop WHERE route_id = %s AND wo_id = %s",
        (route_id, wo_id),
    ).fetchone()
    if existing:
        raise ValueError('This work order is already on this route.')
    max_row = conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) AS max_seq FROM technician_route_stop "
        "WHERE route_id = %s",
        (route_id,),
    ).fetchone()
    next_seq = (max_row['max_seq'] if max_row else 0) + 10
    row = conn.execute(
        "INSERT INTO technician_route_stop "
        "(route_id, wo_id, sequence, estimated_minutes, notes) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (route_id, wo_id, next_seq, int(estimated_minutes or 30), notes or ''),
    ).fetchone()
    return row['id']


def move_stop(conn, route_id, stop_id, direction):
    """Swap this stop's sequence with its neighbor ('up' or 'down')."""
    if direction not in ('up', 'down'):
        raise ValueError("direction must be 'up' or 'down'")
    stops = list_stops(conn, route_id)
    idx = next((i for i, s in enumerate(stops) if s['id'] == stop_id), None)
    if idx is None:
        raise ValueError(f'No stop with id {stop_id} on this route')
    neighbor_idx = idx - 1 if direction == 'up' else idx + 1
    if neighbor_idx < 0 or neighbor_idx >= len(stops):
        return  # already at the edge — no-op
    a, b = stops[idx], stops[neighbor_idx]
    conn.execute(
        "UPDATE technician_route_stop SET sequence = %s WHERE id = %s",
        (b['sequence'], a['id']),
    )
    conn.execute(
        "UPDATE technician_route_stop SET sequence = %s WHERE id = %s",
        (a['sequence'], b['id']),
    )


def complete_stop(conn, stop_id, notes=''):
    """Mark a stop completed and complete its underlying maintenance work
    order (reuses maintenance_core.complete_work_order). If every stop on
    the route is now completed, marks the route completed too."""
    stop = conn.execute(
        "SELECT route_id, wo_id FROM technician_route_stop WHERE id = %s", (stop_id,)
    ).fetchone()
    if not stop:
        raise ValueError(f'No stop with id {stop_id}')
    if not get_work_order(conn, stop['wo_id']):
        raise ValueError(f"No work order with id {stop['wo_id']}")

    conn.execute(
        "UPDATE technician_route_stop SET status = 'completed', notes = %s WHERE id = %s",
        (notes or '', stop_id),
    )
    complete_work_order(conn, stop['wo_id'])

    remaining = conn.execute(
        "SELECT COUNT(*) AS n FROM technician_route_stop "
        "WHERE route_id = %s AND status != 'completed'",
        (stop['route_id'],),
    ).fetchone()
    if remaining and remaining['n'] == 0:
        set_route_status(conn, stop['route_id'], 'completed')


def get_route_summary(conn, route_id):
    stops = list_stops(conn, route_id)
    total = len(stops)
    completed = sum(1 for s in stops if s['status'] == 'completed')
    total_minutes = sum(s['estimated_minutes'] for s in stops)
    return {
        'total_stops': total,
        'completed_stops': completed,
        'total_estimated_minutes': total_minutes,
        'percent_complete': round(100.0 * completed / total, 1) if total else 0.0,
    }
