"""sampling_plan_core.py — Qt-free Sampling Plans & AQL (P2-E from
COMPETITIVE_GAP_ANALYSIS.md), per ISO 2859-1 (single sampling plans,
normal inspection).

Lot-size-range -> sample-size code letter, and code letter -> sample size,
are fixed values straight from the standard, so they're plain Python
constants (LOT_SIZE_RANGES / SAMPLE_SIZE_BY_CODE below) rather than DB
tables — no organization ever needs to edit "lot size 91-150 is code
letter D", any more than they'd edit PO_STATUS_COLORS.

aql_accept_reject (code letter + AQL% -> accept/reject numbers) IS a DB
table: it's the one part of the standard worth extending past what ships
here (more AQL levels, more code letters) without a code change.
**The seeded starter set covers only AQL 0.65/1.0/1.5/2.5/4.0 for code
letters C-N and is built from the standard's known diagonal structure —
verify against your organization's official ISO 2859-1 / ANSI-ASQ Z1.4
tables before relying on this for regulated/compliance decisions. It is
not a certified reproduction of Table II-A.**

sampling_plan is the master record tying an AQL level + inspection level
to an (optional) product or supplier, so incoming inspection can look up
"which plan applies" and auto-calculate sample size / accept / reject —
see resolve_sampling_plan(), called from quality_core.create_inspection.

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / accounting_core).
"""

from __future__ import annotations

# ISO 2859-1 Table 1 — sample size code letters by lot size, general
# inspection levels I/II/III: (lot_size_min, lot_size_max_or_None,
# code_level_i, code_level_ii, code_level_iii).
LOT_SIZE_RANGES = [
    (2, 8, 'A', 'A', 'B'),
    (9, 15, 'A', 'B', 'C'),
    (16, 25, 'B', 'C', 'D'),
    (26, 50, 'C', 'D', 'E'),
    (51, 90, 'C', 'E', 'F'),
    (91, 150, 'D', 'F', 'G'),
    (151, 280, 'E', 'G', 'H'),
    (281, 500, 'F', 'H', 'J'),
    (501, 1200, 'G', 'J', 'K'),
    (1201, 3200, 'H', 'K', 'L'),
    (3201, 10000, 'J', 'L', 'M'),
    (10001, 35000, 'K', 'M', 'N'),
    (35001, 150000, 'L', 'N', 'P'),
    (150001, 500000, 'M', 'P', 'Q'),
    (500001, None, 'N', 'Q', 'R'),
]

INSPECTION_LEVELS = ('I', 'II', 'III')

# ISO 2859-1 Table 1 — sample size by code letter.
SAMPLE_SIZE_BY_CODE = {
    'A': 2, 'B': 3, 'C': 5, 'D': 8, 'E': 13, 'F': 20, 'G': 32, 'H': 50,
    'J': 80, 'K': 125, 'L': 200, 'M': 315, 'N': 500, 'P': 800, 'Q': 1250,
    'R': 2000,
}

# AQL values (%) this module ships accept/reject starter data for. A
# sampling_plan may still be created with any positive AQL value; resolving
# one without accept/reject data just leaves accept_number/reject_number
# unset (see resolve_sampling_plan).
COMMON_AQL_VALUES = (0.65, 1.0, 1.5, 2.5, 4.0)

# Starter accept/reject numbers — see the module docstring's disclaimer.
_ACCEPT_REJECT_STARTER = [
    # code_letter, aql_value, accept_number, reject_number
    ('C', 2.5, 0, 1), ('C', 4.0, 0, 1),
    ('D', 1.5, 0, 1), ('D', 2.5, 0, 1), ('D', 4.0, 1, 2),
    ('E', 1.0, 0, 1), ('E', 1.5, 0, 1), ('E', 2.5, 1, 2), ('E', 4.0, 1, 2),
    ('F', 1.0, 0, 1), ('F', 1.5, 1, 2), ('F', 2.5, 1, 2), ('F', 4.0, 2, 3),
    ('G', 0.65, 0, 1), ('G', 1.0, 1, 2), ('G', 1.5, 1, 2), ('G', 2.5, 2, 3), ('G', 4.0, 3, 4),
    ('H', 0.65, 1, 2), ('H', 1.0, 1, 2), ('H', 1.5, 2, 3), ('H', 2.5, 3, 4), ('H', 4.0, 5, 6),
    ('J', 0.65, 1, 2), ('J', 1.0, 2, 3), ('J', 1.5, 3, 4), ('J', 2.5, 5, 6), ('J', 4.0, 7, 8),
    ('K', 0.65, 2, 3), ('K', 1.0, 3, 4), ('K', 1.5, 5, 6), ('K', 2.5, 7, 8), ('K', 4.0, 10, 11),
    ('L', 0.65, 3, 4), ('L', 1.0, 5, 6), ('L', 1.5, 7, 8), ('L', 2.5, 10, 11), ('L', 4.0, 14, 15),
    ('M', 0.65, 5, 6), ('M', 1.0, 7, 8), ('M', 1.5, 10, 11), ('M', 2.5, 14, 15), ('M', 4.0, 21, 22),
    ('N', 0.65, 7, 8), ('N', 1.0, 10, 11), ('N', 1.5, 14, 15), ('N', 2.5, 21, 22),
]


