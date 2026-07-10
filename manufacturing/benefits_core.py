"""benefits_core.py — Qt-free Benefits Management, 7/10 of the top-10
ERPs have it.

This is deliberately a parallel *plan catalog + enrollment tracker*, not a
replacement for payroll_core's existing `payroll_deduction_type`/
`employee_deduction` tables (which already model a flat/percent payroll
deduction, including a 'Benefits' category) — those two tables answer "how
much comes out of this paycheck," this module answers "which benefit plans
exist, what do they cost, and who's enrolled in what tier." The two are
intentionally not merged: linking an enrollment to a specific
employee_deduction row would require picking one deduction calc method per
plan/tier combination, which isn't this module's job. Enrolling an employee
here does not create or touch any employee_deduction row — an admin still
sets that up separately in Payroll, the same "two independent
sources of truth" scoping already accepted for the FIFO/LIFO cost layers
existing beside standard costing.

Tables:
  benefit_plan       — one row per offered plan: type, carrier, and the
                       employee/employer cost split per pay period
  benefit_enrollment — one row per employee-plan enrollment: tier
                       (Employee Only / +Spouse / +Child(ren) / Family),
                       status, and the dates it was active

Every function takes an open connection; the caller owns the transaction
(same convention as price_list_core / skills_matrix_core).
"""

from __future__ import annotations

import datetime

PLAN_TYPES = ('Health', 'Dental', 'Vision', 'Life', 'Disability', '401k', 'Other')
TIERS = ('Employee Only', 'Employee + Spouse', 'Employee + Child(ren)', 'Family')
ENROLLMENT_STATUSES = ('active', 'waived', 'terminated')


def _today() -> str:
    return datetime.date.today().isoformat()


