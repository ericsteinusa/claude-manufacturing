"""
inventory_core.py — Qt-free inventory data layer for the web UI.

Stock levels live in ``product.amount``.  Every movement is also written to
``inventory_transaction`` so managers can see the full history.

Transaction types
-----------------
receive  — goods arriving (PO receipt, manual receive): amount += qty
issue    — materials consumed (WO pick, sales): amount -= qty
return   — unused materials returned to stock: amount += qty
adjust   — physical-count correction (signed qty, positive or negative)
"""

from datetime import date

from .log_utils import get_logger
from .notify_core import create_notifications_for_dept, ensure_notification_table

log = get_logger(__name__)

TRANS_TYPES = ('receive', 'issue', 'adjust', 'return')

# Net effect on product.amount for each type (before applying sign logic).
# 'adjust' is special — the user supplies a signed qty directly.
_TRANS_SIGN = {
    'receive': 1,
    'issue': -1,
    'return': 1,
    'adjust': None,  # signed passthrough
}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _ensure_product_extra_columns(conn) -> None:
    """Self-heal item_type/uom/lead_time_days/created_by on ``product``.

    schema.py's/work_orders_core.py's own CREATE TABLE IF NOT EXISTS for
    ``product`` (whichever runs first on a fresh deployment) never
    includes any of these four — they're only added via
    seed_sample_products.py's own ALTER TABLE steps, a dev-only seed
    script never run in production. Any query selecting/inserting/
    updating them raises psycopg2.errors.UndefinedColumn until this has
    run once (caught for real via a fresh CI database with only
    seed_sample_data.py run — /inventory/ 500'd on column p.item_type
    does not exist). Called from every function in this module that
    touches any of the four. Does not commit — callers commit right
    after calling this.
    """
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS item_type TEXT DEFAULT 'buy'")
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS uom TEXT DEFAULT 'ea'")
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS lead_time_days INTEGER DEFAULT 0")
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")


