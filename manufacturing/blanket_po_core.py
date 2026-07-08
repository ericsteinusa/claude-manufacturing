"""
blanket_po_core.py — Qt-free Blanket Purchase Orders & Call-offs (P3-E).

A blanket PO is a standing supplier agreement: a vendor, a validity window,
and a ceiling tracked either by total value or total quantity (not both).
"Call-offs" (releases) draw down against that ceiling over time, each with
its own delivery date. This is a header-level agreement, not a multi-line
PO — there is no per-item breakdown, so it does not touch ``purchase_order``
/ ``po_item`` or ``purchase_orders_core.receive_po_item`` (pinned by
exact-SQL-asserting tests) at all; it is a standalone tracking layer,
following the same "new module, don't modify the pinned one" precedent as
``landed_cost_core.py``.

There is no scheduler anywhere in this codebase (the only periodic-job
precedent, ``management.send_daily_digest``, is manually invoked, not a
running cron). So auto-close/auto-expire is computed lazily: every read
(``list_blanket_pos``/``get_blanket_po``) and every ``create_release`` call
re-syncs the status via ``_sync_status`` and persists it if it changed —
no separate scheduled job is introduced.

Every function takes an open connection; the caller owns the transaction
(same convention as landed_cost_core / wms_core).
"""

from __future__ import annotations

from datetime import datetime, date

from .log_utils import get_logger
from .mrp_core import next_sequence_number

log = get_logger(__name__)

BLANKET_STATUSES = ('open', 'closed', 'expired', 'cancelled')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_blanket_po_tables(conn) -> None:
    """Create blanket_po tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blanket_po (
            id                SERIAL PRIMARY KEY,
            blanket_number    TEXT UNIQUE,
            supplier_id       INTEGER,
            description       TEXT DEFAULT '',
            total_value       REAL DEFAULT 0,
            total_qty         REAL DEFAULT 0,
            start_date        TEXT DEFAULT '',
            end_date          TEXT DEFAULT '',
            status            TEXT DEFAULT 'open',
            notes             TEXT DEFAULT '',
            created_by        TEXT DEFAULT '',
            created_at        TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blanket_po_release (
            id               SERIAL PRIMARY KEY,
            blanket_po_id    INTEGER NOT NULL REFERENCES blanket_po(id) ON DELETE CASCADE,
            release_number   TEXT DEFAULT '',
            qty              REAL DEFAULT 0,
            value            REAL DEFAULT 0,
            delivery_date    TEXT DEFAULT '',
            notes            TEXT DEFAULT '',
            created_by       TEXT DEFAULT '',
            created_at       TEXT DEFAULT ''
        )
    """)


def next_blanket_number(conn) -> str:
    year = datetime.now().year
    rows = conn.execute(
        "SELECT blanket_number FROM blanket_po WHERE blanket_number LIKE %s",
        (f"BPO-{year}-%",),
    ).fetchall()
    existing = [dict(r)['blanket_number'] for r in rows]
    return next_sequence_number(existing, f"BPO-{year}-")


# ---------------------------------------------------------------------------
# Status sync (lazy auto-close / auto-expire)
# ---------------------------------------------------------------------------

def _released_totals(conn, blanket_po_id: int) -> tuple:
    row = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS qty, COALESCE(SUM(value), 0) AS value "
        "FROM blanket_po_release WHERE blanket_po_id = %s",
        (blanket_po_id,),
    ).fetchone()
    d = dict(row)
    return float(d['qty'] or 0.0), float(d['value'] or 0.0)


def _sync_status(conn, blanket_po_id: int) -> str:
    """Recompute and persist a blanket PO's effective status. Returns the
    (possibly updated) status. Only writes if the status actually changed."""
    header = conn.execute(
        "SELECT status, total_value, total_qty, end_date FROM blanket_po WHERE id = %s",
        (blanket_po_id,),
    ).fetchone()
    if not header:
        return ''
    h = dict(header)
    current = h['status']
    if current in ('cancelled', 'closed'):
        return current

    released_qty, released_value = _released_totals(conn, blanket_po_id)
    total_value = float(h['total_value'] or 0.0)
    total_qty = float(h['total_qty'] or 0.0)

    new_status = current
    fully_released = (
        (total_value > 0 and released_value >= total_value) or
        (total_qty > 0 and released_qty >= total_qty)
    )
    if fully_released:
        new_status = 'closed'
    elif h['end_date']:
        try:
            end = datetime.strptime(h['end_date'][:10], '%Y-%m-%d').date()
            if end < date.today():
                new_status = 'expired'
        except ValueError:
            pass

    if new_status != current:
        conn.execute(
            "UPDATE blanket_po SET status = %s WHERE id = %s",
            (new_status, blanket_po_id),
        )
    return new_status


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _with_balances(conn, row: dict) -> dict:
    d = dict(row)
    released_qty, released_value = _released_totals(conn, d['id'])
    d['total_value'] = float(d['total_value'] or 0.0)
    d['total_qty'] = float(d['total_qty'] or 0.0)
    d['released_value'] = released_value
    d['released_qty'] = released_qty
    d['remaining_value'] = max(d['total_value'] - released_value, 0.0)
    d['remaining_qty'] = max(d['total_qty'] - released_qty, 0.0)
    return d


