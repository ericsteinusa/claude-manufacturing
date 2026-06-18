"""seed_sample_wos.py — sample work orders for the Work Orders screen.

Seeds work orders spanning every status (draft, open, in_progress,
completed, cancelled) with materials drawn from the sample products seeded by
``manufacturing.seed_sample_products``. Run that seed first so products link
correctly.

Sample WOs are tagged by a ``SMPL-WO-`` ``wo_number`` prefix (the column is
UNIQUE, so the prefix is both the tag and a natural key for idempotency).

Usage::

    python -m manufacturing.seed_sample_wos            # add (idempotent)
    python -m manufacturing.seed_sample_wos --reset     # remove + re-add
    python -m manufacturing.seed_sample_wos --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from .db_pg import get_db_connection

SAMPLE_WO_PREFIX = "SMPL-WO-"

# (suffix, status, start_ago_days, due_offset_days, description,
#  product_name, quantity, notes,
#  [(material_name, qty_required, qty_issued)])
WORK_ORDERS = [
    ("1", "draft", 0, 14,
     "Assemble mountain bike batch", "Mountain Bike", 5,
     "Awaiting materials pick",
     [
         ("Bike Frame",     5,   0),
         ("Wheel Assembly", 10,  0),
         ("Handlebar",      5,   0),
         ("Seat",           5,   0),
     ]),
    ("2", "open", 2, 7,
     "Road bike production run", "Road Bike", 3,
     "Materials staged, ready to start",
     [
         ("Bike Frame",     3,   0),
         ("Wheel Assembly", 6,   0),
         ("Handlebar",      3,   0),
         ("Seat",           3,   0),
     ]),
    ("3", "in_progress", 5, 3,
     "Bike frame fabrication batch", "Bike Frame", 10,
     "Steel cut, painting in progress",
     [
         ("Steel Tube",  40,  40),
         ("Paint Can",   10,   5),
     ]),
    ("4", "completed", 20, -3,
     "Wheel assembly batch — Q2", "Wheel Assembly", 8,
     "All units passed QA",
     [
         ("Rim",        8,    8),
         ("Spoke",      256, 256),
         ("Tire",       8,    8),
         ("Inner Tube", 8,    8),
     ]),
    ("5", "cancelled", 10, 4,
     "Duplicate mountain bike order", "Mountain Bike", 2,
     "Cancelled — merged into SMPL-WO-1",
     []),
]


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_order (
            id SERIAL PRIMARY KEY,
            wo_number TEXT NOT NULL UNIQUE,
            product_id INTEGER,
            description TEXT,
            quantity INTEGER DEFAULT 1,
            start_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_material (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL REFERENCES work_order(id),
            product_id INTEGER,
            qty_required INTEGER DEFAULT 1,
            qty_issued INTEGER DEFAULT 0,
            notes TEXT
        )
    """)


def _sample_product_ids(conn):
    rows = conn.execute(
        "SELECT id, name FROM product WHERE bin = 'SAMPLE'").fetchall()
    return {r["name"]: r["id"] for r in rows}


def sample_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM work_order WHERE wo_number LIKE %s",
        (SAMPLE_WO_PREFIX + "%",)).fetchone()[0] > 0


def remove_sample(conn):
    """Delete sample WOs and their materials. Returns (wos, materials)."""
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM work_order WHERE wo_number LIKE %s",
        (SAMPLE_WO_PREFIX + "%",)).fetchall()]
    mat_n = wo_n = 0
    if ids:
        mat_n = conn.execute(
            "DELETE FROM wo_material WHERE wo_id = ANY(%s)",
            (ids,)).rowcount
        wo_n = conn.execute(
            "DELETE FROM work_order WHERE id = ANY(%s)",
            (ids,)).rowcount
    return wo_n, mat_n


def seed_wos(conn):
    """Insert any missing sample WOs. Returns (wos, materials)."""
    products = _sample_product_ids(conn)
    wos = mats = 0
    today = date.today()
    for (suffix, status, start_ago, due_offset,
         desc, product_name, qty, notes, materials) in WORK_ORDERS:
        wo_number = SAMPLE_WO_PREFIX + suffix
        if conn.execute(
                "SELECT 1 FROM work_order WHERE wo_number = %s",
                (wo_number,)).fetchone():
            continue
        start = (today - timedelta(days=start_ago)).isoformat()
        due = (today - timedelta(days=start_ago)
               + timedelta(days=due_offset)).isoformat()
        wo_id = conn.execute(
            "INSERT INTO work_order (wo_number, product_id, description,"
            " quantity, start_date, due_date, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (wo_number, products.get(product_name), desc,
             qty, start, due, status, notes)
        ).fetchone()["id"]
        wos += 1
        for mat_name, qty_req, qty_iss in materials:
            conn.execute(
                "INSERT INTO wo_material"
                " (wo_id, product_id, qty_required, qty_issued)"
                " VALUES (%s,%s,%s,%s)",
                (wo_id, products.get(mat_name), qty_req, qty_iss))
            mats += 1
    return wos, mats


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed sample work orders.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample WOs, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample WOs only (no seeding)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        _ensure_tables(conn)
        if args.remove or args.reset:
            wo_n, mat_n = remove_sample(conn)
            print(f"removed {wo_n} sample WOs ({mat_n} materials)")
            if args.remove:
                conn.commit()
                return

        if sample_present(conn):
            print("Sample WOs already present; use --reset to recreate.")
            return

        wo_n, mat_n = seed_wos(conn)
        conn.commit()
        print(f"inserted {wo_n} work orders ({mat_n} material lines)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
