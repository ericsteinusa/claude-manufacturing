"""
mrp_web_core.py — Qt-free MRP data layer for the web UI.

Workflow
--------
1. load_mrp_inputs(conn)   — products, BOM structure, on-hand stock,
                             scheduled receipts (open WOs), safety stock
2. get_demand(conn)        — gross demand from confirmed Sales Orders
3. run_mrp(conn)           — calls mrp_core.plan_orders, enriches with names
4. release_plan(conn, …)   — creates Work Orders (make) and draft POs (buy)
"""

from datetime import date, timedelta

from .mrp_core import plan_orders, plan_orders_dated
from .bom_core import explode_quantity
from .work_orders_core import ensure_wo_tables, next_wo_number, create_wo
from .purchase_orders_core import ensure_po_tables, next_po_number, create_po, add_po_item
from .log_utils import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Input loaders
# ---------------------------------------------------------------------------

def load_mrp_inputs(conn):
    """Load all data needed by plan_orders from the database.

    Returns
    -------
    tuple : (products, bom_lines, on_hand, scheduled_receipts, safety)
        products          : {pid: {'name', 'item_type', 'lead_time_days'}}
        bom_lines         : {parent_pid: [(component_pid, qty_per, scrap_pct)]}
        on_hand           : {pid: float}
        scheduled_receipts: {pid: float}  open/in-progress WOs
        safety            : {pid: float}  (zeros — extend to reorder_point if needed)
    """
    rows = conn.execute(
        "SELECT p.id, p.name, "
        "COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.lead_time_days, 0) AS lead_time_days, "
        "COALESCE(p.amount, 0) AS amount, "
        "COALESCE(p.reorder_point, 0) AS safety_stock, "
        "p.supplier_id, s.company_name AS supplier_name "
        "FROM product p "
        "LEFT JOIN supplier s ON s.id = p.supplier_id"
    ).fetchall()
    products = {r['id']: dict(r) for r in rows}
    on_hand = {pid: p['amount'] for pid, p in products.items()}
    safety = {pid: float(p['safety_stock']) for pid, p in products.items()}

    bom_rows = conn.execute(
        "SELECT product_id, component_id, "
        "COALESCE(qty_required, 1.0) AS qty_required, "
        "COALESCE(scrap_pct, 0.0) AS scrap_pct "
        "FROM bom"
    ).fetchall()
    bom_lines: dict = {}
    for r in bom_rows:
        bom_lines.setdefault(r['product_id'], []).append(
            (r['component_id'], r['qty_required'], r['scrap_pct'])
        )

    wo_rows = conn.execute(
        "SELECT product_id, SUM(quantity) AS qty "
        "FROM work_order "
        "WHERE status IN ('draft', 'open', 'in_progress') "
        "AND product_id IS NOT NULL "
        "GROUP BY product_id"
    ).fetchall()
    scheduled = {r['product_id']: float(r['qty']) for r in wo_rows}

    return products, bom_lines, on_hand, scheduled, safety


def get_demand(conn) -> dict:
    """Gross demand from confirmed Sales Orders (product_id → qty)."""
    rows = conn.execute(
        "SELECT si.product_id, SUM(si.qty) AS total "
        "FROM so_item si "
        "JOIN sales_order so ON so.id = si.so_id "
        "WHERE so.status = 'confirmed' AND si.product_id IS NOT NULL "
        "GROUP BY si.product_id"
    ).fetchall()
    return {r['product_id']: float(r['total']) for r in rows}


