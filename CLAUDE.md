# Working in this repo

Django app over a Postgres backend (`db_pg.get_db_connection`). `python
manage.py runserver` is the only way to run it (see *Web UI* below). Notes
below are the non-obvious things that have bitten past changes.

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
  ├── management/        Django management commands (e.g. send_daily_digest)
  ├── migrations/        Django migrations (empty besides __init__.py — this
  │                      app manages its schema via CREATE TABLE IF NOT EXISTS
  │                      in *_core.py, not the Django ORM)
  ├── seeds/             Dev-DB seeders (python -m manufacturing.seeds.seed_sample_*)
  ├── views/             Django HTTP handlers (package split by domain)
  │   ├── __init__.py    Core navigation + re-exports from sub-modules
  │   ├── _quality.py    QA views
  │   ├── _maintenance.py Maintenance views
  │   ├── _payroll.py    Payroll views
  │   ├── _it.py         IT views
  │   ├── _legal.py      Legal views
  │   └── _marketing.py  Marketing views
  │
  ├── *_core.py          Business logic (stay at root — imported by
  │                      views/, seeds/, and cross-dept callers, e.g.
  │                      purchase_requisitions_core.py by 4+ departments)
  ├── accounts.py        Cross-cutting user/session helpers
  ├── menus.py / urls.py Django routing
  ├── db_pg.py / schema.py / gl_utils.py  DB & shared utilities
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
- Keep unit-testable logic in **Qt-free `*_core.py` modules**, and have
  `views/` import/re-export from them. Examples: `bom_core.py` (cycle guard,
  `explode_quantity`) and `mrp_core.py` (`compute_levels`, `plan_orders`,
  `next_sequence_number`). Tests import the `*_core` modules only.
- All `*_core.py` files live at the **package root** (`manufacturing/`), not
  inside subpackages, because `views/` and seeds import them directly and
  several are shared across departments.

## Mobile REST API (`/api/v1/`)
A stateless JSON API consumed by the React Native app in `mobile/`. Has grown
substantially since it was first added (esp. in the "Phase 5–7" work) — keep
this section in sync when adding endpoints, it has gone stale before.
- `manufacturing/api_auth.py` — `api_token` table DDL, plus:
  - Tokens: `create_token`, `verify_token`, `refresh_token`, `revoke_token`,
    `revoke_all_tokens`. Tokens are UUID hex strings stored in
    `api_token(token, people_id, created_at, expires_at)`; `expires_at` backs
    `TOKEN_LIFETIME_HOURS` expiry checked in `verify_token`.
  - Login rate limiting: `record_login_attempt`, `is_rate_limited`,
    `purge_old_attempts`.
  - TOTP two-factor auth: `generate_totp_secret`, `verify_totp_code`,
    `set_totp_secret`, `get_totp_secret`, `disable_totp`, `verify_totp_for_user`
    — fully implemented but currently **dead code**; `api_login` only does
    bcrypt + rate limiting, no route wires TOTP in yet.
- `manufacturing/api_decorators.py` — `api_ok(data)`, `api_err(msg, status)`, `@api_required`
  decorator (checks `Authorization: Bearer <token>`, injects `request.api_user` dict).
- `manufacturing/api_views.py` — all view functions; `@csrf_exempt` throughout; reuses
  `reports_core`, `time_clock_core`, `work_orders_core`, `personnel_core`,
  `purchase_requisitions_core`, `approval_workflow_core`, `costing_core`,
  `inventory_core`, `lot_core`, `maintenance_core`, `quality_core`, `routing_core`,
  `cycle_count_core`, `document_control_core` (the last two back the polymorphic
  entity types in `api_workflow_decide`)
  — no PyQt6, safe in web context. No test coverage yet despite being Qt-free.
