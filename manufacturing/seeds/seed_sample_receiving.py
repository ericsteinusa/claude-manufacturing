"""seed_sample_receiving.py — sample Receiving department data.

Covers: 8 receipts spanning every status (pending, partial, received,
rejected), with 2–4 line items per receipt using realistic manufacturing
supply descriptions.  All rows are tagged so they can be removed without
touching real data.

``po_id`` is stored as NULL in all seed rows because it references
``purchase_order.id`` and the purchase-order seed may not have been run;
there is no FK constraint enforcing this relationship.

Usage::

    python -m manufacturing.seeds.seed_sample_receiving            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_receiving --reset    # remove + re-add
    python -m manufacturing.seeds.seed_sample_receiving --remove   # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-RCV-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving (
            id SERIAL PRIMARY KEY,
            rcv_number TEXT NOT NULL UNIQUE,
            po_id INTEGER,
            rcv_date TEXT,
            supplier TEXT,
            carrier TEXT,
            tracking_number TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving_item (
            id SERIAL PRIMARY KEY,
            receiving_id INTEGER NOT NULL REFERENCES receiving(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty_ordered INTEGER DEFAULT 1,
            qty_received INTEGER DEFAULT 0
        )
    """)
    conn.execute(
        "ALTER TABLE receiving ADD COLUMN IF NOT EXISTS created_by TEXT"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Receipt data
# ---------------------------------------------------------------------------

# (rcv_number, rcv_date_offset, supplier, carrier, tracking_number,
#  status, notes)
RECEIPTS = [
    (f"{TAG}001", -28, "Steel Works Inc.", "UPS",
     "1Z999AA10123456784", "pending",
     "Awaiting dock assignment"),
    (f"{TAG}002", -25, "Metro Rubber Products", "FedEx",
     "770199000456123789", "pending",
     "Expected delivery this week"),
    (f"{TAG}003", -20, "Apex Fasteners LLC", "UPS",
     "1Z999AA10987654321", "partial",
     "Back-ordered items pending second shipment"),
    (f"{TAG}004", -15, "Allied Bearings Corp.", "DHL",
     "1234567891234567", "partial",
     "Partial shipment; remainder ships next week"),
    (f"{TAG}005", -12, "Delta Components Co.", "FedEx",
     "770199001122334455", "received",
     "All items verified and put away"),
    (f"{TAG}006", -8, "Summit Fabricators", "UPS",
     "1Z999AA10246813579", "received",
     "Inspected and signed off by receiving manager"),
    (f"{TAG}007", -4, "Pacific Rim Parts", "USPS",
     "9400111899223401000678", "received",
     "No discrepancies noted"),
    (f"{TAG}008", -2, "National Coating Supply", "FedEx",
     "770199009988776655", "rejected",
     "Wrong paint color; entire shipment returned to supplier"),
]

# {rcv_number: [(description, qty_ordered, qty_received), ...]}
ITEMS = {
    f"{TAG}001": [
        ('1.5" OD Steel Tubing, 6061 Grade, 20 ft lengths', 50, 0),
        ('3/8" Hex Head Cap Screws, Grade 8, zinc-plated (box/100)', 20, 0),
        ('Sheet Metal, 11-gauge, 4x8 ft panels', 30, 0),
    ],
    f"{TAG}002": [
        ('Natural Rubber Gaskets, 3" ID x 4" OD', 200, 0),
        ('EPDM O-Ring Seals, AS568-210 (bag/50)', 500, 0),
        ('Neoprene Strip, 1/4" thick x 2" wide, 10 ft rolls', 40, 0),
    ],
    f"{TAG}003": [
        ('M10 x 1.5mm Hex Bolts, Grade 10.9, 50mm (box/50)', 30, 30),
        ('1/4" Drive Socket Set, SAE/Metric, 40-piece', 5, 3),
        ('Lock Washers, #10, stainless steel (box/100)', 25, 25),
        ('5/16" Nylon Insert Lock Nuts (box/100)', 40, 20),
    ],
    f"{TAG}004": [
        ('Deep Groove Ball Bearings, 6204-2RS, 20mm bore', 60, 40),
        ('Needle Roller Bearings, HK2020, 20x26x20mm', 30, 30),
        ('Thrust Washers, 22mm ID, hardened steel', 100, 50),
    ],
    f"{TAG}005": [
        ('Cold-Drawn Steel Rod, 1" diameter, 12 ft', 24, 24),
        ('Flat Washer, SAE, 5/16" (box/100)', 15, 15),
        ('3/4" NPT Pipe Nipples, Schedule 40, 6" length', 36, 36),
        ('Steel Angle Iron, 2x2x1/4", 10 ft', 20, 20),
    ],
    f"{TAG}006": [
        ('Carbon Steel Weld Fittings, 1/2" 90-deg Elbow', 80, 80),
        ('Mild Steel Plate, 1/4" thick, 24x48"', 12, 12),
        ('Structural Steel Channel, 3x4.1, 10 ft', 16, 16),
    ],
    f"{TAG}007": [
        ('Industrial Roller Chain, ANSI #60, 10 ft section', 8, 8),
        ('Compression Springs, 0.5" OD x 2" free length (pack/10)', 20, 20),
        ('Rubber Anti-Vibration Mounts, M8 stud (pack/4)', 25, 25),
        ('Silicone Sealant, High-Temp 600F, 10.1 oz cartridge', 36, 36),
    ],
    f"{TAG}008": [
        ('Acrylic Enamel Paint, Machinery Gray, 1-gallon', 24, 0),
        ('Two-Part Epoxy Primer, 1-quart kit', 12, 0),
        ('Aerosol Touch-Up Paint, Safety Yellow, 12oz (case/12)', 6, 0),
    ],
}


def _receipts_present(conn) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM receiving WHERE rcv_number LIKE %s",
        (f"{TAG}%",),
    ).fetchone()[0] > 0


def _seed_receipts(conn):
    if _receipts_present(conn):
        print("Receiving sample data already present - skipping.")
        return
    for rcv_number, date_offset, supplier, carrier, tracking, status, notes \
            in RECEIPTS:
        cur = conn.execute(
            "INSERT INTO receiving"
            " (rcv_number, po_id, rcv_date, supplier, carrier,"
            " tracking_number, status, notes, created_by)"
            " VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s)"
            " RETURNING id",
            (rcv_number, _d(date_offset), supplier, carrier,
             tracking, status, notes, TAG),
        )
        rcv_id = cur.fetchone()[0]
        for desc, qty_ordered, qty_received in ITEMS[rcv_number]:
            conn.execute(
                "INSERT INTO receiving_item"
                " (receiving_id, description, product_id,"
                " qty_ordered, qty_received)"
                " VALUES (%s, %s, NULL, %s, %s)",
                (rcv_id, desc, qty_ordered, qty_received),
            )
    conn.commit()
    print("Receiving sample data seeded.")


def _remove_receipts(conn):
    conn.execute(
        "DELETE FROM receiving_item WHERE receiving_id IN"
        " (SELECT id FROM receiving WHERE rcv_number LIKE %s)",
        (f"{TAG}%",),
    )
    conn.execute(
        "DELETE FROM receiving WHERE rcv_number LIKE %s",
        (f"{TAG}%",),
    )
    conn.commit()
    print("Receiving sample data removed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_receipts(conn)


def remove(conn):
    _remove_receipts(conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Receiving sample data")
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


