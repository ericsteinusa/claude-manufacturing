# Working in this repo

PyQt6 desktop app over a Django/Postgres backend (`db_pg.get_db_connection`),
plus a Django web UI that renders the same menus (see *Web UI* below).
Notes below are the non-obvious things that have bitten past changes.

## Directory structure

`manufacturing/` is organized into department subpackages plus a shared root:

```
manufacturing/
  ├── accounting/        Accounting, A/P, A/R, General Ledger
  ├── customer_service/  CS calls, escalations, satisfaction, staff
  ├── customers/         Customer & supplier master files, credit
  ├── engineering/       Design, specs, reviews, reports
  ├── finance/           Audit, bank reconciliation, budget, tax
  ├── it/                Help desk, tasks, technician views
  ├── legal/             Contracts, compliance, risk management
  ├── maintenance/       Equipment, PM schedules, work orders
  ├── marketing/         Campaigns, leads, analytics
  ├── payroll/           Payroll processing
  ├── personnel/         Employee directory, dept/sub-dept, HR
  ├── production/        BOM, MRP, work orders, inventory, warehouse
  ├── purchasing/        Purchase orders, menus
  ├── quality/           QA lab, NCR, CAPA, audits
  ├── reports/           Dashboard and KPI reports
  ├── sales/             Sales orders, quotes, targets
  ├── time_clock/        Clock in/out, time-off, TK login
  │
  ├── *_core.py          Qt-free business logic (stay at root — imported by
  │                      views.py, seeds, and cross-dept callers)
  ├── accounts.py        Cross-cutting user/session helpers
  ├── dept_menu_widget.py Shared Qt widget used by all dept main menus
  ├── purchase_requisitions.py  Used by 4+ non-purchasing departments
  ├── menus.py / views.py / urls.py  Django routing
  ├── db_pg.py / schema.py / gl_utils.py  DB & shared utilities
  ├── qt_theme.py / button_nav.py / launch_utils.py  Qt helpers
  ├── seed_sample_*.py   Dev-DB seeders
  └── templates/         Django HTML templates
```

**Import conventions for code in a subpackage:**
- Root module: `from ..db_pg import get_db_connection`
- Same subpackage: `from .purchase_orders_core import …`
- Cross-dept: `from ..customers.Credit_dept import CreditDeptWidget`

## Workflow
- Always use **feature branches + PRs**; never commit directly to `main`.
- A pre-push hook in `.githooks/pre-push` blocks direct pushes to `main`.
  Activate it once per clone: `git config core.hooksPath .githooks`

## Testing & CI
- CI runners **lack `libEGL`**, so `import PyQt6` fails there. Any module that
  imports PyQt6 therefore **cannot be imported in tests**.
- Keep unit-testable logic in **Qt-free `*_core.py` modules**, and have the GUI
  modules import/re-export from them. Examples: `bom_core.py` (cycle guard,
  `explode_quantity`) and `mrp_core.py` (`compute_levels`, `plan_orders`,
  `next_sequence_number`). Tests import the `*_core` modules only.
- All `*_core.py` files live at the **package root** (`manufacturing/`), not
  inside subpackages, because `views.py` and seeds import them directly and
  several are shared across departments.
- Run the GUI/integration checks locally headless with
  `QT_QPA_PLATFORM=offscreen`; widgets can be driven and captured via
  `QWidget.grab().save(path)`.
- **Windows offscreen fonts:** pip-installed PyQt6 ships no fonts, so
  offscreen text renders as boxes. Fix once with `python setup_qt_fonts.py`
  (copies Arial/Verdana/Tahoma/Courier from `C:\Windows\Fonts` into the
  PyQt6 Qt6 fonts dir). Linux uses system fontconfig and needs no fix.

## Web UI (Django) & menu routing
- The same department menu tree (`menus.MENU_TREE`) is also served as a web app
  (`python manage.py runserver`). A menu leaf whose target is a **subdir-prefixed
  filename string** (e.g. `'production/work_orders.py'`) is, by default,
  **launched as a desktop Qt subprocess on the server** by `views.run_script`
  (the `/run/<dept>/<path>/` links) — so clicking it in a browser renders
  **nothing** (and fails headless: no `libEGL`). Most leaves are still
  desktop-only. `run_script` converts the path to a dotted module name
  (`production/work_orders.py` → `manufacturing.production.work_orders`).
