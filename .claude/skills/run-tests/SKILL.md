---
name: run-tests
description: Run the pytest test suite. Use when asked to run tests, check if tests pass, or verify changes don't break anything.
---

## Run

```bash
/c/tester/virt/Scripts/python.exe -m pytest tests/ -v
```

All 221 tests should pass in under a second.

## What the tests cover

All tests are Qt-free — they import only `*_core.py` modules and use
fake DB connections, so no display or live database is needed.

| File | What it pins |
|---|---|
| `test_bom.py` | BOM cycle guard, `explode_quantity` |
| `test_mrp.py` | MRP level computation, `plan_orders`, `next_sequence_number` |
| `test_purchase_orders_core.py` | PO filter assembly, normalisation, status transitions |
| `test_cs_calls_core.py` | Customer label formatting, ID parsing |
| `test_launch_utils.py` | `launch()` helper |
| `test_db_pg_adapt.py` | SQL dialect adaptation (`_adapt`) |
| `test_log_utils.py` | Logger initialisation |
| `test_menu_dept_routing.py` | Department → menu script routing |
| `test_reports_core.py` | Reports KPI queries (PO, WO, inventory, CS) |
| `test_personnel_core.py` | Employee CRUD, time-off requests, dept/sub loading |
| `test_sales_orders_core.py` | SO filter assembly, status transitions, numbering |
| `test_work_orders_core.py` | WO filter assembly, status transitions, numbering |
| `test_time_clock_core.py` | Clock in/out, hours computation, attendance |
| `test_purchase_requisitions_core.py` | Requisition authorization rules |
| `test_audit_core.py` | Audit trigger SQL, set_audit_user, get_recent/get_history |

## Interpreting results

- All tests should pass (`221 passed`).
- A failure in a `*_core.py` test means broken pure logic — fix before merging.
- `ImportError` on a test file usually means a Qt module leaked into a
  `*_core.py` import chain (violates the Qt-free contract).

## Venv note

The venv is at `C:\tester\virt`. It was originally created on Linux;
`pyvenv.cfg` was updated to point at the Windows Python 3.14 install.
`pytest` and `bcrypt` are installed in `Lib\site-packages\`.
