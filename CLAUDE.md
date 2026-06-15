# Working in this repo

PyQt6 desktop app over a Django/Postgres backend (`db_pg.get_db_connection`).
Notes below are the non-obvious things that have bitten past changes.

## Workflow
- Always use **feature branches + PRs**; never commit directly to `main`.

## Testing & CI
- CI runners **lack `libEGL`**, so `import PyQt6` fails there. Any module that
  imports PyQt6 therefore **cannot be imported in tests**.
- Keep unit-testable logic in **Qt-free `*_core.py` modules**, and have the GUI
  modules import/re-export from them. Examples: `bom_core.py` (cycle guard,
  `explode_quantity`) and `mrp_core.py` (`compute_levels`, `plan_orders`,
  `next_sequence_number`). Tests import the `*_core` modules only.
- Run the GUI/integration checks locally headless with
  `QT_QPA_PLATFORM=offscreen`; widgets can be driven and captured via
  `QWidget.grab().save(path)`.

## Database gotchas
- **Live schema can diverge from the `CREATE TABLE` DDL.** Modules use
  `CREATE TABLE IF NOT EXISTS`, so whichever statement ran first wins and the
  live columns may differ from the DDL string. Seen in practice:
  `product.supplier_id` is **integer** (not the TEXT the DDL declares) and
  `amount`/`reorder_point` are **real**; the `bom` table pre-existed as a flat
  `bom(product_id, component_id, qty_required, unit, notes)`. **Check
  `information_schema.columns` before assuming a column's type.**
- **Batch number generation.** The `_next_wo_num()` / `_next_req_num()` helpers
  compute the next `WO-<yr>-NNNN` / `REQ-<yr>-NNNN` via `COUNT(*)` on **their
  own fresh connection**. That collides when creating **several rows in one
  uncommitted transaction** (e.g. releasing an MRP plan with multiple make
  items) — the count can't see the just-inserted rows, so every one gets
  `...-0001`. For sequential ids in a multi-row transaction, generate on the
  **transaction's own connection** using **max numeric suffix + 1** (gap-safe),
  e.g. `mrp_core.next_sequence_number(existing, prefix)`.

## Sample data (dev DB)
- People: `python -m manufacturing.seed_sample_data` (tagged `@example.com`).
- Products + BOMs + demand for BOM/MRP:
  `python -m manufacturing.seed_sample_products` (tagged `bin='SAMPLE'`).
  Both seeds are idempotent and support `--reset` / `--remove`.
