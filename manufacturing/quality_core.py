"""
quality_core.py — Qt-free data layer for QA web views.

Tables: qa_ncr, qa_capa, qa_audit, qa_supplier (qa_inspection, qa_defect,
qa_spec handled at the bottom).  No PyQt6, no commit inside any function.
"""

import datetime

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
    return row['id']


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
                      result: str, notes: str, created_by: str) -> int:
    row = conn.execute(
        "INSERT INTO qa_inspection "
        "(insp_number, product_id, wo_id, insp_date, inspector, result, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (insp_number, product_id or None, wo_id or None,
         insp_date or _today(), inspector.strip(),
         result if result in INSP_RESULTS else 'pending',
         notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_inspection_result(conn, insp_id: int, result: str) -> None:
    if result not in INSP_RESULTS:
        raise ValueError(f"Unknown result: {result!r}")
    conn.execute(
        "UPDATE qa_inspection SET result=%s WHERE id=%s", (result, insp_id)
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