- To serve a leaf as a **real web page** instead, add
  `(dept, leaf_key) -> url` to **`views.WEB_LEAF_URLS`**; `generic_menu` then
  emits that URL in place of the `/run/...` launcher link. No change to the
  `menus.py` tree is needed. Worked example: the purchase-order pages
  (`/po/...`, `views.po_*`, `purchase_orders_core.py`) route all four
  Purchasing → Purchase Orders leaves this way.
- Web views run where `import PyQt6` fails, so they must import the Qt-free
  `*_core.py` modules only (same rule as tests — see above).
- **Access control** is enforced via decorators in `auth_decorators.py`:
  - `@login_required` — redirect to `'home'` if no active session.
  - `@dept_required(dept_keys, *, role_keys=None, write_redirect=None, deny_redirect='dashboard')`
    — allow logged-in users whose `user_dept_key` matches (or whose role is in
    `role_keys`); full-access roles (President, VP) always bypass. Pass
    `write_redirect` to also block `READ_ONLY_ROLES` (Auditor) on mutating views.
  - `@role_required(role_keys, *, deny_redirect='dashboard')` — allow only
    users whose `user_role` is in `role_keys` (no dept check).
  - Session keys set at login: `user_email`, `user_role`, `user_dept_key`,
    `user_full_access`, `user_dept_name`, `user_is_manager`.

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
- Purchase orders for the web PO pages (every status + a partial receipt):
  `python -m manufacturing.seed_sample_pos` (tagged `po_number` prefix
  `SMPL-PO-`; line items use the `bin='SAMPLE'` products, so run that seed
  first to link them).
- Work orders (every status + materials):
  `python -m manufacturing.seed_sample_wos` (tagged `wo_number` prefix
  `SMPL-WO-`; materials use the `bin='SAMPLE'` products, so run that seed
  first to link them).
- Inventory alerts (drives 3 sample products below reorder point):
  `python -m manufacturing.seed_sample_alerts` (updates `amount` on Rim,
  Tire, Inner Tube; requires `seed_sample_products` first). Supports
  `--remove` to restore original amounts.
- IT department (help desk tickets, tasks, assets, technicians):
  `python -m manufacturing.seed_sample_it` (tagged `SMPL-IT-`).
- Maintenance (mechanics, equipment, work orders, PM schedules, inspections):
  `python -m manufacturing.seed_sample_maintenance` (tagged `SMPL-MAINT-`).
- Quality (NCRs, CAPAs, audits, supplier quality, inspections):
  `python -m manufacturing.seed_sample_quality` (tagged `SMPL-QA-`).
- Engineering (projects, tasks, ECRs/design reviews, standards):
  `python -m manufacturing.seed_sample_engineering` (tagged `SMPL-ENG-`).
- Sales (quotes, targets, leads, contracts, forecasts, territories, commissions):
  `python -m manufacturing.seed_sample_sales` (tagged `SMPL-SALES-`).
- Marketing (campaigns, leads, content, ads, research):
  `python -m manufacturing.seed_sample_marketing` (tagged `SMPL-MKT-`).
- Accounting (GL accounts/chart of accounts, AP invoices+payments, AR invoices+payments, GL journals):
  `python -m manufacturing.seed_sample_accounting` (tagged `SMPL-ACCT-`; AR invoices linked to first customer in `customer` table).
- Customer Service (tickets, improvement plans, returns, KB articles, surveys):
  `python -m manufacturing.seed_sample_cs` (tagged `SMPL-CS-`).
- Finance (budgets+lines, audit schedules+findings, bank accounts+statements, tax filings):
  `python -m manufacturing.seed_sample_finance` (tagged `SMPL-FIN-`).
- Legal (contracts, compliance items, litigation cases):
  `python -m manufacturing.seed_sample_legal` (tagged `SMPL-LEGAL-`).
- Personnel (job titles for all 46 sample employees, 4 weeks of time-clock entries for hourly staff):
  `python -m manufacturing.seed_sample_personnel` (tagged `SMPL-PERS-`; adds `created_by` column
  to `position` and `time_clock` via `ALTER TABLE … ADD COLUMN IF NOT EXISTS`).
- Payroll (deduction types, pay rates, employee deductions, 3 historical bi-weekly payroll runs
  with entries and entry-level deductions for 12 sample employees):
  `python -m manufacturing.seed_sample_payroll` (tagged `SMPL-PAY-`; run
  `seed_sample_personnel` first so time-clock data exists for the current period).
- All seeds are idempotent and support `--reset` / `--remove`.
