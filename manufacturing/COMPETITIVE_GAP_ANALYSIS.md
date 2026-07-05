# Manufacturing ERP — Competitive Gap Analysis
**Generated:** 2026-07-05  
**Compared Against:** SAP S/4HANA, Oracle Cloud Manufacturing, Microsoft Dynamics 365 SCM, Epicor Kinetic, Infor CloudSuite Industrial, Plex Manufacturing Cloud, SYSPRO, Fishbowl, JobBOSS², MRPeasy

---

## Executive Summary

This ERP is a **fully-featured mid-market system** with strong parity in core manufacturing, quality, maintenance, purchasing, sales, HR, payroll, accounting, and IT management. It holds its own against platforms like Infor CloudSuite, SYSPRO, and Epicor for the majority of day-to-day operations.

The primary gaps fall into five areas:
1. **Advanced Planning & Scheduling (APS)** — no finite scheduling, Gantt, or constraint-based sequencing
2. **AI / Predictive Analytics** — no embedded AI, no predictive maintenance, no ML demand forecasting
3. **Shop Floor / MES** — no OEE, no IoT/sensor connectivity, no real-time machine data
4. **Supply Chain Depth** — no Available-to-Promise, no Capable-to-Promise, no landed cost, no EDI
5. **Multi-Company / Multi-Site** — single-entity model; no intercompany, no legal entity separation

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
| **Advanced Planning & Scheduling (APS)** | ❌ | ✅ 8/10 |
| **Finite capacity scheduling** | ❌ | ✅ 8/10 |
| **Gantt chart drag-and-drop scheduler** | ❌ | ✅ 8/10 |
| **Constraint-based sequencing** | ❌ | ✅ 7/10 (Infor core) |
| **Bottleneck analysis** | ❌ | ✅ 7/10 |
| **What-if scenario planning** | ❌ | ✅ 8/10 |
| **Configure-to-Order (CTO)** | ❌ | ✅ 7/10 |
| **Recipe / formula management (process mfg)** | ❌ | ✅ 7/10 |
| **Repetitive manufacturing** | ❌ | ✅ 7/10 |

**Priority gaps:** APS + Gantt scheduler, finite capacity, what-if scenarios.

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
| **True multi-warehouse with transfers** | ❌ | ✅ All |
| **Warehouse Management System (WMS)** | ❌ | ✅ 9/10 |
| **Pick / Pack / Ship automation** | ❌ | ✅ 9/10 |
| **Cycle count structured workflow** | ❌ | ✅ All |
| **Consignment inventory** | ❌ | ✅ 7/10 |
| **Cross-docking** | ❌ | ✅ 6/10 |
| **Wave picking management** | ❌ | ✅ 6/10 |
| **RFID integration** | ❌ | ✅ 8/10 |
| Barcode scanning (entity lookup + label printing) | ✅ Full | ✅ All |

**Priority gaps:** True WMS with pick/pack/ship, cycle count workflow, FIFO/LIFO costing, multi-warehouse transfers.

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
| **Sampling plans & AQL (acceptance quality limit)** | ❌ | ✅ 8/10 |
| **Control plans & FMEA** | ❌ | ✅ 7/10 |
| **Certificate of Analysis (CoA) generation** | ❌ | ✅ 7/10 |
| **Document control & version management** | ❌ | ✅ 8/10 |
| **Regulatory compliance templates (FDA, ISO)** | ❌ | ✅ 7/10 |

**Priority gaps:** Sampling plans/AQL, CoA generation, document control module, FMEA.

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
| **Request for Quote (RFQ) module** | ❌ | ✅ All |
| **Vendor quote comparison & scoring** | ❌ | ✅ All |
| **Supplier performance scorecard** | ❌ | ✅ 7/10 |
| **Supplier collaboration / self-service portal** | ❌ | ✅ 6/10 |
| **Blanket orders & call-offs** | ❌ | ✅ 9/10 |
| **Freight & landed cost allocation** | ❌ | ✅ 7/10 |
| **EDI (850/856/810)** | ❌ | ✅ 8/10 |
| **Auto-generated POs from MRP** | ❌ | ✅ All |