def list_blanket_pos(conn, status: str | None = None, supplier_id: int | None = None) -> list:
    sql = """
        SELECT bp.*, s.company_name AS supplier_name
        FROM blanket_po bp
        LEFT JOIN supplier s ON s.id = bp.supplier_id
        WHERE 1=1
    """
    params: list = []
    if status:
        sql += " AND bp.status = %s"
        params.append(status)
    if supplier_id:
        sql += " AND bp.supplier_id = %s"
        params.append(supplier_id)
    sql += " ORDER BY bp.id DESC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['status'] = _sync_status(conn, d['id'])
        if status and d['status'] != status:
            continue
        out.append(_with_balances(conn, d))
    return out


def get_blanket_po(conn, blanket_po_id: int) -> dict | None:
    _sync_status(conn, blanket_po_id)
    row = conn.execute("""
        SELECT bp.*, s.company_name AS supplier_name
        FROM blanket_po bp
        LEFT JOIN supplier s ON s.id = bp.supplier_id
        WHERE bp.id = %s
    """, (blanket_po_id,)).fetchone()
    if not row:
        return None
    return _with_balances(conn, dict(row))


def list_releases(conn, blanket_po_id: int) -> list:
    rows = conn.execute("""
        SELECT * FROM blanket_po_release
        WHERE blanket_po_id = %s
        ORDER BY id
    """, (blanket_po_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def create_blanket_po(conn, supplier_id: int | None, description: str,
                       total_value: float, total_qty: float,
                       start_date: str, end_date: str,
                       notes: str, created_by: str) -> int:
    """Create a blanket PO. Raises ValueError if neither total_value nor
    total_qty is positive, or if end_date is before start_date."""
    total_value = float(total_value or 0)
    total_qty = float(total_qty or 0)
    if total_value <= 0 and total_qty <= 0:
        raise ValueError("Enter a total value or a total quantity to track against.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    blanket_number = next_blanket_number(conn)
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO blanket_po "
        "(blanket_number, supplier_id, description, total_value, total_qty, "
        "start_date, end_date, status, notes, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (blanket_number, supplier_id, description or '', total_value, total_qty,
         start_date or '', end_date or '', 'open', notes or '', created_by or '', now),
    ).fetchone()
    return row['id']


def create_release(conn, blanket_po_id: int, qty: float, value: float,
                    delivery_date: str, notes: str, created_by: str) -> int:
    """Record a call-off against a blanket PO. Raises ValueError if the
    blanket doesn't exist, isn't open, or the release would exceed the
    remaining balance."""
    blanket = get_blanket_po(conn, blanket_po_id)
    if not blanket:
        raise ValueError("Blanket PO not found.")
    if blanket['status'] != 'open':
        raise ValueError(f"Blanket PO is {blanket['status']} — cannot add a call-off.")

    qty = float(qty or 0)
    value = float(value or 0)

    if blanket['total_value'] > 0 and value > blanket['remaining_value']:
        raise ValueError(
            f"Call-off value ${value:.2f} exceeds remaining balance "
            f"${blanket['remaining_value']:.2f}.")
    if blanket['total_qty'] > 0 and qty > blanket['remaining_qty']:
        raise ValueError(
            f"Call-off qty {qty:g} exceeds remaining balance {blanket['remaining_qty']:g}.")

    releases = list_releases(conn, blanket_po_id)
    release_number = f"REL-{len(releases) + 1:03d}"
    now = datetime.now().isoformat()
    row = conn.execute(
        "INSERT INTO blanket_po_release "
        "(blanket_po_id, release_number, qty, value, delivery_date, notes, created_by, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (blanket_po_id, release_number, qty, value, delivery_date or '',
         notes or '', created_by or '', now),
    ).fetchone()
    _sync_status(conn, blanket_po_id)
    return row['id']


def cancel_blanket_po(conn, blanket_po_id: int) -> None:
    """Cancel a blanket PO. Raises ValueError unless it is currently open."""
    blanket = get_blanket_po(conn, blanket_po_id)
    if not blanket:
        raise ValueError("Blanket PO not found.")
    if blanket['status'] != 'open':
        raise ValueError(f"Blanket PO is already {blanket['status']}.")
    conn.execute(
        "UPDATE blanket_po SET status = %s WHERE id = %s",
        ('cancelled', blanket_po_id),
    )
