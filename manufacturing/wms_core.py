"""
wms_core.py — Qt-free Warehouse Management System (P3-B).

Adds a real bin location hierarchy on top of the existing aggregate
``product.amount``, plus put-away rules, pick-list generation from confirmed
sales orders, a pack station, and ship confirmation:

  bin master        — warehouse -> zone -> bin, where aisle/rack/shelf are
                       plain text columns on the bin row rather than their
                       own parent tables (a flat hierarchy — far less schema/
                       CRUD surface for the same functional coverage, matching
                       this codebase's generally denormalized style)
  put-away rules     — match a product's category or ABC class to a target
                       zone; first-match-by-priority, not a scoring model
  pick-list generation — one pick list per confirmed SO, lines ordered by a
                       greedy (zone.pick_sequence, bin.full_code) sort — an
                       "optimized path" in the sense of a simple zone-aware
                       sort, not a real routing/TSP solver
  pack station       — cartons with weight/dimensions, items scanned in
  ship confirmation  — carrier/tracking/date, reusing the existing
                       ``shipment`` table (production_core) and the SO's
                       already-legal confirmed -> shipped transition

Central invariant: every function that changes a bin's tracked quantity
(``wms_bin_stock``) also changes the aggregate (``product.amount``, via
``inventory_core.record_transaction``) in the same open transaction — never
independently. This is enforced by routing all bin-qty writes through
``_adjust_bin_stock``, which is only ever called back-to-back with
``record_transaction`` inside ``receive_and_putaway`` / ``record_pick``.

**Deliberate exception — inter-warehouse transfers** (``ship_transfer`` /
``receive_transfer_line``): a transfer relocates stock from one bin to
another without changing the company-wide total, so it calls
``_adjust_bin_stock`` on both ends but never ``record_transaction`` — there
is nothing to post to ``inventory_transaction``/``product.amount`` for a
move that nets to zero. This is the one place the invariant above doesn't
apply, by design.

No big-bang migration for pre-existing stock: a lazily-created sentinel
"unassigned" zone/bin (``get_or_create_unassigned_bin``) stands in for all
``product.amount`` that predates this feature or was never put away through
it. Assigning a pick line to it, or picking from it, still adjusts
``product.amount`` via ``record_transaction`` but does not touch
``wms_bin_stock`` (there is nothing tracked to decrement) — the system
self-heals as inventory turns over and gets received into real bins.

Explicitly out of scope: ``cycle_count_core``'s legacy grouping by the
free-text ``product.bin`` column is untouched and coexists with the new
``wms_bin``/``wms_bin_stock`` tables — the two are not the same concept and
this module does not migrate one into the other. Lot/serial bin-awareness is
not added. ``sales_orders_core.SO_STATUS_TRANSITIONS`` is not modified — WMS
progress lives entirely on ``wms_pick_list.status``; ``confirm_shipment``
only exercises the already-legal ``confirmed -> shipped`` transition once, at
the very end. One pick list per confirmed SO in v1 — no partial/backorder
splitting across multiple pick lists.

Wave picking (``create_wave`` / ``record_wave_pick``) is a consolidation
layer *on top of* the per-order pick list model above, not a replacement for
it — a wave batches several SOs' pick lists together (``wms_pick_list.wave_id``)
so a picker walks each (product, bin) combination once per wave instead of
once per order, then the qty picked in that single trip is allocated back
down across the affected orders' own pick-list lines by calling
``record_pick`` per line — reused completely unmodified, never duplicated.
Consolidation only covers lines with a real ``product_id`` (text-only SO
lines have no product identity to batch on and must still be picked from
their own order's pick list, same as before wave picking existed).

Cross-docking (``receive_cross_dock``) routes an inbound PO receipt straight
to one specific waiting pick-list line instead of putting it away into
storage first — shares the receiving half with ``receive_and_putaway`` (both
call ``_apply_po_receipt``) but the outbound half calls ``record_pick``
instead of ``_adjust_bin_stock``, so the goods never land in
``wms_bin_stock`` at all. Only pick-list lines still pointing at the
unassigned sentinel bin (genuine stock-outs) are cross-dock candidates — a
line that already has a real bin assigned should be received normally.
**A second place, alongside transfers, where the net change to
``product.amount`` is zero** — the receive credits +delta and
``record_pick``'s own issue debits -delta (this codebase already decrements
``product.amount`` at pick time, not ship-confirm time), which is exactly
correct: cross-docked goods never spend any time as available on-hand
inventory. Both legs still post a real, separately auditable
``inventory_transaction`` row.

RFID tracking (``simulate_tag_read``) is an honestly-simulated hardware
integration — there is no real RFID reader anywhere in this environment, so
a "reader" is a virtual antenna tied to one ``wms_zone``, and a "read" is a
manual "Simulate Read" action standing in for what a real antenna would
capture automatically (the same honest scoping choice
``predictive_maintenance_core.py`` uses for manual sensor-reading entry, and
``ecommerce_core.py`` uses for config-gated outbound HTTP with no live
storefront to call). A tag is a label wrapping a qty of one product already
tracked in a bin — not a new quantity ledger — and reading it at a
*different* reader relocates that qty to a bin in the new reader's zone via
``_adjust_bin_stock`` on both ends, the same real-time, one-step,
net-zero-to-``product.amount`` movement as the cross-docking/transfer
exception above (reused directly, not duplicated), except automatic rather
than a deliberate multi-step business process — that immediacy is the whole
point of RFID versus a manual transfer. Reading the same reader twice in a
row is a no-op "still here" heartbeat, logged but not moved. Tag/bin
quantities can drift from reality if the underlying stock moves through
another path (pick, transfer, cycle count) without also re-reading the tag —
documented plainly rather than hidden, the same drift already accepted for
FIFO/LIFO cost layers and consignment balances.

Every function takes an open connection; the caller owns the transaction
(same convention as routing_core / capacity_planning_core / mrp_web_core).
"""

from __future__ import annotations

from datetime import date

from .cycle_count_core import compute_abc_classes
from .inventory_core import record_transaction
from .mrp_core import next_sequence_number
from .production_core import add_shipment_item, create_shipment
from .purchase_orders_core import receive_po_item
from .sales_orders_core import can_transition, get_so, set_so_status
from .log_utils import get_logger

log = get_logger(__name__)

PUTAWAY_MATCH_TYPES = ('category', 'abc')
PICK_LIST_STATUSES = ('open', 'picked', 'packed', 'shipped', 'cancelled')
PICK_LINE_STATUSES = ('pending', 'picked', 'short')
CARTON_STATUSES = ('open', 'closed', 'shipped')
TRANSFER_STATUSES = ('draft', 'in_transit', 'completed', 'cancelled')
TRANSFER_LINE_STATUSES = ('pending', 'in_transit', 'received')
WAVE_STATUSES = ('open', 'picking', 'completed', 'cancelled')
RFID_TAG_STATUSES = ('active', 'retired')

