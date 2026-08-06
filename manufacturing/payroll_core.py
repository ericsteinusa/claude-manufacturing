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


def ensure_payroll_tables(conn):
    """Create the payroll tables if absent. Idempotent — does not commit.

    Unlike most *_core.py modules, payroll_core historically assumed these
    tables already existed (inherited from a pre-Django DB that had them
    from years of desktop-app use) — on a freshly provisioned database
    every payroll view/seed call fails with UndefinedTable. Mirrors the
    ensure_benefits_tables(conn) pattern in benefits_core.py."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_deduction_type (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'Other',
            is_pre_tax  INTEGER NOT NULL DEFAULT 0,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_by  TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_pay (
            people_id       INTEGER PRIMARY KEY REFERENCES people(id),
            pay_type        TEXT NOT NULL DEFAULT 'hourly',
            pay_rate        REAL NOT NULL DEFAULT 0,
            effective_date  TEXT NOT NULL DEFAULT '',
            created_by      TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_deduction (
            id                 SERIAL PRIMARY KEY,
            people_id          INTEGER NOT NULL REFERENCES people(id),
            deduction_type_id  INTEGER NOT NULL REFERENCES payroll_deduction_type(id),
            calc_method        TEXT NOT NULL DEFAULT 'flat',
            amount             REAL NOT NULL DEFAULT 0,
            is_active          INTEGER NOT NULL DEFAULT 1,
            notes              TEXT NOT NULL DEFAULT '',
            effective_date     TEXT NOT NULL DEFAULT '',
            created_by         TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_run (
            id                 SERIAL PRIMARY KEY,
            pay_period_start   TEXT NOT NULL,
            pay_period_end     TEXT NOT NULL,
            run_date           TEXT NOT NULL DEFAULT '',
            pay_frequency      TEXT NOT NULL DEFAULT 'Bi-Weekly',
            federal_tax_rate   REAL NOT NULL DEFAULT 0,
            state_tax_rate     REAL NOT NULL DEFAULT 0,
            status             TEXT NOT NULL DEFAULT 'processed',
            created_by         TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_entry (
            id                    SERIAL PRIMARY KEY,
            run_id                INTEGER NOT NULL REFERENCES payroll_run(id),
            people_id             INTEGER NOT NULL REFERENCES people(id),
            regular_hours         REAL NOT NULL DEFAULT 0,
            overtime_hours        REAL NOT NULL DEFAULT 0,
            gross_pay             REAL NOT NULL DEFAULT 0,
            federal_tax           REAL NOT NULL DEFAULT 0,
            state_tax             REAL NOT NULL DEFAULT 0,
            social_security       REAL NOT NULL DEFAULT 0,
            medicare              REAL NOT NULL DEFAULT 0,
            net_pay               REAL NOT NULL DEFAULT 0,
            pre_tax_deductions    REAL NOT NULL DEFAULT 0,
            post_tax_deductions   REAL NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_entry_deduction (
            id               SERIAL PRIMARY KEY,
            entry_id         INTEGER NOT NULL REFERENCES payroll_entry(id),
            deduction_name   TEXT NOT NULL DEFAULT '',
            is_pre_tax       INTEGER NOT NULL DEFAULT 0,
            amount           REAL NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS payroll_entry_run "
        "ON payroll_entry(run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS employee_deduction_people "
        "ON employee_deduction(people_id)"
    )


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


def get_payroll_monthly_gross(conn) -> list:
    """Return gross payroll by month for last 6 months."""
    rows = conn.execute(
        "SELECT TO_CHAR(DATE_TRUNC('month', run_date::date), 'Mon YYYY') AS month, "
        "COALESCE(SUM(pe.gross_pay), 0) AS gross "
        "FROM payroll_run pr "
        "JOIN payroll_entry pe ON pe.run_id = pr.id "
        "WHERE run_date >= (CURRENT_DATE - INTERVAL '6 months')::text "
        "GROUP BY DATE_TRUNC('month', run_date::date) "
        "ORDER BY DATE_TRUNC('month', run_date::date)"
    ).fetchall()
    return [dict(r) for r in rows]


def get_payroll_dept_breakdown(conn) -> list:
    """Return gross YTD payroll grouped by department."""
    year = str(_cur_year())
    rows = conn.execute(
        "SELECT COALESCE(d.dept_name, 'Unassigned') AS dept_name, "
        "COALESCE(SUM(pe.gross_pay), 0) AS gross "
        "FROM payroll_entry pe "
        "JOIN payroll_run pr ON pr.id = pe.run_id "
        "JOIN people p ON p.id = pe.people_id "
        "LEFT JOIN dept d ON d.dept_id = p.dept_id "
        "WHERE LEFT(pr.pay_period_start, 4) = %s "
        "GROUP BY d.dept_name ORDER BY gross DESC LIMIT 8",
        (year,),
    ).fetchall()
    return [dict(r) for r in rows]


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


def process_payroll(conn, pay_period_start: str, pay_period_end: str,
                    pay_frequency: str, federal_tax_rate: float,
                    state_tax_rate: float, created_by: str,
                    run_date: str | None = None) -> int:
    """Process a real payroll run for every employee with a pay rate on
    file: hourly employees are paid on actual clocked hours for the period
    (via time_clock_web_core's existing OT engine — the same regular/OT
    split shown on the OT report, so payroll and that report can never
    disagree); salaried employees are paid pay_rate / periods-per-year for
    the chosen frequency. Applies each employee's active deductions and
    withholds federal/state/SS/Medicare on the post-pre-tax-deduction
    taxable amount. Writes payroll_run + payroll_entry +
    payroll_entry_deduction rows and returns the new run id.

    *federal_tax_rate* / *state_tax_rate* are fractions (0.22, not 22).

    Raises ValueError if pay_frequency is invalid, the period is empty or
    backwards, no employee has a pay rate on file, or a run already exists
    for this exact period (re-running it would double-pay everyone).
    """
    if pay_frequency not in FREQUENCIES:
        raise ValueError(f"pay_frequency must be one of {FREQUENCIES}")
    if not pay_period_start or not pay_period_end:
        raise ValueError("Pay period start and end are required.")
    if pay_period_end < pay_period_start:
        raise ValueError("Pay period end must be on or after the start.")

    existing = conn.execute(
        "SELECT id FROM payroll_run WHERE pay_period_start=%s AND pay_period_end=%s",
        (pay_period_start, pay_period_end),
    ).fetchone()
    if existing:
        raise ValueError(
            f"A payroll run already exists for {pay_period_start} to "
            f"{pay_period_end} (run #{existing['id']}).")

    from .time_clock_web_core import get_ot_report_all

    pay_rows = conn.execute("""
        SELECT ep.people_id, ep.pay_type, ep.pay_rate
        FROM employee_pay ep
        JOIN people p ON p.id = ep.people_id
        WHERE COALESCE(p.employment_status, '') != 'terminated'
    """).fetchall()
    if not pay_rows:
        raise ValueError("No employees have a pay rate on file.")

    hours_by_person = {
        r['people_id']: r
        for r in get_ot_report_all(conn, date_from=pay_period_start,
                                   date_to=pay_period_end)
    }

    run_row = conn.execute(
        "INSERT INTO payroll_run "
        "(pay_period_start, pay_period_end, run_date, pay_frequency, "
        " federal_tax_rate, state_tax_rate, status, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,'processed',%s) RETURNING id",
        (pay_period_start, pay_period_end, run_date or _today(),
         pay_frequency, float(federal_tax_rate), float(state_tax_rate),
         created_by),
    ).fetchone()
    run_id = run_row['id']

    for pr in pay_rows:
        pid = pr['people_id']
        pay_type = pr['pay_type'] if pr['pay_type'] in PAY_TYPES else 'hourly'
        pay_rate = float(pr['pay_rate'] or 0)

        if pay_type == 'hourly':
            hrs = hours_by_person.get(pid)
            total_hrs = float(hrs['total_hours']) if hrs else 0.0
            ot_hrs = float(hrs['ot_hours']) if hrs else 0.0
            reg_hrs = max(0.0, total_hrs - ot_hrs)
            gross = round(pay_rate * reg_hrs + pay_rate * 1.5 * ot_hrs, 2)
        else:
            reg_hrs = ot_hrs = 0.0
            gross = round(pay_rate / FREQ_DIVISORS[pay_frequency], 2)

        emp_deds = [
            d for d in list_employee_deductions(conn, people_id=pid)
            if d.get('is_active')
        ]
        pre_total = 0.0
        post_total = 0.0
        ded_items = []  # [(name, is_pre_tax, amount)]
        for d in emp_deds:
            amt = (round(gross * (float(d['amount']) / 100.0), 2)
                   if d['calc_method'] == 'percent' else float(d['amount']))
            ded_items.append((d['ded_name'], 1 if d['is_pre_tax'] else 0, amt))
            if d['is_pre_tax']:
                pre_total += amt
            else:
                post_total += amt
        pre_total = round(pre_total, 2)
        post_total = round(post_total, 2)

        taxable = max(0.0, gross - pre_total)
        fed = round(taxable * float(federal_tax_rate), 2)
        state_tax = round(taxable * float(state_tax_rate), 2)
        ss = round(taxable * SS_RATE, 2)
        med = round(taxable * MEDICARE_RATE, 2)
        net = round(max(0.0, taxable - fed - state_tax - ss - med - post_total), 2)

        entry_row = conn.execute(
            "INSERT INTO payroll_entry "
            "(run_id, people_id, regular_hours, overtime_hours, "
            " gross_pay, federal_tax, state_tax, social_security, medicare, "
            " net_pay, pre_tax_deductions, post_tax_deductions) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (run_id, pid, reg_hrs, ot_hrs, gross, fed, state_tax,
             ss, med, net, pre_total, post_total),
        ).fetchone()
        entry_id = entry_row['id']

        for ded_name, is_pre_tax, amt in ded_items:
            conn.execute(
                "INSERT INTO payroll_entry_deduction "
                "(entry_id, deduction_name, is_pre_tax, amount) "
                "VALUES (%s,%s,%s,%s)",
                (entry_id, ded_name, is_pre_tax, amt),
            )

    return run_id


# ---------------------------------------------------------------------------
# Pay Stubs
# ---------------------------------------------------------------------------

def list_pay_stubs_for_employee(conn, people_id: int) -> list[dict]:
    """One employee's own stub history across every run (Employee
    Self-Service, P2-G) — list_run_employees is scoped the other way
    (all employees in one run), so this is the missing per-employee view."""
    rows = conn.execute(
        "SELECT pe.id AS entry_id, pe.run_id, pe.gross_pay, pe.net_pay, "
        "pe.regular_hours, pe.overtime_hours, "
        "pr.pay_period_start, pr.pay_period_end, pr.run_date, pr.status "
        "FROM payroll_entry pe "
        "JOIN payroll_run pr ON pr.id = pe.run_id "
        "WHERE pe.people_id = %s "
        "ORDER BY pr.run_date DESC",
        (people_id,),
    ).fetchall()
    return [dict(r) for r in rows]


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
