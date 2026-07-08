"""
costing_layers_core.py — Qt-free FIFO / LIFO / Weighted-Average costing.

This codebase's only per-unit cost field is ``product.purchase_price``, read
directly by ``costing_core.roll_standard_cost`` (buy-item standard cost) and
``compute_wo_actual_cost`` (WO material actuals) — a single scalar with no
per-lot cost history at all (see ``landed_cost_core.py``'s own docstring,
which documents this same gap and works around it by nudging that one
field). This module is a **parallel, opt-in valuation subsystem**, not a
replacement for standard costing: a product's ``costing_method`` defaults to
``'standard'`` (today's behaviour, completely unchanged — this module never
touches a product that hasn't explicitly opted in), and switching to
``'fifo'``/``'lifo'``/``'average'`` starts tracking discrete cost layers per
receipt and costing issues against them.

**Deliberately does not touch `product.purchase_price`, `roll_standard_cost`,
or `compute_wo_actual_cost`.** Top-10 ERPs treat standard costing and
FIFO/LIFO/weighted-average valuation as two independent, alternative
costing methods — not something to silently blend into one scalar — so this
stays a separate, self-contained ledger with its own valuation and COGS
reporting rather than feeding back into the pinned standard-cost functions.

**Deliberately never modifies `inventory_core.record_transaction`.** That
function is the one universal choke-point every stock movement in this app
already goes through (WMS, cycle counts, the mobile API, the generic manual
adjustment screen) and is exercised by a wide, exact-behaviour test suite.
Rather than retrofitting every one of those call sites, this module provides
its own explicit "front door" — ``receive_with_costing`` / ``issue_with_costing``
— that each call ``record_transaction`` internally (so ``product.amount``
stays the single source of truth for on-hand qty, exactly as for every other
product) and *additionally* create/consume cost layers. This mirrors
``wms_core.receive_and_putaway``'s own precedent of wrapping pinned functions
rather than editing them.

**Known limitation, stated plainly rather than silently papered over:** if a
costed product's inventory is moved through one of the *other* existing
paths (WMS receive/pick, cycle count, the mobile API, generic manual
adjustment) instead of this module's own receive/issue functions,
``product.amount`` still updates correctly (it always does — that part is
untouched), but no cost layer is created or consumed for that movement, so
the layer-tracked quantity can drift from ``product.amount`` over time. The
valuation report surfaces both figures side by side so any drift is visible,
not hidden.

Consumption order per method (mirrors standard inventory-accounting
definitions):
    fifo     — oldest layer consumed first; remaining inventory valued at
               the newest layers' cost.
    lifo     — newest layer consumed first; remaining inventory valued at
               the oldest layers' cost.
    average  — no consumption order to speak of: every issue is costed at
               the pooled weighted-average cost of every remaining layer at
               that moment, and layers are decremented oldest-first purely
               for deterministic bookkeeping (the cost is identical
               regardless of which layer's qty_remaining absorbs it).

If an issue asks for more than the tracked layers cover — e.g. because some
of the on-hand qty predates this feature being turned on for that product,
or arrived through one of the untouched paths above — the uncovered
"shortfall" quantity is costed at the product's current ``purchase_price``
(the same graceful, no-big-bang-migration fallback ``wms_core``'s
unassigned-bin sentinel uses) rather than raising an error.

Every function takes an open connection; the caller owns the transaction
(same convention as wms_core / capacity_planning_core / blanket_po_core).
"""

from __future__ import annotations

from .inventory_core import record_transaction
from .log_utils import get_logger

log = get_logger(__name__)

COSTING_METHODS = ('standard', 'fifo', 'lifo', 'average')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_costing_layers_tables(conn):
    """Create inventory_cost_layer / inventory_cogs_entry / product.costing_method
    if absent. Does not commit."""
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS costing_method "
        "TEXT NOT NULL DEFAULT 'standard'"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_cost_layer (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            unit_cost REAL NOT NULL,
            qty_received REAL NOT NULL,
            qty_remaining REAL NOT NULL,
            reference TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS inventory_cost_layer_product "
        "ON inventory_cost_layer(product_id, id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_cogs_entry (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            qty REAL NOT NULL,
            total_cost REAL NOT NULL,
            method TEXT NOT NULL,
            shortfall_qty REAL NOT NULL DEFAULT 0,
            reference TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS inventory_cogs_entry_product "
        "ON inventory_cogs_entry(product_id, id)"
    )


# ---------------------------------------------------------------------------
# Costing method
# ---------------------------------------------------------------------------

def get_costing_method(conn, product_id):
    row = conn.execute(
        "SELECT costing_method FROM product WHERE id = %s", (product_id,),
    ).fetchone()
    return row['costing_method'] if row and row['costing_method'] else 'standard'


