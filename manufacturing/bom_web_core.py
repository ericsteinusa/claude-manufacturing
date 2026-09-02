"""
bom_web_core.py — Qt-free BOM data layer for the web UI.

Builds on the existing flat bom(product_id, component_id, qty_required,
unit, notes, scrap_pct) table and the item-master columns added to product
(item_type, lead_time_days, uom).  The cycle guard lives in bom_core.py and
is imported here so web tests need not touch the DB.
"""

from .bom_core import would_create_cycle, explode_quantity
from .inventory_core import _ensure_product_extra_columns
from .log_utils import get_logger

log = get_logger(__name__)

ITEM_TYPES = ('make', 'buy')


# ---------------------------------------------------------------------------
# Product / item-master queries
# ---------------------------------------------------------------------------

def list_products(conn, item_type: str | None = None,
                  has_bom: bool | None = None) -> list[dict]:
    """All products with on-hand stock and direct-component count.

    ``item_type`` filters to 'make' or 'buy'.
    ``has_bom=True`` limits to products that have at least one BOM line;
    ``has_bom=False`` limits to products with no BOM lines.
    """
    _ensure_product_extra_columns(conn)
    conn.commit()

    sql = (
        "SELECT p.id, p.name, "
        "COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.uom, 'ea') AS uom, "
        "COALESCE(p.lead_time_days, 0) AS lead_time_days, "
        "COALESCE(p.amount, 0) AS amount, "
        "COALESCE(p.reorder_point, 0) AS reorder_point, "
        "COUNT(b.id) AS component_count "
        "FROM product p "
        "LEFT JOIN bom b ON b.product_id = p.id "
    )
    conditions = []
    params: list = []
    if item_type:
        conditions.append("p.item_type = %s")
        params.append(item_type)
    if conditions:
        sql += "WHERE " + " AND ".join(conditions) + " "
    sql += "GROUP BY p.id ORDER BY p.name"

    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    if has_bom is True:
        result = [r for r in result if r['component_count'] > 0]
    elif has_bom is False:
        result = [r for r in result if r['component_count'] == 0]
    return result


def get_product(conn, product_id: int) -> dict | None:
    _ensure_product_extra_columns(conn)
    conn.commit()
    row = conn.execute(
        "SELECT id, name, "
        "COALESCE(item_type, 'buy') AS item_type, "
        "COALESCE(uom, 'ea') AS uom, "
        "COALESCE(lead_time_days, 0) AS lead_time_days, "
        "COALESCE(amount, 0) AS amount, "
        "COALESCE(reorder_point, 0) AS reorder_point "
        "FROM product WHERE id = %s",
        (product_id,),
    ).fetchone()
    return dict(row) if row else None


def update_item_master(conn, product_id: int, item_type: str,
                       lead_time_days: int, uom: str) -> None:
    item_type = item_type if item_type in ITEM_TYPES else 'buy'
    uom = (uom or 'ea').strip() or 'ea'
    lead_time_days = max(0, int(lead_time_days or 0))
    _ensure_product_extra_columns(conn)
    conn.execute(
        "UPDATE product SET item_type = %s, lead_time_days = %s, uom = %s "
        "WHERE id = %s",
        (item_type, lead_time_days, uom, product_id),
    )
    log.info("Item master updated for product %s: type=%s lt=%s uom=%s",
             product_id, item_type, lead_time_days, uom)


# ---------------------------------------------------------------------------
# BOM line queries
# ---------------------------------------------------------------------------

