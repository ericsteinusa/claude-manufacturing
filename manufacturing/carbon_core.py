"""
carbon_core.py — Qt-free Sustainability / Carbon Cost Tracking (P4-G).

A direct structural mirror of costing_core.py's standard-cost rollup —
same BOM-explosion shape, same 'buy' (direct factor) vs 'make'
(recursive children + own routing) split, same cycle guard, same
roll-then-snapshot pattern, same per-WO-actual-quantity multiplication
for a per-unit intensity metric — just kg CO2e instead of dollars.

Material emission factor (kg_co2e_per_unit) lives directly on `product`,
exactly parallel to how `purchase_price` already does for cost. Process
emission factor (kg_co2e_per_hour) lives on `workcenter`, parallel to
`overhead_rate`. Both are added additively via ALTER TABLE ADD COLUMN IF
NOT EXISTS, the same technique costing_core.ensure_costing_tables uses.

Scope framework (simplified, GHG-Protocol-*inspired*, not full
compliance tooling):
    Scope 1 (direct operations)   — process/routing emissions actually
                                     incurred by completed production
                                     (wo_carbon_actual.process_carbon_kg).
    Scope 2 (purchased energy)    — manual monthly kWh x grid-factor
                                     entries. No energy/kWh telemetry
                                     exists anywhere in this codebase
                                     (no power field on equipment, no
                                     utility-bill import), so this is
                                     honestly manual entry, not derived
                                     from nonexistent sensor data. The
                                     default grid factor is an
                                     illustrative placeholder, not an
                                     authoritative regional figure.
    Scope 3 (purchased goods)     — material emissions embodied in
                                     production (wo_carbon_actual.
                                     material_carbon_kg) — a real GHG
                                     Protocol category, computed from
                                     real BOM data.

wo_carbon_actual has no variance fields (unlike wo_cost_actual): there is
no independently-measured "actual" carbon telemetry to vary against —
this is honestly a projection of the standard roll x actual quantity
produced, not a measured actual.
"""

from datetime import date

from .log_utils import get_logger

log = get_logger(__name__)

_MAX_DEPTH = 15


# ---------------------------------------------------------------------------
# Table / column setup
# ---------------------------------------------------------------------------

