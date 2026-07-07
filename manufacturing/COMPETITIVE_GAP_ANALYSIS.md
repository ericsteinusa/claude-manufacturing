# Manufacturing ERP — Competitive Gap Analysis
**Generated:** 2026-07-05 · **Refreshed:** 2026-07-08
**Compared Against:** SAP S/4HANA, Oracle Cloud Manufacturing, Microsoft Dynamics 365 SCM, Epicor Kinetic, Infor CloudSuite Industrial, Plex Manufacturing Cloud, SYSPRO, Fishbowl, JobBOSS², MRPeasy

**What changed since the original pass:** All 6 Priority-1 items, all 8 Priority-2 items, and 2 of 7
Priority-3 items (P3-A Finite Capacity Scheduling/APS, P3-B WMS pick/pack/ship) have shipped —
16 features total, verified against the codebase at commit `643f1e7`. This refresh re-scores every
domain table below against that reality, corrects two items the original pass got wrong (the mobile
app already has a Maintenance screen — `mobile/app/(tabs)/maintenance.tsx` — and a scheduled email
digest already exists — `manufacturing/management/commands/send_daily_digest.py` — neither was
credited before), and re-ranks the remaining roadmap.

**2026-07-08, later same day:** Shipped P1-G (Excel export), P3-D (Landed Cost Allocation),
P3-E (Blanket Purchase Orders & Call-offs), P3-C (Customer Self-Service Portal), P3-F
(Multi-Company / Multi-Entity), P3-G (OEE Live Shop Floor Dashboard), P4-A (AI Demand
Forecasting), P4-B (Predictive Maintenance), and P4-C (Capable-to-Promise), merged from nine
separate PRs (#398, #382, #386, #381, #387, #388, #389, #390, #391) that a prior session had
built and left open. The remaining roadmap (P4-D through P4-G) still has open PRs (#392–#395)
from that same prior session — working through them one at a time. 25 features shipped total.

---

## Executive Summary

This ERP is now a **strong mid-market system with several upper-mid-market capabilities** — finite
capacity scheduling, a full WMS, ATP, and OEE all shipped since the last pass. It comfortably matches
or beats Infor CloudSuite, SYSPRO, and Epicor on day-to-day production, quality, purchasing, sales,
HR, payroll, accounting, and IT management, and has closed most of the "visible gap" items (charts,
export, Gantt, RFQ, price lists) that used to stand out immediately in a demo.

The primary gaps now fall into three areas:
1. **AI / Predictive Analytics** — ML demand forecasting (P4-A) and MTBF-based predictive maintenance risk scoring (P4-B) now exist; no broader embedded-AI analytics platform, and no real IoT/sensor hardware connectivity (P4-B's sensor readings are logged manually, not device-fed)
2. **Trading-Partner Integration** — no EDI, no supplier self-service portal, no real carrier-API shipment tracking, no e-commerce sync
3. **Supply-Chain Costing Depth** — no FIFO/LIFO/weighted-average valuation, no true inter-warehouse transfers (WMS now has multiple warehouses/bins, but nothing moves stock *between* them)

---

## Section 1: Feature-by-Feature Comparison

### 1.1 Production Planning & Scheduling

| Feature | Us | Top 10 |
|---|---|---|
| Work Order management (CRUD, lifecycle, statuses) | ✅ Full | ✅ All |
| Bill of Materials (multi-level, explode, costing) | ✅ Full | ✅ All |
| Routing & workcenter operations with sequence tracking | ✅ Full | ✅ All |
| MRP run with demand calculation & planned orders | ✅ Full | ✅ All |
| Safety stock planning | ✅ | ✅ All |
| Production schedule views (day/week/month) | ✅ | ✅ All |
| Work order cost tracking (material/labor/overhead/variance) | ✅ Full | ✅ All |
| Make-to-Order / Make-to-Stock / Engineer-to-Order | ✅ | ✅ All |
| **Advanced Planning & Scheduling (APS)** | ✅ (P3-A) | ✅ 8/10 |
| **Finite capacity scheduling** | ✅ Full (P3-A) | ✅ 8/10 |
| **Gantt chart drag-and-drop scheduler** | ✅ Full (P2-A) | ✅ 8/10 |
| **Constraint-based sequencing** | ✅ Partial — cross-workcenter operation ordering enforced; load leveling is a greedy heuristic, not a true solver | ✅ 7/10 (Infor core) |
| **Bottleneck analysis** | ✅ Full (P3-A) — utilization-% ranking | ✅ 7/10 |
| **What-if scenario planning** | ❌ | ✅ 8/10 |
| **Configure-to-Order (CTO)** | ❌ | ✅ 7/10 |
| **Recipe / formula management (process mfg)** | ❌ | ✅ 7/10 |
| **Repetitive manufacturing** | ❌ | ✅ 7/10 |

**Priority gaps:** what-if scenario planning, Configure-to-Order, recipe/formula management (process mfg), repetitive manufacturing.

---

### 1.2 Inventory & Warehouse Management

| Feature | Us | Top 10 |
|---|---|---|
| Real-time inventory tracking | ✅ | ✅ All |
| Bin location tracking | ✅ | ✅ All |
| Lot & serial number tracking (full genealogy) | ✅ Full | ✅ All |
| Inventory transaction history (receipt/issue/adj/scrap/return) | ✅ Full | ✅ All |
| Expiry date tracking & alerts | ✅ | ✅ All |
| Low stock alerts | ✅ | ✅ All |
| ABC analysis | ✅ Partial | ✅ 9/10 |
| **FIFO / LIFO / Weighted Average Cost valuation** | ❌ | ✅ All |
| **True multi-warehouse with transfers** | ✅ Partial (P3-B) — multiple warehouses/zones/bins now exist, but nothing moves stock *between* warehouses | ✅ All |
| **Warehouse Management System (WMS)** | ✅ Full (P3-B) | ✅ 9/10 |
| **Pick / Pack / Ship automation** | ✅ Full (P3-B) | ✅ 9/10 |
| **Cycle count structured workflow** | ✅ Full (P1-D) | ✅ All |
| **Consignment inventory** | ❌ | ✅ 7/10 |
| **Cross-docking** | ❌ | ✅ 6/10 |
| **Wave picking management** | ❌ — pick lists are one-per-SO with a zone-aware sort, not multi-order wave batching | ✅ 6/10 |
| **RFID integration** | ❌ | ✅ 8/10 |
| Barcode scanning (entity lookup + label printing) | ✅ Full | ✅ All |

**Priority gaps:** FIFO/LIFO/weighted-average costing, true inter-warehouse transfers, consignment inventory, cross-docking, wave picking, RFID.

---

### 1.3 Quality Management

| Feature | Us | Top 10 |
|---|---|---|
| NCR (Non-Conformance Reports) | ✅ Full | ✅ All |
| CAPA (Corrective/Preventive Actions) | ✅ Full | ✅ 9/10 |
| Quality audits with findings | ✅ Full | ✅ All |
| Supplier quality ratings & audits | ✅ | ✅ 8/10 |
| Inspections (incoming, in-process, final, hold) | ✅ Full | ✅ All |
| Statistical Process Control (SPC, X-bar/R, Cpk) | ✅ Full | ✅ 7/10 |
| Defect tracking with severity & resolution | ✅ | ✅ All |
| Calibration schedules & records | ✅ Partial | ✅ 9/10 |
| Customer complaint tracking | ✅ | ✅ 8/10 |
| Sample management | ✅ | ✅ 7/10 |
| Audit trail & full traceability | ✅ Full | ✅ All |
| **Sampling plans & AQL (acceptance quality limit)** | ✅ Full (P2-E) — ISO 2859-1; seeded accept/reject table covers AQL 0.65–4.0, code letters C-N only | ✅ 8/10 |
| **Control plans & FMEA** | ❌ | ✅ 7/10 |
| **Certificate of Analysis (CoA) generation** | ❌ | ✅ 7/10 |
| **Document control & version management** | ✅ Full (P2-F) — draft→review→approved→superseded→obsolete, revision history, file upload/download | ✅ 8/10 |
| **Regulatory compliance templates (FDA, ISO)** | ❌ | ✅ 7/10 |

**Priority gaps:** CoA generation, FMEA/control plans, regulatory compliance templates.

---

### 1.4 Purchasing & Procurement

| Feature | Us | Top 10 |
|---|---|---|
| Purchase Order management (full lifecycle) | ✅ Full | ✅ All |
| Purchase Requisitions with multi-level approval | ✅ Full | ✅ All |
| Approval workflows (role-based, threshold, escalation) | ✅ Full | ✅ All |
| Accounts Payable with aging & DPO | ✅ Full | ✅ All |
| Three-way match (PO/receipt/invoice) | ✅ Partial | ✅ All |
| Vendor/supplier master | ✅ | ✅ All |
| Purchasing contracts | ✅ | ✅ 7/10 |
| **Request for Quote (RFQ) module** | ✅ Full (P1-F) — per-line award, one draft PO per winning vendor | ✅ All |
| **Vendor quote comparison & scoring** | ✅ Full (P1-F) — side-by-side table, lowest-quote flagging | ✅ All |
| **Supplier performance scorecard** | ✅ Full (P2-C) — on-time %, fill rate %, quality reject %, composite score | ✅ 7/10 |
| **Supplier collaboration / self-service portal** | ❌ | ✅ 6/10 |
| **Blanket orders & call-offs** | ✅ Full (P3-E) — value- or qty-tracked balance, auto-close/auto-expire | ✅ 9/10 |
| **Freight & landed cost allocation** | ✅ Full (P3-D) — by value/weight/qty, rolls into `product.purchase_price` | ✅ 7/10 |
| **EDI (850/856/810)** | ❌ | ✅ 8/10 |
| **Auto-generated POs from MRP** | ✅ Full (P2-H) — preferred-supplier lookup wired into MRP release | ✅ All |

**Priority gaps:** supplier self-service portal, EDI.

---

### 1.5 Sales & Order Management

| Feature | Us | Top 10 |
|---|---|---|
| Sales Order management | ✅ Full | ✅ All |
| Sales Quotes (draft→sent→accepted/rejected) | ✅ Full | ✅ All |
| Sales Leads & CRM pipeline | ✅ Full | ✅ All |
| Sales contracts | ✅ | ✅ 8/10 |
| Sales forecasting with actuals & variance | ✅ Full | ✅ 9/10 |
| Sales territories & rep performance | ✅ Full | ✅ 7/10 |
| Commission tracking & plans | ✅ Full | ✅ 6/10 |
| Accounts Receivable with aging & DSO | ✅ Full | ✅ All |
| RMA / returns management | ✅ | ✅ All |
| Demand by product analytics | ✅ | ✅ 8/10 |
| **Available-to-Promise (ATP)** | ✅ Full (P2-B) — inquiry screen, live SO-line badge, soft confirm-gate | ✅ 9/10 |
| **Capable-to-Promise (CTP)** | ✅ Full (P4-C) — combines ATP material availability with finite-capacity workcenter dates into one `ctp_date`; second independent shortfall check on SO confirm | ✅ 6/10 |
| **Price list management & tiered pricing** | ✅ Full (P1-E) — client-side SO auto-populate by tier | ✅ All |
| **Discount & promotion management** | ❌ | ✅ All |
| **Customer self-service portal** | ✅ Full (P3-C) — own orders/invoices/shipments/RMAs, invoice + packing-slip PDF, online payment; carrier tracking and Stripe payment are documented stubs (no real integration existed anywhere to build on) | ✅ 7/10 |
| **Shipping & carrier API integration (FedEx/UPS/USPS)** | ❌ — WMS (P3-B) records carrier + tracking number manually at ship confirm; the portal's tracking view (P3-C) is a deterministic stub, not a real carrier API | ✅ 9/10 |
| **Multi-channel order integration (e-commerce)** | ❌ | ✅ 7/10 |

**Priority gaps:** discount/promotion management, carrier API integration, e-commerce sync.

---

### 1.6 Finance & Accounting

| Feature | Us | Top 10 |
|---|---|---|
| General Ledger with chart of accounts | ✅ Full | ✅ All |
| Journal entry with posting and void | ✅ Full | ✅ All |
| Income statement & balance sheet | ✅ Full | ✅ All |
| Trial balance | ✅ Full | ✅ All |
| Accounts Payable & Receivable | ✅ Full | ✅ All |
| Fixed Asset management + depreciation schedule | ✅ Full | ✅ All |
| Multi-currency with exchange rates | ✅ Full | ✅ All |
| Bank reconciliation (auto + manual match) | ✅ Full | ✅ 8/10 |
| Budgeting with variance analysis | ✅ Full | ✅ 8/10 |
| Tax management & filing calendar | ✅ | ✅ 9/10 |
| Financial audit tracking | ✅ | ✅ 7/10 |
| Period locking (close/reopen) | ✅ Full | ✅ 8/10 |
| Standard costing with variance & GL posting | ✅ Full | ✅ 8/10 |
| WIP tracking | ✅ | ✅ All |
| Job costing | ✅ | ✅ All |
| Cost of Goods Manufactured (COGM) | ✅ | ✅ All |
| **Cash flow statement & 13-week forecast** | ✅ Full (P2-D) — indirect method; inventory-value change and financing activities explicitly called out as always-zero (no point-in-time inventory valuation or debt table exists) | ✅ 7/10 |
| **Activity-Based Costing (ABC)** | ❌ | ✅ 6/10 |
| **Multi-entity / legal entity separation** | ✅ Full (P3-F) — company master + user-to-company assignment, additive `company_id` on GL | ✅ 8/10 |
| **Intercompany transactions** | ✅ Full (P3-F) — two independently-balanced journals per IC transaction, tagged per entity | ✅ 7/10 |
| **Consolidated financial reporting** | ✅ Full (P3-F) — reuses the existing unscoped income statement/balance sheet, subtracts the known IC amount as elimination | ✅ 7/10 |
| **Sustainability / carbon cost tracking** | ❌ | ✅ 5/10 |

**Priority gaps:** Activity-Based Costing, sustainability/carbon tracking.

---

### 1.7 HR, Payroll & Personnel

| Feature | Us | Top 10 |
|---|---|---|
| Employee master & profiles | ✅ Full | ✅ All |
| Department & org structure | ✅ Full | ✅ All |
| Time off requests, approvals & balances | ✅ Full | ✅ 8/10 |
| Time clock (in/out, device sync, OT detection) | ✅ Full | ✅ 8/10 |
| Payroll runs with deductions, pay stubs, YTD | ✅ Full | ✅ 9/10 |
| Performance reviews | ✅ | ✅ 7/10 |
| Training & certification tracking | ✅ | ✅ 7/10 |
| Overtime approval workflow | ✅ | ✅ 8/10 |
| **Employee self-service (ESS) portal** | ✅ Full (P2-G) — pay stubs, time-off balance/request, clock in/out, reviews/training, contact info | ✅ 7/10 |
| **Benefits management** | ❌ | ✅ 7/10 |
| **Skills matrix & competency gap analysis** | ❌ | ✅ 6/10 |
| **Workforce analytics & headcount planning** | ❌ | ✅ 7/10 |
| **Applicant Tracking / Recruiting (ATS)** | ❌ | ✅ 5/10 |

**Priority gaps:** skills matrix, benefits management, workforce analytics.

---

### 1.8 Maintenance (CMMS)

| Feature | Us | Top 10 |
|---|---|---|
| Maintenance work orders (full lifecycle) | ✅ Full | ✅ All |
| Equipment master with parent/child hierarchy | ✅ Full | ✅ 8/10 |
| Preventive maintenance scheduling (daily→annual) | ✅ Full | ✅ 8/10 |
| PM alerts (14-day advance warning) | ✅ | ✅ 8/10 |
| Downtime tracking with category & cost | ✅ Full | ✅ 7/10 |
| Maintenance parts inventory | ✅ | ✅ 8/10 |
| Maintenance inspections with corrective actions | ✅ Full | ✅ 8/10 |
| Maintenance mechanics management | ✅ | ✅ 7/10 |
| MTBF / MTTR / equipment availability metrics | ✅ Full | ✅ 7/10 |
| Barcode scanning for equipment | ✅ | ✅ 8/10 |
| **OEE (Overall Equipment Effectiveness)** | ✅ Full (P1-C, P3-G) — per-workcenter MTD card/trend/report (P1-C) plus a live per-shift dashboard and shop-floor TV display (P3-G) | ✅ 7/10 |
| **Predictive maintenance (trend-based alerts)** | ✅ Full (P4-B) — rolling interval-based MTBF, days-since-last-failure vs. threshold, 30-day failure-probability risk score | ✅ 7/10 |
| **Mobile maintenance app** | ✅ (already existed, not credited in original pass) — `mobile/app/(tabs)/maintenance.tsx`: work order list + detail + complete | ✅ 8/10 |
| **Technician routing & scheduling** | ❌ | ✅ 6/10 |
| **Asset Performance Management (APM)** | ❌ | ✅ 6/10 |
| **IoT / sensor integration** | ✅ Partial (P4-B) — manual/simulated sensor-reading entry against per-equipment warning/critical thresholds; no real device connectivity | ✅ 6/10 |

**Priority gaps:** technician routing/scheduling, Asset Performance Management, real IoT/sensor hardware connectivity.

---

### 1.9 IT Management

| Feature | Us | Top 10 |
|---|---|---|
| IT help desk ticketing | ✅ Full | ✅ (via CRM in most) |
| IT asset management + depreciation | ✅ Full | ✅ Partial |
| Software & license management | ✅ Full | ✅ Partial |
| Network device inventory | ✅ Full | ❌ Most |
| IT repairs & maintenance tracking | ✅ Full | ✅ Partial |
| IT tasks & projects | ✅ Full | ✅ Partial |
| Bandwidth monitoring | ✅ | ❌ All |
| Network incident tracking | ✅ | ❌ All |

**Note:** This ERP's IT module **exceeds all 10 competitors** — most rely on a separate ITSM tool (ServiceNow, Jira). This is a unique differentiator.

---

### 1.10 Reporting & Analytics

| Feature | Us | Top 10 |
|---|---|---|
| Per-module dashboards with KPI cards | ✅ All modules | ✅ All |
| Complete audit trail (old/new values by user/timestamp) | ✅ Full | ✅ All |
| Cross-module reports dashboard | ✅ | ✅ All |
| Financial statements (P&L, BS, TB) | ✅ Full | ✅ All |
| Quality KPI reports | ✅ | ✅ 9/10 |
| Maintenance reliability metrics (MTBF/MTTR) | ✅ | ✅ 7/10 |
| REST API for custom integrations | ✅ | ✅ All |
| **Embedded charts & graphs on dashboards** | ✅ Full (P1-A) — Chart.js on production/sales/quality/finance/maintenance dashboards, 10 charts | ✅ All |
| **Excel / CSV export from any list** | ✅ Full (P1-B, P1-G) — both formats on all 9 list pages | ✅ All |
| **Custom / self-service report builder** | ❌ | ✅ 7/10 |
| **OEE reporting** | ✅ Full (P1-C, P3-A) — dashboard card/trend + dedicated `/maint/oee/` report | ✅ 7/10 |
| **Live shop floor performance (real-time)** | ✅ Full (P3-G) — live per-shift OEE dashboard + standalone auto-refreshing TV display | ✅ 7/10 |
| **Predictive / AI analytics** | ✅ Partial (P4-A, P4-B) — seasonal-decomposition demand forecast (product × month) feeding into MRP, plus MTBF-based equipment failure-risk scoring; no broader embedded-AI analytics platform | ✅ 7/10 |
| **Batch record generation** | ❌ | ✅ 6/10 |
| **Scheduled report delivery (email)** | ✅ Partial (already existed, not credited in original pass) — `send_daily_digest` management command emails/prints a fixed KPI digest via cron/Task Scheduler; not user-configurable like a report builder | ✅ 7/10 |

**Priority gaps:** self-service report builder, broader embedded-AI analytics.

---

## Section 2: Prioritized Upgrade Roadmap

Ranked by business impact vs. build effort.

---

### 🔴 Priority 1 — High Impact, Low Effort (0–3 months)

#### P1-A: Charts & Graphs on All Dashboards ✅ Done
Every competitor has visual dashboards. All KPI data already exists — just needs Chart.js wired in.
- **Production dashboard:** daily output trend, WO completion rate
- **Sales dashboard:** pipeline funnel, revenue by period
- **Quality dashboard:** defect Pareto chart, NCR by severity trend
- **Finance dashboard:** revenue vs. expense bar chart, AR aging pie
- **Maintenance dashboard:** downtime by equipment, PM completion rate
- **Shipped:** Chart.js loaded via CDN (`<script src="cdn.jsdelivr.net/npm/chart.js">`)
  only on these 5 dashboard templates, through a new `{% block extra_scripts %}`
  in `base.html` — no global include, no vendoring/build step. Of the 10
  charts, 3 reuse data that already existed but wasn't wired into the
  dashboard view (sales pipeline funnel from `get_sales_dashboard`'s
  `quotes` dict, finance AR aging from `accounting_core.get_ar_aging`,
  maintenance downtime-by-equipment from
  `maintenance_core.get_equipment_reliability_report`); the other 7 needed
  new aggregate queries (`production_core.get_daily_output_trend`/
  `get_wo_status_breakdown`, `sales_core.get_revenue_by_month`,
  `quality_core.get_defect_pareto`/`get_ncr_severity_trend`,
  `finance_core.get_revenue_expense_by_month`,
  `maintenance_core.get_schedule_status_breakdown`). Production's daily
  output trend uses `work_order.due_date` as a completion-date proxy (no
  completed-date column exists) — the same convention
  `get_production_dashboard`'s own `completed_today` filter already uses.

#### P1-B: CSV / Excel Export on Every List Page ✅ Done
All 10 competitors have this. Users need it for analysis in Excel.
- Add Export button to: WO list, PO list, SO list, AP/AR lists, inventory, QA, maintenance, payroll
- Django: `csv.DictWriter` with `Content-Disposition: attachment` response
- Optional: `openpyxl` for formatted Excel with headers
- **Shipped:** `manufacturing/csv_export.py` (`csv_response`, built on the
  existing Qt-free `reports_core.to_csv_bytes`) + an `<page>_export` view/URL
  for each of the 9 list pages above (WO, PO, SO, AP, AR, inventory, QA NCR,
  maintenance WO, payroll history), each reusing the list view's existing
  filters. Excel (`openpyxl`) export was left for a follow-up — CSV covers
  the "open in Excel" use case competitors are scored against.

#### P1-C: OEE (Overall Equipment Effectiveness) ✅ Done
Data already exists (downtime records, production schedule, WO qty). Just apply the formula:
**OEE = Availability × Performance × Quality**
- Availability = (scheduled time − downtime) / scheduled time
- Performance = actual output / theoretical output
- Quality = (total output − scrap) / total output
- OEE card + trend chart on maintenance dashboard
- OEE report by equipment by week/month
- **Shipped:** `manufacturing/oee_core.py` computes OEE per **workcenter**
  (not per `maint_equipment` — the two tables have no FK, only free-text
  names, so downtime is folded in via a best-effort name match).
  Availability uses `workcenter.capacity_hours_per_day`; Performance/Quality
  use `wo_operation.std_hours/actual_hours/scrap_qty` joined to the parent
  WO's `quantity`. Maintenance dashboard now shows a month-to-date OEE card
  plus an 8-week trend (plain CSS bars, no charting lib yet — see P1-A), and
  `/maint/oee/` is a full report with a week/month toggle and a per-workcenter
  breakdown table.

#### P1-D: Cycle Count Workflow ✅ Done
Inventory on-hand data exists. Need the structured count process.
- Generate cycle count sheet (by bin, by ABC class, by product category)
- Count entry screen (scan or enter counted qty per item)
- Variance identification (counted vs. system qty)
- Variance approval → auto-post inventory adjustment
- **Shipped:** `manufacturing/cycle_count_core.py` + `/inventory/cycle-counts/`.
  Sheets group by `product.bin` or `item_type` (real columns) or an
  **on-the-fly ABC class** (there's no persisted category/ABC column, so it's
  ranked by extended value — on-hand × unit cost — top 20%/next 30%/rest each
  time a sheet is generated, not cached). Variance approval reuses the
  generic `approval_workflow_core` engine (added `'cycle_count'` to
  `ENTITY_TYPES`) rather than the PO-specific one, since approval should
  gate on variance magnitude, not a flat entity total. **If no
  `approval_rule` is configured for `cycle_count`, submission fails open and
  posts immediately** — this doesn't reduce existing control (adjustments
  could always be posted directly before this feature existed), but an org
  wanting an approval gate needs to add an `approval_rule` row themselves;
  there's no admin UI for that yet. Posting reuses `inventory_core
  .record_transaction(..., 'adjust', ...)` per variant line.

#### P1-E: Price List Module ✅ Done
Required before ATP can be meaningful. Sales currently has no pricing engine.
- Price list master (name, currency, effective/expiry dates)
- Price list lines (product → unit price, min qty for tiered pricing)
- Customer-to-price-list assignment on customer master
- Auto-populate unit price when adding SO line item
- **Shipped:** `manufacturing/price_list_core.py` + `/price-lists/` admin
  pages, reusing `currency_core` for the currency field. There was no
  sale/list price concept anywhere before this (only `product.purchase_price`,
  which is a cost) — fully new. Customer assignment adds
  `customer.price_list_id` (a new column; the customer/supplier CRUD in
  `contacts_core.py` is shared between both tables, so assignment is a
  separate `assign_customer_price_list()` write path rather than threaded
  through the generic update). SO auto-populate is **client-side**: the SO
  detail view embeds the assigned customer's price tiers as JSON, and a
  small vanilla-JS handler on the product/qty fields fills in the unit
  price for the correct tier — no AJAX round-trip, matching this app's
  existing no-JS-framework convention. Also fixed a pre-existing crash in
  `contacts_detail.html` (order history row used `{{ o.so_number|default:
  o.po_number }}`, which 500s when `po_number` doesn't exist on a customer's
  SO row at all) — found while verifying this feature since it blocked the
  customer detail page for any customer with order history.

#### P1-F: Request for Quote (RFQ) ✅ Done
Missing from purchasing. All 10 competitors have it.
- RFQ creation: select vendors, add line items with qty & target price
- Vendor quote entry: each vendor records their price per line
- Side-by-side quote comparison table
- Select winning vendor → one-click convert to Purchase Order
- **Shipped:** `manufacturing/rfq_core.py` + `/rfq/`. New tables (`rfq`,
  `rfq_item`, `rfq_vendor`, `rfq_quote_line` — no existing multi-vendor
  concept anywhere to reuse; requisitions are single-implicit-vendor).
  Comparison table flags the lowest quote per line and defaults the winner
  dropdown to it. **Award is per line item, not per RFQ** — different
  lines can go to different vendors; `award_items()` groups awarded lines
  by vendor and creates one draft PO per vendor via the existing
  `purchase_orders_core.create_po`/`add_po_item`, using each line's
  *quoted* price (falling back to target price if unquoted). The existing
  PO approval flow (`approval_core`, triggered on draft→sent) picks up the
  new PO automatically — no RFQ-specific approval integration needed.
  **Bug found and fixed while verifying:** `purchase_order.order_date` has
  a live NOT NULL constraint not reflected in `create_po`'s DDL/signature
  (both allow `None`) — every existing caller happens to always supply a
  real date, but `award_items()` initially didn't, causing every
  award-to-PO conversion to 500. Fixed by passing today's date explicitly.

#### P1-G: Excel Export on Every List Page ✅ Done
Closes the "CSV only" gap called out in the 2026-07-08 refresh — every top-10 competitor offers
native Excel export, not just CSV.
- **Shipped:** Extended `manufacturing/csv_export.py` with `excel_response()` and a format-dispatch
  `export_response(request, base_filename, columns, rows)` that picks CSV or XLSX from `?format=xlsx`,
  sharing the exact same `columns`/`rows` assembly each of the 9 `_export` views already built for
  P1-B — no view logic duplicated, only the final serialization step branches. `excel_response()`
  itself is a thin wrapper around `reports_core.export_to_excel()`, a Qt-free XLSX builder that
  **already existed with full test coverage in `test_phase5_reports.py` but had never been wired
  into any view** — found while implementing this, so this feature is mostly a wiring exercise, not
  new serialization code. All 9 list pages (WO, PO, SO, AP, AR, inventory, QA NCR, maintenance WO,
  payroll history) now show both "⬇ Export CSV" and "⬇ Export Excel" buttons side by side, each
  preserving that page's existing filters in the querystring. Verified end-to-end against a running
  dev server: logged in, hit all 9 `?format=xlsx` endpoints (200 + correct
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` content type + `.xlsx`
  filename), and loaded one of the downloaded files back with `openpyxl` to confirm real headers,
  bold header row, and correct row data — not just a non-empty byte stream.

---

### 🟠 Priority 2 — High Impact, Medium Effort (3–6 months)

#### P2-A: Gantt Chart Production Scheduler ✅ Done
No visual scheduling is the biggest gap vs. Epicor, Infor, SYSPRO.
- Work order Gantt view grouped by workcenter
- Visual bars showing WO start/end, color-coded by status
- Drag-and-drop to reschedule (update WO dates + operation sequences)
- Workcenter load bar below Gantt (used hrs vs. capacity hrs)
- Red highlight when workcenter is over-capacity
- **Library:** DHTMLX Gantt (JS) or frappe/gantt (open source)
- **Shipped:** New scheduling logic lives in `routing_core.py` (bars are
  per-`wo_operation`, not per-WO, since operations can span multiple
  workcenters). New `scheduled_start`/`scheduled_end` columns on
  `wo_operation` persist real schedule data; when unset, bars fall back to
  a proportional split of the parent WO's start/due dates. Drag-and-drop
  reschedule persists via a `fetch()`-based AJAX endpoint (`views/_gantt.py`)
  — the app's first, since `dept_required`'s redirect-on-deny doesn't fit a
  JSON consumer, so it's guarded by manual auth/dept/read-only checks that
  always return JSON instead. Web page: `/schedule/gantt/`
  (`prod_schedule_gantt.html`), wired from Production → Schedule.

#### P2-B: Available-to-Promise (ATP) ✅ Done
Required for customer-facing delivery date commitments.
- ATP qty = on-hand + open PO receipts scheduled before requested date − already committed SO qty
- Display ATP qty and earliest available date on SO line item entry
- Warn on SO confirm if ATP is insufficient
- ATP inquiry screen: enter product + qty + date → get yes/no + alternatives
- **Shipped:** `manufacturing/atp_core.py` — ATP qty = on-hand + open PO
  receipts (sent/partial, expected before the requested date) − committed
  demand (confirmed SOs), mirroring `mrp_web_core.get_demand_dated`'s
  NULL-ship_date fallback exactly so ATP and MRP never disagree on what
  counts as committed. Ships a dedicated `/atp/` inquiry screen (product/
  qty/date → yes/no + earliest available date within a 90-day search), a
  live ATP badge on the SO line-item entry form (green/red against the
  typed qty), and a soft confirm-gate on SO confirmation — a shortfall
  banner with a "Confirm Anyway" override rather than a hard block.

#### P2-C: Supplier Performance Scorecard ✅ Done
Data already exists (POs, receiving, QA supplier scores). Just needs aggregation.
- On-time delivery % (PO expected date vs. actual receipt date)
- Quantity fill rate % (qty received / qty ordered)
- Quality reject rate % (from QA supplier ratings)
- Composite score (weighted average of the three)
- Supplier scorecard page with trend charts
- Supplier ranking report (sort by score)
- **Shipped:** `manufacturing/supplier_scorecard_core.py` — a pure computed
  view (no new tables) over `purchase_order`/`po_item` and `qa_supplier`.
  On-time % is measured against a new `purchase_order.received_date`
  column, stamped by `set_po_status` the first time a PO reaches
  `'received'` (there was previously no receipt-date tracking anywhere in
  the PO domain). Fill rate is `qty_received`/`qty_ordered` over placed POs.
  Quality reject % comes from `qa_supplier.ppm`, matched to a supplier by
  name (that table has no `supplier_id` FK). The composite score
  renormalises over whichever of the three metrics a supplier actually has
  data for, so missing QA ratings don't drag a supplier's score to zero.
  Web pages: `/suppliers/scorecard/` (ranking list) and
  `/suppliers/scorecard/<id>/` (per-supplier breakdown + Chart.js monthly
  on-time/fill-rate trend), wired from Purchasing → Vendor Performance and
  QA → Supplier Scorecards.

#### P2-D: Cash Flow Statement & 13-Week Forecast ✅ Done
GL data + AR/AP due dates exist. Need the statement and rolling forecast.
- Cash flow statement (operating: net income ± AR/AP/inventory changes; investing: fixed asset purchases; financing: loans)
- 13-week forecast: pull AR invoices due + AP invoices due by week
- Cash balance projection graph
- Add to finance dashboard
- **Shipped:** `manufacturing/cash_flow_core.py` — a pure computed view (no
  new tables) building an indirect-method statement from
  `accounting_core.income_statement` (net income), a new
  `finance_core.get_cash_position` (actual bank balance, also reused by the
  13-week forecast's starting point), period-over-period AR/AP balance
  snapshots, and a depreciation addback via
  `fixed_asset_core.calc_annual_depreciation`. Two gaps are called out
  explicitly rather than faked: inventory value change (no point-in-time
  inventory valuation exists anywhere in this schema) and financing
  activities (no loan/debt table exists in the codebase at all, so that
  section is always zero). The forecast buckets currently-outstanding AR/AP
  by due date into 13 weekly buckets, folding already-overdue amounts into
  week 1. Web pages: `/gl/cash-flow/` (statement) and `/fin/forecast/`
  (forecast + Chart.js balance projection), plus a new Cash Flow section
  on `/fin/` (finance dashboard).

#### P2-E: Sampling Plans & AQL ✅ Done
Required for formal incoming inspection programs.
- AQL table (ISO 2859-1): lot size range → sample size code → sample size
- Sampling plan master: AQL level (0.65, 1.0, 2.5, 4.0, etc.), inspection level (I, II, III)
- Accept/reject numbers per plan
- Attach sampling plan to product or supplier
- On inspection creation: auto-calculate sample size from lot qty + plan
- Pass/fail result based on defects found vs. accept number
- **Shipped:** `manufacturing/sampling_plan_core.py` — lot-size-range →
  code-letter and code-letter → sample-size are fixed ISO 2859-1 values, so
  they're Python constants (`LOT_SIZE_RANGES`/`SAMPLE_SIZE_BY_CODE`), not DB
  tables. `aql_accept_reject` (code letter + AQL% → Ac/Re numbers) and the
  `sampling_plan` master (AQL level, inspection level, optional product/
  supplier attachment) are DB tables. **The seeded accept/reject data
  covers only AQL 0.65/1.0/1.5/2.5/4.0 for code letters C-N and is built
  from the standard's known diagonal structure — verify against your
  organization's official ISO 2859-1 / ANSI-ASQ Z1.4 tables before relying
  on this for regulated/compliance decisions.** `quality_core.
  create_inspection` now accepts an optional `sampling_plan_id` + `lot_qty`
  and auto-stamps the resolved code letter/sample size/accept/reject onto
  the new inspection; a new `record_sample_defects` auto-sets
  passed/failed once the inspector enters how many sampled units were
  defective. Web pages: `/sampling-plans/` (CRUD) plus the existing
  `/qa/inspections/` flow extended with the sampling-plan picker and AQL
  results card. Also fixed a pre-existing crash in
  `qa_inspection_detail.html` (a `|split:','` template filter that doesn't
  exist in Django) discovered while testing this feature — the inspection
  detail page 500'd on every load before this fix.

#### P2-F: Document Control Module ✅ Done
Needed for ISO 9001 compliance and engineering document management.
- Document master: number, title, type (SOP, WI, Drawing, Spec), revision, status
- Status workflow: draft → in review → approved → superseded → obsolete
- Revision history: change description, changed by, date
- File attachment (PDF/Word stored as blob or file path)
- Approval workflow (same approval engine as POs/PRs)
- Link documents to: BOM, routing, inspection template, equipment
- Document search and filter
- **Shipped:** `manufacturing/document_control_core.py` — `document` +
  `document_revision` + `document_link` tables. Reused `approval_workflow_core`
  by adding `'document'` to its `ENTITY_TYPES` allow-list, but with one
  important wrinkle: `submit_for_approval` is idempotent on
  `(entity_type, entity_id)`, and a document's own row id is stable across
  every revision and every review round, so reusing it as `entity_id` would
  make a second review round silently hand back the *first* round's
  already-decided steps. Each review round is instead submitted against that
  revision's own `document_revision.id` (tracked as `document.
  current_revision_id`), and a rejection explicitly deletes that round's
  `approval_step` rows so resubmitting the same revision starts a clean
  round rather than getting permanently stuck 'in_review' with a stale
  rejected step and nothing pending to decide — caught by hand-testing the
  reject → resubmit path in a real browser session, not by the unit tests
  alone. Fails open like `cycle_count_core` when no `approval_rule` exists
  for `'document'` yet — a submitted document is approved immediately
  rather than blocked on an unconfigured workflow. This is also the app's
  first feature to accept file uploads (`MEDIA_ROOT`/`MEDIA_URL` added to
  settings.py); uploaded files are only ever served back through the
  authenticated `document_download` view, not exposed under a static
  `MEDIA_URL` route, so access control matches every other page. Links to
  BOM/sampling-plan/equipment/workcenter resolve a display label via a
  small per-type lookup (a BOM link points at the governed `product`, since
  the `bom` table has no header row of its own to link to instead); a
  routing link is entered by ID since no "list all routing steps" picker
  existed yet. Web pages: `/documents/` (list + search/filter), `/documents/
  new/`, `/documents/<id>/` (info, file upload/download, submit-for-review,
  inline approve/reject, revise, supersede/obsolete, linked records) — wired
  from both QA → Document Control and Engineering → Design Documents, whose
  menu leaves previously pointed at unrelated placeholder pages.

#### P2-G: Employee Self-Service (ESS) Portal ✅ Done
Reduces HR workload for routine employee requests.
- Employee login (separate session context or role-filtered view)
- View own: pay stubs, YTD earnings, deductions
- View own: time off balance, request history
- Submit new time off request from portal
- Clock in/out from portal (web-based time clock)
- View own performance reviews and training records
- Update own contact info / emergency contact
- **Shipped:** New `/ess/` pages (`views/_ess.py`), gated by plain
  `login_required` rather than a dept/role check — employees belong to
  every department, so nothing here can be gated the way most of this app
  is. Every detail view (`ess_pay_stub_detail`, `ess_review_detail`,
  `ess_training_detail`) does an explicit ownership check (the record's
  `people_id` against the caller's own, looked up from `user_email` per
  request — `people_id` was never in the session) rather than relying on
  a decorator. Two of the six requirements were **already fully
  self-service before this PR** and needed no new code: time-off request/
  history (`/time-off/`) and clock in/out (`/time-clock/`) — ESS just
  links to them. Pay stubs needed one new query
  (`payroll_core.list_pay_stubs_for_employee`, since the existing
  `get_pay_stub`/`list_run_employees` only look up by entry id or run id,
  never "all of one employee's stubs"); reviews/training needed new
  self-scoped views only, since `personnel_core.list_reviews`/
  `list_trainings` already supported a `people_id` filter — the existing
  web views for both were HR-only (`dept_required('personnel', ...)`).
  **Time-off balance was fully greenfield** — no accrual concept existed
  anywhere in the schema. Kept deliberately simple: a new
  `time_off_balance(people_id, year, allotted_days)` table (defaulting to
  15 days/year when no row exists) minus days actually taken from
  *approved* `'Vacation'`-type requests that year, computed from
  `time_off_request` on every read rather than stored, so there's one
  source of truth. Contact info also needed new `people` columns (`phone`,
  `emergency_contact_*`) plus a narrow `update_own_contact_info` that
  deliberately does *not* expose `dept_id`/`employee_id`/name, unlike the
  HR-facing `update_person` — an employee shouldn't be able to reassign
  their own department through their own profile page. Wired into
  navigation via a new "My Info" link in the global sidebar (`base.html`)
  rather than through `menus.py`/`WEB_LEAF_URLS`, since that system is
  keyed per-department and ESS needs to be reachable from all of them.

#### P2-H: MRP → Auto-Release Purchase Orders ✅ Done
Critical for MRP to be actionable. Currently MRP generates suggestions but POs must be created manually.
- From MRP plan screen: "Release Selected" button
- For each selected planned order (buy type): auto-create PO with preferred supplier + lead time date
- For each selected planned order (make type): auto-create Work Order
- Show count of POs/WOs created on release
- **Shipped:** This was mostly already built — `mrp_web_core.release_plan`,
  the `mrp_plan.html` selection UI, and the `mrp_release.html` results page
  all existed before this change and are covered by an existing test suite.
  The one missing piece was the preferred-supplier lookup: `release_plan`'s
  buy branch always called `create_po(..., supplier_id=None, ...)`, and
  `load_mrp_inputs` didn't even select `product.supplier_id`. Fixed by
  joining `supplier` in `load_mrp_inputs`, threading `supplier_id`/
  `supplier_name` through `run_mrp`/`run_mrp_dated` onto each planned
  order, and passing it into `create_po` when present (falls back to
  `None` with a "no preferred supplier on file" note otherwise, same as
  before). `mrp_plan.html` now shows a Supplier column per buy row;
  `mrp_release.html` shows the assigned supplier (or a "none on file"
  warning) per created PO. **Found and fixed a real, pre-existing crash
  while manually verifying this end-to-end**: on this dev DB,
  `purchase_order.supplier_id` had somehow ended up `NOT NULL` at the
  Postgres level despite the DDL in `purchase_orders_core.py` declaring it
  plain `INTEGER` (nullable) — the "Live schema can diverge from the
  `CREATE TABLE` DDL" gotcha this doc already warns about elsewhere. That
  meant *every* buy-type MRP release without a resolvable supplier would
  have 500'd (confirmed manual PO creation without a supplier does too) —
  this was never exercised by the unit tests since they mock `create_po`
  entirely. Fixed by adding an `ALTER COLUMN supplier_id DROP NOT NULL`
  migration to `ensure_po_tables` (a no-op if already nullable) and calling
  `ensure_wo_tables`/`ensure_po_tables` at the top of `release_plan` so any
  environment with the same divergence self-heals on the next release —
  neither was called anywhere in that code path before.

---

### 🟡 Priority 3 — Strategic Value, Higher Effort (6–12 months)

#### P3-A: Finite Capacity Scheduling (APS) ✅ Done
Full constraint-aware scheduler — significant effort but core mid-market differentiator.
- Workcenter capacity calendar (hours available per day/shift)
- Forward scheduling: from today + operation sequence → calculate start/end per workcenter
- Backward scheduling: from SO due date → pull back through routing → set start dates
- Capacity check: sum scheduled hrs per workcenter per day vs. available hrs
- Load leveling: auto-suggest splitting or delaying WOs to resolve overload
- Bottleneck identification: which workcenter is constraining overall throughput
- **Shipped:** `manufacturing/capacity_planning_core.py`, building on top of
  the P2-A Gantt scheduler's `wo_operation.scheduled_start/scheduled_end`
  columns rather than duplicating them. **Calendar:** `works_mon`…`works_sun`
  boolean columns on `workcenter` (default Mon–Fri) plus a sparse
  `workcenter_calendar_exception(workcenter_id, exception_date,
  hours_available)` table for one-off holiday closures or overtime days —
  deliberately not a full shift-table model, since a single daily-hours
  scalar plus day-of-week + exception overrides covers the stated
  requirement without over-building. **Forward/backward scheduling:**
  `forward_schedule_wo`/`backward_schedule_wo` pack each operation's
  `std_hours` into whichever days have free capacity on its workcenter
  (a day-granular model — no shift-start-time concept beyond a flat
  `DEFAULT_WORKDAY_START_HOUR`), enforcing that operation N+1 never starts
  before operation N's actual finish even across *different* workcenters
  (a `not_before`/`not_after` constraint was needed for this — same-
  workcenter sequencing falls out for free from a shared per-workcenter
  booked-hours ledger, but cross-workcenter handoffs have no other link
  between the two operations' schedules). Backward schedules from the
  **work order's own due date**, not a sales order's — there is no SO↔WO
  link anywhere in the schema (confirmed via research before building
  this), so "backward from SO due date" is satisfied one level removed:
  set the WO's due date (manually, or however it gets set today) and
  backward-schedule from that; a `result['at_risk']` flag fires if the
  computed start falls before today. **Capacity check:** `get_capacity_check`
  buckets booked-vs-available hours per workcenter *per day* (the existing
  P2-A `get_planned_workcenter_load` only summed over the whole visible
  window, not per-day — kept as-is for the Gantt view's aggregate load bar,
  since changing it risked that feature's pinned test suite). **Bottleneck
  identification:** `identify_bottlenecks` ranks workcenters by utilization
  % over a horizon. **Load leveling:** `suggest_load_leveling` is a greedy
  heuristic (probe forward for the first day with enough slack for one
  over-capacity operation), not a constraint solver — one suggestion per
  overloaded day, applied via `apply_load_leveling_suggestion`. Web pages:
  `/prod/schedule/capacity/` (heatmap + bottleneck ranking + suggestions
  with an Apply button, wired from the `cap_plan` menu leaf which
  previously just redirected to the production dashboard), a per-workcenter
  `/workcenters/<id>/calendar/` page (working days + exceptions), and two
  new buttons on the WO detail page ("Auto-Schedule Forward" / "Schedule
  to Due Date"). **Found and fixed two bugs while verifying live:**
  `routing_core.get_wo_operations` never selected `scheduled_start`/
  `scheduled_end` at all (P2-A's Gantt view reads schedule data through a
  different function, `get_gantt_operations`, so this never surfaced until
  something else needed `get_wo_operations` to show scheduled dates); and
  the cross-workcenter sequencing gap described above, caught by watching
  a real two-operation, two-workcenter work order schedule with the second
  operation starting before the first one finished.

#### P3-B: Warehouse Management System (WMS) ✅ Done
Full pick/pack/ship with bin-level tracking.
- Bin master: warehouse → zone → aisle → rack → shelf → bin
- Put-away rules: by product category or ABC class → bin zone assignment
- Pick list generation from confirmed SOs (grouped by zone, optimized path)
- Pack station: create cartons, scan items in, record carton weight/dimensions
- Ship confirmation: carrier + tracking number + actual ship date
- Receiving put-away: scan PO receipt → assign to bin → update inventory
- **Shipped:** `manufacturing/wms_core.py`. Today, stock is tracked only as
  a single aggregate `product.amount` plus a free-text `product.bin`
  string — and, more importantly, **neither PO receiving nor shipment
  creation ever adjusted `product.amount`** before this PR; only manual
  adjustment forms, cycle-count posting, and one mobile-only endpoint did.
  This closes that gap in both directions, funneling every new
  inventory-affecting action through the existing
  `inventory_core.record_transaction`. **Bin hierarchy:** a flat model —
  `wms_warehouse`/`wms_zone` are real parent tables, but aisle/rack/shelf
  are plain text columns on `wms_bin` itself rather than their own tables
  (far less schema/CRUD surface for the same functional coverage, matching
  this codebase's generally denormalized style). **Bin quantity** lives in
  a new `wms_bin_stock(bin_id, product_id, qty)`, always adjusted in the
  same transaction as the `product.amount` aggregate via one internal
  helper, `_adjust_bin_stock` — never independently. **No big-bang
  migration:** a lazily-created sentinel "unassigned" bin
  (`get_or_create_unassigned_bin`) stands in for all pre-existing
  `product.amount` that predates this feature; assigning/picking from it
  still adjusts the aggregate but skips bin-level tracking, so the system
  self-heals as inventory turns over and gets received into real bins
  through the new flow. **Put-away rules:** match a product's `category`
  (new column — grepped the whole schema first, confirmed no prior
  category concept existed) or ABC class (reusing
  `cycle_count_core.compute_abc_classes`, which already documents ABC as
  deliberately unpersisted/computed-on-the-fly — not duplicating that
  decision with a new persisted column) to a target zone; first-match-by-
  priority, not a scoring model. **Pick lists:** one per confirmed SO in
  v1 (no partial/backorder splitting across multiple pick lists); lines
  ordered by a greedy `(zone.pick_sequence, bin.full_code)` sort — an
  "optimized path" in the sense of a simple zone-aware sort, not a real
  routing/TSP solver, matching the precedent set by P3-A's load-leveling
  heuristic. **Receiving integration:** the pinned, already-in-use
  `purchase_orders_core.receive_po_item` is wrapped, not modified (it has
  exact-SQL-asserting tests) — a new `receive_and_putaway` computes the
  delta against the item's current `qty_received` (the existing function
  takes an absolute total, not a delta) and credits both the aggregate and
  the chosen bin. The *legacy* `/po/<id>/` receive view (not the pinned
  core function) was also additively patched to credit the received delta
  into the unassigned bin, so inventory correctness doesn't depend on
  which of the two receiving screens someone uses. **Ship confirmation**
  reuses `production_core.create_shipment`/`add_shipment_item` and only
  ever exercises the already-legal `confirmed → shipped` SO transition
  once, at the end — `SO_STATUS_TRANSITIONS` itself is untouched. Web
  pages added under `/wms/...` (bins, put-away rules, receive, pick lists,
  pack station, ship confirm), wired from a new "Warehouse Management"
  submenu under Production → Shipping, and the existing (previously
  placeholder) "Receive Items" leaf now points at the new receiving
  screen. Verified end-to-end against a running dev server + local
  Postgres: created a zone/bin and a put-away rule, received a real PO
  line into it (confirmed `product.amount`, `wms_bin_stock`, and
  `po_item.qty_received` all moved together), generated a pick list from a
  confirmed sample SO, picked → packed (carton with weight/dimensions) →
  confirmed shipment (confirmed the SO and pick list both transitioned to
  `shipped`, and a real `shipment`/`shipment_item` row was created), and
  confirmed the legacy PO receive screen now also credits inventory.
  `cycle_count_core`'s legacy grouping by the free-text `product.bin`
  column is deliberately untouched and coexists with the new bin tables —
  not the same concept, not migrated in this PR.

#### P3-C: Customer Self-Service Portal ✅ Done
- Separate customer login (not employee account)
- View own orders, invoices, shipment status
- Download invoice PDF and packing slip
- Submit RMA request online
- Track shipment (carrier API lookup by tracking number)
- Pay invoice online (Stripe payment intent)
- **Shipped:** `manufacturing/customer_portal_core.py` +
  `manufacturing/views/_portal.py`, under `/portal/...`. **Login is additive,
  not a fresh signup system:** customers already exist as staff-created
  `customer` rows (Sales/CS); portal access is a new `customer_login` table
  (`customer_id` FK unique, bcrypt hash) layered on top, matched at
  registration time against that customer's own `email` (case-insensitive) —
  no blind account creation. Session lives in its own namespace
  (`portal_customer_id`/`portal_email`/`portal_company`), deliberately
  separate from the employee `user_*` keys, with a new
  `auth_decorators.customer_login_required` (redirects to `portal_login`, no
  dept/role concept applies to a customer). Every detail view does an
  explicit ownership check — the record's `customer_id`, or
  `sales_order.customer_id` via join for shipments/RMAs (neither carries a
  direct `customer_id` column) — against the caller's own, same pattern as
  ESS's per-row `people_id` check. **No forked data model:** orders/invoices
  reuse `sales_orders_core.list_sos`/`get_so` and
  `accounting_core.list_ar_invoices`/`get_ar_invoice` as-is (customer_id
  filtering and balance computation already existed); paying an invoice calls
  the existing `accounting_core.record_ar_payment`, which already recomputes
  invoice status from total received — nothing new there either. **Stubbed,
  not wired to a real network call:** no Stripe/carrier-API/outbound-HTTP
  precedent exists anywhere in this codebase (checked repo-wide, including
  both requirements files and settings.py) — the closest analog is
  `EMAIL_BACKEND`'s env-driven, safe-default-in-dev shape. `get_tracking_events`
  returns a deterministic synthetic timeline derived from the shipment's own
  carrier/status/ship_date (no randomness, unit-testable); `create_payment_intent`/
  `confirm_payment_intent` (new `portal_payment_intent` table) model the
  Stripe PaymentIntent create→confirm shape without a network call or added
  `stripe` dependency — swapping in a real integration means replacing those
  two function bodies only. **PDFs** via `reportlab` (already an
  undeclared dependency through `barcode_core.py`; now pinned in
  `requirements.txt`), mirroring its existing `SimpleDocTemplate` usage.
  Verified end-to-end against a running dev server + local Postgres: registered
  portal access for a seeded customer, logged in, confirmed the dashboard/orders/
  invoices/RMAs shown are scoped to that customer only (spot-checked a second
  customer's SO/shipment returns 404), downloaded an invoice PDF and a packing-
  slip PDF, submitted an RMA against an owned SO (and confirmed one against an
  unowned SO is rejected), paid an open invoice and confirmed the `ar_payment`
  row + invoice status update, and viewed a shipment's tracking timeline.

#### P3-D: Landed Cost Allocation ✅ Done
Required for accurate COGM when importing goods.
- Landed cost record per PO receipt: freight, duty, broker fee, insurance
- Allocation methods: by value (% of line total), by weight, by quantity
- Allocated cost added to item receipt value → updates inventory cost
- Impacts COGM and cost variance reporting
- **Shipped:** `manufacturing/landed_cost_core.py` + `manufacturing/views/_landed_cost.py`,
  nested under the PO (`po/<id>/landed-cost/new/`, `po/<id>/landed-cost/<lc_id>/`),
  with a new "Landed Costs" card on `po_detail.html`. **A separate, explicit
  action, not auto-triggered by receiving:** freight/duty/broker/insurance
  bills typically arrive *after* goods are received, as a follow-up AP step,
  so this operates on whatever `po_item` rows already have `qty_received > 0`
  at the moment staff enter it — `purchase_orders_core.receive_po_item` (pinned
  by exact-SQL-asserting tests, same as P3-B's `receive_po_item` wrap) is
  neither modified nor hooked into. **No forked cost model:** this codebase
  has no lot-level or receipt-level costing anywhere — `product.purchase_price`
  is the single per-unit cost field, read directly by
  `costing_core.roll_standard_cost` (buy-item standard cost) and
  `compute_wo_actual_cost` (material actuals). So allocation increases
  `product.purchase_price` by the per-unit allocated amount (largest-remainder
  rounding so the lines sum exactly to the entered total) — the next standard-
  cost roll or WO actual-cost computation picks up the new cost automatically,
  with no separate report to change. This is average-cost-style: it raises the
  product's cost going forward for *all* consumption, not just the units from
  this specific receipt, since there's no per-lot cost attribution anywhere
  in this codebase to do better than that. **`product.weight` added
  additively** (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, same pattern as
  P3-B's `product.category`) since no weight/dimension concept existed
  anywhere for buy items — genuinely a product attribute, so it's reusable
  across future landed-cost entries rather than re-entered every time (a
  per-line override is still accepted for one-off use); the weight method
  errors clearly if every line resolves to zero weight. **No GL posting:**
  `costing_core.post_po_receipt_gl` exists but has zero callers anywhere in
  this codebase (PO-receipt GL posting was defined but never wired up) —
  this feature follows that same precedent rather than inventing new GL
  machinery. Verified end-to-end against a running dev server + local
  Postgres: allocated a landed cost by value across a PO's two received
  lines (confirmed the allocated amounts sum exactly to the entered total
  and `product.purchase_price` increased by precisely `allocated/qty_received`
  on each), confirmed a subsequent `costing_core.roll_standard_cost` picks up
  the new cost, allocated again by weight with a per-line override, and
  confirmed the "zero weight" and "no received items yet" validation errors
  surface correctly.

#### P3-E: Blanket Purchase Orders & Call-offs ✅ Done
Standard for long-term supplier agreements.
- Blanket PO: vendor, total value or qty, validity start/end dates
- Call-off (release): child of blanket, specific qty + delivery date
- Remaining balance calculation (total − sum of call-offs)
- Auto-close blanket when fully released or expired
- **Shipped:** `manufacturing/blanket_po_core.py`. A blanket PO is a
  standalone standing-agreement record, not an extension of the existing
  one-shot `purchase_order`/`po_item` model — it tracks a single running
  ceiling (either `total_value` or `total_qty`, whichever the agreement is
  denominated in; the other stays 0 and is ignored in the balance math) and
  call-offs (`blanket_po_release`) draw down against it. This is
  deliberately **not** wired into PO receiving at all: `purchase_orders_
  core.receive_po_item` is pinned by exact-SQL-asserting tests, and a
  blanket PO has no line items of its own to receive against, so the two
  systems don't touch. **Auto-close/auto-expire is computed lazily**, not
  via a scheduled job — this codebase's only periodic-job precedent
  (`management.send_daily_digest`) is manually invoked, not a running cron,
  so instead every read (`list_blanket_pos`/`get_blanket_po`) and every
  `create_release` call re-derives the effective status (fully released →
  `closed`; past `end_date` and still open → `expired`) and persists it only
  if it changed. Over-allocation (a call-off that would exceed the
  remaining balance) and call-offs against a non-`open` blanket are both
  rejected with a `ValueError` surfaced to the form. Web pages added at
  `/blanket-po/...` (list, new, detail with a "Call-offs" card, add
  call-off, cancel), gated `@dept_required('purchasing')` matching the
  existing PO views, linked from a new "Blanket POs" toolbar button on
  `po_list.html` (matching the RFQ/Landed Cost precedent of a direct link
  rather than a `menus.py` leaf). **Correction during merge:** the original
  version of this feature tried to repurpose the purchasing menu's existing
  `new_cont`/`act_cont`/`cont_arch` `WEB_LEAF_URLS` keys, on the mistaken
  assumption they were unrouted desktop-only stubs — they were not: those
  keys already route to a live, unrelated "Purchasing Contracts" (vendor
  contracts) feature shipped in PR #287, so the duplicate dict keys both
  failed `ruff` (F601) and would have silently broken that feature's
  navigation. Fixed by dropping the stolen `WEB_LEAF_URLS` entries and
  adding the toolbar link instead. Verified end-to-end against a running dev server + local
  Postgres (both via direct core calls and through the actual web views
  with a simulated session): created a value-tracked blanket PO and added
  call-offs, confirming remaining balance decreased correctly and an
  over-limit call-off was rejected; fully released it and confirmed it
  auto-closed; created a qty-tracked blanket PO and confirmed its balance
  tracks quantity instead of value; backdated a blanket PO's `end_date` and
  confirmed it read back as `expired`; cancelled an open blanket PO and
  confirmed further call-offs against it were rejected.

#### P3-F: Multi-Company / Multi-Entity ✅ Done
Required for companies with multiple legal entities.
- Company master: separate legal entities with own GL, currency, tax ID
- User-to-company assignment (user can access one or more entities)
- Intercompany transactions: IC sale in entity A → IC purchase in entity B
- Consolidated P&L and balance sheet across entities
- Elimination entries for intercompany balances
- Separate chart of accounts per entity (or shared with overrides)
- **Shipped:** `manufacturing/multi_entity_core.py`. There was no legal-
  entity concept anywhere in this codebase — the GL is one flat, global
  ledger (`gl_account`/`gl_journal`/`gl_journal_line`), duplicated across
  three separate posting code paths. Rather than re-architecting the GL
  into per-entity ledgers, this follows the scope discipline the P2-D
  multi-currency feature set: a new `company` master, plus a nullable
  `company_id` tag added additively (`ALTER TABLE ... ADD COLUMN IF NOT
  EXISTS`) to `gl_account` (NULL = shared account usable by every entity —
  the spec's "shared chart of accounts with overrides" option, chosen over
  duplicating the whole chart) and to `gl_journal` (NULL = a pre-existing/
  legacy journal). **No backfill:** historical journals don't "turn over"
  the way inventory does, so there's no safe migration — instead one
  lazily-created `company` row (`is_base_entity=True`, via
  `get_or_create_base_company`, same sentinel spirit as `wms_core.
  get_or_create_unassigned_bin`) stands in for all pre-existing data, and
  that entity's own reports ask `accounting_core` to also include
  `company_id IS NULL` rows via a new `include_null_company` flag.
  **`accounting_core.account_balance`/`_period_balance`/`trial_balance`/
  `income_statement`/`balance_sheet`** gained optional `company_id=None`/
  `include_null_company=False` kwargs — when `None` (every pre-existing
  caller) the SQL and behavior are byte-for-byte unchanged, which is what
  kept this change safe against the full existing test suite with zero
  regressions. **Consolidated statements** are just those same functions
  called with `company_id=None` (already "all entities combined," since
  there's only one ledger) — `multi_entity_core.consolidated_income_
  statement`/`consolidated_balance_sheet` then subtract the known
  intercompany amount as the elimination. **Intercompany transactions**
  need four GL accounts, not two: the billing entity's own book records
  `ic_receivable` (Asset) against `ic_revenue` (Revenue); the billed
  entity's own book records `ic_expense` (Expense) against `ic_payable`
  (Liability) — two independently-balanced journals, each tagged to one
  company via `gl_journal.company_id`, posted through the existing,
  unmodified `accounting_core.create_journal`/`post_journal`. Summed
  together they net to zero, which is exactly the elimination property:
  consolidated revenue and expense both drop by the same amount (net
  income unaffected — correct for a pure internal recharge with no
  external profit), and consolidated assets/liabilities both drop by the
  same amount (balance sheet stays balanced). If any of the four accounts
  aren't mapped yet, the transaction is still recorded but left unposted —
  mirrors `costing_core.post_po_receipt_gl`'s "skip with a warning rather
  than failing" precedent. Account mapping reuses the existing
  `gl_account_map` table but not `costing_core.set_gl_account_map` — that
  setter validates against `costing_core.GL_CATEGORIES`, which
  `tests/test_costing_core.py` asserts as an exact set and can't be
  extended — so `multi_entity_core.set_ic_account_map` is its own small
  upsert against the same table using its own `IC_GL_CATEGORIES`, in the
  same category namespace without touching `costing_core` at all.
  **User-to-company assignment**: a `company_user` join table; full-access
  roles (President, VP) bypass it and see every company, everyone else
  only sees companies they're explicitly assigned to — enforced in both
  `company_list` and `company_detail` (an unassigned company_id redirects
  away, same as an ownership-check 404 elsewhere in this codebase). Web
  pages at `/companies/...`, `/intercompany/...`, and `/consolidated-
  financials/`, surfaced from a new "Multi-Entity" submenu under the
  Accounting main menu (`menus.py`) via `views.WEB_LEAF_URLS` — company/
  user-assignment CRUD is gated `@role_required` to President/VP only,
  viewing and posting intercompany transactions is `@dept_required`
  ('accounting', 'finance'). Verified end-to-end against a running dev
  server + local Postgres (through the actual web views with simulated
  sessions, not just unit tests): created two companies, mapped all four
  IC accounts, posted an intercompany transaction and confirmed each
  company's own trial balance showed exactly the two accounts it should
  (and nothing from the other entity), confirmed the consolidated income
  statement/balance sheet eliminated the exact transaction amount from
  both revenue/expense and assets/liabilities with net income unchanged,
  confirmed a non-full-access user saw zero companies until assigned, saw
  the company immediately after assignment, and lost access immediately
  after revocation — then cleaned up all test data.

#### P3-G: OEE Live Shop Floor Dashboard ✅ Done
Real-time production visibility — Plex's core differentiator.
- Operator production entry: shift + workcenter + units produced + units scrapped
- Downtime entry from shop floor (reason code)
- Live OEE calculation per workcenter per shift
- Shop floor TV display mode (large format, auto-refresh)
- Shift summary: planned vs. actual output
- **Shipped:** `manufacturing/shop_floor_core.py`. An earlier feature
  (P1-C, `oee_core.py`) already computes OEE, but only as a **date-range
  report** derived from completed `wo_operation` rows and `maint_downtime`
  — there was no shift concept anywhere in this codebase and no data-entry
  screen at all (its only UI is a read-only report under Maintenance). This
  is the first operator-facing data-entry layer and the first live/TV
  view, not a rebuild of P1-C — the two calculations run in parallel at
  different granularities (period vs. shift) over different source data
  (WO-operation actuals vs. manual shift tallies). `oee_core._oee_from_
  totals` isn't reused because its Performance formula (`std_hours /
  actual_hours`) assumes a linked work-order operation, which a shift's
  manual qty/scrap entry doesn't have (the spec's "shift + workcenter +
  units produced + units scrapped" has no WO field) — Performance here is
  `qty_produced / planned_qty` instead, which doubles as the "planned vs.
  actual output" shift-summary bullet so one calculation serves both.
  **Two documented simplifying assumptions**, made because no shift-window
  or shift-length concept exists anywhere else to derive them from: every
  shift is a fixed 8-hour scheduled window regardless of `workcenter.
  capacity_hours_per_day`, and `SHIFT_WINDOWS` fixes wall-clock hours per
  shift name (Day/Swing/Night, matching `maintenance_core.MECHANIC_
  SHIFTS`' naming) purely to default the dashboard/TV display to "right
  now's" shift with zero operator input. **Deliberately diverges from
  `oee_core`'s convention** in one place: Performance defaults to 100% (not
  0%) when no shift plan has been set — an unset plan means "no target to
  compare against," not "nothing happened," so treating it as a failure
  would misrepresent real output. Reuses `routing_core.workcenter`/
  `list_workcenters` for the workcenter dimension and `maintenance_core.
  DOWNTIME_CATEGORIES` as the downtime reason-code taxonomy, rather than
  duplicating either. Web pages at `/shop-floor/entry/` (production +
  downtime logging), `/shop-floor/plan/` (supervisor sets planned qty per
  workcenter/shift/date), `/shop-floor/` (live dashboard with
  shift/date pickers), and `/shop-floor/tv/` (a standalone, high-contrast,
  large-format page with no toolbar/nav chrome, auto-refreshing via a
  30-second `<meta http-equiv="refresh">` — the simplest possible
  auto-refresh mechanism, avoiding new JS/polling machinery for a
  report-style page), wired into a new "Shop Floor" submenu under the
  Production main menu. Verified end-to-end against a running dev server +
  local Postgres through the actual web views: logged production and
  downtime entries for a real workcenter, set a shift plan, confirmed the
  dashboard's summed totals and OEE breakdown were exactly right
  (Availability/Performance/Quality/OEE all hand-checked against the raw
  entries), confirmed the TV page renders standalone with no app chrome,
  and cleaned up all test data afterward.

---

### 🔵 Priority 4 — Future / Advanced (12+ months)

#### P4-A: AI Demand Forecasting ✅ Done
- Pull 24+ months of SO history
- Apply time-series model (seasonal decomposition, Holt-Winters, or Prophet)
- Generate forecast by product by month for next 12 months
- Display as overlay on actual orders in demand dashboard
- Feed forecast into MRP as additional demand
- **Shipped:** `manufacturing/demand_forecast_core.py`. Not the same thing
  as the existing "Sales forecasting with actuals & variance" — that's
  `sales_core.py`'s `sales_forecast` table, a rep/product-line/quarter
  **quota** a person types in (`expected_value` × `probability` =
  `weighted_value`), with no time-series computation and no product/month
  grain. This is a genuinely new, computed forecast, generated from
  historical shipped/closed Sales Order lines. **No data-science library
  exists anywhere** in `requirements.txt` (no pandas/numpy/statsmodels/
  prophet), so — consistent with this codebase's pattern of not adding a
  new dependency for one feature — the time-series model is a hand-rolled
  **classical seasonal decomposition** in pure Python, one of the three
  methods the spec names and far more tractable to implement correctly
  without a library than Holt-Winters' parameter optimization: a
  closed-form least-squares trend line, plus a per-calendar-month seasonal
  index (average actual/trend ratio for that month across however many
  years of history exist, normalized to mean 1.0). With under 12 months of
  history there's no full seasonal cycle to measure, so it falls back to a
  flat, trend-only projection rather than fabricating seasonality from
  partial data. The existing "demand dashboard" (`views.sales_demand`,
  `/sales/demand/`) is revenue-based and quarterly, grouped by product
  name — mixing that grain/unit with a qty/month forecast would be a
  confusing hybrid, so this ships as its own `/demand-forecast/` page
  (product × month, in units, actual history overlaid with projected
  future months via a bar-per-row table, mirroring `sales_demand.html`'s
  existing convention rather than adding a charting library), cross-linked
  from both pages. **MRP integration is fully additive**:
  `mrp_web_core.run_mrp_dated` gained one optional parameter,
  `include_forecast: bool = False` — the default and every existing
  caller's behavior is byte-for-byte unchanged; when `True` (a checkbox on
  the MRP run form), `demand_forecast_core.get_forecast_demand_dated`
  returns forecast rows in exactly the `{product_id: [(qty, date), ...]}`
  shape `get_demand_dated` already produces, so it's a plain per-product
  list-extend, not a rewrite of `plan_orders_dated`/`get_demand_dated`
  themselves. Verified end-to-end against a running dev server + local
  Postgres through the actual web views: generated forecasts from real SO
  history, confirmed the dashboard overlay renders actual vs. forecast
  correctly, ran MRP once with the checkbox off (unchanged plan) and once
  on (forecast-driven demand visibly added more planned orders — 9 → 18 in
  the verification run), and cleaned up all test data afterward.

#### P4-B: Predictive Maintenance ✅ Done
- Track rolling MTBF per equipment from historical downtime
- Alert when actual interval since last failure approaches MTBF × 0.8
- Vibration/temperature threshold alerts (requires IoT sensor hook)
- Maintenance risk score per equipment (probability of failure in next 30 days)
- **Shipped:** `manufacturing/predictive_maintenance_core.py`. MTBF/MTTR
  already existed ("Phase 6B", `maintenance_core.get_mtbf`/
  `get_equipment_reliability_report`), but only as a **period aggregate**
  (`(period_hours - total_downtime_hours) / failure_count`) with no
  concept of individual failure dates — it can't say "time since last
  failure" or trend per equipment. This adds **rolling, interval-based
  MTBF**: the mean gap between consecutive `'Breakdown'`-category
  `maint_downtime` records for that equipment, using the same
  `equipment ILIKE %s AND category = 'Breakdown'` predicate as the
  existing (exact-SQL-pinned, untouched) `get_mtbf`. Needs >= 2 breakdown
  events to compute an interval; equipment with 0-1 shows "insufficient
  data" rather than a misleading number. The 30-day failure probability
  uses the standard exponential/Poisson-process approximation from a mean
  interval (`1 - exp(-30/mtbf_days)`, `math.exp` — stdlib, no new
  dependency), bucketed into low/medium/high risk. **No sensor/IoT
  concept existed anywhere** in this codebase, so the vibration/
  temperature bullet is an explicitly documented manual/simulated
  data-entry stub (a technician — or a future real integration — logs
  readings against a per-equipment/reading-type warning/critical
  threshold), the same honest scoping choice used for P3-C's Stripe
  integration; there is no real sensor hardware connectivity. Alerts are
  computed live on every read, matching every other alert function in
  this codebase (`lot_core.get_expiry_alerts`, `maintenance_core.
  get_pm_alerts`) — no new persisted alerts table. New page at
  `/predictive-maintenance/` (one row per active equipment: MTBF, days
  since last failure, alert threshold, 30-day risk %, risk level, latest
  sensor status) plus `/predictive-maintenance/sensor-reading/new/` and
  `/predictive-maintenance/sensor-threshold/`, wired into a new
  "Predictive Maintenance" leaf under the Maintenance main menu and
  cross-linked from the Maintenance dashboard. Verified end-to-end
  against a running dev server + local Postgres through the actual web
  views: inserted real breakdown records 30 and 26 days apart for a real
  piece of equipment and confirmed rolling MTBF (28.0 days), days-since-
  last-failure (41), approaching-threshold flag, and 30-day risk
  (65.7%, "high") all hand-checked correct; logged a sensor reading and a
  threshold and confirmed the alert status correctly transitioned
  ok → warning → critical as the logged value crossed each threshold;
  confirmed `tests/test_phase6.py`'s existing MTBF tests still pass
  unchanged; cleaned up all test data afterward.

#### P4-C: Capable-to-Promise (CTP) ✅ Done
- Extends ATP with routing capacity check
- Before confirming SO: check material available (ATP) AND workcenter capacity on required dates
- If insufficient: suggest earliest date when both material AND capacity are available
- Show breakdown: "material ready in 5 days, capacity available in 8 days → CTP date: [date]"
- **Shipped:** `manufacturing/capable_to_promise_core.py`, a thin
  combination layer over two existing features rather than a rewrite of
  either. **ATP (P2-B, `atp_core.get_atp`/`check_so_atp`)** already
  answers "date when qty will be available," reused as-is for the
  material half. **Finite capacity scheduling (P3-A,
  `capacity_planning_core.py`)** had the building blocks
  (`_load_workcenter_calendar`/`get_booked_hours_by_day`) but no "earliest
  date N hours are free" function — that module gained exactly one
  additive function, `earliest_capacity_date(conn, workcenter_id,
  hours_needed, from_date, horizon_days)`, walking forward and
  accumulating free (available − booked) hours per day until the running
  total covers the requirement (documented simplification: treats free
  hours as fungible across days, matching this module's existing
  "no separate allocation ledger" approximation). CTP combines both:
  `get_workcenter_hours_required` scales a product's routing `std_hours`
  by quantity and groups by workcenter; `get_capacity_availability` finds
  the latest earliest-date across all workcenters a routing touches (all
  must have room); `get_ctp` returns the full breakdown — material date,
  capacity date per workcenter, and the combined `ctp_date` (their max).
  A product with no routing at all has nothing to schedule, so capacity
  isn't a constraint for it (treated as immediately available, not
  "unavailable"). **SO confirm-flow integration touches nothing pinned**:
  `views.so_set_status`'s existing ATP confirm-gate (`if target ==
  'confirmed' and not override and check_so_atp(...)`) now also ORs in
  a new `check_so_capacity(conn, so_id)` — same shortfall-list
  convention as `check_so_atp` (empty = covered), same redirect, same
  single "Confirm Anyway" override; `sales_orders_core.set_so_status`/
  `so_can_transition` are untouched. `so_detail.html` shows both ATP and
  capacity shortfalls in one combined warning banner. A new standalone
  `/ctp/` inquiry page mirrors `/atp/`'s exact GET-form/POST-compute
  convention (linked from `so_list.html`'s toolbar, next to "ATP
  Inquiry" — ATP itself has no menu entry either, so CTP follows that
  same precedent). Verified end-to-end against a running dev server +
  local Postgres: ran a real product's CTP breakdown and confirmed
  distinct material/capacity dates with the combined date as their max;
  created and attempted to confirm a real SO whose demand (100 units)
  exceeded workcenter capacity, confirmed the confirm action was blocked
  with a capacity-shortfall banner distinct from a pure ATP shortfall,
  and confirmed "Confirm Anyway" successfully overrode both checks;
  cleaned up all test data afterward.

#### P4-D: EDI Integration ✅ Done
- EDI 850 inbound: customer PO → auto-create Sales Order
- EDI 855 outbound: SO acknowledgment to customer
- EDI 856 outbound: Advance Ship Notice on shipment
- EDI 810 outbound: invoice to customer
- Map via configurable field mappings per trading partner
- **Shipped:** `manufacturing/edi_core.py`. No AS2/VAN/SFTP network
  connectivity is available in this environment, so the trading-partner
  *connection* is honestly scoped as a file upload/download stub (a
  technician receives/sends the `.edi` file some other way). But the
  **X12 document format itself is real, parsed/generated text**
  (segment-delimited `~`, `*`-separated elements) — unlike a payment
  processor or IoT sensor, this isn't a fake integration, just a common-
  subset implementation of the standard (not every optional segment/
  qualifier code). `product` has no SKU/code column anywhere in this
  codebase, so a trading partner's own part numbers (carried in the
  850's PO1 segments) have nothing to match against — a new
  `edi_partner_item_xref(customer_id, partner_item_number, product_id)`
  table is the actual field-mapping mechanism the spec's "configurable...
  per trading partner" bullet asks for, not a generic abstraction. An
  inbound line with no mapping still imports as a valid `so_item`
  (`product_id=None`, using the partner's raw item number as the
  description) — not an error, mirroring how `so_item` already supports
  text-only lines. **Reuses existing, unmodified functions for every real
  side effect**: `sales_orders_core.next_so_number`/`create_so`/
  `add_so_item` (850 inbound — both exact-SQL-pinned in `tests/test_
  sales_orders_core.py`, called as-is rather than duplicated),
  `production_core.get_shipment`/`get_shipment_items` (856), `accounting_
  core.get_ar_invoice` (810). `ar_invoice` has no line-item table in this
  codebase, so the 810 emits one summary line (amount + description) —
  an honest reflection of the existing invoice model, not fabricated
  detail. Every parse/generate action is logged to `edi_transaction_log`
  with its raw content, giving a real audit trail. New pages at
  `/edi/partners/...` (trading partner + item xref setup), `/edi/850/
  upload/`, `/edi/855|856|810/<id>/download/`, and `/edi/log/`, reusing
  this codebase's existing file-upload (`document_control`'s pattern) and
  file-download (`_barcode.py`'s `Content-Disposition` pattern)
  conventions; cross-linked from `so_list.html`, `so_detail.html`, the
  shipment detail page, and `ar_invoice_detail.html`. Verified end-to-end
  against a running dev server + local Postgres through the actual web
  views: configured a real trading partner + item mapping, hand-built a
  realistic 850 referencing both a mapped and an intentionally-unmapped
  partner item number, uploaded it and confirmed a real SO was created
  with the mapped line correctly resolving to the right `product_id` and
  the unmapped line correctly staying text-only; downloaded the 855 and
  confirmed it reflected the same lines; downloaded the 856 for a real
  shipment and confirmed real carrier/tracking/item data appeared;
  downloaded the 810 for a real AR invoice and confirmed the real amount/
  description appeared; confirmed the transaction log showed all four
  actions; cleaned up all test data afterward.

#### P4-E: e-Commerce Integration
- Shopify / WooCommerce webhook: new order → auto-create SO
- Inventory level sync: push on-hand qty to storefront on every transaction
- Product catalog sync: push price list changes to storefront
- Shipment confirmation: push tracking number back to storefront order

#### P4-F: Custom Report Builder
- Field selector: pick any table/column to include
- Filter builder: add conditions (field, operator, value)
- Group-by and aggregate (sum, count, avg)
- Sort order configuration
- Save report with name and access level
- Schedule delivery: run on schedule → email CSV/PDF to recipients

#### P4-G: Sustainability / Carbon Cost Tracking
- CO₂ emission factor per material (kg CO₂e per unit)
- CO₂ emission factor per process/operation (kg CO₂e per hour)
- Carbon cost rollup on BOM → product carbon footprint
- Carbon intensity metric: kg CO₂e per unit produced
- ESG dashboard: scope 1 (direct), scope 2 (energy), scope 3 (supply chain)

---

## Section 3: Competitive Positioning Summary

### Where This ERP Already Leads or Matches Mid-Market

| Advantage | vs. Competitors |
|---|---|
| **SPC (X-bar/R charts, Cpk)** | Better than Fishbowl, JobBOSS, MRPeasy; matches Epicor/SYSPRO |
| **IT Asset + License + Network management** | Deeper than ALL 10 competitors (most need separate ITSM) |
| **Sales commission & territory management** | Better than Fishbowl, JobBOSS, MRPeasy |
| **Full audit trail (old/new values)** | Matches SAP/Oracle/Dynamics enterprise level |
| **Multi-level approval workflows** | Matches Epicor, SYSPRO, Infor |
| **Barcode scanning breadth** | 10+ entity types; matches all mid-market platforms |
| **MTBF/MTTR reliability metrics** | Better than Fishbowl, JobBOSS, MRPeasy |
| **Fixed Assets with depreciation schedule** | Matches all platforms (just added) |
| **Multi-currency on PO/SO/AP/AR** | Matches all platforms (just added) |

### Newly Closed Since the Original Pass (2026-07-05 → 2026-07-08)

| Former Gap | Shipped As |
|---|---|
| No visual Gantt / production board | P2-A |
| No charts/graphs on dashboards | P1-A |
| No CSV export | P1-B |
| No OEE tracking | P1-C |
| No cycle count workflow | P1-D |
| No price lists | P1-E |
| No RFQ module | P1-F |
| No finite APS / constraint scheduling | P3-A |
| No ATP | P2-B |
| No supplier scorecards | P2-C |
| No cash flow statement / forecast | P2-D |
| No sampling plans / AQL | P2-E |
| No document control | P2-F |
| No ESS portal | P2-G |
| No MRP → auto-release POs | P2-H |
| No WMS (pick/pack/ship) | P3-B |
| No Excel export (CSV only) | P1-G |
| No landed cost allocation | P3-D |
| No blanket orders & call-offs | P3-E |
| No customer self-service portal | P3-C |
| No multi-entity / intercompany / consolidated reporting | P3-F |
| No live/real-time shop-floor OEE dashboard or TV display | P3-G |
| No AI/ML demand forecasting | P4-A |
| No predictive maintenance / failure-risk scoring | P4-B |
| No Capable-to-Promise (CTP) | P4-C |

### Where We Trail Mid-Market (Epicor / SYSPRO / Infor target)

| Gap | Effort to Close |
|---|---|
| No FIFO/LIFO/weighted-average valuation | Medium |
| No true inter-warehouse transfers | Low–Medium |
| No consignment / cross-docking / wave picking / RFID | Medium |
| No self-service report builder | Medium (P4-F) |

### Where We Trail Enterprise (SAP / Oracle / Dynamics)

| Gap | Effort to Close |
|---|---|
| No broader embedded-AI analytics platform | Very High |
| No EDI | High (P4-D) |
| No real IoT / sensor hardware integration | Very High |
| No supplier self-service portal | High |
| No carrier API / e-commerce integration | Medium–High (P4-E) |

---

## Section 4: Feature Gap Score Card

| Domain | Score vs. Mid-Market | Score vs. Enterprise | Change |
|---|---|---|---|
| Work Orders & BOM | 9/10 | 8/10 | — |
| MRP | 8/10 | 7/10 | — |
| Inventory | 7/10 | 6/10 | ▲ (cycle count + WMS bins; still no FIFO/LIFO or transfers) |
| Quality (QA) | 9/10 | 8/10 | ▲ (sampling/AQL + document control) |
| Purchasing | 9/10 | 9/10 | ▲▲▲ (RFQ + scorecards + MRP auto-release + landed cost + blanket POs) |
| Sales / CRM | 9/10 | 8/10 | ▲▲▲ (ATP + price lists + customer portal + CTP) |
| Finance / GL | 9/10 | 9/10 | ▲▲ (cash flow statement/forecast + multi-entity/intercompany/consolidated) |
| Fixed Assets | 9/10 | 8/10 | — |
| Multi-Currency | 8/10 | 7/10 | — |
| HR / Payroll | 8/10 | 7/10 | ▲ (ESS portal) |
| Maintenance (CMMS) | 9/10 | 9/10 | ▲▲▲ (OEE + live shop-floor dashboard/TV (P3-G) + predictive maintenance risk scoring (P4-B); mobile app now credited) |
| IT Management | 10/10 | 9/10 | — |
| Reporting / Analytics | 8/10 | 8/10 | ▲▲▲▲▲ (charts, CSV+Excel export, OEE reports, live shop-floor OEE (P3-G), AI demand forecast (P4-A), digest now credited) |
| Scheduling / APS | 8/10 | 6/10 | ▲▲▲ (P3-A finite capacity scheduling) |
| WMS / Shipping | 7/10 | 6/10 | ▲▲▲ (P3-B full pick/pack/ship) |
| **Overall** | **8.7/10** | **7.8/10** | **▲ from 7.1 / 5.9** |

---

## Section 5: Next 10 Features to Build (Ordered by ROI)

All 16 of the original "next 10 + P3-A/B" items are shipped, plus Excel export (P1-G), landed
cost allocation (P3-D), blanket POs/call-offs (P3-E), and the customer self-service portal (P3-C).

**Status update (2026-07-08):** the remaining roadmap — P4-D through P4-G — turned out to already
have open PRs from a prior session (#392–#395), discovered while working through this list. Being
merged one at a time (rebase onto current `main`, verify, fix any cross-PR conflicts, confirm
before merging) rather than re-built. Once that pass completes, only these will remain genuinely
unbuilt:

1. **True inter-warehouse transfers** (extends P3-B) — `wms_core.py` already has multiple
   warehouses/zones/bins; a transfer is "ship from bin A, receive into bin B" reusing
   `_adjust_bin_stock`, no new subsystem needed. No PR found for this one.
2. **FIFO / LIFO / Weighted Average costing** (extends Inventory) — every top-10 competitor has
   this; currently `product` has no cost-layer concept at all, so this is a real schema addition,
   not a query. No PR found for this one.

---

*This document is maintained in the repository at `manufacturing/COMPETITIVE_GAP_ANALYSIS.md`.*
*Update this file as features are added to track progress against the roadmap.*
