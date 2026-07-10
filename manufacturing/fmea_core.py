"""fmea_core.py — Qt-free Control Plans & FMEA (Failure Mode and Effects
Analysis), 7/10 of the top-10 ERPs have this.

A control plan is a per-product register of characteristics to control
during production, each with a control method and an FMEA risk score:

    RPN (Risk Priority Number) = Severity x Occurrence x Detection

Severity/Occurrence/Detection are each rated 1-10, the standard AIAG-style
FMEA scale — **the specific rating anchors (what makes something a 7 vs
an 8) vary by organization/industry standard and are not encoded here**;
this module only enforces the 1-10 range and the multiplication, the same
"structure is real, the org's own numbers still need expert judgment"
scoping already used for sampling_plan_core's AQL disclaimer.

Tables:
  control_plan       — header: which product, plan name/revision, status
  control_plan_item  — one row per controlled characteristic: spec,
                       control method, S/O/D ratings, computed RPN,
                       recommended action

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / sampling_plan_core).
"""

from __future__ import annotations

CONTROL_PLAN_STATUSES = ('draft', 'active', 'superseded')

# Common RPN risk buckets (not a certified standard — see module docstring).
_RPN_LOW_MAX = 49
_RPN_MEDIUM_MAX = 99
_RPN_HIGH_MAX = 199