def set_costing_method(conn, product_id, method):
    """Does not commit. Raises ValueError for an unknown method or missing
    product. Switching methods (including back to 'standard') never deletes
    or touches existing cost layers — they simply stop being written to or
    read from until the product is switched back."""
    if method not in COSTING_METHODS:
        raise ValueError(f"Unknown costing method: {method!r}")
    row = conn.execute(
        "UPDATE product SET costing_method = %s WHERE id = %s RETURNING id",
        (method, product_id),
    ).fetchone()
    if not row:
        raise ValueError(f"Product {product_id} not found")


# ---------------------------------------------------------------------------
# Cost layers
# ---------------------------------------------------------------------------

def list_cost_layers(conn, product_id, remaining_only=True):
    sql = "SELECT * FROM inventory_cost_layer WHERE product_id = %s"
    if remaining_only:
        sql += " AND qty_remaining > 0"
    sql += " ORDER BY id"
    rows = conn.execute(sql, (product_id,)).fetchall()
    return [dict(r) for r in rows]


def receive_layer(conn, product_id, qty, unit_cost, reference, created_by):
    """Insert a new cost layer. Does not commit. Raises ValueError for a
    non-positive qty or a negative unit_cost."""
    if qty <= 0:
        raise ValueError("qty must be positive")
    if unit_cost < 0:
        raise ValueError("unit_cost cannot be negative")
    row = conn.execute(
        "INSERT INTO inventory_cost_layer "
        "(product_id, unit_cost, qty_received, qty_remaining, reference, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (product_id, unit_cost, qty, qty, reference or '', created_by),
    ).fetchone()
    return row['id']


def receive_with_costing(conn, product_id, qty, unit_cost, reference, notes, created_by):
    """The front door for receiving a costed product: credits product.amount
    via the existing, unmodified inventory_core.record_transaction, then
    creates a cost layer for the same qty/cost. Does not commit. Raises
    ValueError if the product's costing_method is 'standard' (set a method
    first) or qty/unit_cost are invalid."""
    method = get_costing_method(conn, product_id)
    if method == 'standard':
        raise ValueError(
            "Product is not on a FIFO/LIFO/average costing method — "
            "set one before recording a costed receipt"
        )
    new_amount = record_transaction(
        conn, product_id, 'receive', qty,
        reference=reference, notes=notes, created_by=created_by,
    )
    layer_id = receive_layer(conn, product_id, qty, unit_cost, reference, created_by)
    return {'new_amount': new_amount, 'layer_id': layer_id}


# ---------------------------------------------------------------------------
# Consumption (issue costing)
# ---------------------------------------------------------------------------

def _consume_ordered(conn, product_id, qty, order):
    """Walk remaining layers in the given SQL ORDER BY clause, consuming up
    to qty at each layer's own unit_cost. Returns (total_cost, shortfall_qty)
    — shortfall is whatever qty isn't covered by any tracked layer."""
    remaining_to_cover = qty
    total_cost = 0.0
    layers = conn.execute(
        f"SELECT id, unit_cost, qty_remaining FROM inventory_cost_layer "
        f"WHERE product_id = %s AND qty_remaining > 0 ORDER BY {order}",
        (product_id,),
    ).fetchall()
    for layer in layers:
        if remaining_to_cover <= 1e-9:
            break
        take = min(layer['qty_remaining'], remaining_to_cover)
        total_cost += take * layer['unit_cost']
        conn.execute(
            "UPDATE inventory_cost_layer SET qty_remaining = qty_remaining - %s WHERE id = %s",
            (take, layer['id']),
        )
        remaining_to_cover -= take
    shortfall = max(0.0, remaining_to_cover)
    return total_cost, shortfall


def _consume_fifo(conn, product_id, qty):
    return _consume_ordered(conn, product_id, qty, 'id ASC')


def _consume_lifo(conn, product_id, qty):
    return _consume_ordered(conn, product_id, qty, 'id DESC')


def _consume_average(conn, product_id, qty):
    """Cost the entire qty at the pooled weighted-average cost of every
    remaining layer *before* any of them are decremented, then draw down
    layers oldest-first for deterministic bookkeeping — which layer's
    qty_remaining absorbs the draw-down doesn't affect the cost, since
    every unit on hand is costed identically under this method."""
    pool = conn.execute(
        "SELECT COALESCE(SUM(qty_remaining), 0) AS qty, "
        "COALESCE(SUM(qty_remaining * unit_cost), 0) AS value "
        "FROM inventory_cost_layer WHERE product_id = %s AND qty_remaining > 0",
        (product_id,),
    ).fetchone()
    pool_qty = pool['qty'] or 0.0
    pool_value = pool['value'] or 0.0
    if pool_qty <= 1e-9:
        return 0.0, qty
    avg_cost = pool_value / pool_qty
    covered = min(qty, pool_qty)
    total_cost = covered * avg_cost

    remaining_to_draw = covered
    layers = conn.execute(
        "SELECT id, qty_remaining FROM inventory_cost_layer "
        "WHERE product_id = %s AND qty_remaining > 0 ORDER BY id ASC",
        (product_id,),
    ).fetchall()
    for layer in layers:
        if remaining_to_draw <= 1e-9:
            break
        take = min(layer['qty_remaining'], remaining_to_draw)
        conn.execute(
            "UPDATE inventory_cost_layer SET qty_remaining = qty_remaining - %s WHERE id = %s",
            (take, layer['id']),
        )
        remaining_to_draw -= take

    shortfall = max(0.0, qty - covered)
    return total_cost, shortfall


