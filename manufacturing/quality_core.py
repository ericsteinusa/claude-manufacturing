"""
quality_core.py — Qt-free data layer for QA web views.

Tables: qa_ncr, qa_capa, qa_audit, qa_supplier (qa_inspection, qa_defect,
qa_spec handled at the bottom).  No PyQt6, no commit inside any function.

Phase 6A adds SPC (Statistical Process Control):
  spc_control_limit  — engineering spec limits (USL/LSL) per product+characteristic
  spc_measurement    — individual measured values with in-control flag
"""

import datetime
import statistics

from .sampling_plan_core import resolve_sampling_plan, evaluate_sampling_result

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NCR_STATUSES    = ('Open', 'Under Review', 'Dispositioned', 'Closed')
NCR_SOURCES     = ('Incoming', 'In-Process', 'Final', 'Customer', 'Supplier', 'Audit')
NCR_SEVERITIES  = ('Minor', 'Major', 'Critical')
NCR_DISPOSITIONS = ('Pending', 'Use As-Is', 'Rework', 'Repair', 'Scrap', 'Return')

CAPA_STATUSES   = ('Open', 'In Progress', 'Verification', 'Closed', 'Overdue')
CAPA_TYPES      = ('Corrective', 'Preventive')

AUDIT_STATUSES  = ('Scheduled', 'In Progress', 'Complete', 'Follow-up', 'Closed')
AUDIT_TYPES     = ('Internal', 'External', 'Supplier', 'Process', 'Product', 'ISO 9001')

SUPPLIER_STATUSES = ('Pending', 'Approved', 'Conditional', 'Probation', 'Disqualified')
SUPPLIER_RATINGS  = ('A', 'B', 'C', 'D')

INSP_RESULTS    = ('pending', 'passed', 'failed', 'on_hold')
DEFECT_SEVERITIES = ('minor', 'major', 'critical')


def _today() -> str:
    return datetime.date.today().isoformat()


def _overdue(date_str: str, terminal_statuses: tuple) -> bool:
    """True when date_str is in the past and status is not terminal."""
    return False  # evaluated per-row below


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard_counts(conn) -> dict:
    """Open/active counts for each entity type — used on the QA dashboard."""
    row = conn.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM qa_ncr  WHERE status != 'Closed')  AS open_ncrs, "
        "(SELECT COUNT(*) FROM qa_capa WHERE status NOT IN ('Closed','Overdue')) AS open_capas, "
        "(SELECT COUNT(*) FROM qa_audit WHERE status NOT IN ('Complete','Closed')) AS open_audits, "
        "(SELECT COUNT(*) FROM qa_inspection WHERE result = 'pending') AS pending_inspections, "
        "(SELECT COUNT(*) FROM qa_defect WHERE resolved = 0) AS open_defects, "
        "(SELECT COUNT(*) FROM qa_ncr WHERE severity = 'Critical' AND status != 'Closed') AS critical_ncrs, "
        "(SELECT COUNT(*) FROM qa_capa WHERE due_date != '' AND due_date < %s "
        "  AND status NOT IN ('Closed')) AS overdue_capas",
        (_today(),),
    ).fetchone()
    return dict(row) if row else {
        'open_ncrs': 0, 'open_capas': 0, 'open_audits': 0,
        'pending_inspections': 0, 'open_defects': 0,
        'critical_ncrs': 0, 'overdue_capas': 0,
    }


