"""
lot_core.py — Qt-free lot and serial number tracking.

Tables managed here:
  lot           — a traceable batch of one product (received or produced)
  serial_number — individual unit within (or independent of) a lot

Lot status lifecycle:
  available → quarantine | hold → available | rejected | consumed

Serial number status lifecycle:
  available → issued | scrapped | returned

Lot numbers are generated as <PRODUCT_ID>-LOT-<YYYYMMDD>-<NNN> by default,
but callers can pass any string (e.g. a supplier's lot number on receipt).
"""

from datetime import date


LOT_STATUSES = ('available', 'quarantine', 'hold', 'consumed', 'rejected')
SERIAL_STATUSES = ('available', 'issued', 'scrapped', 'returned')


def ensure_lot_tables(conn):
    """Create lot / serial_number tables and backfill FK columns. No commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lot (
            id SERIAL PRIMARY KEY,
            lot_number TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL REFERENCES product(id),
            qty REAL NOT NULL DEFAULT 0.0,
            received_date TEXT,
            expiry_date TEXT,
            status TEXT NOT NULL DEFAULT 'available',
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS lot_product_id ON lot(product_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS serial_number (
            id SERIAL PRIMARY KEY,
            serial_number TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL REFERENCES product(id),
            lot_id INTEGER REFERENCES lot(id),
            status TEXT NOT NULL DEFAULT 'available',
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS sn_product_id ON serial_number(product_id)"
    )
    # Backfill FK columns onto existing tables
    conn.execute(
        "ALTER TABLE inventory_transaction ADD COLUMN IF NOT EXISTS lot_id INTEGER REFERENCES lot(id)"
    )
    conn.execute(
        "ALTER TABLE wo_material ADD COLUMN IF NOT EXISTS lot_id INTEGER REFERENCES lot(id)"
    )


# ---------------------------------------------------------------------------
# Lot number generation
# ---------------------------------------------------------------------------

def next_lot_number(conn, product_id):
    """Return the next auto-generated lot number for a product.

    Format: <product_id>-LOT-<YYYYMMDD>-<NNN>
    """
    today_str = date.today().strftime('%Y%m%d')
    prefix = f"{product_id}-LOT-{today_str}-"
    rows = conn.execute(
        "SELECT lot_number FROM lot WHERE lot_number LIKE %s",
        (prefix + '%',),
    ).fetchall()
    max_n = 0
    for r in rows:
        try:
            n = int(r['lot_number'].rsplit('-', 1)[-1])
            max_n = max(max_n, n)
        except (ValueError, IndexError):
            pass
    return f"{prefix}{max_n + 1:03d}"


# ---------------------------------------------------------------------------
# Lot queries
# ---------------------------------------------------------------------------

def list_lots(conn, product_id=None, status=None, expiry_before=None):
    """Return lots with optional filters.

    expiry_before: ISO date string — include lots expiring on or before this date.
    """
    where, params = ['1=1'], []
    if product_id:
        where.append("l.product_id = %s")
        params.append(product_id)
    if status:
        where.append("l.status = %s")
        params.append(status)
    if expiry_before:
        where.append("l.expiry_date IS NOT NULL AND l.expiry_date <= %s")
        params.append(expiry_before)
    rows = conn.execute(
        "SELECT l.id, l.lot_number, l.product_id, p.name AS product_name, "
        "l.qty, l.received_date, l.expiry_date, l.status, l.notes, "
        "l.created_by, l.created_at "
        "FROM lot l "
        "JOIN product p ON p.id = l.product_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY l.received_date DESC NULLS LAST, l.id DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_lot(conn, lot_id):
    """Return a single lot dict, or None."""
    row = conn.execute(
        "SELECT l.id, l.lot_number, l.product_id, p.name AS product_name, "
        "l.qty, l.received_date, l.expiry_date, l.status, l.notes, "
        "l.created_by, l.created_at "
        "FROM lot l "
        "JOIN product p ON p.id = l.product_id "
        "WHERE l.id = %s",
        (lot_id,),
    ).fetchone()
    return dict(row) if row else None


def get_lot_by_number(conn, lot_number):
    """Return a lot dict by lot_number, or None."""
    row = conn.execute(
        "SELECT l.id, l.lot_number, l.product_id, p.name AS product_name, "
        "l.qty, l.received_date, l.expiry_date, l.status, l.notes "
        "FROM lot l JOIN product p ON p.id = l.product_id "
        "WHERE l.lot_number = %s",
        (lot_number,),
    ).fetchone()
    return dict(row) if row else None


def get_lot_genealogy(conn, lot_id):
    """Trace a finished-good lot back to the raw material lots that fed it.

    Returns a list of inventory_transaction rows linked to the same WO
    where this lot was produced, showing which input lots were consumed.
    """
    # Find the WO that produced this lot (receive transaction on this lot)
    prod_rows = conn.execute(
        "SELECT reference FROM inventory_transaction "
        "WHERE lot_id = %s AND trans_type = 'receive' "
        "ORDER BY id DESC LIMIT 1",
        (lot_id,),
    ).fetchall()

    result = {'lot': get_lot(conn, lot_id), 'input_lots': []}
    if not prod_rows:
        return result

    wo_ref = prod_rows[0]['reference']  # e.g. "WO-2026-0001"
    input_rows = conn.execute(
        "SELECT it.id, it.product_id, p.name AS product_name, "
        "it.trans_type, it.quantity, it.lot_id, l.lot_number "
        "FROM inventory_transaction it "
        "JOIN product p ON p.id = it.product_id "
        "LEFT JOIN lot l ON l.id = it.lot_id "
        "WHERE it.reference = %s AND it.trans_type = 'issue' "
        "ORDER BY it.id",
        (wo_ref,),
    ).fetchall()
    result['input_lots'] = [dict(r) for r in input_rows]
    return result


# ---------------------------------------------------------------------------
# Lot mutations
# ---------------------------------------------------------------------------

def create_lot(conn, product_id, qty, received_date=None, expiry_date=None,
               lot_number=None, notes=None, created_by=None):
    """Insert a lot and return its id. Does not commit.

    If lot_number is None, an auto-generated number is used.
    """
    if lot_number is None:
        lot_number = next_lot_number(conn, product_id)
    row = conn.execute(
        "INSERT INTO lot (lot_number, product_id, qty, received_date, "
        "expiry_date, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,'available',%s,%s) RETURNING id",
        (lot_number, product_id, max(0.0, qty),
         received_date or date.today().isoformat(),
         expiry_date, notes, created_by),
    ).fetchone()
    return row['id']


def update_lot_status(conn, lot_id, status, notes=None):
    """Change a lot's status. Does not commit."""
    if status not in LOT_STATUSES:
        raise ValueError(f"Unknown lot status: {status!r}")
    conn.execute(
        "UPDATE lot SET status=%s" + (", notes=%s" if notes is not None else "") +
        " WHERE id=%s",
        ((status, notes, lot_id) if notes is not None else (status, lot_id)),
    )