def code_letter_for_lot_size(lot_qty, inspection_level='II'):
    """The ISO 2859-1 sample size code letter for a lot of lot_qty units at
    the given general inspection level (I/II/III). Returns None if lot_qty
    is below the smallest tabulated lot size (2) — inspect 100% for lots
    that small; there's no code letter for it."""
    if inspection_level not in INSPECTION_LEVELS:
        raise ValueError(f'Unknown inspection level: {inspection_level!r}')
    col = INSPECTION_LEVELS.index(inspection_level)
    for lo, hi, *codes in LOT_SIZE_RANGES:
        if lot_qty >= lo and (hi is None or lot_qty <= hi):
            return codes[col]
    return None


def ensure_sampling_plan_tables(conn):
    """Create sampling_plan / aql_accept_reject if absent, seed the
    accept/reject starter data if empty, and extend qa_inspection with the
    columns a resolved plan stamps onto an inspection record. Idempotent —
    does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sampling_plan (
            id                SERIAL PRIMARY KEY,
            plan_name         TEXT NOT NULL UNIQUE,
            aql_value         REAL NOT NULL,
            inspection_level  TEXT NOT NULL DEFAULT 'II',
            product_id        INTEGER REFERENCES product(id),
            supplier_id       INTEGER REFERENCES supplier(id),
            is_active         BOOLEAN NOT NULL DEFAULT TRUE,
            notes             TEXT NOT NULL DEFAULT '',
            created_by        TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aql_accept_reject (
            id             SERIAL PRIMARY KEY,
            code_letter    TEXT NOT NULL,
            aql_value      REAL NOT NULL,
            accept_number  INTEGER NOT NULL,
            reject_number  INTEGER NOT NULL,
            UNIQUE (code_letter, aql_value)
        )
    """)
    for col_sql in [
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS "
        "sampling_plan_id INTEGER REFERENCES sampling_plan(id)",
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS lot_qty REAL",
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS code_letter TEXT",
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS sample_size INTEGER",
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS accept_number INTEGER",
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS reject_number INTEGER",
        "ALTER TABLE qa_inspection ADD COLUMN IF NOT EXISTS qty_defective INTEGER",
    ]:
        conn.execute(col_sql)
    _seed_accept_reject_starter_data(conn)


def _seed_accept_reject_starter_data(conn):
    row = conn.execute("SELECT COUNT(*) AS n FROM aql_accept_reject").fetchone()
    if row and row['n']:
        return
    for code_letter, aql_value, accept_number, reject_number in _ACCEPT_REJECT_STARTER:
        conn.execute(
            "INSERT INTO aql_accept_reject "
            "(code_letter, aql_value, accept_number, reject_number) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (code_letter, aql_value) DO NOTHING",
            (code_letter, aql_value, accept_number, reject_number),
        )


# ---------------------------------------------------------------------------
# Sampling plan CRUD
# ---------------------------------------------------------------------------

def list_sampling_plans(conn, is_active=None, search=None):
    sql = (
        "SELECT sp.*, p.name AS product_name, "
        "s.company_name AS supplier_name "
        "FROM sampling_plan sp "
        "LEFT JOIN product p ON p.id = sp.product_id "
        "LEFT JOIN supplier s ON s.id = sp.supplier_id "
        "WHERE TRUE"
    )
    params: list = []
    if is_active is not None:
        sql += " AND sp.is_active = %s"
        params.append(is_active)
    if search:
        sql += " AND sp.plan_name ILIKE %s"
        params.append(f"%{search}%")
    sql += " ORDER BY sp.plan_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_sampling_plan(conn, plan_id):
    row = conn.execute("""
        SELECT sp.*, p.name AS product_name,
               s.company_name AS supplier_name
        FROM sampling_plan sp
        LEFT JOIN product p ON p.id = sp.product_id
        LEFT JOIN supplier s ON s.id = sp.supplier_id
        WHERE sp.id = %s
    """, (plan_id,)).fetchone()
    return dict(row) if row else None