**Priority gaps:** RFQ with quote comparison, supplier scorecards, blanket orders, landed cost, MRP→PO auto-release.

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
| **Available-to-Promise (ATP)** | ❌ | ✅ 9/10 |
| **Capable-to-Promise (CTP)** | ❌ | ✅ 6/10 |
| **Price list management & tiered pricing** | ❌ | ✅ All |
| **Discount & promotion management** | ❌ | ✅ All |
| **Customer self-service portal** | ❌ | ✅ 7/10 |
| **Shipping & carrier API integration (FedEx/UPS/USPS)** | ❌ | ✅ 9/10 |
| **Multi-channel order integration (e-commerce)** | ❌ | ✅ 7/10 |

**Priority gaps:** ATP/CTP, price lists, carrier integration, customer portal.

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
| **Cash flow statement & 13-week forecast** | ❌ | ✅ 7/10 |
| **Activity-Based Costing (ABC)** | ❌ | ✅ 6/10 |
| **Multi-entity / legal entity separation** | ❌ | ✅ 8/10 |
| **Intercompany transactions** | ❌ | ✅ 7/10 |
| **Consolidated financial reporting** | ❌ | ✅ 7/10 |
| **Sustainability / carbon cost tracking** | ❌ | ✅ 5/10 |

**Priority gaps:** Cash flow forecasting, multi-entity/intercompany, consolidated reporting.

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
| **Employee self-service (ESS) portal** | ❌ | ✅ 7/10 |
| **Benefits management** | ❌ | ✅ 7/10 |
| **Skills matrix & competency gap analysis** | ❌ | ✅ 6/10 |
| **Workforce analytics & headcount planning** | ❌ | ✅ 7/10 |
| **Applicant Tracking / Recruiting (ATS)** | ❌ | ✅ 5/10 |

**Priority gaps:** Employee self-service portal, skills matrix, benefits management.

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
| **OEE (Overall Equipment Effectiveness)** | ❌ | ✅ 7/10 |
| **Predictive maintenance (trend-based alerts)** | ❌ | ✅ 7/10 |
| **Mobile maintenance app** | ❌ | ✅ 8/10 |
| **Technician routing & scheduling** | ❌ | ✅ 6/10 |
| **Asset Performance Management (APM)** | ❌ | ✅ 6/10 |
| **IoT / sensor integration** | ❌ | ✅ 6/10 |

**Priority gaps:** OEE tracking, mobile app, predictive maintenance trend alerts.

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
| **Embedded charts & graphs on dashboards** | ❌ | ✅ All |
| **Excel / CSV export from any list** | ❌ | ✅ All |
| **Custom / self-service report builder** | ❌ | ✅ 7/10 |
| **OEE reporting** | ❌ | ✅ 7/10 |
| **Live shop floor performance (real-time)** | ❌ | ✅ 7/10 |
| **Predictive / AI analytics** | ❌ | ✅ 7/10 |
| **Batch record generation** | ❌ | ✅ 6/10 |
| **Scheduled report delivery (email)** | ❌ | ✅ 7/10 |

**Priority gaps:** Charts/graphs everywhere, CSV/Excel export, OEE, report builder.

---

## Section 2: Prioritized Upgrade Roadmap

Ranked by business impact vs. build effort.

---

### 🔴 Priority 1 — High Impact, Low Effort (0–3 months)

#### P1-A: Charts & Graphs on All Dashboards
Every competitor has visual dashboards. All KPI data already exists — just needs Chart.js wired in.
- **Production dashboard:** daily output trend, WO completion rate
- **Sales dashboard:** pipeline funnel, revenue by period
- **Quality dashboard:** defect Pareto chart, NCR by severity trend
- **Finance dashboard:** revenue vs. expense bar chart, AR aging pie
- **Maintenance dashboard:** downtime by equipment, PM completion rate

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