def get_bom(conn, product_id: int) -> list[dict]:
    """Direct components of a product (one level), with component details."""
    _ensure_product_extra_columns(conn)
    conn.commit()
    rows = conn.execute(
        "SELECT b.id, b.component_id, "
        "COALESCE(b.qty_required, 1.0) AS qty_required, "
        "COALESCE(b.scrap_pct, 0.0) AS scrap_pct, "
        "COALESCE(b.unit, p.uom, 'ea') AS unit, "
        "COALESCE(b.notes, '') AS notes, "
        "p.name AS component_name, "
        "COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.lead_time_days, 0) AS lead_time_days, "
        "COALESCE(p.uom, 'ea') AS uom, "
        "COALESCE(p.amount, 0) AS on_hand "
        "FROM bom b JOIN product p ON p.id = b.component_id "
        "WHERE b.product_id = %s ORDER BY p.name",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_bom_line(conn, product_id: int, component_id: int,
                 qty_required: float, unit: str,
                 notes: str = '', scrap_pct: float = 0.0) -> tuple[bool, str]:
    """Insert a BOM edge after cycle-checking.

    Returns (True, line_id_str) on success or (False, error_message) on failure.
    """
    if product_id == component_id:
        return False, "A product cannot be a component of itself."

    existing = conn.execute(
        "SELECT product_id, component_id FROM bom"
    ).fetchall()
    edges = [(r[0], r[1]) for r in existing]
    if would_create_cycle(edges, product_id, component_id):
        return False, "Adding this component would create a circular BOM."

    already = conn.execute(
        "SELECT id FROM bom WHERE product_id = %s AND component_id = %s",
        (product_id, component_id),
    ).fetchone()
    if already:
        return False, "That component is already in this BOM."

    qty_required = max(0.0, float(qty_required or 1.0))
    scrap_pct = max(0.0, float(scrap_pct or 0.0))
    unit = (unit or 'ea').strip() or 'ea'

    row = conn.execute(
        "INSERT INTO bom (product_id, component_id, qty_required, unit, notes, scrap_pct) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (product_id, component_id, qty_required, unit, notes or '', scrap_pct),
    ).fetchone()
    log.info("BOM line added: product=%s component=%s qty=%s",
             product_id, component_id, qty_required)
    return True, str(row[0])


def update_bom_line(conn, line_id: int, qty_required: float,
                    unit: str, notes: str = '',
                    scrap_pct: float = 0.0) -> bool:
    """Update qty, unit, notes and scrap on an existing BOM line."""
    qty_required = max(0.0, float(qty_required or 1.0))
    scrap_pct = max(0.0, float(scrap_pct or 0.0))
    unit = (unit or 'ea').strip() or 'ea'
    result = conn.execute(
        "UPDATE bom SET qty_required = %s, unit = %s, notes = %s, scrap_pct = %s "
        "WHERE id = %s",
        (qty_required, unit, notes or '', scrap_pct, line_id),
    )
    updated = result.rowcount if hasattr(result, 'rowcount') else 1
    log.info("BOM line %s updated", line_id)
    return bool(updated)


def delete_bom_line(conn, line_id: int) -> bool:
    """Delete a single BOM line by its id."""
    conn.execute("DELETE FROM bom WHERE id = %s", (line_id,))
    log.info("BOM line %s deleted", line_id)
    return True


# ---------------------------------------------------------------------------
# Multi-level explosion
# ---------------------------------------------------------------------------

def explode_bom(conn, product_id: int, qty: float = 1.0) -> list[dict]:
    """Recursively expand the BOM into a flat depth-annotated list.

    Each entry has a ``depth`` field (0 = direct component) so templates can
    render indentation.  The expansion stops at depth 10 or when a visited
    product would be visited again (guards against any cycles that bypassed
    the insert check).
    """
    _cache: dict[int, list[dict]] = {}

    def _load(pid: int) -> list[dict]:
        if pid not in _cache:
            _cache[pid] = get_bom(conn, pid)
        return _cache[pid]

    def _recurse(pid: int, qty: float, depth: int,
                 visited: frozenset) -> list[dict]:
        if depth > 10 or pid in visited:
            return []
        rows = _load(pid)
        result = []
        for r in rows:
            needed = explode_quantity(r['qty_required'], qty, r['scrap_pct'])
            result.append({
                'depth': depth,
                'component_id': r['component_id'],
                'component_name': r['component_name'],
                'item_type': r['item_type'],
                'qty_needed': needed,
                'unit': r['unit'],
                'uom': r['uom'],
                'lead_time_days': r['lead_time_days'],
                'notes': r['notes'],
                'scrap_pct': r['scrap_pct'],
                'on_hand': r['on_hand'],
            })
            if r['item_type'] == 'make':
                result.extend(
                    _recurse(r['component_id'], needed, depth + 1,
                             visited | {pid})
                )
        return result

    return _recurse(product_id, qty, 0, frozenset())
