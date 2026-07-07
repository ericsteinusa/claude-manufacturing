"""
landed_cost_core.py — Qt-free Landed Cost Allocation (P3-D).

Freight/duty/broker/insurance costs on an imported PO typically arrive as a
follow-up AP bill *after* goods are received — this is a separate, explicit
action against a PO's already-received line items
(``purchase_orders_core.receive_po_item`` is pinned by exact-SQL-asserting
tests and is neither modified nor auto-hooked here; a landed cost entry is
recorded whenever staff choose to, against whatever ``qty_received`` already
stands at that moment).

There is no lot-level or receipt-level costing anywhere in this codebase —
``product.purchase_price`` is the single per-unit cost field, read directly
by ``costing_core.roll_standard_cost`` (buy-item standard cost) and
``compute_wo_actual_cost`` (material actuals). So "allocated cost updates
inventory cost / impacts COGM and variance reporting" is satisfied by
increasing ``product.purchase_price`` by the per-unit allocated amount —
the next standard-cost roll or WO actual-cost computation picks it up
automatically; there is no separate report to update. This is an
average-cost-style update: it raises the cost for *all* future consumption
of that product, not just the units from this specific receipt, since this
codebase has no per-lot cost attribution anywhere to do better than that.

No GL posting: ``costing_core.post_po_receipt_gl`` exists but has no
callers anywhere in this codebase (PO-receipt GL posting was defined but
never wired up) — landed cost follows that same precedent rather than
inventing new GL machinery.

``product.weight`` is added additively (``ALTER TABLE ... ADD COLUMN IF NOT
EXISTS``, same non-invasive pattern as wms_core.py's ``product.category``)
since no weight/dimension concept existed anywhere for buy items — it's a
genuine product attribute, so it's reusable across future landed-cost
entries for the same product rather than re-entered every time (a per-line
override is still accepted for one-off use).

Every function takes an open connection; the caller owns the transaction
(same convention as wms_core / capacity_planning_core).
"""

from __future__ import annotations

from datetime import datetime

from .log_utils import get_logger

log = get_logger(__name__)