#### P1-E: Price List Module
Required before ATP can be meaningful. Sales currently has no pricing engine.
- Price list master (name, currency, effective/expiry dates)
- Price list lines (product → unit price, min qty for tiered pricing)
- Customer-to-price-list assignment on customer master
- Auto-populate unit price when adding SO line item

#### P1-F: Request for Quote (RFQ)
Missing from purchasing. All 10 competitors have it.
- RFQ creation: select vendors, add line items with qty & target price
- Vendor quote entry: each vendor records their price per line
- Side-by-side quote comparison table
- Select winning vendor → one-click convert to Purchase Order

---

### 🟠 Priority 2 — High Impact, Medium Effort (3–6 months)

#### P2-A: Gantt Chart Production Scheduler
No visual scheduling is the biggest gap vs. Epicor, Infor, SYSPRO.
- Work order Gantt view grouped by workcenter
- Visual bars showing WO start/end, color-coded by status
- Drag-and-drop to reschedule (update WO dates + operation sequences)
- Workcenter load bar below Gantt (used hrs vs. capacity hrs)
- Red highlight when workcenter is over-capacity
- **Library:** DHTMLX Gantt (JS) or frappe/gantt (open source)

#### P2-B: Available-to-Promise (ATP)
Required for customer-facing delivery date commitments.
- ATP qty = on-hand + open PO receipts scheduled before requested date − already committed SO qty
- Display ATP qty and earliest available date on SO line item entry
- Warn on SO confirm if ATP is insufficient
- ATP inquiry screen: enter product + qty + date → get yes/no + alternatives

#### P2-C: Supplier Performance Scorecard
Data already exists (POs, receiving, QA supplier scores). Just needs aggregation.
- On-time delivery % (PO expected date vs. actual receipt date)
- Quantity fill rate % (qty received / qty ordered)
- Quality reject rate % (from QA supplier ratings)
- Composite score (weighted average of the three)
- Supplier scorecard page with trend charts
- Supplier ranking report (sort by score)

#### P2-D: Cash Flow Statement & 13-Week Forecast
GL data + AR/AP due dates exist. Need the statement and rolling forecast.
- Cash flow statement (operating: net income ± AR/AP/inventory changes; investing: fixed asset purchases; financing: loans)
- 13-week forecast: pull AR invoices due + AP invoices due by week
- Cash balance projection graph
- Add to finance dashboard

#### P2-E: Sampling Plans & AQL
Required for formal incoming inspection programs.
- AQL table (ISO 2859-1): lot size range → sample size code → sample size
- Sampling plan master: AQL level (0.65, 1.0, 2.5, 4.0, etc.), inspection level (I, II, III)
- Accept/reject numbers per plan
- Attach sampling plan to product or supplier
- On inspection creation: auto-calculate sample size from lot qty + plan
- Pass/fail result based on defects found vs. accept number

#### P2-F: Document Control Module
Needed for ISO 9001 compliance and engineering document management.
- Document master: number, title, type (SOP, WI, Drawing, Spec), revision, status
- Status workflow: draft → in review → approved → superseded → obsolete
- Revision history: change description, changed by, date
- File attachment (PDF/Word stored as blob or file path)
- Approval workflow (same approval engine as POs/PRs)
- Link documents to: BOM, routing, inspection template, equipment
- Document search and filter

#### P2-G: Employee Self-Service (ESS) Portal
Reduces HR workload for routine employee requests.
- Employee login (separate session context or role-filtered view)
- View own: pay stubs, YTD earnings, deductions
- View own: time off balance, request history
- Submit new time off request from portal
- Clock in/out from portal (web-based time clock)
- View own performance reviews and training records
- Update own contact info / emergency contact