def get_defect_pareto(conn) -> list[dict]:
    """Return [{defect_type, cnt}] ranked descending, for a defect Pareto
    chart on the QA dashboard."""
    rows = conn.execute(
        "SELECT defect_type, COUNT(*) AS cnt FROM qa_defect "
        "GROUP BY defect_type ORDER BY cnt DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_ncr_severity_trend(conn, months: int = 6) -> dict:
    """Return {months: [...], series: {severity: [cnt, ...]}} — NCR count
    by severity over the last ``months`` months, zero-filled so every
    severity series aligns to the same month axis."""
    start = (datetime.date.today().replace(day=1)
             - datetime.timedelta(days=31 * (months - 1))).isoformat()
    rows = conn.execute("""
        SELECT to_char(date_trunc('month', detected_date::date), 'YYYY-MM') AS month,
               severity, COUNT(*) AS cnt
        FROM qa_ncr
        WHERE detected_date IS NOT NULL AND detected_date != '' AND detected_date >= %s
        GROUP BY date_trunc('month', detected_date::date), severity
        ORDER BY date_trunc('month', detected_date::date)
    """, (start,)).fetchall()

    month_list: list[str] = []
    severities: set[str] = set()
    counts: dict[tuple[str, str], int] = {}
    for r in rows:
        month, severity, cnt = r['month'], r['severity'], r['cnt']
        if month not in month_list:
            month_list.append(month)
        severities.add(severity)
        counts[(month, severity)] = cnt

    return {
        'months': month_list,
        'series': {
            sev: [counts.get((m, sev), 0) for m in month_list]
            for sev in sorted(severities)
        },
    }


def get_inspection_results(conn) -> list[dict]:
    """Return [{result, cnt}] for all inspection outcomes."""
    rows = conn.execute(
        "SELECT result, COUNT(*) AS cnt FROM qa_inspection GROUP BY result ORDER BY cnt DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_ncr_by_status(conn) -> list[dict]:
    """Return [{status, cnt}] for NCR status breakdown."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM qa_ncr GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Non-Conformance Reports (qa_ncr)
# ---------------------------------------------------------------------------

def list_ncrs(conn, status: str | None = None,
              search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(title ILIKE %s OR product ILIKE %s OR owner ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM qa_ncr {where} ORDER BY detected_date DESC, id DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_ncr(conn, ncr_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM qa_ncr WHERE id = %s", (ncr_id,)).fetchone()
    return dict(row) if row else None


def create_ncr(conn, title: str, source: str, severity: str, product: str,
               detected_date: str, disposition: str, owner: str,
               notes: str, created_by: str) -> int:
    if not title.strip():
        raise ValueError("Title is required.")
    row = conn.execute(
        "INSERT INTO qa_ncr (title, source, severity, product, detected_date, "
        "disposition, owner, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,'Open',%s,%s) RETURNING id",
        (title.strip(), source, severity, product.strip(),
         detected_date or _today(), disposition, owner.strip(),
         notes.strip(), created_by),
    ).fetchone()
    ncr_id = row['id']

    from .webhook_core import dispatch_event
    dispatch_event(conn, 'ncr.opened', 'ncr', ncr_id)

    return ncr_id


def update_ncr(conn, ncr_id: int, title: str, source: str, severity: str,
               product: str, detected_date: str, disposition: str,
               owner: str, status: str, notes: str) -> None:
    if not title.strip():
        raise ValueError("Title is required.")
    conn.execute(
        "UPDATE qa_ncr SET title=%s, source=%s, severity=%s, product=%s, "
        "detected_date=%s, disposition=%s, owner=%s, status=%s, notes=%s "
        "WHERE id=%s",
        (title.strip(), source, severity, product.strip(), detected_date,
         disposition, owner.strip(), status, notes.strip(), ncr_id),
    )


def close_ncr(conn, ncr_id: int) -> None:
    conn.execute(
        "UPDATE qa_ncr SET status='Closed', closed_date=%s WHERE id=%s",
        (_today(), ncr_id),
    )


# ---------------------------------------------------------------------------
# Corrective & Preventive Actions (qa_capa)
# ---------------------------------------------------------------------------

def _annotate_capa(d: dict) -> dict:
    today = _today()
    if (d.get('due_date') or '') < today and d.get('status') not in ('Closed',):
        d['is_overdue'] = True
    else:
        d['is_overdue'] = False
    return d


def list_capas(conn, status: str | None = None,
               search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(title ILIKE %s OR owner ILIKE %s OR ncr_ref ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM qa_capa {where} "
        f"ORDER BY CASE WHEN due_date='' THEN '9999' ELSE due_date END, id",
        params,
    ).fetchall()
    return [_annotate_capa(dict(r)) for r in rows]


def get_capa(conn, capa_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM qa_capa WHERE id = %s", (capa_id,)).fetchone()
    return _annotate_capa(dict(row)) if row else None


def create_capa(conn, title: str, capa_type: str, ncr_ref: str, owner: str,
                due_date: str, action_plan: str, created_by: str) -> int:
    if not title.strip():
        raise ValueError("Title is required.")
    row = conn.execute(
        "INSERT INTO qa_capa (title, capa_type, ncr_ref, owner, due_date, "
        "status, action_plan, created_by) "
        "VALUES (%s,%s,%s,%s,%s,'Open',%s,%s) RETURNING id",
        (title.strip(), capa_type, ncr_ref.strip(), owner.strip(),
         due_date, action_plan.strip(), created_by),
    ).fetchone()
    return row['id']


def update_capa(conn, capa_id: int, title: str, capa_type: str, ncr_ref: str,
                owner: str, due_date: str, completed_date: str,
                status: str, action_plan: str) -> None:
    if not title.strip():
        raise ValueError("Title is required.")
    conn.execute(
        "UPDATE qa_capa SET title=%s, capa_type=%s, ncr_ref=%s, owner=%s, "
        "due_date=%s, completed_date=%s, status=%s, action_plan=%s WHERE id=%s",
        (title.strip(), capa_type, ncr_ref.strip(), owner.strip(),
         due_date, completed_date, status, action_plan.strip(), capa_id),
    )


def close_capa(conn, capa_id: int) -> None:
    conn.execute(
        "UPDATE qa_capa SET status='Closed', completed_date=%s WHERE id=%s",
        (_today(), capa_id),
    )


# ---------------------------------------------------------------------------
# Quality Audits (qa_audit)
# ---------------------------------------------------------------------------

def list_audits(conn, status: str | None = None) -> list[dict]:
    where = "WHERE status = %s" if status else ""
    params = [status] if status else []
    rows = conn.execute(
        f"SELECT * FROM qa_audit {where} "
        f"ORDER BY CASE WHEN scheduled_date='' THEN '9999' ELSE scheduled_date END DESC",
        params,
    ).fetchall()
    today = _today()
    result = []
    for r in rows:
        d = dict(r)
        d['is_overdue'] = (
            (d.get('scheduled_date') or '') < today
            and d.get('status') not in ('Complete', 'Closed')
        )
        result.append(d)
    return result


def get_audit(conn, audit_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM qa_audit WHERE id = %s", (audit_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d['is_overdue'] = (
        (d.get('scheduled_date') or '') < _today()
        and d.get('status') not in ('Complete', 'Closed')
    )
    return d


def create_audit(conn, title: str, audit_type: str, auditor: str,
                 scheduled_date: str, findings: str,
                 created_by: str) -> int:
    if not title.strip():
        raise ValueError("Title is required.")
    row = conn.execute(
        "INSERT INTO qa_audit (title, audit_type, auditor, scheduled_date, "
        "status, findings, created_by) "
        "VALUES (%s,%s,%s,%s,'Scheduled',%s,%s) RETURNING id",
        (title.strip(), audit_type, auditor.strip(),
         scheduled_date, findings.strip(), created_by),
    ).fetchone()
    return row['id']


def update_audit(conn, audit_id: int, title: str, audit_type: str,
                 auditor: str, scheduled_date: str, completed_date: str,
                 result: str, status: str, findings: str) -> None:
    if not title.strip():
        raise ValueError("Title is required.")
    conn.execute(
        "UPDATE qa_audit SET title=%s, audit_type=%s, auditor=%s, "
        "scheduled_date=%s, completed_date=%s, result=%s, "
        "status=%s, findings=%s WHERE id=%s",
        (title.strip(), audit_type, auditor.strip(), scheduled_date,
         completed_date, result.strip(), status, findings.strip(), audit_id),
    )


def complete_audit(conn, audit_id: int, result: str, findings: str) -> None:
    conn.execute(
        "UPDATE qa_audit SET status='Complete', completed_date=%s, "
        "result=%s, findings=%s WHERE id=%s",
        (_today(), result.strip(), findings.strip(), audit_id),
    )


# ---------------------------------------------------------------------------
# Supplier Quality (qa_supplier)
# ---------------------------------------------------------------------------

def list_supplier_quality(conn, status: str | None = None,
                           search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(supplier ILIKE %s OR material ILIKE %s)")
        params += [f'%{search}%'] * 2
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM qa_supplier {where} ORDER BY supplier",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_supplier_quality(conn, sq_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM qa_supplier WHERE id = %s", (sq_id,)
    ).fetchone()
    return dict(row) if row else None


def create_supplier_quality(conn, supplier: str, material: str, rating: str,
                             ppm: str, last_audit: str, status: str,
                             notes: str, created_by: str) -> int:
    if not supplier.strip():
        raise ValueError("Supplier name is required.")
    row = conn.execute(
        "INSERT INTO qa_supplier (supplier, material, rating, ppm, "
        "last_audit, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (supplier.strip(), material.strip(), rating, ppm.strip(),
         last_audit, status or 'Pending', notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_supplier_quality(conn, sq_id: int, supplier: str, material: str,
                             rating: str, ppm: str, last_audit: str,
                             status: str, notes: str) -> None:
    if not supplier.strip():
        raise ValueError("Supplier name is required.")
    conn.execute(
        "UPDATE qa_supplier SET supplier=%s, material=%s, rating=%s, "
        "ppm=%s, last_audit=%s, status=%s, notes=%s WHERE id=%s",
        (supplier.strip(), material.strip(), rating, ppm.strip(),
         last_audit, status, notes.strip(), sq_id),
    )


# ---------------------------------------------------------------------------
# Inspections (qa_inspection + qa_defect)
# ---------------------------------------------------------------------------

def next_insp_number(conn) -> str:
    year = datetime.date.today().year
    prefix = f'QA-{year}-'
    rows = conn.execute(
        "SELECT insp_number FROM qa_inspection WHERE insp_number LIKE %s",
        (f'{prefix}%',),
    ).fetchall()
    max_n = 0
    for r in rows:
        try:
            max_n = max(max_n, int(r['insp_number'].split('-')[-1]))
        except (ValueError, IndexError, AttributeError):
            pass
    return f'{prefix}{max_n + 1:04d}'


def list_inspections(conn, result: str | None = None,
                     search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if result:
        conditions.append("i.result = %s")
        params.append(result)
    if search:
        conditions.append("(i.insp_number ILIKE %s OR i.inspector ILIKE %s "
                          "OR p.name ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT i.*, p.name AS product_name, "
        f"(SELECT COUNT(*) FROM qa_defect d WHERE d.insp_id=i.id) AS defect_count, "
        f"(SELECT COUNT(*) FROM qa_defect d WHERE d.insp_id=i.id AND d.resolved=0) "
        f"  AS open_defects "
        f"FROM qa_inspection i "
        f"LEFT JOIN product p ON p.id = i.product_id "
        f"{where} "
        f"ORDER BY i.insp_date DESC, i.id DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_inspection(conn, insp_id: int) -> dict | None:
    row = conn.execute(
        "SELECT i.*, p.name AS product_name "
        "FROM qa_inspection i "
        "LEFT JOIN product p ON p.id = i.product_id "
        "WHERE i.id = %s",
        (insp_id,),
    ).fetchone()
    return dict(row) if row else None


def create_inspection(conn, insp_number: str, product_id: int | None,
                      wo_id: int | None, insp_date: str, inspector: str,
                      result: str, notes: str, created_by: str,
                      sampling_plan_id: int | None = None,
                      lot_qty: float | None = None) -> int:
    """sampling_plan_id + lot_qty: optional — when both given, the
    inspection is stamped with the resolved code_letter/sample_size/
    accept_number/reject_number from that plan (see
    sampling_plan_core.resolve_sampling_plan)."""
    resolved: dict = {}
    if sampling_plan_id and lot_qty:
        resolved = resolve_sampling_plan(conn, sampling_plan_id, lot_qty)
    row = conn.execute(
        "INSERT INTO qa_inspection "
        "(insp_number, product_id, wo_id, insp_date, inspector, result, notes, "
        " created_by, sampling_plan_id, lot_qty, code_letter, sample_size, "
        " accept_number, reject_number) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (insp_number, product_id or None, wo_id or None,
         insp_date or _today(), inspector.strip(),
         result if result in INSP_RESULTS else 'pending',
         notes.strip(), created_by, sampling_plan_id or None, lot_qty,
         resolved.get('code_letter'), resolved.get('sample_size'),
         resolved.get('accept_number'), resolved.get('reject_number')),
    ).fetchone()
    return row['id']


def update_inspection_result(conn, insp_id: int, result: str) -> None:
    if result not in INSP_RESULTS:
        raise ValueError(f"Unknown result: {result!r}")
    conn.execute(
        "UPDATE qa_inspection SET result=%s WHERE id=%s", (result, insp_id)
    )


def record_sample_defects(conn, insp_id: int, qty_defective: int) -> None:
    """Record how many sampled units were found defective and, if the
    inspection has a resolved accept/reject number (from an attached
    sampling plan), auto-set result to 'passed'/'failed' accordingly (see
    sampling_plan_core.evaluate_sampling_result). Does not commit."""
    inspection = get_inspection(conn, insp_id)
    if not inspection:
        raise ValueError(f'No inspection with id {insp_id}')
    outcome = evaluate_sampling_result(
        inspection.get('accept_number'), inspection.get('reject_number'),
        qty_defective)
    if outcome:
        conn.execute(
            "UPDATE qa_inspection SET qty_defective=%s, result=%s WHERE id=%s",
            (qty_defective, outcome, insp_id),
        )
    else:
        conn.execute(
            "UPDATE qa_inspection SET qty_defective=%s WHERE id=%s",
            (qty_defective, insp_id),
        )


def get_defects(conn, insp_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM qa_defect WHERE insp_id=%s ORDER BY id DESC",
        (insp_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def log_defect(conn, insp_id: int, defect_type: str, severity: str,
               description: str, created_by: str) -> int:
    if not description.strip():
        raise ValueError("Defect description is required.")
    row = conn.execute(
        "INSERT INTO qa_defect (insp_id, defect_type, severity, description, "
        "resolved, created_by) VALUES (%s,%s,%s,%s,0,%s) RETURNING id",
        (insp_id, defect_type.strip(),
         severity if severity in DEFECT_SEVERITIES else 'minor',
         description.strip(), created_by),
    ).fetchone()
    return row['id']


def resolve_defect(conn, defect_id: int) -> None:
    conn.execute(
        "UPDATE qa_defect SET resolved=1 WHERE id=%s", (defect_id,)
    )


# ---------------------------------------------------------------------------
# Phase 6A — Statistical Process Control (SPC)
# ---------------------------------------------------------------------------

# Control chart constants for X-bar and R charts (subgroup sizes 2–10)
# A₂: used to compute X-bar UCL/LCL from average range
# D₃/D₄: used to compute R-chart UCL/LCL from average range
_A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577,
       6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
_D3 = {2: 0.0,   3: 0.0,   4: 0.0,   5: 0.0,
       6: 0.0,   7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
_D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114,
       6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}

SPC_SUBGROUP_SIZES = tuple(_A2.keys())   # 2 to 10


def ensure_spc_tables(conn) -> None:
    """Create SPC tables if they do not exist. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spc_control_limit (
            id             SERIAL PRIMARY KEY,
            product_id     INTEGER REFERENCES product(id),
            characteristic TEXT NOT NULL,
            ucl            REAL NOT NULL,
            lcl            REAL NOT NULL,
            target         REAL,
            sigma          REAL,
            subgroup_size  INTEGER NOT NULL DEFAULT 5,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_by     TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(product_id, characteristic)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spc_measurement (
            id             SERIAL PRIMARY KEY,
            product_id     INTEGER REFERENCES product(id),
            characteristic TEXT NOT NULL,
            measured_value REAL NOT NULL,
            measured_by    TEXT NOT NULL DEFAULT '',
            measured_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            wo_id          INTEGER REFERENCES work_order(id),
            lot_id         INTEGER REFERENCES lot(id),
            in_control     BOOLEAN NOT NULL DEFAULT TRUE,
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS spc_meas_product_char "
        "ON spc_measurement(product_id, characteristic, measured_at DESC)"
    )


def create_control_limit(
    conn, product_id: int | None, characteristic: str,
    ucl: float, lcl: float, target: float | None = None,
    sigma: float | None = None, subgroup_size: int = 5,
    created_by: str = '',
) -> int:
    """Upsert a spec limit record and return its id."""
    if not characteristic.strip():
        raise ValueError("characteristic is required")
    if ucl <= lcl:
        raise ValueError("ucl must be greater than lcl")
    n = int(subgroup_size)
    if n not in _A2:
        raise ValueError(f"subgroup_size must be one of {SPC_SUBGROUP_SIZES}")
    row = conn.execute("""
        INSERT INTO spc_control_limit
        (product_id, characteristic, ucl, lcl, target, sigma,
         subgroup_size, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (product_id, characteristic) DO UPDATE
          SET ucl=%s, lcl=%s, target=%s, sigma=%s,
              subgroup_size=%s, is_active=TRUE
        RETURNING id
    """, (product_id, characteristic.strip(),
          float(ucl), float(lcl), target, sigma, n, created_by,
          float(ucl), float(lcl), target, sigma, n)).fetchone()
    return row['id']


def list_control_limits(conn, product_id: int | None = None,
                        active_only: bool = True) -> list[dict]:
    conds, params = [], []
    if active_only:
        conds.append("is_active = TRUE")
    if product_id is not None:
        conds.append("product_id = %s")
        params.append(product_id)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(
        f"SELECT cl.*, p.name AS product_name "
        f"FROM spc_control_limit cl "
        f"LEFT JOIN product p ON p.id = cl.product_id "
        f"{where} "
        f"ORDER BY p.name, cl.characteristic",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_control_limit(conn, product_id: int | None,
                      characteristic: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM spc_control_limit "
        "WHERE product_id IS NOT DISTINCT FROM %s AND characteristic = %s "
        "  AND is_active = TRUE",
        (product_id, characteristic),
    ).fetchone()
    return dict(row) if row else None


def update_control_limit(
    conn, limit_id: int, ucl: float, lcl: float,
    target: float | None = None, sigma: float | None = None,
    subgroup_size: int = 5, is_active: bool = True,
) -> None:
    if ucl <= lcl:
        raise ValueError("ucl must be greater than lcl")
    conn.execute(
        "UPDATE spc_control_limit "
        "SET ucl=%s, lcl=%s, target=%s, sigma=%s, "
        "    subgroup_size=%s, is_active=%s "
        "WHERE id=%s",
        (float(ucl), float(lcl), target, sigma,
         int(subgroup_size), is_active, limit_id),
    )


def log_measurement(
    conn, product_id: int | None, characteristic: str,
    measured_value: float, measured_by: str = '',
    wo_id: int | None = None, lot_id: int | None = None,
    notes: str = '', created_by: str = '',
) -> dict:
    """Insert one measurement and evaluate it against spec limits.

    Returns a dict with 'id', 'in_control', 'ucl', 'lcl', and 'action'
    ('OK', 'ABOVE_UCL', 'BELOW_LCL', or 'NO_LIMITS').
    """
    cl = get_control_limit(conn, product_id, characteristic)
    if cl:
        in_control = float(cl['lcl']) <= float(measured_value) <= float(cl['ucl'])
        if float(measured_value) > float(cl['ucl']):
            action = 'ABOVE_UCL'
        elif float(measured_value) < float(cl['lcl']):
            action = 'BELOW_LCL'
        else:
            action = 'OK'
    else:
        in_control = True
        action = 'NO_LIMITS'

    row = conn.execute("""
        INSERT INTO spc_measurement
        (product_id, characteristic, measured_value, measured_by,
         wo_id, lot_id, in_control, notes, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (product_id, characteristic.strip(), float(measured_value),
          measured_by, wo_id, lot_id, in_control,
          notes, created_by)).fetchone()

    return {
        'id': row['id'],
        'in_control': in_control,
        'action': action,
        'ucl': float(cl['ucl']) if cl else None,
        'lcl': float(cl['lcl']) if cl else None,
    }


def get_measurements(
    conn, product_id: int | None, characteristic: str,
    limit: int = 100,
) -> list[dict]:
    """Return recent measurements, oldest first (for charting)."""
    rows = conn.execute("""
        SELECT m.id, m.measured_value, m.measured_by, m.measured_at,
               m.in_control, m.wo_id, m.lot_id, m.notes
        FROM spc_measurement m
        WHERE m.product_id IS NOT DISTINCT FROM %s
          AND m.characteristic = %s
        ORDER BY m.measured_at ASC
        LIMIT %s
    """, (product_id, characteristic, limit)).fetchall()
    return [dict(r) for r in rows]


def compute_xbar_r_chart(
    conn, product_id: int | None, characteristic: str,
    subgroup_size: int = 5,
) -> dict:
    """Compute X-bar and R chart data from stored measurements.

    Returns:
      subgroups       list of {subgroup_idx, values, mean, range, xbar_oc, r_oc}
      grand_mean      X̄̄
      grand_range     R̄
      ucl_xbar        X-bar chart UCL (X̄̄ + A₂R̄)
      lcl_xbar        X-bar chart LCL (X̄̄ - A₂R̄)
      ucl_r           R chart UCL (D₄R̄)
      lcl_r           R chart LCL (D₃R̄)
      n_subgroups     number of complete subgroups
      spec_ucl        engineering UCL from spc_control_limit (or None)
      spec_lcl        engineering LCL (or None)
    """
    n = int(subgroup_size)
    if n not in _A2:
        raise ValueError(f"subgroup_size must be one of {SPC_SUBGROUP_SIZES}")

    rows = get_measurements(conn, product_id, characteristic, limit=0)
    values = [float(r['measured_value']) for r in rows]

    cl = get_control_limit(conn, product_id, characteristic)

    if len(values) < n:
        return {
            'subgroups': [], 'grand_mean': None, 'grand_range': None,
            'ucl_xbar': None, 'lcl_xbar': None, 'ucl_r': None, 'lcl_r': None,
            'n_subgroups': 0,
            'spec_ucl': float(cl['ucl']) if cl else None,
            'spec_lcl': float(cl['lcl']) if cl else None,
        }

    # Build complete subgroups only
    subgroups = []
    for i in range(len(values) // n):
        chunk = values[i * n: (i + 1) * n]
        sg_mean = sum(chunk) / n
        sg_range = max(chunk) - min(chunk)
        subgroups.append({'idx': i + 1, 'values': chunk,
                          'mean': sg_mean, 'range': sg_range})

    grand_mean = sum(s['mean'] for s in subgroups) / len(subgroups)
    grand_range = sum(s['range'] for s in subgroups) / len(subgroups)

    a2, d3, d4 = _A2[n], _D3[n], _D4[n]
    ucl_xbar = grand_mean + a2 * grand_range
    lcl_xbar = grand_mean - a2 * grand_range
    ucl_r = d4 * grand_range
    lcl_r = d3 * grand_range

    for s in subgroups:
        s['xbar_oc'] = not (lcl_xbar <= s['mean'] <= ucl_xbar)
        s['r_oc'] = not (lcl_r <= s['range'] <= ucl_r)

    return {
        'subgroups':   subgroups,
        'grand_mean':  round(grand_mean, 6),
        'grand_range': round(grand_range, 6),
        'ucl_xbar':    round(ucl_xbar, 6),
        'lcl_xbar':    round(lcl_xbar, 6),
        'ucl_r':       round(ucl_r, 6),
        'lcl_r':       round(lcl_r, 6),
        'n_subgroups': len(subgroups),
        'spec_ucl':    float(cl['ucl']) if cl else None,
        'spec_lcl':    float(cl['lcl']) if cl else None,
    }


def compute_cpk(conn, product_id: int | None,
                characteristic: str) -> dict:
    """Compute Cpk from stored measurements and spec limits.

    Cpk = min(Cpu, Cpl)
    Cpu = (USL - μ) / (3σ)
    Cpl = (μ - LSL) / (3σ)

    Returns dict with cpk, cpu, cpl, mean, std_dev, ucl (USL), lcl (LSL), n.
    Returns {'cpk': None, 'error': '...'} if no measurements or limits.
    """
    cl = get_control_limit(conn, product_id, characteristic)
    if not cl:
        return {'cpk': None, 'error': 'No spec limits defined'}

    rows = get_measurements(conn, product_id, characteristic, limit=0)
    values = [float(r['measured_value']) for r in rows]
    n = len(values)
    if n < 2:
        return {'cpk': None, 'error': f'Need at least 2 measurements (have {n})'}

    mu = statistics.mean(values)
    sigma = statistics.stdev(values)   # sample std dev
    if sigma == 0:
        return {'cpk': None, 'error': 'Zero variance — all measurements identical'}

    usl = float(cl['ucl'])
    lsl = float(cl['lcl'])
    cpu = (usl - mu) / (3 * sigma)
    cpl = (mu - lsl) / (3 * sigma)
    cpk = min(cpu, cpl)

    return {
        'cpk':     round(cpk, 4),
        'cpu':     round(cpu, 4),
        'cpl':     round(cpl, 4),
        'mean':    round(mu, 6),
        'std_dev': round(sigma, 6),
        'ucl':     usl,
        'lcl':     lsl,
        'n':       n,
    }


def get_spc_alerts(conn, limit: int = 50) -> list[dict]:
    """Return recent out-of-control measurements for the SPC alert panel."""
    rows = conn.execute("""
        SELECT m.id, m.product_id, m.characteristic, m.measured_value,
               m.measured_by, m.measured_at, m.in_control, m.wo_id, m.lot_id,
               p.name AS product_name,
               cl.ucl, cl.lcl
        FROM spc_measurement m
        LEFT JOIN product p ON p.id = m.product_id
        LEFT JOIN spc_control_limit cl
          ON cl.product_id IS NOT DISTINCT FROM m.product_id
         AND cl.characteristic = m.characteristic
         AND cl.is_active = TRUE
        WHERE m.in_control = FALSE
        ORDER BY m.measured_at DESC
        LIMIT %s
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Product / WO loaders for dropdowns
# ---------------------------------------------------------------------------

def load_products_for_qa(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name FROM product ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def load_work_orders_for_qa(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, wo_number FROM work_order ORDER BY id DESC LIMIT 100"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# QA Reports
# ---------------------------------------------------------------------------

def get_qa_reports(conn) -> dict:
    """Return aggregated QA statistics for the reports page.

    Covers NCRs by severity, CAPAs by status, audit results, inspection
    pass/fail rates, and monthly inspection volume (last 6 months).
    """
    today = _today()

    # NCR counts by severity
    rows = conn.execute(
        "SELECT severity, COUNT(*) AS cnt FROM qa_ncr "
        "WHERE status != 'Closed' GROUP BY severity ORDER BY severity"
    ).fetchall()
    ncrs_by_severity = [dict(r) for r in rows]

    # NCR counts by source
    rows = conn.execute(
        "SELECT source, COUNT(*) AS cnt FROM qa_ncr "
        "WHERE status != 'Closed' GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    ncrs_by_source = [dict(r) for r in rows]

    # CAPA counts by status
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM qa_capa GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    capas_by_status = [dict(r) for r in rows]

    # Audit counts by type
    rows = conn.execute(
        "SELECT audit_type, COUNT(*) AS cnt FROM qa_audit GROUP BY audit_type ORDER BY cnt DESC"
    ).fetchall()
    audits_by_type = [dict(r) for r in rows]

    # Inspection pass/fail counts
    rows = conn.execute(
        "SELECT result, COUNT(*) AS cnt FROM qa_inspection GROUP BY result ORDER BY result"
    ).fetchall()
    insp_by_result = [dict(r) for r in rows]
    total_insp = sum(r['cnt'] for r in insp_by_result) or 1
    for r in insp_by_result:
        r['pct'] = round(r['cnt'] * 100 / total_insp)

    # Monthly inspection volume (last 6 months)
    rows = conn.execute(
        "SELECT TO_CHAR(insp_date::date, 'YYYY-MM') AS month, COUNT(*) AS cnt "
        "FROM qa_inspection "
        "WHERE insp_date >= (CURRENT_DATE - INTERVAL '6 months')::text "
        "GROUP BY month ORDER BY month"
    ).fetchall()
    monthly_insp = [dict(r) for r in rows]

    # Supplier quality rating breakdown
    rows = conn.execute(
        "SELECT rating, COUNT(*) AS cnt FROM qa_supplier GROUP BY rating ORDER BY rating"
    ).fetchall()
    suppliers_by_rating = [dict(r) for r in rows]

    # KPI totals
    totals = conn.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM qa_ncr WHERE status != 'Closed') AS open_ncrs, "
        "(SELECT COUNT(*) FROM qa_capa WHERE status NOT IN ('Closed','Overdue')) AS open_capas, "
        "(SELECT COUNT(*) FROM qa_capa WHERE due_date != '' AND due_date < %s "
        "  AND status NOT IN ('Closed')) AS overdue_capas, "
        "(SELECT COUNT(*) FROM qa_inspection WHERE result = 'passed') AS passed_insp, "
        "(SELECT COUNT(*) FROM qa_inspection WHERE result = 'failed') AS failed_insp, "
        "(SELECT COUNT(*) FROM qa_inspection) AS total_insp ",
        (today,),
    ).fetchone()
    kpis = dict(totals) if totals else {}
    total_closed = (kpis.get('passed_insp') or 0) + (kpis.get('failed_insp') or 0)
    kpis['pass_rate'] = (
        round(kpis['passed_insp'] * 100 / total_closed) if total_closed else None
    )

    return {
        'kpis': kpis,
        'ncrs_by_severity': ncrs_by_severity,
        'ncrs_by_source': ncrs_by_source,
        'capas_by_status': capas_by_status,
        'audits_by_type': audits_by_type,
        'insp_by_result': insp_by_result,
        'monthly_insp': monthly_insp,
        'suppliers_by_rating': suppliers_by_rating,
    }
