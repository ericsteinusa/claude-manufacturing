"""
atp_core.py — Qt-free Available-to-Promise (ATP) calculations.

ATP is a pure computed view over product / so_item / sales_order / po_item /
purchase_order — there are no ATP-specific tables, so there is no
ensure_atp_tables() here. Every function takes an open connection; the
caller controls the transaction/lifetime (same convention as
sales_orders_core / purchase_orders_core).

ATP qty = on-hand + open PO receipts (sent/partial, expected before the
requested date) − committed SO demand (confirmed orders needed by the
requested date).
"""

from datetime import date, timedelta

from .sales_orders_core import get_so, get_so_items

# How far forward the earliest-available-date search looks before giving up.
ATP_HORIZON_DAYS = 90


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def _committed_demand_rows(conn, product_id):
    """[(need_date, qty), ...] for confirmed SOs demanding this product.

    Mirrors mrp_web_core.get_demand_dated()'s NULL ship_date fallback
    (today + 30 days) exactly — same convention, not a new rule.
    """
    fallback = (date.today() + timedelta(days=30)).isoformat()
    rows = conn.execute(
        "SELECT si.qty, COALESCE(so.ship_date, %s) AS need_date "
        "FROM so_item si JOIN sales_order so ON so.id = si.so_id "
        "WHERE si.product_id = %s AND so.status = 'confirmed'",
        (fallback, product_id),
    ).fetchall()
    return [(_as_date(r['need_date']), float(r['qty'] or 0)) for r in rows]


def _open_po_supply_rows(conn, product_id):
    """[(expected_date, qty), ...] for open (sent/partial) PO receipts.

    NULL expected_date rows are excluded: there is no promised date to
    compare to a requested date, so an unscheduled PO line cannot count as
    a firm receipt.
    """
    rows = conn.execute(
        "SELECT (pi.qty_ordered - pi.qty_received) AS qty, po.expected_date "
        "FROM po_item pi JOIN purchase_order po ON po.id = pi.po_id "
        "WHERE pi.product_id = %s AND po.status IN ('sent', 'partial') "
        "AND po.expected_date IS NOT NULL",
        (product_id,),
    ).fetchall()
    out = []
    for r in rows:
        qty = float(r['qty'] or 0)
        if qty <= 0:
            continue
        out.append((_as_date(r['expected_date']), qty))
    return out


def _walk_earliest_available(req_d, on_hand, requested_qty, demand_rows, supply_rows):
    """First date after req_d whose cumulative ATP covers requested_qty.

    ATP can only change on a date where a demand or supply row lands, so
    only those dates need to be checked (not a day-by-day scan). Capped at
    ATP_HORIZON_DAYS. Returns an ISO date string, or None if never
    sufficient within the horizon.
    """
    horizon_d = req_d + timedelta(days=ATP_HORIZON_DAYS)
    candidates = sorted({d for d, _ in demand_rows if d and req_d < d <= horizon_d} |
                        {d for d, _ in supply_rows if d and req_d < d <= horizon_d})
    for d in candidates:
        committed = sum(q for dd, q in demand_rows if dd and dd <= d)
        supply = sum(q for dd, q in supply_rows if dd and dd <= d)
        if on_hand + supply - committed >= requested_qty:
            return d.isoformat()
    return None


def get_atp(conn, product_id, requested_qty, requested_date=None):
    """Compute ATP for one product/qty/date.

    Returns {product_id, on_hand, committed_qty, open_po_qty, atp_qty,
    requested_qty, requested_date, sufficient, earliest_available_date}.
    earliest_available_date is an ISO string, or None if not achievable
    within ATP_HORIZON_DAYS days of requested_date.
    """
    req_d = _as_date(requested_date) or date.today()
    requested_qty = float(requested_qty)

    row = conn.execute(
        "SELECT COALESCE(amount, 0) AS on_hand FROM product WHERE id = %s",
        (product_id,),
    ).fetchone()
    on_hand = float(row['on_hand']) if row else 0.0

    demand_rows = _committed_demand_rows(conn, product_id)
    supply_rows = _open_po_supply_rows(conn, product_id)

    committed_qty = sum(q for d, q in demand_rows if d and d <= req_d)
    open_po_qty = sum(q for d, q in supply_rows if d and d <= req_d)
    atp_qty = on_hand + open_po_qty - committed_qty
    sufficient = atp_qty >= requested_qty

    earliest_available_date = (
        req_d.isoformat() if sufficient else
        _walk_earliest_available(req_d, on_hand, requested_qty, demand_rows, supply_rows)
    )

    return {
        'product_id': product_id,
        'on_hand': on_hand,
        'committed_qty': committed_qty,
        'open_po_qty': open_po_qty,
        'atp_qty': atp_qty,
        'requested_qty': requested_qty,
        'requested_date': req_d.isoformat(),
        'sufficient': sufficient,
        'earliest_available_date': earliest_available_date,
    }