def ensure_fmea_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS control_plan (
            id           SERIAL PRIMARY KEY,
            product_id   INTEGER NOT NULL REFERENCES product(id),
            name         TEXT NOT NULL,
            revision     TEXT NOT NULL DEFAULT 'A',
            status       TEXT NOT NULL DEFAULT 'draft',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS control_plan_item (
            id                  SERIAL PRIMARY KEY,
            control_plan_id     INTEGER NOT NULL REFERENCES control_plan(id),
            operation_seq       INTEGER,
            characteristic      TEXT NOT NULL,
            specification       TEXT NOT NULL DEFAULT '',
            control_method      TEXT NOT NULL DEFAULT '',
            severity            INTEGER NOT NULL DEFAULT 1,
            occurrence           INTEGER NOT NULL DEFAULT 1,
            detection           INTEGER NOT NULL DEFAULT 1,
            rpn                 INTEGER NOT NULL DEFAULT 1,
            recommended_action  TEXT NOT NULL DEFAULT '',
            notes               TEXT NOT NULL DEFAULT ''
        )
    """)


def _validate_rating(name, value):
    if not isinstance(value, int) or not (1 <= value <= 10):
        raise ValueError(f'{name} must be an integer from 1 to 10, got {value!r}')


def rpn_risk_level(rpn):
    """Bucket an RPN into low/medium/high/critical (see module docstring
    for the disclaimer that these thresholds are a common convention, not
    a certified standard)."""
    if rpn <= _RPN_LOW_MAX:
        return 'low'
    if rpn <= _RPN_MEDIUM_MAX:
        return 'medium'
    if rpn <= _RPN_HIGH_MAX:
        return 'high'
    return 'critical'


# ---------------------------------------------------------------------------
# Control plan CRUD
# ---------------------------------------------------------------------------

def list_control_plans(conn, product_id=None, status=None):
    conditions = ["TRUE"]
    params: list = []
    if product_id:
        conditions.append("cp.product_id = %s")
        params.append(product_id)
    if status:
        conditions.append("cp.status = %s")
        params.append(status)
    rows = conn.execute(f"""
        SELECT cp.*, p.name AS product_name
        FROM control_plan cp
        JOIN product p ON p.id = cp.product_id
        WHERE {" AND ".join(conditions)}
        ORDER BY cp.created_at DESC, cp.id DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_control_plan(conn, plan_id):
    row = conn.execute("""
        SELECT cp.*, p.name AS product_name
        FROM control_plan cp
        JOIN product p ON p.id = cp.product_id
        WHERE cp.id = %s
    """, (plan_id,)).fetchone()
    return dict(row) if row else None


def create_control_plan(conn, product_id, name, revision='A', created_by=''):
    if not name.strip():
        raise ValueError('Name is required.')
    row = conn.execute(
        "INSERT INTO control_plan (product_id, name, revision, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (product_id, name.strip(), revision or 'A', created_by or ''),
    ).fetchone()
    return row['id']


def update_control_plan_status(conn, plan_id, status):
    if status not in CONTROL_PLAN_STATUSES:
        raise ValueError(f'Unknown status: {status!r}')
    conn.execute(
        "UPDATE control_plan SET status = %s WHERE id = %s", (status, plan_id),
    )


# ---------------------------------------------------------------------------
# Control plan items (FMEA rows)
# ---------------------------------------------------------------------------

def list_control_plan_items(conn, plan_id):
    rows = conn.execute(
        "SELECT * FROM control_plan_item WHERE control_plan_id = %s "
        "ORDER BY operation_seq NULLS LAST, id",
        (plan_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_control_plan_item(conn, item_id):
    row = conn.execute(
        "SELECT * FROM control_plan_item WHERE id = %s", (item_id,),
    ).fetchone()
    return dict(row) if row else None


def add_control_plan_item(conn, plan_id, characteristic, severity, occurrence,
                          detection, specification='', control_method='',
                          recommended_action='', notes='', operation_seq=None):
    if not characteristic.strip():
        raise ValueError('Characteristic is required.')
    _validate_rating('severity', severity)
    _validate_rating('occurrence', occurrence)
    _validate_rating('detection', detection)
    rpn = severity * occurrence * detection
    row = conn.execute(
        "INSERT INTO control_plan_item "
        "(control_plan_id, operation_seq, characteristic, specification, "
        " control_method, severity, occurrence, detection, rpn, "
        " recommended_action, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (plan_id, operation_seq, characteristic.strip(), specification or '',
         control_method or '', severity, occurrence, detection, rpn,
         recommended_action or '', notes or ''),
    ).fetchone()
    return row['id']


def update_control_plan_item(conn, item_id, **fields):
    allowed = {'operation_seq', 'characteristic', 'specification',
               'control_method', 'severity', 'occurrence', 'detection',
               'recommended_action', 'notes'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return

    rating_fields = {'severity', 'occurrence', 'detection'} & cols.keys()
    if rating_fields:
        current = get_control_plan_item(conn, item_id)
        if not current:
            raise ValueError(f'No control plan item with id {item_id}')
        severity = cols.get('severity', current['severity'])
        occurrence = cols.get('occurrence', current['occurrence'])
        detection = cols.get('detection', current['detection'])
        _validate_rating('severity', severity)
        _validate_rating('occurrence', occurrence)
        _validate_rating('detection', detection)
        cols['rpn'] = severity * occurrence * detection

    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE control_plan_item SET {set_clause} WHERE id = %s",
        list(cols.values()) + [item_id],
    )


def delete_control_plan_item(conn, item_id):
    conn.execute("DELETE FROM control_plan_item WHERE id = %s", (item_id,))


# ---------------------------------------------------------------------------
# Risk register
# ---------------------------------------------------------------------------

def get_high_risk_items(conn, threshold=100):
    """Cross-plan risk register: every item at or above ``threshold`` RPN
    on an active control plan, highest risk first — the "what should we
    fix first" view."""
    rows = conn.execute("""
        SELECT cpi.*, cp.name AS plan_name, cp.revision, p.name AS product_name
        FROM control_plan_item cpi
        JOIN control_plan cp ON cp.id = cpi.control_plan_id
        JOIN product p ON p.id = cp.product_id
        WHERE cp.status = 'active' AND cpi.rpn >= %s
        ORDER BY cpi.rpn DESC
    """, (threshold,)).fetchall()
    return [dict(r) for r in rows]
