# Manufacturing ERP — Mobile App

React Native (Expo SDK ~57, expo-router) companion app for the Django
manufacturing ERP. Talks to the stateless JSON API at `/api/v1/` (see the
root [`CLAUDE.md`](../CLAUDE.md) for backend details).

## Setup

```bash
cd mobile
npm install
cp .env.example .env.local   # set EXPO_PUBLIC_API_URL to your Django server's LAN IP
npx expo start                # scan the QR code with Expo Go on your phone
```

Login uses the same `passwd` table as the web app (bcrypt-verified via
`POST /api/v1/auth/login/`).

## Verifying changes (no unit-test framework here)

```bash
npx tsc --noEmit               # typecheck
npx expo-doctor                # expect 21/21 checks passed
npx expo export --platform web # full bundle build
```

All three run in CI (`.github/workflows/mobile.yml`).

## Screens

`mobile/app/(tabs)/` has 21 screens — one dashboard per department (all 17)
plus dedicated workflow screens for the highest-traffic areas, in tab order:

| Screen | Covers |
|---|---|
| Dashboard (`index`) | Company-wide KPIs: active WOs, open POs, inventory alerts, CS open tickets |
| Time Clock | Clock in/out, hours (full offline support — see below) |
| Work Orders | List, detail, status transitions (list view has offline read-cache) |
| Maintenance | Work order list, detail, complete |
| Inventory | Stock levels, reorder alerts |
| Quality | NCR list, create, detail |
| Approvals | Pending approval-workflow steps, approve/reject |
| Lots | Lot list with qty/expiry |
| Requisitions | Submit, manager approve/deny |
| Costing | Product search + standard cost/roll/history + routing steps, plus Workcenters/GL Accounts reference lists |
| Finance | Cash position, DSO/DPO, gross margin, AP due this week, AR aging buckets |
| Sales | Open orders, order value, quotes won, target attainment, recent orders |
| Personnel | Headcount, by-department breakdown, time-off pending/approved, recent hires |
| Accounting | AP/AR outstanding + overdue counts, all-time invoiced totals, recent GL journals |
| Customer Service | Open tickets, completion rate, avg resolution/open-ticket age, recent tickets |
| Engineering | Active/planning project counts, overdue tasks, pending ECRs, recent projects with task progress |
| Customers | Credit accounts at risk, total credit exposure, pending credit applications, open collections, recent collection activity |
| IT | Open/critical/in-progress helpdesk ticket counts, asset repair status, recent tickets with priority |
| Legal | Active contract count, pending compliance items, open litigation cases, recent contracts with value/status |
| Marketing | Active/planned campaign counts, new/qualified lead counts, published/draft content counts, recent campaigns |
| Payroll | YTD gross payroll, employees with pay rates, active deduction types, recent payroll runs |

Plus `(auth)/login`.

Every one of the 11 department dashboards added after the original 10
(Finance through Payroll) reuses an existing backend dashboard function
verbatim, or a small `reports_core.*_dashboard()` wrapper combining two
existing functions — no department needed a larger rewrite. See
`manufacturing/COMPETITIVE_GAP_ANALYSIS.md`'s dated log (search for
"mobile-coverage") for the department-by-department build notes.

## Offline support (`src/offline/`)

Deliberately partial, not a full offline-first rewrite:

- **Time Clock** — full read-cache + write-queue (clock in/out are the
  canonical "plant-floor worker with no signal" case).
- **Work Orders list** — read-cache only; status changes and assignment
  still require connectivity.
- **Maintenance list** — read-cache only, same rationale as Work Orders;
  completing a work order still requires connectivity.
- **Quality NCR list** — read-cache only; creating an NCR still requires
  connectivity.
- The other 17 screens have no offline support yet. Extending the pattern
  to a screen is mechanical: wrap its `load()` in
  `fetchWithOfflineCache()` (`src/offline/cache.ts`) and wrap write
  actions in `enqueueMutation()` (`src/offline/queue.ts`) where queuing
  makes sense.

`useIsOnline()` (`src/offline/netStatus.ts`) and the shared `OfflineBanner`
component surface "showing cached data" / "N actions waiting to sync"
rather than failing silently. A global `NetInfo` listener in
`app/_layout.tsx` flushes the queue automatically on reconnect.

## Shared components (`src/components/`)

- `KpiCard` — title/value/subtitle/accent tile used across every dashboard.
- `StatusBadge` — normalizes a status string (lowercase + underscores) and
  looks up a color in a shared map; extend it whenever a screen introduces
  a status value not already covered.
