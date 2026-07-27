"""Qt-free Risk Management data layer — register, assessments, insurance,
continuity, audits, KRIs. Tables already exist (schema.py) and back
risk_dashboard's KPIs; this module adds the list/detail query functions the
individual leaf pages need.
"""

RISK_STATUSES = ('Open', 'Mitigating', 'Mitigated', 'Closed')
ASSESSMENT_STATUSES = ('Identified', 'In Review', 'Assessed', 'Closed')
INSURANCE_STATUSES = ('Active', 'Expired', 'Cancelled')
CONTINUITY_STATUSES = ('Draft', 'Active', 'Under Review', 'Retired')
AUDIT_STATUSES = ('Scheduled', 'In Progress', 'Completed', 'Closed')
KRI_STATUSES = ('Normal', 'Watch', 'Breached')


def list_risk_register(conn, status=None, search=None) -> list:
    sql = ("SELECT id, risk, category, severity, response, owner, "
           "target_date, status, mitigation FROM risk_register WHERE TRUE")
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (risk ILIKE %s OR category ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_risk_register(conn, risk, category, severity, response, owner,
                          target_date, status, mitigation) -> int:
    cur = conn.execute(
        "INSERT INTO risk_register "
        "(risk, category, severity, response, owner, target_date, status, mitigation) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (risk, category, severity, response, owner, target_date or None,
         status or 'Open', mitigation),
    )
    return cur.fetchone()[0]


def list_risk_assessments(conn, status=None, search=None) -> list:
    sql = ("SELECT id, title, category, likelihood, impact, risk_level, "
           "owner, assessed_date, status FROM risk_assessment WHERE TRUE")
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (title ILIKE %s OR category ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_risk_assessment(conn, title, category, likelihood, impact,
                            risk_level, owner, assessed_date, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO risk_assessment "
        "(title, category, likelihood, impact, risk_level, owner, assessed_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (title, category, likelihood, impact, risk_level, owner,
         assessed_date or None, status or 'Identified', notes),
    )
    return cur.fetchone()[0]


def list_risk_insurance(conn, status=None, search=None) -> list:
    sql = ("SELECT id, policy, insurer, policy_type, coverage, premium, "
           "start_date, end_date, status FROM risk_insurance WHERE TRUE")
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (policy ILIKE %s OR insurer ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_risk_insurance(conn, policy, insurer, policy_type, coverage,
                           premium, start_date, end_date, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO risk_insurance "
        "(policy, insurer, policy_type, coverage, premium, start_date, end_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (policy, insurer, policy_type, coverage or 0, premium or 0,
         start_date or None, end_date or None, status or 'Active', notes),
    )
    return cur.fetchone()[0]


def list_risk_continuity(conn, status=None, search=None) -> list:
    sql = ("SELECT id, plan, scope, criticality, owner, last_tested, "
           "next_test, status FROM risk_continuity WHERE TRUE")
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (plan ILIKE %s OR scope ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_risk_continuity(conn, plan, scope, criticality, owner,
                            last_tested, next_test, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO risk_continuity "
        "(plan, scope, criticality, owner, last_tested, next_test, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (plan, scope, criticality, owner, last_tested or None,
         next_test or None, status or 'Draft', notes),
    )
    return cur.fetchone()[0]


def list_risk_audits(conn, status=None, search=None) -> list:
    sql = ("SELECT id, audit, framework, auditor, scheduled_date, "
           "completed_date, finding, status FROM risk_audit WHERE TRUE")
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (audit ILIKE %s OR framework ILIKE %s OR auditor ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_risk_audit(conn, audit, framework, auditor, scheduled_date,
                       completed_date, finding, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO risk_audit "
        "(audit, framework, auditor, scheduled_date, completed_date, finding, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (audit, framework, auditor, scheduled_date or None,
         completed_date or None, finding, status or 'Scheduled', notes),
    )
    return cur.fetchone()[0]


def list_risk_kris(conn, status=None, search=None) -> list:
    sql = ("SELECT id, indicator, category, threshold, current_value, "
           "owner, measured_date, status FROM risk_kri WHERE TRUE")
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (indicator ILIKE %s OR category ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_risk_kri(conn, indicator, category, threshold, current_value,
                     owner, measured_date, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO risk_kri "
        "(indicator, category, threshold, current_value, owner, measured_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (indicator, category, threshold, current_value, owner,
         measured_date or None, status or 'Normal', notes),
    )
    return cur.fetchone()[0]
