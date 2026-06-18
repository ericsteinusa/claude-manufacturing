---
name: run-tests
description: Run the pytest test suite. Use when asked to run tests, check if tests pass, or verify changes don't break anything.
---

## Interpreter

The project venv is `C:\tester\virt`. Tests need packages from two
site-packages trees inside it (Windows layout and a python3.12 subtree).
The Claude Code sandbox intercepts `python.exe` calls, so tests cannot be
launched directly via the Bash or PowerShell tools.

## Running the tests

Ask the user to paste this into the Claude Code prompt (the `!` prefix
runs it in their terminal session and the output lands in the conversation):

```
! cd C:\tester\manufacture && C:\tester\virt\Scripts\python.exe -m pytest tests/ -v
```

Wait for the output to appear in the conversation, then report results.

## What the tests cover

All tests are Qt-free — they import only `*_core.py` modules and use
fake DB connections, so no `QT_QPA_PLATFORM` or display is needed.

| File | What it pins |
|---|---|
| `test_bom.py` | BOM cycle guard, `explode_quantity` |
| `test_mrp.py` | MRP level computation, `plan_orders`, `next_sequence_number` |
| `test_purchase_orders_core.py` | PO filter assembly, normalisation, status transitions |
| `test_cs_calls_core.py` | Customer label formatting, ID parsing |
| `test_launch_utils.py` | `launch()` helper |
| `test_db_pg_adapt.py` | SQL dialect adaptation (`_adapt`) |

## Interpreting results

- All tests should pass (`x passed`).
- A failure in a `*_core.py` test means broken pure logic — fix before merging.
- `ImportError` on a test file usually means a Qt module leaked into a
  `*_core.py` import chain (violates the Qt-free contract).
