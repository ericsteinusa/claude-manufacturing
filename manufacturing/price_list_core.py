"""price_list_core.py — Qt-free sales price list module (P1-E).

price_list      — master record: name, currency, effective/expiry window
price_list_line — product -> unit_price, with an optional min_qty for
                  tiered pricing (e.g. 1@$10, 50@$9, 100@$8)

A customer can be assigned one price list (customer.price_list_id).
get_customer_price() resolves the tier that applies for a given qty: the
line with the largest min_qty that is <= the requested qty. If the
customer has no price list assigned, or the product isn't on their list,
callers fall back to manual entry (this module never invents a price).
"""

import datetime

from .log_utils import get_logger

log = get_logger(__name__)


def ensure_price_list_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_list (
            id             SERIAL PRIMARY KEY,
            name           TEXT NOT NULL UNIQUE,
            currency       TEXT NOT NULL DEFAULT 'USD',
            effective_date TEXT,
            expiry_date    TEXT,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_list_line (
            id            SERIAL PRIMARY KEY,
            price_list_id INTEGER NOT NULL REFERENCES price_list(id),
            product_id    INTEGER NOT NULL REFERENCES product(id),
            min_qty       REAL NOT NULL DEFAULT 1,
            unit_price    REAL NOT NULL DEFAULT 0.0,
            UNIQUE (price_list_id, product_id, min_qty)
        )
    """)
    conn.execute(
        "ALTER TABLE customer ADD COLUMN IF NOT EXISTS "
        "price_list_id INTEGER REFERENCES price_list(id)"
    )


def _is_effective(pl, as_of):
    if pl['effective_date'] and as_of < pl['effective_date']:
        return False
    if pl['expiry_date'] and as_of > pl['expiry_date']:
        return False
    return True


# ---------------------------------------------------------------------------
# Price list CRUD
# ---------------------------------------------------------------------------

def list_price_lists(conn, active_only=False):
    where = "WHERE is_active = TRUE" if active_only else ""
    rows = conn.execute(
        f"SELECT * FROM price_list {where} ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_price_list(conn, price_list_id):
    row = conn.execute(
        "SELECT * FROM price_list WHERE id = %s", (price_list_id,)
    ).fetchone()
    return dict(row) if row else None


def create_price_list(conn, name, currency='USD', effective_date=None,
                      expiry_date=None, notes='', created_by=''):
    row = conn.execute(
        "INSERT INTO price_list "
        "(name, currency, effective_date, expiry_date, notes, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (name.strip(), currency, effective_date or None,
         expiry_date or None, notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def update_price_list(conn, price_list_id, **fields):
    allowed = {'name', 'currency', 'effective_date', 'expiry_date',
               'is_active', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE price_list SET {set_clause} WHERE id = %s",
        list(cols.values()) + [price_list_id],
    )


# ---------------------------------------------------------------------------
# Price list lines
# ---------------------------------------------------------------------------

def list_price_list_lines(conn, price_list_id):
    rows = conn.execute("""
        SELECT pll.id, pll.price_list_id, pll.product_id, pll.min_qty,
               pll.unit_price, p.name AS product_name
        FROM price_list_line pll
        JOIN product p ON p.id = pll.product_id
        WHERE pll.price_list_id = %s
        ORDER BY p.name, pll.min_qty
    """, (price_list_id,)).fetchall()
    return [dict(r) for r in rows]


def add_price_list_line(conn, price_list_id, product_id, unit_price, min_qty=1):
    row = conn.execute(
        "INSERT INTO price_list_line (price_list_id, product_id, min_qty, unit_price) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (price_list_id, product_id, min_qty, unit_price),
    ).fetchone()
    return row['id']


def update_price_list_line(conn, line_id, unit_price, min_qty=1):
    conn.execute(
        "UPDATE price_list_line SET min_qty = %s, unit_price = %s WHERE id = %s",
        (min_qty, unit_price, line_id),
    )


def delete_price_list_line(conn, line_id):
    conn.execute("DELETE FROM price_list_line WHERE id = %s", (line_id,))


# ---------------------------------------------------------------------------
# Price resolution
# ---------------------------------------------------------------------------

def get_price_for_product(conn, price_list_id, product_id, qty=1):
    """Return the best-matching tier price, or None if no tier applies."""
    row = conn.execute("""
        SELECT unit_price FROM price_list_line
        WHERE price_list_id = %s AND product_id = %s AND min_qty <= %s
        ORDER BY min_qty DESC LIMIT 1
    """, (price_list_id, product_id, qty)).fetchone()
    return float(row['unit_price']) if row else None


def get_price_tiers_for_price_list(conn, price_list_id):
    """Return {product_id: [(min_qty, unit_price), ...]} sorted desc by
    min_qty, for embedding as client-side auto-populate data."""
    rows = conn.execute("""
        SELECT product_id, min_qty, unit_price FROM price_list_line
        WHERE price_list_id = %s
        ORDER BY product_id, min_qty DESC
    """, (price_list_id,)).fetchall()
    tiers: dict = {}
    for r in rows:
        tiers.setdefault(r['product_id'], []).append(
            (float(r['min_qty']), float(r['unit_price'])))
    return tiers


def assign_customer_price_list(conn, customer_id, price_list_id):
    """price_list_id may be None to unassign."""
    conn.execute(
        "UPDATE customer SET price_list_id = %s WHERE id = %s",
        (price_list_id, customer_id),
    )


def get_customer_price_list_id(conn, customer_id):
    """Return the customer's assigned price_list_id regardless of whether
    it is currently active/effective (used to pre-select the assignment
    dropdown in the UI). Pricing lookups use
    _get_effective_customer_price_list_id instead."""
    row = conn.execute(
        "SELECT price_list_id FROM customer WHERE id = %s", (customer_id,)
    ).fetchone()
    return row['price_list_id'] if row else None


def _get_effective_customer_price_list_id(conn, customer_id, as_of=None):
    as_of = as_of or datetime.date.today().isoformat()
    row = conn.execute("""
        SELECT pl.* FROM customer c
        JOIN price_list pl ON pl.id = c.price_list_id
        WHERE c.id = %s AND pl.is_active = TRUE
    """, (customer_id,)).fetchone()
    if not row:
        return None
    pl = dict(row)
    return pl['id'] if _is_effective(pl, as_of) else None


def get_customer_price(conn, customer_id, product_id, qty=1):
    """Return the price a customer's assigned, currently-effective price
    list gives this product at this qty, or None (no assignment, list
    inactive/expired, or product not listed)."""
    price_list_id = _get_effective_customer_price_list_id(conn, customer_id)
    if not price_list_id:
        return None
    return get_price_for_product(conn, price_list_id, product_id, qty)


def get_customer_price_tiers(conn, customer_id):
    """Return get_price_tiers_for_price_list() for a customer's assigned,
    currently-effective price list, or {} if none applies."""
    price_list_id = _get_effective_customer_price_list_id(conn, customer_id)
    if not price_list_id:
        return {}
    return get_price_tiers_for_price_list(conn, price_list_id)