def get_demand_details(conn) -> list[dict]:
    """Per-product demand rows with name and contributing SO numbers.

    Used to render the demand summary on the MRP home page.
    """
    rows = conn.execute(
        "SELECT p.id, p.name, "
        "COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.amount, 0) AS on_hand, "
        "COALESCE(p.reorder_point, 0) AS safety_stock, "
        "SUM(si.qty) AS demand_qty, "
        "STRING_AGG(so.so_number, ', ' ORDER BY so.so_number) AS so_numbers "
        "FROM so_item si "
        "JOIN sales_order so ON so.id = si.so_id "
        "JOIN product p ON p.id = si.product_id "
        "WHERE so.status = 'confirmed' AND si.product_id IS NOT NULL "
        "GROUP BY p.id ORDER BY p.name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_scheduled_receipts_detail(conn) -> dict:
    """Open WO quantities per product for display on the home page."""
    rows = conn.execute(
        "SELECT product_id, SUM(quantity) AS qty "
        "FROM work_order "
        "WHERE status IN ('draft', 'open', 'in_progress') "
        "AND product_id IS NOT NULL "
        "GROUP BY product_id"
    ).fetchall()
    return {r['product_id']: float(r['qty']) for r in rows}


# ---------------------------------------------------------------------------
# MRP run
# ---------------------------------------------------------------------------

def get_demand_dated(conn) -> dict:
    """Gross demand from confirmed SOs keyed by (product_id, ship_date).

    Returns ``{pid: [(qty, date), ...]}`` where date is the SO ship_date
    (falls back to 30 days from today when ship_date is NULL).
    """
    fallback = (date.today() + timedelta(days=30)).isoformat()
    rows = conn.execute(
        "SELECT si.product_id, SUM(si.qty) AS total, "
        "COALESCE(so.ship_date, %s) AS need_date "
        "FROM so_item si "
        "JOIN sales_order so ON so.id = si.so_id "
        "WHERE so.status = 'confirmed' AND si.product_id IS NOT NULL "
        "GROUP BY si.product_id, need_date",
        (fallback,),
    ).fetchall()
    result: dict = {}
    for r in rows:
        need_date = date.fromisoformat(r['need_date']) if isinstance(r['need_date'], str) else r['need_date']
        result.setdefault(r['product_id'], []).append((float(r['total']), need_date))
    return result


def run_mrp_dated(conn) -> list[dict]:
    """Time-phased MRP run — returns planned orders with start_date and due_date.

    Each row has:
        product_id, product_name, order_type ('make'|'buy'),
        qty, lead_time_days, start_date (ISO), due_date (ISO)
    Sorted by start_date ascending so the earliest actions appear first.
    """
    products_raw, bom_lines, on_hand, scheduled, safety = load_mrp_inputs(conn)
    demand_dated = get_demand_dated(conn)

    products_slim = {
        pid: {'item_type': p['item_type'], 'lead_time_days': p['lead_time_days']}
        for pid, p in products_raw.items()
    }

    planned = plan_orders_dated(
        products_slim, bom_lines, demand_dated, on_hand, scheduled, safety
    )

    name_map = {pid: p['name'] for pid, p in products_raw.items()}
    for item in planned:
        pid = item['product_id']
        item['product_name'] = name_map.get(pid, f"Product {pid}")
        item['supplier_id'] = products_raw.get(pid, {}).get('supplier_id')
        item['supplier_name'] = products_raw.get(pid, {}).get('supplier_name')

    log.info("MRP dated run: %d planned orders (demand products: %d)",
             len(planned), len(demand_dated))
    return planned


def run_mrp(conn) -> list[dict]:
    """Execute a full MRP planning run and return enriched planned orders.

    Each row in the returned list has:
        product_id, product_name, order_type ('make'|'buy'),
        qty, lead_time_days, due_date (ISO string)
    """
    products_raw, bom_lines, on_hand, scheduled, safety = load_mrp_inputs(conn)
    demand = get_demand(conn)

    # plan_orders expects {pid: {'item_type', 'lead_time_days'}}
    products_slim = {
        pid: {'item_type': p['item_type'], 'lead_time_days': p['lead_time_days']}
        for pid, p in products_raw.items()
    }

    planned = plan_orders(products_slim, bom_lines, demand, on_hand, scheduled, safety)

    name_map = {pid: p['name'] for pid, p in products_raw.items()}
    today = date.today()
    for item in planned:
        pid = item['product_id']
        item['product_name'] = name_map.get(pid, f"Product {pid}")
        item['supplier_id'] = products_raw.get(pid, {}).get('supplier_id')
        item['supplier_name'] = products_raw.get(pid, {}).get('supplier_name')
        lt = item.get('lead_time_days') or 0
        item['due_date'] = (today + timedelta(days=lt)).isoformat()
        item['qty'] = round(item['qty'], 4)

    log.info("MRP run: %d planned orders (demand products: %d)",
             len(planned), len(demand))
    return planned


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------

def _explode_to_wo(conn, wo_id: int, product_id: int, wo_quantity: float) -> int:
    """Populate wo_material from the product's single-level BOM.

    Qt-free equivalent of production.bom.explode_bom_to_wo.
    Returns the number of material lines created.
    """
    rows = conn.execute(
        "SELECT b.component_id, "
        "COALESCE(b.qty_required, 1.0) AS qty_required, "
        "COALESCE(b.scrap_pct, 0.0) AS scrap_pct, "
        "COALESCE(b.notes, '') AS notes "
        "FROM bom b WHERE b.product_id = %s",
        (product_id,),
    ).fetchall()
    for r in rows:
        qty = explode_quantity(r['qty_required'], wo_quantity, r['scrap_pct'])
        conn.execute(
            "INSERT INTO wo_material (wo_id, product_id, qty_required, notes) "
            "VALUES (%s, %s, %s, %s)",
            (wo_id, r['component_id'], qty, r['notes'] or 'from BOM'),
        )
    return len(rows)


def release_plan(conn, items: list[dict],
                 released_by: str) -> tuple[list[dict], list[dict]]:
    """Create Work Orders for make items and draft POs for buy items.

    ``items`` is a subset of the list returned by :func:`run_mrp`.
    Returns ``(created_wos, created_pos)`` — lists of summary dicts.
    All inserts share one connection and are NOT committed here; the caller
    commits after a successful return so the whole release is atomic.
    """
    ensure_wo_tables(conn)
    ensure_po_tables(conn)
    today = date.today().isoformat()
    created_wos: list[dict] = []
    created_pos: list[dict] = []

    for item in items:
        pid = item['product_id']
        name = item['product_name']
        qty = item['qty']
        due = item.get('due_date') or today

        if item['order_type'] == 'make':
            wo_num = next_wo_number(conn)
            wo_id = create_wo(
                conn,
                wo_number=wo_num,
                product_id=pid,
                description=f"MRP: {name}",
                quantity=max(1, round(qty)),
                start_date=today,
                due_date=due,
                status='draft',
                notes='Released from MRP plan',
                created_by=released_by,
            )
            _explode_to_wo(conn, wo_id, pid, qty)
            created_wos.append({
                'wo_number': wo_num,
                'wo_id': wo_id,
                'product_name': name,
                'qty': qty,
            })
            log.info("MRP release: WO %s created for %s qty=%.2f",
                     wo_num, name, qty)

        else:  # buy
            supplier_id = item.get('supplier_id')
            supplier_name = item.get('supplier_name')
            notes = (
                f'MRP: {name}' if supplier_id
                else f'MRP: {name} — no preferred supplier on file, assign one before sending'
            )
            po_num = next_po_number(conn)
            po_id = create_po(
                conn,
                po_number=po_num,
                supplier_id=supplier_id,
                order_date=today,
                expected_date=due,
                status='draft',
                notes=notes,
                created_by=released_by,
            )
            add_po_item(
                conn,
                po_id=po_id,
                description=name,
                product_id=pid,
                qty_ordered=max(1, round(qty)),
                unit_price=0.0,
            )
            created_pos.append({
                'po_number': po_num,
                'po_id': po_id,
                'product_name': name,
                'qty': qty,
                'supplier_id': supplier_id,
                'supplier_name': supplier_name,
            })
            log.info("MRP release: PO %s created for %s qty=%.2f supplier=%s",
                     po_num, name, qty, supplier_name or '(none)')

    return created_wos, created_pos
