"""
payroll_core.py — Qt-free data layer for Payroll web views.

Tables: employee_pay, payroll_run, payroll_entry, payroll_deduction_type,
        employee_deduction, payroll_entry_deduction
No PyQt6, no commit inside any function.
"""

import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SS_RATE       = 0.062
MEDICARE_RATE = 0.0145

FREQ_DIVISORS = {
    'Weekly': 52, 'Bi-Weekly': 26, 'Semi-Monthly': 24, 'Monthly': 12,
}
FREQUENCIES    = tuple(FREQ_DIVISORS.keys())
PAY_TYPES      = ('hourly', 'salary')
DED_CATEGORIES = ('Benefits', 'Retirement', 'Garnishment', 'Other')
DED_METHODS    = ('flat', 'percent')


def _today() -> str:
    return datetime.date.today().isoformat()


def _cur_year() -> int:
    return datetime.date.today().year


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard_counts(conn) -> dict:
    row = conn.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM payroll_run) AS total_runs, "
        "(SELECT COUNT(*) FROM employee_pay) AS emp_with_rates, "
        "(SELECT COUNT(*) FROM people) AS total_people, "
        "(SELECT COUNT(*) FROM payroll_deduction_type WHERE is_active=1) AS active_ded_types, "
        "(SELECT COALESCE(SUM(gross_pay),0) FROM payroll_entry pe "
        " JOIN payroll_run pr ON pr.id=pe.run_id "
        " WHERE LEFT(pr.pay_period_start,4)=%s) AS ytd_gross",
        (str(_cur_year()),),
    ).fetchone()
    return dict(row) if row else {
        'total_runs': 0, 'emp_with_rates': 0, 'total_people': 0,
        'active_ded_types': 0, 'ytd_gross': 0.0,
    }


# ---------------------------------------------------------------------------
# People loader (for dropdowns)
# ---------------------------------------------------------------------------

