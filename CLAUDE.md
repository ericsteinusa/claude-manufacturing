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
  - Dashboards: main (4 KPIs) + financial/production/inventory/sales/personnel/
    accounting/customer-service/engineering/customers/it/legal/marketing/payroll —
    the 17th and last department, closing COMPETITIVE_GAP_ANALYSIS.md §6.9's mobile
    coverage gap to full 17/17.
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
rather than a dedicated product-list endpoint, since none exists), Finance (cash
position, DSO/DPO, gross margin, AP due this week, AR aging buckets — reuses the
existing `/api/v1/dashboards/financial/` endpoint verbatim, no new backend work;
closes COMPETITIVE_GAP_ANALYSIS.md §6.9's Finance-department mobile gap), Sales
(open orders, order value, quotes won, target attainment, recent orders — backed
by a genuinely new `/api/v1/dashboards/sales/` endpoint and `reports_core
.sales_dashboard()`, since no sales API surface existed before this; closes §6.9's
Sales-department mobile gap), Personnel (headcount, by-department breakdown, time-off
pending/approved, recent hires — the underlying `personnel_core.get_personnel_dashboard()`
already existed and was already used by the web dashboard, so this only needed a new
`api_personnel_dashboard` view + `/api/v1/dashboards/personnel/` route, no new core
logic; closes §6.9's Personnel-department mobile gap), Accounting (AP/AR outstanding
+ overdue counts, all-time invoiced totals, recent GL journals — new `reports_core
.accounting_dashboard()` combining `accounting_core`'s existing `get_ap_dashboard()`/
`get_ar_dashboard()` — both already real and in use by the web `acct_dashboard` view
— with the same recent-journals query that view already runs; closes §6.9's
Accounting-department mobile gap), Customer Service (open tickets, completion rate,
avg resolution/open-ticket age, recent tickets — new `reports_core
.customer_service_dashboard()` combining `cs_calls_core`'s existing
`get_summary_stats()`/`list_tickets()`, both already real and in use by the web
`cs_dashboard_view`; closes §6.9's Customer-Service-department mobile gap),
Engineering (active/planning project counts, overdue tasks, pending ECRs, recent
projects with task progress — new `reports_core.engineering_dashboard()` combining
`engineering_core`'s existing `get_eng_dashboard()`/`list_projects()`, both already
real and in use by the web `eng_dashboard` view; closes §6.9's Engineering-department
mobile gap), Customers (credit accounts at risk, total credit exposure, pending
credit applications, open collections, recent collection activity — new `reports_core
.customers_dashboard()` combining `credit_core`'s existing `get_credit_dashboard()`/
`list_collection_activities()`, both already real and in use by the web
`credit_dashboard` view; closes §6.9's Customers-department mobile gap — this is the
credit/collections risk-management domain, distinct from Sales and Customer Service),
IT (open/critical/in-progress helpdesk ticket counts, asset repair status, recent
tickets with priority — pure reuse of `it_core.get_it_dashboard()`, which already
bundled `recent_tickets` into its own return value and was already in use by the web
`it_dashboard` view, so this needed only a new `api_it_dashboard` view +
`/api/v1/dashboards/it/` route, no `reports_core` wrapper at all; closes §6.9's
IT-department mobile gap), Legal (active contract count, pending compliance items,
open litigation cases, recent contracts with value/status — pure reuse of
`legal_core.get_legal_dashboard()`, which already bundled `recent_contracts` into its
own return value and was already in use by the web `_legal.py` dashboard view, so this
also needed only a new `api_legal_dashboard` view + `/api/v1/dashboards/legal/` route,
no `reports_core` wrapper, matching the IT precedent; closes §6.9's Legal-department
mobile gap), Marketing (active/planned campaign counts, new/qualified lead counts,
published/draft content counts, recent campaigns with channel/objective/budget/status —
pure reuse of `marketing_core.get_marketing_dashboard()`, which already bundled
`recent_campaigns` into its own return value and was already in use by the web
`_marketing.py` dashboard view, so this also needed only a new `api_marketing_dashboard`
view + `/api/v1/dashboards/marketing/` route, no `reports_core` wrapper, the third
department in a row to need no wrapper at all; closes §6.9's Marketing-department
mobile gap), Payroll (YTD gross payroll, employees-with-pay-rates, active deduction
type counts, recent payroll runs with period/employee-count/gross/net — the one
department in this whole series with no single existing `get_*_dashboard()` to reuse
verbatim: `payroll_core.py` has `get_dashboard_counts()` and `list_payroll_runs()` as
separate pieces the web `payroll_dashboard` view itself combines, so this needed a new
`reports_core.payroll_dashboard()` wrapper combining the two — same shape as the
Accounting/Customer-Service/Engineering/Customers wrapper cases — plus a new
`api_payroll_dashboard` view + `/api/v1/dashboards/payroll/` route; closes §6.9's
Payroll-department mobile gap and completes mobile coverage for all 17 departments).
Plus `(auth)/login`. To run: `cd mobile && npx expo start` → scan QR with Expo Go on
phone.

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
rather than failing silently. **Wired into all 21 screens now** (initially six,
then extended to the remaining 15 in a follow-up pass): Time Clock (full
read-cache + write-queue — clock in/out are the canonical "plant-floor worker
with no signal" case), Work Orders' list view (read-cache only; status changes
and assignment still require connectivity), Maintenance's list view (read-cache
only, same rationale as Work Orders — completing a work order still requires
connectivity), Quality's NCR list view (read-cache only — creating an NCR
still requires connectivity), Inventory's product list (read-cache only,
caching `products` and the reorder `alerts` banner data together as one unit
since they come from the same response — receiving stock still requires
connectivity), and Costing's product-search list (read-cache only; the
cost/history/routing/reference-data drill-downs it opens into a modal are
not cached in this pass). The remaining 15 are all read-cache only, matching
that same precedent rather than extending write-queueing beyond Time Clock's
canonical case: the 11 single-`getXDashboard()` screens (main Dashboard,
Finance, Sales, Personnel, Accounting, Customer Service, Engineering,
Customers, IT, Legal, Marketing, Payroll) each cache their one dashboard
call under a screen-specific key (`dashboard`, `finance_dashboard`, etc.);
Requisitions caches its two list GETs separately (`req_list_mine`,
`req_list_pending`, the latter only fetched for managers) and merges
`isStale`/`cachedAt` across both, leaving create/submit/decide online-only;
Approvals caches the pending-steps list (`approval_pending_steps`), leaving
the approve/reject decision online-only; Lots caches its list and 30-day
expiry-alert banner together (`lots_list_<statusFilter>`, `lots_expiry_30`,
`Promise.all`'d and merged the same way as Requisitions), leaving the detail
drill-down, product search, and create/status-update mutations uncached —
matching the same "don't cache the modal drill-down" precedent Costing set.
Extending write-queueing to Requisitions/Approvals/Lots' mutations, if
wanted later, is a separate scoping decision from this pass (which only
closed the read-cache coverage gap).
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
pass would have). Translation coverage is the app's core navigation shell,
main landing page, two department dashboards, and both remaining htmx
live-refresh templates so far — `base.html` (sidebar: all 11 section headers
+ all ~37 nav links; top bar: notifications, password, 2FA, logout),
`home.html` (the login page), `dashboard.html` (the post-login main
dashboard: KPI labels, chart titles, the pending-PO-approvals banner using a
real `{% blocktrans count %}` plural, not a hardcoded English `|pluralize`),
`prod_dashboard.html` + `prod_dashboard_kpis.html` (the Production
dashboard: toolbar/dept-grid nav labels, KPI labels, chart titles, the
Recent Work Orders table headers), `maint_dashboard.html` +
`maint_dashboard_kpis.html` (the Maintenance dashboard: toolbar/section-link
nav labels, KPI labels including a second `{% blocktrans count %}` plural
for the "N critical" work-order sub-label, PM-alert urgency badges, and all
5 chart/section titles), `ai_insights_dashboard.html` + `ai_insights_feed.html`
(the AI Insights feed: page title, toolbar, a `{% blocktrans %}` intro
paragraph with embedded links, the "View →" link, and the empty-state
message — data-driven `domain`/`severity` badge text left untranslated,
matching the existing precedent of not translating raw status/enum values
elsewhere), and `sf_tv.html` + `sf_tv_grid.html` (the standalone shop-floor
OEE TV display — doesn't extend `base.html`, so needs its own
`{% load i18n %}`; the header/title and per-workcenter output line use
`{% blocktrans %}` with named variables for the shift name and produced/
planned/scrapped quantities, while the single-letter A/P/Q — Availability/
Performance/Quality — labels are left as-is, matching the app's existing
convention of keeping industry acronyms like MRP/BOM/OEE untranslated) —
wrapped in `{% trans %}`/`{% blocktrans %}`. This closes out all 5 of
§6.1's htmx live-refresh templates (`dashboard.html`, `prod_dashboard.html`,
`maint_dashboard.html`, `ai_insights_dashboard.html`, `sf_tv.html`) as
translated. Also fully translated: the entire **Legal department**
(`legal_dashboard.html`, `legal_contract_list.html`/`_detail.html`,
`legal_compliance_list.html`/`_detail.html`, `legal_litigation_list.html`/
`_detail.html`, `legal_employment_list.html`, `legal_governance_list.html`,
`legal_ip_list.html` — 10 templates, the smallest full department by
template count, picked as a "close out one entire department" milestone
rather than another single dashboard) — nav/toolbar labels, KPI labels,
filter-bar labels/placeholders, table headers, detail-page field labels,
and create/edit form labels and buttons across all 10; page titles using
a record's own name (contract title, case name, compliance requirement)
use `{% blocktrans %}` with a named variable. Status values themselves
(e.g. `contract.status`, `case.status`) are left untranslated, matching
the established precedent of not translating raw DB enum values. Picking
an entire department surfaced a real pre-existing gap while re-running
`makemessages` over the same files: the Maintenance dashboard's
`{% trans "No PM tasks overdue or due in the next 14 days." %}` (added in
an earlier pass) had an empty `msgstr` in all three `.po` files the whole
time — the empty-state branch was never exercised by live sample data
during that pass's own verification, so the gap went uncaught; fixed here.
Also fully translated: the entire **Marketing department**
(`marketing_dashboard.html`, `mkt_campaign_list.html`/`_detail.html`,
`mkt_lead_list.html`/`_detail.html`, `mkt_content_list.html`/`_detail.html`,
`mkt_ad_list.html`/`_detail.html`, `mkt_research_list.html`/`_detail.html`,
`mkt_analytics.html`, `mkt_budget_list.html` — 13 templates, the second
"whole department" pass after Legal), same treatment plus `{% blocktrans
count %}` for several "N active"/"N converted"/"N clicks"/"N in draft"
KPI sub-labels on `mkt_analytics.html`.

