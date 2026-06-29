"""
routing_core.py — Qt-free work order routing and labor tracking.

Tables managed here:
  workcenter   — a production resource with a labor rate and daily capacity
  routing      — ordered list of operations for a product (the template)
  wo_operation — operations instantiated on a specific work order (the actual)

Typical flow:
  1. Create routing steps for a product via create_routing_step().
  2. When a WO is opened, call populate_wo_operations() to copy the product
     routing into wo_operation rows for that WO.
  3. Shop floor workers call start_wo_operation() and complete_wo_operation()
     as they progress through each step.
  4. On WO close, get_wo_labor_cost() returns the actual labour spend.
"""

OP_STATUSES = ('pending', 'in_progress', 'completed', 'skipped')


def ensure_routing_tables(conn):
    """Create workcenter / routing / wo_operation if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workcenter (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            dept TEXT NOT NULL DEFAULT '',
            capacity_hours_per_day REAL NOT NULL DEFAULT 8.0,
            labor_rate REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS routing (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            operation_seq INTEGER NOT NULL DEFAULT 10,
            operation_name TEXT NOT NULL,
            workcenter_id INTEGER REFERENCES workcenter(id),
            std_hours REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            UNIQUE(product_id, operation_seq)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_operation (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL REFERENCES work_order(id),
            routing_id INTEGER REFERENCES routing(id),
            operation_seq INTEGER NOT NULL DEFAULT 10,
            operation_name TEXT NOT NULL,
            workcenter_id INTEGER REFERENCES workcenter(id),
            std_hours REAL NOT NULL DEFAULT 0.0,
            actual_hours REAL,
            scrap_qty REAL NOT NULL DEFAULT 0.0,
            rework_qty REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            completed_by TEXT,
            notes TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wo_operation_wo_id ON wo_operation(wo_id)"
    )


# ---------------------------------------------------------------------------
# Workcenter
# ---------------------------------------------------------------------------

def list_workcenters(conn, active_only=True):
    """Return all workcenters, active ones first."""
    cond = "WHERE is_active = TRUE" if active_only else ""
    rows = conn.execute(
        f"SELECT id, name, dept, capacity_hours_per_day, labor_rate, notes, is_active "
        f"FROM workcenter {cond} ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def create_workcenter(conn, name, dept='', capacity_hours_per_day=8.0,
                      labor_rate=0.0, notes=None):
    """Insert a workcenter and return its id. Does not commit."""
    row = conn.execute(
        "INSERT INTO workcenter (name, dept, capacity_hours_per_day, labor_rate, notes) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), dept.strip(), max(0.0, capacity_hours_per_day),
         max(0.0, labor_rate), notes),
    ).fetchone()
    return row['id']


def update_workcenter(conn, wc_id, name, dept='', capacity_hours_per_day=8.0,
                      labor_rate=0.0, notes=None, is_active=True):
    """Update a workcenter. Does not commit."""
    conn.execute(
        "UPDATE workcenter SET name=%s, dept=%s, capacity_hours_per_day=%s, "
        "labor_rate=%s, notes=%s, is_active=%s WHERE id=%s",
        (name.strip(), dept.strip(), max(0.0, capacity_hours_per_day),
         max(0.0, labor_rate), notes, is_active, wc_id),
    )


# ---------------------------------------------------------------------------
# Product routing (template)
# ---------------------------------------------------------------------------

def get_routing(conn, product_id):
    """Return routing steps for a product in operation_seq order."""
    rows = conn.execute(
        "SELECT r.id, r.product_id, r.operation_seq, r.operation_name, "
        "r.workcenter_id, wc.name AS workcenter_name, wc.labor_rate, "
        "r.std_hours, r.notes "
        "FROM routing r "
        "LEFT JOIN workcenter wc ON wc.id = r.workcenter_id "
        "WHERE r.product_id = %s "
        "ORDER BY r.operation_seq",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_routing_step(conn, product_id, operation_seq, operation_name,
                        workcenter_id=None, std_hours=0.0, notes=None):
    """Append a routing step. Does not commit.

    Raises psycopg2.IntegrityError if (product_id, operation_seq) already exists.
    """
    row = conn.execute(
        "INSERT INTO routing "
        "(product_id, operation_seq, operation_name, workcenter_id, std_hours, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (product_id, operation_seq, operation_name.strip(),
         workcenter_id or None, max(0.0, std_hours), notes),
    ).fetchone()
    return row['id']


def update_routing_step(conn, routing_id, operation_seq, operation_name,
                        workcenter_id=None, std_hours=0.0, notes=None):
    """Update a routing step. Does not commit."""
    conn.execute(
        "UPDATE routing SET operation_seq=%s, operation_name=%s, "
        "workcenter_id=%s, std_hours=%s, notes=%s WHERE id=%s",
        (operation_seq, operation_name.strip(),
         workcenter_id or None, max(0.0, std_hours), notes, routing_id),
    )


def delete_routing_step(conn, routing_id):
    """Delete a routing step. Does not commit."""
    conn.execute("DELETE FROM routing WHERE id=%s", (routing_id,))


def next_routing_seq(conn, product_id):
    """Return the next available operation_seq (max + 10, or 10 if none)."""
    row = conn.execute(
        "SELECT MAX(operation_seq) AS mx FROM routing WHERE product_id=%s",
        (product_id,),
    ).fetchone()
    return (row['mx'] or 0) + 10


# ---------------------------------------------------------------------------
# WO operations (instance)
# ---------------------------------------------------------------------------

def populate_wo_operations(conn, wo_id, product_id):
    """Copy a product's routing into wo_operation rows for a specific WO.

    Idempotent: skips if operations already exist.  Does not commit.
    Returns the number of rows inserted.
    """
    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM wo_operation WHERE wo_id=%s", (wo_id,)
    ).fetchone()['n']
    if existing:
        return 0

    steps = get_routing(conn, product_id)
    for step in steps:
        conn.execute(
            "INSERT INTO wo_operation "
            "(wo_id, routing_id, operation_seq, operation_name, "
            "workcenter_id, std_hours, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,'pending')",
            (wo_id, step['id'], step['operation_seq'], step['operation_name'],
             step['workcenter_id'], step['std_hours']),
        )
    return len(steps)


def get_wo_operations(conn, wo_id):
    """Return operation rows for a WO, in sequence order."""
    rows = conn.execute(
        "SELECT op.id, op.wo_id, op.routing_id, op.operation_seq, "
        "op.operation_name, op.workcenter_id, wc.name AS workcenter_name, "
        "wc.labor_rate, op.std_hours, op.actual_hours, "
        "op.scrap_qty, op.rework_qty, op.status, "
        "op.started_at, op.completed_at, op.completed_by, op.notes "
        "FROM wo_operation op "
        "LEFT JOIN workcenter wc ON wc.id = op.workcenter_id "
        "WHERE op.wo_id=%s "
        "ORDER BY op.operation_seq",
        (wo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def start_wo_operation(conn, op_id):
    """Mark an operation as in_progress. Does not commit."""
    conn.execute(
        "UPDATE wo_operation SET status='in_progress', started_at=NOW() "
        "WHERE id=%s AND status='pending'",
        (op_id,),
    )


def complete_wo_operation(conn, op_id, actual_hours, completed_by,
                          scrap_qty=0.0, rework_qty=0.0, notes=None):
    """Record actual hours and close an operation. Does not commit."""
    conn.execute(
        "UPDATE wo_operation "
        "SET status='completed', actual_hours=%s, scrap_qty=%s, rework_qty=%s, "
        "completed_at=NOW(), completed_by=%s, notes=%s "
        "WHERE id=%s",
        (max(0.0, actual_hours), max(0.0, scrap_qty), max(0.0, rework_qty),
         completed_by, notes, op_id),
    )


def skip_wo_operation(conn, op_id, notes=None):
    """Mark an operation as skipped. Does not commit."""
    conn.execute(
        "UPDATE wo_operation SET status='skipped', notes=%s WHERE id=%s",
        (notes, op_id),
    )


def get_wo_labor_cost(conn, wo_id):
    """Return total actual labour cost for a WO.

    Cost = SUM(actual_hours × workcenter.labor_rate) for completed ops.
    Returns a dict: {total_std_hours, total_actual_hours, labor_cost}.
    """
    row = conn.execute(
        "SELECT "
        "  COALESCE(SUM(op.std_hours), 0)                          AS total_std_hours, "
        "  COALESCE(SUM(op.actual_hours), 0)                       AS total_actual_hours, "
        "  COALESCE(SUM(COALESCE(op.actual_hours,0) * "
        "               COALESCE(wc.labor_rate,0)), 0)             AS labor_cost "
        "FROM wo_operation op "
        "LEFT JOIN workcenter wc ON wc.id = op.workcenter_id "
        "WHERE op.wo_id=%s AND op.status='completed'",
        (wo_id,),
    ).fetchone()
    return dict(row) if row else {'total_std_hours': 0, 'total_actual_hours': 0, 'labor_cost': 0.0}


def get_workcenter_load(conn, start_date, end_date):
    """Return workcenter load (total actual hours) between two dates.

    Used for capacity planning.  Returns [{workcenter_id, workcenter_name,
    dept, capacity_hours_per_day, total_actual_hours, total_std_hours}].
    """
    rows = conn.execute(
        "SELECT wc.id AS workcenter_id, wc.name AS workcenter_name, wc.dept, "
        "wc.capacity_hours_per_day, "
        "COALESCE(SUM(op.actual_hours), 0)   AS total_actual_hours, "
        "COALESCE(SUM(op.std_hours), 0)      AS total_std_hours "
        "FROM workcenter wc "
        "LEFT JOIN wo_operation op ON op.workcenter_id = wc.id "
        "  AND op.status = 'completed' "
        "  AND op.completed_at::date BETWEEN %s AND %s "
        "GROUP BY wc.id, wc.name, wc.dept, wc.capacity_hours_per_day "
        "ORDER BY wc.name",
        (start_date, end_date),
    ).fetchall()
    return [dict(r) for r in rows]