def load_people(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, first_name, last_name, employee_id "
        "FROM people ORDER BY last_name, first_name"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pay Rates  (employee_pay)
# ---------------------------------------------------------------------------

def list_pay_rates(conn, search: str | None = None) -> list[dict]:
    if search:
        rows = conn.execute(
            "SELECT p.id AS people_id, p.first_name, p.last_name, "
            "p.employee_id, ep.pay_type, ep.pay_rate, ep.effective_date "
            "FROM people p LEFT JOIN employee_pay ep ON ep.people_id=p.id "
            "WHERE p.first_name ILIKE %s OR p.last_name ILIKE %s "
            "ORDER BY p.last_name, p.first_name",
            (f'%{search}%', f'%{search}%'),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.id AS people_id, p.first_name, p.last_name, "
            "p.employee_id, ep.pay_type, ep.pay_rate, ep.effective_date "
            "FROM people p LEFT JOIN employee_pay ep ON ep.people_id=p.id "
            "ORDER BY p.last_name, p.first_name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_pay_rate(conn, people_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM employee_pay WHERE people_id=%s", (people_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_pay_rate(conn, people_id: int, pay_type: str,
                    pay_rate: float, effective_date: str) -> None:
    if pay_type not in PAY_TYPES:
        pay_type = 'hourly'
    conn.execute(
        "INSERT INTO employee_pay (people_id, pay_type, pay_rate, effective_date) "
        "VALUES (%s,%s,%s,%s) "
        "ON CONFLICT(people_id) DO UPDATE SET "
        "pay_type=EXCLUDED.pay_type, pay_rate=EXCLUDED.pay_rate, "
        "effective_date=EXCLUDED.effective_date",
        (people_id, pay_type, pay_rate, effective_date or _today()),
    )


def delete_pay_rate(conn, people_id: int) -> None:
    conn.execute("DELETE FROM employee_pay WHERE people_id=%s", (people_id,))


# ---------------------------------------------------------------------------
# Deduction Types  (payroll_deduction_type)
# ---------------------------------------------------------------------------

def list_deduction_types(conn, active_only: bool = False) -> list[dict]:
    if active_only:
        rows = conn.execute(
            "SELECT * FROM payroll_deduction_type WHERE is_active=1 "
            "ORDER BY category, name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM payroll_deduction_type ORDER BY category, name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_deduction_type(conn, ded_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM payroll_deduction_type WHERE id=%s", (ded_id,)
    ).fetchone()
    return dict(row) if row else None


def create_deduction_type(conn, name: str, category: str,
                          is_pre_tax: bool) -> int:
    if not name.strip():
        raise ValueError("Name is required.")
    row = conn.execute(
        "INSERT INTO payroll_deduction_type (name, category, is_pre_tax, is_active) "
        "VALUES (%s,%s,%s,1) RETURNING id",
        (name.strip(), category if category in DED_CATEGORIES else 'Other',
         1 if is_pre_tax else 0),
    ).fetchone()
    return row['id']


def update_deduction_type(conn, ded_id: int, name: str, category: str,
                          is_pre_tax: bool, is_active: bool) -> None:
    if not name.strip():
        raise ValueError("Name is required.")
    conn.execute(
        "UPDATE payroll_deduction_type SET name=%s, category=%s, "
        "is_pre_tax=%s, is_active=%s WHERE id=%s",
        (name.strip(), category if category in DED_CATEGORIES else 'Other',
         1 if is_pre_tax else 0, 1 if is_active else 0, ded_id),
    )


# ---------------------------------------------------------------------------
# Employee Deductions  (employee_deduction)
# ---------------------------------------------------------------------------

def list_employee_deductions(conn, people_id: int | None = None) -> list[dict]:
    if people_id:
        rows = conn.execute(
            "SELECT ed.id, ed.people_id, p.first_name, p.last_name, "
            "dt.name AS ded_name, dt.category, dt.is_pre_tax, "
            "ed.calc_method, ed.amount, ed.is_active, ed.notes "
            "FROM employee_deduction ed "
            "JOIN people p ON p.id=ed.people_id "
            "JOIN payroll_deduction_type dt ON dt.id=ed.deduction_type_id "
            "WHERE ed.people_id=%s "
            "ORDER BY p.last_name, p.first_name, dt.name",
            (people_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT ed.id, ed.people_id, p.first_name, p.last_name, "
            "dt.name AS ded_name, dt.category, dt.is_pre_tax, "
            "ed.calc_method, ed.amount, ed.is_active, ed.notes "
            "FROM employee_deduction ed "
            "JOIN people p ON p.id=ed.people_id "
            "JOIN payroll_deduction_type dt ON dt.id=ed.deduction_type_id "
            "ORDER BY p.last_name, p.first_name, dt.name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_employee_deduction(conn, ded_id: int) -> dict | None:
    row = conn.execute(
        "SELECT ed.*, dt.name AS ded_name, dt.category, dt.is_pre_tax AS ded_is_pre_tax, "
        "p.first_name, p.last_name "
        "FROM employee_deduction ed "
        "JOIN payroll_deduction_type dt ON dt.id=ed.deduction_type_id "
        "JOIN people p ON p.id=ed.people_id "
        "WHERE ed.id=%s",
        (ded_id,),
    ).fetchone()
    return dict(row) if row else None


def create_employee_deduction(conn, people_id: int, deduction_type_id: int,
                              calc_method: str, amount: float,
                              is_active: bool, notes: str) -> int:
    row = conn.execute(
        "INSERT INTO employee_deduction "
        "(people_id, deduction_type_id, calc_method, amount, is_active, notes, effective_date) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (people_id, deduction_type_id,
         calc_method if calc_method in DED_METHODS else 'flat',
         amount, 1 if is_active else 0, notes.strip(), _today()),
    ).fetchone()
    return row['id']


def update_employee_deduction(conn, ded_id: int, people_id: int,
                              deduction_type_id: int, calc_method: str,
                              amount: float, is_active: bool, notes: str) -> None:
    conn.execute(
        "UPDATE employee_deduction SET people_id=%s, deduction_type_id=%s, "
        "calc_method=%s, amount=%s, is_active=%s, notes=%s WHERE id=%s",
        (people_id, deduction_type_id,
         calc_method if calc_method in DED_METHODS else 'flat',
         amount, 1 if is_active else 0, notes.strip(), ded_id),
    )


def delete_employee_deduction(conn, ded_id: int) -> None:
    conn.execute("DELETE FROM employee_deduction WHERE id=%s", (ded_id,))


# ---------------------------------------------------------------------------
# Payroll Runs  (payroll_run + payroll_entry)
# ---------------------------------------------------------------------------

def list_payroll_runs(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT pr.id, pr.run_date, pr.pay_period_start, pr.pay_period_end, "
        "pr.status, pr.created_by, "
        "COUNT(pe.id) AS emp_count, "
        "COALESCE(SUM(pe.gross_pay), 0) AS total_gross, "
        "COALESCE(SUM(pe.net_pay), 0) AS total_net "
        "FROM payroll_run pr "
        "LEFT JOIN payroll_entry pe ON pe.run_id=pr.id "
        "GROUP BY pr.id, pr.run_date, pr.pay_period_start, "
        "pr.pay_period_end, pr.status, pr.created_by "
        "ORDER BY pr.run_date DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_payroll_run(conn, run_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM payroll_run WHERE id=%s", (run_id,)
    ).fetchone()
    return dict(row) if row else None


def get_run_entries(conn, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT pe.*, p.first_name, p.last_name, p.employee_id "
        "FROM payroll_entry pe "
        "JOIN people p ON p.id=pe.people_id "
        "WHERE pe.run_id=%s "
        "ORDER BY p.last_name, p.first_name",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pay Stubs
# ---------------------------------------------------------------------------

def get_pay_stub(conn, entry_id: int) -> dict | None:
    row = conn.execute(
        "SELECT pe.*, p.first_name, p.last_name, p.employee_id, "
        "pr.pay_period_start, pr.pay_period_end, pr.run_date, pr.status, "
        "ep.pay_type, ep.pay_rate "
        "FROM payroll_entry pe "
        "JOIN people p      ON p.id=pe.people_id "
        "JOIN payroll_run pr ON pr.id=pe.run_id "
        "LEFT JOIN employee_pay ep ON ep.people_id=pe.people_id "
        "WHERE pe.id=%s",
        (entry_id,),
    ).fetchone()
    return dict(row) if row else None


def get_stub_deductions(conn, entry_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM payroll_entry_deduction WHERE entry_id=%s "
        "ORDER BY is_pre_tax DESC, deduction_name",
        (entry_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_run_employees(conn, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT pe.id AS entry_id, p.first_name, p.last_name "
        "FROM payroll_entry pe JOIN people p ON p.id=pe.people_id "
        "WHERE pe.run_id=%s ORDER BY p.last_name, p.first_name",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# YTD Report
# ---------------------------------------------------------------------------

def get_ytd(conn, year: int, people_id: int | None = None) -> list[dict]:
    q = (
        "SELECT p.first_name, p.last_name, "
        "COUNT(DISTINCT pe.run_id) AS run_count, "
        "SUM(pe.regular_hours)     AS reg_hrs, "
        "SUM(pe.overtime_hours)    AS ot_hrs, "
        "SUM(pe.gross_pay)         AS gross, "
        "SUM(pe.pre_tax_deductions) AS pre_deds, "
        "SUM(pe.federal_tax)       AS fed, "
        "SUM(pe.state_tax)         AS state_tax, "
        "SUM(pe.social_security)   AS ss, "
        "SUM(pe.medicare)          AS medicare, "
        "SUM(pe.net_pay)           AS net "
        "FROM payroll_entry pe "
        "JOIN people p      ON p.id=pe.people_id "
        "JOIN payroll_run pr ON pr.id=pe.run_id "
        "WHERE LEFT(pr.pay_period_start, 4)=%s"
    )
    params: list = [str(year)]
    if people_id:
        q += " AND pe.people_id=%s"
        params.append(people_id)
    q += (" GROUP BY pe.people_id, p.first_name, p.last_name "
          "ORDER BY p.last_name, p.first_name")
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]