ALLOCATION_METHODS = ('value', 'weight', 'qty')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_landed_cost_tables(conn) -> None:
    """Create landed_cost tables / product.weight if absent. Does not commit."""
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS weight REAL DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS landed_cost (
            id                SERIAL PRIMARY KEY,
            po_id             INTEGER NOT NULL,
            freight           REAL DEFAULT 0,
            duty              REAL DEFAULT 0,
            broker_fee        REAL DEFAULT 0,
            insurance         REAL DEFAULT 0,
            allocation_method TEXT DEFAULT 'value',
            created_at        TEXT DEFAULT '',
            created_by        TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS landed_cost_line (
            id               SERIAL PRIMARY KEY,
            landed_cost_id   INTEGER NOT NULL REFERENCES landed_cost(id) ON DELETE CASCADE,
            po_item_id       INTEGER NOT NULL,
            weight           REAL DEFAULT 0,
            allocated_amount REAL DEFAULT 0
        )
    """)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_receivable_po_items(conn, po_id: int) -> list:
    """PO line items with qty_received > 0, joined to product name/weight —
    the pool a new landed cost allocation can be spread across."""
    rows = conn.execute("""
        SELECT pi.id, pi.description, pi.product_id, p.name AS product_name,
               COALESCE(p.weight, 0) AS product_weight,
               pi.qty_received, pi.unit_price,
               (pi.qty_received * pi.unit_price) AS received_value
        FROM po_item pi
        LEFT JOIN product p ON p.id = pi.product_id
        WHERE pi.po_id = %s AND pi.qty_received > 0
        ORDER BY pi.id
    """, (po_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['unit_price'] = float(d['unit_price'] or 0.0)
        d['received_value'] = float(d['received_value'] or 0.0)
        d['product_weight'] = float(d['product_weight'] or 0.0)
        out.append(d)
    return out


def list_landed_costs(conn, po_id: int) -> list:
    rows = conn.execute("""
        SELECT id, po_id, freight, duty, broker_fee, insurance,
               allocation_method, created_at, created_by,
               (freight + duty + broker_fee + insurance) AS total
        FROM landed_cost
        WHERE po_id = %s
        ORDER BY id DESC
    """, (po_id,)).fetchall()
    return [dict(r) for r in rows]


def get_landed_cost(conn, landed_cost_id: int) -> dict | None:
    header = conn.execute("""
        SELECT id, po_id, freight, duty, broker_fee, insurance,
               allocation_method, created_at, created_by,
               (freight + duty + broker_fee + insurance) AS total
        FROM landed_cost WHERE id = %s
    """, (landed_cost_id,)).fetchone()
    if not header:
        return None
    d = dict(header)
    lines = conn.execute("""
        SELECT lcl.id, lcl.po_item_id, lcl.weight, lcl.allocated_amount,
               pi.description, pi.qty_received, pi.unit_price,
               p.name AS product_name
        FROM landed_cost_line lcl
        JOIN po_item pi ON pi.id = lcl.po_item_id
        LEFT JOIN product p ON p.id = pi.product_id
        WHERE lcl.landed_cost_id = %s
        ORDER BY lcl.id
    """, (landed_cost_id,)).fetchall()
    out_lines = []
    for r in lines:
        line = dict(r)
        line['per_unit_cost'] = (
            line['allocated_amount'] / line['qty_received']
            if line['qty_received'] else 0.0
        )
        out_lines.append(line)
    d['lines'] = out_lines
    return d


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def _allocate_largest_remainder(total: float, weights: list) -> list:
    """Split ``total`` proportionally to ``weights`` so the results sum
    exactly to ``total`` (largest-remainder rounding to the cent)."""
    total_cents = round(total * 100)
    weight_sum = sum(weights)
    if weight_sum <= 0:
        return [0.0] * len(weights)
    raw = [total_cents * w / weight_sum for w in weights]
    floors = [int(x) for x in raw]
    remainder = total_cents - sum(floors)
    remainders = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in remainders[:remainder]:
        floors[i] += 1
    return [c / 100 for c in floors]


def create_landed_cost(conn, po_id: int, freight: float, duty: float,
                       broker_fee: float, insurance: float, method: str,
                       line_weights: dict | None, created_by: str) -> int:
    """Allocate a landed cost across a PO's received line items and roll the
    allocated per-unit amount into each affected product's purchase_price.

    Raises ValueError if the PO has no received items, or (method='weight')
    if every line resolves to zero weight.
    """
    if method not in ALLOCATION_METHODS:
        raise ValueError(f"Unknown allocation method: {method}")
    items = list_receivable_po_items(conn, po_id)
    if not items:
        raise ValueError("This PO has no received line items to allocate against.")

    line_weights = line_weights or {}
    total = float(freight or 0) + float(duty or 0) + float(broker_fee or 0) + float(insurance or 0)

    metrics = []
    weights_used = []
    for it in items:
        if method == 'value':
            metric = it['received_value']
        elif method == 'qty':
            metric = float(it['qty_received'])
        else:  # weight
            w = line_weights.get(it['id'])
            w = float(w) if w not in (None, '') else it['product_weight']
            weights_used.append(w)
            metric = w
        metrics.append(metric)

    if method == 'weight' and sum(metrics) <= 0:
        raise ValueError(
            "No weight available to allocate by — set a weight on the "
            "product(s) or enter one for each line.")

    allocations = _allocate_largest_remainder(total, metrics)

    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO landed_cost "
        "(po_id, freight, duty, broker_fee, insurance, allocation_method, "
        "created_at, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (po_id, float(freight or 0), float(duty or 0), float(broker_fee or 0),
         float(insurance or 0), method, now, created_by or ''),
    ).fetchone()
    landed_cost_id = row['id']

    for it, alloc, w in zip(items, allocations,
                            weights_used or [0.0] * len(items)):
        line_weight = w if method == 'weight' else 0.0
        conn.execute(
            "INSERT INTO landed_cost_line "
            "(landed_cost_id, po_item_id, weight, allocated_amount) "
            "VALUES (%s,%s,%s,%s)",
            (landed_cost_id, it['id'], line_weight, alloc),
        )
        if it['product_id'] and alloc and it['qty_received']:
            per_unit = alloc / it['qty_received']
            conn.execute(
                "UPDATE product SET purchase_price = "
                "COALESCE(purchase_price, 0) + %s WHERE id = %s",
                (per_unit, it['product_id']),
            )

    return landed_cost_id
