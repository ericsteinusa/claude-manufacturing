"""abc_costing_core.py — Qt-free Activity-Based Costing (ABC), 6/10 of the
top-10 ERPs have it. Closes Finance & GL's last remaining gap in the
competitive analysis.

``costing_core.roll_standard_cost`` allocates overhead to a product with a
single flat rate (workcenter ``overhead_rate`` x routing ``std_hours``) —
the traditional method, and still the default for every existing caller.
This module is a parallel, opt-in *analysis* layer, not a replacement:
it allocates the same kind of overhead dollars using activity cost pools
and real consumption drivers (setups, inspections, machine hours,
whatever the organization tracks), then compares the result against the
existing flat-rate number so a controller can see which products the
flat rate is over- or under-costing — the entire point of ABC.

Tables:
  abc_activity         — a cost pool: total overhead $ for one activity
                         (e.g. "Machine Setups") plus its driver's unit of
                         measure (e.g. "per setup")
  abc_product_driver   — how much of an activity's driver each product
                         consumed (e.g. Product X used 40 setups)
  abc_product_output   — units of each product actually produced, needed
                         to turn a total allocated dollar amount into a
                         per-unit number; kept as its own small table
                         rather than duplicated onto every driver row,
                         since a product's output quantity doesn't vary
                         by activity

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / costing_layers_core).
"""

from __future__ import annotations

from .costing_core import get_standard_cost

# A product's ABC-vs-traditional overhead gap flagged as worth investigating
# once it exceeds this percentage — a common ABC-teaching convention, not a
# regulatory or GAAP threshold.
VARIANCE_FLAG_THRESHOLD_PCT = 15.0


