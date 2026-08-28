# Working in this repo

Django app over a Postgres backend (`db_pg.get_db_connection`). `python
manage.py runserver` is the only way to run it (see *Web UI* below). Notes
below are the non-obvious things that have bitten past changes.

## Directory structure

`manufacturing/` has one department-named subpackage per business area
(`accounting/`, `customer_service/`, `customers/`, `engineering/`,
`finance/`, `it/`, `legal/`, `maintenance/`, `marketing/`, `payroll/`,
`personnel/`, `production/`, `purchasing/`, `quality/`, `reports/`,
`sales/`, `time_clock/`) — but each is now an **empty placeholder**: just
`__init__.py`, nothing else. They used to hold that department's PyQt6
desktop screens; those were deleted when the desktop app was retired
(PR #397) and its stragglers cleaned up afterward. Nothing currently
repopulates them — nothing to update there when adding a feature.

All real code lives at the package root (`*_core.py`, routing, utilities)
plus one large `views/` subpackage:

```
manufacturing/
  ├── accounting/ … time_clock/   17 empty department placeholders
  │                                (__init__.py only — see above)
  │
  ├── management/        Django management commands (e.g. send_daily_digest)
  ├── migrations/        Django migrations (empty besides __init__.py — this
  │                      app manages its schema via CREATE TABLE IF NOT EXISTS
  │                      in *_core.py, not the Django ORM)
  ├── seeds/             Dev-DB seeders (python -m manufacturing.seeds.seed_sample_*)
  ├── views/             Django HTTP handlers — __init__.py (core navigation +
  │                      re-exports) plus 60+ domain-specific submodules, one
  │                      per feature area, e.g. _quality.py, _maintenance.py,
  │                      _payroll.py, _it.py, _legal.py, _marketing.py, _wms.py
  │
  ├── *_core.py          Business logic (~85 modules, stay at root — imported
  │                      by views/, seeds/, and cross-dept callers, e.g.
  │                      purchase_requisitions_core.py by 4+ departments)
  ├── accounts.py        Cross-cutting user/session helpers
  ├── menus.py / urls.py Django routing
  ├── db_pg.py / schema.py / gl_utils.py  DB & shared utilities
  └── templates/         Django HTML templates (flat directory, ~430 files —
                         not nested per department)
```

**Import conventions:**
- From a `views/` submodule to a root module: `from ..db_pg import get_db_connection`
- Cross-dept sharing happens via those root `*_core.py` modules — `views/`
  imports them directly, e.g. `from ..purchase_requisitions_core import …`
  (see "Testing & CI" below).

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
  - Per-endpoint API rate limiting (distinct from the login-attempt lockout
    above — this throttles *all* requests, not just failed logins):
    `record_api_request`, `is_api_rate_limited`, `purge_old_api_requests`,
    logged in `api_request_log`. Applied automatically inside
    `@api_required` to every endpoint it decorates, keyed on
    `(people_id, endpoint path)`; default `API_RATE_LIMIT_MAX_REQUESTS=120`
    per `API_RATE_LIMIT_WINDOW_SECONDS=60`, returns `429` once exceeded.
  - TOTP two-factor auth: `generate_totp_secret`, `verify_totp_code`,
    `set_totp_secret`, `get_totp_secret`, `disable_totp`, `verify_totp_for_user`
    — fully implemented but currently **dead code**; `api_login` only does
    bcrypt + rate limiting, no route wires TOTP in yet.
- `manufacturing/api_decorators.py` — `api_ok(data)`, `api_err(msg, status)`, `@api_required`
  decorator (checks `Authorization: Bearer <token>`, enforces the per-endpoint rate limit
  above, injects `request.api_user` dict).
- `manufacturing/api_openapi_core.py` — hand-curated OpenAPI 3.0 spec (`build_openapi_spec()`,
  a plain `ENDPOINTS` list kept in sync with `urls.py`/`api_views.py`'s `@require_http_methods`
  decorators, not introspected). Served as JSON at `/api/v1/openapi.json` and as interactive
  Swagger UI at `/api/docs/` (`views/_api_docs.py`, both unauthenticated — a third-party
  integrator needs to read the docs before they have a token).
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

**Offline support (`mobile/src/offline/`)** — closes COMPETITIVE_GAP_ANALYSIS.md §6.10,
deliberately partial rather than a full offline-first rewrite of every screen:
`cache.ts`'s `fetchWithOfflineCache()` wraps a GET call, caching the response to
`AsyncStorage` on success and falling back to the last cached value (marked stale)
if the network call fails; `queue.ts`'s `enqueueMutation()`/`flushQueue()` persist a
mutating call (method/url/body) to replay in order once connectivity returns, flushed
automatically by a global `NetInfo` listener in `app/_layout.tsx` the instant the
device reconnects — not tied to whichever screen happens to be focused at that
moment. `netStatus.ts`'s `useIsOnline()` hook and the shared `OfflineBanner`
component surface "showing cached data" / "N actions waiting to sync" to the user
rather than failing silently. **Wired into exactly two screens so far**: Time Clock
(full read-cache + write-queue — clock in/out are the canonical "plant-floor worker
with no signal" case) and Work Orders' list view (read-cache only; status changes
and assignment still require connectivity). The other 8 screens have no offline
support yet — extending this pattern to them is mechanical (wrap the existing `load()`
in `fetchWithOfflineCache`, wrap write actions in `enqueueMutation` where queuing
makes sense) but not yet done.
CI (`.github/workflows/mobile.yml`: `npm ci`, `tsc --noEmit`, `expo-doctor`,
`expo export --platform web`) can fail on PRs that never touch `mobile/` —
Expo periodically ships new SDK 57 patch releases, so the pinned patch
versions in `package.json`/`package-lock.json` drift behind what
`expo-doctor` currently expects (not a regression in that PR). Fix with
`npx expo install --fix`, then re-verify with `expo-doctor` and
`expo export --platform web` (done in PR #90, and again in PR #96).

## Localization (i18n)
Closes COMPETITIVE_GAP_ANALYSIS.md §6.11 — deliberately partial, matching this
project's other honestly-scoped gap closures (mobile offline support, RFID,
predictive maintenance) rather than claiming full coverage. Real, working
infrastructure: `django.middleware.locale.LocaleMiddleware` (positioned after
`SessionMiddleware`, before `CommonMiddleware`, per Django's own requirement),
`LANGUAGES`/`LOCALE_PATHS` in `manufacture/settings.py`, and a language
switcher (`<select>` posting to Django's built-in `set_language` view, wired
at `/i18n/` in `manufacture/urls.py`) in `base.html`'s top bar. Four languages
are wired up: English (default), Spanish, French, German
(`locale/{es,fr,de}/LC_MESSAGES/django.po`, all real translations, not
placeholder text — added after the original Spanish-only pass to close the
localization-breadth gap flagged in COMPETITIVE_GAP_ANALYSIS.md §9's
comparison against MRPeasy, which ships more languages than a single-language
pass would have). Translation coverage is the app's core navigation shell and
main landing page only — `base.html` (sidebar: all 11 section headers + all
~37 nav links; top bar: notifications, password, 2FA, logout), `home.html`
(the login page), and `dashboard.html` (the post-login main dashboard: KPI
labels, chart titles, the pending-PO-approvals banner using a real
`{% blocktrans count %}` plural, not a hardcoded English `|pluralize`) —
wrapped in `{% trans %}`/`{% blocktrans %}`. The main dashboard's department
grid button labels are the one exception — they're rendered from
`menus.py`-generated Python strings, not template-static text, so
translating them needs `gettext`/`gettext_lazy` calls in `menus.py` itself,
a different mechanism from the template-level `{% trans %}` used everywhere
else here; not done.

Run `python manage.py makemessages -l <code>` after adding a new `{% trans %}`
to catch the new string in every existing `.po` file (it merges via
`msgmerge`, preserving existing translations by matching on the English
source text) — but check the merge output for `#, fuzzy` markers before
trusting it: `msgmerge` will guess-match a new string against a similar
existing one (e.g. it once fuzzy-matched a new "PO Approvals" against the
existing translation of "Approval Rules") and leave that wrong guess in
place unless it's corrected by hand. Then `python manage.py compilemessages`
— the `.mo` binary Django actually loads at runtime isn't regenerated
automatically, and the dev server's autoreloader doesn't watch `.po`/`.mo`
files, so a manual restart is also needed after compiling. **The other
~450 department-specific content templates (forms, tables, detail pages)
remain untranslated** — extending this pattern to any of them, or adding an
already-wired language, is mechanical (`{% load i18n %}`, wrap each string,
add its line to each `.po` file, recompile) but is real, not-yet-done work
per template, stated plainly rather than implied as complete.

## Web UI (Django) & menu routing
- **Live-refresh via htmx** (COMPETITIVE_GAP_ANALYSIS.md §6.1 "Modern Frontend," deliberately
  partial — a full SPA rewrite isn't proportionate to this codebase's size). 5 of ~450 templates
  poll a small fragment view every 30s instead of doing a full page reload: `sf_tv.html`,
  `prod_dashboard.html`, `maint_dashboard.html`, `ai_insights_dashboard.html`, and `dashboard.html`
  (the main company dashboard). Pattern to copy for the next page: a `<div id="..."
  hx-get="/path/to/fragment/" hx-trigger="every 30s" hx-swap="innerHTML">{% include
  "the_fragment.html" %}</div>` wrapping whatever needs to stay live, a `{name}_fragment` view
  (same auth decorator as the parent view) that renders that same partial template standalone, and
  `<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"></script>` in the page's
  `extra_scripts` block — matches the Chart.js CDN-script precedent, not a new dependency-management
  pattern. Factor the shared data-fetching logic (SQL/computation) into one helper function called
  by both the full-page view and the fragment view — `dashboard.html`'s `_dashboard_kpis()` in
  `views/__init__.py` is the reference example — so the two can't silently drift out of sync.
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
- **A query that JOINs a table to show a display field must also select that
  table's id.** Code rendering `x_name`/`x_number` as a link or API reference
  back to the joined row needs the matching `x_id` in the same result, or
  callers get a name with nothing to link through — in the web UI that's a
  hardcoded `href="/so/{{ s.so_id }}/"` silently rendering as `/so//` (404,
  since the field is missing from the row dict) rather than an obvious error;
  in the API it's a JSON field a mobile client can't follow up on. Found
  missing in four places at once: `production_core.list_shipments` (`so_id`
  dropped — 404'd the Shipping list's SO# link), `work_orders_core.list_wos`/
  `get_wo` (`product_id` dropped), `api_views.api_req`/`api_req_pending`
  (`requester_id` dropped, unlike the `dept_id` alongside it in the same
  query), and `reports_core.inventory_alerts` (never selected `id` at all).
  Fixed in PR #94/#95 — when adding or touching a query that joins for a
  `_name`/`_number` display field, check its sibling `_id` is selected too.

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
`manufacture-autopull.ps1` only restarts the running server if the pull is a
clean fast-forward **and** `manage.py check` **and** the full `pytest tests/`
suite both pass on the newly-pulled commit — a diverged `--ff-only` pull or a
failing check/test leaves whatever was already running in place and just
logs to `manufacture-autopull.log`, so a broken push to `main` never takes
down what's live on the Windows box.

**A DHCP IP change on the Windows box breaks three unrelated things at
once**, seen in practice when its address moved from `192.168.4.46` to
`192.168.0.188`: (1) Windows Firewall silently drops inbound connections
(including ping) after the network is treated as "new," even with the
profile still set to Private — the fix is temporarily disabling the
firewall to confirm it's the cause, then re-enabling it with a proper
inbound rule for the port; (2) `manufacture/settings.py`'s `ALLOWED_HOSTS`
default (`['localhost', '127.0.0.1', '192.168.0.239']` — that last address
is the *Linux* box's own IP, hardcoded) doesn't include whatever the
Windows box's new address is, so requests 400 until `DJANGO_ALLOWED_HOSTS`
in that machine's `.env` is updated and the server restarted (env vars only
take effect on process restart, not on save); (3) a stale Postgres
`postgres`-user password in `.env` can surface at the exact same time by
pure coincidence (e.g. if the machine was reimaged/reset around when the
IP changed) — `psycopg2.OperationalError: ... FATAL: password
authentication failed` in the crashed autoreloader's traceback is that
specific failure, unrelated to the network issue, and needs `DB_PASSWORD`
in `.env` corrected separately. Diagnose in order: `ping` the new IP first
(rules firewall in/out), then a plain `curl`/browser hit to port 8000
(400 = ALLOWED_HOSTS, connection refused/timeout = server not actually
listening — check the crashed process's traceback for the real reason).

## Sample data (dev DB)

**On a fresh Postgres DB, run `python manage.py migrate` before anything
else** — this app's own tables are created ad hoc by the seed scripts below,
but Django's built-in tables (`django_session`, auth, admin, contenttypes)
still need the normal Django migration system. Skipping it doesn't surface
until first login, which 500s with `relation "django_session" does not
exist` (see "Windows deployment" below for the platform-specific version of
this note — it applies to any fresh DB, not just Windows).

Seed scripts live in `manufacturing/seeds/`. Use `python -m manufacturing.seeds.<name>`.

- People: `python -m manufacturing.seeds.seed_sample_data` (tagged `@example.com`).
- Products + BOMs + demand for BOM/MRP:
  `python -m manufacturing.seeds.seed_sample_products` (tagged `bin='SAMPLE'`).
- Purchase orders for the web PO pages (every status + a partial receipt):
  `python -m manufacturing.seeds.seed_sample_pos` (tagged `po_number` prefix
  `SMPL-PO-`; line items use the `bin='SAMPLE'` products, so run that seed
  first to link them). Each PO is attached to the first existing supplier;
  if none exists yet (i.e. run before `seed_sample_purchasing` below), a
  minimal fallback supplier is created instead of leaving `supplier_id`
  NULL, tagged `created_by='SMPL-PO-FALLBACK'`.
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