def get_atp_qty_for_products(conn, requested_date=None):
    """{product_id: {on_hand, committed_qty, open_po_qty, atp_qty}} for
    every product, via 3 aggregate queries (not one query per product).

    Feeds the so_detail.html embedded atp_json — mirrors
    get_customer_price_tiers/price_tiers_json's "dump everything once, no
    AJAX" convention. Does NOT compute 'sufficient' or
    'earliest_available_date' — those need a specific qty, which only the
    ATP Inquiry screen's POST provides.
    """
    requested_date = requested_date or date.today().isoformat()
    fallback = (date.today() + timedelta(days=30)).isoformat()

    result = {
        r['id']: {'on_hand': float(r['on_hand']), 'committed_qty': 0.0, 'open_po_qty': 0.0}
        for r in conn.execute(
            "SELECT id, COALESCE(amount, 0) AS on_hand FROM product"
        ).fetchall()
    }

    for r in conn.execute(
        "SELECT si.product_id, SUM(si.qty) AS qty "
        "FROM so_item si JOIN sales_order so ON so.id = si.so_id "
        "WHERE so.status = 'confirmed' AND si.product_id IS NOT NULL "
        "AND COALESCE(so.ship_date, %s) <= %s GROUP BY si.product_id",
        (fallback, requested_date),
    ).fetchall():
        result.setdefault(r['product_id'], {'on_hand': 0.0, 'committed_qty': 0.0, 'open_po_qty': 0.0})
        result[r['product_id']]['committed_qty'] = float(r['qty'] or 0)

    for r in conn.execute(
        "SELECT pi.product_id, SUM(pi.qty_ordered - pi.qty_received) AS qty "
        "FROM po_item pi JOIN purchase_order po ON po.id = pi.po_id "
        "WHERE po.status IN ('sent','partial') AND po.expected_date IS NOT NULL "
        "AND po.expected_date <= %s AND pi.product_id IS NOT NULL GROUP BY pi.product_id",
        (requested_date,),
    ).fetchall():
        result.setdefault(r['product_id'], {'on_hand': 0.0, 'committed_qty': 0.0, 'open_po_qty': 0.0})
        result[r['product_id']]['open_po_qty'] = float(r['qty'] or 0)

    for d in result.values():
        d['atp_qty'] = d['on_hand'] + d['open_po_qty'] - d['committed_qty']
    return result


def check_so_atp(conn, so_id, as_of_date=None):
    """Shortfall list for an SO's line items, evaluated as of the SO's
    ship_date (falling back to today if NULL). Empty list = fully covered.

    Each shortfall dict: {item_id, product_id, product_name, requested_qty,
    atp_qty, shortfall, earliest_available_date}. Lines with no product_id
    (services/custom text) are skipped — nothing to check ATP against.
    """
    so = get_so(conn, so_id)
    if not so:
        return []
    requested_date = as_of_date or so.get('ship_date') or date.today().isoformat()
    shortfalls = []
    for it in get_so_items(conn, so_id):
        if not it.get('product_id'):
            continue
        atp = get_atp(conn, it['product_id'], it['qty'], requested_date)
        if not atp['sufficient']:
            shortfalls.append({
                'item_id': it['id'],
                'product_id': it['product_id'],
                'product_name': it.get('product_name') or it.get('description'),
                'requested_qty': it['qty'],
                'atp_qty': atp['atp_qty'],
                'shortfall': it['qty'] - atp['atp_qty'],
                'earliest_available_date': atp['earliest_available_date'],
            })
    return shortfalls
