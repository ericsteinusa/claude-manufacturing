"""seed_sample_products.py — sample products, BOMs and demand for testing.

Seeds a small but multi-level product structure plus some firm sales-order
demand, so the BOM editor, work-order explosion and the MRP engine can be
exercised end to end against realistic data. Sample products are tagged by
``bin = 'SAMPLE'`` so they are easy to spot in the inventory screen and to
remove cleanly. (``bin`` is used rather than ``supplier_id`` because the live
``product.supplier_id`` column is an integer foreign-key-style id, not free
text.)

The structure (two finished bikes that share sub-assemblies, so a component
has more than one parent — good for testing the level-by-level explosion):

    Mountain Bike (make)            Road Bike (make)
      ├─ Bike Frame (make) ×1         ├─ Bike Frame (make) ×1
      ├─ Wheel Assembly (make) ×2     ├─ Wheel Assembly (make) ×2
      ├─ Handlebar (buy) ×1           ├─ Handlebar (buy) ×1
      └─ Seat (buy) ×1                └─ Seat (buy) ×1

    Bike Frame (make)               Wheel Assembly (make)
      ├─ Steel Tube (buy) ×4          ├─ Rim (buy) ×1
      └─ Paint Can (buy) ×1, 10%      ├─ Spoke (buy) ×32
         scrap                        ├─ Tire (buy) ×1
                                      └─ Inner Tube (buy) ×1

Usage::

    python -m manufacturing.seeds.seed_sample_products            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_products --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_products --remove    # remove only

Removal deletes the sample sales orders, BOM rows and then the sample
products. If you have released MRP suggestions into requisitions/work orders
that reference these products, remove those first.
"""

import argparse
import sys
from datetime import date, timedelta

from ..db_pg import get_db_connection


SAMPLE_TAG = "SAMPLE"      # stored in product.bin to mark sample rows
SAMPLE_SO_PREFIX = "SMPL-SO-"  # sample sales-order number prefix

# name, item_type, on-hand, reorder_point, unit_cost, lead_time_days, uom
PRODUCTS = [
    ("Mountain Bike",   "make",   0,    0,   0.00,  1, "ea"),
    ("Road Bike",       "make",   0,    0,   0.00,  1, "ea"),
    ("Bike Frame",      "make",   0,    0,   0.00,  2, "ea"),
    ("Wheel Assembly",  "make",   0,    0,   0.00,  1, "ea"),
    ("Handlebar",       "buy",   15,   10,  14.00, 14, "ea"),
    ("Seat",            "buy",   15,   10,   9.50, 14, "ea"),
    ("Steel Tube",      "buy",  100,   50,   3.50, 14, "m"),
    ("Paint Can",       "buy",   20,   10,  12.00,  7, "can"),
    ("Rim",             "buy",   30,   20,  18.00, 21, "ea"),
    ("Spoke",           "buy",  500,  400,   0.40, 10, "ea"),
    ("Tire",            "buy",   25,   20,  22.00, 14, "ea"),
    ("Inner Tube",      "buy",   25,   20,   6.50, 10, "ea"),
]

# parent_name -> list of (component_name, qty_per, scrap_pct, unit)
BOMS = {
    "Mountain Bike": [
        ("Bike Frame",     1, 0.0, "ea"),
        ("Wheel Assembly", 2, 0.0, "ea"),
        ("Handlebar",      1, 0.0, "ea"),
        ("Seat",           1, 0.0, "ea"),
    ],
    "Road Bike": [
        ("Bike Frame",     1, 0.0, "ea"),
        ("Wheel Assembly", 2, 0.0, "ea"),
        ("Handlebar",      1, 0.0, "ea"),
        ("Seat",           1, 0.0, "ea"),
    ],
    "Bike Frame": [
        ("Steel Tube",     4, 0.0,  "m"),
        ("Paint Can",      1, 10.0, "can"),
    ],
    "Wheel Assembly": [
        ("Rim",            1, 0.0, "ea"),
        ("Spoke",         32, 0.0, "ea"),
        ("Tire",           1, 0.0, "ea"),
        ("Inner Tube",     1, 0.0, "ea"),
    ],
}

# Sample demand. so_number_suffix, status, [(product_name, qty, unit_price)].
# MRP counts only 'confirmed' orders as demand; the 'draft' one is seeded to
# demonstrate that it is correctly excluded from the plan.
SALES_ORDERS = [
    ("1", "confirmed", [("Mountain Bike", 10, 450.00)]),
    ("2", "confirmed", [("Road Bike", 4, 520.00),
                        ("Mountain Bike", 2, 450.00)]),
    ("3", "draft",     [("Road Bike", 5, 520.00)]),
]


def ensure_tables(conn):
    """Create the product / bom tables and item-master columns (idempotent).

    Mirrors the DDL in inventory.py / prod_prod_menu.py / bom.py so the seed is
    self-contained and needs no GUI modules. All statements are no-ops if the
    objects already exist.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            supplier_id TEXT,
            name TEXT NOT NULL,
            purchase_date TEXT,
            purchase_price REAL DEFAULT 0.0,
            bin TEXT,
            amount INTEGER DEFAULT 0,
            reorder_point INTEGER DEFAULT 0
        )
    """)
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS item_type TEXT "
        "DEFAULT 'buy'")
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS lead_time_days INTEGER "
        "DEFAULT 0")
    conn.execute(
        "ALTER TABLE product ADD COLUMN IF NOT EXISTS uom TEXT DEFAULT 'ea'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bom (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            qty_required REAL DEFAULT 1.0,
            unit TEXT,
            notes TEXT
        )
    """)
    conn.execute(
        "ALTER TABLE bom ADD COLUMN IF NOT EXISTS scrap_pct REAL DEFAULT 0.0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_order (
            id SERIAL PRIMARY KEY,
            so_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER,
            order_date TEXT,
            ship_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS so_item (
            id SERIAL PRIMARY KEY,
            so_id INTEGER NOT NULL REFERENCES sales_order(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0.0
        )
    """)


