"""seed_sample_alerts.py — drive sample products below their reorder points.

Updates the on-hand ``amount`` for three sample products so the Inventory
Alerts panel on the Reports Dashboard shows real data. The products and their
reorder points are unchanged; only ``amount`` is lowered.

Requires ``manufacturing.seed_sample_products`` to have run first (products
must exist with ``bin = 'SAMPLE'``).

Usage::

    python -m manufacturing.seed_sample_alerts            # apply (idempotent)
    python -m manufacturing.seed_sample_alerts --remove   # restore original amounts
"""

import argparse

from .db_pg import get_db_connection

# (product_name, alert_amount, original_amount)
# alert_amount puts the product at or below its reorder_point.
# original_amount is what seed_sample_products inserted — used by --remove.
ALERT_LEVELS = [
    ("Rim",        15, 30),   # reorder=20 → critically low
    ("Tire",       18, 25),   # reorder=20 → low
    ("Inner Tube",  8, 25),   # reorder=20 → very low
]


def _sample_products(conn):
    """Return {name: id} for bin='SAMPLE' products."""
    rows = conn.execute(
        "SELECT id, name FROM product WHERE bin = 'SAMPLE'"
    ).fetchall()
    return {r["name"]: r["id"] for r in rows}


def alerts_active(conn):
    """True if any of the alert-level amounts are already applied."""
    products = _sample_products(conn)
    for name, alert_amt, _ in ALERT_LEVELS:
        pid = products.get(name)
        if pid is None:
            continue
        row = conn.execute(
            "SELECT amount FROM product WHERE id = %s", (pid,)
        ).fetchone()
        if row and row["amount"] == alert_amt:
            return True
    return False


def apply_alerts(conn):
    """Lower amounts for the alert products. Returns count updated."""
    products = _sample_products(conn)
    updated = 0
    for name, alert_amt, _ in ALERT_LEVELS:
        pid = products.get(name)
        if pid is None:
            print(f"  skip (not found): {name!r} — run seed_sample_products first")
            continue
        conn.execute(
            "UPDATE product SET amount = %s WHERE id = %s", (alert_amt, pid)
        )
        updated += 1
    return updated


def remove_alerts(conn):
    """Restore original amounts. Returns count restored."""
    products = _sample_products(conn)
    restored = 0
    for name, _, orig_amt in ALERT_LEVELS:
        pid = products.get(name)
        if pid is None:
            continue
        conn.execute(
            "UPDATE product SET amount = %s WHERE id = %s", (orig_amt, pid)
        )
        restored += 1
    return restored


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Drive sample products below reorder point for dashboard demos.")
    parser.add_argument("--remove", action="store_true",
                        help="restore original amounts (undo alert levels)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        if args.remove:
            n = remove_alerts(conn)
            conn.commit()
            print(f"restored original amounts for {n} products")
            return

        if alerts_active(conn):
            print("Alert levels already applied; use --remove to restore originals.")
            return

        n = apply_alerts(conn)
        conn.commit()
        print(f"set alert-level amounts for {n} products "
              f"(Rim->15, Tire->18, Inner Tube->8; reorder points: 20 each)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