#### P2-H: MRP → Auto-Release Purchase Orders
Critical for MRP to be actionable. Currently MRP generates suggestions but POs must be created manually.
- From MRP plan screen: "Release Selected" button
- For each selected planned order (buy type): auto-create PO with preferred supplier + lead time date
- For each selected planned order (make type): auto-create Work Order
- Show count of POs/WOs created on release

---

### 🟡 Priority 3 — Strategic Value, Higher Effort (6–12 months)

#### P3-A: Finite Capacity Scheduling (APS)
Full constraint-aware scheduler — significant effort but core mid-market differentiator.
- Workcenter capacity calendar (hours available per day/shift)
- Forward scheduling: from today + operation sequence → calculate start/end per workcenter
- Backward scheduling: from SO due date → pull back through routing → set start dates
- Capacity check: sum scheduled hrs per workcenter per day vs. available hrs
- Load leveling: auto-suggest splitting or delaying WOs to resolve overload
- Bottleneck identification: which workcenter is constraining overall throughput

#### P3-B: Warehouse Management System (WMS)
Full pick/pack/ship with bin-level tracking.
- Bin master: warehouse → zone → aisle → rack → shelf → bin
- Put-away rules: by product category or ABC class → bin zone assignment
- Pick list generation from confirmed SOs (grouped by zone, optimized path)
- Pack station: create cartons, scan items in, record carton weight/dimensions
- Ship confirmation: carrier + tracking number + actual ship date
- Receiving put-away: scan PO receipt → assign to bin → update inventory

#### P3-C: Customer Self-Service Portal
- Separate customer login (not employee account)
- View own orders, invoices, shipment status
- Download invoice PDF and packing slip
- Submit RMA request online
- Track shipment (carrier API lookup by tracking number)
- Pay invoice online (Stripe payment intent)

#### P3-D: Landed Cost Allocation
Required for accurate COGM when importing goods.
- Landed cost record per PO receipt: freight, duty, broker fee, insurance
- Allocation methods: by value (% of line total), by weight, by quantity
- Allocated cost added to item receipt value → updates inventory cost
- Impacts COGM and cost variance reporting

#### P3-E: Blanket Purchase Orders & Call-offs
Standard for long-term supplier agreements.
- Blanket PO: vendor, total value or qty, validity start/end dates
- Call-off (release): child of blanket, specific qty + delivery date
- Remaining balance calculation (total − sum of call-offs)
- Auto-close blanket when fully released or expired

#### P3-F: Multi-Company / Multi-Entity
Required for companies with multiple legal entities.
- Company master: separate legal entities with own GL, currency, tax ID
- User-to-company assignment (user can access one or more entities)
- Intercompany transactions: IC sale in entity A → IC purchase in entity B
- Consolidated P&L and balance sheet across entities
- Elimination entries for intercompany balances
- Separate chart of accounts per entity (or shared with overrides)

#### P3-G: OEE Live Shop Floor Dashboard
Real-time production visibility — Plex's core differentiator.
- Operator production entry: shift + workcenter + units produced + units scrapped
- Downtime entry from shop floor (reason code)
- Live OEE calculation per workcenter per shift
- Shop floor TV display mode (large format, auto-refresh)
- Shift summary: planned vs. actual output

---

### 🔵 Priority 4 — Future / Advanced (12+ months)

#### P4-A: AI Demand Forecasting
- Pull 24+ months of SO history
- Apply time-series model (seasonal decomposition, Holt-Winters, or Prophet)
- Generate forecast by product by month for next 12 months
- Display as overlay on actual orders in demand dashboard
- Feed forecast into MRP as additional demand

#### P4-B: Predictive Maintenance
- Track rolling MTBF per equipment from historical downtime
- Alert when actual interval since last failure approaches MTBF × 0.8
- Vibration/temperature threshold alerts (requires IoT sensor hook)
- Maintenance risk score per equipment (probability of failure in next 30 days)