def ensure_carbon_tables(conn):
    """Create carbon_* tables and add carbon factor columns. Does not commit."""
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS "
        "kg_co2e_per_unit REAL DEFAULT 0"
    )
    # A genuinely fresh Postgres deployment's `product` table (created via
    # schema.py's/work_orders_core.py's own CREATE TABLE IF NOT EXISTS) has
    # no item_type column — it's only added by seed_sample_products.py's own
    # ALTER TABLE, a dev-only script never run in production. _get_bom_lines
    # below selects p.item_type, so self-heal it here too.
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS "
        "item_type TEXT DEFAULT 'buy'"
    )
    conn.execute(
        "ALTER TABLE workcenter ADD COLUMN IF NOT EXISTS "
        "kg_co2e_per_hour REAL DEFAULT 0"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS carbon_roll (
            id                 SERIAL PRIMARY KEY,
            product_id         INTEGER NOT NULL REFERENCES product(id),
            effective_date     TEXT NOT NULL,
            material_carbon_kg REAL NOT NULL DEFAULT 0.0,
            process_carbon_kg  REAL NOT NULL DEFAULT 0.0,
            total_carbon_kg    REAL NOT NULL DEFAULT 0.0,
            roll_notes         TEXT,
            created_by         TEXT,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS carbon_roll_product "
        "ON carbon_roll(product_id, effective_date DESC)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_carbon_actual (
            id                 SERIAL PRIMARY KEY,
            wo_id              INTEGER NOT NULL UNIQUE REFERENCES work_order(id),
            quantity           REAL NOT NULL DEFAULT 0.0,
            material_carbon_kg REAL NOT NULL DEFAULT 0.0,
            process_carbon_kg  REAL NOT NULL DEFAULT 0.0,
            total_carbon_kg    REAL NOT NULL DEFAULT 0.0,
            carbon_per_unit_kg REAL NOT NULL DEFAULT 0.0,
            created_by         TEXT,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS carbon_scope2_entry (
            id                          SERIAL PRIMARY KEY,
            period_month                TEXT NOT NULL UNIQUE,
            kwh_used                    REAL NOT NULL DEFAULT 0.0,
            grid_factor_kg_co2e_per_kwh REAL NOT NULL DEFAULT 0.4,
            total_kg_co2e               REAL NOT NULL DEFAULT 0.0,
            notes                       TEXT,
            created_by                  TEXT,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def set_material_factor(conn, product_id, kg_co2e_per_unit) -> None:
    conn.execute(
        "UPDATE product SET kg_co2e_per_unit = %s WHERE id = %s",
        (kg_co2e_per_unit, product_id),
    )


def set_workcenter_factor(conn, workcenter_id, kg_co2e_per_hour) -> None:
    conn.execute(
        "UPDATE workcenter SET kg_co2e_per_hour = %s WHERE id = %s",
        (kg_co2e_per_hour, workcenter_id),
    )


def list_workcenters_with_carbon_factor(conn):
    """[{id, name, kg_co2e_per_hour}] for the ESG dashboard's process
    emission factor editor."""
    rows = conn.execute(
        "SELECT id, name, COALESCE(kg_co2e_per_hour, 0) AS kg_co2e_per_hour "
        "FROM workcenter WHERE is_active = TRUE ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Carbon footprint roll-up
# ---------------------------------------------------------------------------

def _get_bom_lines(conn, product_id):
    """Return direct BOM components for a product, with their material
    carbon factor. Mirrors costing_core._get_bom_lines."""
    rows = conn.execute(
        "SELECT b.component_id, b.qty_required, COALESCE(b.scrap_pct, 0) AS scrap_pct, "
        "p.name, COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.kg_co2e_per_unit, 0) AS kg_co2e_per_unit "
        "FROM bom b "
        "JOIN product p ON p.id = b.component_id "
        "WHERE b.product_id = %s",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_routing_process_carbon(conn, product_id) -> float:
    """Sum std_hours x kg_co2e_per_hour across routing. Mirrors
    costing_core._get_routing_cost."""
    row = conn.execute(
        "SELECT COALESCE(SUM(r.std_hours * COALESCE(wc.kg_co2e_per_hour, 0)), 0) "
        "AS process_carbon "
        "FROM routing r "
        "LEFT JOIN workcenter wc ON wc.id = r.workcenter_id "
        "WHERE r.product_id = %s",
        (product_id,),
    ).fetchone()
    return float(row['process_carbon']) if row else 0.0


def roll_carbon_footprint(conn, product_id, created_by=None, _depth=0, _visited=None) -> dict:
    """Compute and save the carbon footprint for one product.

    Direct structural mirror of costing_core.roll_standard_cost:
    - 'buy' items: material_carbon = kg_co2e_per_unit, no process carbon.
    - 'make' items: material_carbon = sum of component rolled carbon x
                    qty (+ scrap), process_carbon from routing x
                    workcenter kg_co2e_per_hour.

    Stores a carbon_roll row and returns the carbon dict.
    Does not commit — caller controls the transaction.
    """
    if _visited is None:
        _visited = set()
    if _depth > _MAX_DEPTH:
        log.warning("carbon: max BOM depth reached for product_id=%s", product_id)
        return {'material_carbon_kg': 0.0, 'process_carbon_kg': 0.0, 'total_carbon_kg': 0.0}
    if product_id in _visited:
        log.warning("carbon: cycle detected at product_id=%s", product_id)
        return {'material_carbon_kg': 0.0, 'process_carbon_kg': 0.0, 'total_carbon_kg': 0.0}
    _visited.add(product_id)

    prod_row = conn.execute(
        "SELECT COALESCE(item_type, 'buy') AS item_type, "
        "COALESCE(kg_co2e_per_unit, 0) AS kg_co2e_per_unit "
        "FROM product WHERE id=%s",
        (product_id,),
    ).fetchone()
    if not prod_row:
        return {'material_carbon_kg': 0.0, 'process_carbon_kg': 0.0, 'total_carbon_kg': 0.0}

    item_type = prod_row['item_type']

    if item_type == 'buy':
        mat = float(prod_row['kg_co2e_per_unit'])
        process = 0.0
    else:
        bom_lines = _get_bom_lines(conn, product_id)
        mat = 0.0
        for line in bom_lines:
            child_carbon = roll_carbon_footprint(
                conn, line['component_id'], created_by,
                _depth=_depth + 1, _visited=_visited,
            )
            inflated_qty = line['qty_required'] * (1 + line['scrap_pct'] / 100.0)
            mat += child_carbon['total_carbon_kg'] * inflated_qty
        process = _get_routing_process_carbon(conn, product_id)

    total = mat + process

    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO carbon_roll "
        "(product_id, effective_date, material_carbon_kg, process_carbon_kg, "
        "total_carbon_kg, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (product_id, today, mat, process, total, created_by),
    )
    log.info("Carbon rolled for product_id=%s: material=%.4f process=%.4f total=%.4f",
              product_id, mat, process, total)
    return {'material_carbon_kg': mat, 'process_carbon_kg': process, 'total_carbon_kg': total}


def get_carbon_footprint(conn, product_id):
    """Return the most recent carbon_roll for a product, or None."""
    row = conn.execute(
        "SELECT id, product_id, effective_date, material_carbon_kg, "
        "process_carbon_kg, total_carbon_kg, created_by, created_at "
        "FROM carbon_roll WHERE product_id=%s "
        "ORDER BY effective_date DESC, id DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    return dict(row) if row else None


def list_carbon_history(conn, product_id):
    """Return all carbon_roll rows for a product, newest first."""
    rows = conn.execute(
        "SELECT id, effective_date, material_carbon_kg, process_carbon_kg, "
        "total_carbon_kg, created_by, created_at "
        "FROM carbon_roll WHERE product_id=%s "
        "ORDER BY effective_date DESC, id DESC",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# WO carbon actual — carbon intensity per unit produced
# ---------------------------------------------------------------------------

def save_wo_carbon_actual(conn, wo_id, created_by=None) -> dict:
    """Multiply the latest carbon_roll by a WO's actual output quantity.

    carbon_per_unit_kg is the roll's total_carbon_kg itself — already a
    per-unit figure, and exactly the "carbon intensity" metric the
    roadmap asks for. Upserts wo_carbon_actual. Does not commit.
    """
    wo_row = conn.execute(
        "SELECT product_id, COALESCE(quantity, 1) AS quantity "
        "FROM work_order WHERE id=%s",
        (wo_id,),
    ).fetchone()
    if not wo_row:
        raise ValueError(f"Work order {wo_id} not found")

    quantity = float(wo_row['quantity'])
    roll = get_carbon_footprint(conn, wo_row['product_id']) if wo_row['product_id'] else None
    per_unit_material = float(roll['material_carbon_kg']) if roll else 0.0
    per_unit_process = float(roll['process_carbon_kg']) if roll else 0.0
    per_unit_total = float(roll['total_carbon_kg']) if roll else 0.0

    material_carbon_kg = per_unit_material * quantity
    process_carbon_kg = per_unit_process * quantity
    total_carbon_kg = material_carbon_kg + process_carbon_kg

    conn.execute(
        "INSERT INTO wo_carbon_actual "
        "(wo_id, quantity, material_carbon_kg, process_carbon_kg, total_carbon_kg, "
        "carbon_per_unit_kg, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (wo_id) DO UPDATE SET "
        "quantity=EXCLUDED.quantity, "
        "material_carbon_kg=EXCLUDED.material_carbon_kg, "
        "process_carbon_kg=EXCLUDED.process_carbon_kg, "
        "total_carbon_kg=EXCLUDED.total_carbon_kg, "
        "carbon_per_unit_kg=EXCLUDED.carbon_per_unit_kg, "
        "created_by=EXCLUDED.created_by",
        (wo_id, quantity, material_carbon_kg, process_carbon_kg, total_carbon_kg,
         per_unit_total, created_by),
    )
    result = {
        'quantity': quantity, 'material_carbon_kg': material_carbon_kg,
        'process_carbon_kg': process_carbon_kg, 'total_carbon_kg': total_carbon_kg,
        'carbon_per_unit_kg': per_unit_total,
    }
    log.info("WO %s carbon saved: qty=%.2f total=%.4f kg CO2e (%.4f/unit)",
              wo_id, quantity, total_carbon_kg, per_unit_total)
    return result


def get_wo_carbon(conn, wo_id):
    """Return the saved wo_carbon_actual row for a WO, or None."""
    row = conn.execute(
        "SELECT * FROM wo_carbon_actual WHERE wo_id=%s", (wo_id,)
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Scope 2 (purchased energy) — manual entry
# ---------------------------------------------------------------------------

def set_scope2_entry(conn, period_month: str, kwh_used, grid_factor_kg_co2e_per_kwh,
                      notes=None, created_by=None) -> None:
    if not period_month:
        raise ValueError("period_month is required (e.g. '2026-07').")
    total_kg_co2e = float(kwh_used) * float(grid_factor_kg_co2e_per_kwh)
    conn.execute(
        "INSERT INTO carbon_scope2_entry "
        "(period_month, kwh_used, grid_factor_kg_co2e_per_kwh, total_kg_co2e, "
        "notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (period_month) DO UPDATE SET "
        "kwh_used=EXCLUDED.kwh_used, "
        "grid_factor_kg_co2e_per_kwh=EXCLUDED.grid_factor_kg_co2e_per_kwh, "
        "total_kg_co2e=EXCLUDED.total_kg_co2e, "
        "notes=EXCLUDED.notes, "
        "created_by=EXCLUDED.created_by",
        (period_month, kwh_used, grid_factor_kg_co2e_per_kwh, total_kg_co2e,
         notes or '', created_by),
    )


def list_scope2_entries(conn):
    rows = conn.execute(
        "SELECT * FROM carbon_scope2_entry ORDER BY period_month DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# ESG dashboard
# ---------------------------------------------------------------------------

def get_esg_summary(conn, date_from: str | None = None, date_to: str | None = None) -> dict:
    """Simplified GHG-Protocol-inspired scope 1/2/3 summary — see module
    docstring for what each scope represents and its data source."""
    wo_conds, wo_params = [], []
    if date_from:
        wo_conds.append("w.created_at >= %s")
        wo_params.append(date_from)
    if date_to:
        wo_conds.append("w.created_at <= %s")
        wo_params.append(date_to)
    wo_where = f" WHERE {' AND '.join(wo_conds)}" if wo_conds else ""

    scope13 = conn.execute(
        "SELECT COALESCE(SUM(process_carbon_kg), 0) AS scope1_kg, "
        "COALESCE(SUM(material_carbon_kg), 0) AS scope3_kg "
        f"FROM wo_carbon_actual w{wo_where}",
        wo_params,
    ).fetchone()

    s2_conds, s2_params = [], []
    if date_from:
        s2_conds.append("period_month >= %s")
        s2_params.append(date_from[:7])
    if date_to:
        s2_conds.append("period_month <= %s")
        s2_params.append(date_to[:7])
    s2_where = f" WHERE {' AND '.join(s2_conds)}" if s2_conds else ""
    scope2 = conn.execute(
        f"SELECT COALESCE(SUM(total_kg_co2e), 0) AS scope2_kg FROM carbon_scope2_entry{s2_where}",
        s2_params,
    ).fetchone()

    by_product = conn.execute(
        "SELECT p.id AS product_id, p.name, "
        "COALESCE(SUM(w.total_carbon_kg), 0) AS total_carbon_kg "
        "FROM wo_carbon_actual w "
        "JOIN work_order wo ON wo.id = w.wo_id "
        "JOIN product p ON p.id = wo.product_id "
        f"{wo_where} "
        "GROUP BY p.id, p.name "
        "ORDER BY total_carbon_kg DESC LIMIT 10",
        wo_params,
    ).fetchall()

    monthly_trend = conn.execute(
        "SELECT to_char(w.created_at, 'YYYY-MM') AS month, "
        "COALESCE(SUM(process_carbon_kg), 0) AS scope1_kg, "
        "COALESCE(SUM(material_carbon_kg), 0) AS scope3_kg "
        f"FROM wo_carbon_actual w{wo_where} "
        "GROUP BY month ORDER BY month",
        wo_params,
    ).fetchall()

    scope1_kg = float(scope13['scope1_kg']) if scope13 else 0.0
    scope2_kg = float(scope2['scope2_kg']) if scope2 else 0.0
    scope3_kg = float(scope13['scope3_kg']) if scope13 else 0.0

    return {
        'scope1_kg': scope1_kg, 'scope2_kg': scope2_kg, 'scope3_kg': scope3_kg,
        'total_kg': scope1_kg + scope2_kg + scope3_kg,
        'by_product': [dict(r) for r in by_product],
        'monthly_trend': [dict(r) for r in monthly_trend],
    }
