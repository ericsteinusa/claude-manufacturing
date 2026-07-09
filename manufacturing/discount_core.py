"""discount_core.py — Qt-free Discount & Promotion Management.

Every top-10 manufacturing ERP has this (10/10 in the competitive gap
analysis) and this codebase had no discount concept at all before this
module — only tiered list pricing (price_list_core.py).

promotion — a single-row rule: percent-off or fixed-amount-off, optionally
scoped to one product (NULL = every product) and/or one customer (NULL =
every customer), with an optional min_qty threshold and an effective
window. Deliberately not a header+lines model like price_list — a
promotion is one discount rule, not a multi-line document.

Resolution picks whichever applicable promotion yields the *lowest* final
price for the customer (get_best_price) — that's the one unambiguous
definition of "best" when percent and fixed-amount rules can both apply to
the same line, without needing to compare discount types directly.

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / accounting_core).
"""

from __future__ import annotations

import datetime

DISCOUNT_TYPES = ('percent', 'fixed')


def ensure_discount_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS promotion (
            id             SERIAL PRIMARY KEY,
            name           TEXT NOT NULL,
            discount_type  TEXT NOT NULL DEFAULT 'percent',
            discount_value REAL NOT NULL DEFAULT 0,
            product_id     INTEGER REFERENCES product(id),
            customer_id    INTEGER REFERENCES customer(id),
            min_qty        REAL NOT NULL DEFAULT 1,
            start_date     TEXT,
            end_date       TEXT,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _is_effective(promo, as_of):
    if promo['start_date'] and as_of < promo['start_date']:
        return False
    if promo['end_date'] and as_of > promo['end_date']:
        return False
    return True


def _validate(discount_type, discount_value):
    if discount_type not in DISCOUNT_TYPES:
        raise ValueError(f'Unknown discount_type: {discount_type!r}')
    if discount_value < 0:
        raise ValueError('discount_value cannot be negative.')
    if discount_type == 'percent' and discount_value > 100:
        raise ValueError('A percent discount cannot exceed 100.')


# ---------------------------------------------------------------------------
# Promotion CRUD
# ---------------------------------------------------------------------------

def list_promotions(conn, active_only=False, search=None):
    conditions = []
    params: list = []
    if active_only:
        conditions.append("pr.is_active = TRUE")
    if search:
        conditions.append("pr.name ILIKE %s")
        params.append(f"%{search}%")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(f"""
        SELECT pr.*, p.name AS product_name,
               COALESCE(c.company_name,
                        TRIM(CONCAT(c.first_name, ' ', c.last_name))) AS customer_name
        FROM promotion pr
        LEFT JOIN product p ON p.id = pr.product_id
        LEFT JOIN customer c ON c.id = pr.customer_id
        {where}
        ORDER BY pr.created_at DESC, pr.id DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_promotion(conn, promo_id):
    row = conn.execute("""
        SELECT pr.*, p.name AS product_name,
               COALESCE(c.company_name,
                        TRIM(CONCAT(c.first_name, ' ', c.last_name))) AS customer_name
        FROM promotion pr
        LEFT JOIN product p ON p.id = pr.product_id
        LEFT JOIN customer c ON c.id = pr.customer_id
        WHERE pr.id = %s
    """, (promo_id,)).fetchone()
    return dict(row) if row else None


def create_promotion(conn, name, discount_type='percent', discount_value=0.0,
                     product_id=None, customer_id=None, min_qty=1,
                     start_date=None, end_date=None, notes='', created_by=''):
    if not name.strip():
        raise ValueError('Name is required.')
    _validate(discount_type, discount_value)
    row = conn.execute(
        "INSERT INTO promotion "
        "(name, discount_type, discount_value, product_id, customer_id, "
        " min_qty, start_date, end_date, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), discount_type, discount_value,
         product_id or None, customer_id or None, min_qty or 1,
         start_date or None, end_date or None, notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def update_promotion(conn, promo_id, **fields):
    allowed = {'name', 'discount_type', 'discount_value', 'product_id',
               'customer_id', 'min_qty', 'start_date', 'end_date',
               'is_active', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'discount_type' in cols or 'discount_value' in cols:
        current = get_promotion(conn, promo_id) or {}
        _validate(
            cols.get('discount_type', current.get('discount_type')),
            cols.get('discount_value', current.get('discount_value')),
        )
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE promotion SET {set_clause} WHERE id = %s",
        list(cols.values()) + [promo_id],
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def apply_discount(base_price, discount_type, discount_value):
    """Pure function: final unit price after one discount rule."""
    if discount_type == 'percent':
        return round(base_price * (1 - discount_value / 100), 2)
    return round(max(0.0, base_price - discount_value), 2)


def find_applicable_promotions(conn, customer_id=None, product_id=None,
                               qty=1, as_of=None):
    """Active, effective promotions whose scope covers this
    customer/product combination and whose min_qty threshold is met.

    A promotion with product_id/customer_id NULL applies to every
    product/customer respectively — matching price_list_core's convention
    of NULL meaning "no assignment / applies generally" rather than a
    wildcard row that has to be maintained.
    """
    as_of = as_of or datetime.date.today().isoformat()
    conditions = ["pr.is_active = TRUE", "pr.min_qty <= %s"]
    params: list = [qty]
    if product_id:
        conditions.append("(pr.product_id = %s OR pr.product_id IS NULL)")
        params.append(product_id)
    else:
        conditions.append("pr.product_id IS NULL")
    if customer_id:
        conditions.append("(pr.customer_id = %s OR pr.customer_id IS NULL)")
        params.append(customer_id)
    else:
        conditions.append("pr.customer_id IS NULL")
    conditions.append("(pr.start_date IS NULL OR pr.start_date <= %s)")
    params.append(as_of)
    conditions.append("(pr.end_date IS NULL OR pr.end_date >= %s)")
    params.append(as_of)
    rows = conn.execute(f"""
        SELECT pr.*, p.name AS product_name,
               COALESCE(c.company_name,
                        TRIM(CONCAT(c.first_name, ' ', c.last_name))) AS customer_name
        FROM promotion pr
        LEFT JOIN product p ON p.id = pr.product_id
        LEFT JOIN customer c ON c.id = pr.customer_id
        WHERE {" AND ".join(conditions)}
        ORDER BY pr.min_qty DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_best_price(conn, customer_id, product_id, qty, base_price, as_of=None):
    """Return (final_price, promotion_or_None) — the lowest price any
    applicable promotion yields, or (base_price, None) if none apply.
    Comparing final prices sidesteps having to rank a 10%-off rule
    against a $5-off rule directly."""
    promos = find_applicable_promotions(
        conn, customer_id=customer_id, product_id=product_id, qty=qty,
        as_of=as_of)
    if not promos:
        return base_price, None
    best_price, best_promo = min(
        (
            (apply_discount(base_price, p['discount_type'], p['discount_value']), p)
            for p in promos
        ),
        key=lambda pair: pair[0],
    )
    return best_price, best_promo


def get_promotion_tiers_for_customer(conn, customer_id, as_of=None):
    """Return {product_id_or_'__all__': [(min_qty, discount_type,
    discount_value, promo_name), ...]} sorted desc by min_qty, for
    embedding as client-side auto-apply data on the SO line-entry form —
    the same shape/precedent as
    price_list_core.get_price_tiers_for_price_list. A promotion with no
    product_id (applies to every product) is grouped under the '__all__'
    key since it has no single product_id to key on; callers should fall
    back to '__all__' when a product has no product-specific entry."""
    as_of = as_of or datetime.date.today().isoformat()
    rows = conn.execute("""
        SELECT product_id, min_qty, discount_type, discount_value, name
        FROM promotion
        WHERE is_active = TRUE
          AND (customer_id = %s OR customer_id IS NULL)
          AND (start_date IS NULL OR start_date <= %s)
          AND (end_date IS NULL OR end_date >= %s)
        ORDER BY product_id NULLS LAST, min_qty DESC
    """, (customer_id, as_of, as_of)).fetchall()
    tiers: dict = {}
    for r in rows:
        key = r['product_id'] if r['product_id'] is not None else '__all__'
        tiers.setdefault(key, []).append(
            (float(r['min_qty']), r['discount_type'], float(r['discount_value']),
             r['name']))
    return tiers