def ensure_benefits_tables(conn):
    """Create benefit_plan / benefit_enrollment if absent. Idempotent —
    does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS benefit_plan (
            id                    SERIAL PRIMARY KEY,
            name                  TEXT NOT NULL,
            plan_type             TEXT NOT NULL DEFAULT 'Health',
            carrier               TEXT NOT NULL DEFAULT '',
            description           TEXT NOT NULL DEFAULT '',
            employee_cost_per_pay REAL NOT NULL DEFAULT 0,
            employer_cost_per_pay REAL NOT NULL DEFAULT 0,
            is_active             INTEGER NOT NULL DEFAULT 1,
            created_by            TEXT NOT NULL DEFAULT '',
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS benefit_enrollment (
            id                SERIAL PRIMARY KEY,
            people_id         INTEGER NOT NULL REFERENCES people(id),
            plan_id           INTEGER NOT NULL REFERENCES benefit_plan(id),
            tier              TEXT NOT NULL DEFAULT 'Employee Only',
            status            TEXT NOT NULL DEFAULT 'active',
            dependents_count  INTEGER NOT NULL DEFAULT 0,
            enrollment_date   TEXT NOT NULL DEFAULT '',
            termination_date  TEXT,
            notes             TEXT NOT NULL DEFAULT '',
            created_by        TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS benefit_enrollment_people "
        "ON benefit_enrollment(people_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS benefit_enrollment_plan "
        "ON benefit_enrollment(plan_id)"
    )


# ---------------------------------------------------------------------------
# Plan catalog
# ---------------------------------------------------------------------------

def list_plans(conn, active_only=False, plan_type=None):
    sql = "SELECT * FROM benefit_plan WHERE TRUE"
    params: list = []
    if active_only:
        sql += " AND is_active = 1"
    if plan_type:
        sql += " AND plan_type = %s"
        params.append(plan_type)
    sql += " ORDER BY plan_type, name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_plan(conn, plan_id):
    row = conn.execute(
        "SELECT * FROM benefit_plan WHERE id = %s", (plan_id,)
    ).fetchone()
    return dict(row) if row else None


def create_plan(conn, name, plan_type, carrier='', description='',
                employee_cost_per_pay=0.0, employer_cost_per_pay=0.0,
                created_by=''):
    if not name or not name.strip():
        raise ValueError('name is required')
    if plan_type not in PLAN_TYPES:
        raise ValueError(f'plan_type must be one of {PLAN_TYPES}')
    row = conn.execute(
        "INSERT INTO benefit_plan "
        "(name, plan_type, carrier, description, employee_cost_per_pay, "
        " employer_cost_per_pay, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), plan_type, carrier or '', description or '',
         float(employee_cost_per_pay), float(employer_cost_per_pay),
         created_by or ''),
    ).fetchone()
    return row['id']


def update_plan(conn, plan_id, **fields):
    allowed = {
        'name', 'plan_type', 'carrier', 'description',
        'employee_cost_per_pay', 'employer_cost_per_pay', 'is_active',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if 'plan_type' in cols and cols['plan_type'] not in PLAN_TYPES:
        raise ValueError(f'plan_type must be one of {PLAN_TYPES}')
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE benefit_plan SET {set_clause} WHERE id = %s",
        list(cols.values()) + [plan_id],
    )


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------

def list_enrollments(conn, people_id=None, plan_id=None, status=None):
    sql = (
        "SELECT e.*, p.first_name, p.last_name, "
        "bp.name AS plan_name, bp.plan_type, bp.carrier, "
        "bp.employee_cost_per_pay, bp.employer_cost_per_pay "
        "FROM benefit_enrollment e "
        "JOIN people p ON p.id = e.people_id "
        "JOIN benefit_plan bp ON bp.id = e.plan_id "
        "WHERE TRUE"
    )
    params: list = []
    if people_id:
        sql += " AND e.people_id = %s"
        params.append(people_id)
    if plan_id:
        sql += " AND e.plan_id = %s"
        params.append(plan_id)
    if status:
        sql += " AND e.status = %s"
        params.append(status)
    sql += " ORDER BY p.last_name, p.first_name, bp.name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_enrollment(conn, enrollment_id):
    row = conn.execute(
        "SELECT e.*, p.first_name, p.last_name, "
        "bp.name AS plan_name, bp.plan_type, bp.carrier, "
        "bp.employee_cost_per_pay, bp.employer_cost_per_pay "
        "FROM benefit_enrollment e "
        "JOIN people p ON p.id = e.people_id "
        "JOIN benefit_plan bp ON bp.id = e.plan_id "
        "WHERE e.id = %s",
        (enrollment_id,),
    ).fetchone()
    return dict(row) if row else None


def enroll_employee(conn, people_id, plan_id, tier, dependents_count=0,
                    notes='', created_by=''):
    """Enroll an employee in a plan at a given tier. Raises if the plan
    isn't active, the tier isn't recognized, or the employee already has
    an active enrollment in this plan (waive/terminate it first — an
    employee can't be double-enrolled in the same plan)."""
    plan = get_plan(conn, plan_id)
    if not plan:
        raise ValueError(f'No plan with id {plan_id}')
    if not plan['is_active']:
        raise ValueError(f"Plan {plan['name']!r} is not active")
    if tier not in TIERS:
        raise ValueError(f'tier must be one of {TIERS}')
    existing = conn.execute(
        "SELECT id FROM benefit_enrollment "
        "WHERE people_id = %s AND plan_id = %s AND status = 'active'",
        (people_id, plan_id),
    ).fetchone()
    if existing:
        raise ValueError('Employee already has an active enrollment in this plan')
    row = conn.execute(
        "INSERT INTO benefit_enrollment "
        "(people_id, plan_id, tier, status, dependents_count, "
        " enrollment_date, notes, created_by) "
        "VALUES (%s,%s,%s,'active',%s,%s,%s,%s) RETURNING id",
        (people_id, plan_id, tier, int(dependents_count or 0), _today(),
         notes or '', created_by or ''),
    ).fetchone()
    return row['id']


def _set_enrollment_status(conn, enrollment_id, status):
    conn.execute(
        "UPDATE benefit_enrollment SET status = %s, termination_date = %s "
        "WHERE id = %s",
        (status, _today(), enrollment_id),
    )


def waive_enrollment(conn, enrollment_id):
    _set_enrollment_status(conn, enrollment_id, 'waived')


def terminate_enrollment(conn, enrollment_id):
    _set_enrollment_status(conn, enrollment_id, 'terminated')


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def get_employee_benefits(conn, people_id):
    """Active enrollments for one employee, plus their total per-pay-period
    cost. Used by the Employee Self-Service benefits view."""
    enrollments = list_enrollments(conn, people_id=people_id, status='active')
    total_employee_cost = sum(e['employee_cost_per_pay'] for e in enrollments)
    total_employer_cost = sum(e['employer_cost_per_pay'] for e in enrollments)
    return {
        'enrollments': enrollments,
        'total_employee_cost_per_pay': total_employee_cost,
        'total_employer_cost_per_pay': total_employer_cost,
    }


def get_benefits_dashboard(conn):
    """Org-wide summary: plan count, active enrollment count, and total
    employer/employee cost per pay period across all active enrollments,
    broken down by plan type."""
    plan_row = conn.execute(
        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_active = 1) AS active "
        "FROM benefit_plan"
    ).fetchone()
    enroll_row = conn.execute(
        "SELECT COUNT(*) AS active_count, "
        "COALESCE(SUM(bp.employee_cost_per_pay), 0) AS total_employee_cost, "
        "COALESCE(SUM(bp.employer_cost_per_pay), 0) AS total_employer_cost "
        "FROM benefit_enrollment e "
        "JOIN benefit_plan bp ON bp.id = e.plan_id "
        "WHERE e.status = 'active'"
    ).fetchone()
    by_type_rows = conn.execute(
        "SELECT bp.plan_type, COUNT(*) AS enrolled_count, "
        "COALESCE(SUM(bp.employer_cost_per_pay), 0) AS employer_cost "
        "FROM benefit_enrollment e "
        "JOIN benefit_plan bp ON bp.id = e.plan_id "
        "WHERE e.status = 'active' "
        "GROUP BY bp.plan_type ORDER BY employer_cost DESC"
    ).fetchall()
    return {
        'plans': dict(plan_row) if plan_row else {'total': 0, 'active': 0},
        'enrollments': dict(enroll_row) if enroll_row else
            {'active_count': 0, 'total_employee_cost': 0, 'total_employer_cost': 0},
        'by_plan_type': [dict(r) for r in by_type_rows],
    }