**Corrected gotcha** (an earlier version of this note, written during the
Marketing pass, misdiagnosed this as "`makemessages` can silently revert an
already-correct translation back to blank... a `msgmerge` quirk, most
likely" — that theory was wrong, root-caused in a follow-up fix; see below).
What actually happened: gettext line-wraps long translated values across
multiple `"..."` continuation lines in the `.po` file (`msgstr ""` followed
by several bare quoted-string lines that concatenate per `.po` syntax)
whenever a value is long enough, which `msgmerge` can trigger on any re-run
simply by reformatting. A hand-rolled fix script used for the Legal/
Marketing passes replaced only the *first* `msgstr "..."` line and `break`'d,
leaving the old wrapped continuation lines in place below the new one —
which then concatenated the old translation fragments onto the new one
instead of replacing them. Applied twice in a row (once per pass) to the
Maintenance dashboard's `"No PM tasks overdue or due in the next 14 days."`
string, this produced a 2-3x duplicated/garbled value in all three
languages, silently merged to `main` and deployed to the Windows box via
the Legal and Marketing PRs. A naive single-line-regex "did an existing
translation go blank" diff check (used to try to catch exactly this) also
missed it, because it only matched single-line `msgstr "..."` values and
misread the legitimately-wrapped (but now-corrupted) entry as blank rather
than parsing the continuation lines. Fixed for real (PR following #154):
audited all three `.po` files for any msgstr value containing a repeated
≥20-char substring (found only this one affected string), then replaced it
by consuming the *entire* old value (the `msgstr` line plus every following
bare-quoted continuation line) before writing the single-line replacement —
the correct pattern for any future manual `.po` edit: never replace just
the first line of a multi-line value (shipped as PR #155, ahead of and
independent from the next department's i18n PR since it corrected an
already-shipped defect). The same audit incidentally surfaced a second,
narrower gap while adding the next department below: a msgid can itself
span multiple wrapped lines (not just its msgstr), and a check that
assumes single-line msgids will silently skip those entries entirely —
`report_builder_detail.html`'s scheduled-delivery description was blank
in all three languages for exactly this reason until caught by hand.

Also fully translated: the entire **Reports department**
(`reports_dashboard.html`, `report_builder_list.html`,
`report_builder_detail.html`, `report_builder_form.html` — 4 templates,
the smallest remaining department, the third "whole department" pass),
same treatment plus `{% blocktrans count %}` for the PO-overdue and
inventory-reorder-point KPI sub-labels and the results/preview row-count
headers, and `{% blocktrans with %}` for the "Edit Report: {name}" and
"Last run: {timestamp}" headers.

Also fully translated: the entire **Payroll department**
(`payroll_dashboard.html`, `payroll_pay_rates.html`,
`payroll_deductions.html`, `payroll_history.html`, `payroll_run_detail.html`,
`payroll_run_new.html`, `payroll_stub_detail.html`, `payroll_ytd.html` —
8 templates, the fourth "whole department" pass, the smallest remaining
department at the time), same treatment plus `{% blocktrans with %}` for
the "Payroll Run — {start} to {end}" detail-page header and the pay
stub's "Social Security ({rate}%)"/"Medicare ({rate}%)" tax lines, and
`{% blocktrans count %}` for the YTD report's "N employee(s)" summary
line. Two new wrinkles here: (1) a msgid containing a bare `%` (not part
of a `%(name)s` placeholder, e.g. `"Federal Tax Rate (%)"`) gets escaped
by `makemessages` to `%%` in the `.po` file and is flagged
`#, python-format` — the `msgstr` must also use the doubled `%%` or
`msgfmt --check` fails; (2) another instance of the multi-line-msgid gap
from the Reports pass's PR #155/#156 turned up again — `payroll_run_new
.html`'s "Hourly employees are paid on actual clocked hours..." hint
paragraph is a `{% blocktrans %}` spanning several template lines, so its
msgid itself wraps across multiple `.po` lines and was left blank by the
same kind of check that only understands single-line msgids; fixed by
hand the same way as the Reports-pass instance.

Also fully translated: the entire **Time Clock department**
(`time_clock_status.html`, `time_clock_hours.html`,
`time_clock_attendance.html`, `tc_ot_report.html`, `tc_schedule.html`,
`tc_device_list.html`, `tc_device_form.html` — 7 templates, the fifth
"whole department" pass, tied with Customers/Credit for the smallest
remaining department at the time), same treatment plus `{% blocktrans
with %}` for the clock-status page's "Since {time}" and "Total today:
{total}" lines, the schedule page's "Daily Summary ({start} – {end})"
header, and a couple of multi-line device-form hints (the ZKTeco/manual
config help text). **New gotcha found here**: a translated `msgstr` that
itself contains a literal double quote (e.g. Spanish `Use "Consultar
ahora"...`, German `Verwenden Sie "Jetzt abfragen"...` — French sidestepped
it by using guillemets `« »` instead) must have that quote escaped as
`\"` in the `.po` file, same as the source msgid already does; a fix
script that writes the raw translated string straight into `msgstr
"..."` without escaping embedded quotes produces a `.po` file that looks
fine on casual inspection but fails `msgfmt --check` with a syntax error
at the point the unescaped quote closes the string early. Caught immediately
by running `msgfmt --check` right after the fix script rather than only at
`compilemessages` time.

Also fully translated: the entire **Customers/Credit department**
(`credit_dashboard.html`, `credit_account_list.html`,
`credit_account_detail.html`, `credit_application_list.html`,
`credit_application_detail.html`, `credit_collections_list.html`,
`credit_collections_detail.html` — 7 templates, the sixth "whole
department" pass, tied with Time Clock for smallest at the time —
this is the credit/collections risk-management domain, distinct from
the separate Sales and Customer Service departments), same treatment
plus `{% blocktrans with %}` for the three detail pages' dynamic page
titles ("Credit Account — {name}", "Credit Application — {name}",
"Collection Activity — {name}") and, trickiest of the three, the
application-detail page's "This customer already has a credit
account: `<a href="...">`view account`</a>` (current limit ${limit},
status {status})." banner — a `{% blocktrans %}` with literal HTML
(an `<a>` tag) mixed with three named interpolated variables. Built
the link's `href` with a plain `id=existing_account.id` named var
substituted directly into the URL template inside the blocktrans body
(`href="/credit/accounts/{{ id }}/"`) rather than trying to pre-build
the full URL string via chained `|add:` filters — Django's `add`
filter does a Python `+`, which raises (and is silently swallowed,
returning `''`) on `string + int`, so `"/credit/accounts/"|add:some_id`
quietly produces an empty/broken URL; passing the id straight through
and building the path as literal template text inside the `blocktrans`
block sidesteps that trap entirely. This batch's `makemessages` diff
was unusually large (900+ changed lines per file vs. the ~500 typical
of prior single-department passes) purely from `msgmerge` reflowing
and repositioning existing entries around the new ones, not from any
new corruption — reconfirmed via the same duplication/blank sweep
used since the corruption-fix PR, which came back clean.

Also fully translated: the entire **Engineering department**
(`eng_dashboard.html`, `eng_projects.html`, `eng_project_detail.html`,
`eng_tasks_list.html`, `eng_task_detail.html`, `eng_ecrs.html`,
`eng_ecr_detail.html`, `eng_specs_list.html`, `eng_spec_detail.html`,
`eng_reports.html` — 10 templates, the seventh "whole department"
pass — note the `engagement_*.html` files living alongside these in
`templates/` are a separate Consultants feature under `/consultants/`,
not this department; only the `eng_*.html` prefix is Engineering),
same treatment plus `{% blocktrans count %}` reusing the existing
"N overdue" plural from the Reports pass for the project list's
overdue-tasks badge, and `{% blocktrans with %}` for three dynamic
page/section titles ("Project: {num} — {title}", "ECR: {num} —
{title}", "Standard — {title}", "Task — {name}") plus the task-detail
page's project-link line. **Caught and fixed a real bug during this
pass, before it ever reached the `.po` file**: the task-detail
page's project-link `{% blocktrans %}` originally referenced
`{{ task.project_id }}` directly inside the block without binding it
via `with` first. `blocktrans`/`makemessages` don't reject a dotted
lookup like this at extraction time — it silently produces a msgid
containing the literal placeholder `%(task.project_id)s`, which is not
a valid Python `%`-format key (dots aren't permitted in identifiers),
so it would have failed at *render* time once translated, or at best
never actually interpolated the id and left a broken `href="/eng/
projects/{{ task.project_id }}/"`-shaped URL in production. Fixed by
adding `pid=task.project_id` to the `with` bindings and referencing
`{{ pid }}` in the href instead — every variable used inside a
`blocktrans` block that isn't a bare context name needs an explicit
`with` binding, not just filtered values as documented in the Reports
pass. Caught by inspecting the generated msgid in the `.po` diff
before writing translations, not by a test failure — worth treating as
a standing checklist item (grep the `makemessages` diff for `%(` keys
containing a `.` before translating) for any future `blocktrans` block
that references a dotted attribute lookup directly.

Also fully translated: the entire **Customer Service department**
(`cs_dashboard.html`, `cs_list.html`, `cs_detail.html`, `cs_new.html`,
`cs_escalations.html`, `cs_reports.html`, `cs_plans.html`,
`cs_returns_list.html`, `cs_returns_detail.html`, `cs_kb_list.html`,
`cs_kb_detail.html`, `cs_surveys_list.html`, `cs_surveys_detail.html` —
13 templates, the eighth "whole department" pass and the largest one
in this series so far, tied with Accounting at 13), 149 unique strings
per language (144 simple + 5 plural). Reused the existing "N overdue"
plural verbatim for the ticket-list overdue badge, and added several
new `{% blocktrans count %}` plurals ("N ticket(s)", "Open — N day(s)
old", "N open ticket(s)", "Responses (N)"). **Two gotchas recurred
here**: (1) the quote-escaping issue first found in the Time Clock
pass came back — two Spanish translations for search-result messages
embedded a literal `"%(q)s"` with straight double quotes, which needed
escaping as `\"` in the `.po` file the same way the source msgid
already does (French sidestepped it with guillemets, matching the
Time Clock precedent, but Spanish and German both needed the escape
this time); caught immediately via `msgfmt --check` right after the
fix script, before compiling. (2) A msgid/msgid_plural pair that was
itself long enough to be wrapped by `makemessages` from the very first
extraction (not from a later re-run, unlike every prior wrapped-msgid
case in this series) — the "N overdue (≥7 days)" banner on the CS
Reports page — needed the same "preserve the original msgid/msgid_plural
lines verbatim, only replace msgstr[0]/msgstr[1]" technique as before;
also re-confirmed that `msgid_plural` itself is source text, never a
translation target — a fix-script draft briefly (and incorrectly)
tried to write a translated placeholder into `msgid_plural`, caught by
reasoning through what gettext actually uses at lookup time (the
singular `msgid` is the runtime key; `msgid_plural` is metadata only)
before ever writing that draft to disk. Full suite 3431 passed
(unchanged), `manage.py check` clean, `compilemessages` clean,
`msgfmt --check` clean on all three files after the quote fix, zero
fuzzy/blank/duplicated entries confirmed programmatically (the
recurring "heures supplémentaires" false positive from the Payroll
pass reappears here too, unrelated to this batch). Verified end-to-end
against the real dev server: navigated the CS dashboard, the ticket
list (confirmed both plural badges and the quote-escaped "no results"
message with a live search), an open and a closed ticket's detail page
(confirmed the "Open — N days old" plural and the "Completed {date}
{time}" line), Reports (confirmed the nested "N open tickets — N
overdue" summary line), Escalations, Returns list/detail, Knowledge
Base list/detail, Surveys list/detail (confirmed the "Responses (N)"
plural), and Improvement Plans, in Spanish, French, and German with
real sample data, no console errors.

Also fully translated: the entire **Accounting department**
(`acct_dashboard.html`, `ap_list.html`, `ap_invoice_detail.html`,
`ar_list.html`, `ar_invoice_detail.html`, `gl_dashboard.html`,
`gl_accounts.html`, `gl_journals.html`, `gl_journal_detail.html`,
`gl_trial_balance.html`, `gl_income_statement.html`,
`gl_balance_sheet.html`, `gl_cash_flow_statement.html` — 13 templates,
the ninth "whole department" pass, tied with Customer Service and
Marketing at 13, and the last remaining department at the smallest
tier), 162 unique strings per language, all simple (no new plurals
needed this time — the department reuses the existing "N overdue"
plural precedent nowhere directly, since none of its KPI sub-labels
needed a plural form). `ar_list.html`/`ar_invoice_detail.html` and
`ap_list.html`/`ap_invoice_detail.html` are structurally
near-identical pairs (Customer/Received vs. Vendor/Paid terminology),
same pattern as the Reports/Time Clock precedent of near-duplicate
templates across a department. Used `{% blocktrans with %}` for the
AP/AR invoice detail pages' dynamic titles ("AP Invoice {num}"/"AR
Invoice {num}", "Invoice: {num}") and the "Record Payment (Balance:
${bal})" sub-header, the GL journal detail page's "Journal Entry
#{num}" title, the Balance Sheet's "Balance Sheet as of {as_of}"
header, the Trial Balance's "OUT OF BALANCE by ${amt}" status text,
and the G/L dashboard's "Chart of Accounts ({count} accounts)" nav
button — the last one mixing literal HTML (`<br>`/`<span>`) with an
interpolated variable, the same pattern established in the
Customers/Credit pass. **A new, larger-scale variant of the
`msgmerge` fuzzy-matching gotcha first documented in the Production
dashboard note surfaced here**: because Accounting's templates are
dominated by short, generic labels ("Date," "Status," "Amount,"
"Vendor," "Due Date"), `makemessages` fuzzy-matched 88 of the ~250
new strings against unrelated existing translations from other
departments — worst example, the new GL journal-line header "Credit"
got fuzzy-matched against the pre-existing "Credit Limit" (from the
Customers/Credit department) and inherited its translation "Límite de
crédito" ("Credit limit"), which is wrong in the accounting-ledger
context. **A fix-script bug written to handle this made it worse
before it was caught**: the first version stripped the `#, fuzzy`
marker and `#| msgid` metadata lines but left the wrong guessed
`msgstr` value in place, since the audit step only looked for
genuinely *blank* `msgstr`s and a fuzzy-matched entry isn't blank —
this would have silently shipped 88 wrong translations per language
with no `#, fuzzy` flag left behind to ever flag them for review
again. Caught before writing any translations, by inspecting the
"Credit" entry's translation by hand; fixed by reverting the `.po`
files, re-running `makemessages`, and rewriting the strip script to
also blank out the `msgstr`/`msgstr[n]` value (and its continuation
lines) whenever it removes a `#, fuzzy` marker, folding all 88
formerly-fuzzy entries into the normal "blank means needs a fresh
translation" audit path rather than special-casing them. Full suite
3431 passed (unchanged), `manage.py check` clean, `compilemessages`
clean, `msgfmt --check` clean on all three files, zero blank/
duplicated entries confirmed programmatically after the fix (the
recurring plural-concatenation false positive from the Customer
Service pass's checker reappears here too, unrelated to this batch).
Verified end-to-end against the real dev server: the Accounting
dashboard, AP list + an overdue invoice's detail page (confirmed the
"Invoice: {num}" title and "Record Payment (Balance: ...)" sub-header
with a live payment-history section), the G/L dashboard, Chart of
Accounts, Journal Entries list, a posted journal entry's detail page
(confirmed "Journal Entry #{num}"), the Trial Balance (confirmed the
BALANCED/CUADRADO status pill), and the Cash Flow Statement (confirmed
the multi-line reconciliation note), in Spanish, French, and German
with real sample data, no console errors.

Also fully translated: the entire **IT department**
(`it_dashboard.html`, `it_ticket_list.html`, `it_ticket_detail.html`,
`it_asset_list.html`, `it_asset_detail.html`, `it_repairs_list.html`,
`it_repairs_detail.html`, `it_software_list.html`,
`it_software_detail.html`, `it_license_list.html`,
`it_license_detail.html`, `it_network_list.html`,
`it_network_detail.html`, `it_task_list.html`, `it_task_detail.html`,
`it_incident_list.html`, `it_incident_detail.html` — 17 templates,
the tenth "whole department" pass and the largest one in this series
so far), 177 unique strings per language, all simple (no plurals —
IT's KPI sub-labels are all single counts, no "N of M" phrasing).
Used `{% blocktrans with %}` for six different dynamic-title shapes
across the department's five detail pages ("Ticket {num}", "Asset
{tag}", "Repair #{num}"/"Repair Request #{num}", "IT Task {num}"/
"Task {num}", "Incident: {title}", and — reusing the "{name} — #{num}"
shape twice, once for Software and once for License detail pages —
`{{ name }} — #{{ num }}` with `name` bound to `install.software_name|
default:"Software Installation"` / `lic.software_name|default:
"License"` so the friendly fallback text stays translatable too, the
same pattern as the Software/License list-page row links). Also used
`{% blocktrans with %}` three times on the Asset detail page's
Depreciation Summary card for "Method: {method}", "Vendor: {vendor}",
and "Location: {loc}" — three independent inline fragments rather
than one combined string, matching how the source template already
built the line up piecemeal with separate `{% if %}` blocks. **Two
bare `{{ x|default:"..." }}` fallbacks were caught and fixed before
they were missed entirely**: the Network Device detail page's
`page_title` and `<h2>` both defaulted directly to a literal English
string (`"Device"` / `"Network Device"`) with no `{% trans %}`
wrapping at all — since this is a bare filter default rather than a
`blocktrans with` binding, Django templates don't allow a translation
function call inside the filter argument, so the fix uses an explicit
`{% if device.hostname %}{{ device.hostname }}{% else %}{% trans "..."
%}{% endif %}` instead of the filter. Worth a standing note: any
`{{ var|default:"literal text" }}` used as a heading or title needs
this if/else expansion, not a `default:` filter fix, since the filter
argument position can't hold a `{% trans %}` or `_()` call. **Also
caught and fixed a Django template syntax mistake before it ever hit
`makemessages`**: a first draft used `{% trans \"Requester's dept\"
%}` inside a double-quoted HTML attribute, escaping the trans tag's
own quotes with a backslash — but Django's template lexer doesn't
support backslash-escaping inside a `{% %}` tag's own string argument,
so the literal backslash would have leaked into the rendered output.
The correct approach (confirmed by testing) is simpler than it looks:
the trans tag's internal quotes are consumed during template parsing
and never appear in the HTML output, so nesting `{% trans "Requester's
dept" %}` directly inside `placeholder="..."` is safe as-is — no
escaping needed at all, since the string's only special character is
an apostrophe, which doesn't conflict with the tag's own double
quotes. **Found the largest `msgmerge` fuzzy-matching batch in this
series yet**: 121 of the new strings were fuzzy-matched against
unrelated existing translations (up from Accounting's 88), including
10 in the newly-seen combined `#, fuzzy, python-format` form (used for
every fuzzy-matched string that also contains a `%(name)s`-style
placeholder) — confirming that combined-flag variant isn't a one-off,
it recurs any time a fuzzy-matched string happens to carry a
placeholder, and a strip script must match both `#, fuzzy` and `#,
fuzzy, python-format` (reducing the latter to plain `#, python-format`
rather than deleting the flag outright, since the string genuinely
does contain a placeholder). Applied the corrected strip-and-blank
technique from the Accounting pass's fix (blank the `msgstr` whenever
either fuzzy variant is stripped, rather than only removing the flag)
from the start this time, so no wrong guesses ever reached a written
translation. Full suite 3431 passed (unchanged), `manage.py check`
clean, `compilemessages` clean, `msgfmt --check` clean on all three
files, zero blank/duplicated entries confirmed programmatically (the
recurring plural-concatenation false positive from the Customer
Service pass's checker reappears here too, unrelated to this batch,
since IT added no new plurals). Verified end-to-end against the real
dev server: the IT dashboard, Tickets list + a resolved ticket's
detail page (confirmed "Ticket {num}"), Assets list + an asset detail
page (confirmed "Asset {tag}" — no sample asset has a purchase price
set, so the Depreciation Summary card's translations couldn't be
exercised live, though the template logic is otherwise identical to
every other verified block), Licenses list + a license detail page
(confirmed "{name} — Nr. {num}" in German), Software list + a
software detail page, Network Devices list + a device detail page,
Repairs list + a repair detail page (confirmed "Reparaturanfrage Nr.
{num}"), Tasks list (confirmed the hardcoded priority/status pill
translations "Hoch"/"Mittel") + a task detail page (confirmed "Task
{num}"), and Incidents list (empty state only — no sample incidents
exist), in German, Spanish, and French with real sample data, no
console errors.

Also fully translated: the entire **Finance department**
(`finance_dashboard.html`, `finance_budget_list.html`,
`finance_budget_detail.html`, `finance_audit_list.html`,
`finance_audit_detail.html`, `finance_bank_rec_list.html`,
`finance_bank_rec_detail.html`, `finance_tax_list.html`,
`finance_tax_detail.html`, `fin_cash_forecast.html` — 10 templates,
the eleventh "whole department" pass, tied with Legal at the smallest
size seen in this series). Note this "Finance" surface is distinct
from — and reached via toolbar links out of — the already-translated
Accounting department: it covers Budgets, Audits, Bank Reconciliation,
Tax Filings, and the 13-Week Cash Forecast, all served under `/fin/`.
100 unique strings per language (99 simple + 1 plural). Used
`{% blocktrans with %}` for three dynamic detail-page titles
("Budget — {name}", "Audit — {name}", "Tax Filing — {tax_type}"), and
added one new `{% blocktrans count %}` plural for the audit detail
page's "Findings (N)" header — the first plural in this series where
the target languages use genuinely different singular/plural *nouns*
(Spanish "Hallazgo"/"Hallazgos", French "Constatation"/
"Constatations", German "Feststellung"/"Feststellungen") rather than
an invariant noun with only the count changing, since the English
source text is identical in both forms ("Findings (N)") but the
Romance/Germanic target grammar isn't. Left two dynamic headings
un-wrapped by design, matching established precedent: the bank
account detail page's `{{ account.account_name }}{% if
account.bank_name %} — {{ account.bank_name }}{% endif %}` and the
tax filing detail page's `{{ filing.tax_type }}{% if
filing.jurisdiction %} — {{ filing.jurisdiction }}{% endif %}` both
combine only data fields with a literal " — " separator, with no
English words to translate. `manage.py makemessages` fuzzy-matched 74
of the new strings against unrelated existing translations from other
departments (down from IT's 121, none combined with `python-format`
this time), all handled cleanly from the start with the
blank-the-msgstr-when-stripping-fuzzy technique established since the
Accounting pass. Full suite 3431 passed (unchanged), `manage.py check`
clean, `compilemessages` clean, `msgfmt --check` clean on all three
files, zero blank/duplicated entries confirmed programmatically (the
recurring plural-concatenation false positive from the Customer
Service pass's checker reappears here too, unrelated to this batch).
Verified end-to-end against the real dev server: the Finance
dashboard, Budgets list + a draft budget's detail page ("Lignes
Budgétaires" / no line items yet), Audits list + a scheduled audit's
detail page (confirmed the "Constatation (0)" plural with zero
findings), Bank Accounts list + an account detail page (confirmed the
Active "Oui"/"Yes" dropdown), Tax Filings list + a filing detail page,
and the 13-Week Cash Forecast (confirmed the multi-line
methodology note), in French, German, and Spanish with real sample
data, no console errors.

Also fully translated: the entire **Quality department**
(`qa_dashboard.html`, `qa_ncr_list.html`, `qa_ncr_detail.html`,
`qa_capa_list.html`, `qa_capa_detail.html`, `qa_audit_list.html`,
`qa_audit_detail.html`, `qa_inspection_list.html`,
`qa_inspection_detail.html`, `qa_supplier_list.html`,
`qa_supplier_detail.html`, `qa_reports.html` — 12 templates, the
twelfth "whole department" pass). Note the QA Dashboard also links
out to four further sub-features (SPC, Certificates of Analysis,
Control Plans/FMEA, Regulatory Compliance) that are **not** part of
this pass — their nav labels on the dashboard were translated since
they're literal dashboard text, but the destination pages themselves
remain untranslated, the same "translate the link, not yet the
target" situation as Accounting's toolbar links into the separately-
handled Finance department. 142 unique strings per language (138
simple + 4 plural). Kept the `NCR`/`CAPA` acronyms themselves
untranslated across all three languages (same treatment as MRP/BOM/
OEE elsewhere in the app) while translating the surrounding
descriptive text around them. Used `{% blocktrans with %}` for the
"NCR #{num} — {title}" / "CAPA #{num} — {title}" / "Audit #{num} —
{title}" / "Supplier Quality #{num}" dynamic detail-page titles, and
`{% blocktrans %}` with an embedded literal `<a>` tag for the
inspection-form's "Manage plans on the Sampling Plans page" hint
paragraph — the same embedded-HTML-link pattern established in the
Customers/Credit pass. Added four new `{% blocktrans count %}`
plurals: the dashboard KPI cards' "{{ counter }} critical" / "{{
counter }} overdue" suffixes (reusing the existing "N overdue" plural
verbatim, confirming yet again it's now a shared string across many
departments), the inspection detail page's "Defects (N)" header, and
the inspection list's inline defect-count fragments ("N open", "N
total", "N resolved"). **Two more bare `{{ x|default:"literal" }}`
fallbacks were caught and fixed before they were missed**, the same
class of bug first found in the IT department's Network Device page:
the inspection detail page's "not yet recorded" fallback for
`qty_defective`, and the reports page's "Unrated" fallback for a
supplier's rating — both needed the `{% if %}/{% else %}/{% trans %}`
expansion since a bare filter argument can't hold a `{% trans %}` or
`_()` call. `makemessages` fuzzy-matched 93 of the new strings against
unrelated existing translations, handled cleanly from the start with
the blank-the-msgstr-when-stripping-fuzzy technique. Full suite 3431
passed (unchanged), `manage.py check` clean, `compilemessages` clean,
`msgfmt --check` clean on all three files, zero blank/duplicated
entries confirmed programmatically (the recurring plural-
concatenation false positive reappears here too, now including this
pass's own new plurals, unrelated to any real corruption). Verified
end-to-end against the real dev server: the QA dashboard (confirmed
both "N critical"/"N overdue" KPI suffixes), NCR list + a closed NCR's
detail page (confirmed "NCR N.° {num} — {title}"), CAPA list + an
overdue CAPA's detail page (confirmed the overdue-notice banner),
Audits list + a detail page (confirmed "Audit N° {num} — {title}" and
its overdue notice in French), Inspections list + a detail page with
a logged defect (confirmed the "N open" and "Defecto (1)" plurals and
the embedded Sampling Plans link), Supplier Quality list, and QA
Reports (confirmed all KPI labels and section headers), in Spanish,
French, and German with real sample data, no console errors.

Also translated: the QA dashboard's four **SPC/CoA/Control Plans/
Compliance** sub-features named as excluded above (`spc_list.html`,
`spc_log.html`, `coa_list.html`, `coa_new.html`, `coa_detail.html`,
`control_plan_list.html`, `control_plan_new.html`,
`control_plan_detail.html`, `compliance_template_list.html`,
`compliance_template_new.html`, `compliance_template_detail.html`,
`compliance_checklist_list.html`, `compliance_checklist_detail.html` —
13 templates, closing the "translate the link, not yet the target" gap
this department was left with). 243 `{% trans %}`/`{% blocktrans %}`
tags added by two parallel subagents (SPC+CoA, Control Plans+Compliance)
given the established conventions verbatim — the same delegation
approach first used for Personnel's recruiting/benefits/offboarding
cluster. Kept `FMEA`, `Cpk`, `LCL`/`UCL`, and quality-standard names
(`ISO 13485:2016`, etc.) untranslated where used as raw labels, matching
the `NCR`/`CAPA`/`MRP`/`BOM`/`OEE` acronym precedent — single-letter
`S`/`O`/`D` (Severity/Occurrence/Detection) column headers in the
control plan's characteristics table also left as-is, matching `sf_tv
.html`'s A/P/Q precedent for bare single-letter acronym headers. Found
and fixed **two non-heading `default:"literal English"` fallbacks** the
delegated agent correctly flagged rather than silently expanding, since
its instructions scoped that fix to headings only — `spc_list.html`'s
`{{ l.product_name|default:"(any)" }}` table cell and `spc_log.html`'s
`{{ cpk.error|default:"Not enough data yet." }}` empty-state message —
both genuinely meaningful English text, not non-linguistic placeholders
like "—", so both got the same `{% if %}/{% else %}/{% trans %}`
expansion as a heading would. `makemessages` fuzzy-matched 65 of the new
strings against unrelated existing translations and left 49 more
genuinely blank — both corrected by hand across all three languages;
zero fuzzy/blank/duplicated entries confirmed programmatically after the
fix. Full suite re-ran clean (3438, unchanged — template/locale-file
work only), `manage.py check` clean, `msgfmt --check` clean on all three
files. Verified end-to-end against a from-this-worktree dev server
instance, using real seeded sample data rather than empty-state pages:
the SPC limits list and measurement-log page, a real CoA's detail page
(confirmed "Bestanden"/Pass, "Losnummer"/Lot Number, "Ausstellungsdatum"
/Issued Date), a real control plan's detail page (confirmed "Merkmale
und FMEA" with the FMEA acronym preserved), a real compliance
template's detail page, and a real compliance checklist's detail page
(confirmed the multi-variable `{% blocktrans with standard=... owner=
... %}` binding renders correctly as "Norm: … · Verantwortlicher: …"),
in German (plus spot-checks in Spanish and French on the list/new-form
pages), no console errors.

Also fully translated: the entire **Production department**
(`prod_reports.html`, `prod_daily_report.html`,
`prod_delivery_status.html`, `prod_labor_report.html`,
`prod_performance_report.html`, `prod_returns_list.html`,
`prod_returns_detail.html`, `prod_returns_reports.html`,
`prod_schedule.html`, `prod_schedule_gantt.html`,
`prod_shipping_list.html`, `prod_shipping_detail.html`,
`prod_tracking_dashboard.html` — 13 templates, the thirteenth "whole
department" pass; `prod_dashboard.html`/`prod_dashboard_kpis.html`
were already translated in the original htmx-templates pass, so
weren't re-touched here). 112 unique strings per language (109 simple
+ 3 plural). Converted two hand-rolled `|pluralize` filter uses to
proper `{% blocktrans count %}` blocks — `prod_labor_report.html`'s
per-person "N WO" summary and `prod_schedule.html`'s "N work order(s)
shown" footer — since the bare `|pluralize` filter only ever appends
an English "s" and can't be translated at all; found by grepping for
`|pluralize` while auditing the department, the same kind of targeted
check as the Engineering pass's "grep for dotted blocktrans variables"
checklist item. Used `{% blocktrans with %}` for three dynamic report
titles carrying a day-count ("Work Order Summary/Shipping Summary/Top
Completed Products ({days} days)"), plus "Work Orders Due {date}" and
"RMA {num}"/"Shipment — {num}" detail-page titles. Kept the `RMA`
acronym untranslated (same treatment as `NCR`/`CAPA` in the Quality
pass and `MRP`/`BOM`/`OEE` elsewhere). **Found the labor report's
"Completed By"/"Assigned To" footnote already had embedded straight
double quotes in the English source** (`whose name matches the
operation's "Completed By"...`) — rather than risk the quote-escaping
gotcha first hit in the Time Clock pass, translated using guillemets
(`« »`) in all three target languages here rather than just French,
sidestepping backslash-escaping entirely for this string. **Three more
bare `{{ x|default:"literal" }}` fallbacks were caught and fixed**,
continuing the bug class first found in the IT department's Network
Device page: `prod_performance_report.html`'s "Unknown" fallback for
a product name, and `prod_returns_reports.html`'s "Unknown" fallback
for a return reason — both needed the `{% if %}/{% else %}/{% trans %}`
expansion. `makemessages` fuzzy-matched 84 of the new strings against
unrelated existing translations, handled cleanly from the start with
the established blank-the-msgstr-when-stripping-fuzzy technique. Full
suite 3431 passed (unchanged), `manage.py check` clean,
`compilemessages` clean, `msgfmt --check` clean on all three files,
zero blank/duplicated entries confirmed programmatically (the
recurring plural-concatenation false positive reappears here too,
now including this pass's own new plurals, unrelated to any real
corruption). Verified end-to-end against the real dev server: the
Production Schedule (confirmed the "N work orders shown" plural),
Labor Time & Cost Report (confirmed both the KPI cards and the
per-person "N WO" plural in its `<details>` summary, plus the
guillemet-quoted footnote), Shipping list + a returned shipment's
detail page (confirmed "SH-2026-0003" title, the EDI/push-confirmation
toolbar buttons, and the "Items (0)" plural), Returns list + a detail
page (confirmed "RMA RMA-2026-0002"), the Gantt chart page (confirmed
the empty-state message with no scheduled operations), the Tracking
Dashboard, and Production Reports (confirmed all KPI cards and table
headers), in German, French, and Spanish with real sample data, no
console errors. **Localization coverage is now 144 templates across
three languages** (core shell + login + main dashboard + all 5 htmx
templates + the full Legal department (10) + the full Marketing
department (13) + the full Reports department (4) + the full Payroll
department (8) + the full Time Clock department (7) + the full
Customers/Credit department (7) + the full Engineering department
(10) + the full Customer Service department (13) + the full
Accounting department (13) + the full IT department (17) + the full
Finance department (10) + the full Quality department (12) + the full
Production department (13, plus the 2 already-translated htmx
templates)) out of ~450 total.

Also fully translated: the entire **Maintenance department**
(`maint_downtime_list.html`/`_detail.html`, `maint_equipment_list.html`/
`_detail.html`, `maint_inspection_list.html`/`_detail.html`,
`maint_mechanics_list.html`/`maint_mechanic_detail.html`,
`maint_parts_list.html`/`maint_part_detail.html`,
`maint_schedule_list.html`/`_detail.html`, `maint_wo_list.html`/
`_detail.html`, `maint_labor_report.html`, `maint_oee_report.html` —
16 templates, the fourteenth "whole department" pass; `maint_dashboard
.html`/`maint_dashboard_kpis.html` were already translated in the
original htmx-templates pass and are not recounted here). Deliberately
excluded, matching the established "translate the link, not yet the
target" precedent (Quality's SPC/COA/Control-Plans/Compliance,
Accounting's separate Finance department): the dashboard's links out
to `/maint/apm/` (Asset Performance Management), `/predictive-
maintenance/`, and `/maint/routes/`, none of which are part of this
16-template core. 114 unique strings per language, all simple (no new
plurals — the one place a plural would have applied, the per-mechanic
"N WO" badge in the Labor Time & Cost Report's `<details>` summary,
reused the exact `%(counter)s WO`/`%(counter)s WOs` msgid already
translated by the Production department's own labor report, so
`makemessages` merged it automatically with zero new translation work
needed). Used `{% blocktrans with %}` for six dynamic titles ("WO
#{num}", "WO #{num} — {title}", "Downtime #{num}", "Downtime:
{equipment}", "Inspection #{num}", "Inspection: {area}", "PM Task
#{num}", "PM Task: {task}" — several pages needed both an id-based
`page_title` and a name-based `<h2>`, both wrapped). Found the same
`{{ x }} WO{{ x|pluralize }}` untranslatable-filter pattern first
documented in the Production pass, in `maint_labor_report.html`'s
per-mechanic summary line — converted to `{% blocktrans count %}`,
which is what let it merge with Production's existing translation
instead of needing a fresh one. `manage.py makemessages` fuzzy-matched
88 of the new strings against unrelated existing translations from
other departments (same count as the Accounting pass, all handled from
the start with the blank-the-msgstr-when-stripping-fuzzy technique
established since that pass). One embedded-newline gotcha in the
translation-application script itself (not the `.po` file): a
`{% blocktrans %}` footnote in `maint_labor_report.html` wraps across
a template line break, so its msgid contains a literal `\n` escape
sequence (two characters, backslash and "n") rather than an actual
newline byte — a translation dict built by typing a normal `\n` in the
Python source produces a real newline at runtime, which silently fails
to match the `.po` file's literal-backslash-n key and leaves the entry
unapplied; fixed by writing the escape as `\\n` in the dict source so
the runtime string also holds the literal two-character sequence,
verified with a byte-level check before re-running the apply script.
Full suite 3431 passed (unchanged), `manage.py check` clean,
`compilemessages` clean, `msgfmt --check` clean on all three files,
zero blank/duplicated entries confirmed programmatically (the
recurring plural-concatenation false positives from earlier passes
reappear here too, unrelated to this batch, since Maintenance added no
new plurals). Verified end-to-end against the real dev server: the
Maintenance Work Orders list + a completed WO's detail page (confirmed
"OT n° 4 — ..." in French), Equipment list + a detail page, Downtime
list, Mechanics list + a detail page (confirmed the hidden-compensation
tooltip logic still renders for a full-access user), Parts list, PM
Schedule list + an overdue task's detail page (confirmed the overdue
notice and "Mark Complete" hint text in German), the Labor Time & Cost
Report (confirmed the KPI cards and the reused "3 OT" per-mechanic
plural badge), and the OEE Report (confirmed the doubled-`%%` "World-
class = 85%" KPI sub-label and the blocktrans'd Availability/Quality
sub-labels), in Spanish, French, and German with real sample data, no
console errors. **Localization coverage is now 160 templates across
three languages** (core shell + login + main dashboard + all 5 htmx
templates + the full Legal department (10) + the full Marketing
department (13) + the full Reports department (4) + the full Payroll
department (8) + the full Time Clock department (7) + the full
Customers/Credit department (7) + the full Engineering department
(10) + the full Customer Service department (13) + the full
Accounting department (13) + the full IT department (17) + the full
Finance department (10) + the full Quality department (12) + the full
Production department (13, plus the 2 already-translated htmx
templates) + the full Maintenance department (16, plus the 2
already-translated htmx templates)) out of ~450 total.

Also fully translated: the entire **Purchasing department**
(`purchasing_dashboard.html`, `purch_reports.html`,
`purch_contracts_list.html`/`_detail.html`, `po_list.html`/`_detail.html`/
`_form.html`, `po_approvals.html`, `po_landed_cost_detail.html`/`_new.html`,
`rfq_list.html`/`_detail.html`/`_new.html`, `blanket_po_list.html`/
`_detail.html`/`_new.html`, `blanket_po_release_new.html`, `req_list.html`/
`_detail.html` — 19 templates, the fifteenth "whole department" pass, the
largest yet by unique-string count). Deliberately excluded, matching the
established "translate the link, not yet the target" precedent: the
dashboard's links to `/suppliers/` (renders the generic, non-Purchasing-
specific `contacts_list.html` shared across multiple contact types — not
even really a Purchasing-owned template), `/consignment/` (5 templates),
`/supplier-portal/` (9 templates), and the supplier-scorecard pages (2
templates) — none of which are part of this 19-template core. 182 unique
strings per language, all simple (no plurals — none of this department's
KPI sub-labels needed one). Half of these templates (`po_*.html`,
`blanket_po_*.html`) use the newer shared `erp-table`/`menu-title`/`pill`/
`empty-state` design-system classes from the web-native PO migration
(`views.WEB_LEAF_URLS`; see the Web-PO feature note) rather than this
app's older hand-styled per-page CSS — cosmetically different from the
`purch_*.html`/`rfq_*.html` half of the pass, but translated with the same
`{% trans %}`/`{% blocktrans %}` approach throughout. Extended the existing
`confirm('{% trans "..." %}')` pattern (previously used in only two other
templates app-wide, `finance_budget_detail.html` and `gl_journal_detail
.html`) to five more JS `confirm()` dialogs here, including two using
`{% blocktrans %}` with an interpolated PO/blanket-PO number inside the JS
string — confirmed this works identically to `{% trans %}` since Django
renders the tag server-side before the JS ever reaches the browser. Used
`{% blocktrans with %}` for eight dynamic titles ("Edit {num}", "Contract —
{num}", "Landed Cost — PO {num}", "Add Landed Cost — PO {num}", "Add
Call-off — {num}", "Requisition {num}", plus two embedded-HTML "Total
Value:"/"Total Qty:" summary lines mixing a `<b>` tag with two or three
interpolated variables, the same pattern established in the Customers/
Credit and Accounting passes). **Found and correctly handled the same
class of escaping gotcha the Maintenance pass hit for embedded newlines,
but for embedded quotes instead**: three empty-state messages
(`po_list.html`, `blanket_po_list.html`, `rfq_list.html`) read `No purchase
orders with status "{{ status }}".` in the English source — `makemessages`
escapes the literal `"` characters to the two-character sequence `\"` in
the `.po` msgid (same as any quoted string embedded in a `.po` file), so a
translation-dict key built with a normal escaped-quote Python string
(where `\"` is decoded to a single `"` character) silently fails to match
and leaves the entry unapplied; fixed by building those specific dict keys
as Python raw strings (`r'...\"...'`) so the literal two-character
backslash-quote sequence survives into the runtime string exactly as
`makemessages` wrote it — confirmed with a byte-level check before
applying, mirroring the Maintenance pass's `\n`-escape fix. Sidestepped the
same issue in the *translated* values entirely by using guillemets (`«
»`) instead of straight quotes, the established convention since the Time
Clock pass. Same raw-string technique also handled two multi-line
`{% blocktrans %}` strings that wrap across a template line break (the PO
approval-queue's threshold notice, mirroring the Maintenance labor
report's footnote gotcha). No bare `{{ x|default:"literal" }}` fallback
bugs and no untranslatable `|pluralize` uses found this pass — the first
department pass in this series to come up clean on both of those standing
checklist items. `makemessages` fuzzy-matched 111 of the new strings
against unrelated existing translations (second only to IT's 121), handled
cleanly from the start with the established blank-the-msgstr-when-stripping-fuzzy
technique. Full suite 3431 passed (unchanged), `manage.py check` clean,
`compilemessages` clean, `msgfmt --check` clean on all three files
(including the two escaped-quote and two multi-line entries), zero blank/
duplicated entries confirmed programmatically (the recurring plural-
concatenation false positives from earlier passes reappear here too,
unrelated to this batch, since Purchasing added no new plurals). Verified
end-to-end against the real dev server: the Purchasing Dashboard (KPI
cards and charts), PO list + a draft PO's detail page, RFQ list + an open
RFQ's detail page (confirmed the quote-comparison table and vendor-invite
flow), Blanket PO list + a closed blanket PO's detail page (confirmed the
embedded-`<b>`-tag "Valor Total: $1000,00 (Liberado: ..., Restante: ...)"
line in Spanish), Purchase Requisitions list + a dept-approved
requisition's detail page (confirmed "Requisición REQ-2026-0006"), the PO
Approval Queue (confirmed the threshold notice's multi-line blocktrans in
French), Vendor Contracts (empty state + new-contract form), and a New PO
form, in Spanish, French, and German with real sample data, no console
errors. **A pre-existing, unrelated bug was found and flagged separately
rather than fixed in this i18n-only pass**: `/purch/reports/` 500s with
`relation "purchase_order_item" does not exist` — the view's SQL
references a table name that doesn't match the live schema (the real
table is `po_item`), the same live-schema-vs-code-assumption class of bug
documented elsewhere in this file's "Database gotchas" section; confirmed
present on `main` before this branch's changes, unrelated to any template
edit here. **Localization coverage is now 179 templates across three
languages** (core shell + login + main dashboard + all 5 htmx templates +
the full Legal department (10) + the full Marketing department (13) + the
full Reports department (4) + the full Payroll department (8) + the full
Time Clock department (7) + the full Customers/Credit department (7) +
the full Engineering department (10) + the full Customer Service
department (13) + the full Accounting department (13) + the full IT
department (17) + the full Finance department (10) + the full Quality
department (12) + the full Production department (13, plus the 2
already-translated htmx templates) + the full Maintenance department (16,
plus the 2 already-translated htmx templates) + the full Purchasing
department (19)) out of ~450 total.