#### P4-C: Capable-to-Promise (CTP)
- Extends ATP with routing capacity check
- Before confirming SO: check material available (ATP) AND workcenter capacity on required dates
- If insufficient: suggest earliest date when both material AND capacity are available
- Show breakdown: "material ready in 5 days, capacity available in 8 days → CTP date: [date]"

#### P4-D: EDI Integration
- EDI 850 inbound: customer PO → auto-create Sales Order
- EDI 855 outbound: SO acknowledgment to customer
- EDI 856 outbound: Advance Ship Notice on shipment
- EDI 810 outbound: invoice to customer
- Map via configurable field mappings per trading partner

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

### Where We Trail Mid-Market (Epicor / SYSPRO / Infor target)

| Gap | Effort to Close |
|---|---|
| No visual Gantt / production board | Medium (P2-A) |
| No charts/graphs on dashboards | Low (P1-A) |
| No CSV/Excel export | Low (P1-B) |
| No OEE tracking | Low (P1-C) |
| No RFQ module | Low (P1-F) |
| No price lists | Low (P1-E) |
| No ATP | Medium (P2-B) |
| No cycle count workflow | Low (P1-D) |
| No supplier scorecards | Medium (P2-C) |
| No WMS (pick/pack/ship) | High (P3-B) |

### Where We Trail Enterprise (SAP / Oracle / Dynamics)

| Gap | Effort to Close |
|---|---|
| No finite APS / constraint scheduling | High (P3-A) |
| No multi-entity / intercompany | High (P3-F) |
| No AI / predictive analytics | Very High (P4-A, P4-B) |
| No EDI | High (P4-D) |
| No IoT / shop floor integration | Very High |
| No customer or supplier portals | High (P3-C) |
| No CTP | High (P4-C) |

---

## Section 4: Feature Gap Score Card

| Domain | Score vs. Mid-Market | Score vs. Enterprise |
|---|---|---|
| Work Orders & BOM | 9/10 | 8/10 |
| MRP | 8/10 | 7/10 |
| Inventory | 6/10 | 5/10 |
| Quality (QA) | 8/10 | 7/10 |
| Purchasing | 7/10 | 6/10 |
| Sales / CRM | 7/10 | 6/10 |
| Finance / GL | 8/10 | 7/10 |
| Fixed Assets | 9/10 | 8/10 |
| Multi-Currency | 8/10 | 7/10 |
| HR / Payroll | 7/10 | 6/10 |
| Maintenance (CMMS) | 8/10 | 6/10 |
| IT Management | 10/10 | 9/10 |
| Reporting / Analytics | 5/10 | 4/10 |
| Scheduling / APS | 2/10 | 1/10 |
| WMS / Shipping | 2/10 | 1/10 |
| **Overall** | **7.1/10** | **5.9/10** |

---

## Section 5: Next 10 Features to Build (Ordered by ROI)

1. **Charts & graphs on dashboards** (P1-A) — highest visibility, low effort
2. **CSV/Excel export** (P1-B) — users ask for this constantly
3. **OEE tracking** (P1-C) — data exists, just needs formula + display
4. **RFQ module** (P1-F) — closes a full purchasing workflow gap
5. **Price list module** (P1-E) — enables ATP and proper quoting
6. **Cycle count workflow** (P1-D) — completes inventory accuracy loop
7. **Gantt chart scheduler** (P2-A) — biggest visible gap vs. mid-market
8. **Available-to-Promise (ATP)** (P2-B) — improves SO delivery accuracy
9. **Supplier performance scorecard** (P2-C) — data-driven procurement
10. **MRP → auto-release POs/WOs** (P2-H) — makes MRP actionable

---

*This document is maintained in the repository at `manufacturing/COMPETITIVE_GAP_ANALYSIS.md`.*
*Update this file as features are added to track progress against the roadmap.*
