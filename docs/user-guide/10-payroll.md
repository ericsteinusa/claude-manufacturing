# Payroll

**Menu:** Payroll isn't its own top-level department in the main navigation —
you reach it from the **Accounting** or **Personnel** menu ("Payroll
Department").

**Who can access it:** Payroll, Accounting, and Finance staff.

## Dashboard (`/payroll/`)

Recent payroll runs, monthly gross-pay trend, department breakdown.

## Pay Rates (`/payroll/pay-rates/`)

Set an employee's pay type (hourly/salary) and rate with an effective date;
remove a pay-rate assignment.

## Deductions (`/payroll/deductions/`)

Create a deduction type (name, category, pre-tax flag); assign a deduction to
an employee (method flat/percent, amount, active flag, notes); remove an
assignment.

## Payroll History (`/payroll/history/`)

View a past payroll run's total gross/net and per-employee entries.
Exportable to CSV.

## Pay Stub (`/payroll/stubs/<entry_id>/`)

A single employee's stub for one run: gross pay, pre-tax and post-tax
deductions itemized, federal/state/Social Security/Medicare tax, and net
pay.

## Year-to-Date Report (`/payroll/ytd/`)

Year-to-date totals (hours, gross, deductions, taxes, net) per employee,
filterable by year and employee.

## Employee self-service

Every employee — regardless of department — can view their **own** pay
stubs and YTD summary through Employee Self-Service; see
[Getting Started](00-getting-started.md#employee-self-service-everyone-regardless-of-department).