- Routes wired at `/api/v1/` in `manufacturing/urls.py`:
  - Auth: login/logout/refresh/profile.
  - Dashboards: main (4 KPIs) + financial/production/inventory.
  - Time clock (status/clock-in/clock-out/hours) + time-off.
  - Work orders: list/detail/status, operations (list/start/complete), cost (get/compute).
  - Requisitions: list/pending, add item, submit, decide.
  - Inventory: list, receive.
  - Quality: NCR list/detail.
  - Maintenance: work order list/detail/complete.
  - Approval workflow: pending steps, decide.
  - Lots/serials: list, detail, status, expiry alerts.
  - Workcenters/routing: list, product routing.
  - Costing: product cost/roll/history, GL accounts.
- **Auth**: `POST /api/v1/auth/login/` verifies against existing `passwd` table (bcrypt);
  returns a token. All other endpoints require `Authorization: Bearer <token>`.

## Mobile app (`mobile/`)
React Native (expo-router) companion app. Set `EXPO_PUBLIC_API_URL` in `.env.local`.
Installed Expo SDK is `^57.0.0` (`mobile/package.json`) — upgraded from `~54.0.0`
staged one major at a time (54→55→56→57) via `expo install`/`expo install --fix`
at each step, verified with `expo-doctor` and a full `expo export --platform web`
bundle build at each stage. `mobile/AGENTS.md` points at the matching v57 docs.
`babel-preset-expo` must stay an explicit `dependencies` entry in
`mobile/package.json` — it's only ever transitively available via `expo`'s own
`node_modules`, and relying on npm's hoisting for it is fragile: a
routine reinstall during this upgrade un-hoisted it and broke every build with
`Cannot find module 'babel-preset-expo'` until it was added explicitly.
Screens under `mobile/app/(tabs)/`: Dashboard (4 KPI cards: active WOs, open POs,
inventory alerts, CS open tickets), Time Clock (clock in/out + hours), Work Orders
(list + detail + status transitions), Requisitions (submit + manager approve/deny),
Approvals (pending approval-workflow steps, approve/reject), Inventory (stock levels
+ reorder alerts), Lots (lot list with qty/expiry), Maintenance (work order list +
detail + complete), Quality (NCR list + create + detail), Costing (product search +
standard cost/roll/history + routing steps, plus Workcenters/GL Accounts reference
lists — product search reuses `getInventory` from the Inventory screen's API client
rather than a dedicated product-list endpoint, since none exists). Plus `(auth)/login`.
To run: `cd mobile && npx expo start` → scan QR with Expo Go on phone.

## Web UI (Django) & menu routing
- **End-user documentation** for every department's pages, workflows, and the
  role/permission model lives in `docs/user-guide/` (Markdown source, plus a
  combined `Manufacturing System User Manual.docx` for distribution to
  non-technical staff). Keep it in sync when adding/moving a leaf in
  `WEB_LEAF_URLS` or changing access rules in `auth_decorators.py` — it has
  gone stale before (see the Mobile REST API section above for the pattern).
- The department menu tree (`menus.MENU_TREE`) is served entirely as web
  pages via `python manage.py runserver`. Every `(dept, leaf_key)` leaf
  resolves to a URL in `views.WEB_LEAF_URLS`; `generic_menu`
  (`views/__init__.py`) looks up that URL when rendering a menu — there is no
  other resolution path.
- To add a new leaf's web page, add its `(dept, leaf_key) -> url` mapping to
  `views.WEB_LEAF_URLS`. No change to the `menus.py` tree is needed. Worked
  example: the purchase-order pages (`/po/...`, `views.po_*`,
  `purchase_orders_core.py`) route all four Purchasing → Purchase Orders
  leaves this way.
- Views must import the Qt-free `*_core.py` modules only (same rule as
  tests — see above).
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
  `bom(product_id, component_id, qty_required, unit, notes)`; `ap_invoice.due_date`
  is **NOT NULL** live even though `accounting_core.create_ap_invoice`'s own
  signature treats it as optional (`due_date or None`) — every pre-existing
  caller happens to always supply a real date from a form field, so this only
  surfaced when `consignment_core.py` tried passing `None` for an
  auto-generated invoice. **Check `information_schema.columns` before assuming
  a column's type or nullability.**