def consume_cost(conn, product_id, qty, method):
    """Dispatch to the right consumption algorithm. Any shortfall (qty not
    covered by tracked layers) is costed at the product's current
    purchase_price as a graceful fallback. Returns
    {'total_cost', 'unit_cost', 'shortfall_qty'}."""
    if method == 'fifo':
        total_cost, shortfall = _consume_fifo(conn, product_id, qty)
    elif method == 'lifo':
        total_cost, shortfall = _consume_lifo(conn, product_id, qty)
    elif method == 'average':
        total_cost, shortfall = _consume_average(conn, product_id, qty)
    else:
        raise ValueError(f"Unknown costing method: {method!r}")
    if shortfall > 1e-9:
        price_row = conn.execute(
            "SELECT COALESCE(purchase_price, 0) AS purchase_price FROM product WHERE id = %s",
            (product_id,),
        ).fetchone()
        fallback_price = float(price_row['purchase_price']) if price_row else 0.0
        total_cost += shortfall * fallback_price
        log.warning(
            "costing_layers: product_id=%s method=%s shortfall=%.4f "
            "(not covered by tracked layers) costed at purchase_price=%.4f",
            product_id, method, shortfall, fallback_price,
        )
    unit_cost = (total_cost / qty) if qty else 0.0
    return {'total_cost': total_cost, 'unit_cost': unit_cost, 'shortfall_qty': shortfall}


def issue_with_costing(conn, product_id, qty, reference, notes, created_by):
    """The front door for issuing a costed product: debits product.amount
    via the existing, unmodified inventory_core.record_transaction, costs
    the issue against tracked layers per the product's costing_method, and
    records an inventory_cogs_entry row. Does not commit. Raises ValueError
    if the product's costing_method is 'standard'."""
    method = get_costing_method(conn, product_id)
    if method == 'standard':
        raise ValueError(
            "Product is not on a FIFO/LIFO/average costing method — "
            "set one before recording a costed issue"
        )
    new_amount = record_transaction(
        conn, product_id, 'issue', qty,
        reference=reference, notes=notes, created_by=created_by,
    )
    result = consume_cost(conn, product_id, qty, method)
    conn.execute(
        "INSERT INTO inventory_cogs_entry "
        "(product_id, qty, total_cost, method, shortfall_qty, reference, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (product_id, qty, result['total_cost'], method,
         result['shortfall_qty'], reference or '', created_by),
    )
    return {'new_amount': new_amount, **result}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def get_inventory_valuation(conn, product_id):
    """{'product_id', 'method', 'layer_qty_remaining', 'total_value',
    'avg_unit_cost', 'product_amount'} — the last two fields let a caller
    see at a glance whether the layer-tracked qty has drifted from
    product.amount (see module docstring's Known Limitation)."""
    method = get_costing_method(conn, product_id)
    row = conn.execute(
        "SELECT COALESCE(SUM(qty_remaining), 0) AS qty, "
        "COALESCE(SUM(qty_remaining * unit_cost), 0) AS value "
        "FROM inventory_cost_layer WHERE product_id = %s AND qty_remaining > 0",
        (product_id,),
    ).fetchone()
    qty = row['qty'] or 0.0
    value = row['value'] or 0.0
    amount_row = conn.execute(
        "SELECT COALESCE(amount, 0) AS amount FROM product WHERE id = %s", (product_id,),
    ).fetchone()
    return {
        'product_id': product_id,
        'method': method,
        'layer_qty_remaining': qty,
        'total_value': value,
        'avg_unit_cost': (value / qty) if qty else 0.0,
        'product_amount': amount_row['amount'] if amount_row else 0.0,
    }


def list_inventory_valuation(conn):
    """get_inventory_valuation() for every product currently on a
    FIFO/LIFO/average costing method, ordered by name."""
    rows = conn.execute(
        "SELECT id, name FROM product WHERE costing_method != 'standard' ORDER BY name",
    ).fetchall()
    result = []
    for r in rows:
        v = get_inventory_valuation(conn, r['id'])
        v['product_name'] = r['name']
        result.append(v)
    return result


def list_cogs_history(conn, product_id=None, limit=100):
    conds, params = [], []
    if product_id is not None:
        conds.append("product_id = %s")
        params.append(product_id)
    sql = "SELECT * FROM inventory_cogs_entry"
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
