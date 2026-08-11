"""
costing_core.py — Qt-free standard cost and WO variance accounting.

Two concepts live here:

Standard cost (cost_roll)
    A snapshot of what a product *should* cost, computed by recursively
    exploding its BOM and summing component costs + routing labour +
    workcenter overhead.  Stored with an effective date so history is
    preserved when costs change.

WO actual cost (wo_cost_actual)
    Computed when a Work Order is closed: actual material spend (qty_issued ×
    purchase_price) + actual labour (actual_hours × labor_rate) + actual
    overhead (actual_hours × overhead_rate).  The gap between actual and
    standard is split into material_variance and labor_variance and posted to
    the configured GL accounts.

GL account map (gl_account_map)
    A lookup table that maps named cost categories to GL account numbers.
    Set these up once in the chart of accounts admin screen.  If a category
    has no mapping the GL post is skipped with a warning rather than failing.

    Standard categories:
        raw_material     — Raw Material Inventory (Asset)
        wip              — Work In Process (Asset)
        finished_goods   — Finished Goods Inventory (Asset)
        cogs             — Cost of Goods Sold
        material_variance — Material Variance (COGS or Expense)
        labor_variance   — Labour Variance (COGS or Expense)
        ap_payable       — Accounts Payable (Liability) — for PO receipts
"""

from datetime import date

from .log_utils import get_logger

log = get_logger(__name__)

# Cycle guard: prevent infinite recursion on malformed BOMs
_MAX_DEPTH = 15