def list_products(conn, search=None, filter_status=None,
                  item_type=None) -> list[dict]:
    """Return product rows annotated with a stock-status label.

    filter_status: None | 'low' (at or below reorder_point > 0) | 'zero'
    item_type:     None | 'make' | 'buy'
    """
    _ensure_product_extra_columns(conn)
    conn.commit()

    where = ['1=1']
    params: list = []

    if search:
        where.append("p.name ILIKE %s")
        params.append(f'%{search}%')
    if item_type:
        where.append("COALESCE(p.item_type, 'buy') = %s")
        params.append(item_type)

    rows = conn.execute(
        "SELECT p.id, p.name, "
        "COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.uom, 'ea') AS uom, "
        "COALESCE(p.bin, '') AS bin, "
        "COALESCE(p.amount, 0) AS amount, "
        "COALESCE(p.reorder_point, 0) AS reorder_point, "
        "COALESCE(p.purchase_price, 0) AS purchase_price, "
        "COALESCE(p.lead_time_days, 0) AS lead_time_days, "
        "s.company_name AS supplier_name "
        "FROM product p "
        "LEFT JOIN supplier s ON s.id = p.supplier_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY p.name",
        params,
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        amt = d['amount']
        rop = d['reorder_point']
        if amt <= 0:
            d['status'] = 'zero'
        elif rop > 0 and amt <= rop:
            d['status'] = 'low'
        else:
            d['status'] = 'ok'

        if filter_status == 'zero' and d['status'] != 'zero':
            continue
        if filter_status == 'low' and d['status'] not in ('low', 'zero'):
            continue
        result.append(d)

    return result


def get_product(conn, product_id: int) -> dict | None:
    """Single product with supplier name."""
    _ensure_product_extra_columns(conn)
    conn.commit()
    row = conn.execute(
        "SELECT p.id, p.name, "
        "COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.uom, 'ea') AS uom, "
        "COALESCE(p.bin, '') AS bin, "
        "COALESCE(p.amount, 0) AS amount, "
        "COALESCE(p.reorder_point, 0) AS reorder_point, "
        "COALESCE(p.purchase_price, 0) AS purchase_price, "
        "COALESCE(p.lead_time_days, 0) AS lead_time_days, "
        "p.supplier_id, "
        "s.company_name AS supplier_name, "
        "p.created_by "
        "FROM product p "
        "LEFT JOIN supplier s ON s.id = p.supplier_id "
        "WHERE p.id = %s",
        (product_id,),
    ).fetchone()
    return dict(row) if row else None


def get_transactions(conn, product_id: int, limit: int = 50) -> list[dict]:
    """Transaction history for one product, most recent first."""
    rows = conn.execute(
        "SELECT id, trans_date, trans_type, quantity, reference, notes, created_by "
        "FROM inventory_transaction "
        "WHERE product_id = %s "
        "ORDER BY id DESC LIMIT %s",
        (product_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_alert_counts(conn) -> dict:
    """Count of products at zero stock and below reorder point."""
    row = conn.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE COALESCE(amount,0) <= 0) AS zero_count, "
        "  COUNT(*) FILTER (WHERE COALESCE(amount,0) > 0 "
        "                   AND reorder_point > 0 "
        "                   AND COALESCE(amount,0) <= reorder_point) AS low_count "
        "FROM product"
    ).fetchone()
    return dict(row) if row else {'zero_count': 0, 'low_count': 0}


def load_suppliers(conn) -> list[dict]:
    """Supplier dropdown list: [{id, label}]."""
    rows = conn.execute(
        "SELECT id, "
        "COALESCE(NULLIF(company_name,''), "
        "         TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) AS label "
        "FROM supplier ORDER BY label"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def record_transaction(conn, product_id: int, trans_type: str,
                       quantity: float, reference: str,
                       notes: str, created_by: str) -> float:
    """Write a transaction row and update product.amount.

    For ``receive`` / ``return``: stock increases by abs(quantity).
    For ``issue``: stock decreases by abs(quantity).
    For ``adjust``: signed quantity applied directly (positive or negative).

    Returns the new on-hand quantity.  Does not commit.
    """
    if trans_type not in TRANS_TYPES:
        raise ValueError(f"Unknown trans_type: {trans_type!r}")

    sign = _TRANS_SIGN[trans_type]
    if sign is None:  # adjust: passthrough
        delta = quantity
    else:
        delta = sign * abs(quantity)

    # inventory_transaction predates created_by on some deployments (whichever
    # CREATE TABLE ran first won, and schema.py's version is a no-op against
    # an already-existing table) — self-heal since this function doesn't
    # commit its own transaction for callers to run an ensure-step against.
    conn.execute(
        "ALTER TABLE inventory_transaction ADD COLUMN IF NOT EXISTS created_by TEXT")
    conn.execute(
        "INSERT INTO inventory_transaction "
        "(product_id, trans_date, trans_type, quantity, reference, notes, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (product_id, date.today().isoformat(),
         trans_type, quantity, reference or '', notes or '', created_by),
    )
    row = conn.execute(
        "UPDATE product SET amount = COALESCE(amount, 0) + %s WHERE id = %s "
        "RETURNING amount, reorder_point, name",
        (delta, product_id),
    ).fetchone()
    new_qty = row['amount'] if row else 0.0
    log.info("Inventory %s: product_id=%s qty=%s delta=%s → on_hand=%.4f",
             trans_type, product_id, quantity, delta, new_qty)

    if row:
        reorder_point = row['reorder_point'] or 0
        old_qty = new_qty - delta
        if reorder_point > 0 and old_qty > reorder_point >= new_qty:
            ensure_notification_table(conn)
            create_notifications_for_dept(
                conn, 'Purchasing', 'low_stock',
                f"Low stock: {row['name']} at {new_qty:g} "
                f"(reorder point {reorder_point:g})",
                entity_type='product', entity_id=product_id,
            )
            log.info("Low-stock breach notified for product_id=%s", product_id)

    return new_qty


def create_product(conn, name: str, supplier_id, bin_loc: str,
                   amount: float, reorder_point: float, purchase_price: float,
                   item_type: str, lead_time_days: int, uom: str,
                   created_by: str) -> int:
    """Insert a new product and return its id. Does not commit."""
    if not name.strip():
        raise ValueError("Product name is required")
    _ensure_product_extra_columns(conn)
    row = conn.execute(
        "INSERT INTO product "
        "(name, supplier_id, bin, amount, reorder_point, purchase_price, "
        " item_type, lead_time_days, uom, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), supplier_id or None,
         bin_loc.strip() or None,
         max(0.0, amount), max(0.0, reorder_point),
         max(0.0, purchase_price),
         item_type if item_type in ('make', 'buy') else 'buy',
         max(0, lead_time_days), uom.strip() or 'ea',
         created_by),
    ).fetchone()
    return row['id']


def update_product(conn, product_id: int, name: str, supplier_id,
                   bin_loc: str, reorder_point: float, purchase_price: float,
                   item_type: str, lead_time_days: int, uom: str) -> None:
    """Update editable product master fields. Does not commit."""
    if not name.strip():
        raise ValueError("Product name is required")
    _ensure_product_extra_columns(conn)
    conn.execute(
        "UPDATE product SET name=%s, supplier_id=%s, bin=%s, "
        "reorder_point=%s, purchase_price=%s, item_type=%s, "
        "lead_time_days=%s, uom=%s WHERE id=%s",
        (name.strip(), supplier_id or None,
         bin_loc.strip() or None,
         max(0.0, reorder_point), max(0.0, purchase_price),
         item_type if item_type in ('make', 'buy') else 'buy',
         max(0, lead_time_days), uom.strip() or 'ea',
         product_id),
    )
