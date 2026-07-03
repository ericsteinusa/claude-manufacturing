---
name: run-tests
description: Run the pytest test suite. Use when asked to run tests, check if tests pass, or verify changes don't break anything.
---

## Run

```bash
/c/tester/virt/Scripts/python.exe -m pytest tests/ -v
```

All 1606 tests should pass in under a second.

## What the tests cover

All tests are Qt-free — they import only `*_core.py` modules and use
fake DB connections, so no display or live database is needed.

| File | What it pins |
|---|---|
| `test_accounting_core.py` | GL accounts, AP/AR invoices+payments, journals, trial balance, income statement/balance sheet |
| `test_approval_core.py` | PO approval thresholds, request/approve/reject workflow, role checks |
| `test_approval_workflow_core.py` | Approval rule CRUD, `submit_for_approval`, `decide_step`, escalation |
| `test_audit_core.py` | Audit trigger SQL, `set_audit_user`, `get_recent`/`get_history` |
| `test_auth_decorators.py` | `login_required`/`dept_required`/`role_required` access control |
| `test_bom.py` | BOM cycle guard, `explode_quantity` |
| `test_bom_web_core.py` | Web BOM editor: product/BOM CRUD, cycle guards, `explode_bom` |
| `test_contacts_core.py` | Customer/supplier label formatting, CRUD, order history |
| `test_costing_core.py` | GL account map, `roll_standard_cost`, WO actual cost/variance, GL posting |
| `test_cs_calls_core.py` | Customer label formatting, ID parsing |
| `test_cs_web_core.py` | Web CS tickets: filters, escalations, summary stats, improvement plans |
| `test_db_pg_adapt.py` | SQL dialect adaptation (`_adapt`) |
| `test_engineering_core.py` | Eng projects/tasks/ECRs CRUD, numbering, dashboard |
| `test_finance_core.py` | Finance dashboard (AP/AR summary, recent journals) |
| `test_inventory_core.py` | Inventory transactions, stock levels, alert thresholds |
| `test_it_core.py` | IT dashboard, ticket/asset CRUD, numbering |
| `test_launch_utils.py` | `launch()` helper |
| `test_legal_core.py` | Legal dashboard, contracts/compliance/litigation CRUD |
| `test_log_utils.py` | Logger initialisation |
| `test_lot_core.py` | Lot/serial tracking: numbering, status transitions, expiry alerts, genealogy |
| `test_maintenance_core.py` | Maintenance dashboard, WO/schedule/inspection/downtime/part/mechanic CRUD |
| `test_marketing_core.py` | Marketing dashboard, campaign/lead/content CRUD |
| `test_menu_dept_routing.py` | Department → menu script routing |
| `test_mrp.py` | MRP level computation, `plan_orders`, `next_sequence_number` |
| `test_mrp_web_core.py` | Web MRP: demand calc, `run_mrp`, `explode_to_wo`, `release_plan` |
| `test_notify_core.py` | Approval email notifications (requested/decided) |
| `test_payroll_core.py` | Pay rates, deduction types, payroll runs, pay stubs, YTD |
| `test_period_locking_core.py` | Period lock/reopen, admin role checks, month labeling |
| `test_personnel_core.py` | Employee CRUD, time-off requests, dept/sub loading |
| `test_personnel_dashboard_core.py` | Personnel dashboard (headcount, by-dept, time-off, recent hires) |
| `test_phase3_accounting.py` | AR aging, DSO/DPO, dunning letters, budget vs actual, bank reconciliation, cost centers |
| `test_phase4.py` | API tokens, rate limiting, TOTP 2FA, approval workflow, period-lock trigger SQL |
| `test_phase5_reports.py` | Financial/production/inventory dashboards, CSV/Excel export, daily digest |
| `test_phase6.py` | SPC control charts/Cpk, equipment hierarchy, MTBF, PM alerts |
| `test_production_core.py` | Production dashboard (WO/inventory counts, recent WOs) |
| `test_purchase_orders_core.py` | PO filter assembly, normalisation, status transitions |
| `test_purchase_requisitions_core.py` | Requisition authorization rules |
| `test_purchasing_core.py` | Purchasing dashboard (PO counts, recent POs) |
| `test_quality_core.py` | QA dashboard, NCR/CAPA/audit/supplier/inspection/defect CRUD |
| `test_reports_core.py` | Reports KPI queries (PO, WO, inventory, CS) |
| `test_routing_core.py` | Workcenter/routing CRUD, WO operation lifecycle, labor cost, workcenter load |
| `test_sales_core.py` | Sales dashboard, quote/target CRUD |
| `test_sales_orders_core.py` | SO filter assembly, status transitions, numbering |
| `test_time_clock_core.py` | Clock in/out, hours computation, attendance |
| `test_time_clock_poller_core.py` | Time-clock device polling, punch import, sync log |
| `test_time_clock_web_core.py` | OT computation, OT reports, schedule summary |
| `test_work_orders_core.py` | WO filter assembly, status transitions, numbering |

## Interpreting results

- All tests should pass (`1606 passed`).
- A failure in a `*_core.py` test means broken pure logic — fix before merging.
- `ImportError` on a test file usually means a Qt module leaked into a
  `*_core.py` import chain (violates the Qt-free contract).

## Venv note

The venv is at `C:\tester\virt`. It was originally created on Linux;
`pyvenv.cfg` was updated to point at the Windows Python 3.14 install.
`pytest` and `bcrypt` are installed in `Lib\site-packages\`.