GL_CATEGORIES = (
    'raw_material',
    'wip',
    'finished_goods',
    'cogs',
    'material_variance',
    'labor_variance',
    'ap_payable',
)


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def ensure_costing_tables(conn):
    """Create cost_roll / wo_cost_actual / gl_account_map. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_account_map (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL UNIQUE,
            account_number TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cost_roll (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            effective_date TEXT NOT NULL,
            std_material_cost REAL NOT NULL DEFAULT 0.0,
            std_labor_cost REAL NOT NULL DEFAULT 0.0,
            std_overhead_cost REAL NOT NULL DEFAULT 0.0,
            total_std_cost REAL NOT NULL DEFAULT 0.0,
            roll_notes TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS cost_roll_product "
        "ON cost_roll(product_id, effective_date DESC)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_cost_actual (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL UNIQUE REFERENCES work_order(id),
            actual_material_cost REAL NOT NULL DEFAULT 0.0,
            actual_labor_cost REAL NOT NULL DEFAULT 0.0,
            actual_overhead_cost REAL NOT NULL DEFAULT 0.0,
            total_actual_cost REAL NOT NULL DEFAULT 0.0,
            std_cost REAL NOT NULL DEFAULT 0.0,
            material_variance REAL NOT NULL DEFAULT 0.0,
            labor_variance REAL NOT NULL DEFAULT 0.0,
            total_variance REAL NOT NULL DEFAULT 0.0,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Add overhead_rate to workcenter if not present (Phase 1 tables may exist)
    conn.execute(
        "ALTER TABLE workcenter ADD COLUMN IF NOT EXISTS "
        "overhead_rate REAL NOT NULL DEFAULT 0.0"
    )


# ---------------------------------------------------------------------------
# GL account map
# ---------------------------------------------------------------------------

def get_gl_account_map(conn):
    """Return {category: account_number} for all active mappings."""
    rows = conn.execute(
        "SELECT category, account_number FROM gl_account_map WHERE is_active=TRUE"
    ).fetchall()
    return {r['category']: r['account_number'] for r in rows}


def set_gl_account_map(conn, category, account_number, description=None):
    """Upsert a GL account mapping. Does not commit."""
    if category not in GL_CATEGORIES:
        raise ValueError(f"Unknown GL category: {category!r}")
    conn.execute(
        "INSERT INTO gl_account_map (category, account_number, description) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (category) DO UPDATE "
        "SET account_number=EXCLUDED.account_number, "
        "    description=EXCLUDED.description, "
        "    is_active=TRUE",
        (category, account_number, description),
    )


def list_gl_account_map(conn):
    """Return all account map rows as dicts."""
    rows = conn.execute(
        "SELECT id, category, account_number, description, is_active "
        "FROM gl_account_map ORDER BY category"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Standard cost roll-up
# ---------------------------------------------------------------------------

def _get_bom_lines(conn, product_id):
    """Return direct BOM components for a product."""
    rows = conn.execute(
        "SELECT b.component_id, b.qty_required, COALESCE(b.scrap_pct, 0) AS scrap_pct, "
        "p.name, COALESCE(p.item_type, 'buy') AS item_type, "
        "COALESCE(p.purchase_price, 0) AS purchase_price "
        "FROM bom b "
        "JOIN product p ON p.id = b.component_id "
        "WHERE b.product_id = %s",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_routing_cost(conn, product_id):
    """Sum std_hours × labor_rate and std_hours × overhead_rate across routing."""
    row = conn.execute(
        "SELECT "
        "COALESCE(SUM(r.std_hours * COALESCE(wc.labor_rate, 0)), 0)    AS labor_cost, "
        "COALESCE(SUM(r.std_hours * COALESCE(wc.overhead_rate, 0)), 0) AS overhead_cost "
        "FROM routing r "
        "LEFT JOIN workcenter wc ON wc.id = r.workcenter_id "
        "WHERE r.product_id = %s",
        (product_id,),
    ).fetchone()
    if row:
        return float(row['labor_cost']), float(row['overhead_cost'])
    return 0.0, 0.0


def roll_standard_cost(conn, product_id, created_by=None, _depth=0, _visited=None):
    """Compute and save the standard cost for one product.

    Recursively explodes the BOM:
    - 'buy' items: std_material = purchase_price, no labour/overhead.
    - 'make' items: std_material = sum of component rolled costs × qty (+ scrap),
                    std_labor / std_overhead from routing × workcenter rates.

    Stores a cost_roll row and returns the cost dict.
    Does not commit — caller controls the transaction.
    """
    if _visited is None:
        _visited = set()
    if _depth > _MAX_DEPTH:
        log.warning("costing: max BOM depth reached for product_id=%s", product_id)
        return {'std_material_cost': 0.0, 'std_labor_cost': 0.0,
                'std_overhead_cost': 0.0, 'total_std_cost': 0.0}
    if product_id in _visited:
        log.warning("costing: cycle detected at product_id=%s", product_id)
        return {'std_material_cost': 0.0, 'std_labor_cost': 0.0,
                'std_overhead_cost': 0.0, 'total_std_cost': 0.0}
    _visited.add(product_id)

    prod_row = conn.execute(
        "SELECT COALESCE(item_type, 'buy') AS item_type, "
        "COALESCE(purchase_price, 0) AS purchase_price "
        "FROM product WHERE id=%s",
        (product_id,),
    ).fetchone()
    if not prod_row:
        return {'std_material_cost': 0.0, 'std_labor_cost': 0.0,
                'std_overhead_cost': 0.0, 'total_std_cost': 0.0}

    item_type = prod_row['item_type']

    if item_type == 'buy':
        mat = float(prod_row['purchase_price'])
        labor, overhead = 0.0, 0.0
    else:
        # Make item: roll up component costs
        bom_lines = _get_bom_lines(conn, product_id)
        mat = 0.0
        for line in bom_lines:
            child_cost = roll_standard_cost(
                conn, line['component_id'], created_by,
                _depth=_depth + 1, _visited=_visited,
            )
            inflated_qty = line['qty_required'] * (1 + line['scrap_pct'] / 100.0)
            mat += child_cost['total_std_cost'] * inflated_qty
        labor, overhead = _get_routing_cost(conn, product_id)

    total = mat + labor + overhead

    today = date.today().isoformat()
    conn.execute(
        "INSERT INTO cost_roll "
        "(product_id, effective_date, std_material_cost, std_labor_cost, "
        "std_overhead_cost, total_std_cost, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (product_id, today, mat, labor, overhead, total, created_by),
    )
    log.info("Cost rolled for product_id=%s: material=%.4f labor=%.4f "
             "overhead=%.4f total=%.4f", product_id, mat, labor, overhead, total)
    return {
        'std_material_cost': mat,
        'std_labor_cost': labor,
        'std_overhead_cost': overhead,
        'total_std_cost': total,
    }


def get_standard_cost(conn, product_id):
    """Return the most recent cost_roll for a product, or None."""
    row = conn.execute(
        "SELECT id, product_id, effective_date, std_material_cost, "
        "std_labor_cost, std_overhead_cost, total_std_cost, created_by, created_at "
        "FROM cost_roll WHERE product_id=%s "
        "ORDER BY effective_date DESC, id DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    return dict(row) if row else None


def list_cost_history(conn, product_id):
    """Return all cost_roll rows for a product, newest first."""
    rows = conn.execute(
        "SELECT id, effective_date, std_material_cost, std_labor_cost, "
        "std_overhead_cost, total_std_cost, created_by, created_at "
        "FROM cost_roll WHERE product_id=%s "
        "ORDER BY effective_date DESC, id DESC",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# WO actual cost and variance
# ---------------------------------------------------------------------------

def compute_wo_actual_cost(conn, wo_id):
    """Compute actual cost for a WO from issued materials and logged labour.

    Returns a dict (does not write to DB).
    """
    mat_row = conn.execute(
        "SELECT COALESCE(SUM(m.qty_issued * COALESCE(p.purchase_price, 0)), 0) "
        "AS actual_material_cost "
        "FROM wo_material m "
        "JOIN product p ON p.id = m.product_id "
        "WHERE m.wo_id = %s",
        (wo_id,),
    ).fetchone()
    actual_material = float(mat_row['actual_material_cost']) if mat_row else 0.0

    labor_row = conn.execute(
        "SELECT "
        "COALESCE(SUM(op.actual_hours * COALESCE(wc.labor_rate, 0)), 0)    AS actual_labor_cost, "
        "COALESCE(SUM(op.actual_hours * COALESCE(wc.overhead_rate, 0)), 0) AS actual_overhead_cost "
        "FROM wo_operation op "
        "LEFT JOIN workcenter wc ON wc.id = op.workcenter_id "
        "WHERE op.wo_id = %s AND op.status = 'completed'",
        (wo_id,),
    ).fetchone()
    actual_labor = float(labor_row['actual_labor_cost']) if labor_row else 0.0
    actual_overhead = float(labor_row['actual_overhead_cost']) if labor_row else 0.0

    return {
        'actual_material_cost': actual_material,
        'actual_labor_cost': actual_labor,
        'actual_overhead_cost': actual_overhead,
        'total_actual_cost': actual_material + actual_labor + actual_overhead,
    }


def save_wo_actual_cost(conn, wo_id, created_by=None):
    """Compute, compare against standard, and persist WO cost data.

    Fetches the WO's product and quantity, looks up the latest standard cost,
    computes actual spend from wo_material and wo_operation, then writes a
    wo_cost_actual row (upsert).  Does not commit.

    Returns the saved cost dict including variance fields.
    """
    wo_row = conn.execute(
        "SELECT product_id, COALESCE(quantity, 1) AS quantity "
        "FROM work_order WHERE id=%s",
        (wo_id,),
    ).fetchone()
    if not wo_row:
        raise ValueError(f"Work order {wo_id} not found")

    quantity = float(wo_row['quantity'])
    actuals = compute_wo_actual_cost(conn, wo_id)

    std_row = get_standard_cost(conn, wo_row['product_id']) if wo_row['product_id'] else None
    std_cost = float(std_row['total_std_cost']) * quantity if std_row else 0.0
    std_material = float(std_row['std_material_cost']) * quantity if std_row else 0.0
    std_labor = (float(std_row['std_labor_cost']) +
                 float(std_row['std_overhead_cost'])) * quantity if std_row else 0.0

    mat_var = actuals['actual_material_cost'] - std_material
    lab_var = (actuals['actual_labor_cost'] + actuals['actual_overhead_cost']) - std_labor
    total_var = actuals['total_actual_cost'] - std_cost

    conn.execute(
        "INSERT INTO wo_cost_actual "
        "(wo_id, actual_material_cost, actual_labor_cost, actual_overhead_cost, "
        "total_actual_cost, std_cost, material_variance, labor_variance, "
        "total_variance, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (wo_id) DO UPDATE SET "
        "actual_material_cost=EXCLUDED.actual_material_cost, "
        "actual_labor_cost=EXCLUDED.actual_labor_cost, "
        "actual_overhead_cost=EXCLUDED.actual_overhead_cost, "
        "total_actual_cost=EXCLUDED.total_actual_cost, "
        "std_cost=EXCLUDED.std_cost, "
        "material_variance=EXCLUDED.material_variance, "
        "labor_variance=EXCLUDED.labor_variance, "
        "total_variance=EXCLUDED.total_variance, "
        "created_by=EXCLUDED.created_by",
        (wo_id,
         actuals['actual_material_cost'],
         actuals['actual_labor_cost'],
         actuals['actual_overhead_cost'],
         actuals['total_actual_cost'],
         std_cost, mat_var, lab_var, total_var, created_by),
    )
    result = {**actuals, 'std_cost': std_cost,
              'material_variance': mat_var, 'labor_variance': lab_var,
              'total_variance': total_var}
    log.info("WO %s cost saved: actual=%.4f std=%.4f variance=%.4f",
             wo_id, actuals['total_actual_cost'], std_cost, total_var)
    return result


def get_wo_cost(conn, wo_id):
    """Return the saved wo_cost_actual row for a WO, or None."""
    row = conn.execute(
        "SELECT * FROM wo_cost_actual WHERE wo_id=%s", (wo_id,)
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# GL posting helpers (work within an existing connection/transaction)
# ---------------------------------------------------------------------------

def _gl_acct(account_map, category):
    """Return account number for a category, or None (with a warning)."""
    acct = account_map.get(category)
    if not acct:
        log.warning("costing: no GL account mapped for category %r — skipping post",
                    category)
    return acct


def _post_lines_on_conn(conn, journal_date, reference, description,
                        lines, created_by):
    """Insert a GL journal + lines on an existing open connection.

    Unlike gl_utils.post_gl_entry, this does NOT open a new connection
    so it participates in the caller's transaction.  Returns journal id
    or None if an account number isn't found.
    """
    resolved = []
    for acct_num, debit, credit, memo in lines:
        row = conn.execute(
            "SELECT id FROM gl_account WHERE account_number=%s", (acct_num,)
        ).fetchone()
        if not row:
            log.warning("costing GL post aborted: account %s not in chart of accounts",
                        acct_num)
            return None
        resolved.append((row['id'], float(debit), float(credit), str(memo)))

    jid_row = conn.execute(
        "INSERT INTO gl_journal(journal_date, reference, description, "
        "posted, created_by) VALUES(%s,%s,%s,0,%s) RETURNING id",
        (journal_date, reference, description, created_by),
    ).fetchone()
    jid = jid_row['id']
    for aid, dr, cr, memo in resolved:
        conn.execute(
            "INSERT INTO gl_journal_line(journal_id, account_id, debit, credit, memo) "
            "VALUES(%s,%s,%s,%s,%s)",
            (jid, aid, dr, cr, memo),
        )
    return jid


def post_po_receipt_gl(conn, po_number, amount, created_by=None):
    """DR Raw Material Inventory / CR Accounts Payable on PO receipt.

    Call this after marking a PO as received.  Does not commit.
    """
    account_map = get_gl_account_map(conn)
    inv_acct = _gl_acct(account_map, 'raw_material')
    ap_acct = _gl_acct(account_map, 'ap_payable')
    if not inv_acct or not ap_acct:
        return None
    return _post_lines_on_conn(
        conn,
        journal_date=date.today().isoformat(),
        reference=po_number,
        description=f"PO receipt — {po_number}",
        lines=[
            (inv_acct, amount, 0.0, f"Inventory receipt {po_number}"),
            (ap_acct, 0.0, amount, f"AP liability {po_number}"),
        ],
        created_by=created_by or 'System',
    )


def post_wo_material_issue_gl(conn, wo_number, amount, created_by=None):
    """DR WIP / CR Raw Material Inventory on WO material issue.

    Call this when materials are issued to a WO.  Does not commit.
    """
    account_map = get_gl_account_map(conn)
    wip_acct = _gl_acct(account_map, 'wip')
    inv_acct = _gl_acct(account_map, 'raw_material')
    if not wip_acct or not inv_acct:
        return None
    return _post_lines_on_conn(
        conn,
        journal_date=date.today().isoformat(),
        reference=wo_number,
        description=f"Material issue to WO {wo_number}",
        lines=[
            (wip_acct, amount, 0.0, f"WIP — material issue {wo_number}"),
            (inv_acct, 0.0, amount, f"Inventory consumed {wo_number}"),
        ],
        created_by=created_by or 'System',
    )


def post_wo_close_gl(conn, wo_id, wo_number, quantity, created_by=None):
    """Post GL entries when a WO is closed.

    Reads wo_cost_actual (must exist — call save_wo_actual_cost first).

    Entries:
        DR Finished Goods   (standard cost × qty)
        CR WIP              (total actual cost — material + labour + overhead —
                             already charged to WIP)
        DR/CR Material Variance
        DR/CR Labour Variance

    Does not commit.  Returns journal id or None.
    """
    cost = get_wo_cost(conn, wo_id)
    if not cost:
        log.warning("post_wo_close_gl: no cost data for WO %s — skipping", wo_id)
        return None

    account_map = get_gl_account_map(conn)
    fg_acct = _gl_acct(account_map, 'finished_goods')
    wip_acct = _gl_acct(account_map, 'wip')
    mat_var_acct = _gl_acct(account_map, 'material_variance')
    lab_var_acct = _gl_acct(account_map, 'labor_variance')
    if not fg_acct or not wip_acct:
        return None

    std_cost = cost['std_cost']
    mat_var = cost['material_variance']   # positive = unfavorable (actual > std)
    lab_var = cost['labor_variance']

    lines = [
        (fg_acct, std_cost, 0.0, f"FG completion {wo_number}"),
        (wip_acct, 0.0, cost['total_actual_cost'],
         f"WIP clearance {wo_number}"),
    ]
    # Material variance: unfavorable (actual > std) → DR variance account
    if mat_var_acct and abs(mat_var) >= 0.01:
        if mat_var > 0:
            lines.append((mat_var_acct, mat_var, 0.0,
                          f"Material variance (unfav) {wo_number}"))
        else:
            lines.append((mat_var_acct, 0.0, abs(mat_var),
                          f"Material variance (fav) {wo_number}"))

    # Labour + overhead variance
    if lab_var_acct and abs(lab_var) >= 0.01:
        if lab_var > 0:
            lines.append((lab_var_acct, lab_var, 0.0,
                          f"Labour variance (unfav) {wo_number}"))
        else:
            lines.append((lab_var_acct, 0.0, abs(lab_var),
                          f"Labour variance (fav) {wo_number}"))

    return _post_lines_on_conn(
        conn,
        journal_date=date.today().isoformat(),
        reference=wo_number,
        description=f"WO close — {wo_number} qty={quantity}",
        lines=lines,
        created_by=created_by or 'System',
    )