- **Batch number generation.** The `_next_wo_num()` / `_next_req_num()` helpers
  compute the next `WO-<yr>-NNNN` / `REQ-<yr>-NNNN` via `COUNT(*)` on **their
  own fresh connection**. That collides when creating **several rows in one
  uncommitted transaction** (e.g. releasing an MRP plan with multiple make
  items) — the count can't see the just-inserted rows, so every one gets
  `...-0001`. For sequential ids in a multi-row transaction, generate on the
  **transaction's own connection** using **max numeric suffix + 1** (gap-safe),
  e.g. `mrp_core.next_sequence_number(existing, prefix)`.
- **AR/AP invoices and bank accounts carry no balance column.** `ar_invoice`
  and `ap_invoice` have no `received`/`paid` column — amounts collected/paid
  live in separate `ar_payment`/`ap_payment` tables (one row per payment,
  `invoice_id` FK), so outstanding balance requires
  `i.amount - COALESCE(SUM(p.amount), 0)` via a `LEFT JOIN`. Likewise
  `bank_account` has no balance column at all; the balance is
  `bank_statement.ending_balance` on that account's most recent statement.
  `accounting_core.get_dso`/`get_dpo` already do this join correctly — reuse
  that pattern rather than assuming a direct balance column (a past bug in
  `reports_core.financial_dashboard` did, and 500'd; fixed in PR #336).

## Windows deployment (`scripts/windows/`)
`manufacture-autopull.ps1` (polls `origin/main` and redeploys) and
`manufacture-run.ps1` (start/restart the dev server, tracked by port
listening rather than PID — see its own docstring) run this app on a
Windows box as a separate deployment from the Linux one, each against its
**own local Postgres** (`DB_HOST=localhost` in that machine's `.env`, not
shared). On a **fresh Postgres DB**, run `python manage.py migrate` before
anything else — this app's own tables are created ad hoc via the seed
scripts' `CREATE TABLE IF NOT EXISTS`, but Django's built-in tables
(`django_session`, auth, admin, contenttypes) still go through the normal
Django migration system. Skipping it doesn't surface until first login,
which 500s with `relation "django_session" does not exist`.

## Sample data (dev DB)

Seed scripts live in `manufacturing/seeds/`. Use `python -m manufacturing.seeds.<name>`.

- People: `python -m manufacturing.seeds.seed_sample_data` (tagged `@example.com`).
- Products + BOMs + demand for BOM/MRP:
  `python -m manufacturing.seeds.seed_sample_products` (tagged `bin='SAMPLE'`).
- Purchase orders for the web PO pages (every status + a partial receipt):
  `python -m manufacturing.seeds.seed_sample_pos` (tagged `po_number` prefix
  `SMPL-PO-`; line items use the `bin='SAMPLE'` products, so run that seed
  first to link them).
- Work orders (every status + materials):
  `python -m manufacturing.seeds.seed_sample_wos` (tagged `wo_number` prefix
  `SMPL-WO-`; materials use the `bin='SAMPLE'` products, so run that seed
  first to link them).
- Inventory alerts (drives 3 sample products below reorder point):
  `python -m manufacturing.seeds.seed_sample_alerts` (updates `amount` on Rim,
  Tire, Inner Tube; requires `seed_sample_products` first). Supports
  `--remove` to restore original amounts.
- IT department (help desk tickets, tasks, assets, technicians):
  `python -m manufacturing.seeds.seed_sample_it` (tagged `SMPL-IT-`).
- Maintenance (mechanics, equipment, work orders, PM schedules, inspections):
  `python -m manufacturing.seeds.seed_sample_maintenance` (tagged `SMPL-MAINT-`).
- Quality (NCRs, CAPAs, audits, supplier quality, inspections):
  `python -m manufacturing.seeds.seed_sample_quality` (tagged `SMPL-QA-`).
- Engineering (projects, tasks, ECRs/design reviews, standards):
  `python -m manufacturing.seeds.seed_sample_engineering` (tagged `SMPL-ENG-`).
- Sales (quotes, targets, leads, contracts, forecasts, territories, commissions):
  `python -m manufacturing.seeds.seed_sample_sales` (tagged `SMPL-SALES-`).
- Marketing (campaigns, leads, content, ads, research):
  `python -m manufacturing.seeds.seed_sample_marketing` (tagged `SMPL-MKT-`).
- Accounting (GL accounts/chart of accounts, AP invoices+payments, AR invoices+payments, GL journals):
  `python -m manufacturing.seeds.seed_sample_accounting` (tagged `SMPL-ACCT-`; AR invoices linked to first customer in `customer` table).
- Customer Service (tickets, improvement plans, returns, KB articles, surveys):
  `python -m manufacturing.seeds.seed_sample_cs` (tagged `SMPL-CS-`).
- Finance (budgets+lines, audit schedules+findings, bank accounts+statements, tax filings):
  `python -m manufacturing.seeds.seed_sample_finance` (tagged `SMPL-FIN-`).
- Legal (contracts, compliance items, litigation cases):
  `python -m manufacturing.seeds.seed_sample_legal` (tagged `SMPL-LEGAL-`).
- Personnel (job titles for all 46 sample employees, 4 weeks of time-clock entries for hourly staff):
  `python -m manufacturing.seeds.seed_sample_personnel` (tagged `SMPL-PERS-`; adds `created_by` column
  to `position` and `time_clock` via `ALTER TABLE … ADD COLUMN IF NOT EXISTS`).
- Payroll (deduction types, pay rates, employee deductions, 3 historical bi-weekly payroll runs
  with entries and entry-level deductions for 12 sample employees):
  `python -m manufacturing.seeds.seed_sample_payroll` (tagged `SMPL-PAY-`; run
  `seed_sample_personnel` first so time-clock data exists for the current period).
- Purchasing (8 supplier contacts + 7 purchase requisitions spanning every status with
  line items and approval history):
  `python -m manufacturing.seeds.seed_sample_purchasing` (suppliers tagged `created_by='SMPL-PURCH-'`;
  requisitions tagged `req_number` prefix `SMPL-REQ-`; run `seed_sample_data` first so
  department/people records exist).
- Customers and Credit (10 B2B customer records, credit accounts with varying limits and
  statuses, credit applications across pending/approved/denied, limit change history, and
  collection activities for hold/suspended accounts):
  `python -m manufacturing.seeds.seed_sample_customers` (tagged `created_by='SMPL-CUST-'`).
- Shipping (8 shipments spanning every status — pending, shipped, delivered, returned —
  with 2–4 bicycle-part line items each; `so_id` is NULL unless sales seed has been run):
  `python -m manufacturing.seeds.seed_sample_shipping` (tagged `created_by='SMPL-SHIP-'`;
  `ship_number` prefix `SMPL-SH-`).
- Receiving (8 receipts spanning every status — pending, partial, received, rejected —
  with 2–4 line items each; `po_id` is NULL with no FK constraint so no PO seed dependency):
  `python -m manufacturing.seeds.seed_sample_receiving` (tagged `rcv_number` prefix `SMPL-RCV-`).
- Operations — routing/costing/lot/approval-workflow data covering the routing_core,
  lot_core, costing_core and approval_workflow_core modules (workcenters, product
  routings + WO operations with shop-floor progress, raw-material/finished-good lots
  and serial numbers across every status, a GL account map + standard cost rolls +
  one WO actual-cost/variance record, and approval rules with real approval_step
  workflows against the sample requisitions — pending/escalated/dept-approved/
  rejected/fully-approved):
  `python -m manufacturing.seeds.seed_sample_operations` (tagged `created_by='SMPL-OPS-'`
  on workcenter/routing/lot/serial_number/cost_roll/wo_cost_actual, `notes='SMPL-OPS-'`
  on approval_rule; run `seed_sample_products` and `seed_sample_wos` first so products/
  WOs exist to attach routings and operations to, and `seed_sample_purchasing` first for
  approval_step demo data — otherwise only the approval rule config is seeded).
- All seeds are idempotent and support `--reset` / `--remove`.
