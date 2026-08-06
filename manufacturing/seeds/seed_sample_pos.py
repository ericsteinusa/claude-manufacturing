"""seed_sample_pos.py — sample purchase orders for the web PO pages.

Seeds a handful of purchase orders spanning every status (draft, sent,
partial, received, cancelled) with line items drawn from the sample products,
so the web purchase-order pages (`/po/...`) can be exercised with realistic
data: the status filter, the status pills, partial receipts and totals.

Sample POs are tagged by a ``SMPL-PO-`` ``po_number`` prefix (the column is
UNIQUE, so the prefix is both the tag and a natural key for idempotency).
Line items reference the sample products seeded by
``manufacturing.seed_sample_products`` (``bin = 'SAMPLE'``); run that first for
the products to be linked. A line whose product is missing is still inserted
with its description and a NULL ``product_id`` so the PO is never empty.

Each PO is attached to the first existing supplier row. If none exists yet
(this seed can run before ``seed_sample_purchasing``, which is what
actually creates suppliers), a minimal fallback supplier is created instead
of leaving ``supplier_id`` NULL — tagged ``created_by='SMPL-PO-FALLBACK'``
and removed along with the sample POs on ``--reset``/``--remove``.

Usage::

    python -m manufacturing.seeds.seed_sample_pos            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_pos --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_pos --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection
from ..purchase_orders_core import ensure_po_tables


SAMPLE_PO_PREFIX = "SMPL-PO-"   # po_number prefix marking sample rows
FALLBACK_SUPPLIER_TAG = "SMPL-PO-FALLBACK"  # created_by tag for the
# fallback supplier row created below when no supplier exists yet

# suffix, status, order_date offset (days ago), expected offset (days from
# order), received offset (days ago, or None if not yet received), notes,
# [(product_name, qty_ordered, unit_price, qty_received)]. Quantities
# received are consistent with the status (partial = some lines short,
# received = all full). received offset is only set for status='received'
# (matches set_po_status: received_date is only stamped on that transition,
# so it's what the supplier-scorecard's on-time % is computed from).
PURCHASE_ORDERS = [
    ("1", "draft", 0, 14, None, "Restock frame raw material", [
        ("Steel Tube", 100, 3.50, 0),
        ("Paint Can",   20, 12.00, 0),
    ]),
    ("2", "sent", 3, 14, None, "Wheel components — awaiting delivery", [
        ("Rim",  30, 18.00, 0),
        ("Tire", 25, 22.00, 0),
    ]),
    ("3", "partial", 10, 14, None, "Spokes partially received", [
        ("Spoke",      500, 0.40, 200),
        ("Inner Tube",  25, 6.50, 25),
    ]),
    ("4", "received", 20, 14, 7, "Cockpit parts — fully received", [
        ("Handlebar", 15, 14.00, 15),
        ("Seat",      15,  9.50, 15),
    ]),
    ("5", "cancelled", 8, 14, None, "Duplicate order — cancelled", [
        ("Tire", 10, 22.00, 0),
    ]),
]


def _first_supplier_id(conn):
    """Return an arbitrary supplier id to attach POs to.

    If the `supplier` table doesn't exist at all, schema.py's init_schema()
    (normally run via the Django app's startup) hasn't happened yet —
    that's a different, unsupported precondition than this seed can fix, so
    behave like every other seed here and return None rather than trying to
    create tables of our own.

    If the table exists but is empty (e.g. this seed ran before
    seed_sample_purchasing, which CLAUDE.md's own documented seed order
    does), create a minimal fallback supplier instead of leaving
    purchase_order.supplier_id NULL — a PO with no supplier is silently
    invisible to every supplier-portal account, which isn't a case any
    seed here should produce."""
    try:
        row = conn.execute(
            "SELECT id FROM supplier ORDER BY id LIMIT 1").fetchone()
    except Exception:
        return None
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO supplier (company_name, email, created_by)"
        " VALUES (%s,%s,%s) RETURNING id",
        ("Sample Fallback Supplier", "fallback-supplier@example.com",
         FALLBACK_SUPPLIER_TAG),
    ).fetchone()["id"]


def _sample_product_ids(conn):
    """Return ``{name: id}`` for the seeded sample products."""
    rows = conn.execute(
        "SELECT id, name FROM product WHERE bin = 'SAMPLE'").fetchall()
    return {r["name"]: r["id"] for r in rows}


def sample_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM purchase_order WHERE po_number LIKE %s",
        (SAMPLE_PO_PREFIX + "%",)).fetchone()[0] > 0


def remove_sample(conn):
    """Delete sample POs, their line items, and the fallback supplier (if
    one was created). Returns (pos, items)."""
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM purchase_order WHERE po_number LIKE %s",
        (SAMPLE_PO_PREFIX + "%",)).fetchall()]
    item_n = po_n = 0
    if ids:
        item_n = conn.execute(
            "DELETE FROM po_item WHERE po_id = ANY(%s)", (ids,)).rowcount
        po_n = conn.execute(
            "DELETE FROM purchase_order WHERE id = ANY(%s)", (ids,)).rowcount
    conn.execute(
        "DELETE FROM supplier WHERE created_by = %s", (FALLBACK_SUPPLIER_TAG,))
    return po_n, item_n


def seed_pos(conn):
    """Insert any missing sample POs. Returns (pos, items)."""
    supplier_id = _first_supplier_id(conn)
    products = _sample_product_ids(conn)
    pos = items = 0
    for suffix, status, ago, exp, received_ago, notes, lines in PURCHASE_ORDERS:
        po_number = SAMPLE_PO_PREFIX + suffix
        if conn.execute(
                "SELECT 1 FROM purchase_order WHERE po_number = %s",
                (po_number,)).fetchone():
            continue
        order_date = (date.today() - timedelta(days=ago)).isoformat()
        expected = (date.today() - timedelta(days=ago)
                    + timedelta(days=exp)).isoformat()
        received = (
            (date.today() - timedelta(days=received_ago)).isoformat()
            if received_ago is not None else None
        )
        po_id = conn.execute(
            "INSERT INTO purchase_order (po_number, supplier_id, order_date,"
            " expected_date, status, notes, received_date)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)"
            " RETURNING id",
            (po_number, supplier_id, order_date, expected, status, notes,
             received)
        ).fetchone()["id"]
        pos += 1
        for name, qty, price, received in lines:
            conn.execute(
                "INSERT INTO po_item (po_id, description, product_id,"
                " qty_ordered, unit_price, qty_received)"
                " VALUES (%s,%s,%s,%s,%s,%s)",
                (po_id, name, products.get(name), qty, price, received))
            items += 1
    return pos, items


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed sample purchase orders for the web PO pages.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample POs, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample POs only (no seeding)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        ensure_po_tables(conn)
        if args.remove or args.reset:
            po_n, item_n = remove_sample(conn)
            print(f"removed {po_n} sample POs ({item_n} line items)")
            if args.remove:
                conn.commit()
                return

        if sample_present(conn):
            print("Sample POs already present; use --reset to recreate.")
            return

        pos_n, items_n = seed_pos(conn)
        conn.commit()
        print(f"inserted {pos_n} purchase orders ({items_n} line items)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