def consume_lot_qty(conn, lot_id, qty):
    """Reduce a lot's remaining qty (e.g. on WO issue). Does not commit.

    Automatically marks the lot consumed when qty reaches zero.
    Returns the new remaining qty.
    """
    row = conn.execute(
        "UPDATE lot SET qty = GREATEST(0, qty - %s) "
        "WHERE id=%s RETURNING qty",
        (abs(qty), lot_id),
    ).fetchone()
    new_qty = row['qty'] if row else 0.0
    if new_qty <= 0:
        conn.execute(
            "UPDATE lot SET status='consumed' WHERE id=%s AND status='available'",
            (lot_id,),
        )
    return new_qty


def get_expiry_alerts(conn, days_ahead=30):
    """Return lots expiring within the next N days that are still available."""
    rows = conn.execute(
        "SELECT l.id, l.lot_number, l.product_id, p.name AS product_name, "
        "l.qty, l.expiry_date, l.status "
        "FROM lot l JOIN product p ON p.id = l.product_id "
        "WHERE l.status = 'available' "
        "  AND l.expiry_date IS NOT NULL "
        "  AND l.expiry_date <= (CURRENT_DATE + %s)::text "
        "ORDER BY l.expiry_date",
        (days_ahead,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Serial number queries and mutations
# ---------------------------------------------------------------------------

def list_serials(conn, product_id=None, lot_id=None, status=None):
    """Return serial numbers with optional filters."""
    where, params = ['1=1'], []
    if product_id:
        where.append("sn.product_id = %s")
        params.append(product_id)
    if lot_id:
        where.append("sn.lot_id = %s")
        params.append(lot_id)
    if status:
        where.append("sn.status = %s")
        params.append(status)
    rows = conn.execute(
        "SELECT sn.id, sn.serial_number, sn.product_id, p.name AS product_name, "
        "sn.lot_id, l.lot_number, sn.status, sn.notes, sn.created_at "
        "FROM serial_number sn "
        "JOIN product p ON p.id = sn.product_id "
        "LEFT JOIN lot l ON l.id = sn.lot_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY sn.id DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def create_serial(conn, serial_number, product_id, lot_id=None,
                  notes=None, created_by=None):
    """Insert a serial number and return its id. Does not commit."""
    row = conn.execute(
        "INSERT INTO serial_number (serial_number, product_id, lot_id, "
        "status, notes, created_by) "
        "VALUES (%s,%s,%s,'available',%s,%s) RETURNING id",
        (serial_number.strip(), product_id, lot_id or None, notes, created_by),
    ).fetchone()
    return row['id']


def update_serial_status(conn, serial_id, status, notes=None):
    """Change a serial number's status. Does not commit."""
    if status not in SERIAL_STATUSES:
        raise ValueError(f"Unknown serial status: {status!r}")
    conn.execute(
        "UPDATE serial_number SET status=%s" +
        (", notes=%s" if notes is not None else "") + " WHERE id=%s",
        ((status, notes, serial_id) if notes is not None else (status, serial_id)),
    )