def _sample_ids(conn):
    """Return ``{name: id}`` for the currently seeded sample products."""
    rows = conn.execute(
        "SELECT id, name FROM product WHERE bin = %s",
        (SAMPLE_TAG,)).fetchall()
    return {r["name"]: r["id"] for r in rows}


def sample_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM product WHERE bin = %s",
        (SAMPLE_TAG,)).fetchone()[0] > 0


def remove_sample(conn):
    """Delete sample sales orders, BOM rows and products. Returns counts."""
    so_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM sales_order WHERE so_number LIKE %s",
        (SAMPLE_SO_PREFIX + "%",)).fetchall()]
    soi_n = so_n = 0
    if so_ids:
        soi_n = conn.execute(
            "DELETE FROM so_item WHERE so_id = ANY(%s)", (so_ids,)).rowcount
        so_n = conn.execute(
            "DELETE FROM sales_order WHERE id = ANY(%s)", (so_ids,)).rowcount

    ids = list(_sample_ids(conn).values())
    bom_n = prod_n = 0
    if ids:
        bom_n = conn.execute(
            "DELETE FROM bom WHERE product_id = ANY(%s) "
            "OR component_id = ANY(%s)", (ids, ids)).rowcount
        prod_n = conn.execute(
            "DELETE FROM product WHERE id = ANY(%s)", (ids,)).rowcount
    return prod_n, bom_n, so_n, soi_n


def seed_products(conn):
    """Insert any missing sample products. Returns the number added."""
    existing = set(_sample_ids(conn))
    added = 0
    for name, item_type, amount, rop, cost, lead, uom in PRODUCTS:
        if name in existing:
            continue
        conn.execute(
            "INSERT INTO product (name, bin, amount, reorder_point, "
            "purchase_price, item_type, lead_time_days, uom) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (name, SAMPLE_TAG, amount, rop, cost, item_type, lead, uom))
        added += 1
    return added


def seed_boms(conn):
    """Insert any missing sample BOM lines. Returns the number added."""
    ids = _sample_ids(conn)
    added = 0
    for parent_name, lines in BOMS.items():
        parent_id = ids.get(parent_name)
        if parent_id is None:
            print(f"  skip BOM (missing parent): {parent_name!r}",
                  file=sys.stderr)
            continue
        for comp_name, qty, scrap, unit in lines:
            comp_id = ids.get(comp_name)
            if comp_id is None:
                print(f"  skip line (missing component): {comp_name!r}",
                      file=sys.stderr)
                continue
            exists = conn.execute(
                "SELECT 1 FROM bom WHERE product_id = %s "
                "AND component_id = %s",
                (parent_id, comp_id)).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO bom (product_id, component_id, qty_required, "
                "unit, scrap_pct, notes) VALUES (%s,%s,%s,%s,%s,'sample')",
                (parent_id, comp_id, qty, unit, scrap))
            added += 1
    return added


def seed_sales_orders(conn):
    """Insert any missing sample sales orders. Returns (orders, lines)."""
    ids = _sample_ids(conn)
    today = date.today().isoformat()
    ship = (date.today() + timedelta(days=21)).isoformat()
    orders = lines = 0
    for suffix, status, items in SALES_ORDERS:
        so_number = SAMPLE_SO_PREFIX + suffix
        existing = conn.execute(
            "SELECT id FROM sales_order WHERE so_number = %s",
            (so_number,)).fetchone()
        if existing:
            continue
        cur = conn.execute(
            "INSERT INTO sales_order (so_number, order_date, ship_date, "
            "status, notes) VALUES (%s,%s,%s,%s,'sample') RETURNING id",
            (so_number, today, ship, status))
        so_id = cur.fetchone()["id"]
        orders += 1
        for prod_name, qty, price in items:
            pid = ids.get(prod_name)
            if pid is None:
                print(f"  skip SO line (missing product): {prod_name!r}",
                      file=sys.stderr)
                continue
            conn.execute(
                "INSERT INTO so_item (so_id, description, product_id, qty, "
                "unit_price) VALUES (%s,%s,%s,%s,%s)",
                (so_id, prod_name, pid, qty, price))
            lines += 1
    return orders, lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed sample products and BOMs.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample products, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample products only (no seeding)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        ensure_tables(conn)
        if args.remove or args.reset:
            prod_n, bom_n, so_n, soi_n = remove_sample(conn)
            print(f"removed {prod_n} sample products, {bom_n} BOM lines, "
                  f"{so_n} sales orders ({soi_n} lines)")
            if args.remove:
                conn.commit()
                return

        if sample_present(conn):
            print("Sample products already present; use --reset to recreate.")
            return

        products_n = seed_products(conn)
        boms_n = seed_boms(conn)
        orders_n, so_lines_n = seed_sales_orders(conn)
        conn.commit()
        print(f"inserted {products_n} products, {boms_n} BOM lines, "
              f"{orders_n} sales orders ({so_lines_n} lines)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


