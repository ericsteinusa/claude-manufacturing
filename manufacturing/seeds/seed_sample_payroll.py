"""seed_sample_payroll.py — sample Payroll data.

Covers: deduction types, pay rates, employee deductions, and three
historical bi-weekly payroll runs (with entries and entry-level deductions).
All rows are tagged with created_by='seed' for safe removal.

Usage::

    python -m manufacturing.seeds.seed_sample_payroll            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_payroll --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_payroll --remove    # remove only

Run seed_sample_personnel first so time_clock data exists for the
current period when you use the Payroll desktop module.
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-PAY-"
TODAY = date.today()

FED_RATE = 0.22
STATE_RATE = 0.05
SS_RATE = 0.062
MEDICARE_RATE = 0.0145


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    for tbl in ("payroll_deduction_type", "employee_pay", "employee_deduction"):
        conn.execute(
            f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''"
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Deduction types
# ---------------------------------------------------------------------------

# (name, category, is_pre_tax)
DEDUCTION_TYPES = [
    ("Health Insurance",  "Benefits",    1),
    ("Dental Insurance",  "Benefits",    1),
    ("Vision Insurance",  "Benefits",    1),
    ("401k Contribution", "Retirement",  1),
    ("Life Insurance",    "Benefits",    0),
]


def _seed_deduction_types(conn):
    for name, category, is_pre_tax in DEDUCTION_TYPES:
        if conn.execute(
            "SELECT 1 FROM payroll_deduction_type WHERE name=%s AND created_by='seed'",
            (name,)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO payroll_deduction_type (name, category, is_pre_tax, is_active, created_by)"
            " VALUES (%s,%s,%s,1,'seed')",
            (name, category, is_pre_tax),
        )
    conn.commit()


def _remove_deduction_types(conn):
    conn.execute("DELETE FROM payroll_deduction_type WHERE created_by='seed'")
    conn.commit()


# ---------------------------------------------------------------------------
# Employee pay rates
# ---------------------------------------------------------------------------

# (employee_id_num, pay_type, pay_rate, effective_date_offset)
EMPLOYEE_PAY = [
    (1001, "salary", 120000.00, -365),   # James Carter     — CEO
    (1002, "salary",  85000.00, -300),   # Mary Mitchell    — QA Manager
    (1009, "hourly",     20.00, -200),   # Elizabeth Edwards— Assembly
    (1010, "hourly",     24.00, -180),   # William Collins  — CNC Machinist
    (1011, "hourly",     19.50, -150),   # Barbara Stewart  — QA Inspector
    (1015, "hourly",     26.00, -400),   # Joseph Rogers    — AR Specialist
    (1016, "hourly",     32.00, -350),   # Jessica Reed     — IT Sysadmin
    (1017, "salary",  65000.00, -280),   # Sarah Morgan     — CS Rep
    (1021, "salary",  90000.00, -320),   # Daniel Bailey    — Mech. Engineer
    (1023, "hourly",     24.00, -290),   # Matthew Cooper   — Maintenance
    (1025, "salary",  70000.00, -260),   # Anthony Cox      — Account Exec.
    (1029, "hourly",     26.00, -230),   # Donald Peterson  — AP Specialist
]


def _seed_pay_rates(conn):
    for emp_id_num, pay_type, pay_rate, eff_off in EMPLOYEE_PAY:
        row = conn.execute(
            "SELECT id FROM people WHERE employee_id=%s", (emp_id_num,)
        ).fetchone()
        if not row:
            continue
        pid = row["id"]
        if conn.execute("SELECT 1 FROM employee_pay WHERE people_id=%s", (pid,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO employee_pay (people_id, pay_type, pay_rate, effective_date, created_by)"
            " VALUES (%s,%s,%s,%s,'seed')",
            (pid, pay_type, pay_rate, _d(eff_off)),
        )
    conn.commit()


def _remove_pay_rates(conn):
    conn.execute("DELETE FROM employee_pay WHERE created_by='seed'")
    conn.commit()


# ---------------------------------------------------------------------------
# Employee deductions
# ---------------------------------------------------------------------------

# (employee_id_num, deduction_type_name, calc_method, amount)
# calc_method: "flat" = dollar amount per period; "percent" = % of gross
EMPLOYEE_DEDUCTIONS = [
    # Salaried employees — full benefit package + 401k
    (1001, "Health Insurance",  "flat",    250.00),
    (1001, "Dental Insurance",  "flat",     45.00),
    (1001, "Vision Insurance",  "flat",     12.00),
    (1001, "401k Contribution", "percent",   6.00),
    (1001, "Life Insurance",    "flat",     25.00),

    (1002, "Health Insurance",  "flat",    250.00),
    (1002, "Dental Insurance",  "flat",     45.00),
    (1002, "401k Contribution", "percent",   5.00),
    (1002, "Life Insurance",    "flat",     15.00),

    (1017, "Health Insurance",  "flat",    250.00),
    (1017, "Dental Insurance",  "flat",     45.00),
    (1017, "401k Contribution", "percent",   4.00),

    (1021, "Health Insurance",  "flat",    250.00),
    (1021, "Dental Insurance",  "flat",     45.00),
    (1021, "Vision Insurance",  "flat",     12.00),
    (1021, "401k Contribution", "percent",   5.00),
    (1021, "Life Insurance",    "flat",     15.00),

    (1025, "Health Insurance",  "flat",    250.00),
    (1025, "401k Contribution", "percent",   3.00),

    # Hourly employees — health insurance (some with 401k)
    (1009, "Health Insurance",  "flat",    250.00),
    (1010, "Health Insurance",  "flat",    250.00),
    (1011, "Health Insurance",  "flat",    250.00),
    (1015, "Health Insurance",  "flat",    250.00),
    (1015, "401k Contribution", "percent",   3.00),
    (1016, "Health Insurance",  "flat",    250.00),
    (1016, "401k Contribution", "percent",   4.00),
    (1023, "Health Insurance",  "flat",    250.00),
    (1029, "Health Insurance",  "flat",    250.00),
]


def _seed_employee_deductions(conn):
    for emp_id_num, ded_name, calc_method, amount in EMPLOYEE_DEDUCTIONS:
        p_row = conn.execute(
            "SELECT id FROM people WHERE employee_id=%s", (emp_id_num,)
        ).fetchone()
        if not p_row:
            continue
        pid = p_row["id"]
        dt_row = conn.execute(
            "SELECT id FROM payroll_deduction_type WHERE name=%s AND created_by='seed'",
            (ded_name,)
        ).fetchone()
        if not dt_row:
            continue
        dtid = dt_row["id"]
        if conn.execute(
            "SELECT 1 FROM employee_deduction"
            " WHERE people_id=%s AND deduction_type_id=%s AND created_by='seed'",
            (pid, dtid)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO employee_deduction"
            " (people_id, deduction_type_id, calc_method, amount, is_active, created_by)"
            " VALUES (%s,%s,%s,%s,1,'seed')",
            (pid, dtid, calc_method, amount),
        )
    conn.commit()


def _remove_employee_deductions(conn):
    conn.execute("DELETE FROM employee_deduction WHERE created_by='seed'")
    conn.commit()


# ---------------------------------------------------------------------------
# Payroll runs
# ---------------------------------------------------------------------------

# Three bi-weekly historical runs: (period_start_offset, period_end_offset)
RUNS = [
    (-56, -43),   # ~8 weeks ago
    (-42, -29),   # ~6 weeks ago
    (-28, -15),   # ~4 weeks ago
]

# Overtime hours by (run_index, employee_id_num); default = 0
OVERTIME = {
    (1, 1010): 5.0,
    (1, 1015): 3.0,
    (2, 1023): 4.0,
}


def _compute_entry(pay_type, pay_rate, reg_hrs, ot_hrs, emp_deds):
    """Return (gross, fed, state, ss, med, net, pre_deds, post_deds, items).

    items = [(ded_name, is_pre_tax, computed_amount)]
    """
    if pay_type == "hourly":
        gross = round(pay_rate * reg_hrs + pay_rate * 1.5 * ot_hrs, 2)
    else:
        gross = round(pay_rate / 26.0, 2)

    pre_total = 0.0
    post_total = 0.0
    items = []
    for ded_name, is_pre_tax, calc_method, amount in emp_deds:
        amt = round(gross * (amount / 100.0), 2) if calc_method == "percent" else amount
        items.append((ded_name, is_pre_tax, amt))
        if is_pre_tax:
            pre_total += amt
        else:
            post_total += amt

    pre_total = round(pre_total, 2)
    post_total = round(post_total, 2)
    taxable = max(0.0, gross - pre_total)
    fed = round(taxable * FED_RATE, 2)
    state_tax = round(taxable * STATE_RATE, 2)
    ss = round(taxable * SS_RATE, 2)
    med = round(taxable * MEDICARE_RATE, 2)
    net = round(max(0.0, taxable - fed - state_tax - ss - med - post_total), 2)
    return gross, fed, state_tax, ss, med, net, pre_total, post_total, items


def _seed_payroll_runs(conn):
    # Build pay map: people_id -> {pay_type, pay_rate, emp_id_num}
    pay_map = {}
    for emp_id_num, pay_type, pay_rate, _ in EMPLOYEE_PAY:
        row = conn.execute("SELECT id FROM people WHERE employee_id=%s", (emp_id_num,)).fetchone()
        if not row:
            continue
        pay_map[row["id"]] = {"pay_type": pay_type, "pay_rate": pay_rate, "emp_id_num": emp_id_num}

    # Build deduction map: people_id -> [(name, is_pre_tax, calc_method, amount)]
    ded_map = {}
    for emp_id_num, ded_name, calc_method, amount in EMPLOYEE_DEDUCTIONS:
        p_row = conn.execute("SELECT id FROM people WHERE employee_id=%s", (emp_id_num,)).fetchone()
        if not p_row:
            continue
        pid = p_row["id"]
        dt_row = conn.execute(
            "SELECT id, is_pre_tax FROM payroll_deduction_type"
            " WHERE name=%s AND created_by='seed'",
            (ded_name,)
        ).fetchone()
        if not dt_row:
            continue
        ded_map.setdefault(pid, []).append(
            (ded_name, dt_row["is_pre_tax"], calc_method, amount)
        )

    for run_idx, (start_off, end_off) in enumerate(RUNS):
        start = _d(start_off)
        end = _d(end_off)
        if conn.execute(
            "SELECT 1 FROM payroll_run"
            " WHERE pay_period_start=%s AND pay_period_end=%s AND created_by='seed'",
            (start, end)
        ).fetchone():
            continue

        run_row = conn.execute(
            "INSERT INTO payroll_run"
            " (pay_period_start, pay_period_end, run_date, pay_frequency,"
            "  federal_tax_rate, state_tax_rate, status, created_by)"
            " VALUES (%s,%s,%s,'Bi-Weekly',%s,%s,'processed','seed') RETURNING id",
            (start, end, end, FED_RATE, STATE_RATE),
        ).fetchone()
        run_id = run_row["id"]

        for pid, info in pay_map.items():
            pay_type = info["pay_type"]
            pay_rate = info["pay_rate"]
            emp_id_num = info["emp_id_num"]

            if pay_type == "hourly":
                reg_hrs = 80.0
                ot_hrs = float(OVERTIME.get((run_idx, emp_id_num), 0.0))
            else:
                reg_hrs = 0.0
                ot_hrs = 0.0

            gross, fed, state_tax, ss, med, net, pre_deds, post_deds, items = _compute_entry(
                pay_type, pay_rate, reg_hrs, ot_hrs, ded_map.get(pid, [])
            )

            entry_row = conn.execute(
                "INSERT INTO payroll_entry"
                " (run_id, people_id, regular_hours, overtime_hours,"
                "  gross_pay, federal_tax, state_tax, social_security, medicare,"
                "  net_pay, pre_tax_deductions, post_tax_deductions)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (run_id, pid, reg_hrs, ot_hrs, gross, fed, state_tax,
                 ss, med, net, pre_deds, post_deds),
            ).fetchone()
            entry_id = entry_row["id"]

            for ded_name, is_pre_tax, amt in items:
                conn.execute(
                    "INSERT INTO payroll_entry_deduction"
                    " (entry_id, deduction_name, is_pre_tax, amount)"
                    " VALUES (%s,%s,%s,%s)",
                    (entry_id, ded_name, is_pre_tax, amt),
                )

        conn.commit()


def _remove_payroll_runs(conn):
    run_ids = [
        r["id"] for r in conn.execute(
            "SELECT id FROM payroll_run WHERE created_by='seed'"
        ).fetchall()
    ]
    if run_ids:
        ph = ",".join(["%s"] * len(run_ids))
        conn.execute(f"DELETE FROM payroll_entry WHERE run_id IN ({ph})", tuple(run_ids))
        conn.execute(f"DELETE FROM payroll_run WHERE id IN ({ph})", tuple(run_ids))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_deduction_types(conn)
    _seed_pay_rates(conn)
    _seed_employee_deductions(conn)
    _seed_payroll_runs(conn)
    print("Payroll sample data seeded.")


def remove(conn):
    _remove_payroll_runs(conn)
    _remove_employee_deductions(conn)
    _remove_pay_rates(conn)
    _remove_deduction_types(conn)
    print("Payroll sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Payroll sample data")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--reset",  action="store_true", help="Remove then re-add")
    grp.add_argument("--remove", action="store_true", help="Remove only")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.remove:
            remove(conn)
        elif args.reset:
            remove(conn)
            seed(conn)
        else:
            seed(conn)
    finally:
        conn.close()