Also fully translated: the entire **Sales department**
(`sales_dashboard.html`, `sales_orders.html`, `sales_order_detail.html`,
`sales_quotes.html`, `sales_leads_list.html`/`_detail.html`,
`sales_contracts_list.html`/`_detail.html`, `sales_forecast_list.html`/
`_detail.html`, `sales_targets.html`, `sales_territories.html`,
`sales_territory_performance.html`, `sales_commissions.html`,
`sales_commission_plans.html`, `sales_commission_history.html`,
`sales_performance.html`, `sales_performance_reviews.html`,
`sales_coaching.html`, `sales_reports.html`, `sales_demand.html` — 21
templates, the sixteenth "whole department" pass and the largest yet by
template count, tied with Purchasing's 19 but one bigger). Deliberately
excluded `/demand-forecast/` (a separate AI-driven demand-forecasting
feature backed by its own `demand_forecast.html`, distinct from this
department's own `sales_demand.html` "Demand Forecast" page which pulls
from actual sales-order revenue) — matching the "translate the link, not
yet the target" precedent. 214 unique strings per language, all simple —
the largest single-department string count in this series, edging out
Purchasing's 182. Found and fixed **two more bare `{{ x|default:"literal"
}}` fallback bugs**, continuing the class first found in the IT
department's Network Device page: `sales_territory_performance.html`'s
`{{ t.assigned_rep|default:"Unassigned" }}` and
`sales_forecast_detail.html`'s `{{ forecast.rep|default:"Forecast" }}`
(the latter in the page's own `<h2>` heading) — both needed the
`{% if %}/{% else %}/{% trans %}` expansion. Also translated a literal
`{% if p.active %}Active{% else %}Inactive{% endif %}` badge in
`sales_commission_plans.html` that had been left as bare English text
inside the conditional. **Extended the embedded-HTML-link `{% blocktrans
%}` pattern (established in the Customers/Credit and Accounting passes)
to its most complex case yet**: `sales_performance.html`'s two ranking-
table empty-state messages and `sales_territory_performance.html`'s
empty-state plus a multi-line footer paragraph containing **two**
`<a href="..." style="...">` links with an inline `style` attribute —
each `href`'s and `style`'s literal double quote gets escaped by
`makemessages` to the two-character sequence `\"` in the `.po` msgid
(the same escaping gotcha the Purchasing pass hit for plain quoted text,
now recurring inside HTML attributes), and the multi-line footer
additionally wraps across a template line break exactly like the
Maintenance pass's labor-report footnote. Both gotchas compound in the
same string: translation-dict keys and values both needed to be built as
Python raw strings (`r"...\"..."`) using a **double-quote-delimited** raw
string rather than single-quoted, specifically because several French
translations of this content contain apostrophes (`d'objectif`,
`l'instant`) that would otherwise prematurely terminate a single-quoted
raw string — confirmed by testing both delimiter choices at the byte
level before applying, since getting this wrong would have silently
dropped the real `<a>` links from the translated pages in favor of
plain text (caught in a first draft that mistakenly rendered these as
guillemet-quoted plain text instead of live links, corrected before
applying to the `.po` files). `manage.py makemessages` fuzzy-matched 169
of the new strings against unrelated existing translations, a new high
for this series, handled cleanly with the established
blank-the-msgstr-when-stripping-fuzzy technique. Full suite 3431 passed
(unchanged), `manage.py check` clean, `compilemessages` clean,
`msgfmt --check` clean on all three files (including the four
attribute-quoted/multi-line entries), zero blank/duplicated entries
confirmed programmatically (the recurring plural-concatenation false
positives reappear here too, plus one new expected false-positive flag
on the multi-line footer paragraph itself, since its two `style="color:
#aad;"` attributes are legitimately repeated text within a single long
string — confirmed not corruption). Verified end-to-end against the real
dev server: the Sales Dashboard, Sales Orders list + a draft order's
detail page, Sales Quotes, Leads list + a detail page, Sales Contracts
list, Sales Forecast list + a detail page (confirmed the blocktrans'd
period-actuals banner), Territory Management + Territory Performance
(confirmed the "Sin Asignar"/`Unassigned` fix and, via direct DOM
inspection, that the footer paragraph's two `<a>` tags render as real
working links with correct `href`s in Spanish), Commission Tracking,
Commission Plans (confirmed the Active/Inactive fix and the doubled-`%%`
"e.g. Standard 5%" placeholder), Commission Payment History, the Sales
Performance rankings dashboard, Performance Reviews, Coaching Notes,
Sales Reports, and Demand Forecast, in Spanish, French, and German with
real sample data, no console errors. **Two pre-existing, unrelated bugs
were found and flagged separately rather than fixed in this i18n-only
pass**: (1) `sales_order_detail.html`'s status-transition buttons
(`{{ SO_STATUS_ACTION_LABELS|get_item:t|default:t }}`) crash with
`TemplateSyntaxError: Invalid filter: 'get_item'` whenever an order has
available status transitions, because no `get_item` template filter has
ever been defined anywhere in the codebase (confirmed via `git show
main:...` that this predates this pass entirely — there is no
`manufacturing/templatetags/` directory at all); (2) confirmed to be a
distinct, already-flagged issue from the `/purch/reports/` table-name bug
found during the Purchasing pass. **Localization coverage is now 200
templates across three languages** (core shell + login + main dashboard +
all 5 htmx templates + the full Legal department (10) + the full
Marketing department (13) + the full Reports department (4) + the full
Payroll department (8) + the full Time Clock department (7) + the full
Customers/Credit department (7) + the full Engineering department (10) +
the full Customer Service department (13) + the full Accounting
department (13) + the full IT department (17) + the full Finance
department (10) + the full Quality department (12) + the full Production
department (13, plus the 2 already-translated htmx templates) + the full
Maintenance department (16, plus the 2 already-translated htmx
templates) + the full Purchasing department (19) + the full Sales
department (21)) out of ~450 total — the first time this series has
crossed 200.

