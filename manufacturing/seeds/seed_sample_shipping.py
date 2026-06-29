"""seed_sample_shipping.py — sample Shipping department data.

Covers: 8 shipments spanning every status (pending, shipped, delivered,
returned) and 2–4 line items each (bicycle parts).

All rows are tagged so they can be removed without touching real data.
so_id is NULL in all sample rows; it links to the sales_order table but
requires seed_sample_sales to have been run and rows to be associated
manually.

Usage::

    python -m manufacturing.seeds.seed_sample_shipping            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_shipping --reset    # remove + re-add
    python -m manufacturing.seeds.seed_sample_shipping --remove   # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-SHIP-"
SHIP_PREFIX = "SMPL-SH-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment (
            id SERIAL PRIMARY KEY,
            ship_number TEXT NOT NULL UNIQUE,
            so_id INTEGER,
            ship_date TEXT,
            carrier TEXT,
            tracking_number TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment_item (
            id SERIAL PRIMARY KEY,
            shipment_id INTEGER NOT NULL REFERENCES shipment(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty INTEGER DEFAULT 1
        )
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Shipment data
# ---------------------------------------------------------------------------

SHIPMENTS = [
    # (ship_number, date_offset, carrier, tracking_number, status, notes, items)
    # items: list of (description, qty)
    (
        f"{SHIP_PREFIX}001", -28, "FedEx", "274899689001",
        "delivered", "Standard ground — delivered to loading dock",
        [
            ("Road Bike Frame — Carbon 54cm", 2),
            ("700c Front Wheel Assembly", 2),
            ("Drop Handlebar 42cm", 4),
            ("Racing Saddle", 2),
        ],
    ),
    (
        f"{SHIP_PREFIX}002", -21, "UPS", "1Z999AA10123456001",
        "delivered", "Residential delivery confirmed",
        [
            ("Mountain Bike Frame — Aluminum 17in", 3),
            ("26in Knobby Tire", 6),
            ("26in Inner Tube", 6),
            ("Disc Brake Rotor 180mm", 4),
        ],
    ),
    (
        f"{SHIP_PREFIX}003", -14, "USPS", "9400111899223800000001",
        "delivered", "Delivered — signature obtained",
        [
            ("Aluminum Stem 90mm", 8),
            ("Ergonomic Grip Set", 10),
            ("Seat Post 27.2mm x 350mm", 5),
        ],
    ),
    (
        f"{SHIP_PREFIX}004", -7, "FedEx", "274899689002",
        "shipped", "In transit — estimated 2-day delivery",
        [
            ("Road Bike Crankset 170mm", 4),
            ("Chain 11-Speed", 4),
            ("Rear Derailleur 11-Speed", 4),
            ("Front Derailleur Braze-On", 4),
        ],
    ),
    (
        f"{SHIP_PREFIX}005", -5, "DHL", "1234567890001",
        "shipped", "International — customs cleared",
        [
            ("700c Rear Wheel Hub Flange", 10),
            ("Spoke Set 32H Stainless", 5),
            ("700c Rim 32H Double-Wall", 5),
        ],
    ),
    (
        f"{SHIP_PREFIX}006", -2, "UPS", "1Z999AA10123456002",
        "pending", "Label printed — awaiting carrier pickup",
        [
            ("Hybrid Bike Frame 19in", 1),
            ("Flat Handlebar 680mm", 2),
            ("V-Brake Caliper Set", 2),
            ("Hybrid Comfort Saddle Wide", 1),
        ],
    ),
    (
        f"{SHIP_PREFIX}007", -1, "FedEx", "274899689003",
        "pending", "Packing in progress",
        [
            ("Kids Bike Frame 20in", 5),
            ("20in Training Wheel Set", 5),
        ],
    ),
    (
        f"{SHIP_PREFIX}008", -18, "UPS", "1Z999AA10123456003",
        "returned", "Customer refused delivery — damaged in transit",
        [
            ("Road Bike Frame — Carbon 56cm", 1),
            ("Carbon Fork 1-1/8in Tapered", 1),
            ("Integrated Headset 44mm", 1),
        ],
    ),
]


def _shipments_present(conn) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM shipment WHERE ship_number LIKE %s",
        (f"{SHIP_PREFIX}%",),
    ).fetchone()[0] > 0


def _seed_shipments(conn):
    for (ship_number, date_offset, carrier, tracking,
         status, notes, items) in SHIPMENTS:
        existing = conn.execute(
            "SELECT id FROM shipment WHERE ship_number = %s",
            (ship_number,),
        ).fetchone()
        if existing:
            ship_id = existing[0]
        else:
            ship_id = conn.execute(
                "INSERT INTO shipment"
                " (ship_number, so_id, ship_date, carrier,"
                "  tracking_number, status, notes, created_by)"
                " VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)"
                " RETURNING id",
                (ship_number, _d(date_offset), carrier, tracking,
                 status, notes, TAG),
            ).fetchone()[0]
        for description, qty in items:
            if conn.execute(
                "SELECT 1 FROM shipment_item"
                " WHERE shipment_id = %s AND description = %s",
                (ship_id, description),
            ).fetchone():
                continue
            conn.execute(
                "INSERT INTO shipment_item"
                " (shipment_id, description, product_id, qty)"
                " VALUES (%s, %s, NULL, %s)",
                (ship_id, description, qty),
            )
    conn.commit()


def _remove_shipments(conn):
    ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM shipment WHERE ship_number LIKE %s",
            (f"{SHIP_PREFIX}%",),
        ).fetchall()
    ]
    if ids:
        placeholders = ",".join(["%s"] * len(ids))
        conn.execute(
            f"DELETE FROM shipment_item WHERE shipment_id IN ({placeholders})",
            ids,
        )
    conn.execute(
        "DELETE FROM shipment WHERE ship_number LIKE %s",
        (f"{SHIP_PREFIX}%",),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    if _shipments_present(conn):
        print("Shipping sample data already present — skipping.")
        return
    _seed_shipments(conn)
    print("Shipping sample data seeded.")


def remove(conn):
    _remove_shipments(conn)
    print("Shipping sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Shipping sample data")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--reset",  action="store_true", help="Remove then re-add")
    grp.add_argument("--remove", action="store_true", help="Remove only")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.remove:
            remove(conn)
        elif args.reset:
            remove(conn)
            seed(conn)
        else:
            seed(conn)
    finally:
        conn.close()


