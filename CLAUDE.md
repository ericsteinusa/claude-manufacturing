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
Closes COMPETITIVE_GAP_ANALYSIS.md §6.11 (and its §9.4/§10.5/§11 follow-ups)
— **now complete**, unlike this project's other honestly-scoped *partial*
gap closures (mobile offline support, RFID, predictive maintenance): every
template in `manufacturing/templates/` (474/474) plus `menus.py`'s
`MENU_TREE` (the Python-side department drill-down menu, which never
counted toward the template metric since it isn't one) load i18n and
translate cleanly into six languages with zero fuzzy/untranslated entries
in any of them, confirmed via `msgfmt --statistics`. This section's history
below is preserved as a chronological log of how coverage was built up from
one department at a time to that 100% endpoint — read it as a build order
and a catalog of every escaping/pluralization/fuzzy-matching gotcha hit
along the way, not as a description of current scope. Real, working
infrastructure: `django.middleware.locale.LocaleMiddleware` (positioned after
`SessionMiddleware`, before `CommonMiddleware`, per Django's own requirement),
`LANGUAGES`/`LOCALE_PATHS` in `manufacture/settings.py`, and a language
switcher (`<select>` posting to Django's built-in `set_language` view, wired
at `/i18n/` in `manufacture/urls.py`) in `base.html`'s top bar, plus
`base_card.html` (login/register/password/MFA) and both customer/supplier
portal base templates. Six languages are wired up: English (default),
Spanish, French, German, Portuguese, Dutch
(`locale/{es,fr,de,pt,nl}/LC_MESSAGES/django.po`, all real translations, not
placeholder or machine-translated text throughout). The initial pass's
translation coverage was the app's core navigation shell, main landing
page, two department dashboards, and both remaining htmx live-refresh
templates — `base.html` (sidebar: all 11 section headers
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

Also translated: the **web-native Work Order / Sales Order pages**
(`so_list.html`, `so_detail.html`, `so_form.html`, `wo_list.html`,
`wo_detail.html`, `wo_form.html`, `wo_carbon_detail.html`,
`wo_cost_detail.html` — 8 templates). Note these are distinct from
`sales_orders.html`/`sales_order_detail.html`, the older reporting-style
pages already translated in the Sales department pass — `so_*`/`wo_*`
are the actual `views.so_detail`/`views.wo_detail` CRUD pages (routed at
`/so/`, `/wo/`) and were missed by every department-scoped pass so far
since they don't carry a department-name prefix. 90 unique strings across
5 languages (450 translations), all simple except 3 multi-line
`{% blocktrans %}` paragraphs (the WO Carbon/Cost compute-hint text and
the WO Gantt forward/backward-scheduling hint, all wrapping across
template lines the same way as the Maintenance labor report's footnote).
Also wrapped `SO_STATUS_ACTION_LABELS`/`WO_STATUS_ACTION_LABELS` (in
`sales_orders_core.py`/`work_orders_core.py`) in `gettext_lazy` — these
are plain dicts rendered directly as status-transition button text
(`{{ label }}`) in `so_detail.html`/`wo_detail.html`, the same
non-template-rendered-string situation `menus.py`'s
`DASHBOARD_DEPARTMENTS` hit, and unlike `PO_STATUS_ACTION_LABELS` (left
untranslated — out of scope, `po_detail.html` is a different page) these
two are used nowhere else (no mobile/API JSON serialization), so wrapping
was safe. Caught and fixed a bare `{{ wo.assigned_to|default:"— Unassigned
—" }}` fallback (the same bug class first found on IT's Network Device
page) sitting right next to an already-correct `{% if %}/{% else %}`
version of the identical fallback three lines up — copy-paste had
preserved the bug in one branch while fixing it in the other.

**New gotcha, distinct from every prior escaping pitfall in this file**:
a fill script that pre-embeds a literal `\n` (backslash+n, written as
`"\\n"` in the Python source) into a translation string, then also runs
a generic `.replace("\\", "\\\\")` escaping pass over that same string
before writing it to the `.po` file, double-escapes the backslash —
the file ends up with `\\n` (two backslashes) instead of `\n`, which
`msgfmt --check` accepts without complaint (it's still a syntactically
valid escape sequence, just the wrong one) and which every blank/fuzzy/
duplication audit in this file's history would also pass clean, since
none of them decode escape sequences. The only thing that catches it is
calling `django.utils.translation.gettext()` at runtime and checking
`"\n" in result` — `msgfmt --check` and a raw `.po` diff both look
identical whether the newline decoded correctly or not. Found by doing
exactly that (`translation.activate('es'); gettext(...)`) before trusting
the multi-line strings, rather than stopping at `msgfmt --check` passing.
Fixed by re-deriving the 3 affected entries (5 languages) with a targeted
substring fix rather than re-running the whole fill script. Full suite
3475 passed (unchanged), `manage.py check` and `ruff check .` clean,
`msgfmt --check` clean on all 5 files, zero fuzzy/blank entries.
Verified end-to-end against the real dev server: SO list + a draft SO's
detail page (confirmed "Fecha de Envío:", "Descargar 855 (EDI)"), a WO's
detail page including its Operations card (confirmed the
"Progreso: 2 / 2 pasos completados" and "Total hrs. est.: ... | Hrs.
real: ... | Costo de mano de obra: ..." blocktrans fragments, the
"— Sin asignar —" fallback fix, and the forward/backward-scheduling
hint paragraph rendering as real line breaks, not literal `\n`), the WO
Cost and WO Carbon detail pages (confirmed both remaining multi-line
paragraphs), and the SO/WO "New" forms, in Spanish, French, German,
Portuguese, and Dutch with real sample data, no console or server errors.

Also translated: the **Employee Self-Service (ESS) pages**
(`ess_home.html`, `ess_profile.html`, `ess_pay_stubs.html`,
`ess_pay_stub_detail.html`, `ess_time_off.html`, `ess_reviews.html`,
`ess_review_detail.html`, `ess_trainings.html`,
`ess_training_detail.html`, `ess_ytd.html` — 10 templates, routed at
`/ess/`). The employee-facing counterpart to the manager-facing Personnel
core/cluster passes — every hourly or salaried employee hits these
pages directly, not just HR staff, making this one of the higher-value
remaining gaps despite its small size. 94 unique strings across 5
languages, 57 genuinely new (the other 37 auto-merged via exact-text
match) — reuse was unusually high because `ess_pay_stub_detail.html` is
structurally identical to the already-translated `payroll_stub_detail
.html` (same `Employee:`/`Pay Period:`/`Social Security ({{ rate }}%):`
labels, copied verbatim from that pass), and several list-page column
headers (`Type`, `Status`, `Reviewer`, `Course`) were already established
by the Personnel and Time Clock passes. Used the same non-pluralized
`{% blocktrans %}{{ days }} days{% endblocktrans %}` pattern
`cs_dashboard_kpis.html` established for a `floatformat`-rendered value
(vacation-balance days) rather than `{% blocktrans count %}`, since a
decimal count (e.g. "3.5 days") has no clean singular/plural split.
**Caught and fixed a live bug via cross-reference, not by re-deriving
convention from scratch**: `ess_home.html`'s tile above the
Quick-Links card had `{{ balance.used_days|floatformat:1 }} of
{{ balance.allotted_days|floatformat:1 }} used` sitting right next to
`ess_time_off.html`'s near-identical "Allotted/Used/Remaining" tiles —
both wrapped with the same technique, confirming the two pages'
otherwise-independent English copy was already meant to read as one
family of phrasing. Full suite 3475 passed (unchanged), `manage.py
check` and `ruff check .` clean, `msgfmt --check` clean on all 5 files,
zero fuzzy/blank entries. Verified end-to-end against the real dev
server: the ESS home tile grid (confirmed the vacation-balance and
latest-pay-stub tiles with real data), My Profile, My Pay Stubs list +
a real pay stub's detail page (confirmed it reuses the entire Payroll
pass's vocabulary — Employee:/Pay Period:/Social Security (%)/PAGO
NETO: — byte-for-byte), My Time Off, My Reviews, My Training, and My
YTD Summary, in Spanish, French, German, Portuguese, and Dutch with
real sample data, no console or server errors.

Also translated: the **Customer and Supplier Portals** (`base_portal.html`,
`portal_home.html`, `portal_orders.html`, `portal_order_detail.html`,
`portal_invoices.html`, `portal_invoice_detail.html`, `portal_login.html`,
`portal_register.html`, `portal_rma_list.html`, `portal_rma_detail.html`,
`portal_rma_new.html`, `portal_shipment_detail.html` — 12 templates —
plus `base_supplier_portal.html`, `supplier_portal_home.html`,
`supplier_portal_pos.html`, `supplier_portal_po_detail.html`,
`supplier_portal_invoices.html`, `supplier_portal_invoice_detail.html`,
`supplier_portal_invoice_new.html`, `supplier_portal_rfqs.html`,
`supplier_portal_rfq_detail.html`, `supplier_portal_login.html`,
`supplier_portal_register.html` — 11 more; 23 templates total, routed at
`/portal/` and `/supplier-portal/`). The first external-facing surface in
this series — every prior pass translated pages only employees see.
`base_portal.html`/`base_supplier_portal.html` are their own standalone
base templates (not `base.html`), had zero i18n infrastructure before
this pass (no `{% load i18n %}`, no `<html lang>`, no language switcher),
and are used by non-employee customer/supplier accounts with their own
separate login systems — so this pass had to add the switcher itself
(same `{% get_available_languages %}` / `set_language` form as
`base.html`'s, adapted to the portal header's `.btn-sm-nav` styling)
before any translated content on those pages would be reachable by a
real portal user. `portal_login.html`/`portal_register.html` and their
supplier-portal counterparts extend a third base (`base_card.html`,
shared with the already-translated `home.html`) which itself carries no
i18n either — same pattern, each child just adds its own `{% load i18n %}`.
209 unique strings across 5 languages, marked up by two parallel
subagents (one per portal, working from the established conventions
verbatim) and then centrally reviewed, makemessages'd, fuzzy-stripped,
translated, and verified by hand — the same division of labor first used
for the ATS/Benefits/Offboarding cluster. Both subagents' work checked
out clean on review (`manage.py check`, full diff read), with a few
small polish fixes applied afterward: a no-op `{% blocktrans %}` wrapping
a bare variable with no literal text (`supplier_portal_po_detail.html`/
`supplier_portal_rfq_detail.html`'s page titles) collapsed back to a
plain variable, and two "*"-suffixed required-field labels
(`supplier_portal_invoice_new.html`) moved the asterisk inside the
`{% trans %}` string to match the established `"Due Date *"`-style
convention instead of concatenating it outside — cosmetically identical
output, but the inside-the-string form is what lets a future required
field named the same thing merge onto the existing translation instead
of creating a near-duplicate msgid.

Two real bugs found and fixed in this pass, both surfaced by translating
content that was previously invisible in English:
- `portal_shipment_detail.html`'s tracking timeline renders labels built
  in Python (`customer_portal_core.get_tracking_events()`:
  "Shipping Label Created", "Picked up by {carrier}", "In Transit", "Out
  for Delivery", "Shipment Cancelled"), not in the template — the
  now-familiar non-template-rendered-string gap first hit by `menus.py`'s
  `DASHBOARD_DEPARTMENTS` and the WO/SO pass's `*_STATUS_ACTION_LABELS`.
  Fixed by wrapping each with `gettext_lazy` and switching the
  `f"Picked up by {carrier}"` f-string to `_("Picked up by %(carrier)s")
  % {"carrier": carrier}` (an f-string can't be lazily translated — the
  interpolation has already happened by the time gettext would see it).
  `tests/test_customer_portal_core.py`'s `assert events[0]['label'] ==
  'Shipping Label Created'` still passes unchanged — Django's lazy
  translation proxy compares equal to a plain `str` in the active
  (default English) locale, confirmed by re-running that test file
  specifically before trusting it more broadly.
- `portal_rma_list.html`'s new `{% trans "RMA #" %}` column header
  exact-matched an **already-existing but wrong** translation: `"RMA #"`
  was first marked up in the Production department pass
  (`prod_returns_list.html`/`prod_returns_reports.html`) and had been
  mistranslated as the equivalent of "Order" in **all five languages**
  the entire time (es "Pedido", fr "Commande", de "Bestellung", pt
  "Pedido", nl "Bestelling") — invisible on those two pages since their
  adjacent "Order" column (`{{ r.so_number }}`) doesn't sit right next to
  it, but immediately obvious on the portal list page where "RMA #" and
  "Order" are neighboring columns and both rendered as literally the same
  word. Fixed to "N.º de RMA" / "N° RMA" / "RMA-Nr." / "N.º da RMA" /
  "RMA-nr." (keeping the RMA acronym itself untranslated, matching NCR/
  CAPA/PO/SO/WO precedent) across all 5 `.po` files — this also
  retroactively corrects the two Production-department pages that had
  been shipping the wrong label since that pass. A reminder that
  exact-msgid-text reuse, while usually the right behavior (it's what
  makes the WO/SO and ESS passes' high merge rates possible), can also
  propagate a wrong translation silently into a brand-new page — worth a
  quick sanity read of what a surprisingly-already-translated string
  actually says before trusting the merge, not just checking that it's
  non-blank.

Full suite 3475 passed (unchanged), `manage.py check` and `ruff check .`
clean, `msgfmt --check` clean on all 5 files, zero fuzzy/blank entries.
Verified end-to-end against the real dev server logged in as both a real
customer and a real supplier portal account (reset via a narrowly-scoped
`UPDATE ... WHERE id = <n>` on the single existing sample login row for
each, not a blanket update): the customer portal's dashboard, an order's
detail page, Returns list (confirmed the "RMA #" fix renders as a
distinct column from "Order"), and the New Return form in Spanish; the
supplier portal's dashboard, a PO's detail page (confirmed "Print / Save
PDF", the acknowledge-order form, and the line-items table), and an
RFQ's detail page (confirmed the "Update Quote" button rendering for an
item with an existing quote) in French and German — including confirming
the newly-added language switcher itself lists and switches between all
6 languages from within the portal header, not just the main app.

Also translated: the entire **WMS (Warehouse Management)** feature
(`wms_warehouse_list.html`, `wms_bin_list.html`, `wms_bin_detail.html`,
`wms_bin_new.html`, `wms_putaway_rule_list.html`, `wms_pick_list_list.html`,
`wms_pick_list_detail.html`, `wms_wave_list.html`, `wms_wave_detail.html`,
`wms_pack_station.html`, `wms_ship_confirm.html`, `wms_receive.html`,
`wms_transfer_list.html`, `wms_transfer_detail.html`, `wms_transfer_new.html`,
`wms_rfid_reader_list.html`, `wms_rfid_tag_list.html`,
`wms_rfid_tag_detail.html` — 18 templates, routed at `/wms/`, all extending
`base.html` directly — no separate base template needed this time, unlike
the Portals pass). Split across two parallel subagents (locations/picking
vs. fulfillment/RFID, ~9 files each) working from the same conventions,
then centrally reviewed, makemessages'd, fuzzy-stripped, translated, and
verified — same pipeline as the Portals pass. 154 unique strings across 5
languages. Both subagents' diffs checked out clean on review; one caught
its own mistake mid-edit (`wms_wave_list.html`'s quoted-status empty-state
split briefly dropped the `.empty-state` wrapper div, fixed before
finishing) and one hand-rolled pluralization anti-pattern
(`{{ x|length }} order line(s)`) was converted to a proper
`{% blocktrans count %}` in `wms_receive.html`.

**Found a genuine `makemessages` extraction bug, distinct from every
prior escaping gotcha in this file** — and this one is NOT a mistake in
how the translation pipeline was *used*, it's a real gap in what
`makemessages` can correctly *parse*: `wms_putaway_rule_list.html`'s
placeholder hint used backslash-escaped quotes matching the tag's own
delimiter — `{% trans 'e.g. \'raw material\' or \'A\'' %}` — to embed
literal apostrophes inside a single-quoted `{% trans %}` argument. This
is **not** the already-documented "backslash doesn't work for a
non-matching quote" gotcha (that one is about trying to escape a
different quote character than the delimiter, and produces a leaked
literal backslash); this is the delimiter's *own* quote character,
correctly escaped, and it renders **perfectly correctly at runtime** —
confirmed by rendering the template directly (`{{ ... }}` → `e.g. 'raw
material' or 'A'`, exactly as intended, no stray backslash). The failure
is specific to *extraction*: `makemessages` mis-tokenized the argument
and silently produced a garbage 3-character msgid (`"e.g. \\"` — "e.g. "
plus a bare escaped backslash) instead of raising an error, meaning the
real string was **never added to the catalog at all** in any language —
it would have shipped as permanently-untranslated English with no trace
in any `.po` file, and no warning from `manage.py check`, `msgfmt
--check`, or the test suite, since a missing catalog entry isn't a
syntax error to any of those tools. The fix was to stop escaping
entirely: since the argument only contains apostrophes and the tag
itself is nested inside a *double*-quoted HTML attribute
(`placeholder="..."`), switching the `{% trans %}` argument to
double-quotes (`{% trans "e.g. 'raw material' or 'A'" %}`) needs no
escaping at all — matching the IT department pass's established finding
that Django's own tag/HTML-attribute quote nesting doesn't require
escaping, and additionally confirming that finding extends to
*extraction*, not just runtime rendering. Re-ran `makemessages` after
the fix and confirmed the full, correct string (`"e.g. 'raw material' or
'A'"`) was extracted this time. **Worth a standing checklist item**:
after adding any escaped-quote `{% trans %}`/`{% blocktrans %}` argument,
check the `.po` diff for a suspiciously short or truncated new msgid
before translating it — `msgfmt`/`manage.py check`/pytest all stay green
on a silently-dropped string, so eyeballing the extracted text is the
only thing that catches it.

Full suite 3475 passed (unchanged), `manage.py check` and `ruff check .`
clean, `msgfmt --check` clean on all 5 files, zero fuzzy/blank entries.
Verified end-to-end against the real dev server: Bin Master (confirmed
the corrected placeholder text renders as real apostrophes, not a stray
backslash), Put-Away Rules, Receive & Put-Away, Wave Picking, Warehouse
Transfers + a completed transfer's detail page, RFID Readers, RFID Tags
+ a real tag's detail page (confirmed the embedded-quote "still here"
heartbeat sentence), in Spanish, French, and German with real sample
data, no console or server errors.

Also translated: the **ABC (Activity-Based) Costing** feature
(`abc_activity_list.html`, `abc_activity_new.html`, `abc_activity_detail.html`,
`abc_product_output.html`, `abc_report.html` — 5 templates, routed at
`/gl/abc-costing/`). Small enough to do by hand rather than delegating —
44 unique strings across 5 languages, all simple except one
`{% blocktrans count %}`-free `%(pct)s%%` variance-threshold sentence
(the bare-`%`-gets-doubled-to-`%%` gotcha first documented in the Payroll
pass, confirmed here too: `msgfmt --check` and a live `% {'pct': ...}`
substitution both came back clean). Caught and fixed a bare
`{{ x|default:"no driver UOM set" }}` fallback bug in
`abc_activity_detail.html` (same class as every prior pass) — expanded to
the standard `{% if %}/{% else %}/{% trans %}` form, but split into two
full independent `{% blocktrans %}` sentences (one with the UOM, one
without) rather than trying to interpolate the fallback text mid-sentence,
matching the "each branch is a complete, natural sentence" precedent from
the IT Asset Depreciation Summary. Full suite 3475 passed (unchanged),
`manage.py check` and `ruff check .` clean, `msgfmt --check` clean on all
5 files, zero fuzzy/blank entries. Verified end-to-end against the real
dev server: Activity Cost Pools list, a real activity's detail page
(confirmed both the with-UOM and no-UOM-set variants), the New Activity
form, the ABC vs. Traditional report (confirmed the `%(pct)s%%` sentence
renders as a real single `%`), and a product's ABC output-quantity page,
in Spanish, French, and German with real sample data, no console or
server errors.

Also translated: **Personnel's remaining named links** — Employees
(`people_list.html`, `people_detail.html`, `people_form.html`), Time Off
(`time_off_list.html`, `time_off_detail.html`, `time_off_form.html`),
Skills Matrix/Workforce Analytics (`skill_list.html`, `skill_new.html`,
`skill_requirements.html`, `skills_matrix_summary.html`,
`workforce_analytics.html`, `headcount_plan_new.html`), plus two detail
pages reached only from those (`employee_employment_dates.html`,
`employee_gap_detail.html`) — 14 templates. This closes the "translate
the link, not yet the target" gap the Personnel core pass explicitly
named as still open — Personnel now has **zero** remaining untranslated
templates of its own, core and long-tail cluster alike, unlike most other
departments in this series which still carry at least one deliberately-
excluded sub-cluster (Purchasing's Consignment/Supplier-Portal/Scorecard,
Maintenance's APM/Predictive-Maintenance, Sales' Demand Forecast). Marked
up by two parallel
subagents (Employees & Time Off vs. Workforce Planning), reviewed and
translated centrally — same pipeline as every batch since Portals. 82
unique strings across 5 languages. Both subagents' diffs checked out
clean; the only fix needed was cosmetic, not a bug — `workforce_analytics
.html`'s tenure/headcount-trend hint was split into two separate
`{% trans %}` tags at an em-dash where it's actually one continuous
sentence, joined into a single `{% blocktrans %}` for better translation
quality (a translator working from two disconnected fragments can't see
they're one sentence). Two bare `default:"literal english"` fallback
bugs caught and fixed, continuing the class first found on IT's Network
Device page: `people_detail.html`'s `"No title on record"` and
`employee_gap_detail.html`'s `"No job title on file"` (the latter
embedded in a dynamic `menu-title` line with a literal " — " separator,
left un-wrapped per the established "data fields + literal separator"
precedent). Full suite 3475 passed (unchanged), `manage.py check` and
`ruff check .` clean, `msgfmt --check` clean on all 5 files, zero fuzzy/
blank entries. Verified end-to-end against the real dev server: Employee
Directory + a real employee's detail page (confirmed the "No title on
record" fix), Time-Off Requests + a real request's detail page, Skills,
Skills Matrix (confirmed the two-sentence description), Job Requirements,
and Workforce Analytics (confirmed the tenure/headcount hint now renders
as one continuous sentence with a real line break, not two disconnected
fragments), in Spanish, French, and German with real sample data, no
console or server errors.

Also fully translated: the entire **Inventory, Lots, BOM, and MRP**
feature set (`inventory_dashboard.html`, `inventory_detail.html`,
`inventory_list.html`, `inventory_new.html`, `lot_detail.html`,
`lot_list.html`, `lot_new.html`, `bom_detail.html`, `bom_explode.html`,
`bom_list.html`, `mrp_home.html`, `mrp_plan.html`, `mrp_release.html`,
`mrp_safety_stock.html` — 14 templates, the eighteenth "whole feature
set" pass and the first to span four related-but-distinct feature areas
in one batch rather than one department, since Inventory/Lots/BOM/MRP
share the same product-master data and are cross-linked constantly
(a BOM's components link to Inventory detail pages, MRP plans link back
to BOM). Marked up by two parallel subagents (Inventory+Lots vs.
BOM+MRP), reviewed and translated centrally — same pipeline as every
batch since Portals. 169 unique strings across 5 languages (163 simple
+ 6 plural), translated by two further parallel agents split by string
count rather than by file, each producing all 5 languages together per
string for terminology consistency.

Introduced a new `{{ d }} d` / `{{ d }} days` lead-time abbreviation
pattern (`{% blocktrans with d=... %}`), reused across `bom_detail.html`,
`bom_explode.html`, `mrp_plan.html`, and `mrp_safety_stock.html`, so each
language can supply its own short unit abbreviation rather than the
literal English "d". Two `|pluralize` anti-patterns converted to proper
`{% blocktrans count %}` blocks, continuing the class first found in the
Production pass: `inventory_list.html`'s "N product(s)" footer and
`lot_list.html`'s "N lot(s) expiring within 30 days" banner.
`mrp_release.html` needed the trickiest pluralization handling in this
series so far — two *independent* counts in one sentence ("Released N
Work Order(s) and M Purchase Order(s)"), split into two separate
`{% blocktrans count %}` blocks joined by a plain `{% trans "and" %}`
rather than one combined block, since gettext plural forms only support
a single counting variable per block.

**A genuine cross-context mistranslation bug was found and fixed,
the same class as the Portals pass's "RMA #" bug**: the bare English
word "Make" is ambiguous between "manufacturer brand" (as in
`it_asset_list.html`'s IT Asset "Make" column, already translated
Marca/Marque/Marke/Marca/Merk from the IT department pass) and "produce
in-house" (this batch's `item_type=make` filter/dropdown options in
`inventory_list.html`, `inventory_detail.html`, `inventory_new.html`).
Because gettext keys its catalog by exact source text with no notion of
surrounding context, the new item_type usage silently inherited the
IT Asset translation in all 5 languages — French rendered the "Make"
inventory filter as "Marque" (brand), not "Fabriquer" (to produce).
Caught by inspecting the rendered French filter bar directly rather
than trusting a passing test suite (this class of bug produces no
syntax error, no blank/fuzzy entry, and no test failure — the string
*is* translated, just to the wrong word). Fixed with Django's
`{% trans "Make" context "item_type" %}` tag, which creates a separate
`msgctxt`-scoped catalog entry independent of the IT Asset one; verified
the IT Asset page still renders "Marque"/"Marque"/"Marke"/"Marca"/"Merk"
unaffected before translating the new context-scoped entry as a verb
infinitive to match the existing "Buy" → Comprar/Acheter/Kaufen/
Comprar/Kopen pattern (Fabricar/Fabriquer/Herstellen/Fabricar/Maken).
Worth a standing checklist item alongside the dotted-blocktrans-variable
and bare-`default:"literal"` checks from prior passes: before trusting
an exact-msgid auto-merge, grep the new template's own words for
generic single-word labels ("Make", "Type", "Status") and spot-check
one non-English rendering of each, since ambiguous English homographs
are exactly the case ordinary syntax/blank-entry checks can't catch.

Full suite 3475 passed (unchanged), `manage.py check` and `ruff check .`
clean, `msgfmt --check` clean on all 5 files, zero fuzzy/blank entries
confirmed programmatically both before and after a same-session merge
with the Personnel batch (PR #250, merged concurrently — both batches
touched `locale/*/LC_MESSAGES/django.po`, requiring a conflict
resolution: rather than a manual line-level `.po` merge, the cleaner
fix was taking `main`'s post-merge catalog as the base, re-running
`makemessages` to re-extract this batch's own new strings fresh against
it, and re-applying the same saved translation dictionary — safer than
resolving a multi-thousand-line textual diff by hand). Verified
end-to-end against the real dev server, in French with real sample
data: the Inventory Dashboard, Inventory list (confirmed the "N
products" plural and the "Fabriquer"/"Acheter" filter fix, and that
`it_asset_list.html`'s unrelated "Marque" column was unaffected), a
real product's Inventory detail page (confirmed the item-type edit
dropdown's context-scoped translation), Lot Tracking list, a BOM
detail page (confirmed "Composants (2)" and the untranslated literal
"BOM" in the page title, correct per the BOM/MRP-stay-literal
convention), the MRP Home page (confirmed the full demand-source/
scheduled-receipts/safety-stock info-card sentence), and — via direct
`gettext()` calls activating all 5 locales — that all 6 multi-line
`{% blocktrans %}` strings in this batch (the BOM explosion quantity
line, the inventory transaction-type hint, the MRP run/release/
safety-stock explanatory paragraphs) render with real line breaks, not
literal `\n` escapes, continuing the runtime-verification habit
established after the WO/SO pass's double-escape bug. No console or
server errors.

Also fully translated: the entire **Administration** section
(`approval_rule_list.html`/`_new.html`/`_edit.html`, `webhook_list.html`/
`_new.html`/`_edit.html`, `currency_list.html`, `audit_log.html`,
`audit_record.html`, `user_roles.html`, `data_governance_dashboard.html`,
`retention_policy_edit.html`, `periods.html`, `fixed_asset_list.html`,
`fixed_asset_detail.html` — 15 templates, the nineteenth "whole
section" pass, matching the by-now-standard "translate the link, not
yet the target" gap: the sidebar's ADMINISTRATION section header and
all 7 of its nav labels (Rôles utilisateurs, Journal d'audit,
Immobilisations, Devises, Règles d'approbation, Webhooks, Gouvernance
des données) were already translated from `base.html`'s original core
pass, but every page they link to was still English-only). Marked up
by two parallel subagents (Approval Rules/Webhooks/Currency vs.
Audit/Roles/Governance/Periods/Fixed-Assets), then translated by two
further parallel agents split by string count. 194 unique strings
across 5 languages (193 simple + 1 plural), the 12 calendar month
names among them (no prior translation existed for any of them
anywhere in the app, confirmed via grep before assuming so).

**Two confirm-dialog fragment-concatenation bugs caught in review and
fixed before translating**, the same quality issue the Personnel-core
pass first flagged for a static paragraph (a translator working from
two disconnected fragments can't produce correct grammar) but which
had not previously been checked for JS `confirm()` strings built from
an `{% if %}/{% else %}` verb plus a shared suffix:
`approval_rule_edit.html` and `webhook_edit.html` had each built their
Deactivate/Activate confirm as `{% if x %}{% trans "Deactivate" %}
{% else %}{% trans "Activate" %}{% endif %} {% trans "this rule?" %}`
— concatenating a bare verb with a shared tail rather than translating
one complete question per branch. Fixed to two full independent
`{% trans %}` calls each (`"Deactivate this rule?"` /
`"Activate this rule?"`), matching the pattern the other subagent's
files (`retention_policy_edit.html`, `currency_list.html`) already got
right on the first pass — worth a standing checklist item alongside
the dotted-blocktrans-variable and bare-`default:"literal"` checks:
grep any new `confirm()` string for an `{% if %}...{% endif %}`
sitting *next to* (not fully wrapping) a `{% trans %}`, since that
shape is exactly this fragment-gluing anti-pattern.

**A real, independently-caught bug in `fixed_asset_detail.html`'s Log
Event form**: its 11 `<option>` tags had no `value=` attribute, so the
browser submits whatever text is *displayed* as the field's value —
translating the display text without also pinning an explicit
`value="purchased"` etc. would have silently changed what gets POSTed
once a non-English locale was active (a French user's "Acheté" would
have been stored as the event type instead of "purchased"). Fixed by
adding explicit lowercase `value` attributes matching the original
English text, translating only the display labels — the same
data-integrity class of gotcha as the Engineering pass's dotted-lookup
`blocktrans` bug (a translation-marking change silently breaking a
data path is worse than one breaking a translation catalog, since
nothing red-flags it: `manage.py check`, `msgfmt --check`, and the
test suite all stay green).

**Two real, pre-existing (non-i18n) bugs found while browser-verifying
this batch, both fixed in this same PR since they directly blocked
verifying the very pages being translated** — a departure from this
series' usual "flag but don't fix" precedent for unrelated bugs
(Purchasing's `/purch/reports/` table-name bug, Sales' `get_item`
filter bug), justified here because both fixes were small, low-risk,
and left the page silently broken/wrong rather than merely undiscovered:
1. `fixed_asset_list.html`'s KPI row read `summary.total_count` /
   `summary.active_count` / `summary.total_annual_dep`, but
   `fixed_asset_core.get_fixed_asset_summary()` actually returns
   `count` / `active` / (no `total_annual_dep` key at all) — a
   longstanding key-name mismatch that Django's template engine
   silently renders as blank rather than erroring, so the "Total
   Assets" and "N active" KPIs have always shown blank, and "Annual
   Depreciation" was blank because the underlying total was never
   even computed. This i18n pass's `{% blocktrans count %}` conversion
   of the "N active" sub-label is what surfaced it as a hard
   `TemplateSyntaxError: 'counter' argument to 'blocktrans' tag must
   be a number` 500 instead of silent wrongness, since blocktrans
   validates its counter is numeric — unlike a bare `{{ }}` var, it
   can't silently swallow a missing key. Fixed by correcting the two
   template variable names to match the real dict keys, and adding
   `total_annual_dep` to `get_fixed_asset_summary()`'s return value
   (summing the module's own already-tested `calc_annual_depreciation()`
   per asset — the same aggregation pattern that function already uses
   for `total_book_value`/`total_accumulated_depreciation`, not new
   business logic), plus one new assertion in the existing
   `test_get_fixed_asset_summary_aggregates_across_assets` test.
2. **The sidebar's "Currencies" link has been completely unreachable
   since it was built** — `{% url 'currency_list' %}` resolved to
   `/admin/currencies/`, which `manufacture/urls.py`'s
   `path('admin/', admin.site.urls)` (registered first, ahead of
   `include('manufacturing.urls')`) swallows before Django ever tries
   the app's own URLconf, silently redirecting every visitor to the
   Django admin login screen instead. This was already known and
   explicitly documented as deferred in `COMPETITIVE_GAP_ANALYSIS.md`'s
   2026-07-17 Approval Rules entry ("verified this is pre-existing and
   not new... left that as a separate, already-there issue") — the
   Approval Rules pages were deliberately routed at `/approval-rules/`
   (no `/admin/` prefix) specifically to avoid the same trap. Fixed
   here, with the user's explicit go-ahead, by moving `currency_list`
   to `/currencies/`, matching that same no-`/admin/`-prefix
   convention (`/approval-rules/`, `/price-lists/`, `/sampling-plans/`,
   `/rfq/`) — updated the URL pattern, `base.html`'s active-link check,
   `currency_list.html`'s own toolbar self-link (now `{% url %}`
   instead of a hardcoded path), and the `/currencies/` reference in
   `docs/user-guide/00-getting-started.md`.

Full suite 3475 passed (+0 net — one new assertion added to an
existing test, no new test functions), `manage.py check` and
`ruff check .` both clean, `msgfmt --check` clean on all 5 `.po`
files, zero fuzzy/blank entries confirmed programmatically. Grepped
every generic single-word label reused via exact-msgid auto-merge
(Base, Success, Failed, Assigned, Sold, Note, Details, Year, By,
Signed, Maintenance, Purchased, Deployed, Repaired, Relocated,
Disposed) for the "Make"-style cross-context mistranslation risk the
Inventory/BOM/MRP pass's fix established as a standing checklist item
— all merges checked out semantically correct, no new instance of that
bug class this pass. Verified end-to-end against the real dev server,
in French with real sample data: Approval Rules list + a rule's edit
page (confirmed the fixed Deactivate/Activate confirm dialogs render
as complete sentences), Webhook Subscriptions list + an edit page
(same fix), **Currency Management at its corrected `/currencies/` URL**
(confirmed the sidebar link now navigates there instead of the Django
admin login, real data — base currency, 12 active currencies, full
table), Audit Log + a record's history page, User Role Management,
Data Governance, Period Management (confirmed all 12 translated month
names in the dropdown), and **Fixed Assets** (confirmed the KPI-row
crash is fixed and all four KPI cards — including the two previously
always-blank ones — now show correct real numbers), plus direct
`gettext()` calls confirming all 7 multi-line `{% blocktrans %}`
strings in this batch render with real line breaks in all 5 locales.
No console or server errors.

Also fully translated: the **Authentication / MFA** cluster
(`register.html`, `change_password.html`, `forgot_password.html`,
`forgot_password_reset.html`, `home_mfa.html`, `mfa_enroll.html`,
`mfa_settings.html` — 7 pages, plus their shared base template — the
twentieth "whole section" pass and, unusually for this series, the
one with the smallest template count but arguably the highest reach:
every single user hits at least the login page regardless of role or
department, and a non-English-speaking new hire's very first
interaction with the app is `register.html`). Small enough (47
strings) to translate directly by hand rather than delegating, the
first pass since ABC Costing to skip subagent delegation entirely.

**Found `base_card.html` — the shared shell all 7 of these pages (plus
the already-translated `home.html`, the login page) extend — had never
itself been touched by any prior i18n pass**, the same "shared base
template overlooked" gap the Portals batch closed for
`base_portal.html`/`base_supplier_portal.html`: `home.html` loads
`{% load i18n %}` and translates its own blocks independently, but the
"Manufacturing ERP" / "Enterprise Resource Planning" logo text and the
"© {year} Manufacturing ERP" footer live in the *parent* template and
had been rendering in hardcoded English on every single one of these
pages the entire time, undetected because nothing in this series'
per-page verification ever looked above a child template's own
`{% block %}` content. Fixed by adding `{% load i18n %}`, the standard
`<html lang="{% get_current_language as LANGUAGE_CODE %}{{ LANGUAGE_CODE }}">`
attribute, and wrapping the three strings — the year is bound via
`{% now "Y" as cur_year %}` first since blocktrans can't call a
template tag inline, then referenced as a bare context name inside
`{% blocktrans %}` (same rule as `audit_record.html`'s `table_name`/
`record_id`: only *dotted* lookups need explicit `with` binding).
**Also added a language switcher to `base_card.html`** — this whole
flow (login, register, forgot-password, MFA) previously had no way to
pick a language before authenticating at all, unlike every other part
of the app; copied `base.html`'s `{% url 'set_language' %}` form
verbatim and restyled it to fit the centered-card layout (small
top-right dropdown) rather than the app shell's dark toolbar.

Caught and fixed one small layout regression this pass's own
translations caused, before it shipped: `register.html`'s City/State/
Zip row has fixed-width columns (`.csz-row .zip { width: 96px; }`,
sized for the 3-character English word "Zip"), and French's natural
translation "Code Postal" (11 characters) visually overflowed and
truncated inside that field's placeholder text — confirmed via
`preview_inspect`'s bounding-box measurement, not just eyeballing a
screenshot. Fixed by widening that one column to 132px (the other 4
languages' translations — Spanish "C.P.", German "PLZ", Portuguese
"CEP" — all chose short, natural abbreviations and were never at risk;
French has no equally-short idiomatic postal-code abbreviation). Worth
a standing note distinct from every prior "check the rendered text"
verification step in this file: a fixed-width form field sized for the
*English* label is a latent trap for any language whose translation is
longer, and catching it requires actually rendering the page and
checking layout, not just confirming the string translated correctly.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. Grepped the small set of generic single-word labels
reused via exact-msgid auto-merge (Verify, Confirm, Register, Zip) for
the "Make"-style cross-context mistranslation risk — "Confirm" merged
with an existing Sales Order status-action label ("Confirmar"/
"Confirmer"/"Bestätigen"), checked and confirmed both senses ("confirm
this order" / "confirm this password") use the same natural verb in
every language, no bug. Verified end-to-end against the real dev
server, in French with real sample data: the Login page (confirmed
the base-card shell's logo/subtitle/footer are now translated, and the
language switcher works from an unauthenticated session), Register New
Employee (confirmed the Zip-field width fix, screenshot-verified),
Change Password, Forgot Password (confirmed the `<br>`-embedded
two-line subtitle), Reset Password, MFA Settings, and MFA Enroll
(confirmed the two-step numbered instructions and the authenticator-app
proper nouns — Google Authenticator, Authy, 1Password — left
untranslated), plus direct `gettext()` calls confirming both
`<strong>`-embedded and `<br>`-embedded multi-line strings render
correctly with real line breaks and intact tags in all 5 locales. No
console or server errors.

Also fully translated: the entire **Risk Management** feature
(`risk_dashboard.html`, `risk_register_list.html`,
`risk_assessment_list.html`, `risk_audit_list.html`,
`risk_continuity_list.html`, `risk_insurance_list.html`,
`risk_kri_list.html` — 7 templates, the twenty-first "whole feature"
pass, and another instance of the "translate the link, not yet the
target" gap: `/risk/` is linked from the already-translated Legal
Dashboard but had never itself been touched). Marked up by two
parallel subagents (dashboard+register+assessments+audits vs.
continuity+insurance+KRI), translated by hand afterward — small enough
(79 strings, all simple, no plurals) to skip delegating the
translation step, matching ABC Costing/Auth. Both subagents' diffs
checked out clean on review — no bugs, no bare `default:"literal"`
fallbacks, no dotted-blocktrans-variable mistakes.

One correctly-applied precedent worth reconfirming rather than a new
finding: several placeholders needed `{% trans "..." %}` nested
directly inside a double-quoted HTML `placeholder="..."` attribute
(e.g. `placeholder="{% trans "Search risk / category / owner…" %}"`).
Verified against two pre-existing files that already do this
(`it_ticket_list.html`, `wms_putaway_rule_list.html`) before trusting
it, rather than taking the subagents' self-reported precedent claim at
face value — both files genuinely exist and genuinely use this
pattern, confirming Django's tag tokenizer really does resolve `{% %}`
boundaries before the surrounding HTML's own quoting matters (the same
finding the IT department pass made for a single embedded apostrophe,
now reconfirmed for a full nested double-quoted string). Also
translated the Chart.js "No data yet" empty-chart title text inside
`risk_dashboard.html`'s `<script>` block as `'{% trans "No data yet"
%}'`, the same proven-safe pattern used for `confirm()` dialogs
elsewhere (Django renders the tag server-side before the JS ever
reaches the browser) — the first time this series has translated
chart-internal text rather than just chart labels/titles outside the
`<script>` tag.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. Grepped the generic single-word labels reused via
exact-msgid auto-merge (Threshold, Scope, Framework, Finding, Response,
Coverage, Premium, Assessed) for the "Make"-style cross-context
mistranslation risk — "Threshold" merged with `approval_rule_list
.html`'s monetary approval threshold, both senses ("a numeric limit")
compatible in every language, no bug. Verified end-to-end against the
real dev server, in French with real sample data: the Risk Dashboard
(confirmed all 6 KPI cards, both dept-grid rows, and no console errors
after a mid-verification dev-server crash from an unrelated transient
Postgres `tuple concurrently updated` error during autoreload — restarted
cleanly, unrelated to this batch's changes), Risk Register (confirmed
the full New Risk form's labels and the "Faible / Moyen / Élevé"
severity-hint placeholder), Risk Assessments, Compliance Audits,
Business Continuity, Insurance Policies, and Key Risk Indicators — all
7 pages return 200 with correctly translated titles, headings, table
headers, and toolbar navigation.

Also fully translated: **Consignment Inventory** and the **Supplier
Scorecard** (`consignment_list.html`/`_detail.html`/`_new.html`/
`_receive.html`/`_use.html`, `supplier_scorecard_list.html`/`_detail.html`
— 7 templates, the twenty-second "whole feature" pass, and the last two
gaps explicitly named as deferred in the original Purchasing department
pass — everything else on that exclusion list (`/supplier-portal/`) was
already closed by the Portals batch). Marked up by two parallel subagents
(consignment list/detail/new vs. consignment receive/use + both scorecard
pages), translated by hand afterward — small enough (56 strings: 52
simple + 4 plural) to skip delegating the translation step. Both
subagents' diffs checked out clean on review — correct dynamic-title
`{% blocktrans with %}` bindings on `consignment_receive.html`/`_use.html`
(`Receive Stock — {{ num }}` / `Record Usage — {{ num }}`) and
`supplier_scorecard_detail.html` (`{{ name }} — Scorecard`), all four
`{{ x }}...{{ x|pluralize }}` occurrences converted to proper
`{% blocktrans count %}` blocks, raw DB enum values (`{{ s|capfirst }}`
status filters/pills) correctly left untouched, and Chart.js dataset
labels (`'On-Time %'`, `'Fill Rate %'`) deliberately left as bare JS
strings per this pass's own scope decision — translating every chart
legend label was judged unnecessary scope creep, unlike the Risk pass's
"No data yet" empty-state text which the Chart.js precedent was
established for.

**A raw `gettext()` sanity check briefly looked like a doubled-`%%`
bug, but wasn't one** — worth documenting since it could mislead a
future audit: calling `django.utils.translation.gettext()` directly on
the Composite Score explanation msgid returned the literal two-character
`%%` in the output (e.g. "40%% on-time delivery"), which looks exactly
like the double-escape bug class documented earlier in this file. But
`gettext()` alone never performs `%`-substitution — that only happens
inside `{% blocktrans %}`'s own render path, which always applies
`result % data` (even with an empty `data` dict when the block has no
`{% blocktrans with %}` bindings) specifically to collapse a
`python-format`-flagged string's escaped `%%` back to a literal `%`.
Confirmed by rendering the actual template tag via `django.template
.Template(...).render()` instead of calling `gettext()` in isolation —
the real render path correctly produces "40% on-time delivery", and a
live browser fetch of the scorecard list page confirmed the same.
Worth a standing amendment to this file's runtime-verification habit:
a bare `gettext()` call is the wrong tool for confirming `%%`-escaped
strings specifically — render the actual `{% blocktrans %}`/`{% trans %}`
tag (via `Template.render()` or a live page fetch) instead, since
`gettext()` skips the substitution step blocktrans depends on.

Also reconfirmed, not a new finding: French's `n > 1` plural rule (as
opposed to English's `n != 1`) means a zero count renders in the
*singular* form — `supplier_scorecard_detail.html`'s "0 matériau" (not
"0 matériaux") for a supplier with no rated-material samples yet is
linguistically correct per the `.po` file's own `Plural-Forms: nplurals=2;
plural=(n > 1);` header, not a translation bug, confirmed by checking
that header directly rather than assuming English pluralization rules
apply universally.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check` clean
on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. Grepped the generic single-word/short-phrase labels
reused via exact-msgid auto-merge (Qty Used, Composite Score, AP Invoice,
Supplier Detail, no data) for the "Make"-style cross-context
mistranslation risk — all merges are exclusively within this batch's own
7 files, no cross-department collision, no bug. Verified end-to-end
against the real dev server, in French with real sample data:
Consignment Inventory list + New Agreement form, a real supplier
scorecard's list page (confirmed the Composite Score explanation
paragraph renders with real single `%` signs, not doubled), and a real
scorecard's detail page (confirmed the "{name} — Bilan" dynamic title
and both pluralized "N Commande(s)"/"N matériau(x)" KPI sub-labels,
including the French zero-count singular case) — all pages return 200
with correctly translated titles, headings, and labels, no console or
server errors.

Also fully translated: **Asset Performance Management (APM)**,
**Predictive Maintenance**, and **Technician Routes**
(`apm_dashboard.html`/`_criticality.html`/`_asset_detail.html`,
`predictive_maintenance.html`, `technician_route_list.html`/`_new.html`/
`_detail.html` — 7 templates, the twenty-third "whole feature" pass, and
the last of Maintenance's own explicitly-deferred exclusions —
`maint_dashboard.html`'s three links to `/maint/apm/`,
`/predictive-maintenance/`, and `/maint/routes/` were named as
deliberately out of scope in the original 16-template Maintenance pass;
this closes all three at once since they share one health-scoring/
routing feature set). Marked up by two parallel subagents (APM
dashboard+asset+criticality vs. Predictive Maintenance+Technician
Routes), translated by hand afterward — small enough (54 strings, all
simple, no plurals) to skip delegating the translation step.

**One subagent ran an unrequested, destructive `makemessages` sanity
check mid-task and caught its own mistake before it could ship**: to
inspect generated msgids, it ran `manage.py makemessages` with
`--no-location -e html --extension html`, which reformatted
`locale/es/LC_MESSAGES/django.po` and stripped ~9,300 lines of
already-translated content (a destructive flag combination against a
live, populated catalog — not the project's own established
`makemessages -l <code> --ignore=...` invocation). The agent noticed
immediately, ran `git checkout -- locale/es/LC_MESSAGES/django.po` to
fully revert, and reported the incident transparently in its own
summary rather than silently moving on. Independently re-verified via
`git status`/`git diff --stat locale/` before trusting the report — the
revert was clean, zero residual diff. Worth a standing note distinct
from every prior agent-trust finding in this file: a background
subagent given narrow markup-only scope can still reach for a broader
diagnostic tool than the task calls for; the mitigation isn't "don't
let agents run shell commands" (the same session's agents have safely
run `manage.py check`/`render_to_string` dozens of times) but reviewing
`git status`/`git diff --stat` for *every* file touched by a subagent
report, not just the files it says it edited on purpose, before moving
on to the next pipeline step.

Two dotted-lookup blocktrans bindings needed care here, both handled
correctly: `apm_asset_detail.html`'s Recommendation card interpolates
`{{ health.criticality }}` (a dotted lookup) inside one of its three
branches — bound via `{% blocktrans with c=health.criticality %}`; the
same template's lifecycle-cost line interpolates a *filtered*
expression, `{{ health.lifecycle_cost|floatformat:2 }}`, which needs
the identical `with`-binding treatment since a filter isn't a bare
context name either (`{% blocktrans with cost=health.lifecycle_cost
|floatformat:2 %}`) — a filtered-value case this file's dotted-lookup
checklist item hadn't explicitly named before, now added to it.
Reconfirmed, not new: `technician_route_detail.html`'s page_title
`{{ route.mechanic_name }} — {{ route.route_date }}` is pure data with
a literal separator and needs no wrapping at all, matching the
established "data fields + literal separator" precedent; the template's
three repeated `{% if x == 'completed' %}Completed{% elif ... %}In
Progress{% else %}Planned{% endif %}` pill blocks (appearing 3 times
across `technician_route_list.html`/`_detail.html`) are hardcoded
template-literal English per branch and need translating, distinct from
the adjacent raw-enum `{{ s|title }}` status `&lt;select&gt;` options
sitting right next to them in the same files, which stay bare.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. Grepped the generic single-word labels reused via
exact-msgid auto-merge (Health, Stops, Recorded, Failures, Monitor,
Recommendation) for the "Make"-style cross-context mistranslation
risk — all merges are exclusively within this batch's own 7 files, no
bug. Two strings ("Technician Routes", "Predictive Maintenance")
correctly auto-merged with `maint_dashboard.html`'s already-translated
nav-link text from an earlier pass rather than needing fresh
translation, confirmed by their absence from this batch's own blank-
entry list. Verified end-to-end against the real dev server, in French
with real sample data: the APM Dashboard, Asset Criticality, a real
route's detail page (confirmed the KPI labels and the "Planifié"
pill correctly reusing the shared Planned/In-Progress/Completed
catalog entries), a New Route form, and Predictive Maintenance
(confirmed the OEE-report link paragraph renders with the embedded
`<a>` tag intact) — all pages return 200 with correctly translated
titles and labels, no console or server errors.

Also fully translated: **Cycle Counts** and **Sampling Plans**
(`cc_list.html`/`_detail.html`/`_new.html`, `sampling_plan_list.html`/
`_detail.html`/`_new.html` — 6 templates, the twenty-fourth "whole
feature" pass, and two more "translate the link, not yet the target"
closures — Inventory's "Cycle Counts" nav link (`inventory_dashboard
.html`, `inventory_list.html`) and QA's inspection-page hint linking to
"the Sampling Plans page" (`qa_inspection_list.html`/`_detail.html`)
were both already translated, but neither destination had been touched).
Marked up by two parallel subagents (Cycle Count vs. Sampling Plan),
translated by hand afterward — small enough (35 strings, all simple, no
plurals) to skip delegating the translation step.

**`cc_detail.html` needed the most involved `{% blocktrans %}` work in
this series' "translate the link" passes so far**: a "Grouped by
{enum}: {value} — created {date} by {user}" line binding four separate
variables in one block (`gb=cc.group_by|capfirst` — a *filtered*
expression, `gv`, `dt=cc.created_at|date:"Y-m-d H:i"`, `by`), correctly
translating only the connecting words ("Grouped by"/"created"/"by")
while leaving the `gb` enum value itself as a bare interpolation; a
signature-meaning placeholder containing HTML-entity-escaped quotes
(`&quot;...&quot;`, not raw `"` characters) that needed single-quoted
`{% trans '...' %}` nesting; and a "Variance found — awaiting
approval{% if approval.steps %} from {role}{% endif %}." sentence
needing the established conditional-suffix split pattern, with the
role name bound but not translated (it's a person's role-enum value,
same treatment as `pending_step.approver_role` elsewhere on the same
page). Both subagents correctly avoided running `manage.py
makemessages` themselves this time — explicitly instructed not to,
after the previous APM batch's incident — confirmed via `git status`/
`git diff --stat locale/` showing zero changes before either subagent's
markup-only diff was trusted.

**`cc_new.html`'s "Make / Buy" grouping-option label was wrapped as one
complete phrase in a single `{% trans %}` call, deliberately not split
into separate "Make" and "Buy" translations** — both subagents were
told explicitly to do this, since a bare standalone "Make" already
exists in the catalog from the Inventory/BOM/MRP pass's `msgctxt
"item_type"` fix, and reusing that entry (or its untagged pre-fix
sibling) here would have risked reintroducing the same class of
cross-context mistranslation bug. Confirmed correct on review: the
compound phrase is a distinct msgid from bare "Make", no collision.

**A real translation-quality bug was caught during browser
verification, not template review**: "Bin Location" was translated
fresh in this pass, but French rendered as "Emplacement de
l'Emplacement" (literally "Location of the Location") because the
translation was composed without cross-checking this app's own
already-established "Bin" → "Emplacement" glossary entry from earlier
passes. Caught by inspecting the live rendered `&lt;select&gt;` options
in the browser, not by any syntax/blank/fuzzy check (a grammatically
garbled but non-empty translation passes every automated check in this
file's pipeline). Fixed by reusing the exact existing "Bin" translation
for all 5 languages (es "Ubicación", fr "Emplacement", pt
"Localização", nl "Locatie" — German's fresh "Lagerplatz" already
matched by coincidence) rather than composing a new, longer phrase —
since in this app's terminology "Bin" and "Bin Location" mean the same
warehouse-location concept. Worth a standing checklist item distinct
from the "Make"-style cross-context check (which catches *wrong*
reuse of an existing term): before translating a *new* compound label
containing an already-established shorter term as a substring (here,
"Bin" inside "Bin Location"), check whether the established term's
exact translation should just be reused verbatim rather than
independently re-translated, since composing a fresh translation for
the longer phrase can accidentally duplicate a word the shorter term's
translation already covers.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically both before and after the Bin Location fix. Verified
end-to-end against the real dev server, in French with real sample
data: Cycle Counts list + a real count's detail page (confirmed the
four-variable "Groupé par Bin : SAMPLE — créé le ... par ..." sentence
renders correctly with the raw `Bin` enum left untranslated, and the
corrected "Emplacement" column header), a New Cycle Count form
(confirmed the "Fabriquer / Acheter" grouping option and the ABC-class
explanatory paragraph's real single `%` signs), Sampling Plans list,
and a real plan's detail page (confirmed all seven form labels) — all
pages return 200 with correctly translated titles and labels, no
console or server errors.

Also fully translated: **Work Centers** and **Routing**
(`workcenter_list.html`, `workcenter_calendar.html`, `routing_detail
.html` — 3 templates, the twenty-fifth "whole feature" pass, and the
highest-visibility "translate the link, not yet the target" closure in
this series so far — `base.html`'s core sidebar itself links to
`workcenter_list` under Production's "🏭 Postes de travail" entry,
already translated since the very first i18n pass, but every page
behind it was still English-only). Marked up by two parallel subagents
(Work Center list+calendar vs. Routing detail), translated by hand
afterward — small enough (43 strings: 42 simple + 1 plural) to skip
delegating the translation step.

**Introduced a genuinely new pattern for this series: day-of-week
abbreviations.** `workcenter_list.html` uses a compact 2-letter form
(Mo/Tu/We/Th/Fr/Sa/Su) in a read-only calendar-summary cell *and* a
3-letter form (Mon/Tue/Wed/Thu/Fri/Sat/Sun) in its own Add-form
checkboxes — two genuinely different strings needing two separate sets
of `{% trans %}` tags, not one shared set; `workcenter_calendar.html`
reuses only the 3-letter form. Translated each with the target
language's own natural weekday abbreviation convention rather than a
literal transliteration of the English letter count — German and Dutch
both use 2-letter abbreviations as their *natural* form (Mo/Di/Mi/Do/
Fr/Sa/So and Ma/Di/Wo/Do/Vr/Za/Zo respectively), so their "3-letter
slot" translations are identical to their "2-letter slot" ones by
design, not a translation gap; Portuguese's 2-letter slot uses ad hoc
two-character codes (Sg/Te/Qa/Qi/Sx/Sb/Do) since Portuguese has no
standard super-short weekday abbreviation the way Spanish/French/
German do, while its 3-letter slot uses the real standard Portuguese
abbreviations (Seg/Ter/Qua/Qui/Sex/Sáb/Dom). Verified end-to-end in
French rather than by translation-table inspection alone: fetched a
real workcenter's list row (confirmed "Lu Ma Me Je Ve" for its 2-letter
weekday summary) and that same workcenter's calendar page (confirmed
"Lun/Mar/Mer/Jeu/Ven/Sam/Dim" for its 3-letter checkbox labels) side by
side, so the two forms are confirmed genuinely distinct in the
rendered UI, not just in the source `.po` file.

`routing_detail.html` combined three tricky patterns already
established elsewhere in this series, cleanly handled together in one
file for the first time: a dynamic title (`Routing — {{ product.name
}}`), a `{{ x }}...{{ x|pluralize }}` conversion to `{% blocktrans
count %}`, and a `{% blocktrans with %}`-bound acronym sentence ("SKU:
{{ sku }}") where the acronym itself (SKU) stays literal in every
language per the established NCR/CAPA/PO precedent. Both subagents
correctly avoided running `manage.py makemessages` themselves, having
been explicitly told not to after the APM batch's prior incident —
confirmed via `git status`/`git diff --stat locale/` showing zero
changes before either markup-only diff was trusted.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. Grepped the short/generic labels reused via
exact-msgid auto-merge (Seq, Operation, Work Center) for the
"Make"-style cross-context mistranslation risk — all three merged with
`wo_detail.html`'s and `control_plan_detail.html`'s existing uses of
the identical concepts (a routing/operation sequence number, an
operation name, a work center), semantically compatible, no bug.
Verified end-to-end against the real dev server, in French with real
sample data: the Work Centers list (confirmed both weekday-abbreviation
forms as described above), a real workcenter's Calendar page (confirmed
the dynamic "{name} — Calendrier" title), and a real product's Routing
page (confirmed the dynamic "Gamme — {name}" title, the "3 opérations"
plural, and all 5 table headers) — all pages return 200 with correctly
translated titles and labels, no console or server errors.

Also fully translated: **Sensor Readings/Thresholds** and **Batch
Records** (`sensor_reading_new.html`, `sensor_threshold_set.html`,
`batch_record_list.html`, `batch_record_detail.html` — 4 templates,
the twenty-sixth "whole feature" pass, pairing two more small
"translate the link, not yet the target" closures in one batch — the
Predictive Maintenance pass already translated its own "Log Sensor
Reading"/"Set Thresholds" toolbar links, and the Production dashboard
already links to Batch Records, but neither destination had been
touched). Small enough (28 strings, all simple, no plurals) to do by
hand rather than delegating, matching ABC Costing/Auth/Risk
Management/Cycle-Count-Sampling-Plan precedent.

`batch_record_detail.html`'s "Generated {date} by {user}" line needed
an `{% if %}/{% else %}` split rather than a bare `default:"—"`
fallback inside the sentence, continuing the "each conditional branch
is a complete, natural sentence" precedent first established for the
IT Asset Depreciation Summary card — a lone em-dash mid-sentence
("Generated {date} by —") would read as broken in every language,
whereas dropping to a shorter complete sentence ("Generated {date}")
when no `generated_by` value exists reads naturally in all five.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. All 28 new strings are exclusive to this batch's own
4 files — no exact-msgid auto-merge collision risk to check this time.
Verified end-to-end against the real dev server, in French with real
sample data: Batch Records list (confirmed the page title correctly
auto-merging with the Production department's existing catalog entry),
a real batch record's detail page (confirmed the three-variable "Ordre
de Fabrication : ... · Produit : ... · Qté : ..." sentence and the
"Généré le ... par ..." line render correctly together), Log Sensor
Reading, and Set Sensor Thresholds (confirmed both correctly reuse the
`predictive_maintenance.html` toolbar's already-translated link text
for their page titles) — all pages return 200 with correctly translated
titles and labels, no console or server errors.

Also fully translated: the **Costing** feature (`cost_detail.html`,
`costing_product_detail.html`, `costing_valuation_list.html` — 3
templates, another "translate the link, not yet the target" closure:
linked from `routing_detail.html`'s "View Cost Roll" button, translated
in the immediately-prior Workcenter/Routing pass, but never itself
touched). Marked up by two parallel subagents (Cost Detail + Valuation
List vs. the larger Product Valuation Detail page), reviewed and
translated by hand afterward — small enough (39 strings, all simple, no
plurals) to skip delegating the translation step, matching the
ABC Costing/Auth/Risk Management/Cycle-Count-Sampling-Plan/Sensor-Batch
precedent.

**A new kind of intentional-literal-text exception, distinct from every
prior "leave this untranslated" case in this file**: `costing_
valuation_list.html`'s table has a column header that reads, verbatim,
`product.amount` — not a normal English phrase but a raw Python/DB
attribute reference. Initially suspected as a leftover display bug (a
header that should probably read "On Hand"), this was confirmed
intentional by cross-referencing `costing_product_detail.html`, which
uses the identical literal phrase twice more, inline in prose ("On-hand
(product.amount): ...", "...differs from product.amount (...) — some
receipts/issues for this product were recorded through a path that
doesn't create/consume cost layers..."). The whole Costing feature is
about reconciling a raw DB field (`product.amount`) against a
separately cost-layer-tracked quantity, so showing the literal field
name is deliberate technical clarity for the target audience (this
page's likely users already think in terms of the underlying schema),
not a mistake — unlike every previous acronym-preservation case (NCR,
CAPA, MRP, BOM, OEE, RMA, FMEA, WMS, COGS, etc.), this isn't a
recognized industry term, it's a literal code identifier shown to the
user on purpose. Left completely untouched, unwrapped, in all three
occurrences across both files — neither wrapped in its own `{% trans
%}` nor "fixed" into a friendlier label. Both subagents' diffs
confirmed this was followed correctly before any translation work
began.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check` clean
on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically, zero placeholder (`%(name)s`-style) mismatches
between msgid and any of the 5 languages' translations (checked
programmatically for this batch's 39 new strings), and the auto-merged
generic labels this batch reused (Product, Method, Qty, Unit Cost,
Reference, Received, Date, Total Cost, Detail, Inventory) all
cross-checked semantically compatible with their existing catalog
translations — no "Make"-style cross-context mistranslation risk this
time. Verified end-to-end against the real dev server, in French and
German with real sample data: the Standard Cost page for a real
Make-type product (confirmed the dynamic "Coût Standard — Road Bike"
title, the two-piece "Coût Standard Actuel — calculé" heading split,
and the full Cost History table with real rolled-cost rows in both
languages), the Cost Valuation detail page for a product with drift
between its layer-tracked quantity and `product.amount` (confirmed the
⚠ drift-warning sentence renders correctly with both interpolated
values and the literal "product.amount" text intact), and the
Inventory Valuation list page (confirmed the "product.amount" column
header survives literally next to fully-translated sibling headers,
with a real FIFO-method product row) — all pages return 200 with
correctly translated titles and labels, no console or server errors.

Also fully translated: the **Scan (barcode)** feature (`scan_home.html`,
`scan_receive.html` — 2 templates, linked from `base.html`'s own global
header — the "🔍 Scan barcode…" search box and "⬛ Scan" button that
appear on every authenticated page in the app, not just one department's
dashboard — making this a higher-visibility "translate the link, not
yet the target" closure than most prior batches, even though it's the
smallest batch by template count so far). 24 unique strings across 5
languages, all simple (no plurals). Small enough to translate directly
by hand rather than delegating, matching the ABC Costing/Auth/Risk
Management precedent. Barcode prefixes (`WO-`, `PART-`, `PO-`, `RCV-`,
`ASSET-`) and their example codes' numeric/alphanumeric portions stay
untranslated literals (e.g. `e.g. WO-2024-001` translates the "e.g."
but not the code itself), matching the established
acronym/identifier-preservation convention. The empty-state hint
paragraph ("Scan a `<strong>`PO-`</strong>` or `<strong>`RCV-`</strong>`
barcode...") needed one `{% blocktrans %}` preserving both `<strong>`
tags around the two literal prefixes, the same embedded-HTML pattern
established in the Customers/Credit and Sales passes.

**A real, pre-existing, unrelated-to-i18n bug was found while trying to
browser-verify the loaded-PO items table with live data, flagged here
rather than fixed, matching the Purchasing/Sales precedent of leaving
out-of-scope bugs for a separate pass**: `views/_barcode.py`'s
`receive_scan()` strips a literal `"PO-"` or `"RCV-"` prefix off the
scanned code and looks up `purchase_order.po_number = <stripped
value>` — but every real `po_number` in this schema already includes
its own `"PO-"` prefix as part of the stored value (`PO-2026-0001`,
`PO-CORRECTNESS-CHECK-1`, etc.), so stripping a second, redundant `PO-`
before the lookup means the query can never match any real PO — scanning
any genuine PO barcode always falls through to `"PO not found: ..."`,
confirmed live against every sample PO in the dev DB. `tests/
test_barcode_core.py` covers the sibling `scan_lookup`/`resolve_scan_url`
code path (used by `scan_home.html`) thoroughly, but has no coverage at
all for this second, independent prefix-stripping implementation inside
`receive_scan()` itself — the gap that let this ship unnoticed. Verified
the table itself renders and translates correctly by rendering
`scan_receive.html` directly with a mocked `po`/`items` context instead
(confirmed the Description/SKU/Ordered/Received/Status headers and the
Complete/Partial/Pending pill states in both French and German with
real-shaped sample rows) rather than via the (broken) live scan flow.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check` clean
on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically. The auto-merged generic labels this batch reused
(Ordered, Received, Status, Description, Complete, Partial, Pending,
Print Receiving Label) all cross-checked semantically compatible with
their existing catalog translations — no "Make"-style cross-context
mistranslation risk. Verified end-to-end against the real dev server,
in German with real sample data: the Barcode Scanner home page
(confirmed the full prefix-legend table renders with all 5 untranslated
codes and their translated descriptions/examples), and the Receive
Goods scan-session page's empty state (confirmed the
`<strong>`-tag-embedded hint paragraph and the "Unrecognised scan"/"PO
not found" error messages, which are themselves untranslated Python
f-strings from the view — same class of gap as `menus.py`'s
`DASHBOARD_DEPARTMENTS` before it was wrapped in `gettext_lazy`, left
out of scope for this pass since fixing it means auditing every
f-string in `_barcode.py`, not a template-marking change) — no console
or server errors.

Also fully translated: the **Recipes / Formulas** feature
(`recipe_list.html`, `recipe_detail.html`, `recipe_new.html` — 3
templates, linked from `prod_dashboard.html`'s already-translated
"Recipes" toolbar button — another "translate the link, not yet the
target" closure). 24 unique strings across 5 languages, all simple (no
plurals). Small enough to translate directly by hand rather than
delegating, matching the ABC Costing/Auth/Risk Management/Scan
precedent. Status values (`draft`/`active`/`superseded`) driving the
`{% if %}` branches stay bare per the standard raw-enum convention, but
the pill *labels* shown to the user (Draft/Active/Superseded) and the
status-filter dropdown's raw `{{ s|title }}` display both needed
separate handling — the pill labels are literal template text and were
wrapped, while the dropdown's raw enum display was deliberately left
bare, matching the identical dropdown pattern already established
elsewhere (e.g. Cycle Count/QA status filters).

The recipe detail page's dynamic heading — `{{ recipe.name }}
({{ recipe.product_name }}, Rev {{ recipe.revision }})` — needed a
`{% blocktrans with %}` binding all three values; its resulting msgid
(`%(name)s (%(product)s, Rev %(rev)s)`) auto-merged with an
already-correct existing translation elsewhere in the app using the
same "Rev" formatting convention, confirmed compatible before trusting
the merge (the standing "Make"-style cross-context check). The
"Batch size: {{ size }} {{ uom }} · Yield: {{ pct }}%" line and the New
Recipe form's "Yield %" label both contain a bare literal `%`
immediately after a value — `makemessages` auto-escaped both to `%%` in
the `.po` msgid per the established Payroll-pass convention, and both
were confirmed to render as a real single `%` (not a doubled `%%`) via
direct `Template().render()` calls in all 5 languages before trusting
the browser check, continuing the runtime-verification habit
established after the WO/SO pass's double-escape bug.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check` clean
on all 5 `.po` files (including the two `%%`-escaped entries), zero
fuzzy/blank entries confirmed programmatically, zero placeholder
(`%(name)s`-style) mismatches between msgid and any of the 5 languages'
translations. The auto-merged generic labels this batch reused
(Component, UOM, Product, Revision, Name, Status, Detail, Qty Needed)
all cross-checked semantically compatible with their existing catalog
translations — no cross-context mistranslation risk. Verified
end-to-end against the real dev server, in German and French with real
sample data: the Recipes list page (confirmed both the Draft/Active
pill translations and the untranslated raw-enum status filter
dropdown), an active recipe's detail page (confirmed the dynamic
"Paint Batch CORRECTNESS-CHECK (Paint Can, Rev. A)" title, the real
single `%` in "Ausbeute: 95,0%"/"Rendement : 95,0%", the Ingredients
table with a real component row, and the Scale/Release a Batch
section), a draft recipe's detail page (confirmed the empty-ingredients
state, the Add Ingredient form, and the Activate card, all only shown
for `draft`-status recipes), and the New Recipe form (confirmed the
"z. B. Sirupbasis" placeholder and the real single `%` in the "Yield %"
label) — all pages return 200 with correctly translated titles and
labels, no console or server errors.

Also fully translated: the **Discounts & Promotions** feature
(`promo_list.html`, `promo_detail.html`, `promo_new.html` — 3
templates, linked from `so_list.html`'s already-translated toolbar
button — another "translate the link, not yet the target" closure). 23
unique strings across 5 languages, all simple (no plurals). Small
enough to translate directly by hand rather than delegating, matching
the ABC Costing/Auth/Risk Management/Scan/Recipes precedent.

Several `{{ x|default:"literal english" }}` fallbacks needed the
standard `{% if %}/{% else %}/{% trans %}` expansion, continuing the
bug class first found on IT's Network Device page —
`promo.product_name|default:"All products"` and
`promo.customer_name|default:"All customers"` on the list page — since
a bare filter argument can't hold a `{% trans %}` call. The list page's
discount-amount cell ("15% off" / "$10.00 off") needed two separate
`{% blocktrans with val=... %}` blocks, one per `discount_type` branch,
each with a bare literal `%`/`$` immediately after the interpolated
value — `makemessages` auto-escaped the `%` to `%%` in the msgid per
the established Payroll-pass/Recipes-pass convention, confirmed to
render as a real single `%` (not doubled) via direct `Template
().render()` calls in all 5 languages before trusting the browser
check. The "— All products —"/"— All customers —" placeholder
`<option>` text (appearing on both the detail and new-record forms)
is genuine translatable English wrapped in em-dashes, not a
punctuation-only fallback like this codebase's usual `default:"—"`
exemption, so it got the standard `{% trans %}` treatment.

**A pre-existing, harmless inconsistency was left as-is rather than
"fixed" out of scope**: `promo_list.html`'s `page_title` block used a
bare `&` ("Discounts & Promotions") while its `menu-title`/toolbar
uses of the same phrase already used the HTML-entity form ("Discounts
&amp; Promotions") — two different msgids for what reads as the
same English phrase in a browser. Confirmed this exact bare-vs-entity
split already existed in the original untranslated source (not
introduced by this batch's edits), and confirmed via direct DOM
inspection of the already-shipped `so_list.html`'s identical `&amp;`
pattern that translators sidestep any double-escaping risk simply by
translating the entity-form msgid to a natural word ("et"/"y"/"und"
instead of another literal ampersand) — so both forms render correctly
independently, just as two separate catalog entries instead of one
merged entry. Left alone per this series' standing "wrap, don't
rewrite" convention; not a functional bug.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check` clean
on all 5 `.po` files (including the two `%%`-escaped discount-amount
entries), zero fuzzy/blank entries confirmed programmatically, zero
placeholder (`%(name)s`-style) mismatches between msgid and any of the
5 languages' translations. The auto-merged generic labels this batch
reused (Yes, No, Save Changes, Notes, Active, Inactive, Start Date, End
Date, Name, Product, Customer, Home, Status, Detail) all cross-checked
semantically compatible with their existing catalog translations — no
cross-context mistranslation risk. Verified end-to-end against the
real dev server, in French with real sample data: the Discounts &amp;
Promotions list page (confirmed the real "10% de remise" discount cell
and the "Tous les clients" fallback for a promotion with no customer
restriction), a real promotion's detail page (confirmed the Oui/Non
Active dropdown and both "— Tous les produits —"/"— Tous les clients
—" em-dash placeholders), and the New Promotion form (confirmed the
"p. ex. Soldes d'Été" placeholder and both leave-blank hint labels) —
all pages return 200 with correctly translated titles and labels, no
console or server errors.

Also fully translated: the **e-Commerce Connections** feature
(`ecommerce_connection_list.html`, `ecommerce_connection_detail.html`,
`ecommerce_connection_new.html`, `ecommerce_sync_log_list.html` — 4
templates, linked from `so_list.html`'s already-translated toolbar
button and reachable via `prod_shipping_detail.html`'s "Push Shipment
Confirmation" flow too — another "translate the link, not yet the
target" closure, and the largest/most complex of the three candidates
this series identified after the Recipes/Promotions passes). 40 unique
strings across 5 languages, all simple (no plurals) — the largest
single-batch string count since the Costing pass. Small enough to
translate directly by hand rather than delegating, matching the ABC
Costing/Auth/Risk Management/Scan/Recipes/Promotions precedent.

Two `{{ x|default:"literal english" }}` fallback bugs fixed with the
standard `{% if %}/{% else %}/{% trans %}` expansion, continuing the
class first found on IT's Network Device page:
`connection.store_name|default:"Storefront Connection"` (appearing
twice — once in `page_title`, once in the `<h2>` — both needed the
expansion independently since a block/tag can't share a variable
binding across them) and the list page's
`c.sync_endpoint_url|default:"— (queued only)"`, where only the
"(queued only)" parenthetical is real English text needing translation
— the leading em-dash stays a literal separator outside the
conditional, matching the "data fields + literal separator"
precedent.

This batch had the most multi-line `{% blocktrans %}` prose blocks with
embedded straight-quoted phrases of any single pass so far — three
separate paragraphs (the webhook admin-instructions paragraph
interpolating `{{ platform }}`, the "logged as 'queued' instead of
sent" hint, and the New Connection form's near-identical "status
'queued'" hint), plus a fourth, fully static paragraph explaining the
storefront-SKU cross-reference mapping with no variables at all. None
needed backslash-escaping despite the embedded quotes, since (per the
established IT-department/WMS-pass finding) Django's tag tokenizer
resolves `{% %}` boundaries before any surrounding quote nesting
matters — these are template *body* text, not JS strings or HTML
attributes, so straight `"..."` quotes inside a `{% blocktrans %}`
block need no escaping at all. Confirmed all three interpolated/static
paragraphs render with real newlines (not literal `\n`) and with the
embedded quotes intact — including French's own guillemets and
German's „…" low-quote convention, both chosen naturally by the
translations rather than reusing the source's straight quotes — via
direct `Template().render()` calls in all 5 languages before trusting
the browser check, continuing the runtime-verification habit
established after the WO/SO pass's double-escape bug.

Full suite 3475 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check` clean
on all 5 `.po` files (including the three quote-embedded multi-line
entries), zero fuzzy/blank entries confirmed programmatically, zero
placeholder (`%(platform)s`-style) mismatches between msgid and any of
the 5 languages' translations. Raw DB enum values
(`c.platform`/`l.event_type`/`l.direction`/`l.status`) all stay
untranslated per the established precedent — `l.event_type` in
particular reconfirms the exact "deliberately left untranslated"
exception this file already documented for it. The auto-merged generic
labels this batch reused (Back, Home, Date, Detail, Created By, Cancel,
Status:) all cross-checked semantically compatible with their existing
catalog translations — no cross-context mistranslation risk. Verified
end-to-end against the real dev server, in French with real sample
data: the Connections list page (confirmed the real "— (en attente
uniquement)" queued-only fallback for a connection with no sync
endpoint configured), a real connection's detail page (confirmed the
dynamic "Configurez cette URL comme webhook « commande créée » dans
l'administration de Shopify..." paragraph interpolating the real
platform name, the Item Cross-Reference card's fully static
explanatory paragraph, and the empty "Aucun mappage d'article pour le
moment" state), the New Connection form (confirmed both
"(sélectionner)"/"(aucun)" placeholder options and the sync-endpoint
hint paragraph), and the Sync Log page (confirmed two real log rows
with untranslated raw event-type/direction/status enum values sitting
correctly bare next to their translated column headers) — all pages
return 200 with correctly translated titles and labels, no console or
server errors (one transient dev-server crash from the
already-documented `psycopg2.errors.InternalError_: tuple concurrently
updated` autoreload race occurred mid-verification, unrelated to this
batch's changes, resolved by restarting the preview server).

Also fully translated: the **EDI (Electronic Data Interchange)**
feature (`edi_partner_list.html`, `edi_partner_detail.html`,
`edi_partner_new.html`, `edi_850_upload.html`,
`edi_transaction_log_list.html` — 5 templates, linked from
`so_list.html`'s already-translated "EDI" toolbar button and reachable
from Accounting's/Production's 810/856 download links too — another
"translate the link, not yet the target" closure). 25 unique strings
across 5 languages (23 simple + 2 plural). Small enough to translate
directly by hand rather than delegating, matching the ABC
Costing/Auth/Risk Management/Scan/Recipes/Promotions/e-Commerce
precedent. The "EDI 850"/"EDI 855"/"EDI 810"/"EDI 856" document-type
codes stay untranslated literals (same treatment as the barcode
prefixes in the Scan pass), including the raw `l.doc_type` enum
rendered with a literal "EDI " prefix in the transaction log.

**The trickiest single string in this series' history**: the EDI 850
upload success message combines an embedded dynamic link, a pluralized
line count, and an *optional* pluralized "N unmapped" suffix, all in
one sentence — "Created `<a href="/so/{{ id }}/">`{{ num }}`</a>` with
{{ count }} line(s)[, {{ count }} unmapped]." Split into two
independent `{% blocktrans count %}` blocks rather than one combined
block, since gettext plural forms only support a single counting
variable per block (the same two-independent-counts technique
`mrp_release.html` established for "Released N WO(s) and M PO(s)",
here applied to a *conditional* second count rather than an
always-present one) — the first block handles "Created `<a>`...`</a>`
with N line(s)" (embedding the link via a plain `id`/`num` `with`
binding, the same pattern established in the Sales/Consignment/
e-Commerce passes for links inside `blocktrans`), the second,
independently pluralized block handles the optional ", N unmapped"
tail, wrapped in its own `{% if %}`. Verified both the singular
("1 line.") and plural-with-unmapped ("3 lines, 2 unmapped.") render
paths directly via `Template().render()` before ever touching
`makemessages`, confirming the link renders correctly inside the
pluralized block in both forms.

Full suite 3486 passed (+11 from the separately-merged barcode-scan
bugfix PRs #265/#266, unrelated to this i18n-only batch — confirmed by
diffing `tests/` against the pre-EDI-batch commit before trusting the
new count), `manage.py check` and `ruff check .` both clean,
`msgfmt --check` clean on all 5 `.po` files, zero fuzzy/blank entries
confirmed programmatically, zero placeholder (`%(id)s`/`%(num)s`/
`%(counter)s`-style) mismatches between msgid and any of the 5
languages' translations, checked across both the simple and plural
entry sets. The auto-merged generic labels this batch reused
(Customer, Customer:, Status:, Active, Inactive, Manage, Our Product,
Add Mapping, No item mappings yet., Back, Home, Cancel) all
cross-checked semantically compatible with their existing catalog
translations — the "Our Product"/"Add Mapping"/"No item mappings yet."
reuse from the e-Commerce Connections pass in particular confirms this
codebase's cross-reference-mapping vocabulary is now shared cleanly
across both features. Verified end-to-end against the real dev server,
in French with real sample data: the EDI Trading Partners list
(confirmed a real partner row with ISA sender/receiver IDs), a real
partner's detail page (confirmed the Item Cross-Reference card with an
actual mapped part number → product row), the New Trading Partner
form, the Import EDI 850 upload form, and the Transaction Log
(confirmed 5 real log rows spanning EDI 850/855/856/810 with untranslated
raw doc-type/direction values sitting correctly bare next to translated
column headers) — all pages return 200 with correctly translated
titles and labels, no console or server errors.

Also fully translated: a consolidated **long-tail sweep of 37 remaining
templates across 16 small feature clusters** — the largest single i18n
pass in this series by template count, done in one batch rather than
one PR per cluster specifically to avoid the same `locale/*.po` files
being touched by many divergent branches at once (a real problem hit
earlier in this series — see the Inventory/BOM/MRP pass's merge-conflict
note). Clusters: ATP Inquiry (`atp_inquiry.html`), CTP Inquiry
(`ctp_inquiry.html`), Demand Forecast (`demand_forecast.html`), Budget
Dashboard (`budget_dashboard.html`), Capacity Planning
(`capacity_planning.html`), FMEA Risk Register
(`fmea_risk_register.html`), the generic department drill-down menu
(`dept_menu.html`), Carbon Footprint + ESG Dashboard (`carbon_detail
.html`, `esg_dashboard.html`), Configure-to-Order (`cto_product_list
.html`, `cto_options.html`, `cto_configure.html`), Repetitive
Manufacturing Schedule (`repetitive_schedule_list/_detail/_new.html`),
Contacts — the shared Customers/Suppliers template (`contacts_list
/_detail/_new.html`), Shop Floor Data Entry (`sf_dashboard.html`,
`sf_entry.html`, `sf_shift_plan.html` — distinct from the
already-translated `sf_tv.html`/`sf_tv_grid.html` TV-display pair),
Price Lists (`pl_list/_detail/_new.html`), What-If Scenario Planning
(`scenario_list/_detail/_new/_run.html`), Document Control
(`document_list/_detail/_new.html`), and Multi-Entity Companies +
Intercompany + Consolidated Financials (`company_list/_detail/_new
.html`, `intercompany_list/_new.html`, `consolidated_financials.html`).
332 unique strings across 5 languages (330 simple + 2 plural).

**Process departure from every prior pass**: markup was done by 4
parallel subagents (one per cluster-group, ~9 templates each) using the
established conventions verbatim; translation of the resulting 330
blank strings was then done by 5 more parallel subagents (one per
~66-string chunk, each producing all 5 languages together for
terminology consistency), rather than by hand — the string count made
hand-translation impractical for a single-session batch this size. Both
stages were followed by the usual trust-but-verify review: `git diff`
on every markup file, and a msgid-set cross-check confirming the 5
translation chunks' output exactly matched the real blank list (zero
missing, zero extra) before applying.

**A genuine `msgfmt` fatal error was caught before it could ship,
distinct from every prior escaping/duplication gotcha in this file**:
`contacts_list.html`'s search-result count line was marked up as
`{% blocktrans count counter=contacts|length %}{{ counter }}
{{ contact_type }}{% plural %}{{ counter }} {{ contact_type_plural }}
{% endblocktrans %}` — syntactically valid Django, and it even rendered
fine in isolation — but gettext's plural-form validation requires every
placeholder used in msgid_plural to be self-consistent, and this msgid
used `%(contact_type)s` in the singular form while msgid_plural used a
*different* name, `%(contact_type_plural)s`. `msgfmt --check` correctly
rejected this as a fatal error ("a format specification for argument
'contact_type', as in 'msgstr[0]', doesn't exist in 'msgid_plural'")
across all 5 `.po` files. Root cause: `contact_type`/`contact_type_plural`
are pre-computed whole words already selected by the Python view (e.g.
"customer"/"customers") — there was no actual English text being
pluralized by gettext at all, just two different variables being
swapped in, so wrapping it in `{% blocktrans count %}` was never
correct to begin with. Fixed by removing the blocktrans entirely in
favor of plain `{% if contacts|length == 1 %}{{ contact_type }}
{% else %}{{ contact_type_plural }}{% endif %}` — no translation tag
needed since there's no literal text to translate. Worth a standing
checklist item distinct from the dotted-blocktrans-variable check: if a
`{% blocktrans count %}`'s singular and plural branches interpolate
*different* variable names for the same slot (not the same variable
under a shared `with` binding), that's a sign there's no real
English-language pluralization happening and the block should probably
not be a blocktrans at all.

**A second, related bug surfaced only after fixing the first**:
`contacts_detail.html`'s "Recent Sales Orders"/"Recent Purchase Orders"
section heading was built as `{% blocktrans %}Recent {{ order_label }}s
{% endblocktrans %}` — a bare English "s" concatenated directly onto a
template variable, the same untranslatable-suffix anti-pattern
documented in the Production/Maintenance passes for `|pluralize`, except
here there wasn't even a filter, just a literal glued-on letter. Once
`order_label` itself was properly translated (see below), this produced
literally broken output in French: "Commande Client" + "s" cannot
become "Commandes Clients" by string concatenation, since French
pluralizes by changing the noun itself, not appending a Roman letter.
Fixed at the Python level (matching precedent) by adding a
`order_label_plural` context key (`_('Sales Orders')`/`_('Purchase
Orders')`, wrapped in `gettext_lazy` next to `order_label` itself — see
below) and simplifying the template to `{% blocktrans with
lbl=order_label_plural %}Recent {{ lbl }}{% endblocktrans %}` — no
Python-side pluralization heuristic needed at all, since the caller
already knows which literal noun to use.

**The real root cause underlying both of the above, and the reason
`contacts_list.html`/`contacts_detail.html` initially rendered "Suppliers"
in English even after full template markup**: `contact_type`,
`contact_type_plural`, and `order_label` were plain Python string
literals (`contact_type='customer'`, `order_label='Sales Order'`) passed
as template context from 6 call sites in `views/__init__.py`'s
`customer_list`/`customer_new`/`customer_detail`/`supplier_list`/
`supplier_new`/`supplier_detail` — the exact same class of gap as
`menus.py`'s `DASHBOARD_DEPARTMENTS` and the WO/SO pass's
`*_STATUS_ACTION_LABELS` before those were wrapped in `gettext_lazy`.
No template-level `{% trans %}` can ever fix a Python string that's
already plain text by the time it reaches the template — it has to be
wrapped at the source. Fixed by adding `from django.utils.translation
import gettext_lazy as _` to `views/__init__.py` and wrapping all 6
`contact_type`/`contact_type_plural` call sites plus the 2
`order_label` sites (with the new `order_label_plural` added alongside).
Confirmed the module-level `_` import doesn't collide with this same
file's pre-existing local-scope `_, total_fmt = tc_total_hours(...)`
unpacking idiom used in two unrelated functions — a local assignment to
`_` only shadows within that function's own scope, standard Python
behavior, verified by running the full suite afterward. This is a
narrower, more surgical version of the still-much-larger, still-open
`menus.py` `MENU_TREE` gap (hundreds of untranslated Python-string menu
labels, used by `dept_menu.html` for non-full-access users) — noted
here but explicitly left out of scope for this pass, since it's a
separate body of work disproportionate to a template-marking pass.

**One accepted, documented grammatical limitation, not fixed**: French
is the only one of the 5 target languages whose adjectives fully
decline by gender, and the "Recent %(lbl)s" msgid's French translation
("%(lbl)s Récentes") assumed the feminine plural to match "Commandes
Clients" (Sales Orders) — but "Bons de Commande" (Purchase Orders) is
masculine, so the Suppliers-side heading renders as "Bons de commande
Récentes" instead of the grammatically correct "Récents". Confirmed
Spanish/Portuguese ("recientes"/invariant for gender), German
("Letzte", plural-invariant in this construction), and Dutch are all
unaffected, since none of their equivalent adjectives decline by
gender in this position. Not fixed: doing so correctly would require a
separate gendered `msgctxt` variant per consumer noun, disproportionate
to a single cosmetic heading — documented here per this series'
established practice of naming known limitations rather than silently
shipping imperfect grammar unremarked.

Full suite 3486 passed (unchanged — template/locale/view-level Python
string wrapping only, no business logic touched), `manage.py check`
and `ruff check .` both clean, `msgfmt --check` clean on all 5 `.po`
files after the plural-mismatch fix, zero fuzzy/blank entries confirmed
programmatically at every stage of this pass's 3 makemessages
re-runs (initial 332-entry pass, the 4-entry `contact_type` pass after
the `gettext_lazy` fix, and the 2-entry `order_label_plural` pass), zero
placeholder mismatches confirmed across the *entire* catalog (not just
this batch's new entries — 3988 simple msgid/msgstr pairs checked in
every language) both as a scoped and an unscoped sweep, and zero
duplicated-substring corruption signatures found by scanning all 330
translated values for the class of `msgmerge`-continuation-line bug
documented earlier in this file. Verified end-to-end against the real
dev server, in French and German with real sample data, across a
representative sample spanning most of the 16 clusters: ATP Inquiry, a
Capacity Planning report (confirmed the "repos"/day-off translation
against real weekend cells), a real product's Carbon Footprint page,
a real Document Control record's full revision history and
linked-records forms, a real subsidiary's Companies list, a real
Scenario's comparison-run page (confirmed the Make/Buy quantity
translations and a real single `%` after the doubled-`%%` collapse),
Price Lists, the Suppliers and Customers contact lists plus a real
customer's and a real supplier's detail page (confirmed the "Recent
Sales Orders"/"Recent Purchase Orders" fix renders with correct French
grammar on the Customers side), the Shop Floor OEE dashboard (confirmed
the A/P/Q single-letter convention holds), Intercompany Transactions'
GL account-mapping dropdown, a Repetitive Manufacturing Schedule's
production log, the FMEA Risk Register (confirmed the S/O/D column
convention holds), and Consolidated Financials (confirmed the
"Konzern-" German accounting-statement prefix convention applied
consistently across Income Statement and Balance Sheet) — all pages
return 200 with correctly translated titles and labels, no console or
server errors.

Also fully translated: **`menus.py`'s `MENU_TREE`** — the last
remaining i18n gap in the app, and the only one that wasn't a
template. `MENU_TREE` is a Python dict structure (16 departments, up
to 4 levels of nested sub-menus, several submenus like
`_TIME_CLOCK_MENU`/`_MAINT_MENU` factored out and reused by reference
across departments) that backs `dept_menu.html`'s drill-down grid menu
for non-full-access users — a separate rendering path from `base.html`'s
always-present sidebar, which has its own independently-translated
static `{% trans %}` tags and doesn't consume this tree at all. Every
`'title': '...'` value and every `(key, 'Label', target)` tuple's label
across the whole file — 642 distinct strings, 486 of them genuinely new
(156 auto-merged via exact-msgid match with labels already translated
elsewhere, e.g. department names repeated from dashboard tiles) — needed
wrapping in `gettext_lazy`, matching the exact pattern already
established for this same file's `DASHBOARD_DEPARTMENTS` list (wrapped
in an earlier pass) and the Contacts batch's `contact_type`/`order_label`
fix just before this one.

**Mechanical wrap done via a targeted regex script, not by hand or by
subagent, given the extreme structural regularity of the file**: two
patterns — `'title':\s*(STRING)` and `\('[a-z_0-9]+',\s*(STRING)` (the
tuple's key-then-label position) — covering both single- and
double-quoted strings (`"Today's Hours"` needed double quotes to avoid
escaping its apostrophe, handled by the same pattern). The script
skipped `DASHBOARD_DEPARTMENTS`'s 17 already-wrapped entries for free,
since their label position no longer starts with a bare quote character
after wrapping (`_('...')` doesn't match a pattern requiring the next
token to be a quote) — confirmed by an exact accounting check (792 raw
tuple-opening occurrences minus 17 already-wrapped = 775 wrapped by the
script, plus 177 title lines = the reported 486 distinct new blanks
after accounting for reuse across `_TIME_CLOCK_MENU`-style shared
submenus). Verified safe before running: labels are never used as dict
keys or lookup values anywhere in this codebase — `_walk_tree` matches
on the tuple's first element (an id-like slug such as `'clock_in_out'`),
and `WEB_LEAF_URLS`/`DEPT_MENU_KEY` (in `views/__init__.py`) key on
slugs and department *display names*, never on `MENU_TREE`'s own label
strings — so wrapping every label in a lazy translation proxy carries
zero structural risk. Confirmed post-wrap: `ast.parse()` succeeds, the
diff is a clean 953/953 line-for-line swap with zero non-`_(`-containing
added lines and zero double-wrapped `_(_(` occurrences, `manage.py
check`/`ruff check .`/the full test suite (3486) all stay green.

**Translation volume (486 strings) was split across 7 parallel
subagents** (~70 strings each, by department cluster: Time Clock/
Maintenance, Marketing, Shipping/Receiving/Logistics, Personnel/
Onboarding/Customer-Service, Finance/Audit/Multi-Entity/Tax,
Engineering/Quality/IT, Purchasing/Consultants/QA) rather than
delegating markup separately, since there was no markup step here — just
translation of the pre-extracted blank list, the same shape as the
long-tail sweep's translation phase. Given these are short 1-4-word
navigation labels rather than prose, no placeholders/HTML/multi-line
strings appeared anywhere in the batch (confirmed by inspection before
launching), simplifying the translation task relative to every prior
batch in this series.

**Five real cross-chunk terminology inconsistencies caught and fixed
in a dedicated post-translation consistency pass**, a new step for this
series — with 486 strings split across 7 independent agents with no
visibility into each other's output, this class of error (the same
underlying concept translated two different ways in two different
chunks, or one chunk drifting from an established prior-pass term) was
expected and specifically checked for, rather than left to chance:
1. **German "Engineering" collision**: this codebase's Engineering
   department was already established as German "Konstruktion" (from
   an earlier department pass), but the chunk translating "Engineering
   Main Menu"/"Engineering Manager"/"Engineering Budget" independently
   picked "Technik" (a reasonable-sounding but wrong choice — Dutch
   "Techniek" is actually the correct established term for a *different*
   language, which may have primed the same guess for German). Fixed to
   "Hauptmenü Konstruktion"/"Konstruktionsleiter"/"Konstruktionsbudget".
2. **German "Requisition" drift**: "Approved Requisitions"/"Requisition
   History" used a newly-invented "Bestellanforderung" stem instead of
   this codebase's already-established bare "Anforderung" (used in
   "Requisition %(num)s" → "Anforderung %(num)s" from an earlier
   Purchasing-adjacent pass) — fixed to reuse the established stem.
3. **Spanish "Leads" drift**: "Active Leads"/"Lead Reports" used newly
   -invented "Prospectos" instead of this codebase's already-established
   "Clientes potenciales" (from the Sales department pass's "Leads" →
   "Clientes potenciales") — fixed to reuse the established term.
4. **Ampersand inconsistency**: one chunk correctly followed the
   established "natural word beats literal ampersand" convention
   ("Standards & Compliance" → "Normen und Compliance"/"Normen en
   Compliance") while another chunk left two sibling strings
   ("Audit & Compliance", "Compliance & Audit") with a literal `&` in
   German/Dutch — fixed both to the natural-word form for consistency
   with the sibling entries in the same feature area.
5. Reconfirmed, not a bug: German/Dutch consistently keep "Compliance"
   as an established loanword across both chunks that touched it, while
   Spanish/French/Portuguese consistently translate it natively
   ("Cumplimiento"/"Conformité"/"Conformidade") — both choices are
   internally consistent within their own language, just independently
   arrived at twice with the same result, confirming rather than
   contradicting each other.

A sixth, pre-existing inconsistency was found but deliberately **not**
touched: `eng_reports.html`'s already-shipped "Engineering Reports" →
German "Engineering-Berichte" (a literal, untranslated "Engineering"
left in the German string) predates this batch entirely — it's a
different file from an earlier, separately-merged Engineering
department pass, out of scope for a menu-tree-only fix.

Full suite 3486 passed (unchanged — `menus.py`/locale-file work only,
no template or business-logic changes), `manage.py check` and
`ruff check .` both clean, `msgfmt --check` clean on all 5 `.po` files,
zero blank entries confirmed programmatically, zero placeholder
mismatches swept across the *entire* catalog in every language (4478
entries checked per language), zero duplicated-substring corruption
signatures found across all 486 translated values. This was the largest
single fuzzy-match count in this series' history (473, versus the prior
high of 238 for the long-tail sweep) — expected, given hundreds of
short, generic-sounding menu labels ("Reports", "History", "Schedule")
are exactly the shape most prone to `msgmerge` guessing a wrong existing
match; all 473 were blanked via the established
strip-fuzzy-and-replace technique before any translation work began, so
none of the wrong guesses ever reached a written translation. Verified
end-to-end against the real dev server, hitting `/dept/<slug>/` and its
sub-paths directly (this menu is normally only reached by non-full-access
users, but the view has no access restriction of its own — full-access
users can browse it directly) across three languages: German (Marketing
→ Content Management, three levels deep, confirmed the "Konstruktion"
fix on the Engineering department's top-level menu and sub-item),
Spanish (Purchasing's manager/main sub-menus, Legal's five leaf items),
and Dutch (IT's two-level drill-down into Budget & Procurement) — all
pages return 200 with correctly translated titles and menu-item labels,
no console or server errors.

Also fully translated: the entire **Consultants** feature
(`consultant_list.html`, `consultant_detail.html`, `consultant_form
.html`, `consultant_invoice_list.html`, `consultant_invoice_detail
.html`, `consultant_spend_report.html`, `engagement_list.html`,
`engagement_detail.html`, `engagement_form.html` — 9 templates) —
**the last remaining i18n gap in the entire app**, previously
documented across every prior pass in this series as deliberately
excluded by design rather than merely deferred. Closed on explicit
user request after confirming there was nothing else left (a full
`{% load i18n %}` sweep of `manufacturing/templates/*.html` turned up
only these 9 files). Manages external consultants/contractors, their
engagements (consulting contracts with a scope, rate, and date range),
and consultant invoices with itemized time/charges and an approval
workflow — reached from Purchasing/Finance areas. 83 unique strings
across 5 languages (81 simple + 2 plural). Markup was split across 2
parallel subagents (Consultant-prefixed templates vs.
Engagement-prefixed templates); translation of the resulting 83 blank
strings was done directly by hand rather than delegating, the same
threshold this series has used throughout (roughly ≤100 new strings →
hand-translate, more → parallel subagent chunks).

**Trickiest pattern in this batch**: `engagement_detail.html`'s
unbilled-time/unbilled-charges footer needed the established
two-independent-counts technique (first used for EDI's upload-success
message, and `mrp_release.html` before that) — "N unbilled time
entr(y/ies), M unbilled charge(s) on this engagement." combines two
separately-pluralized counts in one sentence, split into two
independent `{% blocktrans count %}` blocks joined by a plain
`{% trans %}` for the shared tail, since gettext plural forms only
support one counting variable per block. Verified both the
zero-count and mixed singular/plural cases render correctly via direct
`Template().render()` before running `makemessages`.

One `default:"literal english"` fallback bug fixed, continuing the
class first found on IT's Network Device page:
`consultant_invoice_detail.html`'s badge showing
`c.supplier_name|default:"Linked Supplier"` couldn't hold a
`{% trans %}` inside the filter argument, so it was expanded to an
explicit `{% if %}/{% else %}` with the fallback branch as its own
complete `{% blocktrans %}` sentence ("External — Linked Supplier"),
matching the "each conditional branch is a complete sentence"
precedent. The `&quot;`-escaped signature-meaning placeholder (`e.g.
&quot;I approve this invoice for payment&quot;`) reused the exact
established pattern from `document_detail.html`, needing no additional
escaping since `&quot;` is already an HTML entity, not a raw quote
character the template engine would try to re-escape.

Full suite 3486 passed (unchanged — template/locale-file work only),
`manage.py check` and `ruff check .` both clean, `msgfmt --check`
clean on all 5 `.po` files, zero fuzzy/blank entries confirmed
programmatically, zero placeholder mismatches across both the simple
and plural entry sets. The auto-merged generic labels this batch
reused (`Print / Save PDF`, `All Statuses`, `Active`, `Inactive`,
`Deactivate`, `Activate`, `Rejected`, `Invoiced`) all cross-checked
semantically compatible with their existing catalog translations — no
cross-context mistranslation risk. Verified end-to-end against the
real dev server, in French and German with real sample data: the
Consultants list (confirmed Internal/External/Ad-hoc badge rendering
with real supplier/personnel links), a consultant's detail page
(confirmed the dynamic "External — linked to supplier Acme LLc."
sentence), an Engagement's detail page (confirmed real time-entry and
charge line items, an existing invoice row, and the two-count
pluralized footer with a real "0 entrée de temps non facturée, 0 frais
non facturé" zero-case), a Consultant Invoice's detail page (confirmed
itemized time/charges, the GL invoice link, and a real approval-history
row), the Spend Report (confirmed all three By-Consultant/By-Engagement
/By-Department tables with real KPI totals and the guillemet-quoted
"—"-means footnote), and the New Consultant form — all pages return
200 with correctly translated titles and labels, no console or server
errors. **This closes out localization coverage for the entire
application** — every template outside Django's own admin interface
and every Python-side navigation label (`menus.py`'s `MENU_TREE`,
closed in the immediately-prior pass) is now translated into Spanish,
French, German, Portuguese, and Dutch.

## Web UI (Django) & menu routing
- **Live-refresh via htmx** (COMPETITIVE_GAP_ANALYSIS.md §6.1 "Modern Frontend," deliberately
  partial — a full SPA rewrite isn't proportionate to this codebase's size). 24 of ~450 templates
  poll a small fragment view every 30s instead of doing a full page reload: `sf_tv.html`,
  `prod_dashboard.html`, `maint_dashboard.html`, `ai_insights_dashboard.html`, `dashboard.html`
  (the main company dashboard), `purchasing_dashboard.html`, `qa_dashboard.html`,
  `sales_dashboard.html`, `it_dashboard.html`, `acct_dashboard.html`, `cs_dashboard.html`,
  `eng_dashboard.html`, `credit_dashboard.html`, `finance_dashboard.html`, `sales_reports.html`,
  `eng_reports.html`, `cs_reports.html`, `sales_performance.html`, `marketing_dashboard.html`,
  `gl_dashboard.html`, `ar_list.html`, `ap_list.html`, `ar_invoice_detail.html`, and
  `ap_invoice_detail.html`. Pattern to
  copy for
  the next page:
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
  `cs_dashboard.html`'s own version (`cs_dashboard_kpis_fragment` polling
  `/cs-dash/kpis-fragment/`) picked the ticket KPI row (Open/Completed/Total 12mo/Completion
  Rate/Avg Resolution/Avg Age Open) plus the Recent Tickets table — a CS manager watching this page
  wants to see a new ticket land or the open count drop without a manual refresh, the same
  "time-sensitive queue" rationale as every prior htmx pass, over the static ticket-trend,
  open-vs-closed, return-status/reason, survey-score, and KB-status charts below it. No
  core-module refactor was needed: `cs_calls_core.get_summary_stats(conn)` and
  `list_tickets(conn)[:8]` were already small, independently-tested functions the full-page view
  already called directly, the same shape as Sales' and IT's no-refactor cases. Full suite passes
  (3460, unchanged — no new core logic), `manage.py check` and `ruff check .` both clean. Verified
  end-to-end via the Django test client: hit `/cs-dash/kpis-fragment/` directly (renders standalone
  with real data — Open Tickets: 8); created a real ticket via `cs_calls_core.create_ticket`,
  re-fetched the fragment, and confirmed it appeared in the Recent Tickets table — then deleted it
  and confirmed it was gone; also confirmed the fragment renders correctly in Portuguese and Dutch
  with an active session in each.
  `eng_dashboard.html`'s own version (`eng_dashboard_kpis_fragment` polling `/eng/kpis-fragment/`)
  picked the KPI row (Active/Planning/Completed Projects, ECRs Pending, Open/Overdue Tasks) plus
  the Recent Projects and Recent ECRs tables — an engineering manager watching this page wants to
  see a new ECR land or a project's status change without a manual refresh, the same
  "time-sensitive queue" rationale as every prior htmx pass, over the static
  project/task-status/priority, ECR-status, engineer-workload, and standards-status charts below
  it. No core-module refactor was needed: `engineering_core.get_eng_dashboard(conn)`,
  `list_projects(conn)[:8]`, and `list_ecrs(conn)[:8]` were already small, independently-tested
  functions the full-page view already called directly, the same shape as Sales/IT/CS's
  no-refactor cases — the fourth dashboard in a row not needing one. Full suite passes (3460,
  unchanged — no new core logic), `manage.py check` and `ruff check .` both clean. Verified
  end-to-end via the Django test client: hit `/eng/kpis-fragment/` directly (renders standalone
  with real data); created a real ECR via `engineering_core.create_ecr`, re-fetched the fragment,
  and confirmed it appeared in the Recent ECRs table — then deleted it and confirmed it was gone;
  also confirmed the fragment renders correctly in Portuguese and Dutch with an active session in
  each.
  `credit_dashboard.html`'s own version (`credit_dashboard_kpis_fragment` polling
  `/credit/kpis-fragment/`) is the first one with no static charts to leave behind at all — the
  entire body past the toolbar/dept-grid (all three KPI-row sections — Credit Accounts,
  Applications, Collections — plus the Credit Accounts/Pending Applications/Open Collections
  tables) is exactly the "manager watches a live queue" content, so the whole thing moved into the
  fragment; the full-page template also needed its first-ever `extra_scripts` block added, just to
  carry the htmx script tag, since this dashboard never had a Chart.js include to begin with. No
  core-module refactor was needed: `credit_core.get_credit_dashboard(conn)`,
  `list_credit_accounts()`, `list_credit_applications()`, and `list_collection_activities()` were
  already small, independently-tested functions the full-page view already called directly (with
  simple list-comprehension filtering for the "pending"/"open" subsets, not raw SQL) — the fifth
  dashboard in a row not needing one. Full suite passes (3460, unchanged — no new core logic),
  `manage.py check` and `ruff check .` both clean. Verified end-to-end via the Django test client:
  hit `/credit/kpis-fragment/` directly (renders standalone with real data — Total Exposure:
  $245,000); created a real credit application via `credit_core.create_credit_application`,
  re-fetched the fragment, and confirmed it appeared in the Pending Applications table — then
  deleted it and confirmed it was gone; also confirmed the fragment renders correctly in Portuguese
  and Dutch with an active session in each.
  `finance_dashboard.html`'s own version (`fin_dashboard_kpis_fragment` polling
  `/fin/kpis-fragment/`) picked the AP KPI row, AR KPI row, and Cash Flow KPI row (Cash Position,
  Projected Balance 13wks, Net Change 13wks) plus the Recent Journal Entries table — the same
  AP/AR/journals content as Accounting's own dashboard (this department shares
  `_ACCOUNTING_DEPT_KEYS`/`finance_core.get_finance_dashboard()` with it) plus a cash-position KPI
  row unique to Finance, over the static 13-week cash-forecast line chart, revenue/expense chart,
  AR/AP aging charts, top-AR-customers chart, and invoice-status-mix chart below it — a
  controller/CFO watching this page wants to see cash position or a new journal change without a
  manual refresh, the same "time-sensitive queue" rationale as every prior htmx pass. No
  core-module refactor was needed: `get_finance_dashboard(conn)`, `get_cash_position(conn)`, and
  `get_cash_forecast_13wk(conn, starting_balance=...)` were already small, independently-tested
  functions the full-page view already called directly — the sixth dashboard in a row not needing
  one. Full suite passes (3460, unchanged — no new core logic), `manage.py check` and `ruff check .`
  both clean. Verified end-to-end via the Django test client: hit `/fin/kpis-fragment/` directly
  (renders standalone with real data — Cash Position: $805,200.00); created a real balanced GL
  journal via `accounting_core.create_journal`, re-fetched the fragment, and confirmed it appeared
  in the Recent Journal Entries table — then deleted it and confirmed it was gone; also confirmed
  the fragment renders correctly in Portuguese and Dutch with an active session in each.
  `sales_reports.html`'s own version (`sales_reports_kpis_fragment` polling
  `/sales/reports/kpis-fragment/`) is the first one that's a period-filtered analytical report
  rather than a fixed-scope department landing dashboard — the whole page (KPI row, Top Customers,
  Top Products) is scoped to whatever `[start, end]` date range the Today/This Month/This
  Quarter/This Year chips or the custom date-range form selected, so the `hx-get` URL carries that
  through as query params read straight from the already-resolved `start`/`end` context variables
  (`hx-get="/sales/reports/kpis-fragment/?start={{ start }}&amp;end={{ end }}"`) rather than a
  fixed path — the fragment view re-runs `sales_core.get_sales_reports(conn, start, end)` for
  exactly the range currently on screen, so a sales manager who leaves "This Month" open sees
  revenue tick up as new orders are confirmed, without the poll silently reverting to a different
  range. Matching the Accounting pass's precedent of grouping all "live" content contiguously, the
  KPI row and Top Customers/Top Products tables (previously separated by the Revenue Trend chart)
  moved together into the fragment, with the chart — left static per every prior pass's
  canvas-redraw-avoidance precedent — now rendered after them instead of between. No core-module
  refactor was needed: `get_sales_reports()` was already the single small, independently-tested
  function backing this page. Full suite passes (3460, unchanged — no new core logic), `manage.py
  check` and `ruff check .` both clean. Verified end-to-end via the Django test client: confirmed
  the `hx-get` URL correctly carries the resolved date range (e.g. `?start=2026-01-01&end=2026-09-02`
  for the "This Year" chip); hit the fragment URL directly (renders standalone with real data);
  created a real confirmed sales order with a line item via `sales_orders_core.create_so`/
  `add_so_item`, re-fetched the fragment for the current month, and confirmed Total Revenue jumped
  from $0 to the order's exact value — then deleted it and confirmed it reverted to $0; also
  confirmed the fragment renders correctly in Portuguese and Dutch with an active session in each.
  `eng_reports.html`'s own version (`eng_reports_kpis_fragment` polling
  `/eng/reports/kpis-fragment/`) is the second one (after Credit) with nothing static to leave
  behind — the Projects-by-Status/ECRs-by-Status/Open-Tasks-by-Priority breakdowns are plain CSS
  bar charts (`.bar-inner` width percentages), not Chart.js canvases, so there's no
  canvas-redraw-avoidance concern at all; the whole page (three status/priority breakdown cards
  plus the Overdue Projects and Recent ECRs tables) moved into the fragment verbatim. The
  full-page template also needed its first-ever `extra_scripts` block, just to carry the htmx
  script tag, matching the Credit dashboard precedent. No core-module refactor was needed:
  `engineering_core.eng_reports()` (aliased `_eng_reports_data` in `views/__init__.py`) was
  already the single small, independently-tested function backing this entire page — the seventh
  dashboard in a row not needing one. Full suite passes (3460, unchanged — no new core logic),
  `manage.py check` and `ruff check .` both clean. Verified end-to-end via the Django test client:
  hit `/eng/reports/kpis-fragment/` directly (renders standalone with real data); created a real
  overdue project (due date in the past, status `in_progress`) via
  `engineering_core.create_project`, re-fetched the fragment, and confirmed it appeared in the
  Overdue Projects table — then deleted it and confirmed it was gone; also confirmed the fragment
  renders correctly in Portuguese and Dutch with an active session in each.
  `cs_reports.html`'s own version (`cs_reports_kpis_fragment` polling
  `/cs/reports/kpis-fragment/?days={{ days }}`) combines both prior patterns at once: like Sales
  Reports, it's a period-filtered analytical report (90 days/6 months/1 year/2 years chips) whose
  `hx-get` URL carries the current `days` value through as a query param so the poll doesn't
  silently revert to a different period; like Engineering Reports, it has nothing static to leave
  behind (no Chart.js canvas anywhere on the page), so the entire KPI-cards/Monthly-Call-Volume-
  table/Open-Tickets-Summary content moved into the fragment verbatim, needing its own first-ever
  `extra_scripts` block just for the htmx tag. No core-module refactor was needed:
  `cs_calls_core.get_summary_stats(conn, days)`, `get_monthly_volume(conn, days)`, and
  `list_tickets(conn, status='open')` were already small, independently-tested functions the
  full-page view already called directly — the eighth dashboard in a row not needing one. Full
  suite passes (3460, unchanged — no new core logic), `manage.py check` and `ruff check .` both
  clean. Verified end-to-end via the Django test client: confirmed the `hx-get` URL correctly
  carries the resolved `days` value (e.g. `?days=180`); hit the fragment URL directly (renders
  standalone with real data — Total Tickets: 25); created a real ticket via
  `cs_calls_core.create_ticket`, re-fetched the fragment, and confirmed Total Tickets incremented
  from 25 to 26 — then deleted it and confirmed it reverted to 25; also confirmed the fragment
  renders correctly in Portuguese and Dutch with an active session in each.
  `sales_performance.html`'s own version (`sales_performance_kpis_fragment` polling
  `/sales/performance/kpis-fragment/`) is the third page (after Credit and Engineering Reports)
  with nothing static to leave behind — both ranking tables (Target Attainment, Revenue from
  Orders) are exactly the "manager watches a live leaderboard" content, no query params or
  Chart.js canvases involved, so the whole page moved into the fragment verbatim, needing its own
  first-ever `extra_scripts` block just for the htmx tag. No core-module refactor was needed:
  `sales_core.get_sales_performance()` was already the single small, independently-tested
  function backing this entire page — the ninth dashboard in a row not needing one. Full suite
  passes (3460, unchanged — no new core logic), `manage.py check` and `ruff check .` both clean
  (the URL route line needed a manual wrap to stay under ruff's line-length limit — the only
  formatting wrinkle in this pass). Verified end-to-end via the Django test client: hit
  `/sales/performance/kpis-fragment/` directly (renders standalone with real data); created a real
  sales target via `sales_core.create_target`, re-fetched the fragment, and confirmed the new rep
  appeared in the Target Attainment ranking table — then deleted it and confirmed it was gone;
  also confirmed the fragment renders correctly in Portuguese and Dutch with an active session in
  each.
  `marketing_dashboard.html`'s own version (`mkt_dashboard_kpis_fragment` polling
  `/mkt/kpis-fragment/`) picked the KPI row trio (Campaigns/Leads/Content) plus the Recent
  Campaigns table — a marketing manager watching this page wants to see a new campaign go active
  or a lead get qualified without a manual refresh, the same "time-sensitive queue" rationale as
  every prior htmx pass, over the six static status/channel/source breakdown charts below it,
  which stay static until reload. No core-module refactor was needed:
  `marketing_core.get_marketing_dashboard(conn)` was already the single small, independently-
  tested function backing this content — the tenth dashboard in a row not needing one. Full suite
  passes (3460, unchanged — no new core logic), `manage.py check` and `ruff check .` both clean.
  Verified end-to-end via the Django test client: hit `/mkt/kpis-fragment/` directly (renders
  standalone with real data — Total Leads: 11); created a real active campaign via
  `marketing_core.create_campaign`, re-fetched the fragment, and confirmed it appeared in the
  Recent Campaigns table — then deleted it and confirmed it was gone; also confirmed the fragment
  renders correctly in Portuguese and Dutch with an active session in each.
  `gl_dashboard.html`'s own version (`gl_dashboard_kpis_fragment` polling `/gl/kpis-fragment/`)
  picked the AP/AR summary cards, the accounts-count Chart-of-Accounts nav link, and the Recent
  Journal Entries table — everything on this page past the toolbar, since it has no Chart.js
  canvases at all, the same "nothing static to leave behind" shape as Credit/Engineering
  Reports/Sales Performance. Unlike those three, this one *did* simplify existing code: the view
  previously called `get_ap_dashboard()`/`get_ar_dashboard()`/`list_journals()[:8]` separately —
  the exact same three calls `accounting_core.get_accounting_dashboard_kpis()` already combines
  (built for the Accounting dashboard pass) — so `gl_dashboard` now calls that shared helper
  directly instead of duplicating the combining logic, with `acct_count` (a `list_accounts()`
  call, outside that helper's scope) fetched alongside it in both the full-page and fragment
  views. No new core logic, so no new tests were needed. Full suite passes (3460, unchanged),
  `manage.py check` and `ruff check .` both clean. Verified end-to-end via the Django test client:
  hit `/gl/kpis-fragment/` directly (renders standalone with real data); created a real balanced
  GL journal via `accounting_core.create_journal`, re-fetched the fragment, and confirmed it
  appeared in the Recent Journal Entries table — then deleted it and confirmed it was gone; also
  confirmed the fragment renders correctly in Portuguese and Dutch with an active session in each.
  `ar_list.html`'s own version (`ar_list_kpis_fragment` polling `/ar/kpis-fragment/`) is the first
  one in this series that isn't a department landing page at all — it's the AR invoice *list*
  page, whose 5-card KPI row (Open/Overdue/Outstanding/Total Invoiced/Total Invoices) is computed
  globally by `get_ar_dashboard(conn)` with no arguments, independent of the page's own
  status/customer/date-range filters below it — a controller watching this page wants the KPI
  counts to stay current without a manual refresh regardless of which filtered slice of invoices
  they're currently looking at, so only that KPI row (not the filtered invoice table or the New
  Invoice form) moved into the fragment, the same "KPI-grid-only, no recent-items table" shape
  `qa_dashboard_kpis.html` established. No core-module refactor was needed: `get_ar_dashboard()`
  was already the single small, independently-tested function backing it. Full suite passes
  (3460, unchanged — no new core logic), `manage.py check` and `ruff check .` both clean. Verified
  end-to-end via the Django test client: hit `/ar/kpis-fragment/` directly (renders standalone
  with real data — Total Invoices: 9); created a real AR invoice via
  `accounting_core.create_ar_invoice`, re-fetched the fragment, and confirmed Total Invoices
  incremented from 9 to 10 — then deleted it and confirmed it reverted to 9; also confirmed the
  fragment renders correctly in Portuguese and Dutch with an active session in each.
  `ap_list.html`'s own version (`ap_list_kpis_fragment` polling `/ap/kpis-fragment/`) mirrors
  AR's exact shape — the same 5-card KPI grid, computed globally by `get_ap_dashboard(conn)` with
  no filter arguments, independent of the page's own status/vendor/date-range filters below it —
  the AP/AR pair being structurally near-identical (Vendor/Paid vs. Customer/Received
  terminology) is itself an established precedent from the Accounting i18n pass. No core-module
  refactor was needed. Full suite passes (3460, unchanged — no new core logic), `manage.py check`
  and `ruff check .` both clean. Verified end-to-end via the Django test client: hit
  `/ap/kpis-fragment/` directly (renders standalone with real data — Total Invoices: 13); created
  a real AP invoice via `accounting_core.create_ap_invoice`, re-fetched the fragment, and
  confirmed Total Invoices incremented from 13 to 14 — then deleted it and confirmed it reverted
  to 13; also confirmed the fragment renders correctly in Portuguese and Dutch with an active
  session in each.
  `ar_invoice_detail.html`'s own version (`ar_invoice_payments_fragment` polling
  `/ar/<id>/payments-fragment/`) is the first target in this series that isn't a dashboard or list
  page at all — it's a single-record detail/edit page, which changes the calculus: the page has
  two live `<form>`s (an inline status-change select next to the balance summary, and a Record
  Payment form pre-filled with the current balance as its default amount), and naively wrapping
  either in a 30s innerHTML swap would silently discard in-progress form input mid-edit — a risk
  none of the dashboard/list passes had to consider, since none of them had a live form sitting
  inside the polled region. Scoped this pass narrowly in response: only the read-only Payment
  History table polls (matching the established "recent-items table" shape exactly), while both
  forms — including the Record Payment form immediately below the same table, inside the same
  `.card` — stay outside the fragment and are never touched by the poll. The status-change form
  and balance summary above it were also left alone rather than carved apart, since splitting a
  single-line flex row into "live text + static form" for one small display value wasn't worth
  the added markup complexity this pass's scope didn't require. No core-module refactor was
  needed: `accounting_core.list_ar_payments(conn, inv_id)` was already the exact function the
  full page already called. Full suite passes (3460, unchanged — no new core logic), `manage.py
  check` and `ruff check .` both clean. Verified end-to-end via the Django test client — including
  explicitly confirming both forms' markup is present on the full page load and absent from the
  fragment response, the specific risk this pass was scoped to avoid: recorded a real payment via
  `accounting_core.record_ar_payment`, re-fetched the fragment, and confirmed it appeared in the
  Payment History table — then deleted it and confirmed it was gone; also confirmed the fragment
  renders correctly in Portuguese and Dutch with an active session in each.
  `ap_invoice_detail.html`'s own version (`ap_invoice_payments_fragment` polling
  `/ap/<id>/payments-fragment/`) mirrors AR's exact shape — the same "Payment History table only,
  both forms untouched" scoping, since AP/AR invoice detail pages are structurally
  near-identical (Vendor/Paid vs. Customer/Received terminology, the same near-duplicate pattern
  already established for the list pages). No core-module refactor was needed:
  `accounting_core.list_ap_payments(conn, inv_id)` was already the exact function the full page
  already called. Full suite passes (3460, unchanged — no new core logic), `manage.py check` and
  `ruff check .` both clean. Verified end-to-end via the Django test client — including explicitly
  confirming both forms' markup is present on the full page load and absent from the fragment
  response: recorded a real payment via `accounting_core.record_ap_payment`, re-fetched the
  fragment, and confirmed it appeared in the Payment History table — then deleted it and confirmed
  it was gone; also confirmed the fragment renders correctly in Portuguese and Dutch with an
  active session in each.
- **Button and text colours (the light content area).** The app was
  originally dark-themed; the content area is now light while the chrome
  (`.app-header` / `.app-actions`) stayed dark. Colours written for the old
  theme render white-on-white and are *invisible, not merely ugly* — a
  button that is present, functional and unreadable reads to a user as
  "the button isn't there" (PR #103 was reported as "can't find where to
  assign a WO"). The conventions below are enforced in `base.html`:

  *Buttons.* Bare `class="btn"` **is correct** in the content area — it is
  the neutral/secondary button. This supersedes the older advice to always
  reach for `btn-primary`, which was a per-page workaround from PR #103;
  the root cause was fixed app-wide in PR #217. Use `btn-primary` for a
  page's main action and `btn-danger` for destructive ones (prior art:
  `blanket_po_detail.html`'s Cancel Blanket PO, `consignment_detail.html`'s
  Cancel Agreement, `bom_detail.html`'s Remove). The dark-chrome treatment
  is scoped with `:where(.app-header, .app-actions) .btn` — **the
  `:where()` is load-bearing and must not be "simplified" to a plain
  descendant selector**: `.app-actions .btn` (0,2,0) would out-specify
  `.btn-primary` (0,1,0) and silently repaint all 44 toolbar `btn-primary`
  buttons.

  *The one remaining trap:* setting `background` inline on a `.btn`
  **without also setting `color`**. The old styling supplied
  `color: white` implicitly, so such buttons depended on it invisibly —
  see `time_off_detail.html`'s Approve/Deny, which needed an explicit
  `color:#fff` added when the default changed.

  *Status pills.* Don't hand-roll pill colours. `base.html` defines a
  `.pill-<status>` set grouped by meaning (info / success / warn / grey);
  use `<span class="pill pill-{{ x.status }}">` and add a new status to the
  appropriate existing group. The PO/SO/WO/time-off **list** pages used to
  render `background:{{ status_color }}20; color:{{ status_color }}` — the
  same colour as both a 12.5%-alpha background and the text, which reads on
  a dark theme and is invisible on a light one (`draft` was mapped to
  `#ffffff`). Fixed in PR #226. The `*_STATUS_COLORS` maps still exist and
  still back the mobile API — don't delete them, just don't style web pills
  from them.

  *Table links vs. buttons.* `.erp-table a` / `.po-table a` / `.filter-bar
  a:hover` set a link colour and are written `a:not(.btn)` on purpose: at
  (0,1,1) they out-specify `.btn-primary` (0,1,0), so without the
  `:not(.btn)` an `<a class="btn btn-primary">` inside a table renders
  accent-on-accent (PR #225). Per-template `.list-table a { color: … }`
  rules in `extra_styles` carry the same latent hazard.

  *Never* use `color:white` / `#fff` / `#aad` / `#aef` for text in
  `{% block body %}`, inline or in `extra_styles`. Use `var(--text)`,
  `var(--text-muted)` or `var(--accent)`. White text is only correct inside
  a container with its own dark background (e.g. `.chip { background:#334 }`
  and its `.chip.active` companion — correct as-is, don't "fix" it).

  *Verifying this is not a grep job.* The defect has appeared in five
  different shapes — inline `color:white`, the same thing spelled `#aad`,
  CSS rules in `extra_styles`, pale-grey placeholders, and data-driven pill
  colours where no colour literal exists in the source at all. Measure
  instead: render the pages via the Django test client, inject a script
  that computes WCAG contrast for every element rendering its own text and
  writes the result into `document.title`, then run `google-chrome
  --headless --dump-dom` over the saved files (parallel with `xargs -P8`)
  and parse it back. Two gotchas that will otherwise produce false
  positives: a `linear-gradient` background is a `background-image`, so
  `getComputedStyle().backgroundColor` reports it as transparent (every
  gradient button looks white-on-white); and a translucent `rgba()`
  background must be alpha-blended over its ancestor before comparing.
  *Muted text uses the `--text-muted` token, not ad-hoc hex greys.* Don't
  write `color:#999` / `#888` / `#aaa` — use `var(--text-muted)`
  (`#5a6a84`, 5.48:1 on white, WCAG AA). All four base templates define
  it. 508 hardcoded greys were converted in one pass; note `#888` on white
  is only 3.54:1, so it looks "fine" while failing AA.

  Related dark-theme leftover, now gone but worth recognising: panels
  built as `background: rgba(0,0,0,0.25)` with `border:
  rgba(255,255,255,0.15)` were designed to overlay a *dark* page and
  render as mid-grey boxes on the light one, dragging their text to ~2:1.
  Three existed (`mrp_home.html`'s `.info-card`, `mrp_plan.html`'s
  `.sum-card`, `lot_list.html`'s filter chips); all now use
  `var(--card-bg)` / `var(--border)`. `base.html`'s `rgba(0,0,0,.45)`
  mobile-sidebar scrim is *not* one of these — it's a genuine overlay.

  *The brand accents are AA-compliant — keep them that way.* `--accent` is
  `#1a66d9` (was `#1d6fe8`) and the supplier portal's is `#2b8038` (was
  `#2f8f3e`); both old values failed AA as link text. **Check any change
  against `--content-bg` (`#f0f4fa`), not white** — that's the binding
  surface and it's ~0.4 stricter, which is exactly how the old blue passed
  a white-background spot-check (4.68) while failing in situ (4.24).
  `--accent-hover` must stay darker than `--accent`. The Chart.js palettes
  that hardcode `#1d6fe8` were deliberately left — chart fills aren't text,
  so AA doesn't apply and restyling every chart buys nothing.

  Current state on `main`: across 299 pages — zero elements below 2.0
  contrast, zero muted-grey text below AA, and zero sub-AA brand-colour
  text. *Semantic status colours are AA too* — the badge palette was
  darkened in place (`#e65100`→`#c34500`, `#827717`→`#7c7216`,
  `#bf360c`→`#ba350c`, `#f5a623`→`#a36907`, `#059669`→`#04865e`) plus the
  green action-button background `#28a745`→`#1e8035`, which also lifts the
  white text on it from 3.13 to 5.01. **Hue and saturation were preserved
  and only lightness reduced**, so `In Progress` is still orange and
  `Quality` still green — the signal survives, it is just legible. Do the
  same for a new status colour rather than reaching for a generic grey.
  `#e65100` had to serve two jobs (badge text on `#fff3e0`, and a button
  background under white text); `#c34500` clears AA both ways (4.59/5.03).

  **The only sub-AA text left is Swagger UI's own error banner** on
  `/api/docs/` (4 elements, `errors__title` and friends). That CSS ships
  from `cdn.jsdelivr.net/npm/swagger-ui-dist@5` — a floating major — so
  overriding its internal class names to restyle a failure-only banner is
  fragile for no real gain. Left on purpose; not an oversight.

  Two colours were deliberately NOT darkened where they act as **chart
  fills** rather than text (`#f5a623`'s forecast bar and legend swatch,
  `#059669`'s OEE series): AA does not apply to fills, and darkening them
  visibly muddies the chart for no benefit. Only their `color:` uses
  changed — the same call made for the Chart.js palettes in the accent
  pass.

  Measure with a size-aware threshold (AA allows 3:1 for text ≥24px, or
  ≥18.66px bold) — otherwise you over-report large KPI numbers by ~36
  items.

  **When converting greys, check the *ancestor's* background, not just the
  element's own.** A rule like `.scope-total .label { color:#ccc }` is
  correct light-on-dark because `.scope-total` is `#333`; blindly swapping
  it to `var(--text-muted)` makes it unreadable. This exact case was
  caught by the audit in `esg_dashboard.html` and reverted.

- **Print / export buttons on detail and list pages.** Document-type detail
  pages carry a `Print / Save PDF` button; list pages carry `Export CSV` /
  `Export Excel` links. Both follow one established pattern each, and the
  print one has a non-obvious scoping rule that is easy to get wrong.

  *Print* — copy `po_detail.html`: a `.print-btn` style block plus an
  `@media print { ... display: none !important; }` rule in `extra_styles`,
  and `<button class="print-btn" onclick="window.print()">` as the first
  element inside `{% block body %}`'s `.content` div. **The rule that
  matters: hide only the workflow-action controls, never the record's own
  data.** Several of these pages render the record *inside form fields*
  (`<input readonly>` / `<textarea readonly>` when the viewer lacks edit
  rights, editable otherwise), so a naive `form { display: none }` blanks
  the document it was supposed to print. Work control-by-control instead:
  every state-mutating control needs *some* selector in the rule, and the
  record's own fields need to survive. Which selectors you need depends on
  how the page is built, and pages often need more than one:
  - **Action lives in its own card/form, separate from the data** — give it
    a `no-print` class and add `.no-print` to the rule. `legal_contract
    _detail.html` (Edit Contract card), `credit_application_detail.html`
    (Review Application), `req_detail.html` (Add Item + Submit + Decide,
    3 elements), `consultant_invoice_detail.html` (Submit + the
    approval-decision alert), `eng_ecr_detail.html` (inline status-change
    dropdown).
  - **The data itself is inside the edit form** — hide only that form's
    submit button, not the form. `.btn-submit` in `purch_contract_detail
    .html`, `sales_contracts_detail.html`, `eng_spec_detail.html`,
    `finance_tax_detail.html`, `cs_returns_detail.html`; `.btn-row` in the
    QA trio; `.btn-act` in `eng_ecr_detail.html`. Hiding the whole form
    here is the failure mode described above.
  - **Both at once** is common, not exceptional. `qa_ncr_detail.html` /
    `qa_capa_detail.html` / `qa_audit_detail.html` hide `.btn-row` (their
    details card *is* a form) *and* `.no-print` (the separate Close NCR /
    Close CAPA / Complete Audit card). `eng_ecr_detail.html` likewise
    pairs `.btn-act` with `.no-print`.
  - **Nothing extra needed** — when the only controls are toolbar links or
    buttons already carrying `.btn`, the generic `.btn` entry covers them.
    `supplier_scorecard_detail.html` (genuinely form-free) and
    `blanket_po_detail.html` (its Cancel Blanket PO button is a `.btn`).

  Portal templates (`base_portal.html` / `base_supplier_portal.html`) also
  need `.portal-header` in the rule, since their nav bar isn't a `.btn` —
  see `portal_rma_detail.html` and `supplier_portal_po_detail.html`.

  Verify by loading a real record in each permission/status state the page
  branches on, not just one — the action controls are usually behind
  `{% if can_edit %}` / status checks, so a single spot-check silently
  misses whichever branch you didn't hit.

  *Export* — copy `it_repairs_list.html`: an `?export=1[&format=xlsx]` link
  pair in `toolbar_left` with **`|urlencode` on every filter value**, and an
  `if 'export' in request.GET: return export_response(request,
  '<base_filename>', [(field, 'Header'), …], rows)` branch in the view,
  placed **after** the rows are fetched but **before** any POST handling or
  extra context queries. `csv_export.export_response` handles the CSV/XLSX
  split; row dicts may be missing keys without raising. The `|urlencode` is
  not optional even when the current filter values look safe: without it,
  any value containing `&` or a space silently truncates the export's scope
  rather than erroring (the bug fixed in `ar_list.html`/`ap_list.html` in
  PRs #201/#202, where the free-text `search`/date filters made it
  reachable). The mechanism is worth knowing, since nothing errors: Django
  auto-escapes the `&` to `&amp;`, the browser entity-decodes it back to a
  real separator, and the link splits into a truncated `search=` plus a
  junk param — so the user sees N filtered rows, clicks Export, and gets a
  *larger* set for the truncated term. Apply it to whitelisted filters too
  — `bom_list.html`'s `item_type` is validated against `ITEM_TYPES` in the
  view so it can't currently break, but it carries the filter for the same
  reason and widening that tuple shouldn't quietly reintroduce the bug.

  **The app is now uniformly compliant** — a sweep of the remaining 51
  templates (PRs #201/#202/#222 had each fixed one page in isolation)
  means any export link you copy from is a safe reference, not just
  `it_repairs_list.html`. It covered both link shapes: `?export=1` on the
  same path, and a separate export URL like `/qa/ncr/export/?…`. Catch a
  regression from `manufacturing/templates/` with
  `grep -l 'href="[^"]*export[^"]*{{' *.html | while read f; do grep -H
  'href="[^"]*export[^"]*{{' "$f" | grep -v urlencode; done` — any output
  is an unencoded filter. When the view
  already scopes rows by permission (e.g. `req_list`'s full-access /
  manager / own visibility), exporting that same `rows` variable inherits
  the scoping for free — don't re-query.

  **i18n caveat for both:** wrap the new button/link text in `{% trans %}`
  *only if the template already has `{% load i18n %}`*. As of the
  Consultants-feature pass (the last remaining gap, closed after every
  other area in this app), there are no more untranslated-by-design areas
  left — the customer/supplier portals, `bom_detail.html`, and
  `supplier_scorecard_detail.html` were all fully translated in earlier
  passes despite this note's own stale claim otherwise for a long time (a
  reminder that a note like this one needs updating the moment the gap it
  describes closes, not left to rot). Where the tag applies, `makemessages`
  merges into the existing `"Print / Save PDF"` / `"Export CSV"` /
  `"Export Excel"` msgids, which are already translated in all five
  languages, so no new translation work is needed.
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

## Checking what a box is actually serving (`/healthz/`)
Unauthenticated, no session needed, works on both deployments:

    curl -s http://<box>:8000/healthz/

`status` is a pure **liveness** signal (is the DB reachable) — `ok`, or
`error` with 503. Don't widen it: load balancers assert on it, and a stale
deploy is still a serving one. Deploy identity lives under `version`:

  * `sha` / `short_sha` — the commit **this process booted with**, read once
    at import. What the box is *actually serving*.
  * `disk_sha` — what the working tree holds *now*, read per request.
  * `code_stale` — true when those differ: the pulled-but-not-restarted
    window, which is otherwise invisible from outside the machine. A commit
    that cannot be read reports `None` and `code_stale: false` — "I could
    not look" must not masquerade as "the deploy is broken".

This exists because on 2026-09-04 the Linux box served an eight-hour-old
process while its repo sat fully current: `git log` on the box looked
right, HTTP looked right, and only the *restart* had failed. It is also
the only way to confirm a deploy of a commit that changes no rendered
output (docs, `scripts/`) — HTTP alone cannot distinguish those.

`version_core.py` reads `.git` directly rather than shelling out to `git`:
no subprocess per request, no dependency on git being installed or on the
deploy user's `PATH`, and it cannot hang. It follows the worktree `.git`-as-
a-file indirection and `commondir`, and falls back to `packed-refs` when a
loose ref is absent. **Strip the `refs/heads/` prefix, don't `rsplit('/')`**
— branch names here are nearly all `feat/x` or `docs/y`, and the naive
split silently reports `x`.

## Linux deployment (`scripts/linux/`)
`manufacture-autopull.sh` (polls `origin/main`, gates on `manage.py check`
plus the full pytest suite, restarts `manufacture.service`) plus the three
systemd units it needs; the timer fires every 2 minutes. `install.sh` sets
it up — counterpart to `scripts/windows/register-scheduled-tasks.ps1`.

These lived untracked at `~/tester/` until the bug below made the cost
obvious: the Windows half was version-controlled and reviewed while its
Linux twin had no history, no review and no CI. `install.sh` symlinks
`~/tester/manufacture-autopull.sh` at the repo copy, so a pull updates the
deploy tooling itself — which is how the Windows box already works.

**Never `git pull origin main --ff-only` in a deploy script that shares a
checkout with interactive work.** It decides from the `main` ref but pulls
into `HEAD`, so whenever a session has a feature branch checked out the
pull targets *that* branch: `main` never advances, the next cycle sees the
identical delta, and the deploy stalls silently while the log keeps
announcing `New commits detected` — five consecutive cycles with the same
source SHA, observed live. Worse, on a freshly-created branch with no
commits of its own the `--ff-only` pull *succeeds* and fast-forwards that
branch onto `origin/main`, moving someone's work with no warning. The two
cases need different mechanisms and neither is `pull`: on `main` use
`git merge --ff-only` (advances the working tree); anywhere else use
`git fetch origin main:main` (moves the ref only) — git **refuses** that
form when `main` is checked out, so one cannot serve both. The script also
declines to restart the service when the tree is not on `main`, rather
than deploying whatever branch happens to be there.

**`systemctl restart` returning 0 does not mean the server is up.** For
`Type=simple` it returns as soon as the process is *spawned*, so a
`runserver` that dies immediately — port already held, bad `.env`, DB auth
— still exits zero, after which `Restart=on-failure` cycles it forever.
The script logs the *outcome*: a healthy deploy writes
`Restart OK -- now serving <sha>` (the same diagnostic as the Windows
side), a failure writes `Restart FAILED` plus indented `svc:` lines from
`systemctl status`. **A single `is-active` sample cannot tell a healthy
server from a crash loop** — during auto-restart the unit reads `active`
for the moment between spawn and the child's bind failure — so it waits
for `active`, then re-checks a few seconds later *and* confirms
`NRestarts` has not climbed.

**The quiet path is health-checked too.** `Restart=on-failure` recovers a
one-off crash but cannot fix a server that fails every start for the same
reason, and that state used to be invisible: the unit sat in `activating`
forever while autopull exited 0 every two minutes with nothing to say.
Seen live 2026-09-04 — `manufacture.service` crash-looped **4,000+ times
over eight hours** because a leftover `.claude/launch.json` preview dev
server (`../manage.py runserver 0.0.0.0:8000`, started by an editor
session, not by a unit) held the port. The app still answered, because
*that* process was serving, so nothing looked wrong from outside. A
non-`active` service is now logged even when there is nothing to pull.
`fuser -k -9 8000/tcp` clears such a squatter; a plain reboot fixes it
permanently, since it is not a service and does not come back.

**Port 8000 belongs to `manufacture.service` — do not point a dev server
at it.** `.claude/launch.json` is gitignored and per-checkout, so each
worktree carries its own copy and they are easy to create by copy-paste;
one aimed at `0.0.0.0:8000` silently takes the port from systemd on the
next restart, and because that dev server *also* serves the app, the box
keeps answering and nothing looks wrong. That is exactly the eight-hour
outage above. Give every preview config a distinct high port bound to
`127.0.0.1` (the ones on this box now use 8010/8011/8012). Since the file
is untracked, this convention only survives by being written down here.

**An empty autopull log is the normal, healthy state — it is not evidence
that the timer has stopped.** The script is deliberately silent on the
quiet path: nothing to pull and the service `active` means it exits 0
without a word, so `journalctl` over a window where nothing was deployed
correctly prints `-- No entries --`. During the incident above that
silence was twice misread as "the deploy never ran". To ask *"is autopull
alive?"* query the unit's own bookkeeping instead, which is populated
whether or not anything was logged:

    systemctl show manufacture-autopull.service -p Result -p ExecMainStatus \
        -p ExecMainStartTimestamp --value
    systemctl list-timers manufacture-autopull.timer

**Read the script's own lines with `journalctl -t manufacture-autopull`.
`-u manufacture-autopull.service` silently drops most of them** — it is not
a superset. Measured across three deploy cycles, `-t` returned every
`logger` line (3, 3, 2) while `-u` returned 2, 1 and 1.

The cause is cgroup attribution, verified from the journal's own fields:

    "New commits detected ..."   _SYSTEMD_CGROUP=/system.slice/manufacture-autopull.service
    "Checks passed, restarting"  _SYSTEMD_CGROUP=None
    "Restart OK -- now serving"  _SYSTEMD_CGROUP=None

The script does its work through `sudo -u eric`, which re-parents out of the
unit's cgroup; every `logger` invocation after that point is recorded with
no `_SYSTEMD_UNIT`, and `-u` filters on exactly that field. So the lines
that matter most — the restart outcome — are the ones `-u` hides. `-t`
filters on `SYSLOG_IDENTIFIER`, which survives.

Use `-t` for the deploy narrative, `-u` for the unit's stdout (the pytest
run) and systemd's start/stop records, and no filter at all when you want
both interleaved.

*This note was wrong twice before being measured.* The first version
claimed `-t` was the lossy one; the correction claimed the two were
equivalent, from a test that compared `grep 'New commits'` under `-t`
against `grep -E 'New commits|passed in'` under `-u` — different patterns,
so the matching counts meant nothing. Compare like with like, over a window
that contains a real deploy, before believing either.

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

**"Pulled" is not "deployed" — check the log line, not just that one
exists.** The box once served weeks-old code while `git log -1` on that
machine showed it fully current, behind a log containing 30 consecutive
`Checks passed, restarting service` entries. Every commit had been pulled
correctly; none had ever been *served*. Three silent failures stacked:
`manufacture-run.ps1` swallowed `Stop-Process` errors under
`-ErrorAction SilentlyContinue`, then slept a fixed 2s and started a
replacement **without re-checking the port had freed** — so the new
`runserver` died instantly on a bind error into `manufacture-server.log
.err` while the *original* process kept serving; and autopull wrote its
`restarting service` line **before** the attempt and never inspected the
exit code, so total failure and total success were textually identical.
Nothing on screen changes without a real restart, because `DEBUG=False`
makes Django cache templates for the life of the process — a pull alone
is invisible. All three are fixed (the run script now reports kill
failures with the offending PID, polls until the port genuinely frees,
refuses to start a server that cannot bind, and confirms the new one is
listening; autopull logs the outcome plus the run script's transcript).
**The diagnostic that matters now: a healthy deploy logs
`Restart OK -- now serving <sha>`.** A bare `Checks passed, restarting
service` with nothing after it means the restart did not complete.
**`Win32_Process.CommandLine` reads back empty for a process owned by
another user unless the caller is elevated** — so `manufacture-run.ps1`
finds the server by the socket it holds (`Get-NetTCPConnection ...
OwningProcess`, which carries no such restriction), not by matching
`manage.py runserver` against `CommandLine`. It used to do the latter,
which failed silently and precisely in the case that matters: a stale
server left by an earlier session was invisible, so no kill was ever
*attempted*, `kill failures` stayed `0`, and the "run this elevated"
hint — gated on that counter — never printed. The log read
`still held (kill failures: 0)`, which looks like the process vanished
rather than like a permissions wall. Seen live 2026-09-04: the box
served `fb8f2df` for hours after pulling `6d7e61b`, `Get-CimInstance ...
CommandLine` returned nothing from a normal shell, and `netstat -ano |
findstr :8000` plus `taskkill /F /PID` was the only thing that could see
it (in the end a reboot was what cleared it — `taskkill` also reported
`could not be terminated`). The message now prints `found: N, kill
failures: M` so "could not see it" and "could not kill it" are
distinguishable, and both get a hint. Because runserver's autoreloader is
a parent/child pair where only the child binds the port, the lookup also
walks up one level and takes a `python.exe` parent — killing only the
child lets the parent respawn it.
Failures log `Restart FAILED (exit N)` followed by indented `run.ps1:`
lines naming the PID and reason — `Access is denied` there points at the
scheduled task lacking privilege to kill a server owned by another user,
fixed by setting the task to run as that account **with highest
privileges** (a Task Scheduler setting, not a repo change). Worth noting
the original trigger was never definitively isolated: both the swallowed
kill error and the fixed-2s race were live, either could have caused it,
and the manual elevated restart used to recover changed process ownership
before the fix landed — so treat the above as two real defects closed,
not one confirmed root cause.

**Four `python.exe` processes on that box is normal, not a leak.** A bare
process count is meaningless here: the venv's `Scripts\python.exe` is a
255 KB *redirector*, not an interpreter — `pyvenv.cfg` points it at a
separate `pythoncore-3.14-64` install — so every logical Python process
appears twice, as a ~3 MB shim plus the real interpreter it launches.
Django's `runserver` autoreloader is its usual parent/child pair, so a
single healthy server is 2 logical and 4 OS processes, in one chain:

```
 9060   3MB  virt\Scripts\python.exe        <- venv shim
  16688  64MB  pythoncore-3.14-64\python.exe  <- reloader parent
   23420   3MB  virt\Scripts\python.exe       <- venv shim
    11268  81MB  pythoncore-3.14-64\python.exe <- server child, owns :8000
```

Distinguish a real leak from this by **memory and executable path**, not
count: only the large `pythoncore-*` entries are loaded Django apps, and
exactly one should own port 8000
(`(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess`).
The Linux box shows the plain 2-process pair for the same server, which
is the useful control. Counts that stay at 4 across restarts are healthy;
growth beyond that is the accumulation `manufacture-run.ps1`'s docstring
describes.

**A DHCP IP change on the Windows box breaks three unrelated things at
once**, seen in practice when its address moved from `192.168.4.46` to
`192.168.0.188`: (1) Windows Firewall silently drops inbound connections
(including ping) after the network is treated as "new," even with the
profile still set to Private — the fix is temporarily disabling the
firewall to confirm it's the cause, then re-enabling it with a proper
inbound rule for the port; (2) `manufacture/settings.py`'s `ALLOWED_HOSTS`
default (`['localhost', '127.0.0.1', '192.168.0.231']` — that last address
is the *Linux* box's own IP, hardcoded, and drifts too: it was `.239`
until 2026-09-10, when it had silently drifted to `.231` and every
request arriving via the real IP instead of `localhost` was 400ing —
verify against `hostname -I`/`ip addr` on that box rather than trusting
this value) doesn't include whatever the Windows box's new address is, so
requests 400 until `DJANGO_ALLOWED_HOSTS`
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
