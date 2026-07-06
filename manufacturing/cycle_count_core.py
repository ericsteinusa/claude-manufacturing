"""cycle_count_core.py — Qt-free structured cycle-count workflow.

Flow: generate_sheet() snapshots system on-hand qty for a group of products
(by bin, item_type, or an on-the-fly ABC value ranking — there is no
persisted category/ABC column, see COMPETITIVE_GAP_ANALYSIS.md P1-D) ->
enter_counts() records what was actually counted and computes variance ->
if every line matches (no variance) the sheet auto-posts immediately;
otherwise it is submitted to approval_workflow_core (entity_type=
'cycle_count') -> decide_cycle_count() records the approve/reject decision
and, once fully approved, post_cycle_count() posts one inventory_core
'adjust' transaction per variant line.

If no approval_rule is configured for 'cycle_count' (the org hasn't set one
up), submitting fails open — the sheet posts immediately rather than
blocking on a workflow nobody configured, matching the pre-existing
behavior where 'adjust' transactions could always be posted directly.
"""

import datetime

from .mrp_core import next_sequence_number
from .inventory_core import record_transaction
from .approval_workflow_core import submit_for_approval, decide_step

STATUSES = ('open', 'submitted', 'rejected', 'posted')
GROUP_BY_OPTIONS = ('bin', 'item_type', 'abc')
ABC_CLASSES = ('A', 'B', 'C')