def create_sampling_plan(conn, plan_name, aql_value, inspection_level='II',
                         product_id=None, supplier_id=None, notes='',
                         created_by=''):
    if inspection_level not in INSPECTION_LEVELS:
        raise ValueError(f'Unknown inspection level: {inspection_level!r}')
    row = conn.execute(
        "INSERT INTO sampling_plan "
        "(plan_name, aql_value, inspection_level, product_id, supplier_id, "
        " notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (plan_name.strip(), aql_value, inspection_level,
         product_id or None, supplier_id or None, notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def update_sampling_plan(conn, plan_id, **fields):
    allowed = {'plan_name', 'aql_value', 'inspection_level', 'product_id',
               'supplier_id', 'is_active', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE sampling_plan SET {set_clause} WHERE id = %s",
        list(cols.values()) + [plan_id],
    )


def find_applicable_plans(conn, product_id=None, supplier_id=None):
    """Active sampling plans attached to product_id and/or supplier_id (a
    plan attached to neither is a general-purpose plan usable for any
    inspection, so it's included too). Used to populate the "which plan
    applies" picker on the inspection-creation form — the inspector picks
    among whatever matches rather than the system silently guessing one."""
    conds = ["sp.is_active = TRUE"]
    params: list = []
    scope = ["sp.product_id IS NULL AND sp.supplier_id IS NULL"]
    if product_id:
        scope.append("sp.product_id = %s")
        params.append(product_id)
    if supplier_id:
        scope.append("sp.supplier_id = %s")
        params.append(supplier_id)
    conds.append("(" + " OR ".join(scope) + ")")
    rows = conn.execute(f"""
        SELECT sp.*, p.name AS product_name, s.company_name AS supplier_name
        FROM sampling_plan sp
        LEFT JOIN product p ON p.id = sp.product_id
        LEFT JOIN supplier s ON s.id = sp.supplier_id
        WHERE {" AND ".join(conds)}
        ORDER BY sp.plan_name
    """, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Resolution & evaluation
# ---------------------------------------------------------------------------

def resolve_sampling_plan(conn, sampling_plan_id, lot_qty):
    """Resolve a sampling_plan + lot quantity into concrete inspection
    parameters: {code_letter, sample_size, accept_number, reject_number}.
    accept_number/reject_number are None if aql_accept_reject has no row
    for this code_letter/aql_value combination (see the module docstring's
    disclaimer) — the inspection is still created with a sample_size, just
    without an automatic pass/fail threshold.

    Raises ValueError if the plan doesn't exist or lot_qty is below the
    smallest tabulated lot size (no code letter applies).
    """
    plan = get_sampling_plan(conn, sampling_plan_id)
    if not plan:
        raise ValueError(f'No sampling plan with id {sampling_plan_id}')
    code_letter = code_letter_for_lot_size(lot_qty, plan['inspection_level'])
    if not code_letter:
        raise ValueError(
            f'Lot quantity {lot_qty} is too small for AQL sampling '
            '(ISO 2859-1 starts at lot size 2)')
    sample_size = SAMPLE_SIZE_BY_CODE[code_letter]
    row = conn.execute(
        "SELECT accept_number, reject_number FROM aql_accept_reject "
        "WHERE code_letter = %s AND aql_value = %s",
        (code_letter, plan['aql_value']),
    ).fetchone()
    return {
        'code_letter': code_letter,
        'sample_size': sample_size,
        'accept_number': row['accept_number'] if row else None,
        'reject_number': row['reject_number'] if row else None,
    }


def evaluate_sampling_result(accept_number, reject_number, qty_defective):
    """'passed' if qty_defective <= accept_number, 'failed' if it reaches
    reject_number, None if accept/reject numbers aren't known (see
    resolve_sampling_plan) or qty_defective hasn't been recorded yet.

    ISO 2859-1's Ac/Re are always consecutive integers (Re = Ac + 1) for
    single sampling plans, so there is no gap between the two outcomes.
    """
    if accept_number is None or reject_number is None or qty_defective is None:
        return None
    return 'passed' if qty_defective <= accept_number else 'failed'