UNASSIGNED_WAREHOUSE_CODE = 'DEFAULT'
UNASSIGNED_ZONE_CODE = 'UNASSIGNED'
UNASSIGNED_BIN_CODE = 'UNASSIGNED'


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_bin_tables(conn):
    """Create the warehouse/zone/bin/bin-stock/put-away-rule tables if
    absent -- the subset of ensure_wms_tables() with no FK on
    sales_order/so_item/shipment, so callers that only need bin lookups
    and put-away suggestions (receiving_core.py, the Inventory list/detail
    bin-location display) don't transitively require those other modules'
    tables to already exist. Does not commit.

    Split out after a fresh-CI-database load test regression: /inventory/
    started calling ensure_wms_tables() for its new bin-location column,
    which also creates wms_pick_list (REFERENCES sales_order) -- on a
    database where no sales-order page had run yet, hitting /inventory/
    first threw "relation sales_order does not exist" and 500'd, the same
    "live schema can diverge" / FK-ordering class of bug this file's other
    self-heal helpers already guard against."""
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS category TEXT DEFAULT ''"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_warehouse (
            id SERIAL PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_zone (
            id SERIAL PRIMARY KEY,
            warehouse_id INTEGER NOT NULL REFERENCES wms_warehouse(id),
            code TEXT NOT NULL,
            name TEXT DEFAULT '',
            pick_sequence INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (warehouse_id, code)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_bin (
            id SERIAL PRIMARY KEY,
            zone_id INTEGER NOT NULL REFERENCES wms_zone(id),
            aisle TEXT DEFAULT '',
            rack TEXT DEFAULT '',
            shelf TEXT DEFAULT '',
            bin_code TEXT NOT NULL,
            full_code TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (zone_id, bin_code)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_bin_stock (
            id SERIAL PRIMARY KEY,
            bin_id INTEGER NOT NULL REFERENCES wms_bin(id),
            product_id INTEGER NOT NULL REFERENCES product(id),
            qty REAL NOT NULL DEFAULT 0,
            UNIQUE (bin_id, product_id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wms_bin_stock_product "
        "ON wms_bin_stock(product_id)"
    )
    # wms_putaway_rule only FKs to wms_zone (already created above), so it's
    # safe to include here too -- suggest_putaway_bin() (used by both the
    # Receiving screen and the PO put-away screen) needs it and has no
    # reason to depend on sales_order/so_item/shipment either.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_putaway_rule (
            id SERIAL PRIMARY KEY,
            match_type TEXT NOT NULL,
            match_value TEXT NOT NULL,
            zone_id INTEGER NOT NULL REFERENCES wms_zone(id),
            priority INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)


def ensure_wms_tables(conn):
    """Create all WMS tables/columns if absent. Does not commit."""
    ensure_bin_tables(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_wave (
            id SERIAL PRIMARY KEY,
            wave_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'open',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_pick_list (
            id SERIAL PRIMARY KEY,
            pick_number TEXT NOT NULL UNIQUE,
            so_id INTEGER NOT NULL REFERENCES sales_order(id),
            status TEXT NOT NULL DEFAULT 'open',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "ALTER TABLE wms_pick_list ADD COLUMN IF NOT EXISTS "
        "wave_id INTEGER REFERENCES wms_wave(id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wms_pick_list_wave "
        "ON wms_pick_list(wave_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_pick_list_line (
            id SERIAL PRIMARY KEY,
            pick_list_id INTEGER NOT NULL REFERENCES wms_pick_list(id),
            so_item_id INTEGER NOT NULL REFERENCES so_item(id),
            product_id INTEGER REFERENCES product(id),
            description TEXT DEFAULT '',
            qty_ordered REAL NOT NULL,
            qty_picked REAL NOT NULL DEFAULT 0,
            bin_id INTEGER REFERENCES wms_bin(id),
            zone_id INTEGER REFERENCES wms_zone(id),
            pick_sequence INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wms_pick_list_line_pick_list "
        "ON wms_pick_list_line(pick_list_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_carton (
            id SERIAL PRIMARY KEY,
            carton_number TEXT NOT NULL UNIQUE,
            pick_list_id INTEGER NOT NULL REFERENCES wms_pick_list(id),
            status TEXT NOT NULL DEFAULT 'open',
            weight REAL,
            weight_uom TEXT DEFAULT 'lb',
            length REAL,
            width REAL,
            height REAL,
            dim_uom TEXT DEFAULT 'in',
            shipment_id INTEGER REFERENCES shipment(id),
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_carton_item (
            id SERIAL PRIMARY KEY,
            carton_id INTEGER NOT NULL REFERENCES wms_carton(id),
            pick_list_line_id INTEGER NOT NULL REFERENCES wms_pick_list_line(id),
            product_id INTEGER REFERENCES product(id),
            qty REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_transfer (
            id SERIAL PRIMARY KEY,
            transfer_number TEXT NOT NULL UNIQUE,
            from_warehouse_id INTEGER NOT NULL REFERENCES wms_warehouse(id),
            to_warehouse_id INTEGER NOT NULL REFERENCES wms_warehouse(id),
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            shipped_by TEXT DEFAULT '',
            shipped_at TIMESTAMPTZ,
            received_by TEXT DEFAULT '',
            received_at TIMESTAMPTZ,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_transfer_line (
            id SERIAL PRIMARY KEY,
            transfer_id INTEGER NOT NULL REFERENCES wms_transfer(id),
            product_id INTEGER NOT NULL REFERENCES product(id),
            from_bin_id INTEGER NOT NULL REFERENCES wms_bin(id),
            to_bin_id INTEGER REFERENCES wms_bin(id),
            qty REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wms_transfer_line_transfer "
        "ON wms_transfer_line(transfer_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_rfid_reader (
            id SERIAL PRIMARY KEY,
            reader_code TEXT NOT NULL UNIQUE,
            zone_id INTEGER NOT NULL REFERENCES wms_zone(id),
            description TEXT DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_rfid_tag (
            id SERIAL PRIMARY KEY,
            tag_code TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL REFERENCES product(id),
            qty REAL NOT NULL,
            bin_id INTEGER REFERENCES wms_bin(id),
            status TEXT NOT NULL DEFAULT 'active',
            created_by TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wms_rfid_tag_bin ON wms_rfid_tag(bin_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wms_rfid_read_event (
            id SERIAL PRIMARY KEY,
            tag_id INTEGER NOT NULL REFERENCES wms_rfid_tag(id),
            reader_id INTEGER NOT NULL REFERENCES wms_rfid_reader(id),
            from_bin_id INTEGER REFERENCES wms_bin(id),
            to_bin_id INTEGER REFERENCES wms_bin(id),
            moved BOOLEAN NOT NULL DEFAULT FALSE,
            read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS wms_rfid_read_event_tag "
        "ON wms_rfid_read_event(tag_id, id)"
    )


# ---------------------------------------------------------------------------
# Bin master
# ---------------------------------------------------------------------------

def list_warehouses(conn, active_only=True):
    sql = "SELECT * FROM wms_warehouse"
    if active_only:
        sql += " WHERE is_active"
    sql += " ORDER BY code"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def create_warehouse(conn, code, name=''):
    if not code.strip():
        raise ValueError("Warehouse code is required")
    row = conn.execute(
        "INSERT INTO wms_warehouse (code, name) VALUES (%s,%s) RETURNING id",
        (code.strip(), name.strip()),
    ).fetchone()
    return row['id']


def get_or_create_default_warehouse(conn):
    row = conn.execute(
        "SELECT id FROM wms_warehouse ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        return row['id']
    return create_warehouse(conn, 'WH1', 'Main Warehouse')


def list_zones(conn, warehouse_id=None, active_only=True):
    conds, params = [], []
    if warehouse_id is not None:
        conds.append("warehouse_id = %s")
        params.append(warehouse_id)
    if active_only:
        conds.append("is_active")
    sql = "SELECT * FROM wms_zone"
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY pick_sequence, code"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_zone(conn, warehouse_id, code, name='', pick_sequence=0):
    if not code.strip():
        raise ValueError("Zone code is required")
    row = conn.execute(
        "INSERT INTO wms_zone (warehouse_id, code, name, pick_sequence) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (warehouse_id, code.strip(), name.strip(), pick_sequence),
    ).fetchone()
    return row['id']


def update_zone(conn, zone_id, **fields):
    allowed = {'code', 'name', 'pick_sequence', 'is_active'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE wms_zone SET {set_clause} WHERE id = %s",
        list(cols.values()) + [zone_id],
    )


def get_or_create_unassigned_bin(conn, warehouse_id=None):
    """Return the id of the sentinel bin that represents un-located stock —
    lazily creating its warehouse/zone/bin the first time it's needed (see
    module docstring for why this avoids a big-bang migration)."""
    row = conn.execute(
        "SELECT id FROM wms_bin WHERE full_code = %s",
        (f"{UNASSIGNED_ZONE_CODE}-{UNASSIGNED_BIN_CODE}",),
    ).fetchone()
    if row:
        return row['id']
    wh_id = warehouse_id or get_or_create_default_warehouse(conn)
    zone_row = conn.execute(
        "SELECT id FROM wms_zone WHERE warehouse_id = %s AND code = %s",
        (wh_id, UNASSIGNED_ZONE_CODE),
    ).fetchone()
    zone_id = zone_row['id'] if zone_row else create_zone(
        conn, wh_id, UNASSIGNED_ZONE_CODE, 'Unassigned', pick_sequence=999999)
    return create_bin(conn, zone_id, '', '', '', UNASSIGNED_BIN_CODE)


def is_unassigned_bin(conn, bin_id):
    row = conn.execute(
        "SELECT full_code FROM wms_bin WHERE id = %s", (bin_id,),
    ).fetchone()
    return bool(row) and row['full_code'] == f"{UNASSIGNED_ZONE_CODE}-{UNASSIGNED_BIN_CODE}"


def _build_full_code(zone_code, aisle, rack, shelf, bin_code):
    parts = [zone_code] + [p for p in (aisle, rack, shelf) if p] + [bin_code]
    return '-'.join(parts)


def list_bins(conn, zone_id=None, search=None, active_only=True):
    conds, params = [], []
    if zone_id is not None:
        conds.append("b.zone_id = %s")
        params.append(zone_id)
    if search:
        conds.append("b.full_code ILIKE %s")
        params.append(f'%{search}%')
    if active_only:
        conds.append("b.is_active")
    sql = (
        "SELECT b.*, z.code AS zone_code, z.warehouse_id "
        "FROM wms_bin b JOIN wms_zone z ON z.id = b.zone_id"
    )
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY z.pick_sequence, b.full_code"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_bin(conn, bin_id):
    row = conn.execute(
        "SELECT b.*, z.code AS zone_code, z.warehouse_id "
        "FROM wms_bin b JOIN wms_zone z ON z.id = b.zone_id WHERE b.id = %s",
        (bin_id,),
    ).fetchone()
    return dict(row) if row else None


def create_bin(conn, zone_id, aisle, rack, shelf, bin_code):
    if not bin_code.strip():
        raise ValueError("Bin code is required")
    zone = conn.execute(
        "SELECT code FROM wms_zone WHERE id = %s", (zone_id,),
    ).fetchone()
    if not zone:
        raise ValueError(f"Zone {zone_id} not found")
    full_code = _build_full_code(zone['code'], aisle.strip(), rack.strip(), shelf.strip(), bin_code.strip())
    row = conn.execute(
        "INSERT INTO wms_bin (zone_id, aisle, rack, shelf, bin_code, full_code) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (zone_id, aisle.strip(), rack.strip(), shelf.strip(), bin_code.strip(), full_code),
    ).fetchone()
    return row['id']


def update_bin(conn, bin_id, **fields):
    allowed = {'aisle', 'rack', 'shelf', 'bin_code', 'is_active'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE wms_bin SET {set_clause} WHERE id = %s",
        list(cols.values()) + [bin_id],
    )


def deactivate_bin(conn, bin_id):
    conn.execute("UPDATE wms_bin SET is_active = FALSE WHERE id = %s", (bin_id,))


def get_bin_stock(conn, bin_id):
    rows = conn.execute(
        "SELECT s.product_id, p.name AS product_name, s.qty "
        "FROM wms_bin_stock s JOIN product p ON p.id = s.product_id "
        "WHERE s.bin_id = %s AND s.qty > 0 ORDER BY p.name",
        (bin_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_product_bin_stock(conn, product_id):
    """[{bin_id, full_code, zone_id, qty}] for every tracked bin holding
    this product, largest qty first."""
    rows = conn.execute(
        "SELECT s.bin_id, b.full_code, b.zone_id, s.qty "
        "FROM wms_bin_stock s JOIN wms_bin b ON b.id = s.bin_id "
        "WHERE s.product_id = %s AND s.qty > 0 ORDER BY s.qty DESC",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_bin_summary_by_product(conn):
    """{product_id: "CODE (qty), CODE (qty), ..."} for every product with
    tracked WMS bin stock -- lets an inventory list annotate every row with
    its real bin location(s) in one query instead of one per product."""
    rows = conn.execute("""
        SELECT s.product_id,
               STRING_AGG(b.full_code || ' (' || trim(to_char(s.qty, 'FM999999999.##')) || ')',
                          ', ' ORDER BY s.qty DESC) AS bins
        FROM wms_bin_stock s
        JOIN wms_bin b ON b.id = s.bin_id
        WHERE s.qty > 0
        GROUP BY s.product_id
    """).fetchall()
    return {r['product_id']: r['bins'] for r in rows}


def get_warehouse_stock(conn, warehouse_id):
    """[{bin_id, full_code, product_id, product_name, qty}] for every
    tracked (bin, product) with qty > 0 anywhere in a warehouse — what's
    actually available to move out of it, used to populate the transfer
    "add line" picker."""
    rows = conn.execute(
        "SELECT s.bin_id, b.full_code, s.product_id, p.name AS product_name, s.qty "
        "FROM wms_bin_stock s "
        "JOIN wms_bin b ON b.id = s.bin_id "
        "JOIN wms_zone z ON z.id = b.zone_id "
        "JOIN product p ON p.id = s.product_id "
        "WHERE z.warehouse_id = %s AND s.qty > 0 "
        "ORDER BY p.name, b.full_code",
        (warehouse_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _adjust_bin_stock(conn, bin_id, product_id, delta):
    """Upsert wms_bin_stock by delta (positive or negative). Internal —
    only ever called alongside record_transaction, never on its own (see
    module docstring's central invariant). Raises ValueError if the
    resulting qty would go negative."""
    row = conn.execute(
        "SELECT qty FROM wms_bin_stock WHERE bin_id = %s AND product_id = %s",
        (bin_id, product_id),
    ).fetchone()
    current = row['qty'] if row else 0.0
    new_qty = current + delta
    if new_qty < -1e-9:
        raise ValueError(
            f"Cannot remove {abs(delta)} of product {product_id} from bin "
            f"{bin_id} — only {current} tracked there"
        )
    new_qty = max(0.0, new_qty)
    if row:
        conn.execute(
            "UPDATE wms_bin_stock SET qty = %s WHERE bin_id = %s AND product_id = %s",
            (new_qty, bin_id, product_id),
        )
    else:
        conn.execute(
            "INSERT INTO wms_bin_stock (bin_id, product_id, qty) VALUES (%s,%s,%s)",
            (bin_id, product_id, new_qty),
        )
    return new_qty


# ---------------------------------------------------------------------------
# Put-away rules
# ---------------------------------------------------------------------------

def list_putaway_rules(conn, active_only=False):
    sql = (
        "SELECT r.*, z.code AS zone_code, z.warehouse_id "
        "FROM wms_putaway_rule r JOIN wms_zone z ON z.id = r.zone_id"
    )
    if active_only:
        sql += " WHERE r.is_active"
    sql += " ORDER BY r.priority DESC, r.id"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def create_putaway_rule(conn, match_type, match_value, zone_id, priority=0):
    if match_type not in PUTAWAY_MATCH_TYPES:
        raise ValueError(f"Unknown match_type: {match_type!r}")
    if not str(match_value).strip():
        raise ValueError("match_value is required")
    row = conn.execute(
        "INSERT INTO wms_putaway_rule (match_type, match_value, zone_id, priority) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (match_type, str(match_value).strip(), zone_id, priority),
    ).fetchone()
    return row['id']


def update_putaway_rule(conn, rule_id, **fields):
    allowed = {'match_type', 'match_value', 'zone_id', 'priority', 'is_active'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE wms_putaway_rule SET {set_clause} WHERE id = %s",
        list(cols.values()) + [rule_id],
    )


def delete_putaway_rule(conn, rule_id):
    conn.execute("DELETE FROM wms_putaway_rule WHERE id = %s", (rule_id,))


def _least_full_active_bin_in_zone(conn, zone_id):
    """The active bin in a zone with the smallest tracked total quantity —
    a simple greedy heuristic for spreading put-away, not an optimizer."""
    row = conn.execute(
        "SELECT b.id, b.full_code, COALESCE(SUM(s.qty), 0) AS total_qty "
        "FROM wms_bin b LEFT JOIN wms_bin_stock s ON s.bin_id = b.id "
        "WHERE b.zone_id = %s AND b.is_active "
        "GROUP BY b.id, b.full_code ORDER BY total_qty ASC, b.full_code LIMIT 1",
        (zone_id,),
    ).fetchone()
    return dict(row) if row else None


def suggest_putaway_bin(conn, product_id):
    """{bin_id, full_code, rule_id, reason} — first-match-by-priority
    against active put-away rules (category, then ABC class); falls back
    to the unassigned sentinel bin if nothing matches or the matched zone
    has no active bin."""
    product = conn.execute(
        "SELECT category FROM product WHERE id = %s", (product_id,),
    ).fetchone()
    category = (product['category'] or '') if product else ''
    abc_classes = compute_abc_classes(conn)
    abc_class = abc_classes.get(product_id)

    for rule in list_putaway_rules(conn, active_only=True):
        matched = (
            (rule['match_type'] == 'category' and category
             and rule['match_value'].lower() == category.lower())
            or (rule['match_type'] == 'abc' and abc_class
                and rule['match_value'].upper() == abc_class.upper())
        )
        if not matched:
            continue
        bin_row = _least_full_active_bin_in_zone(conn, rule['zone_id'])
        if bin_row:
            return {
                'bin_id': bin_row['id'], 'full_code': bin_row['full_code'],
                'rule_id': rule['id'], 'reason': 'rule match',
            }

    bin_id = get_or_create_unassigned_bin(conn)
    bin_row = get_bin(conn, bin_id)
    assert bin_row is not None
    return {
        'bin_id': bin_id, 'full_code': bin_row['full_code'],
        'rule_id': None, 'reason': 'no rule matched',
    }


# ---------------------------------------------------------------------------
# Receiving put-away
# ---------------------------------------------------------------------------

def _apply_po_receipt(conn, po_item_id, po_id, qty):
    """Shared receiving primitive for both receive_and_putaway and
    receive_cross_dock: validates qty, looks up the PO item, computes the
    delta actually receivable *in this transaction* (clamped to
    qty_ordered so repeated partial receipts never double-count — qty here
    is not the item's new running total, receive_po_item itself stores
    that as an absolute), and updates po_item.qty_received via the pinned
    receive_po_item. Returns the delta. Raises ValueError for a
    non-positive qty, an item that doesn't belong to the given PO, or
    nothing left to receive."""
    if qty <= 0:
        raise ValueError("qty must be positive")
    item = conn.execute(
        "SELECT qty_ordered, qty_received FROM po_item WHERE id = %s AND po_id = %s",
        (po_item_id, po_id),
    ).fetchone()
    if not item:
        raise ValueError(f"PO item {po_item_id} not found on PO {po_id}")
    old_received = item['qty_received'] or 0
    new_total = min(item['qty_ordered'], old_received + qty)
    delta = new_total - old_received
    if delta <= 0:
        raise ValueError("Nothing to receive — item is already fully received")

    rows = receive_po_item(conn, po_item_id, new_total, po_id=po_id)
    if rows == 0:
        raise ValueError(f"Failed to update PO item {po_item_id}")
    return delta


def receive_into_bin(conn, product_id, qty, bin_id, created_by, reference, notes='Receiving'):
    """Credit qty of product_id into inventory and the given bin in one step.

    Generic building block for any receiving flow that wants the same
    "credit inventory + credit bin stock" pairing receive_and_putaway uses
    for PO items -- e.g. the standalone Receiving screen (receiving_core.py),
    which isn't PO-item-shaped. Does not commit.
    """
    new_amount = record_transaction(
        conn, product_id, 'receive', qty,
        reference=reference, notes=notes, created_by=created_by,
    )
    bin_qty = _adjust_bin_stock(conn, bin_id, product_id, qty)
    return {'new_amount': new_amount, 'bin_qty': bin_qty}


def receive_and_putaway(conn, po_item_id, po_id, product_id, qty, bin_id, created_by):
    """Receive qty of a PO item and put it away into bin_id, in one step.

    qty is the amount being received *in this transaction* (not the PO
    item's new running total) — receive_po_item itself stores an absolute
    qty_received, so this looks up the item's current qty_received first and
    clamps the new total to qty_ordered exactly like the existing
    po_receive_item view does, crediting only the resulting delta to
    inventory (so repeated partial receipts never double-count).

    Does not commit. Raises ValueError if the item doesn't belong to the
    given PO or qty is not positive.
    """
    delta = _apply_po_receipt(conn, po_item_id, po_id, qty)
    new_amount = record_transaction(
        conn, product_id, 'receive', delta,
        reference=f'PO item {po_item_id}', notes='WMS put-away',
        created_by=created_by,
    )
    bin_qty = _adjust_bin_stock(conn, bin_id, product_id, delta)
    return {'received_qty': delta, 'new_amount': new_amount, 'bin_qty': bin_qty}


def credit_unassigned_receipt(conn, product_id, delta, reference, created_by):
    """Credit a quantity received through the legacy (non-WMS) PO receive
    screen into inventory, landing in the unassigned bin since no bin was
    chosen. Lets that screen keep crediting product.amount regardless of
    whether the caller ever uses the dedicated /wms/receive/ put-away flow.
    No-ops if delta <= 0 (the legacy screen also allows reducing a
    previously-recorded qty_received, which isn't a receipt event). Does
    not commit.
    """
    if delta <= 0 or not product_id:
        return None
    record_transaction(
        conn, product_id, 'receive', delta,
        reference=reference, notes='PO receipt', created_by=created_by,
    )
    bin_id = get_or_create_unassigned_bin(conn)
    return _adjust_bin_stock(conn, bin_id, product_id, delta)


# ---------------------------------------------------------------------------
# Pick list generation
# ---------------------------------------------------------------------------

def list_confirmed_sos_awaiting_pick(conn):
    rows = conn.execute("""
        SELECT so.id, so.so_number, so.order_date, so.ship_date
        FROM sales_order so
        LEFT JOIN wms_pick_list wpl
               ON wpl.so_id = so.id AND wpl.status != 'cancelled'
        WHERE so.status = 'confirmed' AND wpl.id IS NULL
        ORDER BY so.order_date NULLS LAST, so.id
    """).fetchall()
    return [dict(r) for r in rows]


_SEQUENCE_TABLES = {
    'PICK-': ('wms_pick_list', 'pick_number'),
    'CTN-': ('wms_carton', 'carton_number'),
    'TRF-': ('wms_transfer', 'transfer_number'),
    'WAVE-': ('wms_wave', 'wave_number'),
}


def _next_sequence(conn, prefix, today=None):
    """Gap-safe max-suffix+1 numbering for a WMS prefix, generated on the
    caller's own connection (see mrp_core.next_sequence_number)."""
    table, column = _SEQUENCE_TABLES[prefix]
    year = (today or date.today()).year
    full_prefix = f"{prefix}{year}-"
    rows = conn.execute(
        f"SELECT {column} AS num FROM {table} WHERE {column} LIKE %s",
        (full_prefix + '%',),
    ).fetchall()
    return next_sequence_number([r['num'] for r in rows], full_prefix)


def generate_pick_list(conn, so_id, created_by):
    """Create a pick list + one line per so_item for a confirmed SO,
    assigning the best tracked bin per line (or the unassigned sentinel)
    and ordering lines by a greedy (zone.pick_sequence, bin.full_code)
    sort — the "optimized path," not a real routing solver. Does not
    commit. Raises ValueError if the SO isn't confirmed or already has a
    non-cancelled pick list.
    """
    so = get_so(conn, so_id)
    if not so:
        raise ValueError(f"SO {so_id} not found")
    if so['status'] != 'confirmed':
        raise ValueError(f"SO {so_id} is not confirmed (status={so['status']})")
    existing = conn.execute(
        "SELECT id FROM wms_pick_list WHERE so_id = %s AND status != 'cancelled'",
        (so_id,),
    ).fetchone()
    if existing:
        raise ValueError(f"SO {so_id} already has an active pick list ({existing['id']})")

    so_items = conn.execute(
        "SELECT id, product_id, description, qty FROM so_item WHERE so_id = %s ORDER BY id",
        (so_id,),
    ).fetchall()
    if not so_items:
        raise ValueError(f"SO {so_id} has no line items to pick")

    pick_number = _next_sequence(conn, 'PICK-')
    pick_list_id = conn.execute(
        "INSERT INTO wms_pick_list (pick_number, so_id, created_by) "
        "VALUES (%s,%s,%s) RETURNING id",
        (pick_number, so_id, created_by),
    ).fetchone()['id']

    unassigned_bin_id = None
    line_ids = []
    for item in so_items:
        qty_ordered = item['qty'] or 0
        bin_id = zone_id = None
        if item['product_id']:
            candidates = get_product_bin_stock(conn, item['product_id'])
            best = next((c for c in candidates if c['qty'] >= qty_ordered), None)
            if best:
                bin_id, zone_id = best['bin_id'], best['zone_id']
        if bin_id is None:
            if unassigned_bin_id is None:
                unassigned_bin_id = get_or_create_unassigned_bin(conn)
            unassigned = get_bin(conn, unassigned_bin_id)
            assert unassigned is not None
            bin_id, zone_id = unassigned_bin_id, unassigned['zone_id']
        row = conn.execute(
            "INSERT INTO wms_pick_list_line "
            "(pick_list_id, so_item_id, product_id, description, qty_ordered, bin_id, zone_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (pick_list_id, item['id'], item['product_id'], item['description'] or '',
             qty_ordered, bin_id, zone_id),
        ).fetchone()
        line_ids.append(row['id'])

    _resequence_pick_list(conn, pick_list_id)
    return pick_list_id


def _resequence_pick_list(conn, pick_list_id):
    """Recompute pick_sequence for every line on a pick list, sorted by
    (zone.pick_sequence, bin.full_code) ascending — a greedy path
    ordering, not a solver."""
    rows = conn.execute(
        "SELECT l.id, COALESCE(z.pick_sequence, 999999) AS zone_seq, "
        "COALESCE(b.full_code, '') AS full_code "
        "FROM wms_pick_list_line l "
        "LEFT JOIN wms_zone z ON z.id = l.zone_id "
        "LEFT JOIN wms_bin b ON b.id = l.bin_id "
        "WHERE l.pick_list_id = %s",
        (pick_list_id,),
    ).fetchall()
    ordered = sorted(rows, key=lambda r: (r['zone_seq'], r['full_code']))
    for seq, row in enumerate(ordered, start=1):
        conn.execute(
            "UPDATE wms_pick_list_line SET pick_sequence = %s WHERE id = %s",
            (seq, row['id']),
        )


def list_pick_lists(conn, status=None):
    conds, params = [], []
    if status:
        conds.append("wpl.status = %s")
        params.append(status)
    sql = (
        "SELECT wpl.*, so.so_number FROM wms_pick_list wpl "
        "JOIN sales_order so ON so.id = wpl.so_id"
    )
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY wpl.created_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_pick_list(conn, pick_list_id):
    row = conn.execute(
        "SELECT wpl.*, so.so_number FROM wms_pick_list wpl "
        "JOIN sales_order so ON so.id = wpl.so_id WHERE wpl.id = %s",
        (pick_list_id,),
    ).fetchone()
    return dict(row) if row else None


def get_pick_list_lines(conn, pick_list_id):
    rows = conn.execute(
        "SELECT l.*, p.name AS product_name, b.full_code AS bin_full_code "
        "FROM wms_pick_list_line l "
        "LEFT JOIN product p ON p.id = l.product_id "
        "LEFT JOIN wms_bin b ON b.id = l.bin_id "
        "WHERE l.pick_list_id = %s ORDER BY l.pick_sequence",
        (pick_list_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def record_pick(conn, line_id, qty_picked, created_by):
    """Record a pick for one line: updates qty_picked/status, adjusts
    product.amount via record_transaction, and decrements the source bin's
    tracked qty (unless it's the unassigned sentinel). Advances the parent
    pick list to 'picked' once every line is resolved. Does not commit.
    """
    line = conn.execute(
        "SELECT l.*, wpl.pick_number FROM wms_pick_list_line l "
        "JOIN wms_pick_list wpl ON wpl.id = l.pick_list_id WHERE l.id = %s",
        (line_id,),
    ).fetchone()
    if not line:
        raise ValueError(f"Pick list line {line_id} not found")
    if qty_picked <= 0:
        raise ValueError("qty_picked must be positive")

    new_status = 'picked' if qty_picked >= line['qty_ordered'] else 'short'
    conn.execute(
        "UPDATE wms_pick_list_line SET qty_picked = %s, status = %s WHERE id = %s",
        (qty_picked, new_status, line_id),
    )

    if line['product_id']:
        record_transaction(
            conn, line['product_id'], 'issue', qty_picked,
            reference=line['pick_number'], notes='WMS pick',
            created_by=created_by,
        )
        if line['bin_id'] and not is_unassigned_bin(conn, line['bin_id']):
            _adjust_bin_stock(conn, line['bin_id'], line['product_id'], -qty_picked)

    remaining = conn.execute(
        "SELECT COUNT(*) AS n FROM wms_pick_list_line "
        "WHERE pick_list_id = %s AND status = 'pending'",
        (line['pick_list_id'],),
    ).fetchone()['n']
    if remaining == 0:
        conn.execute(
            "UPDATE wms_pick_list SET status = 'picked' WHERE id = %s",
            (line['pick_list_id'],),
        )
    return new_status


# ---------------------------------------------------------------------------
# Cross-docking
# ---------------------------------------------------------------------------
#
# Cross-docking routes an inbound PO receipt straight to a waiting outbound
# order instead of putting it away into storage first — the highest-value
# case is a genuine stock-out: a pending pick-list line with nothing tracked
# in any bin (pointing at the unassigned sentinel), with inbound stock
# arriving right now. This shares the receiving half with
# receive_and_putaway (_apply_po_receipt + record_transaction) but the
# outbound half calls record_pick — completely unmodified — instead of
# _adjust_bin_stock, so the cross-docked goods never land in wms_bin_stock
# at all; they move receive -> outbound in one step, the defining
# characteristic of cross-docking. A line that already has a real bin
# assigned isn't a cross-dock candidate — receive that one normally and let
# it be picked from there.

def find_cross_dock_candidates(conn, product_id):
    """Pending pick-list lines for product_id currently pointing at the
    unassigned sentinel bin — genuine unfulfilled outbound demand with
    nothing in stock, the opportunities a receiving clerk could cross-dock
    an incoming PO receipt straight into instead of putting it away first.
    Ordered oldest pick list first (first-come-first-served)."""
    rows = conn.execute(
        "SELECT l.id, l.qty_ordered, l.pick_list_id, wpl.pick_number, so.so_number "
        "FROM wms_pick_list_line l "
        "JOIN wms_pick_list wpl ON wpl.id = l.pick_list_id "
        "JOIN sales_order so ON so.id = wpl.so_id "
        "JOIN wms_bin b ON b.id = l.bin_id "
        "WHERE l.product_id = %s AND l.status = 'pending' "
        "AND b.full_code = %s "
        "ORDER BY wpl.id, l.id",
        (product_id, f"{UNASSIGNED_ZONE_CODE}-{UNASSIGNED_BIN_CODE}"),
    ).fetchall()
    return [dict(r) for r in rows]


def receive_cross_dock(conn, po_item_id, po_id, product_id, qty, pick_list_line_id, created_by):
    """Cross-dock a PO receipt straight to one specific waiting pick-list
    line instead of putting it away into storage first. Does not commit.

    **product.amount nets to unchanged, by design** — record_transaction
    credits +delta for the receipt, then record_pick's own internal
    record_transaction call debits -delta for the pick (this codebase's
    existing model already decrements product.amount at pick time, not at
    ship-confirm time — see confirm_shipment, which posts no inventory
    transaction of its own). Both are real, separately auditable
    inventory_transaction rows (a receive and an issue), they simply net
    to zero because the goods genuinely never become available on-hand
    inventory at any point — that dwell time is the entire thing
    cross-docking exists to skip. This is the same "moves without changing
    the company-wide total" property the module docstring already
    documents for inter-warehouse transfers, arrived at here for free by
    composing two existing, unmodified functions rather than needing its
    own deliberate exception.

    Raises ValueError for a non-positive qty, if the pick-list line isn't a
    pending line for this exact product, the line's bin isn't the
    unassigned sentinel (it already has real stock earmarked — receive
    normally instead), or qty exceeds what that one line still needs
    (cross-dock up to the line's need in this action; receive any excess
    separately via receive_and_putaway) — plus whatever _apply_po_receipt
    itself raises for an item that doesn't belong to the PO.
    """
    if qty <= 0:
        raise ValueError("qty must be positive")
    line = conn.execute(
        "SELECT id, product_id, qty_ordered, status, bin_id "
        "FROM wms_pick_list_line WHERE id = %s",
        (pick_list_line_id,),
    ).fetchone()
    if not line:
        raise ValueError(f"Pick list line {pick_list_line_id} not found")
    if line['product_id'] != product_id:
        raise ValueError("That pick list line is for a different product")
    if line['status'] != 'pending':
        raise ValueError(
            f"Pick list line {pick_list_line_id} is not pending (status={line['status']})")
    if not is_unassigned_bin(conn, line['bin_id']):
        raise ValueError(
            "This line already has a real bin assigned — receive it "
            "normally and it will be picked from there")
    if qty > line['qty_ordered']:
        raise ValueError(
            f"qty {qty:g} exceeds what this line needs ({line['qty_ordered']:g}) — "
            "cross-dock up to the line's need, then receive any excess separately")

    delta = _apply_po_receipt(conn, po_item_id, po_id, qty)
    new_amount = record_transaction(
        conn, product_id, 'receive', delta,
        reference=f'PO item {po_item_id}', notes='Cross-dock receipt',
        created_by=created_by,
    )
    pick_status = record_pick(conn, pick_list_line_id, delta, created_by)
    return {'received_qty': delta, 'new_amount': new_amount, 'pick_status': pick_status}


# ---------------------------------------------------------------------------
# Pack station
# ---------------------------------------------------------------------------

def create_carton(conn, pick_list_id, created_by):
    carton_number = _next_sequence(conn, 'CTN-')
    row = conn.execute(
        "INSERT INTO wms_carton (carton_number, pick_list_id, created_by) "
        "VALUES (%s,%s,%s) RETURNING id",
        (carton_number, pick_list_id, created_by),
    ).fetchone()
    return row['id']


def _packed_qty_for_line(conn, pick_list_line_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS packed FROM wms_carton_item "
        "WHERE pick_list_line_id = %s",
        (pick_list_line_id,),
    ).fetchone()
    return row['packed'] or 0.0


def add_carton_item(conn, carton_id, pick_list_line_id, qty):
    if qty <= 0:
        raise ValueError("qty must be positive")
    line = conn.execute(
        "SELECT product_id, qty_picked FROM wms_pick_list_line WHERE id = %s",
        (pick_list_line_id,),
    ).fetchone()
    if not line:
        raise ValueError(f"Pick list line {pick_list_line_id} not found")
    already_packed = _packed_qty_for_line(conn, pick_list_line_id)
    remaining = (line['qty_picked'] or 0) - already_packed
    if qty > remaining + 1e-9:
        raise ValueError(
            f"Cannot pack {qty} — only {remaining} picked-but-unpacked for this line"
        )
    row = conn.execute(
        "INSERT INTO wms_carton_item (carton_id, pick_list_line_id, product_id, qty) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (carton_id, pick_list_line_id, line['product_id'], qty),
    ).fetchone()
    return row['id']


def set_carton_dimensions(conn, carton_id, weight=None, weight_uom='lb',
                          length=None, width=None, height=None, dim_uom='in'):
    conn.execute(
        "UPDATE wms_carton SET weight=%s, weight_uom=%s, length=%s, width=%s, "
        "height=%s, dim_uom=%s WHERE id=%s",
        (weight, weight_uom, length, width, height, dim_uom, carton_id),
    )


def close_carton(conn, carton_id):
    conn.execute("UPDATE wms_carton SET status = 'closed' WHERE id = %s", (carton_id,))


def get_cartons_for_pick_list(conn, pick_list_id):
    rows = conn.execute(
        "SELECT * FROM wms_carton WHERE pick_list_id = %s ORDER BY id",
        (pick_list_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_carton_items(conn, carton_id):
    rows = conn.execute(
        "SELECT ci.*, p.name AS product_name, l.description "
        "FROM wms_carton_item ci "
        "LEFT JOIN product p ON p.id = ci.product_id "
        "JOIN wms_pick_list_line l ON l.id = ci.pick_list_line_id "
        "WHERE ci.carton_id = %s ORDER BY ci.id",
        (carton_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_pick_list_packed(conn, pick_list_id):
    """Guard: every picked line must be fully allocated to a closed
    carton. Raises ValueError otherwise. Does not commit."""
    lines = conn.execute(
        "SELECT id, qty_picked FROM wms_pick_list_line "
        "WHERE pick_list_id = %s AND status = 'picked'",
        (pick_list_id,),
    ).fetchall()
    open_cartons = conn.execute(
        "SELECT COUNT(*) AS n FROM wms_carton "
        "WHERE pick_list_id = %s AND status = 'open'",
        (pick_list_id,),
    ).fetchone()['n']
    if open_cartons:
        raise ValueError("All cartons must be closed before marking the pick list packed")
    for line in lines:
        packed = _packed_qty_for_line(conn, line['id'])
        if packed + 1e-9 < (line['qty_picked'] or 0):
            raise ValueError(f"Pick list line {line['id']} is not fully packed")
    conn.execute(
        "UPDATE wms_pick_list SET status = 'packed' WHERE id = %s",
        (pick_list_id,),
    )


# ---------------------------------------------------------------------------
# Ship confirmation
# ---------------------------------------------------------------------------

def confirm_shipment(conn, pick_list_id, carrier, tracking_number, ship_date, created_by):
    """Confirm shipment of a packed pick list: creates a shipment (reusing
    production_core), one shipment_item per pick-list line, closes out the
    cartons, marks the pick list shipped, and — if legal — transitions the
    SO to 'shipped'. Does not commit. Raises ValueError if the pick list
    isn't packed.
    """
    pick_list = get_pick_list(conn, pick_list_id)
    if not pick_list:
        raise ValueError(f"Pick list {pick_list_id} not found")
    if pick_list['status'] != 'packed':
        raise ValueError(f"Pick list {pick_list_id} is not packed (status={pick_list['status']})")

    lines = get_pick_list_lines(conn, pick_list_id)
    shipment_id = create_shipment(
        conn, pick_list['so_id'], ship_date, carrier, tracking_number,
        status='in_transit', notes=f"WMS {pick_list['pick_number']}",
        created_by=created_by,
    )
    for line in lines:
        if line['status'] != 'picked':
            continue
        add_shipment_item(
            conn, shipment_id, line['description'] or line.get('product_name') or 'Item',
            line['product_id'], line['qty_picked'],
        )

    conn.execute(
        "UPDATE wms_carton SET shipment_id = %s, status = 'shipped' WHERE pick_list_id = %s",
        (shipment_id, pick_list_id),
    )
    conn.execute(
        "UPDATE wms_pick_list SET status = 'shipped' WHERE id = %s",
        (pick_list_id,),
    )

    so = get_so(conn, pick_list['so_id'])
    if so and can_transition(so['status'], 'shipped'):
        set_so_status(conn, pick_list['so_id'], 'shipped')

    return shipment_id


# ---------------------------------------------------------------------------
# Inter-warehouse transfers
# ---------------------------------------------------------------------------
#
# A transfer relocates stock from a bin in one warehouse to a bin in another
# — draft (being built) -> in_transit (shipped, stock left the source bin
# but hasn't landed anywhere yet) -> completed (every line received). The
# destination bin per line is chosen at receive time, not when the line is
# added, since the receiving warehouse may reorganize bins in the time it
# takes goods to actually arrive. See the module docstring's "Deliberate
# exception" note for why this never touches product.amount.

def list_transfers(conn, status=None):
    conds, params = [], []
    if status:
        conds.append("t.status = %s")
        params.append(status)
    sql = (
        "SELECT t.*, wf.code AS from_warehouse_code, wt.code AS to_warehouse_code "
        "FROM wms_transfer t "
        "JOIN wms_warehouse wf ON wf.id = t.from_warehouse_id "
        "JOIN wms_warehouse wt ON wt.id = t.to_warehouse_id"
    )
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY t.created_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_transfer(conn, transfer_id):
    row = conn.execute(
        "SELECT t.*, wf.code AS from_warehouse_code, wt.code AS to_warehouse_code "
        "FROM wms_transfer t "
        "JOIN wms_warehouse wf ON wf.id = t.from_warehouse_id "
        "JOIN wms_warehouse wt ON wt.id = t.to_warehouse_id "
        "WHERE t.id = %s",
        (transfer_id,),
    ).fetchone()
    return dict(row) if row else None


def get_transfer_lines(conn, transfer_id):
    rows = conn.execute(
        "SELECT l.*, p.name AS product_name, "
        "fb.full_code AS from_bin_full_code, tb.full_code AS to_bin_full_code "
        "FROM wms_transfer_line l "
        "JOIN product p ON p.id = l.product_id "
        "JOIN wms_bin fb ON fb.id = l.from_bin_id "
        "LEFT JOIN wms_bin tb ON tb.id = l.to_bin_id "
        "WHERE l.transfer_id = %s ORDER BY l.id",
        (transfer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_transfer(conn, from_warehouse_id, to_warehouse_id, created_by, notes=''):
    """Create a draft transfer between two distinct warehouses. Does not
    commit. Raises ValueError if the warehouses are the same or either
    doesn't exist."""
    if from_warehouse_id == to_warehouse_id:
        raise ValueError("Source and destination warehouses must differ")
    for wh_id, label in ((from_warehouse_id, 'from'), (to_warehouse_id, 'to')):
        row = conn.execute(
            "SELECT id FROM wms_warehouse WHERE id = %s", (wh_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"{label}_warehouse_id {wh_id} not found")
    transfer_number = _next_sequence(conn, 'TRF-')
    row = conn.execute(
        "INSERT INTO wms_transfer "
        "(transfer_number, from_warehouse_id, to_warehouse_id, created_by, notes) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (transfer_number, from_warehouse_id, to_warehouse_id, created_by, notes.strip()),
    ).fetchone()
    return row['id']


def add_transfer_line(conn, transfer_id, product_id, from_bin_id, qty):
    """Add a line to a draft transfer: qty of product_id to move out of
    from_bin_id, which must belong to the transfer's source warehouse.
    Does not validate qty against the bin's tracked stock here — that's
    enforced authoritatively by _adjust_bin_stock at ship time, since stock
    in the bin can still change between adding a line and shipping. Does
    not commit. Raises ValueError if the transfer isn't a draft, qty isn't
    positive, or from_bin_id isn't in the source warehouse."""
    if qty <= 0:
        raise ValueError("qty must be positive")
    transfer = conn.execute(
        "SELECT status, from_warehouse_id FROM wms_transfer WHERE id = %s",
        (transfer_id,),
    ).fetchone()
    if not transfer:
        raise ValueError(f"Transfer {transfer_id} not found")
    if transfer['status'] != 'draft':
        raise ValueError(f"Transfer {transfer_id} is not draft (status={transfer['status']})")
    bin_row = conn.execute(
        "SELECT z.warehouse_id FROM wms_bin b JOIN wms_zone z ON z.id = b.zone_id WHERE b.id = %s",
        (from_bin_id,),
    ).fetchone()
    if not bin_row:
        raise ValueError(f"Bin {from_bin_id} not found")
    if bin_row['warehouse_id'] != transfer['from_warehouse_id']:
        raise ValueError("from_bin_id does not belong to the transfer's source warehouse")
    row = conn.execute(
        "INSERT INTO wms_transfer_line (transfer_id, product_id, from_bin_id, qty) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (transfer_id, product_id, from_bin_id, qty),
    ).fetchone()
    return row['id']


def remove_transfer_line(conn, line_id):
    """Remove a line from a transfer that hasn't shipped yet. Does not
    commit. Raises ValueError if the line doesn't exist or its transfer has
    already shipped."""
    line = conn.execute(
        "SELECT t.status AS transfer_status FROM wms_transfer_line l "
        "JOIN wms_transfer t ON t.id = l.transfer_id WHERE l.id = %s",
        (line_id,),
    ).fetchone()
    if not line:
        raise ValueError(f"Transfer line {line_id} not found")
    if line['transfer_status'] != 'draft':
        raise ValueError("Cannot remove a line once the transfer has shipped")
    conn.execute("DELETE FROM wms_transfer_line WHERE id = %s", (line_id,))


def ship_transfer(conn, transfer_id, created_by):
    """Ship a draft transfer: decrements each line's source bin (raising
    ValueError via _adjust_bin_stock if that bin doesn't have enough
    tracked stock) and advances every line and the transfer itself to
    'in_transit'. Deliberately does not touch product.amount — see the
    module docstring's "Deliberate exception" note; a transfer's net effect
    on the company-wide total is zero. Does not commit. Raises ValueError
    if the transfer isn't a draft or has no lines."""
    transfer = get_transfer(conn, transfer_id)
    if not transfer:
        raise ValueError(f"Transfer {transfer_id} not found")
    if transfer['status'] != 'draft':
        raise ValueError(f"Transfer {transfer_id} is not draft (status={transfer['status']})")
    lines = get_transfer_lines(conn, transfer_id)
    if not lines:
        raise ValueError(f"Transfer {transfer_id} has no lines to ship")
    for line in lines:
        _adjust_bin_stock(conn, line['from_bin_id'], line['product_id'], -line['qty'])
        conn.execute(
            "UPDATE wms_transfer_line SET status = 'in_transit' WHERE id = %s",
            (line['id'],),
        )
    conn.execute(
        "UPDATE wms_transfer SET status = 'in_transit', shipped_by = %s, shipped_at = NOW() "
        "WHERE id = %s",
        (created_by, transfer_id),
    )


def receive_transfer_line(conn, line_id, to_bin_id, created_by):
    """Receive one in-transit transfer line into to_bin_id, which must
    belong to the transfer's destination warehouse. Credits the
    destination bin via _adjust_bin_stock (again, never product.amount —
    see module docstring). Once every line on the transfer is received,
    advances the transfer itself to 'completed'. Does not commit. Raises
    ValueError if the line isn't in_transit or to_bin_id is in the wrong
    warehouse."""
    line = conn.execute(
        "SELECT l.*, t.to_warehouse_id FROM wms_transfer_line l "
        "JOIN wms_transfer t ON t.id = l.transfer_id WHERE l.id = %s",
        (line_id,),
    ).fetchone()
    if not line:
        raise ValueError(f"Transfer line {line_id} not found")
    if line['status'] != 'in_transit':
        raise ValueError(f"Transfer line {line_id} is not in transit (status={line['status']})")
    bin_row = conn.execute(
        "SELECT z.warehouse_id FROM wms_bin b JOIN wms_zone z ON z.id = b.zone_id WHERE b.id = %s",
        (to_bin_id,),
    ).fetchone()
    if not bin_row:
        raise ValueError(f"Bin {to_bin_id} not found")
    if bin_row['warehouse_id'] != line['to_warehouse_id']:
        raise ValueError("to_bin_id does not belong to the transfer's destination warehouse")

    _adjust_bin_stock(conn, to_bin_id, line['product_id'], line['qty'])
    conn.execute(
        "UPDATE wms_transfer_line SET to_bin_id = %s, status = 'received' WHERE id = %s",
        (to_bin_id, line_id),
    )

    remaining = conn.execute(
        "SELECT COUNT(*) AS n FROM wms_transfer_line "
        "WHERE transfer_id = %s AND status != 'received'",
        (line['transfer_id'],),
    ).fetchone()['n']
    if remaining == 0:
        conn.execute(
            "UPDATE wms_transfer SET status = 'completed', received_by = %s, received_at = NOW() "
            "WHERE id = %s",
            (created_by, line['transfer_id']),
        )


def cancel_transfer(conn, transfer_id):
    """Cancel a transfer that hasn't shipped yet. Does not commit. Raises
    ValueError if the transfer doesn't exist or has already shipped —
    reversing an in-transit transfer would itself be a transfer back to
    the source, which is out of scope here; create one separately once the
    original is received."""
    transfer = get_transfer(conn, transfer_id)
    if not transfer:
        raise ValueError(f"Transfer {transfer_id} not found")
    if transfer['status'] != 'draft':
        raise ValueError(
            f"Cannot cancel transfer {transfer_id} — status is "
            f"{transfer['status']}, not draft"
        )
    conn.execute("UPDATE wms_transfer SET status = 'cancelled' WHERE id = %s", (transfer_id,))


# ---------------------------------------------------------------------------
# Wave picking
# ---------------------------------------------------------------------------
#
# A wave batches several confirmed SOs' pick lists together so a picker can
# walk each (product, bin) combination once per wave instead of once per
# order — see the module docstring's "Wave picking" paragraph. open (being
# built / not yet started) -> picking (at least one consolidated pick
# recorded) -> completed (every member line resolved), or cancelled (only
# while still open, before any picking has begun).

def _sync_wave_status(conn, wave_id, current_status=None):
    """Lazily recompute a wave's status from its member pick-list lines —
    same precedent as blanket_po_core / consignment_core's status sync.
    Cancelled is terminal and short-circuits without a query."""
    if current_status is None:
        row = conn.execute("SELECT status FROM wms_wave WHERE id = %s", (wave_id,)).fetchone()
        if not row:
            return ''
        current_status = row['status']
    if current_status == 'cancelled':
        return current_status

    counts = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE l.status = 'pending') AS pending, "
        "COUNT(*) FILTER (WHERE l.status != 'pending') AS resolved "
        "FROM wms_pick_list_line l "
        "JOIN wms_pick_list wpl ON wpl.id = l.pick_list_id "
        "WHERE wpl.wave_id = %s",
        (wave_id,),
    ).fetchone()
    if counts['pending'] == 0:
        new_status = 'completed'
    elif counts['resolved'] > 0:
        new_status = 'picking'
    else:
        new_status = 'open'

    if new_status != current_status:
        conn.execute("UPDATE wms_wave SET status = %s WHERE id = %s", (new_status, wave_id))
    return new_status


def list_waves(conn, status=None):
    rows = conn.execute("SELECT * FROM wms_wave ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['status'] = _sync_wave_status(conn, d['id'], current_status=d['status'])
        if status and d['status'] != status:
            continue
        out.append(d)
    return out


def get_wave(conn, wave_id):
    row = conn.execute("SELECT * FROM wms_wave WHERE id = %s", (wave_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d['status'] = _sync_wave_status(conn, wave_id, current_status=d['status'])
    return d


def get_wave_pick_lists(conn, wave_id):
    rows = conn.execute(
        "SELECT wpl.*, so.so_number FROM wms_pick_list wpl "
        "JOIN sales_order so ON so.id = wpl.so_id "
        "WHERE wpl.wave_id = %s ORDER BY wpl.id",
        (wave_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_wave(conn, so_ids, created_by):
    """Create a wave from a batch of confirmed SOs: generates a pick list
    per SO (reusing generate_pick_list unmodified) and assigns them all to
    a new wave. Does not commit. Raises ValueError if so_ids is empty, or
    propagates generate_pick_list's own ValueError (e.g. an SO that isn't
    confirmed or already has an active pick list) — the whole wave fails
    to create rather than partially forming, since the caller's open
    transaction rolls back as one unit.
    """
    so_ids = list(dict.fromkeys(so_ids))  # de-dupe, preserve order
    if not so_ids:
        raise ValueError("Select at least one sales order for the wave")

    wave_number = _next_sequence(conn, 'WAVE-')
    wave_id = conn.execute(
        "INSERT INTO wms_wave (wave_number, created_by) VALUES (%s,%s) RETURNING id",
        (wave_number, created_by),
    ).fetchone()['id']

    for so_id in so_ids:
        pick_list_id = generate_pick_list(conn, so_id, created_by)
        conn.execute(
            "UPDATE wms_pick_list SET wave_id = %s WHERE id = %s",
            (wave_id, pick_list_id),
        )
    return wave_id


def get_consolidated_pick_lines(conn, wave_id):
    """Group every still-pending line across a wave's member pick lists by
    (product, bin) — the whole point of wave picking: pick everything of
    one product from one bin in a single trip, once, no matter how many
    orders in the wave need it. Text-only SO lines (product_id IS NULL)
    have no product identity to batch on, so they're excluded here — they
    still exist on their own order's pick list and must be picked from
    there individually, same as before wave picking existed."""
    rows = conn.execute(
        "SELECT l.product_id, p.name AS product_name, l.bin_id, b.full_code AS bin_full_code, "
        "COALESCE(z.pick_sequence, 999999) AS zone_seq, "
        "SUM(l.qty_ordered) AS qty_needed, COUNT(DISTINCT l.pick_list_id) AS order_count "
        "FROM wms_pick_list_line l "
        "JOIN wms_pick_list wpl ON wpl.id = l.pick_list_id "
        "LEFT JOIN product p ON p.id = l.product_id "
        "LEFT JOIN wms_bin b ON b.id = l.bin_id "
        "LEFT JOIN wms_zone z ON z.id = l.zone_id "
        "WHERE wpl.wave_id = %s AND l.status = 'pending' AND l.product_id IS NOT NULL "
        "GROUP BY l.product_id, p.name, l.bin_id, b.full_code, z.pick_sequence "
        "ORDER BY zone_seq, b.full_code",
        (wave_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def record_wave_pick(conn, wave_id, product_id, bin_id, qty_picked, created_by):
    """Record one consolidated pick — qty_picked of product_id taken from
    bin_id in a single trip — and allocate it back down across every
    still-pending line in the wave that needs that exact (product, bin)
    combination, oldest pick list first, by calling the existing, unmodified
    record_pick() once per affected line (so every per-line side effect —
    product.amount, bin stock, that line's own pick list flipping to
    'picked' once fully resolved — happens exactly the way it always has;
    nothing about single-order picking changes). Does not commit. Raises
    ValueError for a non-positive qty, a missing/cancelled wave, no matching
    pending lines, or a qty exceeding what the wave actually needs for that
    product/bin (the over-pick guard — mirrors record_usage's on-hand-balance
    check in consignment_core).
    """
    if qty_picked <= 0:
        raise ValueError("qty_picked must be positive")
    wave = get_wave(conn, wave_id)
    if not wave:
        raise ValueError(f"Wave {wave_id} not found")
    if wave['status'] == 'cancelled':
        raise ValueError(f"Wave {wave_id} is cancelled")

    lines = conn.execute(
        "SELECT l.id, l.qty_ordered FROM wms_pick_list_line l "
        "JOIN wms_pick_list wpl ON wpl.id = l.pick_list_id "
        "WHERE wpl.wave_id = %s AND l.product_id = %s AND l.bin_id = %s AND l.status = 'pending' "
        "ORDER BY wpl.id, l.id",
        (wave_id, product_id, bin_id),
    ).fetchall()
    if not lines:
        raise ValueError(
            "No pending lines in this wave need that product/bin combination")

    total_needed = sum(line['qty_ordered'] for line in lines)
    if qty_picked > total_needed + 1e-9:
        raise ValueError(
            f"qty_picked {qty_picked:g} exceeds what this wave needs for "
            f"that product/bin ({total_needed:g})")

    remaining = qty_picked
    lines_updated = 0
    for line in lines:
        if remaining <= 1e-9:
            break
        take = min(line['qty_ordered'], remaining)
        record_pick(conn, line['id'], take, created_by)
        remaining -= take
        lines_updated += 1

    _sync_wave_status(conn, wave_id)
    return {'lines_updated': lines_updated, 'total_allocated': qty_picked - remaining}


def cancel_wave(conn, wave_id):
    """Cancel a wave that hasn't started picking yet. Does not commit.
    Raises ValueError if the wave doesn't exist or picking has already
    begun. Cascades to cancel every member pick list too, so the
    underlying SOs are free to be picked again individually or in a new
    wave — generate_pick_list only blocks on a non-cancelled pick list."""
    wave = get_wave(conn, wave_id)
    if not wave:
        raise ValueError(f"Wave {wave_id} not found")
    if wave['status'] != 'open':
        raise ValueError(
            f"Cannot cancel wave {wave_id} — status is {wave['status']}, not open")
    conn.execute("UPDATE wms_wave SET status = 'cancelled' WHERE id = %s", (wave_id,))
    conn.execute(
        "UPDATE wms_pick_list SET status = 'cancelled' WHERE wave_id = %s",
        (wave_id,),
    )


# ---------------------------------------------------------------------------
# RFID tracking (simulated)
# ---------------------------------------------------------------------------
#
# There is no real RFID reader anywhere in this environment — see the
# module docstring's "RFID tracking" paragraph. A reader is a virtual
# antenna tied to one zone (realistic: zone-level RFID resolution, not
# bin-level — an antenna can tell you a tagged pallet entered a zone, not
# which exact bin within it). A tag labels a qty of one product already
# tracked in a bin. Movement is detected at the zone level: reading a tag
# at a reader whose zone differs from the tag's current zone relocates it
# to the least-full active bin in the new zone (same greedy heuristic
# put-away rules already use) via _adjust_bin_stock on both ends — net
# zero to product.amount, the same exception as transfers/cross-docking.
# A re-read within the same zone is just a "still here" heartbeat.

def list_readers(conn, active_only=True):
    sql = (
        "SELECT r.*, z.code AS zone_code, z.warehouse_id "
        "FROM wms_rfid_reader r JOIN wms_zone z ON z.id = r.zone_id"
    )
    if active_only:
        sql += " WHERE r.is_active"
    sql += " ORDER BY r.reader_code"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def create_reader(conn, zone_id, reader_code, description=''):
    if not reader_code.strip():
        raise ValueError("Reader code is required")
    row = conn.execute(
        "INSERT INTO wms_rfid_reader (reader_code, zone_id, description) "
        "VALUES (%s,%s,%s) RETURNING id",
        (reader_code.strip(), zone_id, description.strip()),
    ).fetchone()
    return row['id']


def list_tags(conn, status='active'):
    conds, params = [], []
    if status:
        conds.append("t.status = %s")
        params.append(status)
    sql = (
        "SELECT t.*, p.name AS product_name, b.full_code AS bin_full_code "
        "FROM wms_rfid_tag t "
        "JOIN product p ON p.id = t.product_id "
        "LEFT JOIN wms_bin b ON b.id = t.bin_id"
    )
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY t.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_tag(conn, tag_id):
    row = conn.execute(
        "SELECT t.*, p.name AS product_name, b.full_code AS bin_full_code "
        "FROM wms_rfid_tag t "
        "JOIN product p ON p.id = t.product_id "
        "LEFT JOIN wms_bin b ON b.id = t.bin_id "
        "WHERE t.id = %s",
        (tag_id,),
    ).fetchone()
    return dict(row) if row else None


def create_tag(conn, tag_code, product_id, qty, bin_id, created_by):
    """Register a new RFID tag labelling qty of product_id already tracked
    in bin_id. Does not create new stock — the tag is a label on top of
    existing tracked bin stock, sanity-checked (not reserved) at creation
    time, so it can drift from reality if the underlying stock later moves
    through a path that never re-reads the tag (documented plainly in the
    module docstring, same drift already accepted for cost layers /
    consignment balances). Does not commit. Raises ValueError for a
    non-positive qty, a missing tag code, or a bin with less than qty of
    that product currently tracked.
    """
    if qty <= 0:
        raise ValueError("qty must be positive")
    if not tag_code.strip():
        raise ValueError("Tag code is required")
    stock = conn.execute(
        "SELECT qty FROM wms_bin_stock WHERE bin_id = %s AND product_id = %s",
        (bin_id, product_id),
    ).fetchone()
    tracked = stock['qty'] if stock else 0.0
    if tracked < qty:
        raise ValueError(
            f"Bin only has {tracked:g} of this product tracked — cannot tag {qty:g}")
    row = conn.execute(
        "INSERT INTO wms_rfid_tag (tag_code, product_id, qty, bin_id, created_by) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (tag_code.strip(), product_id, qty, bin_id, created_by),
    ).fetchone()
    return row['id']


def get_tag_history(conn, tag_id):
    rows = conn.execute(
        "SELECT e.*, r.reader_code, "
        "fb.full_code AS from_bin_full_code, tb.full_code AS to_bin_full_code "
        "FROM wms_rfid_read_event e "
        "JOIN wms_rfid_reader r ON r.id = e.reader_id "
        "LEFT JOIN wms_bin fb ON fb.id = e.from_bin_id "
        "LEFT JOIN wms_bin tb ON tb.id = e.to_bin_id "
        "WHERE e.tag_id = %s ORDER BY e.id DESC",
        (tag_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def simulate_tag_read(conn, tag_id, reader_id, created_by):
    """Simulate an RFID antenna reading a tag — the manual stand-in for
    real hardware (see module docstring). Logs a read event; if the
    reader's zone differs from the tag's current zone, relocates the
    tag's qty to the least-full active bin in the new zone via
    _adjust_bin_stock on both ends. Does not commit. Raises ValueError for
    a missing or retired tag, a missing reader, or a target zone with no
    active bin to land in.
    """
    tag = get_tag(conn, tag_id)
    if not tag:
        raise ValueError(f"Tag {tag_id} not found")
    if tag['status'] != 'active':
        raise ValueError(f"Tag {tag_id} is not active (status={tag['status']})")
    reader = conn.execute(
        "SELECT id, zone_id FROM wms_rfid_reader WHERE id = %s", (reader_id,),
    ).fetchone()
    if not reader:
        raise ValueError(f"Reader {reader_id} not found")

    current_zone_id = None
    if tag['bin_id']:
        current_bin = conn.execute(
            "SELECT zone_id FROM wms_bin WHERE id = %s", (tag['bin_id'],),
        ).fetchone()
        current_zone_id = current_bin['zone_id'] if current_bin else None

    moved = reader['zone_id'] != current_zone_id
    if moved:
        target_bin = _least_full_active_bin_in_zone(conn, reader['zone_id'])
        if not target_bin:
            raise ValueError("Reader's zone has no active bin to land the tag in")
        target_bin_id = target_bin['id']
        if tag['bin_id']:
            _adjust_bin_stock(conn, tag['bin_id'], tag['product_id'], -tag['qty'])
        _adjust_bin_stock(conn, target_bin_id, tag['product_id'], tag['qty'])
        conn.execute(
            "UPDATE wms_rfid_tag SET bin_id = %s WHERE id = %s",
            (target_bin_id, tag_id),
        )
    else:
        target_bin_id = tag['bin_id']

    conn.execute(
        "INSERT INTO wms_rfid_read_event "
        "(tag_id, reader_id, from_bin_id, to_bin_id, moved, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (tag_id, reader_id, tag['bin_id'], target_bin_id, moved, created_by),
    )
    return {'moved': moved, 'bin_id': target_bin_id}


def retire_tag(conn, tag_id):
    """Retire a tag (pallet consumed/broken down) — does not touch bin
    stock, since normal issue/pick/transfer flows already handle that;
    this only removes the label. Does not commit. Raises ValueError if
    the tag doesn't exist or is already retired."""
    tag = get_tag(conn, tag_id)
    if not tag:
        raise ValueError(f"Tag {tag_id} not found")
    if tag['status'] != 'active':
        raise ValueError(f"Tag {tag_id} is already {tag['status']}")
    conn.execute("UPDATE wms_rfid_tag SET status = 'retired' WHERE id = %s", (tag_id,))