def ensure_abc_costing_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS abc_activity (
            id                SERIAL PRIMARY KEY,
            name              TEXT NOT NULL UNIQUE,
            cost_pool_amount  REAL NOT NULL DEFAULT 0.0,
            driver_uom        TEXT NOT NULL DEFAULT '',
            notes             TEXT NOT NULL DEFAULT '',
            created_by        TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS abc_product_driver (
            id            SERIAL PRIMARY KEY,
            activity_id   INTEGER NOT NULL REFERENCES abc_activity(id),
            product_id    INTEGER NOT NULL REFERENCES product(id),
            driver_qty    REAL NOT NULL DEFAULT 0.0,
            UNIQUE (activity_id, product_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS abc_product_output (
            id           SERIAL PRIMARY KEY,
            product_id   INTEGER NOT NULL UNIQUE REFERENCES product(id),
            output_qty   REAL NOT NULL DEFAULT 0.0,
            notes        TEXT NOT NULL DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

def list_activities(conn, search=None):
    sql = "SELECT * FROM abc_activity WHERE TRUE"
    params: list = []
    if search:
        sql += " AND name ILIKE %s"
        params.append(f"%{search}%")
    sql += " ORDER BY name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_activity(conn, activity_id):
    row = conn.execute(
        "SELECT * FROM abc_activity WHERE id = %s", (activity_id,),
    ).fetchone()
    return dict(row) if row else None


def create_activity(conn, name, cost_pool_amount, driver_uom='', notes='', created_by=''):
    if not name.strip():
        raise ValueError('Name is required.')
    if cost_pool_amount < 0:
        raise ValueError('Cost pool amount cannot be negative.')
    row = conn.execute(
        "INSERT INTO abc_activity (name, cost_pool_amount, driver_uom, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), cost_pool_amount, driver_uom or '', notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def update_activity(conn, activity_id, **fields):
    allowed = {'name', 'cost_pool_amount', 'driver_uom', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'cost_pool_amount' in cols and cols['cost_pool_amount'] < 0:
        raise ValueError('Cost pool amount cannot be negative.')
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE abc_activity SET {set_clause} WHERE id = %s",
        list(cols.values()) + [activity_id],
    )


def delete_activity(conn, activity_id):
    conn.execute("DELETE FROM abc_product_driver WHERE activity_id = %s", (activity_id,))
    conn.execute("DELETE FROM abc_activity WHERE id = %s", (activity_id,))


# ---------------------------------------------------------------------------
# Product driver consumption / output
# ---------------------------------------------------------------------------

def list_product_drivers(conn, activity_id=None, product_id=None):
    conditions = ["TRUE"]
    params: list = []
    if activity_id:
        conditions.append("apd.activity_id = %s")
        params.append(activity_id)
    if product_id:
        conditions.append("apd.product_id = %s")
        params.append(product_id)
    rows = conn.execute(f"""
        SELECT apd.*, a.name AS activity_name, a.driver_uom, p.name AS product_name
        FROM abc_product_driver apd
        JOIN abc_activity a ON a.id = apd.activity_id
        JOIN product p ON p.id = apd.product_id
        WHERE {" AND ".join(conditions)}
        ORDER BY a.name, p.name
    """, params).fetchall()
    return [dict(r) for r in rows]


def set_product_driver(conn, activity_id, product_id, driver_qty):
    if driver_qty < 0:
        raise ValueError('Driver qty cannot be negative.')
    conn.execute(
        "INSERT INTO abc_product_driver (activity_id, product_id, driver_qty) "
        "VALUES (%s,%s,%s) "
        "ON CONFLICT (activity_id, product_id) DO UPDATE SET driver_qty = EXCLUDED.driver_qty",
        (activity_id, product_id, driver_qty),
    )


def remove_product_driver(conn, driver_id):
    conn.execute("DELETE FROM abc_product_driver WHERE id = %s", (driver_id,))


def set_product_output(conn, product_id, output_qty, notes=''):
    if output_qty < 0:
        raise ValueError('Output qty cannot be negative.')
    conn.execute(
        "INSERT INTO abc_product_output (product_id, output_qty, notes) "
        "VALUES (%s,%s,%s) "
        "ON CONFLICT (product_id) DO UPDATE SET output_qty = EXCLUDED.output_qty, "
        "notes = EXCLUDED.notes",
        (product_id, output_qty, notes or ''),
    )


def get_product_output(conn, product_id):
    row = conn.execute(
        "SELECT * FROM abc_product_output WHERE product_id = %s", (product_id,),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def compute_activity_rate(conn, activity_id):
    """$ per driver unit for one activity, or None if no product has
    recorded any driver consumption yet (nothing to divide the pool by —
    reported as unresolvable rather than a misleading 0.0)."""
    activity = get_activity(conn, activity_id)
    if not activity:
        raise ValueError(f'No activity with id {activity_id}')
    row = conn.execute(
        "SELECT COALESCE(SUM(driver_qty), 0) AS total FROM abc_product_driver "
        "WHERE activity_id = %s",
        (activity_id,),
    ).fetchone()
    total_driver_qty = row['total']
    if total_driver_qty <= 0:
        return None
    return activity['cost_pool_amount'] / total_driver_qty


def get_abc_overhead_for_product(conn, product_id):
    """{activities: [{activity_id, activity_name, driver_qty, rate,
    allocated_cost}], total_allocated_cost, output_qty,
    abc_overhead_per_unit}. Only activities the product has a driver row
    for are included — a product with no recorded consumption of an
    activity isn't assumed to owe it anything."""
    drivers = list_product_drivers(conn, product_id=product_id)
    activities = []
    total_allocated = 0.0
    for d in drivers:
        rate = compute_activity_rate(conn, d['activity_id'])
        allocated = rate * d['driver_qty'] if rate is not None else None
        if allocated is not None:
            total_allocated += allocated
        activities.append({
            'activity_id': d['activity_id'],
            'activity_name': d['activity_name'],
            'driver_uom': d['driver_uom'],
            'driver_qty': d['driver_qty'],
            'rate': rate,
            'allocated_cost': allocated,
        })

    output = get_product_output(conn, product_id)
    output_qty = output['output_qty'] if output else 0.0
    per_unit = (total_allocated / output_qty) if output_qty > 0 else None

    return {
        'product_id': product_id,
        'activities': activities,
        'total_allocated_cost': total_allocated,
        'output_qty': output_qty,
        'abc_overhead_per_unit': per_unit,
    }


def compare_to_traditional(conn, product_id):
    """ABC per-unit overhead vs. the existing flat-rate standard cost's
    std_overhead_cost (costing_core.get_standard_cost) — the actual ABC
    deliverable: is the traditional method over- or under-costing this
    product relative to what it really consumes?"""
    abc = get_abc_overhead_for_product(conn, product_id)
    traditional = get_standard_cost(conn, product_id)
    traditional_overhead = traditional['std_overhead_cost'] if traditional else None

    variance = None
    variance_pct = None
    flagged = False
    if abc['abc_overhead_per_unit'] is not None and traditional_overhead is not None:
        variance = abc['abc_overhead_per_unit'] - traditional_overhead
        if traditional_overhead > 0:
            variance_pct = variance / traditional_overhead * 100.0
            flagged = abs(variance_pct) >= VARIANCE_FLAG_THRESHOLD_PCT
        elif abc['abc_overhead_per_unit'] > 0:
            flagged = True  # traditional says $0 overhead, ABC says otherwise

    return {
        **abc,
        'traditional_overhead_per_unit': traditional_overhead,
        'variance': variance,
        'variance_pct': variance_pct,
        'flagged': flagged,
    }


def get_abc_summary_all_products(conn):
    """One row per product with at least one recorded driver, sorted by
    absolute variance vs. the traditional flat rate (largest first) — the
    "which products are most mis-costed today" view."""
    rows = conn.execute(
        "SELECT DISTINCT apd.product_id, p.name AS product_name "
        "FROM abc_product_driver apd JOIN product p ON p.id = apd.product_id "
        "ORDER BY p.name"
    ).fetchall()
    summary = []
    for r in rows:
        comparison = compare_to_traditional(conn, r['product_id'])
        comparison['product_name'] = r['product_name']
        summary.append(comparison)
    summary.sort(key=lambda c: abs(c['variance']) if c['variance'] is not None else -1, reverse=True)
    return summary