Also fully translated: the entire **Personnel department** core
(`personnel_dashboard.html`, `pers_depts.html`, `pers_reviews_list.html`/
`_detail.html`, `pers_training_list.html`/`_detail.html` — 6 templates,
the seventeenth "whole department" pass and, by a wide margin, the
smallest yet). Personnel's dashboard links out to far more areas than any
prior department — Employees (`/people/`), Time Off (`/time-off/`),
Benefits (`/benefits/`), Skills Matrix/Workforce Analytics
(`/skills/matrix/`, `/workforce/`), Recruiting/ATS (`/ats/`), and an
Offboarding cluster (`/pers/terminations/`, `/pers/exit-interviews/`,
`/pers/offboarding/`) — but only Dashboard, Departments, Reviews, and
Training share the `pers_` view/template naming convention; the rest
route through distinctly-named views (`termination_list`,
`exit_interview_list`, `offboarding_list`, `benefits_dashboard`,
`skill_list`, `workforce_analytics`, `ats_dashboard`, etc.) backed by
their own `benefit_*`/`employee_*`/`skill_*`/`termination_*`/
`exit_interview_*`/`offboarding_*`/`ats_*`/`workforce_*`-prefixed
templates — a materially larger and more sprawling set of sub-features
than any prior "translate the link, not yet the target" exclusion in
this series, deliberately left untranslated here. 48 unique strings per
language, all simple (no plurals, no bare `default:"literal"` fallback
bugs, no `|pluralize` uses — the second department pass in this series,
after Purchasing, to come up clean on every standing checklist item).
Used `{% blocktrans with %}` for three dynamic titles/lines ("Review —
{last}, {first}", "Training — {course}", and the review detail page's
"View {first} {last}'s profile" back-link, the last one a possessive
apostrophe requiring no special escaping since it contains no straight
double quotes). `makemessages` fuzzy-matched only 40 of the new strings,
the smallest fuzzy count in this series (matching its smallest string
count), handled cleanly with the established
blank-the-msgstr-when-stripping-fuzzy technique. Full suite 3431 passed
(unchanged), `manage.py check` clean, `compilemessages` clean,
`msgfmt --check` clean on all three files, zero blank/duplicated entries
confirmed programmatically (the recurring plural-concatenation false
positives from earlier passes reappear here too, unrelated to this
batch). Verified end-to-end against the real dev server: the Personnel
Dashboard (all KPI cards and chart titles), Departments &amp;
Sub-Departments (both tables live-edited), Performance Reviews list
(empty state) plus a review created live through the form and its detail
page (confirmed "Bailey, Daniel — Annual" and the possessive back-link),
and Training &amp; Development list plus a training record created live
through the form and its detail page (confirmed "CORRECTNESS-CHECK
Forklift Safety" title and "Employee: Bailey, Daniel" line), in Spanish,
French, and German with real data, no console errors. **Localization
coverage is now 206 templates across three languages** (core shell +
login + main dashboard + all 5 htmx templates + the full Legal
department (10) + the full Marketing department (13) + the full Reports
department (4) + the full Payroll department (8) + the full Time Clock
department (7) + the full Customers/Credit department (7) + the full
Engineering department (10) + the full Customer Service department (13)
+ the full Accounting department (13) + the full IT department (17) +
the full Finance department (10) + the full Quality department (12) +
the full Production department (13, plus the 2 already-translated htmx
templates) + the full Maintenance department (16, plus the 2
already-translated htmx templates) + the full Purchasing department
(19) + the full Sales department (21) + the Personnel department core
(6)) out of ~450 total — this closes out the last of the 17 named
departments' core areas, though a substantial long tail of linked
sub-features across many departments (Personnel's own recruiting/
benefits/offboarding cluster foremost among them) remains untranslated,
consistent with this series' policy of scoping each pass to a
department's own directly-owned templates rather than every reachable
link.

Also translated: Personnel's own **recruiting/benefits/offboarding
cluster** (`ats_dashboard.html`, `ats_requisition_list.html`,
`ats_requisition_new.html`, `ats_requisition_detail.html`,
`ats_candidate_list.html`, `ats_candidate_new.html`,
`ats_candidate_detail.html`, `ats_application_detail.html`,
`benefits_dashboard.html`, `benefit_plan_new.html`,
`benefit_plan_detail.html`, `employee_benefits.html`,
`termination_list.html`, `termination_detail.html`,
`exit_interview_list.html`, `offboarding_list.html` — 16 templates, the
long-tail exception explicitly named as still-open in the Personnel core
pass above; the biggest deliberately-scoped-out sub-feature in this
series). 307 `{% trans %}`/`{% blocktrans %}` tags added across the three
sub-clusters (ATS 136, Benefits 71, Offboarding 100). `makemessages`
fuzzy-matched 76 of the new strings against unrelated existing
translations — the largest fuzzy count in this series yet (previous high
was Sales' 169, but that was against ~10x this batch's own new-string
count; 76 wrong guesses out of ~180 unique new strings this pass is a
much higher *rate* than any prior single pass) — all corrected by hand
with real translations across all three languages using the established
strip-fuzzy-and-replace technique. Also found — and this is new relative
to every prior pass — **24 entries `makemessages` left genuinely blank**
(not fuzzy-guessed at all, just empty `msgstr`), because these were
short, generic-sounding strings (`"Stage"`, `"Tier"`, `"Enrolled"`,
`"Candidate"`, `"Waive"`, etc.) with no similar-enough existing
translation anywhere in the app for `msgmerge` to even attempt a guess;
translated all 24 by hand. A blank-entry audit script written for this
pass initially produced a **false-positive list of 36**, not 24 — it
mis-parsed gettext's standard line-wrapping for long translated values
(`msgstr ""` followed by unprefixed `"..."` continuation lines) as an
empty translation, because its regex only captured the first `msgstr`
line; 12 of the 36 were long-standing, correctly-translated, wrapped
entries from unrelated departments (Customer Service, Maintenance,
Quality, Reports, RFQ, Sales, Time Clock) that just happened to sort
alongside this pass's real gaps. Confirmed via `git show HEAD:...` that
all 12 already had real multi-line translations before this pass touched
anything, then rewrote the audit script to properly reassemble wrapped
`msgstr` values across their continuation lines before flagging — this
is a new, more subtle variant of the multi-line-value parsing gotcha
already documented above (previously only the msgid side, and only for
`{% blocktrans %}`-wrapped source text spanning template lines, was
known to wrap across multiple `.po` lines; this is the msgstr side
wrapping purely from *translated* value length, independent of the
source). Worth a standing note for any future manual blank/duplication
audit: reconstruct the full `msgstr` (and `msgstr[N]`) value by
concatenating the `msgstr` line with every immediately-following
bare-`"..."` line, not just the first line, before deciding an entry is
blank. Full suite re-ran clean (3431, unchanged — template/locale-file
work only), `manage.py check` clean, `msgfmt --check` clean on all three
files, zero fuzzy/blank/duplicated entries confirmed programmatically
after the fix. This pass's template-marking work (adding the
`{% trans %}`/`{% blocktrans %}` tags themselves, before any of the
`makemessages`/fuzzy/blank work above) was done by three parallel
subagents, one per sub-cluster (ATS, Benefits, Offboarding), each given
the same established conventions (dotted-lookup `blocktrans` binding
rule, bare `default:"..."` heading expansion, no raw-enum translation,
no `|pluralize`) verbatim — a first for this series, previously always
done by hand in one pass; a follow-up programmatic sweep confirmed no
file was missing `{% load i18n %}`, no stray `|pluralize` survived, and
no unbound dotted lookup was left inside any `{% blocktrans %}` block
across all 16 files before `makemessages` was ever run. Verified
end-to-end against a dev server instance run from this exact worktree
(not the stale port-8000 instance from a different worktree that tripped
up the department-grid-label pass immediately before this one — see
below): logged in as a full-access user, switched through all three
languages via `/i18n/setlang/`, and confirmed correct translated text on
all 10 list/dashboard/new-record pages in the cluster (ATS dashboard,
requisition list/new, candidate list/new, Benefits dashboard/new-plan,
Terminations list, Exit Interviews list, Offboarding checklist),
including several of the specific strings that were fuzzy- or
blank-fixed by hand (e.g. German "z. B. PPO Gold" and "z. B. Empfehlung,
Jobbörse" placeholder text on the new-record forms), in Spanish, French,
and German.

The main dashboard's department grid button labels were the one exception —
they're rendered from `menus.py`-generated Python strings
(`DASHBOARD_DEPARTMENTS`, a 17-entry `(key, label)` list, also reused
verbatim by the Approval Rules admin's department dropdown in
`views/_approval_rules.py`), not template-static text, so translating them
needed `gettext_lazy` calls in `menus.py` itself rather than the
template-level `{% trans %}` used everywhere else — now done (`from
django.utils.translation import gettext_lazy as _`, each label wrapped in
`_(...)`). 15 of the 17 labels auto-merged with existing correct
translations from elsewhere in the app (department names repeated as sidebar
nav labels, page titles, etc.) via `makemessages`'s exact-source-text
matching; 2 (`"Information Tech"`, `"Budget Management"`) were genuinely new
strings that `msgmerge` fuzzy-matched to unrelated existing translations
("Information Technology Dashboard" and "Budget Name" respectively) —
handled with the by-now-standard fix (strip the `#, fuzzy`/`#| msgid` lines,
replace with a correct manual translation) rather than the
blank-and-retranslate technique, since only these 2 of the 17 needed fresh
translation work. Verified end-to-end against a from-this-worktree dev
server instance (the already-running `manage.py runserver` on port 8000
turned out to be serving a *different* worktree's checkout — a reminder
that a long-lived background dev server doesn't necessarily reflect the
current worktree's uncommitted changes; spun up a throwaway instance on
port 8001 instead) logged in as a full-access (President) user, switching
through all three languages via `/i18n/setlang/` and confirming both the
main dashboard grid and the Approval Rules new-rule form's department
dropdown render the correct translated label for all 17 departments,
including the 2 previously-fuzzy ones. `manage.py makemessages` does **not** ignore `venv/` by
default (unlike `.gitignore`-based tools) — a bare `makemessages -l <code>`
run against this repo will scan the whole venv's site-packages and pollute
every `.po` file with hundreds of unrelated strings; always pass
`--ignore=venv --ignore=mobile --ignore=media --ignore=backups --ignore=docs`
(confirmed the hard way once: a bare run added 1800+ lines of Django/click
internals to all three `.po` files before being caught and reverted).

Run `python manage.py makemessages -l <code> --ignore=venv --ignore=mobile
--ignore=media --ignore=backups --ignore=docs` after adding a new
`{% trans %}` to catch the new string in every existing `.po` file (it
merges via `msgmerge`, preserving existing translations by matching on the
English source text) — but check the merge output for `#, fuzzy` markers
before trusting it: `msgmerge` will guess-match a new string against a
similar existing one (e.g. it once fuzzy-matched a new "PO Approvals"
against the existing translation of "Approval Rules", and separately
fuzzy-matched 11 of the ~37 new strings added for the Production
dashboard, e.g. guessing "Product" → the existing translation of
"Production") and leave that wrong guess in place unless it's corrected
by hand. Then `python manage.py compilemessages`
— the `.mo` binary Django actually loads at runtime isn't regenerated
automatically, and the dev server's autoreloader doesn't watch `.po`/`.mo`
files, so a manual restart is also needed after compiling.

**Two more languages added: Portuguese and Dutch** (closing the
localization-breadth gap COMPETITIVE_GAP_ANALYSIS.md §9.4 called out —
MRPeasy shipping more languages than this app's then-three). `LANGUAGES`
in `manufacture/settings.py` now has 6 entries (en/es/fr/de/pt/nl).
Unlike every prior language pass, which paired "mark a new template with
`{% trans %}`" with "add its translation," this pass added **zero** new
`{% trans %}`/`{% blocktrans %}` tags — every template already marked for
es/fr/de (206+ templates, the full 17-department core plus every
long-tail cluster) was already extraction-ready, so `python manage.py
makemessages -l pt --ignore=venv --ignore=mobile --ignore=media
--ignore=backups --ignore=docs` (and `-l nl`) against a completely new,
previously-nonexistent locale directory just extracted the existing 2,437
msgids straight from the source templates with empty `msgstr`s — no
`msgmerge`/fuzzy-matching gotchas at all, since there was no prior
translation for anything to fuzzy-match against. The entire remaining
effort was translating those 2,437 entries (2,413 simple + 24 plural
pairs) into both languages: split into 18 chunks of ~140 entries each and
translated by 18 parallel subagents (one per chunk, each producing both
languages together so terminology stays paired), then merged
programmatically into `locale/pt/LC_MESSAGES/django.po` and
`locale/nl/LC_MESSAGES/django.po` by matching on msgid/msgid_plural and
writing correctly-escaped `msgstr`/`msgstr[0]`/`msgstr[1]` lines — no
manual `msgstr`-editing gotchas from prior passes applied either, since
every value was written as a single escaped line (backslash, then `"`,
then real newlines → literal `\n`) rather than hand-typed multi-line
continuations. Kept the same acronym-preservation convention (NCR, CAPA,
MRP, BOM, OEE, RMA, FMEA, ISO, SPC, CoA, GL, AP, AR, PO, WO, SO, KPI,
etc. left untranslated) and each language's native quotation marks for
strings with embedded quotes (Portuguese `«…»`, Dutch `„…"`). Verified:
`msgfmt --check` clean on both new `.po` files, zero blank/duplicated
entries confirmed programmatically (all 2,437 keys present, no gaps),
full suite 3,457 passed (unchanged — no Python logic touched), `manage.py
check` and `ruff check .` both clean. Verified end-to-end via the Django
test client (the background dev server on port 8000 was serving a
different worktree, same recurring gotcha noted elsewhere in this file)
logged in as the President sample user, switching to both `pt` and `nl`
via `/i18n/setlang/` and confirming translated content on the main
dashboard, Quality, Purchasing, Sales, Legal, and Personnel dashboards,
plus a live plural ("N overdue" → "N atrasados"/"N te laat") and the
language switcher itself listing both new languages. **The other ~250
department-specific content templates never marked for es/fr/de remain
untranslated in pt/nl too** — this pass only extended existing coverage
to two new languages, it didn't mark any new template.

## Web UI (Django) & menu routing
- **Live-refresh via htmx** (COMPETITIVE_GAP_ANALYSIS.md §6.1 "Modern Frontend," deliberately
  partial — a full SPA rewrite isn't proportionate to this codebase's size). 10 of ~450 templates
  poll a small fragment view every 30s instead of doing a full page reload: `sf_tv.html`,
  `prod_dashboard.html`, `maint_dashboard.html`, `ai_insights_dashboard.html`, `dashboard.html`
  (the main company dashboard), `purchasing_dashboard.html`, `qa_dashboard.html`,
  `sales_dashboard.html`, `it_dashboard.html`, and `acct_dashboard.html`. Pattern to copy for the
  next page:
  a `<div id="..." hx-get="/path/to/fragment/" hx-trigger="every 30s" hx-swap="innerHTML">{% include
  "the_fragment.html" %}</div>` wrapping whatever needs to stay live, a `{name}_fragment` view
  (same auth decorator as the parent view) that renders that same partial template standalone, and
  `<script src="https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"></script>` in the page's
  `extra_scripts` block — matches the Chart.js CDN-script precedent, not a new dependency-management
  pattern. Factor the shared data-fetching logic (SQL/computation) into one helper function called
  by both the full-page view and the fragment view — `dashboard.html`'s `_dashboard_kpis()` in
  `views/__init__.py` is the reference example — so the two can't silently drift out of sync.
  `purchasing_dashboard.html`'s own version of this (`purch_dashboard_kpis_fragment` polling
  `/purch/kpis-fragment/`) picked the KPI row (Open/Pending Approval/Draft/Sent/Partial/Total PO
  counts) plus the Recent Purchase Orders table — a manager watching this page wants to see a PO's
  status change or a new draft appear without a manual refresh, the same "time-sensitive queue"
  rationale as Maintenance's and Production's dashboards, picked over the heavier chart-data half of
  the page (PO status breakdown, spend by month, top suppliers/items, PO trend, requisition status)
  which stays static until reload, matching every other htmx pass's precedent of not polling slow
  aggregate chart data. `purchasing_core.py`'s `get_purchasing_dashboard()` was refactored to extract
  a `get_purchasing_dashboard_kpis(conn)` helper (the first two of its eight queries) that it now
  calls internally, rather than duplicating those two queries in the fragment view — 7 new unit
  tests added, including one asserting the full dashboard call and the standalone kpis-only call
  return byte-identical `pos`/`recent_pos` values, so the two truly can't drift apart. Full suite
  passes (3438, +7 from the new tests), `manage.py check` clean. Verified end-to-end against a
  from-this-worktree dev server instance (not the port-8000 instance from a different worktree —
  see the note further down): hit `/purch/kpis-fragment/` directly and confirmed it renders
  standalone with real data (Total POs: 13); created a real PO via
  `purchase_orders_core.create_po` (status `'draft'`), re-fetched the fragment, and confirmed
  "Total POs" incremented to 14 with the new PO appearing at the top of the Recent Purchase Orders
  table — genuine live data, not a cached partial — then deleted the test PO and confirmed the
  count reverted to 13; separately confirmed the fragment renders correctly in French when fetched
  with an active French session, matching `dashboard.html`'s own i18n/htmx-composition precedent.
  `qa_dashboard.html`'s version (`qa_dashboard_kpis_fragment` polling `/qa/kpis-fragment/`) picked
  the KPI grid alone (Open NCRs/CAPAs, critical/overdue sub-counts, Active Audits, Pending
  Inspections, Open Defects) — a QA manager watching for a new critical NCR or an overdue CAPA
  wants that without a manual refresh, the same rationale as Purchasing's PO-approval queue — over
  the heavier Pareto/trend/results charts below it, which stay static until reload. No core-module
  refactor was needed here, unlike Purchasing: `quality_core.get_dashboard_counts(conn)` was
  already a small standalone function (a single query), already shared and independently tested, so
  the fragment view just calls it directly rather than needing a new extracted helper. Full suite
  passes (3438, unchanged — no new core logic), `manage.py check` clean. Verified end-to-end against
  a from-this-worktree dev server instance: hit `/qa/kpis-fragment/` directly (renders standalone
  with real data — Open NCRs: 12, 4 critical); created a real Critical-severity NCR via
  `quality_core.create_ncr`, re-fetched the fragment, and confirmed "Open NCRs" incremented to 13
  with the critical sub-count to 5 — then deleted the test NCR and confirmed both reverted; also
  confirmed the fragment renders correctly in Spanish with an active Spanish session.
  `sales_dashboard.html`'s version (`sales_dashboard_kpis_fragment` polling
  `/sales/kpis-fragment/`) picked the KPI row (Confirmed/Shipped/Invoiced Orders, Total Order
  Value, Open Quotes, Won Quote Value) plus the Recent Orders and Recent Quotes tables — a sales
  manager watching this page wants to see an order confirm or a quote get won without a manual
  refresh, the same "time-sensitive queue" rationale as Purchasing's PO-approval queue, over the
  heavier revenue/customer/pipeline/leads/product/status charts below it, which stay static until
  reload. No core-module refactor was needed here either: `sales_core.get_sales_dashboard(conn)`,
  `list_sos(conn)`, and `list_quotes(conn)` were already small standalone, independently-tested
  functions the full-page view already called directly, so the fragment view just calls the same
  three rather than needing a new extracted helper. Full suite passes (3457, unchanged — no new
  core logic), `manage.py check` clean. Verified end-to-end against a from-this-worktree dev
  server instance: hit `/sales/kpis-fragment/` directly (renders standalone with real data —
  Confirmed Orders: 6); created a real confirmed sales order via
  `sales_orders_core.create_so` (status `'confirmed'`), re-fetched the fragment, and confirmed
  "Confirmed Orders" incremented to 7 with the new order appearing at the top of the Recent
  Orders table — then deleted the test order and confirmed the count reverted to 6; also
  confirmed the fragment renders correctly in French with an active French session.
  `it_dashboard.html`'s own version (`it_dashboard_kpis_fragment` polling
  `/it/kpis-fragment/`) picked the Help Desk Tickets KPI row (Open/In Progress/Critical/Total
  counts) plus the Recent Support Tickets table — an IT manager watching this page wants to see a
  new critical ticket land without a manual refresh, the same "time-sensitive queue" rationale as
  Quality's critical-NCR count and Purchasing's PO-approval queue, over the static Asset Inventory
  KPI row and all six charts below it (ticket/asset status/priority/type/trend breakdowns), which
  stay static until reload matching every other htmx pass's precedent. No core-module refactor was
  needed: `it_core.get_it_dashboard(conn)` already returned `tickets` + `recent_tickets` in one
  small, already-tested call that the full-page view already used directly, so the fragment view
  just calls the same function rather than needing a new extracted helper. Full suite passes
  (3457, unchanged — no new core logic), `manage.py check` and `ruff check .` both clean. Verified
  end-to-end via the Django test client (logged in as the President sample user): hit
  `/it/kpis-fragment/` directly (renders standalone with real data — Open: 6, Critical: 2); created
  a real critical ticket via `it_core.create_ticket`, re-fetched the fragment, and confirmed "Open"
  incremented to 7 and "Critical (Open)" to 3 with the new ticket appearing in the Recent Support
  Tickets table — then deleted the test ticket and confirmed both counts reverted; also confirmed
  the fragment renders correctly in Portuguese and Dutch with an active session in each.
  `acct_dashboard.html`'s own version (`acct_dashboard_kpis_fragment` polling
  `/acct/kpis-fragment/`) picked the AP KPI row (Open/Overdue/Total Outstanding), the AR KPI row
  (same three), and the Recent Journal Entries table — a controller watching this page wants to see
  a new invoice go overdue or a journal get posted without a manual refresh, the same
  "time-sensitive queue" rationale as every prior htmx pass, over the static AP/AR-status,
  top-vendor/customer, and journal-trend charts below it. Unlike IT/Sales/Quality, this one *did*
  need a small core-module refactor: the view's inline "recent journals" SQL (a `LEFT JOIN`
  aggregating line count + total debit per journal, `LIMIT 8`) was duplicated logic waiting to
  happen, so it's now `accounting_core.get_accounting_dashboard_kpis(conn)` — a thin wrapper
  combining the already-existing `get_ap_dashboard()`/`get_ar_dashboard()` with
  `list_journals(conn)[:8]` (reusing the *unfiltered* `list_journals()` rather than duplicating its
  query, since calling it with no filters already returns every journal ordered newest-first) —
  called by both the full-page view and the new fragment view so they can't drift apart, the same
  pattern `purchasing_core.get_purchasing_dashboard_kpis()` established. 3 new unit tests
  (`test_accounting_core.py`), mocking `get_ap_dashboard`/`get_ar_dashboard`/`list_journals`
  directly rather than `conn.execute`, since the combining function's own logic (slicing to 8,
  wrapping in dicts) is what needed coverage, not the underlying queries those three functions
  already test themselves. Full suite passes (3460, +3), `manage.py check` and `ruff check .` both
  clean. Verified end-to-end via the Django test client: hit `/acct/kpis-fragment/` directly
  (renders standalone with real data — AP Open Invoices: 7); created a real balanced GL journal via
  `accounting_core.create_journal`, re-fetched the fragment, and confirmed it appeared at the top of
  the Recent Journal Entries table — then deleted it and confirmed it was gone; also confirmed the
  fragment renders correctly in Portuguese and Dutch with an active session in each.
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
  a column's type or nullability.** A related variant, caught by
  `.github/workflows/loadtest.yml` once it started running on every PR
  against a genuinely fresh CI database (see `COMPETITIVE_GAP_ANALYSIS.md`
  §6.13 for the workflow change itself): `product.item_type`/`uom`/
  `lead_time_days`/
  `created_by` are **only ever added via `seeds/seed_sample_products.py`'s own
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`** — `schema.py`'s and
  `work_orders_core.py`'s `CREATE TABLE IF NOT EXISTS product` (whichever runs
  first) never include them. A real production deployment (which never runs
  that dev-only seed script) hitting `/inventory/` before those columns exist
  500'd with `psycopg2.errors.UndefinedColumn`. Fixed with a shared
  `inventory_core._ensure_product_extra_columns(conn)` self-heal, called from
  every function in that module that touches any of the four columns — the
  same "self-heal in the query path" pattern `get_product()` already used for
  just `created_by` before this fix generalized it. Five more modules
  (`bom_web_core.py`, `carbon_core.py`, `mrp_web_core.py`,
  `cycle_count_core.py`, `costing_core.py`) referenced the same columns
  without any self-heal and shared the identical latent bug, despite not
  being on the load test's page list — fixed in a follow-up pass:
  `bom_web_core.py`/`mrp_web_core.py` import
  `inventory_core._ensure_product_extra_columns` directly, while
  `carbon_core.py`/`costing_core.py`/`cycle_count_core.py` already gate
  their queries behind their own `ensure_*_tables(conn)` (called from every
  view), so the missing `item_type`/`uom` `ALTER TABLE`s were added there
  instead. Postgres DDL is transactional, so functions that must not commit
  their own transaction (`create_product`/`update_product`/
  `update_item_master`) just run the `ALTER`s without an explicit
  `conn.commit()` — the caller's own commit persists them alongside the row
  it's writing.
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