def ensure_cycle_count_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycle_count (
            id           SERIAL PRIMARY KEY,
            count_number TEXT NOT NULL UNIQUE,
            group_by     TEXT NOT NULL DEFAULT 'bin',
            group_value  TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'open',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            submitted_at TIMESTAMPTZ,
            posted_at    TIMESTAMPTZ,
            notes        TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycle_count_line (
            id              SERIAL PRIMARY KEY,
            cycle_count_id  INTEGER NOT NULL REFERENCES cycle_count(id),
            product_id      INTEGER NOT NULL REFERENCES product(id),
            system_qty      REAL NOT NULL DEFAULT 0,
            counted_qty     REAL,
            variance_qty    REAL,
            posted          BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS cycle_count_line_cc_id "
        "ON cycle_count_line(cycle_count_id)"
    )


def _next_count_number(conn):
    yr = datetime.date.today().year
    prefix = f"CC-{yr}-"
    rows = conn.execute(
        "SELECT count_number FROM cycle_count WHERE count_number LIKE %s",
        (prefix + "%",),
    ).fetchall()
    return next_sequence_number([r['count_number'] for r in rows], prefix)


def compute_abc_classes(conn):
    """Rank active products by extended value (amount x purchase_price) and
    bucket into A (top 20%), B (next 30%), C (remaining 50%).

    Returns {product_id: 'A'|'B'|'C'}. Computed on the fly every call — there
    is no persisted ABC column (see module docstring).
    """
    rows = conn.execute("""
        SELECT id, COALESCE(amount, 0) * COALESCE(purchase_price, 0) AS value
        FROM product
        ORDER BY value DESC, id
    """).fetchall()
    n = len(rows)
    classes = {}
    for i, r in enumerate(rows):
        pct = (i + 1) / n if n else 1
        classes[r['id']] = 'A' if pct <= 0.2 else ('B' if pct <= 0.5 else 'C')
    return classes


def list_group_values(conn, group_by):
    """Return the selectable values for a group_by, for populating a form."""
    if group_by == 'bin':
        rows = conn.execute(
            "SELECT DISTINCT bin FROM product "
            "WHERE bin IS NOT NULL AND bin != '' ORDER BY bin"
        ).fetchall()
        return [r['bin'] for r in rows]
    if group_by == 'item_type':
        return ['make', 'buy']
    if group_by == 'abc':
        return list(ABC_CLASSES)
    raise ValueError(f"group_by must be one of {GROUP_BY_OPTIONS}")


def generate_sheet(conn, group_by, group_value, created_by):
    """Create a cycle_count header + one line per matching product,
    snapshotting each product's current on-hand qty. Returns the new id.
    """
    if group_by not in GROUP_BY_OPTIONS:
        raise ValueError(f"group_by must be one of {GROUP_BY_OPTIONS}")

    if group_by == 'abc':
        classes = compute_abc_classes(conn)
        product_ids = [pid for pid, cls in classes.items() if cls == group_value]
        rows = (
            conn.execute(
                "SELECT id, COALESCE(amount, 0) AS amount FROM product "
                "WHERE id = ANY(%s) ORDER BY id",
                (product_ids,),
            ).fetchall()
            if product_ids else []
        )
    elif group_by == 'bin':
        rows = conn.execute(
            "SELECT id, COALESCE(amount, 0) AS amount FROM product "
            "WHERE bin = %s ORDER BY id",
            (group_value,),
        ).fetchall()
    else:  # item_type
        rows = conn.execute(
            "SELECT id, COALESCE(amount, 0) AS amount FROM product "
            "WHERE COALESCE(item_type, 'buy') = %s ORDER BY id",
            (group_value,),
        ).fetchall()

    count_number = _next_count_number(conn)
    header = conn.execute(
        "INSERT INTO cycle_count (count_number, group_by, group_value, created_by) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (count_number, group_by, group_value, created_by),
    ).fetchone()
    count_id = header['id']

    for r in rows:
        conn.execute(
            "INSERT INTO cycle_count_line (cycle_count_id, product_id, system_qty) "
            "VALUES (%s, %s, %s)",
            (count_id, r['id'], r['amount']),
        )
    return count_id


def get_cycle_count(conn, count_id):
    row = conn.execute(
        "SELECT * FROM cycle_count WHERE id = %s", (count_id,)
    ).fetchone()
    return dict(row) if row else None


def get_cycle_count_lines(conn, count_id):
    rows = conn.execute("""
        SELECT ccl.id, ccl.product_id, ccl.system_qty, ccl.counted_qty,
               ccl.variance_qty, ccl.posted,
               p.name AS product_name, p.bin, p.uom
        FROM cycle_count_line ccl
        JOIN product p ON p.id = ccl.product_id
        WHERE ccl.cycle_count_id = %s
        ORDER BY p.name
    """, (count_id,)).fetchall()
    return [dict(r) for r in rows]


def list_cycle_counts(conn, status=None):
    conds, params = [], []
    if status:
        conds.append("status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(
        f"SELECT * FROM cycle_count {where} ORDER BY created_at DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def enter_counts(conn, count_id, counted_qtys, counted_by):
    """Record counted quantities for a sheet's lines and either auto-post
    (no variance found) or submit the variance for approval.

    ``counted_qtys`` is {line_id: counted_qty}. Returns the resulting
    cycle_count status ('posted' or 'submitted').
    """
    lines = get_cycle_count_lines(conn, count_id)
    total_variance_value = 0.0
    any_variance = False
    for line in lines:
        if line['id'] not in counted_qtys:
            continue
        counted = float(counted_qtys[line['id']])
        variance = counted - line['system_qty']
        conn.execute(
            "UPDATE cycle_count_line SET counted_qty = %s, variance_qty = %s "
            "WHERE id = %s",
            (counted, variance, line['id']),
        )
        if variance != 0:
            any_variance = True
            price_row = conn.execute(
                "SELECT COALESCE(purchase_price, 0) AS price FROM product WHERE id = %s",
                (line['product_id'],),
            ).fetchone()
            price = float(price_row['price']) if price_row else 0.0
            total_variance_value += abs(variance) * price

    conn.execute(
        "UPDATE cycle_count SET status = 'submitted', submitted_at = NOW() "
        "WHERE id = %s",
        (count_id,),
    )

    if not any_variance:
        post_cycle_count(conn, count_id, counted_by)
        return 'posted'

    step_ids = submit_for_approval(
        conn, 'cycle_count', count_id, total_variance_value,
        requested_by=counted_by,
    )
    if not step_ids:
        # No approval_rule configured for cycle_count — fail open, post now.
        post_cycle_count(conn, count_id, counted_by)
        return 'posted'
    return 'submitted'


def decide_cycle_count(conn, count_id, step_id, decision, decided_by, notes=''):
    """Record an approve/reject decision; posts the adjustment once every
    approval step for this sheet is approved. Returns the resulting
    cycle_count status.
    """
    overall = decide_step(conn, step_id, decision, decided_by, notes)
    if overall == 'approved':
        post_cycle_count(conn, count_id, decided_by)
        return 'posted'
    if overall == 'rejected':
        conn.execute(
            "UPDATE cycle_count SET status = 'rejected' WHERE id = %s",
            (count_id,),
        )
        return 'rejected'
    return 'submitted'


def post_cycle_count(conn, count_id, posted_by):
    """Post an inventory 'adjust' transaction for every un-posted line with
    a non-zero variance, then mark the sheet posted. Idempotent per line.
    """
    cc = get_cycle_count(conn, count_id)
    if not cc:
        raise ValueError(f"Cycle count {count_id} not found")
    lines = get_cycle_count_lines(conn, count_id)
    for line in lines:
        if line['posted'] or not line['variance_qty']:
            continue
        record_transaction(
            conn, line['product_id'], 'adjust', line['variance_qty'],
            reference=cc['count_number'],
            notes=f"Cycle count {cc['count_number']} variance adjustment",
            created_by=posted_by,
        )
        conn.execute(
            "UPDATE cycle_count_line SET posted = TRUE WHERE id = %s",
            (line['id'],),
        )
    conn.execute(
        "UPDATE cycle_count SET status = 'posted', posted_at = NOW() WHERE id = %s",
        (count_id,),
    )
