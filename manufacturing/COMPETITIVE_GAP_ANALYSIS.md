# Manufacturing ERP — Competitive Gap Analysis
**Generated:** 2026-07-05 · **Refreshed:** 2026-07-08 · **2026-07-09 update below**
**Compared Against:** SAP S/4HANA, Oracle Cloud Manufacturing, Microsoft Dynamics 365 SCM, Epicor Kinetic, Infor CloudSuite Industrial, Plex Manufacturing Cloud, SYSPRO, Fishbowl, JobBOSS², MRPeasy

**Roadmap status (2026-07-10): closed for now.** Every Section 1 domain table has zero remaining
❌ rows, and the broader embedded-AI analytics platform (P12-A) closed the last buildable-in-
software item in Section 3. The four rows left in Section 3's "Where We Trail Enterprise" table
(real IoT/sensor/RFID hardware, real carrier-API tracking, real AS2/EDI transport, a live
e-commerce storefront) are not a backlog of unwritten code — each already ships real logic behind
an honestly-scoped stub/simulation, and closing them for real requires an actual external account
or piece of hardware (a carrier API credential, a live trading partner, a real storefront, physical
sensors/readers) that this dev environment doesn't have, not more engineering effort. This document
is retained as a reference for what's shipped and what those four gaps would take to close if that
infrastructure becomes available.

**2026-07-09:** Shipped the next 3 highest-ROI items from the "buildable now" list: **What-If
Scenario Planning** (8/10 of the top-10 have it — the highest-adoption item remaining),
**Control Plans & FMEA** (7/10), and **Activity-Based Costing** (6/10, but the last remaining
gap in the entire Finance & GL domain). All three extend existing infrastructure rather than
adding a new subsystem: scenario planning layers hypothetical demand/capacity on top of
`mrp_web_core.run_mrp_dated` (gained an additive `extra_demand` parameter, same opt-in pattern
as P4-A's `include_forecast`) and `capacity_planning_core.get_capacity_check`, entirely in memory
— nothing is ever written against real MRP/capacity data; control plans/FMEA is a sibling module
to `sampling_plan_core.py`/`quality_core.py`'s SPC work; ABC costing (`abc_costing_core.py`) is a
parallel, opt-in analysis layer that allocates the same overhead dollars `costing_core`'s flat
rate already computes, but via activity cost pools and real consumption drivers, then flags
products where the two methods disagree by 15%+. Found and fixed one real bug while verifying
end-to-end: merging a scenario's TEXT `need_date` into MRP's demand list raised `TypeError: '<'
not supported between str and date`, because confirmed-SO demand dates come back from Postgres
as `datetime.date` — the exact same class of bug `demand_forecast_core.get_forecast_demand_dated`
already normalizes against for the same reason; fixed by normalizing the same way. Details in
each domain table below and in the three modules' own docstrings (`scenario_planning_core.py`,
`fmea_core.py`, `abc_costing_core.py`), and in Priority 5 of Section 2. 38 features shipped total.

**2026-07-09, later same day:** Shipped the next 3 highest-ROI items from the "buildable now"
list this document's own Sections 1.1–1.10 still marked ❌ (narrower, vertical-specific gaps that
don't require a live external system or hardware, as opposed to Section 3's "Where We Trail
Enterprise" items, which do): **Discount & Promotion Management** (10/10 of the top-10 have it —
the single most universally-adopted item still missing), **Certificate of Analysis (CoA)
Generation** (7/10), and **Skills Matrix & Competency Gap Analysis** (6/10). All three were picked
because they extend infrastructure that already existed rather than requiring a new subsystem —
discounts build on `price_list_core.py`, CoA reuses the SPC measurements `quality_core.py`
already records per lot, and the skills matrix reuses `personnel_core.py`'s existing
training/certification data and the `position` table's free-text job title. Built on a parallel
branch and merged in after a rebase onto the What-If/FMEA/ABC work above. Details in each domain
table below and in the three modules' own docstrings (`discount_core.py`, `coa_core.py`,
`skills_matrix_core.py`). 41 features shipped total.

**2026-07-10:** Shipped the next 3 highest-ROI items still marked ❌ across Sections 1.1–1.10:
**Benefits Management** (7/10), **Regulatory Compliance Templates** (7/10, closes Quality
Management's last remaining domain gap), and **Workforce Analytics & Headcount Planning** (7/10).
Benefits (`benefits_core.py`) is a plan catalog + tiered enrollment tracker, deliberately kept
separate from `payroll_core`'s existing flat/percent deduction tables rather than merged into
them — the two answer different questions ("what plans exist and who's enrolled" vs. "how much
comes out of this paycheck"). Compliance templates (`regulatory_compliance_core.py`) snapshot a
reusable ISO/FDA requirement checklist into a per-audit instance at creation time, the same
snapshot-at-instantiation choice already used for CoA generation against SPC measurements; the
two seeded starter templates are explicitly disclosed as illustrative, not certified or
exhaustive. Workforce analytics (`workforce_analytics_core.py`) required adding hire_date/
termination_date/employment_status columns to `people` — there was no employment-date tracking
anywhere in this app before — and every tenure/trend/turnover number is computed only from
employees who actually have a hire date on file, with existing employees silently (but
documented) excluded rather than backfilled with a fabricated date. 44 features shipped total.

**2026-07-10, later same day:** Shipped Applicant Tracking / Recruiting (ATS, 5/10), the last
remaining gap in the entire HR/Payroll & Personnel domain table. `ats_core.py` adds job
requisitions, candidates, and applications moving through a fixed pipeline (Applied → Screening →
Interview → Offer → Hired/Rejected) with a full stage-history audit trail. The one place this
module writes outside itself: hiring a candidate (`convert_to_employee`) creates a real `people`
row via `personnel_core.create_person` and sets its hire_date via
`workforce_analytics_core.set_employment_dates` — the same hire_date column P7-C added — so a
candidate hired through the ATS is counted correctly by Workforce Analytics from day one, closing
the loop between recruiting and the rest of the HR suite. 45 features shipped total. HR/Payroll &
Personnel and Quality Management are now the only two Section 1 domain tables with zero remaining
❌ rows; Production Planning (CTO, recipe/formula management, repetitive manufacturing),
Purchasing (supplier self-service portal), Maintenance (technician routing, APM), and Reporting
(batch record generation) still have real, buildable-without-hardware gaps not yet scheduled.

**2026-07-10, one more:** Shipped the Supplier Self-Service Portal (6/10), closing Purchasing &
Procurement's last remaining domain gap. `supplier_portal_core.py` mirrors `customer_portal_core.py`
(P3-C) exactly: a separate bcrypt-login layer on the existing `supplier` master file
(`supplier_login`, matched against that supplier's own email at registration), session-scoped
under `portal_supplier_id` — deliberately separate from both the employee `user_*` keys and the
customer portal's `portal_customer_id`. Every capability reuses an existing core module rather
than forking it: PO viewing reuses `purchase_orders_core.list_pos/get_po/get_po_items` (PO
acknowledgement is the one genuinely new piece — two additive columns on `purchase_order`, since
nothing tracked "did the supplier confirm this order" before); AP invoice submission reuses
`accounting_core.create_ap_invoice`; RFQ quoting reuses `rfq_core.enter_quote` — a supplier
submitting a quote through the portal calls the *exact same function* an internal buyer would use
keying in a phoned-in quote, scoped by an ownership check against `rfq_vendor` (which suppliers
were actually invited to quote). 46 features shipped total. Purchasing & Procurement joins
HR/Payroll & Personnel and Quality Management as domain tables with zero remaining ❌ rows.

**2026-07-10, one more still:** Shipped the last three items in Production Planning &
Scheduling's domain table together: Configure-to-Order (7/10), Recipe/Formula Management (7/10),
and Repetitive Manufacturing (7/10) — closing that domain out entirely. All three release a real
Work Order through the existing `work_orders_core.create_wo`, never forking WO creation: CTO
(`cto_core.py`) resolves a per-SO-line configuration (option groups mapped to BOM-component
substitutions) into a configured material list and fills a genuine prior gap — there was no
SO-to-WO conversion path anywhere in this app before, production was always planned from
aggregate MRP demand. Recipe management (`recipe_core.py`) is a deliberately parallel structure
to the fixed-qty `bom` table, not a fork of it, since scaling a batch formula to an arbitrary
target output while accounting for process yield loss is a genuinely different computation than
BOM's per-unit `explode_quantity`. Repetitive manufacturing (`repetitive_core.py`) models
flow-line production directly — a rate-per-day schedule with daily output logging — rather than
faking it with one Work Order per day; logging output backflushes BOM components through the same
audited `inventory_core.record_transaction` path every other stock movement in this app already
uses (an 'issue' per component, a 'receive' for the finished good), not a bypass or a new
net-zero exception. 49 features shipped total. Production Planning & Scheduling joins
HR/Payroll & Personnel, Quality Management, and Purchasing & Procurement as domain tables with
zero remaining ❌ rows — four of ten.

**2026-07-10, still one more:** Shipped the last three items across Maintenance and Reporting &
Analytics together: Technician Routing & Scheduling (6/10), Asset Performance Management (6/10),
and Batch Record Generation (6/10). None of these reimplement math that already existed —
`technician_routing_core.py` schedules real maintenance work orders (`maint_work_order`) into an
ordered daily stop list per mechanic, and completing a stop calls the existing
`maintenance_core.complete_work_order` rather than forking WO completion. `apm_core.py` is the
missing layer *on top of* the reliability math this app already had (`maintenance_core.get_mtbf`'s
MTBF/MTTR/availability, computed from real `maint_downtime` records): an admin-set per-asset
criticality rating combined with that existing availability data and the asset's real downtime
cost (`maint_downtime.cost`, tracked but never rolled up per asset before) into a health score and
a repair-vs-replace recommendation. `batch_record_core.py` snapshots a completed Work Order's
materials, cost (`work_orders_core.get_wo_cost_summary`), and quality inspections
(`qa_inspection.wo_id`) into a numbered, point-in-time record with a PDF export — the same
snapshot-not-live-query choice `coa_core` already made for Certificates of Analysis, for the same
reason: a record that silently changed if someone later edited a WO's materials would defeat the
point of having a record. 52 features shipped total. **Every domain table in Section 1 now has
zero remaining ❌ rows — the only gaps left anywhere in this document are Section 3's "Where We
Trail Enterprise" table, which needs real external hardware/systems this dev environment has no
live counterpart for.**

**2026-07-10, final:** Shipped the last buildable-in-pure-software item from Section 3's "Where We
Trail Enterprise" table: the **broader embedded-AI analytics platform**. `ai_insights_core.py` is a
pure computed layer (no new tables, same "nothing persisted against real data" choice as
`cash_flow_core.py`/`scenario_planning_core.py`) that ties together two previously siloed risk
reports — `predictive_maintenance_core.get_predictive_maintenance_report` and
`apm_core.get_apm_dashboard` — with three genuinely new hand-rolled statistical detectors: a
demand-anomaly z-score over each product's actual-vs-forecast history
(`demand_forecast_core.list_demand_forecast`), a quality-anomaly z-score over the monthly NCR
total (`quality_core.get_ncr_severity_trend`), and a customer churn-risk score comparing each
customer's days-since-last-order against their own historical average order interval
(`contacts_core.get_customer_orders`). All three follow this app's existing no-ML-library
convention (hand-rolled mean/stdev, no pandas/numpy/statsmodels) and its honest-scoping precedent:
customers/products without enough history are silently excluded rather than defaulted to "safe" or
fabricated. Everything merges into one severity-ranked feed at `/ai-insights/`, linked from the
Reports dashboard. 53 features shipped total. **This closes the only remaining pure-software gap
in this document — the four items still open in Section 3's "Where We Trail Enterprise" table all
require a real external account/hardware (carrier API, EDI trading partner, live storefront,
IoT/RFID readers) this dev environment has no live counterpart for.**

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
Forecasting), P4-B (Predictive Maintenance), P4-C (Capable-to-Promise), P4-D (EDI Integration),
P4-E (e-Commerce Integration), P4-F (Custom Report Builder), and P4-G (Sustainability / Carbon
Cost Tracking), merged from thirteen separate PRs (#398, #382, #386, #381, #387, #388, #389,
#390, #391, #392, #393, #394, #395) that a prior session had built and left open. **This closes
out every numbered item (P1–P4) in this roadmap.** 29 features shipped total.

**2026-07-08, still later:** Shipped P3-H (True Inter-Warehouse Transfers), the first of the two
gaps discovered while working the list above that had no prior PR — built fresh this session
rather than merged from an existing branch. 30 features shipped total.

**2026-07-08, final:** Shipped P3-I (FIFO / LIFO / Weighted-Average Costing), the second and
last gap with no prior PR — also built fresh (`costing_layers_core.py`, opt-in per-product cost
layers with FIFO/LIFO/weighted-average consumption, its own COGS ledger, deliberately parallel
to and non-invasive of the existing standard-cost roll). 31 features shipped total. **Every item
in this roadmap — all of P1 through P4, plus both gaps found along the way — is now shipped.**

**2026-07-08, re-verified:** Re-checked this document against the actual codebase at commit
`97f763f` (post-P3-I merge): confirmed no open PRs and no stray unmerged branches exist beyond
what's already tracked here; confirmed all 24 `*_core.py` modules this document credits as
"Shipped" are present on disk; grepped the codebase for every item this document still marks
❌ (consignment, cross-docking, wave picking, RFID, what-if scenario planning,
Configure-to-Order, recipe/formula management, repetitive manufacturing, Activity-Based Costing,
supplier self-service portal, real carrier-API tracking, benefits management, skills matrix,
workforce analytics, ATS, technician routing, APM, batch record generation, control plans/FMEA,
CoA generation, regulatory compliance templates, discount/promotion management) and confirmed
none of them have any implementation anywhere — every ❌ in Sections 1.1–1.10 is still accurate.
No corrections were needed; this pass is a clean bill of health, not a new round of shipped work.

**2026-07-08, one more:** Shipped P3-J (Consignment Inventory), the highest-ROI item remaining
from the "Where We Trail Mid-Market" list once the P1–P4 roadmap and both P3-H/P3-I gaps closed.
`consignment_core.py` — vendor-owned stock received into the warehouse without touching
`product.amount` until a separate "usage" action transfers ownership (credits inventory) and
opens an AP invoice for the vendor in one step. 32 features shipped total. **Follow-up same day:**
a code review of P3-J found and fixed three real bugs (agreements could be created with no
supplier, letting usage silently bill a null vendor; a count-based invoice-numbering scheme that
would collide under concurrent usage against the same agreement; a silently-swallowed cancel
error) — shipped as its own small PR, no roadmap-status change.

**2026-07-08, next:** Shipped P3-K (Wave Picking), the next item from the "Where We Trail
Mid-Market" list. Extends P3-B's pick-list model with a consolidation layer: a wave batches
several confirmed SOs' pick lists together so a picker walks each (product, bin) combination once
per wave instead of once per order, then that single consolidated pick is allocated back down
across every affected order's own pick-list lines by calling the existing, unmodified
`record_pick()` per line. 33 features shipped total.

**2026-07-08, last one:** Shipped P3-L (Cross-Docking), leaving only RFID (a hardware-dependent
gap this dev environment has no reader to integrate against) on the "Where We Trail Mid-Market"
list. Routes an inbound PO receipt straight to one specific waiting pick-list line — a genuine
stock-out pointing at the unassigned sentinel bin — instead of putting it away first, composing
`receive_and_putaway`'s receiving half with `record_pick`'s existing outbound half so the goods
never land in `wms_bin_stock` at all. 34 features shipped total.

**2026-07-08, truly last one:** Shipped P3-M (RFID Tracking), the final item on the "Where We
Trail Mid-Market" list — honestly simulated rather than faked, since this dev environment has no
real RFID reader to integrate against: a "reader" is a virtual antenna tied to one WMS zone, and
a "read" is a manual "Simulate Read" action standing in for what real antenna hardware would
capture automatically, the same honest-scoping choice already used for predictive maintenance's
manual sensor entry and e-commerce's config-gated HTTP stub. Reading a tag at a reader whose zone
differs from the tag's current zone relocates its qty to a bin in the new zone via
`_adjust_bin_stock` on both ends — a third documented net-zero-to-`product.amount` exception
alongside inter-warehouse transfers and cross-docking. 35 features shipped total. **Every item in
this roadmap, including every gap discovered along the way with no prior PR, is now shipped.**

---

## Executive Summary

This ERP is now a **strong mid-market system with several upper-mid-market capabilities** — finite
capacity scheduling, a full WMS, ATP, and OEE all shipped since the last pass. It comfortably matches
or beats Infor CloudSuite, SYSPRO, and Epicor on day-to-day production, quality, purchasing, sales,
HR, payroll, accounting, and IT management, and has closed most of the "visible gap" items (charts,
export, Gantt, RFQ, price lists) that used to stand out immediately in a demo.

Every roadmap item that could be built without a live external system to connect to has now
shipped, including the last remaining supply-chain costing gap (FIFO/LIFO/weighted-average, P3-I)
and RFID tracking (P3-M). What remains is narrowly **real external connectivity and hardware**:
EDI (P4-D), e-commerce sync (P4-E), predictive maintenance (P4-B), and RFID (P3-M) all ship with
real logic but honestly-scoped stubs/simulations where this environment has no live external
system or hardware to connect to (file upload/download instead of AS2/VAN/SFTP, config-gated HTTP
POST instead of a live Shopify/WooCommerce store, manual sensor entry instead of IoT hardware, a
manual "Simulate Read" action instead of a real RFID antenna); there is also no real carrier-API
shipment tracking. (Note: this paragraph predates several later passes — see the dated log above
for what has shipped since, including the supplier self-service portal and the broader embedded-AI
analytics platform / AI Insights Hub.)

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
| **What-if scenario planning** | ✅ Full (2026-07-09) — compares hypothetical demand/capacity adjustments against real MRP and workcenter data entirely in memory, nothing persisted against real data | ✅ 8/10 |
| **Configure-to-Order (CTO)** | ✅ Full (2026-07-10) — per-product option groups mapped to BOM-component substitutions; a resolved configuration releases a real Work Order with per-order materials, filling a gap where no SO-to-WO path existed at all before | ✅ 7/10 |
| **Recipe / formula management (process mfg)** | ✅ Full (2026-07-10) — batch-based recipes with a draft→active→superseded lifecycle, scaling to any target output that correctly accounts for process yield loss | ✅ 7/10 |
| **Repetitive manufacturing** | ✅ Full (2026-07-10) — rate-per-day production schedules with daily output logging that automatically backflushes BOM components through the same audited inventory_core.record_transaction path every other stock movement uses | ✅ 7/10 |

**Priority gaps:** none remaining in this domain.

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
| **FIFO / LIFO / Weighted Average Cost valuation** | ✅ Full (P3-I) — opt-in per product; standard costing unchanged as the default | ✅ All |
| **True multi-warehouse with transfers** | ✅ Full (P3-B, P3-H) — multiple warehouses/zones/bins (P3-B) plus a draft→in_transit→completed transfer workflow that actually relocates stock between them (P3-H) | ✅ All |
| **Warehouse Management System (WMS)** | ✅ Full (P3-B) | ✅ 9/10 |
| **Pick / Pack / Ship automation** | ✅ Full (P3-B) | ✅ 9/10 |
| **Cycle count structured workflow** | ✅ Full (P1-D) | ✅ All |
| **Consignment inventory** | ✅ Full (P3-J) — vendor-owned stock, usage-triggered ownership transfer + AP billing | ✅ 7/10 |
| **Cross-docking** | ✅ Full (P3-L) — routes an inbound PO receipt straight to a waiting pick-list line for a genuine stock-out, skipping storage entirely | ✅ 6/10 |
| **Wave picking management** | ✅ Full (P3-K) — batches confirmed SOs into a wave; a consolidated (product, bin) pick sheet is allocated back down across every affected order's pick-list lines | ✅ 6/10 |
| **RFID integration** | ✅ Full (P3-M, simulated — no real reader in this environment) | ✅ 8/10 |
| Barcode scanning (entity lookup + label printing) | ✅ Full | ✅ All |

**Priority gaps:** none remaining in this domain.

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
| **Control plans & FMEA** | ✅ Full (2026-07-09) — per-product control plans with Severity x Occurrence x Detection RPN scoring per characteristic, plus a cross-plan risk register | ✅ 7/10 |
| **Certificate of Analysis (CoA) generation** | ✅ Full (2026-07-09) — generated per lot from that lot's existing SPC measurements (`spc_measurement`/`spc_control_limit`), snapshotted at generation time into `coa_document`/`coa_result` so a later measurement edit can't retroactively alter an issued certificate; reportlab PDF matching the customer-portal invoice/packing-slip pattern | ✅ 7/10 |
| **Document control & version management** | ✅ Full (P2-F) — draft→review→approved→superseded→obsolete, revision history, file upload/download | ✅ 8/10 |
| **Regulatory compliance templates (FDA, ISO)** | ✅ Full (2026-07-10) — reusable ISO/FDA requirement checklist templates, instantiated per-audit with per-item status/evidence tracking and a progress rollup; seeded starter ISO 9001/FDA 21 CFR 820 templates are illustrative, not certified or exhaustive | ✅ 7/10 |

**Priority gaps:** none remaining in this domain.

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
| **Supplier collaboration / self-service portal** | ✅ Full (2026-07-10) — separate bcrypt-login portal (mirrors the customer portal) for viewing/acknowledging POs, submitting AP invoices, and quoting on invited RFQs, all reusing existing core modules rather than forking them | ✅ 6/10 |
| **Blanket orders & call-offs** | ✅ Full (P3-E) — value- or qty-tracked balance, auto-close/auto-expire | ✅ 9/10 |
| **Freight & landed cost allocation** | ✅ Full (P3-D) — by value/weight/qty, rolls into `product.purchase_price` | ✅ 7/10 |
| **EDI (850/856/810)** | ✅ Full (P4-D) — real X12 parsing/generation with per-partner item-number field mappings; 850 inbound auto-creates SOs, 855/856/810 generated on demand; trading-partner connectivity is a file upload/download stub, not a real AS2/VAN/SFTP transport | ✅ 8/10 |
| **Auto-generated POs from MRP** | ✅ Full (P2-H) — preferred-supplier lookup wired into MRP release | ✅ All |

**Priority gaps:** none remaining in this domain.

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
| **Discount & promotion management** | ✅ Full (2026-07-09) — percent/fixed-amount rules scoped to a product and/or customer with a min-qty threshold and effective window; resolution picks whichever applicable rule yields the lowest final price rather than ranking discount types directly; auto-applies client-side on the SO line-entry form, the same JSON-embed pattern `price_list_core`'s tiered pricing already uses | ✅ All |
| **Customer self-service portal** | ✅ Full (P3-C) — own orders/invoices/shipments/RMAs, invoice + packing-slip PDF, online payment; carrier tracking and Stripe payment are documented stubs (no real integration existed anywhere to build on) | ✅ 7/10 |
| **Shipping & carrier API integration (FedEx/UPS/USPS)** | ❌ — WMS (P3-B) records carrier + tracking number manually at ship confirm; the portal's tracking view (P3-C) is a deterministic stub, not a real carrier API | ✅ 9/10 |
| **Multi-channel order integration (e-commerce)** | ✅ Full (P4-E) — real, verified Shopify/WooCommerce webhook order intake with dedupe and SKU field mapping; outbound inventory/price/shipment sync is real config-gated HTTP POST code with no live storefront in this environment to call | ✅ 7/10 |

**Priority gaps:** carrier API integration.

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
| **Activity-Based Costing (ABC)** | ✅ Full (2026-07-09) — activity cost pools + real consumption drivers allocate the same overhead dollars the flat rate does, then flag products where the two methods disagree by 15%+; a parallel opt-in analysis layer, not a replacement for the existing standard-cost roll | ✅ 6/10 |
| **Multi-entity / legal entity separation** | ✅ Full (P3-F) — company master + user-to-company assignment, additive `company_id` on GL | ✅ 8/10 |
| **Intercompany transactions** | ✅ Full (P3-F) — two independently-balanced journals per IC transaction, tagged per entity | ✅ 7/10 |
| **Consolidated financial reporting** | ✅ Full (P3-F) — reuses the existing unscoped income statement/balance sheet, subtracts the known IC amount as elimination | ✅ 7/10 |
| **Sustainability / carbon cost tracking** | ✅ Full (P4-G) — BOM carbon rollup mirroring standard costing, per-WO carbon-intensity actuals, ESG dashboard (scope 1/3 from real production data; scope 2 is manual kWh × illustrative grid-factor entry, not full GHG Protocol compliance tooling) | ✅ 5/10 |

**Priority gaps:** none remaining in this domain.

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
| **Benefits management** | ✅ Full (2026-07-10) — a benefit plan catalog (Health/Dental/Vision/Life/Disability/401k) with employee/employer cost per pay period, and per-employee enrollments by tier; deliberately parallel to, not merged with, `payroll_core`'s existing flat/percent deduction tables | ✅ 7/10 |
| **Skills matrix & competency gap analysis** | ✅ Full (2026-07-09) — a skill master, required-proficiency-level requirements keyed by `position.job_title` (free text, matched case-insensitively — no job-title master table exists to key on instead), and per-employee assessed levels; a per-employee gap report and an org-wide gap-ranked summary | ✅ 6/10 |
| **Workforce analytics & headcount planning** | ✅ Full (2026-07-10) — headcount summary/trend, avg tenure, and trailing-12-month turnover computed from new hire_date/termination_date columns on `people`; per-dept target-vs-actual headcount planning. Only employees with a hire date actually entered count toward tenure/trend — existing employees default to none and are excluded, not backfilled with a fabricated date | ✅ 7/10 |
| **Applicant Tracking / Recruiting (ATS)** | ✅ Full (2026-07-10) — job requisitions, candidates, and applications through a fixed pipeline (Applied → Screening → Interview → Offer → Hired/Rejected) with full stage history; hiring a candidate creates a real Personnel record with hire date set, wired directly into Workforce Analytics | ✅ 5/10 |

**Priority gaps:** none remaining in this domain.

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
| **Technician routing & scheduling** | ✅ Full (2026-07-10) — ordered daily stop lists per mechanic against real maintenance work orders; completing a stop closes the underlying WO through the existing lifecycle, never a fork of it | ✅ 6/10 |
| **Asset Performance Management (APM)** | ✅ Full (2026-07-10) — admin-set per-asset criticality combined with the existing MTBF/availability math and real downtime cost into a health score and repair-vs-replace recommendation | ✅ 6/10 |
| **IoT / sensor integration** | ✅ Partial (P4-B) — manual/simulated sensor-reading entry against per-equipment warning/critical thresholds; no real device connectivity | ✅ 6/10 |

**Priority gaps:** real IoT/sensor hardware connectivity (Section 3's "Where We Trail Enterprise" table).

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
| **Custom / self-service report builder** | ✅ Full (P4-F) — allowlist-based field/filter/group-by/aggregate builder over 11 tables (single-table, no cross-table joins in v1), CSV/PDF export, scheduled email delivery | ✅ 7/10 |
| **OEE reporting** | ✅ Full (P1-C, P3-A) — dashboard card/trend + dedicated `/maint/oee/` report | ✅ 7/10 |
| **Live shop floor performance (real-time)** | ✅ Full (P3-G) — live per-shift OEE dashboard + standalone auto-refreshing TV display | ✅ 7/10 |
| **Predictive / AI analytics** | ✅ Full (2026-07-10) — seasonal-decomposition demand forecast and MTBF-based failure-risk scoring (P4-A/P4-B) now feed a cross-domain **AI Insights Hub** (`ai_insights_core.py`) that also adds hand-rolled demand-anomaly, quality-anomaly, and customer churn-risk detection into one severity-ranked feed | ✅ 7/10 |
| **Batch record generation** | ✅ Full (2026-07-10) — numbered as-built records for completed Work Orders, snapshotting materials/cost/quality inspections at generation time (same snapshot-not-live pattern as CoA generation), with a PDF export | ✅ 6/10 |
| **Scheduled report delivery (email)** | ✅ Partial (already existed, not credited in original pass) — `send_daily_digest` management command emails/prints a fixed KPI digest via cron/Task Scheduler; not user-configurable like a report builder | ✅ 7/10 |

**Priority gaps:** none remaining in this domain.

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

#### P3-H: True Inter-Warehouse Transfers ✅ Done
Extends P3-B (WMS): multiple warehouses/zones/bins already existed, but nothing moved stock
*between* warehouses — this closes that gap.
- Draft a transfer between two distinct warehouses, add line items (product + source bin + qty)
- Ship: decrements each line's source bin
- Receive: credits a chosen destination bin per line; transfer completes once every line lands
- Cancel a transfer before it ships
- **Shipped:** New functions directly in `wms_core.py` (`wms_transfer`/`wms_transfer_line` tables)
  rather than a separate module — a transfer reuses the same `_adjust_bin_stock` primitive that
  every other bin-quantity change in this file goes through, so it belongs alongside it, not
  behind an import boundary. **The one deliberate break from this file's own central invariant**
  (every `_adjust_bin_stock` call is normally paired with `inventory_core.record_transaction`):
  a transfer relocates stock, it doesn't change the company-wide total, so `ship_transfer`/
  `receive_transfer_line` call `_adjust_bin_stock` on each end and *never* `record_transaction` —
  there's nothing to post to `inventory_transaction`/`product.amount` for a move that nets to
  zero. Verified this exact property end-to-end (see below). Status flow is
  `draft → in_transit → completed` at the transfer level and `pending → in_transit → received`
  per line; the destination bin is chosen at receive time, not when the line is added, since the
  receiving warehouse may reorganize bins in however long the goods take to actually arrive.
  Shipping decrements every line's source bin via the existing `_adjust_bin_stock` negative-qty
  guard as the sole authoritative availability check — no separate qty validation is duplicated
  in `add_transfer_line`. Cancellation is only legal while `draft`; reversing an already-shipped
  transfer is explicitly out of scope (that's a transfer back to the source, created separately
  once the original lands). **Found and fixed a real, pre-existing gap while building this**:
  there was no web UI anywhere to create a second warehouse or assign a zone to one — every zone
  creation call was hardcoded to `get_or_create_default_warehouse`, so the "multiple warehouses"
  P3-B credited itself with had no path to actually exist in practice. Added a `/wms/warehouses/`
  list+create page and a warehouse picker on the zone-creation form (`wms_bin_new.html`) as a
  prerequisite for this feature to be testable at all. New pages at `/wms/transfers/` (list +
  status filter), `/wms/transfers/new/`, and `/wms/transfers/<id>/` (line management, ship,
  per-line receive, cancel), wired into a new "Warehouses" + "Warehouse Transfers" pair of leaves
  on the existing WMS submenu. Verified end-to-end against a running dev server + local Postgres
  through the actual web views (not just unit tests): created two real warehouses and a bin in
  each, seeded 20 tracked units of a real product into the source bin, created a transfer and
  added an 8-unit line, shipped it and confirmed the source bin dropped to 12 while
  `product.amount` was **exactly unchanged** (the invariant this feature deliberately breaks from
  the module's default), received the line into the destination bin and confirmed it landed at 8
  with `product.amount` still unchanged and the transfer auto-completing with `received_by`
  stamped, confirmed a second transfer cancels correctly while still a draft, and confirmed
  attempting to ship more than a bin actually holds surfaces a real "only N tracked there" error
  banner through the web view rather than silently succeeding.

#### P3-I: FIFO / LIFO / Weighted-Average Costing ✅ Done
The second gap discovered with no prior PR — every top-10 competitor offers this; `product` had
no cost-layer concept at all before this feature.
- Per-product opt-in costing method (defaults to `standard`, today's single-purchase-price
  behavior, unchanged)
- Discrete cost layers created per costed receipt; issues consumed per the chosen method
- FIFO: oldest layer first. LIFO: newest layer first. Average: pooled weighted-average cost
- COGS ledger and a valuation report showing layer-tracked qty alongside `product.amount`
- **Shipped:** `manufacturing/costing_layers_core.py` — a parallel, opt-in valuation subsystem,
  not a replacement for standard costing. `receive_with_costing`/`issue_with_costing` wrap the
  existing, unmodified `inventory_core.record_transaction` (so `product.amount` stays the single
  source of truth for on-hand qty) and additionally create/consume `inventory_cost_layer` rows.
  **Deliberately never modifies `record_transaction` itself** — this is its own explicit front
  door, mirroring `wms_core.receive_and_putaway`'s precedent of wrapping pinned functions rather
  than editing them. If a costed product's inventory moves through any of the *other* existing
  paths (WMS, cycle count, manual adjustment, mobile API), `product.amount` still updates
  correctly but no cost layer is created/consumed for that movement — the valuation report
  surfaces both figures side by side so any drift is visible, not hidden, rather than silently
  papered over. An issue that exceeds tracked layers falls back to costing the shortfall at the
  product's current `purchase_price`, the same graceful no-big-bang-migration pattern
  `wms_core`'s unassigned-bin sentinel uses. New pages at `/inventory/valuation/` (all costed
  products) and `/inventory/<id>/valuation/` (method switch, costed receive/issue forms, cost
  layers, COGS history), cross-linked from the existing Standard Cost and Inventory Detail pages.
  Verified end-to-end against a running dev server + local Postgres: set a real product to FIFO,
  recorded two costed receipts at different unit costs ($4 and $6/unit), issued 12 units and
  confirmed FIFO consumption order (COGS $52.00 = 10 units @ $4 + 2 units @ $6, exactly matching
  a hand calculation), confirmed the remaining layer/valuation figures ($48.00 for 8 units @ $6),
  and confirmed both cross-links render correctly; cleaned up all test data afterward.

#### P3-J: Consignment Inventory ✅ Done
The highest-ROI item remaining in the "Where We Trail Mid-Market" list once the numbered roadmap
and both P3-H/P3-I gaps closed — vendor-owned stock held in our warehouse, not paid for until used.
- Consignment agreement: vendor, product, per-unit cost, validity window
- Receive vendor-owned stock (doesn't touch our own inventory count)
- Record usage: transfers ownership, credits our inventory, bills the vendor
- On-hand (vendor-owned) balance visible alongside used-to-date
- **Shipped:** `manufacturing/consignment_core.py` — single-product, open-ended replenishment
  agreements (not a fixed-ceiling model like `blanket_po_core.py`, since a VMI relationship has no
  natural "total" to track against), with two running ledgers: `consignment_receipt` (vendor ships
  stock in — deliberately does **not** touch `product.amount`/`record_transaction`, since the
  goods aren't company-owned yet, the same "don't blend two ownership concepts into one column"
  discipline as `wms_core.py`'s bin-stock-vs-aggregate split, one ownership level earlier) and
  `consignment_usage` (the single moment ownership transfers: decrements the vendor-owned balance,
  credits `product.amount` via the existing, unmodified `inventory_core.record_transaction`, and
  opens an AP invoice via the existing, unmodified `accounting_core.create_ap_invoice` — usage
  *is* the billing trigger in a consignment arrangement, unlike a normal PO where the invoice
  follows receipt). **Deliberately simplified**: in a real warehouse, consigned stock can be
  picked straight out of its bin for production without a separate "we now own this"
  administrative step — modeling that exactly would mean hooking into WO material-pick and SO-ship
  (both already-pinned call sites elsewhere); instead, recording usage is the one explicit action
  standing in for "this qty left vendor ownership and entered ours," the same honest scoping
  choice `landed_cost_core.py` documents for why its own allocation is a separate action rather
  than auto-triggered by receiving. **Found and fixed a real, pre-existing gap while verifying
  live**: `create_ap_invoice`'s own signature treats `due_date` as optional (`due_date or None`),
  but the live `ap_invoice` table has a NOT NULL constraint on that column not reflected in the
  DDL string — exactly the "live schema can diverge from the `CREATE TABLE` DDL" gotcha this
  document's own Database Gotchas section already warns about elsewhere. Every other existing
  caller of `create_ap_invoice` happens to always supply a real due date from a form field, so
  this had never surfaced before; fixed by defaulting the consignment usage invoice to a net-30
  due date rather than `None`. Web pages at `/consignment/` (list), `/consignment/new/`,
  `/consignment/<id>/` (balances, receipts, usage history), `/consignment/<id>/receive/`, and
  `/consignment/<id>/use/`, linked from a new "Consignment" toolbar button on `po_list.html`
  (matching the Blanket PO/RFQ/Landed Cost precedent of a direct link rather than a `menus.py`
  leaf). Verified end-to-end against a running dev server + local Postgres through the actual web
  views: created a real agreement, received 40 units of vendor-owned stock and confirmed
  `product.amount` stayed exactly unchanged, recorded a 15-unit usage and confirmed
  `product.amount` increased by exactly 15, a real AP invoice was opened for the vendor at the
  correct amount ($232.50) with a 30-day due date, and the on-hand/used-to-date balances updated
  correctly (25.00 remaining, 15.00 used); confirmed attempting to use more than the on-hand
  balance is rejected with a clear error; cleaned up all test data afterward.

#### P3-K: Wave Picking Management ✅ Done
Extends P3-B (WMS): pick lists were one-per-SO with a zone-aware sort, but nothing batched
multiple orders into a single consolidated pick run.
- Batch several confirmed SOs into one wave
- Consolidated pick sheet: one row per (product, bin) across the whole wave, not per order
- Recording one consolidated pick allocates it back across every order that needed it
- Wave auto-completes once every member order's lines are resolved; cancel while still untouched
- **Shipped:** New functions directly in `wms_core.py` (`wms_wave` table, plus a nullable
  `wms_pick_list.wave_id` column) — a consolidation layer *on top of* the existing per-order pick
  list model, not a replacement for it. `create_wave` generates a real pick list per SO by calling
  the existing, unmodified `generate_pick_list` once per order (so the whole wave fails to create
  as one unit if any SO isn't eligible, same all-or-nothing transaction semantics as everything
  else in this module) and assigns them all to a new wave. `get_consolidated_pick_lines` groups
  every still-pending line across the wave's member pick lists by `(product_id, bin_id)` — the
  entire point of wave picking: pick everything of one product from one bin in a single trip, once,
  no matter how many orders in the wave need it. `record_wave_pick` is the actual consolidated
  pick action: it allocates the picked qty back down across the affected lines (oldest pick list
  first) by calling `record_pick` once per line — **reused completely unmodified**, so every
  per-line side effect (crediting `product.amount`, decrementing bin stock, that line's own order
  flipping to `'picked'` once fully resolved) happens exactly the way single-order picking already
  did; wave picking adds no new inventory-movement code path, only a smarter allocation front end.
  An over-pick (asking for more than the wave actually needs for that product/bin) is rejected with
  a clear error rather than silently over-crediting — mirrors `consignment_core.record_usage`'s
  on-hand-balance check. Text-only SO lines (`product_id IS NULL`) have no product identity to
  batch on, so they're explicitly excluded from consolidation and must still be picked from their
  own order's pick list individually, same as before wave picking existed — a documented scoping
  choice, not an oversight. Wave status (`open` → `picking` → `completed`, or `cancelled` while
  still untouched) is lazily re-derived on every read from its member lines' own statuses, the
  same precedent `blanket_po_core`/`consignment_core` use for their own status sync; cancelling a
  wave cascades to cancel its member pick lists too, freeing the underlying SOs to be picked again
  individually or in a new wave. New pages at `/wms/waves/` (list + a checkbox picker over
  confirmed SOs awaiting a pick list) and `/wms/waves/<id>/` (consolidated pick sheet, member-order
  progress table, cancel), cross-linked from the existing Pick Lists and Bin Master pages. Verified
  end-to-end against a running dev server + local Postgres through the actual web views: seeded 50
  tracked units of a real product into one bin, created two confirmed SOs needing 6 and 4 units of
  it respectively, batched both into a wave and confirmed the consolidated sheet showed one row
  summing to 10 (not two separate rows), confirmed an over-pick request (999) was rejected,
  recorded a single 10-unit consolidated pick and confirmed **both** orders' pick lists flipped to
  `'picked'`, the bin dropped by exactly 10, `product.amount` dropped by exactly 10, and the wave
  auto-completed; separately confirmed cancelling an untouched wave cascades to cancel its member
  pick list. Cleaned up all test data afterward.

#### P3-L: Cross-Docking ✅ Done
Extends P3-B (WMS): receiving always put stock away into a bin first, even when an order was
already waiting on it with nothing in stock — cross-docking skips that detour.
- Receiving screen surfaces waiting orders for whatever product is being received
- Route the receipt straight to a specific waiting order instead of putting it away
- Any excess beyond what that order needs still receives normally, separately
- Only targets genuine stock-outs — a line with a real bin already assigned isn't offered
- **Shipped:** New functions directly in `wms_core.py`. `receive_and_putaway`'s own receiving
  logic (PO-item lookup, qty clamping, `receive_po_item` call) was extracted into a shared
  `_apply_po_receipt` primitive — a pure refactor, no behavior change, verified against the
  existing mocked-call-argument tests, which don't assert internal structure — so
  `receive_cross_dock` could reuse it rather than duplicate it.
  `find_cross_dock_candidates` finds pending pick-list lines for a product that are still
  pointing at the unassigned sentinel bin (genuine unfulfilled demand with nothing tracked
  anywhere) — the only lines cross-docking targets; a line that already has a real bin earmarked
  is received normally instead. `receive_cross_dock` composes `_apply_po_receipt` +
  `record_transaction` (the receiving half, identical to `receive_and_putaway`) with
  `record_pick` — **completely unmodified** — for the outbound half, so the cross-docked qty
  never touches `wms_bin_stock` at all. **A second place, alongside inter-warehouse transfers,
  where `product.amount` nets to unchanged** — the receive credits +delta and `record_pick`'s own
  issue debits -delta, because this codebase already decrements `product.amount` at pick time,
  not ship-confirm time (`confirm_shipment` posts no inventory transaction of its own). This
  isn't a coincidence or a workaround: it's exactly correct, since cross-docked goods genuinely
  never spend any time as available on-hand inventory — that's the entire point of cross-docking.
  Both legs still post a real, separately auditable `inventory_transaction` row (a `receive` and
  an `issue`), so the movement stays fully traceable even though the net is zero. Qty is capped
  to what the target line actually needs — cross-docking more than one line's demand in a single
  action isn't supported; the excess receives normally via the existing put-away form instead. The
  existing `/wms/receive/` screen gained a highlighted "cross-dock opportunity" row under any PO
  item with waiting candidates, with its own qty/target-order form, rather than a separate page —
  the whole point is surfacing the opportunity at the moment of receiving. Verified end-to-end
  against a running dev server + local Postgres through the actual web views: created a product
  with zero stock, a confirmed SO needing 6 units of it (its pick-list line fell back to the
  unassigned bin, confirming a genuine stock-out), and an open PO with 20 owed; confirmed the
  cross-dock opportunity surfaced on the receiving page; confirmed requesting more than the line's
  need (50) was rejected; cross-docked 6 units and confirmed the PO's received qty updated, the
  order's pick-list line flipped to `'picked'`, no row was ever created in a real storage bin, a
  real `receive` + `issue` transaction pair was posted, and `product.amount` correctly netted to
  unchanged; then received the remaining 14 units through the normal put-away form and confirmed
  it worked exactly as before, landing in a real bin with `product.amount` increasing by 14.
  Cleaned up all test data afterward.

#### P3-M: RFID Tracking ✅ Done (simulated)
There is no real RFID reader anywhere in this dev environment, so this is built as an honestly
simulated hardware integration, not a fake one — the same scoping choice already used for
predictive maintenance's manual sensor entry and e-commerce's config-gated HTTP stub.
- A "reader" is a virtual antenna tied to one WMS zone (zone-level resolution is realistic for
  RFID — an antenna can tell you a tagged pallet entered a zone, not which exact bin within it)
- A "tag" labels a qty of one product already tracked in a bin — not a new quantity ledger
- A manual "Simulate Read" action stands in for what real antenna hardware would capture
  automatically
- Reading a tag at a reader in a *different* zone than the tag's current one relocates its qty to
  the least-full active bin in the new zone; re-reading the same zone is a no-op "still here"
  heartbeat, logged but not moved
- **Shipped:** New tables in `wms_core.py` — `wms_rfid_reader`, `wms_rfid_tag`,
  `wms_rfid_read_event` — plus `create_reader`, `list_readers`, `create_tag`, `list_tags`,
  `get_tag`, `get_tag_history`, `simulate_tag_read`, and `retire_tag`. `simulate_tag_read` reuses
  the existing `_least_full_active_bin_in_zone` put-away heuristic to pick the landing bin, and
  relocates via `_adjust_bin_stock` directly on both ends — **a third documented exception, after
  inter-warehouse transfers (P3-H) and cross-docking (P3-L), where a real stock movement posts no
  `record_transaction`** because it isn't a receive/issue event, just a label's tracked bin
  changing; net change to `product.amount` is zero, though unlike the other two exceptions this
  one is automatic (triggered by reading a tag) rather than a deliberate multi-step business
  process — that immediacy is the whole point of RFID versus a manual transfer. Creating a tag
  sanity-checks that the bin actually has at least that much of the product tracked; tag/bin
  quantities can still drift from reality if the underlying stock later moves through another path
  (pick, transfer, cycle count) without also re-reading the tag — documented plainly in the module
  docstring rather than hidden, the same class of drift already accepted for FIFO/LIFO cost layers
  and consignment balances. New pages at `/wms/rfid/readers/` (list + create) and
  `/wms/rfid/tags/` (list with a status filter + create, picking from real tracked stock across
  every warehouse) and `/wms/rfid/tags/<id>/` (current bin/status, Simulate Read form, Retire
  button, full read history), cross-linked from the existing Bin Master page. Verified end-to-end
  against a running dev server + local Postgres through the actual web views: seeded 20 tracked
  units of a real product into one zone's bin, created a reader in that zone and a second reader
  in a different zone, tagged 5 of those units, simulated a read at the same-zone reader and
  confirmed it logged a heartbeat with zero stock movement, simulated a read at the different-zone
  reader and confirmed exactly 5 units moved from the first bin to a bin in the second zone with
  `product.amount` staying net-unchanged and both read events recorded correctly, then retired the
  tag and confirmed its detail page no longer offers a read form. Cleaned up all test data
  afterward.

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

#### P4-E: e-Commerce Integration ✅ Done
- Shopify / WooCommerce webhook: new order → auto-create SO
- Inventory level sync: push on-hand qty to storefront on every transaction
- Product catalog sync: push price list changes to storefront
- Shipment confirmation: push tracking number back to storefront order

**Implementation notes:** `ecommerce_core.py` — real, platform-agnostic
inbound webhook handling: Shopify (`X-Shopify-Hmac-Sha256`) and
WooCommerce (`X-WC-Webhook-Signature`) both sign as
`base64(HMAC-SHA256(secret, raw_body))`, so `verify_webhook_signature`
covers both with one function; `parse_order_webhook` normalizes both
platforms' near-identical order JSON (`line_items: [{sku, quantity,
price, name}]`) into a common shape. `receive_order_webhook` verifies
the signature, dedupes against `ecommerce_order_log`
(`UNIQUE(connection_id, external_order_id)`) so retried/replayed
webhooks don't create duplicate orders — unlike EDI's one-shot manual
file upload (P4-D), a storefront webhook can legitimately fire more than
once for the same order — then creates a real Sales Order via the
existing, unmodified `sales_orders_core.next_so_number`/`create_so`/
`add_so_item`. Unmapped line items (no matching `storefront_item_xref`
row) still import as valid `so_item`s with `product_id=None`, mirroring
how `so_item` already supports text-only lines. `product` has no
SKU/code column anywhere in this codebase, so `storefront_item_xref`
(storefront SKU ↔ our `product_id`) is the actual field-mapping
mechanism, exactly as `edi_partner_item_xref` is for EDI.

There is no live Shopify/WooCommerce store reachable from this
environment, so outbound sync (inventory level, price, shipment
confirmation) is real, config-gated HTTP POST code (stdlib
`urllib.request` — no new dependency): if a connection has a
`sync_endpoint_url` configured, it is actually called and the real
success/failure is logged; with no endpoint configured the attempt is
logged as `queued` rather than faked as delivered — the exact precedent
already set by `send_daily_digest.py`'s `EMAIL_HOST`-gated email/print
fallback. Price push reads from this codebase's existing tiered pricing
(`price_list_core.get_price_for_product`) rather than
`product.purchase_price` (cost, not a sell price). "Push on every
transaction" is implemented as on-demand sync buttons (connection detail
page) plus a schedulable batch command (`manage.py sync_ecommerce`,
doc-commented with cron/Task Scheduler wiring like
`send_daily_digest.py`) rather than intrusive hooks into `product`'s 5+
duplicated `CREATE TABLE`/mutation call sites. New pages at
`/ecommerce/connections/...` (storefront connection + item xref setup,
shows the webhook URL to configure in the storefront's admin),
`/ecommerce/webhook/<id>/order/` (the machine-facing, non-session-gated
webhook receiver — HMAC *is* the auth here), and `/ecommerce/log/`;
cross-linked from `so_list.html` ("e-Commerce") and
`prod_shipping_detail.html` ("Push Shipment Confirmation"). Verified
end-to-end against a running dev server + local Postgres through the
actual web views and a real local HTTP listener: configured a real
storefront connection + item mapping, signed a realistic Shopify-shaped
order payload and POSTed it to the webhook, confirming a real SO was
created with the mapped line resolving to the right `product_id` and the
unmapped line staying text-only; replayed the identical payload and
confirmed it was detected as a duplicate (no second SO); POSTed with a
bad signature and confirmed a 401 rejection; pointed a connection's
`sync_endpoint_url` at a real local HTTP server and confirmed the actual
POST body arrived and was logged `success`, then at an unreachable port
and confirmed a real `failed` status with the real connection error;
used the "Sync Now" buttons with no endpoint configured and confirmed a
`queued` log entry; pushed a shipment confirmation for a shipment on the
webhook-created SO and confirmed the right `external_order_id` appeared
in the payload; ran `manage.py sync_ecommerce` and confirmed its summary
output; cleaned up all test data afterward.

#### P4-F: Custom Report Builder ✅ Done
- Field selector: pick any table/column to include
- Filter builder: add conditions (field, operator, value)
- Group-by and aggregate (sum, count, avg)
- Sort order configuration
- Save report with name and access level
- Schedule delivery: run on schedule → email CSV/PDF to recipients

**Implementation notes:** `report_builder_core.py` — a generic ad-hoc
query tool over a hardcoded allowlist of 11 tables (`sales_order`,
`so_item`, `work_order`, `product`, `purchase_order`, `po_item`,
`customer`, `supplier`, `ar_invoice`, `ap_invoice`, `shipment`), whose
columns were verified directly against the live dev DB's
`information_schema.columns` rather than trusted from `CREATE TABLE`
strings (this codebase's live schema is known to diverge from its DDL —
see the DB gotchas section above). v1 scope is deliberately
**single-table** (no cross-table joins), which still covers every
roadmap bullet without the much larger design surface of a join-graph
UI. SQL injection is the central risk of any report builder — this
codebase has no `psycopg2.sql.Identifier`/runtime-identifier-safety
infrastructure to build on, so `validate_definition` is the actual
security boundary: every table and column name is checked against
`REPORTABLE_TABLES` before it can reach a SQL string, and is safe to
string-format afterward *specifically because* it is then guaranteed to
be the literal allowlist dict key, never raw user text. Filter *values*
are always sent as `%s` parameters. Aggregate output aliases are
computed server-side (`f"{func}_{column}"`) rather than accepted from
the client, removing a free-text-alias injection surface entirely.
Verified end-to-end via the real web UI and a deliberately
malicious-looking filter value (`'; DROP TABLE product; --`), which was
correctly treated as an inert literal filter value with zero effect on
the schema; also verified aggregate math (`SUM`/`AVG` grouped by
product) against a manual SQL query, byte-for-byte-correct CSV/PDF
export, and `access_level` visibility (`private`/`department`/
`company`) filtering correctly between two different users. Scheduled
delivery (`manage.py run_scheduled_reports`) reuses the exact
`EMAIL_HOST`-gated send-or-print fallback already established by
`send_daily_digest.py`, using `django.core.mail.EmailMessage` instead of
`send_mail` since only the former supports attachments; a report's
`last_run_at` plus its `daily`/`weekly`/`monthly` frequency determines
whether it's due, verified end-to-end (a report ran once, then a second
immediate run correctly skipped it as not yet due).

#### P4-G: Sustainability / Carbon Cost Tracking ✅ Done
- CO₂ emission factor per material (kg CO₂e per unit)
- CO₂ emission factor per process/operation (kg CO₂e per hour)
- Carbon cost rollup on BOM → product carbon footprint
- Carbon intensity metric: kg CO₂e per unit produced
- ESG dashboard: scope 1 (direct), scope 2 (energy), scope 3 (supply chain)

**Implementation notes:** `carbon_core.py` — a direct structural mirror
of the existing standard-cost rollup (`costing_core.roll_standard_cost`):
same BOM-explosion recursion, same `'buy'` (direct per-unit factor) vs
`'make'` (recursive children + own routing process emissions) split,
same `_MAX_DEPTH`/`_visited` cycle guard, same roll-then-snapshot
(`carbon_roll`) pattern, same per-WO-actual-quantity multiplication
(`wo_carbon_actual`) for a carbon-intensity-per-unit metric — kg CO₂e
instead of dollars. Material factor (`kg_co2e_per_unit`) lives directly
on `product`, parallel to `purchase_price`; process factor
(`kg_co2e_per_hour`) lives on `workcenter`, parallel to
`overhead_rate` — both added additively via `ALTER TABLE ... ADD COLUMN
IF NOT EXISTS`, the same technique `costing_core.ensure_costing_tables`
already uses. Scope framework is a simplified, GHG-Protocol-*inspired*
model (explicitly not full compliance tooling): Scope 1 (direct
operations) and Scope 3 (purchased goods / supply chain) are computed
from real production data (`wo_carbon_actual`'s process/material split);
Scope 2 (purchased energy) is honestly manual monthly kWh × grid-factor
entry, since no energy/kWh telemetry exists anywhere in this codebase
(no power field on equipment, no utility-bill import) to automate it —
the default grid factor is a documented illustrative placeholder, not an
authoritative regional figure. ESG dashboard at `/esg/` reuses this
codebase's existing Chart.js wiring (P1-A) for a scope 1/2/3 doughnut and
a monthly trend bar chart. Verified end-to-end against a running dev
server + local Postgres through the actual web views: set a material
factor on a real leaf ("buy") component and a process factor on a real
workcenter, rolled a real product's carbon footprint and confirmed
material/process/total matched a manual hand calculation from the BOM +
routing exactly; computed WO carbon actuals for a real work order and
confirmed the quantity multiplication was exact; added a Scope 2 manual
entry and confirmed the ESG dashboard's scope totals, top-products list,
and charts reflected it correctly; cleaned up all test data afterward.

---

### 🟣 Priority 5 — Further "Buildable Now" Gaps Closed

#### P5-A: What-If Scenario Planning ✅ Done
- A named scenario holds hypothetical adjustments — extra demand for a product, or a temporary
  capacity override on a workcenter — compared against the real baseline without ever writing to
  real data
- **Shipped:** `scenario_planning_core.py` — `create_scenario`/`list_scenarios`, demand/capacity
  adjustment CRUD, and `run_scenario`, which returns baseline-vs-scenario MRP volume and
  bottleneck pressure side by side. Demand adjustments feed `mrp_web_core.run_mrp_dated`'s new
  `extra_demand: dict | None = None` parameter — additive/opt-in, the exact same pattern as
  P4-A's `include_forecast`, so every existing caller's behavior is byte-for-byte unchanged.
  Capacity adjustments overlay a hypothetical per-day hours override on top of
  `capacity_planning_core.get_capacity_check`'s real output entirely in Python; the real
  `workcenter`/`workcenter_calendar_exception` tables are never written to. New pages at
  `/scenarios/` (list + create), `/scenarios/<id>/` (adjustment editor), and
  `/scenarios/<id>/run/` (baseline vs. scenario comparison). **Found and fixed one real bug while
  verifying end-to-end:** merging a scenario's TEXT `need_date` into MRP's demand list raised
  `TypeError: '<' not supported between str and date`, because confirmed-SO demand dates come
  back from Postgres as `datetime.date` — the same class of bug `demand_forecast_core.
  get_forecast_demand_dated` already normalizes against for the same reason; fixed the same way
  and locked in with `test_run_scenario_normalizes_string_need_date_to_date`.

#### P5-B: Control Plans & FMEA ✅ Done
- A control plan is a per-product register of characteristics to control during production, each
  with a control method and an FMEA risk score: RPN (Risk Priority Number) = Severity x
  Occurrence x Detection, each rated 1–10 on the standard AIAG-style scale
- **Shipped:** `fmea_core.py` — `control_plan` (header: product, name/revision, status) and
  `control_plan_item` (one row per characteristic: spec, control method, S/O/D ratings, computed
  RPN, recommended action) tables, plus `create_control_plan`, `add_control_plan_item`/
  `update_control_plan_item` (recomputes RPN on any rating change), and `get_high_risk_items` for
  a cross-plan risk register filtered by RPN threshold. The specific rating anchors (what makes
  something a severity 7 vs. 8) vary by organization/industry standard and are deliberately not
  encoded — this module only enforces the 1–10 range and the multiplication, the same
  "structure is real, the org's own numbers still need expert judgment" scoping already used for
  `sampling_plan_core`'s AQL disclaimer. New pages at `/qa/control-plans/` (list + create),
  `/qa/control-plans/<id>/` (characteristic editor with live RPN), and
  `/qa/fmea/risk-register/` (cross-plan high-risk view), cross-linked from the QA menu alongside
  sampling plans.

#### P5-C: Activity-Based Costing (ABC) ✅ Done
- A parallel, opt-in analysis layer next to `costing_core.roll_standard_cost`'s single flat
  overhead rate (workcenter `overhead_rate` x routing `std_hours`, still the default for every
  existing caller) — allocates the same overhead dollars via activity cost pools and real
  consumption drivers, then flags products where the two methods disagree
- **Shipped:** `abc_costing_core.py` — `abc_activity` (a cost pool: total overhead $ for one
  activity plus its driver's unit of measure, e.g. "$40,000 / per setup"), `abc_product_driver`
  (how much of an activity's driver each product consumed), and `abc_product_output` (units
  actually produced, kept as its own small table since output doesn't vary by activity).
  `compute_activity_rate` → `get_abc_overhead_for_product` → `compare_to_traditional` chains
  through to flag any product where ABC and the existing flat-rate roll disagree by more than
  `VARIANCE_FLAG_THRESHOLD_PCT` (15%); `get_abc_summary_all_products` sorts the whole product
  list by absolute variance so the biggest mis-costed items surface first. This closes the last
  remaining gap in the entire Finance & GL domain table. New pages at
  `/gl/abc-costing/activities/` (list + create), `/gl/abc-costing/activities/<id>/` (driver
  entry per product), `/gl/abc-costing/products/<id>/output/` (output qty entry), and
  `/gl/abc-costing/report/` (the full ABC-vs-traditional comparison, variance-flagged).

---

### 🟤 Priority 6 — Discount/CoA/Skills-Matrix (Built in Parallel, Merged After Rebase)

#### P6-A: Discount & Promotion Management ✅ Done
- Percent/fixed-amount discount rules scoped to a product and/or customer, with a minimum-qty
  threshold and an effective date window
- **Shipped:** `discount_core.py`. Resolution picks whichever applicable rule gives the customer
  the lowest final price. Auto-applies on the SO line-entry form via the same client-side
  JSON-embed pattern the existing tiered pricing (`price_list_core.py`) already uses — no new
  pricing-calculation code path, just a second rule source feeding the same "lowest applicable
  price wins" resolution. Admin at `/promotions/`.

#### P6-B: Certificate of Analysis (CoA) Generation ✅ Done
- Generates a CoA per lot from that lot's existing SPC measurements
- **Shipped:** `coa_core.py`, reusing `quality_core.py`'s `spc_measurement`/`spc_control_limit`
  tables — no new measurement data model. Snapshots results into `coa_document`/`coa_result` at
  generation time so a later measurement edit can't retroactively alter an issued certificate.
  Ships a PDF via the same reportlab pattern already used for invoices/packing slips. Pages at
  `/qa/coa/`.

#### P6-C: Skills Matrix & Competency Gap Analysis ✅ Done
- A skill master, required-proficiency-per-job-title requirements, per-employee assessed levels,
  a per-employee gap report, and an org-wide gap-ranked summary
- **Shipped:** `skills_matrix_core.py`. Requirements key on `position.job_title` (free text,
  matched case-insensitively) since no job-title master table exists to key on instead. Pages at
  `/skills/`.

This batch was built on a parallel branch (`feature/discount-coa-skills-matrix`, PR #410) at the
same time as Priority 5 above, off the same base commit — rebased onto the Priority 5 work with
three small additive conflicts (an import-block merge, a cross-link button merge, and two domain
tables where each branch had independently completed one adjacent row) before merging.

---

### ⚪ Priority 7 — Benefits, Regulatory Compliance, and Workforce Analytics

#### P7-A: Benefits Management ✅ Done
- A benefit plan catalog (Health/Dental/Vision/Life/Disability/401k) with employee/employer cost
  per pay period, and per-employee enrollments by tier (Employee Only / +Spouse / +Child(ren) /
  Family)
- **Shipped:** `benefits_core.py` — `benefit_plan`/`benefit_enrollment` tables, `create_plan`/
  `enroll_employee` (rejects a duplicate active enrollment in the same plan), `waive_enrollment`/
  `terminate_enrollment`, and `get_benefits_dashboard` (org-wide cost + enrollment breakdown by
  plan type). Deliberately kept **separate from** `payroll_core`'s existing `payroll_deduction_type`/
  `employee_deduction` tables (which already model a flat/percent payroll deduction, including a
  'Benefits' category) rather than merged into them — the two answer different questions ("which
  plans exist and who's enrolled at what tier" vs. "how much comes out of this paycheck"); enrolling
  here does not create or touch any `employee_deduction` row, the same "two independent sources of
  truth" scoping already accepted for the FIFO/LIFO cost layers existing beside standard costing.
  New pages at `/benefits/` (org dashboard + plan list), `/benefits/plans/new/`,
  `/benefits/plans/<id>/` (enrollment management), and `/benefits/employee/<id>/` (an employee's
  own active enrollments and per-pay-period cost), cross-linked from the Personnel Dashboard and
  each employee's profile page.

#### P7-B: Regulatory Compliance Templates (FDA, ISO) ✅ Done
- Reusable requirement checklists for a named standard, instantiated per real audit/scope with
  per-item status and evidence tracking. Closes Quality Management's last remaining domain gap.
- **Shipped:** `regulatory_compliance_core.py` — `compliance_template`/`compliance_template_item`
  (the reusable requirement list) and `compliance_checklist`/`compliance_checklist_item` (one
  instantiation against a real scope). `create_checklist` snapshots every template item into its
  own checklist-item row at creation time, the same snapshot-at-instantiation choice already used
  for CoA generation against SPC measurements — editing the template afterward never rewrites a
  checklist already in progress. Seeds two starter templates (`seed_default_templates`, called
  idempotently on every template-list page load): "ISO 9001:2015 Quality Management System" and
  "FDA 21 CFR Part 820 Quality System Regulation", each with a handful of representative clauses.
  **These are explicitly disclosed as illustrative, not certified or exhaustive** — the same
  "structure is real, the org's own content still needs expert judgment" scoping already used for
  FMEA's S/O/D rating anchors and `sampling_plan_core`'s AQL disclaimer; consult the actual
  standard text and a qualified auditor for real certification work. New pages at
  `/qa/compliance/templates/` (list, seeded on load) and `/qa/compliance/templates/new/`,
  `/qa/compliance/templates/<id>/` (requirements + instantiate-a-checklist), and
  `/qa/compliance/checklists/` + `/qa/compliance/checklists/<id>/` (per-item status/evidence
  entry with a live progress rollup), cross-linked from the Sampling Plans page alongside Control
  Plans and CoA.

#### P7-C: Workforce Analytics & Headcount Planning ✅ Done
- Headcount summary/trend, average tenure, and trailing-12-month turnover, plus per-department
  target-vs-actual headcount planning
- **Shipped:** `workforce_analytics_core.py`. There was no hire-date/termination-date tracking
  anywhere in this app before this — `ensure_workforce_columns` adds `hire_date`,
  `termination_date`, and `employment_status` to `people` via additive `ALTER TABLE ... ADD
  COLUMN IF NOT EXISTS`, the same pattern `personnel_core.ensure_contact_columns` already used for
  phone/emergency-contact fields. **Every tenure/trend/turnover number is computed only from
  employees whose hire_date has actually been entered** — existing employees default to an empty
  string and are silently excluded from the math rather than backfilled with a fabricated hire
  date, disclosed plainly in the module docstring rather than hidden, the same "drift/gaps are
  real, document them" scoping already used for RFID tag/bin quantity drift. Headcount planning
  is a second, independent `headcount_plan` table — an admin-entered target headcount per
  department by a target date, compared against today's actual active headcount; there's no
  forecasting model, just a real target vs. a real count. New pages at `/workforce/` (summary +
  by-dept breakdown + 12-month trend + plan-vs-actual), `/workforce/headcount-plans/new/`, and
  `/workforce/employee/<id>/` (set an employee's hire/termination dates), cross-linked from the
  Personnel Dashboard and each employee's profile page. Verified end-to-end against a running dev
  server + local Postgres through the actual web views for all three P7 features in this batch:
  created a benefit plan and enrolled/waived a test employee and confirmed the dashboard and
  employee-facing pages reflected it; confirmed the ISO/FDA templates seed correctly, instantiated
  a checklist from one, marked an item complete with evidence notes, and confirmed the progress
  rollup persisted; set a test employee's hire date, created a headcount plan, and confirmed the
  workforce dashboard reflected both. Cleaned up all test data afterward.

---

### 🟢 Priority 8 — Applicant Tracking / Recruiting

#### P8-A: Applicant Tracking / Recruiting (ATS) ✅ Done
- Job requisitions, candidates, and applications moving through a fixed pipeline (Applied →
  Screening → Interview → Offer → Hired/Rejected) with a full stage-history audit trail. Closes
  the last remaining gap in the HR/Payroll & Personnel domain table.
- **Shipped:** `ats_core.py` — `job_requisition`/`candidate`/`application`/
  `application_stage_history` tables; `create_requisition`/`update_requisition_status`,
  `create_candidate`, `create_application`, `advance_stage` (rejects moving an application that's
  already in a terminal stage — 'Hired' or 'Rejected' — since reopening a closed application
  isn't supported; create a new application against a reopened requisition instead), and
  `get_ats_dashboard` (open requisitions, total candidates, a pipeline-stage funnel, recent
  hires). **The one place this module writes outside itself**: `convert_to_employee` advances an
  application to 'Hired' and creates a real `people` row via `personnel_core.create_person`, then
  sets its `hire_date` via `workforce_analytics_core.set_employment_dates` — the same hire_date
  column P7-C added. This is the only path in the app that sets a hire_date automatically instead
  of requiring a manual HR entry, so a candidate hired through the ATS is counted correctly by
  Workforce Analytics from day one; an employee added directly via `/people/new/` (bypassing the
  ATS entirely) still needs its hire_date set by hand, same as before this module existed — a
  `people` row stays the single source of truth for actual staff, `candidate` never becomes one
  until someone is actually hired. New pages at `/ats/` (dashboard + pipeline funnel + recent
  hires), `/ats/requisitions/` (list + new + detail with an apply-candidate form),
  `/ats/candidates/` (list + new + detail with an apply-to-requisition form), and
  `/ats/applications/<id>/` (stage history, advance-stage form, and the hire-conversion form),
  cross-linked from the Personnel Dashboard. Verified end-to-end against a running dev server +
  local Postgres through the actual web views: created a requisition and a candidate, applied the
  candidate to the requisition, advanced the application through Screening → Interview → Offer
  confirming stage history recorded each transition, hired the candidate and confirmed a real
  Personnel record was created with the correct hire date and `employment_status = 'active'`,
  confirmed the now-terminal application correctly hides its advance-stage form, and confirmed
  Workforce Analytics remained reachable with the new hire counted. Cleaned up all test data
  afterward.

---

### 🔵 Priority 9 — Supplier Self-Service Portal

#### P9-A: Supplier Self-Service Portal ✅ Done
- A separate, non-employee supplier login for viewing/acknowledging purchase orders, submitting
  AP invoices, and quoting on invited RFQs. Closes the last remaining gap in the Purchasing &
  Procurement domain table.
- **Shipped:** `supplier_portal_core.py`, structurally identical to `customer_portal_core.py`
  (P3-C): `supplier_login` holds one bcrypt-hashed credential per `supplier.id`, matched at
  registration time against that supplier's own `email` column — no blind account creation.
  Session/auth wiring lives in `auth_decorators.supplier_login_required` and
  `views/_supplier_portal.py`, under `portal_supplier_id` — deliberately separate from the
  employee `user_*` keys *and* the customer portal's `portal_customer_id`, so a browser could in
  principle hold both portal sessions at once without collision. Every capability reuses an
  existing core module rather than forking it:
  - **Purchase orders** — `purchase_orders_core.list_pos/get_po/get_po_items`, already filterable
    by `supplier_id`. PO acknowledgement is the one genuinely new piece of state: two additive
    columns on `purchase_order` (`supplier_acknowledged_at`, `supplier_ack_notes`), since nothing
    tracked "did the supplier confirm this order" before this module existed.
  - **AP invoices** — self-service submission reuses `accounting_core.create_ap_invoice`
    directly (`vendor_id` *is* `supplier_id` — the `ap_invoice` table's column is just named
    differently), with an ownership check when a `po_id` is supplied so a supplier can't invoice
    against someone else's order.
  - **RFQs** — a supplier only sees RFQs they're actually invited to (`rfq_vendor`), and
    `submit_quote` calls `rfq_core.enter_quote` — the exact same function an internal buyer uses
    when keying in a phoned-in quote — after verifying the RFQ line's `rfq_id` has this supplier
    in `rfq_vendor`.
  New pages at `/supplier-portal/` (dashboard: open PO count, unacknowledged count, open invoice
  balance, open RFQ count), `/supplier-portal/pos/` + `/supplier-portal/pos/<id>/`
  (acknowledgement form), `/supplier-portal/invoices/` + `/supplier-portal/invoices/new/`
  (self-service submission, optionally tied to a PO), and `/supplier-portal/rfqs/` +
  `/supplier-portal/rfqs/<id>/` (per-line quote entry, pre-filled with the supplier's own
  existing quote if any), plus `/supplier-portal/register/` and `/supplier-portal/login/`
  (cross-linked from the employee login page and the Purchasing Dashboard, same pattern as the
  customer portal's login link). Verified end-to-end against a running dev server + local
  Postgres through the actual web views: created a real supplier, a PO, and an RFQ inviting that
  supplier; registered and logged into the portal; confirmed the dashboard and PO detail page
  showed the real PO; acknowledged the PO and confirmed the timestamp/notes persisted; submitted
  an AP invoice against that PO and confirmed it appeared correctly in both the list and detail
  pages; submitted an RFQ quote and confirmed it landed in `rfq_quote_line` under the supplier's
  own `vendor_id`, visible to an internal buyer's existing quote-comparison view unmodified;
  confirmed a made-up/unowned PO id correctly 404s rather than leaking another supplier's order.
  Cleaned up all test data afterward.

---

### 🟠 Priority 10 — Configure-to-Order, Recipe Management, Repetitive Manufacturing

#### P10-A: Configure-to-Order (CTO) ✅ Done
- Per-product option groups (e.g. "Frame Color") each holding mutually-exclusive options, each
  mapped to a BOM-component substitution; a customer's actual selections for one SO line resolve
  into a configured material list that releases a real Work Order. Closes one of three remaining
  Production Planning & Scheduling gaps.
- **Shipped:** `cto_core.py` — `cto_option_group`/`cto_option` (product-level setup) and
  `cto_configuration`/`cto_configuration_selection` (per-SO-line selections) tables.
  `generate_configured_bom` resolves a configuration: every base BOM line (via
  `bom_web_core.get_bom`) except the ones covered by an option group's slot components, plus the
  selected options' own components — the base `bom` table stays the single source of truth for
  the product's fixed structure, only the option-covered slots get swapped. **There was no
  SO-to-WO conversion path anywhere else in this app before this** — production has always been
  planned from aggregate confirmed-SO demand via MRP, never by converting one SO line into its
  own WO. `release_configured_wo` fills that gap for the CTO case specifically (where the whole
  point is that *this* order's WO needs *this* customer's exact configuration), reusing
  `work_orders_core.create_wo` and `bom_core.explode_quantity` — no forked WO-creation logic.
  Rejects releasing an incomplete configuration (a selection missing for any option group). New
  pages at `/cto/products/` (which make products are configurable), `/cto/products/<id>/options/`
  (set up groups/options), and `/cto/configure/<so_item_id>/` (make selections, see the resolved
  material list, release the WO), cross-linked from the Production Dashboard and a new
  "Configure" link on each SO line item.

#### P10-B: Recipe / Formula Management (Process Manufacturing) ✅ Done
- Batch-based recipes for process manufacturing, with a draft→active→superseded lifecycle and
  scaling to any target output quantity that correctly accounts for process yield loss.
- **Shipped:** `recipe_core.py` — `recipe` (product, batch_size, batch_uom, yield_pct, status)
  and `recipe_ingredient` (qty per batch) tables. Deliberately **parallel to the `bom` table, not
  a fork or a replacement of it** — the same "parallel, not merged" scoping already used for
  FIFO/LIFO cost layers next to standard costing: BOM's `qty_required` is a fixed per-unit
  quantity, right for discrete assembly, but a recipe scales per **batch**, and yield loss means
  scaling isn't a straight ratio — producing more good output than one batch normally yields
  requires proportionally *more* input than the naive (target / batch_size) multiply would give,
  which `scale_recipe` computes correctly (`batches_needed = target_qty / (batch_size *
  yield_fraction)`). `activate_recipe` mirrors `document_control_core`'s single-active-revision
  pattern — activating one recipe automatically supersedes whichever was previously active for
  the same product, so exactly one recipe is ever the one `release_batch_wo` actually uses.
  `release_batch_wo` creates a real WO via `work_orders_core.create_wo` with materials populated
  from the scaled recipe. New pages at `/recipes/` (list + new), `/recipes/<id>/` (ingredients,
  activation, scale-preview, batch release), cross-linked from the Production Dashboard.

#### P10-C: Repetitive Manufacturing ✅ Done
- Rate-per-day production schedules (product + workcenter) with daily output logging that
  automatically backflushes BOM components, instead of a discrete Work Order per production run.
  Closes the last remaining Production Planning & Scheduling gap.
- **Shipped:** `repetitive_core.py` — `repetitive_schedule` (rate_per_day, effective date range,
  active/inactive) and `repetitive_production_log` (one row per day's completed/scrapped qty)
  tables. `log_production` is the core of the module: for the units completed, it computes the
  BOM-derived component quantities (reusing `bom_web_core.get_bom` + `bom_core.explode_quantity`
  — no forked BOM logic) and posts them through `inventory_core.record_transaction` — an
  `'issue'` for each component and a `'receive'` for the finished product, **the same audited
  transaction path every other inventory movement in this app already goes through**, not a new
  bypass or net-zero exception. Scrapped units are logged but not backflushed — no component
  consumption or output credit for units that didn't ship. `get_schedule_summary` reports planned
  (rate × days in range) vs. actual vs. scrapped vs. attainment % over any date range. New pages
  at `/repetitive/` (list + new), `/repetitive/<id>/` (status, log production, production log,
  planned-vs-actual), cross-linked from the Production Dashboard. Verified end-to-end against a
  running dev server + local Postgres through the actual web views for all three P10 features in
  this batch: configured a bike's frame-color option, released a WO and confirmed its materials
  contained only the selected color's component (not the unselected one); created and activated a
  syrup recipe at 80% yield, confirmed the scaled-ingredient preview and the released batch WO's
  materials both correctly required more sugar than a naive linear scale would (400 kg sugar for
  a 500 kg target, not 320 kg); created a repetitive schedule and logged 50 completed + 2 scrapped
  units, confirming the finished product's on-hand quantity increased by exactly 50 and its BOM
  component's on-hand quantity decreased by exactly 200 (4 per unit × 50) via real inventory
  transactions. **Found and fixed one real bug while verifying end-to-end:** the CTO release
  view passed the release-quantity form field through as a raw string, and `round()` on a string
  raised `TypeError: type str doesn't define __round__ method` — fixed by coercing to `float()` in
  the view before calling `release_configured_wo`, the same coercion pattern every other numeric
  form field in this batch already used. Cleaned up all test data afterward.

---

### 🟢 Priority 11 — Technician Routing, Asset Performance Management, Batch Records

#### P11-A: Technician Routing & Scheduling ✅ Done
- Ordered daily stop lists per mechanic against real maintenance work orders, so a dispatcher can
  see and plan one technician's whole day instead of `maint_work_order.assigned_to`'s bare
  free-text "who's assigned" with no sequencing. Closes one of the last two Maintenance gaps.
- **Shipped:** `technician_routing_core.py` — `technician_route` (mechanic, date, status) and
  `technician_route_stop` (ordered `maint_work_order` references with an estimated duration) 
  tables. `add_stop` auto-assigns the next sequence number; `move_stop` swaps a stop with its
  neighbor to reorder. `complete_stop` is the one place this module writes outside itself: it
  calls `maintenance_core.complete_work_order` — the exact same function an internal CMMS user
  would call — rather than forking work-order completion, then auto-completes the route once every
  stop on it is done. New pages at `/maint/routes/` (list + new) and `/maint/routes/<id>/`
  (reorderable stop list, add-stop form, complete-stop actions), cross-linked from the
  Maintenance Dashboard.

#### P11-B: Asset Performance Management (APM) ✅ Done
- A per-asset health score and repair-vs-replace recommendation, ranked dashboard worst-first.
  Closes the last Maintenance gap.
- **Shipped:** `apm_core.py` — deliberately does not reimplement reliability math that already
  existed: `maintenance_core.get_mtbf` already computes real MTBF/MTTR/availability from
  `maint_downtime` records. APM adds the layer on top — `asset_criticality` (admin-set, since no
  formula can infer how much an asset actually matters to the business) combined with that
  existing availability data and the asset's real downtime cost (`maint_downtime.cost`, already
  tracked but never rolled up per asset before this module) into `get_asset_health`'s health score:
  `availability_pct` penalized by `failure_count × criticality_weight`, clamped to [0, 100]. The
  recommendation threshold is stricter for higher-criticality assets — the same failure count
  matters far more on a critical asset than a low-priority one, so a critical asset crosses into
  "consider replacement" at a higher score than a low-criticality one would. New pages at
  `/maint/apm/` (ranked dashboard), `/maint/apm/criticality/` (set ratings), and
  `/maint/apm/asset/` (one asset's health detail + recommendation), cross-linked from the
  Maintenance Dashboard.

#### P11-C: Batch Record Generation ✅ Done
- Numbered, point-in-time as-built records for completed Work Orders — materials consumed, cost,
  and quality inspections performed — with a PDF export. Closes the last Reporting & Analytics
  gap (aside from the standing broader-embedded-AI-platform Enterprise gap).
- **Shipped:** `batch_record_core.py` pulls together data that already existed across three other
  modules (`work_orders_core.get_wo`/`get_wo_materials`/`get_wo_cost_summary`, and `qa_inspection`
  rows keyed by `wo_id`) and **snapshots** it into `batch_record`/`batch_record_material`/
  `batch_record_inspection` rows at generation time — the same snapshot-not-live-query choice
  `coa_core` already made for Certificates of Analysis, for the same reason: a record that
  silently changed if someone later edited a WO's materials would defeat the point of having a
  record. `generate_batch_record` only accepts a `'completed'` Work Order — an unfinished job has
  no as-built story worth recording yet. `render_batch_record_pdf` mirrors the reportlab pattern
  already established in `coa_core.py`/`customer_portal_core.py`. New pages at `/batch-records/`
  (list + generate-from-completed-WO form) and `/batch-records/<id>/` (materials, cost, quality
  inspections, PDF download), cross-linked from the Production Dashboard. Verified end-to-end
  against a running dev server + local Postgres through the actual web views for all three P11
  features in this batch: created a mechanic and a maintenance WO, built a route, added a stop,
  completed it, and confirmed both the underlying maintenance WO and the route itself flipped to
  completed automatically; logged two breakdown events with real cost against a test asset, set
  its criticality to critical, and confirmed the APM dashboard and asset detail page surfaced a
  real repair/replace recommendation (not just raw MTBF numbers); completed a real production WO
  with materials and a quality inspection attached, generated a batch record, and confirmed the
  detail page showed the correct snapshotted materials, inspection, and cost ($20.00 material
  cost = 200 bolts × $0.10), then downloaded a real PDF. Cleaned up all test data afterward.

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
| No EDI (850/855/856/810) | P4-D |
| No e-commerce (Shopify/WooCommerce) integration | P4-E |
| No self-service report builder | P4-F |
| No sustainability / carbon cost tracking | P4-G |
| No true inter-warehouse transfers | P3-H |
| No FIFO/LIFO/weighted-average valuation | P3-I |
| No consignment inventory | P3-J |
| No wave picking management | P3-K |
| No cross-docking | P3-L |
| No RFID tracking | P3-M |
| No what-if scenario planning | P5-A |
| No control plans / FMEA | P5-B |
| No Activity-Based Costing (ABC) | P5-C |
| No discount & promotion management | P6-A |
| No Certificate of Analysis (CoA) generation | P6-B |
| No skills matrix / competency gap analysis | P6-C |
| No benefits management | P7-A |
| No regulatory compliance templates (FDA, ISO) | P7-B |
| No workforce analytics / headcount planning | P7-C |
| No Applicant Tracking / Recruiting (ATS) | P8-A |
| No supplier self-service portal | P9-A |
| No Configure-to-Order (CTO) | P10-A |
| No recipe / formula management (process mfg) | P10-B |
| No repetitive manufacturing | P10-C |
| No technician routing & scheduling | P11-A |
| No Asset Performance Management (APM) | P11-B |
| No batch record generation | P11-C |
| No broader embedded-AI analytics platform | P12-A |

### Where We Trail Mid-Market (Epicor / SYSPRO / Infor target)

Every item previously listed here has shipped (the last, RFID, closed as P3-M — see the note under
"Where We Trail Enterprise" below for the real-hardware caveat that remains). None outstanding.

### Where We Trail Enterprise (SAP / Oracle / Dynamics)

| Gap | Effort to Close |
|---|---|
| No real IoT / sensor / RFID hardware integration (predictive maintenance and RFID both ship with real logic behind a manual/simulated stand-in for live hardware) | Very High |
| No real carrier-API shipment tracking (FedEx/UPS/USPS) | Medium–High |
| No real AS2/VAN/SFTP EDI transport (file upload/download stub only) | Medium |
| No live storefront to verify outbound e-commerce sync against (config-gated HTTP code only) | Low–Medium |

---

## Section 4: Feature Gap Score Card

| Domain | Score vs. Mid-Market | Score vs. Enterprise | Change |
|---|---|---|---|
| Work Orders & BOM | 9/10 | 8/10 | — |
| MRP | 8/10 | 7/10 | — |
| Inventory | 9/10 | 8/10 | ▲▲▲▲▲ (cycle count + WMS bins + inter-warehouse transfers (P3-H) + FIFO/LIFO/weighted-average costing (P3-I) + consignment inventory (P3-J) + RFID tracking (P3-M, simulated)) |
| Quality (QA) | 9/10 | 9/10 | ▲▲▲▲ (sampling/AQL + document control + control plans/FMEA (P5-B) + CoA generation (P6-B) + regulatory compliance templates (P7-B) — domain fully closed) |
| Purchasing | 9/10 | 9/10 | ▲▲▲▲▲ (RFQ + scorecards + MRP auto-release + landed cost + blanket POs + EDI + supplier self-service portal (P9-A) — domain fully closed) |
| Sales / CRM | 9/10 | 8/10 | ▲▲▲▲▲ (ATP + price lists + customer portal + CTP + e-commerce sync + discount/promotion management (P6-A)) |
| Finance / GL | 9/10 | 9/10 | ▲▲▲▲ (cash flow statement/forecast + multi-entity/intercompany/consolidated + carbon/ESG tracking + Activity-Based Costing (P5-C)) |
| Fixed Assets | 9/10 | 8/10 | — |
| Multi-Currency | 8/10 | 7/10 | — |
| HR / Payroll | 9/10 | 9/10 | ▲▲▲▲▲ (ESS portal + skills matrix (P6-C) + benefits management (P7-A) + workforce analytics/headcount planning (P7-C) + ATS (P8-A) — domain fully closed) |
| Maintenance (CMMS) | 9/10 | 9/10 | ▲▲▲▲▲ (OEE + live shop-floor dashboard/TV (P3-G) + predictive maintenance risk scoring (P4-B) + technician routing (P11-A) + Asset Performance Management (P11-B); mobile app now credited — domain fully closed apart from real IoT hardware) |
| IT Management | 10/10 | 9/10 | — |
| Reporting / Analytics | 9/10 | 9/10 | ▲▲▲▲▲▲▲▲ (charts, CSV+Excel export, OEE reports, live shop-floor OEE (P3-G), AI demand forecast (P4-A), self-service report builder (P4-F), batch record generation (P11-C), digest now credited, broader embedded-AI analytics platform / AI Insights Hub (P12-A) — domain fully closed) |
| Scheduling / APS | 9/10 | 7/10 | ▲▲▲▲▲▲▲ (P3-A finite capacity scheduling + what-if scenario planning (P5-A) + Configure-to-Order (P10-A) + recipe/formula management (P10-B) + repetitive manufacturing (P10-C) — domain fully closed) |
| WMS / Shipping | 9/10 | 7/10 | ▲▲▲▲▲ (P3-B full pick/pack/ship + wave picking (P3-K) + cross-docking (P3-L)) |
| **Overall** | **9.3/10** | **8.7/10** | **▲ from 7.1 / 5.9** |

---

## Section 5: Next 10 Features to Build (Ordered by ROI)

All 16 of the original "next 10 + P3-A/B" items are shipped, plus Excel export (P1-G), landed
cost allocation (P3-D), blanket POs/call-offs (P3-E), and the customer self-service portal (P3-C).

**Status update (2026-07-08):** every numbered roadmap item from P1 through P4 has now shipped —
the last batch (P3-F through P4-G) turned out to already have open PRs from a prior session
(#387–#395), discovered while working through this list, and were merged one at a time (rebase
onto current `main`, verify, fix any cross-PR conflicts, confirm before merging) rather than
re-built. The two gaps discovered along the way with no PR ever opened for them — true
inter-warehouse transfers (P3-H) and FIFO/LIFO/weighted-average costing (P3-I) — have since both
been built fresh and shipped. Consignment inventory (P3-J), wave picking (P3-K), cross-docking
(P3-L), and RFID tracking (P3-M) — four more next-highest-ROI items, taken one at a time as each
prior one closed — have since also shipped, closing out the "Where We Trail Mid-Market" list
entirely. Everything tracked in Sections 1–4 above that shows a ✅ or a closed-gap entry is real,
verified, shipped code; the only gaps left are Section 3's "Where We Trail Enterprise" table —
real external-connectivity/hardware dependencies this dev environment has no live counterpart for
(RFID and predictive maintenance both ship real logic behind an honestly-scoped manual/simulated
stand-in for that missing hardware, same as EDI/e-commerce do for missing live external systems) —
or lower-ROI items not yet scheduled.

**Status update (2026-07-09):** with every numbered P1–P4 roadmap item and the "Where We Trail
Mid-Market" list fully closed, shipped six more highest-ROI items from what remained scattered
across the Section 1 domain tables as plain ❌ entries, built in two parallel batches off the same
base commit: what-if scenario planning (P5-A), control plans/FMEA (P5-B), and Activity-Based
Costing (P5-C) — see Priority 5 above — plus discount/promotion management (P6-A), Certificate of
Analysis generation (P6-B), and skills matrix/competency gap analysis (P6-C) — see Priority 6
above, rebased onto the Priority 5 branch and merged in second. None of these needed external
hardware or a live third-party system, so unlike the Section 3 "Where We Trail Enterprise" gaps
they shipped as full, non-simulated implementations. 41 features shipped total.

**Status update (2026-07-10):** shipped three more highest-ROI items: benefits management (P7-A),
regulatory compliance templates (P7-B) — closing out Quality Management's domain table entirely —
and workforce analytics & headcount planning (P7-C), which also added the app's first
hire-date/termination-date tracking. See Priority 7 above. 44 features shipped total. The only
gaps left anywhere in this document are Section 3's "Where We Trail Enterprise" table (real
external-connectivity/hardware dependencies), Applicant Tracking/Recruiting (ATS, the last item
in HR/Payroll), and Configure-to-Order/recipe-formula-management/repetitive-manufacturing
(Production Planning), Supplier Self-Service Portal (Purchasing), Technician Routing/Asset
Performance Management (Maintenance), and Batch Record Generation (Reporting) — the remaining
lower-ROI domain gaps not yet scheduled.

**Status update (2026-07-10, later same day):** shipped Applicant Tracking/Recruiting (ATS,
P8-A), closing HR/Payroll & Personnel's domain table entirely — its `convert_to_employee`
function ties directly into the hire_date column P7-C added earlier the same day, so a candidate
hired through the ATS is immediately counted correctly by Workforce Analytics. 45 features
shipped total. HR/Payroll & Personnel and Quality Management are now the only two Section 1
domain tables with zero remaining ❌ rows. The gaps still open: Section 3's "Where We Trail
Enterprise" table (real external-connectivity/hardware dependencies), and four real,
buildable-without-hardware domain gaps not yet scheduled — Configure-to-Order/recipe-formula-
management/repetitive-manufacturing (Production Planning), Supplier Self-Service Portal
(Purchasing), Technician Routing/Asset Performance Management (Maintenance), and Batch Record
Generation (Reporting).

**Status update (2026-07-10, one more):** shipped the Supplier Self-Service Portal (P9-A),
closing Purchasing & Procurement's domain table entirely — built as a structural mirror of the
customer portal (P3-C), reusing `purchase_orders_core`/`accounting_core`/`rfq_core` throughout
rather than forking any of them. 46 features shipped total. Three of ten Section 1 domain tables
(HR/Payroll & Personnel, Quality Management, Purchasing & Procurement) now have zero remaining ❌
rows. The gaps still open: Section 3's "Where We Trail Enterprise" table (real
external-connectivity/hardware dependencies), and three real, buildable-without-hardware domain
gaps not yet scheduled — Configure-to-Order/recipe-formula-management/repetitive-manufacturing
(Production Planning), Technician Routing/Asset Performance Management (Maintenance), and Batch
Record Generation (Reporting).

**Status update (2026-07-10, one more still):** shipped the last three Production Planning &
Scheduling gaps together — Configure-to-Order (P10-A), Recipe/Formula Management (P10-B), and
Repetitive Manufacturing (P10-C) — closing that domain table entirely. See Priority 10 above.
49 features shipped total. Four of ten Section 1 domain tables (HR/Payroll & Personnel, Quality
Management, Purchasing & Procurement, Production Planning & Scheduling) now have zero remaining
❌ rows. The only gaps left anywhere in this document: Section 3's "Where We Trail Enterprise"
table (real external-connectivity/hardware dependencies), and two real, buildable-without-hardware
domain gaps not yet scheduled — Technician Routing/Asset Performance Management (Maintenance) and
Batch Record Generation (Reporting).

**Status update (2026-07-10, final):** shipped the last three items anywhere in this roadmap —
Technician Routing & Scheduling (P11-A), Asset Performance Management (P11-B), and Batch Record
Generation (P11-C) — closing both Maintenance and Reporting & Analytics entirely. See Priority 11
above. 52 features shipped total. **Every domain table in Section 1 now has zero remaining ❌
rows.** The only gap left anywhere in this document is Section 3's "Where We Trail Enterprise"
table — real external-connectivity/hardware dependencies (broader embedded-AI analytics, real
IoT/sensor/RFID hardware, real carrier-API tracking, real AS2/EDI transport, a live e-commerce
storefront) that this dev environment has no live counterpart for, and which every affected
feature (predictive maintenance, RFID, EDI, e-commerce) already ships real logic behind an
honestly-scoped manual/simulated stand-in for, rather than faking the missing hardware/system
outright.

**Status update (2026-07-10, actually final):** shipped the broader embedded-AI analytics platform
(P12-A) — the one item in Section 3's "Where We Trail Enterprise" table that didn't actually need
real external hardware/connectivity, just effort. `ai_insights_core.py` unifies the existing
predictive-maintenance and APM risk reports with three new hand-rolled statistical detectors
(demand anomaly, quality anomaly, customer churn risk) into one severity-ranked feed at
`/ai-insights/`. 53 features shipped total. **The only gaps left anywhere in this document are the
four remaining rows of Section 3's "Where We Trail Enterprise" table, every one of which requires a
real external account or hardware this dev environment has no live counterpart for** (real
IoT/sensor/RFID hardware, real carrier-API tracking, real AS2/EDI transport, a live e-commerce
storefront) — each already ships real logic behind an honestly-scoped manual/simulated stand-in
rather than faking the missing system outright.

---

*This document is maintained in the repository at `manufacturing/COMPETITIVE_GAP_ANALYSIS.md`.*
*Update this file as features are added to track progress against the roadmap.*

---

## Section 6: 2026-07-17 Fresh Pass — Platform & Competitive Dimensions Beyond Section 1

**Why this pass exists:** the 2026-07-10 status line at the top of this document is accurate —
every Section 1 domain table genuinely has zero remaining ❌ rows, and the four items left in
Section 3 ("Where We Trail Enterprise") all require external hardware or accounts (IoT/RFID
readers, a carrier-API credential, a live AS2/EDI trading partner, a live e-commerce storefront)
that this dev environment doesn't have and the owner has confirmed he can't get. Re-running
Section 1's feature tables would reproduce a result the owner already knows. Instead, this pass
does two things: (1) spot-verifies a sample of prior "✅ Full" claims directly against the running
codebase rather than trusting the document's own prose, and (2) scores this app against **platform-
level dimensions top-10 ERP vendors compete on today that no part of this document has ever scored**
— frontend architecture, SSO, RBAC granularity, GDPR-style data governance, vertical compliance
depth, integration/webhooks, low-code workflow tooling, notifications, mobile breadth, offline
support, localization, observability, and load-testing maturity. Every claim below is grounded in a
specific file/line actually read this session — nothing here is inferred from the document's own
narrative.

### 6.0 Spot-check: does Section 1's "✅ Full" hold up?

Ten claims were checked directly against code (module exists, is wired to a URL, and is reachable
from somewhere a user would actually click), spanning Production, Purchasing, Quality, Finance,
Sales, Maintenance, and Reporting:

| # | Claim checked | Verified? | What was actually read |
|---|---|---|---|
| 1 | Configure-to-Order / Recipe / Repetitive Mfg (1.1) are "Full" | ✅ Holds | `cto_core.py`/`recipe_core.py`/`repetitive_core.py` all have URL routes in `manufacturing/urls.py` (`/cto/`, `/recipes/`, `/repetitive/...`) **and** are linked from `manufacturing/templates/prod_dashboard.html` — reachable, not orphaned code. None of the three appear in `views.WEB_LEAF_URLS` (the menu-tree resolution path CLAUDE.md describes as the *only* one) — like the ESS portal before them, they're reached via a direct dashboard button instead, a precedent this same document already disclosed for P2-G. Worth a documentation note: CLAUDE.md's claim that `WEB_LEAF_URLS` is the department menu's "only resolution path" is true for the *menu tree* but several 2026-07-10 features are deliberately outside that tree entirely. |
| 2 | Technician Routing (1.8) / APM (1.8) / Batch Record Generation (1.10) are "Full" | ✅ Holds | `/maint/routes/` linked from `maint_dashboard.html`; `/maint/apm/` linked from `maint_dashboard.html`; `/batch-records/` linked from `prod_dashboard.html` (line 9: `<a href="/batch-records/" class="btn">Batch Records</a>`). All reachable. |
| 3 | Discount/Promotion Mgmt (1.5), What-If Scenario Planning (1.1), ABC Costing (1.6), Regulatory Compliance Templates (1.3) are "Full" | ✅ Holds | Wired under different URL prefixes than their module names (`/promotions/`, `/scenarios/`, `/gl/abc-costing/`, `/qa/compliance/templates/` — `manufacturing/urls.py` lines 94-96, 353-356, 361-367, 372-378) and each has a template linking to it (`pl_list.html`/`so_list.html` → promo; `capacity_planning.html` → scenario; `finance_dashboard.html` → abc). Confirms the doc is accurate, but also confirms a real methodology risk: matching module names against `urls.py` alone produces false negatives, since several features are wired under a business-facing route name, not their module name. |
| 4 | FIFO/LIFO/Weighted-Average Costing (`costing_layers_core.py`, P3-I, 1.2) is "Full" | ✅ Holds | Wired as `/inventory/valuation/` (`costing_valuation_list`) and `/inventory/<id>/valuation/`, linked from `inventory_dashboard.html` and present in `WEB_LEAF_URLS` as `('production', 'cost_valuation')`. Real logic confirmed: `costing_layers_core.py` has genuine `_consume_fifo`/`_consume_lifo`/`_consume_average` implementations, not stubs. |
| 5 | Regulatory Compliance Templates (1.3) — "seeded starter templates are illustrative, not certified or exhaustive" | ✅ Holds, and worth restating for §6.5 below | `manufacturing/regulatory_compliance_core.py` seeds exactly two templates: `'ISO 9001:2015 Quality Management System (starter)'` and `'FDA 21 CFR Part 820 Quality System Regulation (starter)'`. No AS9100, IATF 16949, or GxP/21 CFR Part 11 content anywhere in the file or in `seed_sample_quality.py`. The doc's own hedge is accurate — this is a generic checklist engine with two illustrative seeds, not vertical compliance depth. |
| 6 | e-Commerce inbound webhook (P4-E, 1.5) is "real, verified" | ✅ Holds | `manufacturing/ecommerce_core.py` has a real `verify_webhook_signature` (Shopify HMAC-SHA256 / WooCommerce signature) and `receive_order_webhook` with dedupe against `ecommerce_order_log` — genuine signature-checked code, not a stub that always returns success. |
| 7 | "Full audit trail (old/new values by user/timestamp)" (1.10, and the Executive Summary's "matches SAP/Oracle/Dynamics enterprise level" claim) | ✅ Holds, and better than expected | `manufacturing/audit_core.py` installs real PostgreSQL `AFTER INSERT OR UPDATE OR DELETE` triggers (`install_triggers`) on 29+ tables (`AUDITED_TABLES`), including `people` and `user_roles` — meaning role/permission changes on a person **are** already captured with old/new JSONB values, which directly informs §6.3 below (this is a genuine, unscored positive that the document never explicitly credited toward RBAC). |
| 8 | Cycle Count (P1-D) / Document Control (P2-F) "fails open... no admin UI yet" for `approval_rule` | ✅ Holds, and generalizes further than the doc states | Grepped every caller of `create_approval_rule`/`update_approval_rule` across `manufacturing/views/*.py` and `manufacturing/seeds/*.py`: the **only** caller anywhere in the codebase is `manufacturing/seeds/seed_sample_operations.py:429`. This isn't just true for cycle-count/document-control specifically (as the doc states in those two sections) — it's true for **every** entity type the approval engine supports (PO, PR, GL journal, cycle count, document, etc.). There is no admin screen anywhere to create or edit an approval rule; it's a seed-script/direct-SQL-only concern app-wide. This is a real, previously-under-stated gap, expanded on in §6.7. |
| 9 | "Live shop floor performance (real-time)" (1.10, P3-G) | ✅ Technically accurate, mechanism worth naming | `manufacturing/templates/sf_tv.html` line 5: `<meta http-equiv="refresh" content="30">`. The doc already says "auto-refreshing TV display," which is honest — but it's a 30-second full-page reload, not a push/websocket update, which matters directly for §6.1 below. Not a correction, just the concrete mechanism behind an already-honest claim. |
| 10 | Testing maturity — assumed (going in) that only unit tests exist, no load/perf testing | ❌ This assumption was wrong — corrected here | `scripts/loadtest/locustfile.py` is a real Locust load-test script (`git log` shows it landed in commit `514c226`, "Phase 3: add load testing (locust)") simulating logged-in browsing across dashboard/WO/inventory/PO/SO/QA pages, plus `scripts/loadtest/run.sh` and `locust==2.45.0` in `requirements-dev.txt`. It is **not** wired into any GitHub Actions workflow (checked `.github/workflows/tests.yml`, `ruff.yml`, `docker-build.yml` — no `locust` reference in any of them), so it's a real but manual-only tool, never run in CI. This document has never mentioned this file; see §6.13. |

**Net result of the spot-check: no over-claimed features were found.** Every "✅ Full" sampled was
real, wired, and reachable. The one correction is to my own starting assumption about load testing
(item 10), not to the document.

### 6.1 Modern Frontend / Real-Time UX

| Feature | Us | Top 10 |
|---|---|---|
| Component-based / reactive frontend (SPA or islands) | ❌ — 100% server-rendered Django templates + vanilla JS; no React/Vue/Angular/htmx/Alpine anywhere in `manufacturing/templates/` or a root `package.json` (only `mobile/package.json` exists, for the separate React Native app) | ✅ 9/10 (SAP Fiori, Oracle Redwood, Dynamics' Power Apps/React-based UI, Epicor Kinetic, Infor Mingle/CloudSuite, Plex are all modern reactive web UIs; only MRPeasy-tier tools stay closer to classic server-rendered forms) |
| Live data without a page reload (websocket/SSE/polling-driven partial update) | ❌ — grepped for `websocket`, `django-channels`, `EventSource`, `htmx` across templates and `requirements*.txt`: zero hits. The one page marketed as "live" (`sf_tv.html`, the shop-floor TV display from P3-G) is a `<meta http-equiv="refresh" content="30">` full-page reload, not a partial live update | ✅ 7/10 have real push/live-refresh dashboards (SAP, Oracle, Dynamics, Plex's real-time shop floor); mid-market tools vary |
| Mobile-responsive web layout | ✅ Partial — Bootstrap-based templates render acceptably on phones but there's no distinct mobile-web breakpoint strategy beyond the framework defaults | ✅ All |

**Assessment:** this is the single most visible gap in any live demo against a modern competitor.
Every top-10 vendor's current web UI is a reactive SPA with live-updating widgets; this app is
architecturally committed to full-page Django template renders. This isn't necessarily wrong for a
mid-market on-prem tool (it's simpler to maintain, no build pipeline, no JS framework churn), but
it is the thing a buyer evaluating against Epicor Kinetic or Dynamics 365 side-by-side will notice
in the first five minutes. **What it would take:** the honest options are (a) introduce `htmx` for
partial-page updates on the highest-traffic dashboards/lists — a small, incremental addition that
doesn't require a SPA rewrite and matches this app's "no heavy JS framework" convention, or (b) add
a lightweight polling-based live-refresh (a `setInterval` + `fetch()` partial DOM swap) to the 5-6
dashboard pages that most need it (production, maintenance, shop-floor TV, AI Insights). A full SPA
rewrite is not proportionate to this codebase's size or the owner's stated priorities.

### 6.2 Enterprise Auth / SSO

| Feature | Us | Top 10 |
|---|---|---|
| SAML 2.0 / OAuth2 / OIDC SSO (Azure AD, Okta, Google Workspace) | ❌ — `manufacturing/accounts.py` `_verify_login` (lines 105-134) checks `bcrypt.checkpw` against a plain `passwd` table; grepped for `saml`, `oauth`, `openid`, `social_auth`, `allauth` across every `.py` file and `requirements*.txt` — zero hits anywhere in the app (only unrelated substring matches in `edi_core.py`/`maintenance_core.py` comments) | ✅ 10/10 — SSO is table-stakes for every enterprise/mid-market ERP buyer today; every one of the ten named competitors supports SAML/OIDC federation |
| Multi-factor authentication | ✅ Partial — TOTP 2FA exists but only for the mobile REST API (`manufacturing/api_auth.py`: `generate_totp_secret`/`verify_totp_code`/`set_totp_secret`), not for the web login flow in `accounts.py` | ✅ 9/10 |
| Password policy / rotation enforcement | ❌ — no password complexity check, expiry, or history found in `accounts.py` beyond bcrypt storage | ✅ 8/10 |

**Assessment:** this is a real, unscored, and significant enterprise gap — no top-10 buyer's IT
department will accept plain email+password with no SSO option for a system touching payroll,
finance, and HR data. **What it would take:** adding `django-allauth` (or a hand-rolled OIDC client
against `authlib`) for at least one identity provider (Azure AD / Google Workspace cover the large
majority of buyers), mapping the IdP's group/role claims onto the existing `user_dept_key`/
`user_role` session keys so `dept_required`/`role_required` continue working unchanged. Extending
the existing mobile TOTP 2FA to the web login path is a smaller, faster win that reuses code
already in `api_auth.py`.

### 6.3 Granular RBAC / Field-Level Permissions

| Feature | Us | Top 10 |
|---|---|---|
| Whole-view gating by department + role | ✅ Full — `manufacturing/auth_decorators.py`: `dept_required(dept_keys, *, role_keys=None, write_redirect=None)` and `role_required` gate entire views; full-access roles (President/VP) bypass | ✅ All |
| Row-level permission control (e.g., a rep sees only their own accounts) | ❌ — no row-level filter mechanism found anywhere in `auth_decorators.py`; the closest analog is ESS's manual per-view ownership check (`people_id` compared against the caller's own), which is a one-off pattern hand-copied per view, not a reusable row-level security layer | ✅ 6/10 (SAP/Oracle/Dynamics have real row-level security; mid-market tools vary) |
| Field-level permission control (e.g., hide salary field from non-HR roles within a shared view) | ❌ — none found | ✅ 5/10 |
| Audit-logged permission/role changes | ✅ Full, and previously uncredited — `manufacturing/audit_core.py`'s `AUDITED_TABLES` list includes `'people'` and `'user_roles'` (lines 50-51), and `install_triggers` attaches a real `AFTER INSERT OR UPDATE OR DELETE` PostgreSQL trigger to both. A change to someone's role is captured with full old/new JSONB values in `audit_log`, queryable via `audit_core.get_history('user_roles', id)` | ✅ 8/10 |

**Assessment:** this is a genuine mixed picture the document has never scored. The gating model is
coarse (dept + role, whole-view) with no row- or field-level control, but permission/role *changes*
themselves are already captured by the generic DB-trigger audit trail — a real strength this
document's Section 1 audit-trail row never connected to the RBAC question. **What it would take**
for row-level: a reusable helper (e.g. `owned_by_filter(queryset_or_sql, request)`) generalizing the
ESS ownership-check pattern, rather than one-off checks per view. Field-level masking would need a
small per-template convention (e.g. a `{% if_can_view field %}` templatetag backed by a
role→field-visibility table) — there is no such mechanism today.

### 6.4 Data Governance / GDPR-Style Tooling

| Feature | Us | Top 10 |
|---|---|---|
| Right-to-erasure / data deletion for a data subject | ❌ — grepped `personnel_core.py` for any `delete_person`/`deactivate_person`/`remove_person` function: none exist. There is no way to delete or scrub a person's PII anywhere in the app | ✅ 6/10 (formal GDPR toolkits are common in SAP/Oracle/Dynamics; smaller vendors vary) |
| Subject data export ("give me everything you have on me") | ❌ — the existing CSV/Excel export (P1-B/P1-G) is a list-level report export, not a per-subject compiled export across tables | ✅ 5/10 |
| PII field tagging / classification | ❌ — no PII metadata, tagging, or masking mechanism found anywhere in `schema.py` or `*_core.py` | ✅ 5/10 |
| Data retention policy engine (auto-purge after N years) | ❌ — none found; no scheduled purge job beyond `api_auth.py`'s `purge_old_attempts` (which is a security rate-limit table, not a PII retention policy) | ✅ 5/10 |
| Soft-delete pattern for auditability of deletions | ❌ — grepped for `is_deleted`/`deleted_at`/soft-delete conventions app-wide: the only hit is a code comment in `scenario_planning_core.py` explicitly noting deletes there are "plain cascade-by-hand," not soft | — |

**Assessment:** genuinely zero data-governance tooling exists — not partial, not stubbed, simply
absent. This tracks with the app's overall design (it was built feature-by-feature against
functional ERP gaps, not compliance-officer requirements) but it is a real, buildable-in-software
gap that would matter to any EU-facing buyer or any US buyer selling into the EU. **What it would
take:** a `data_governance_core.py` with (1) a `delete_person`/anonymize path that overwrites PII
columns on `people` while preserving FK-referenced history rows (name → "Redacted", email → a
placeholder), consistent with how this codebase already treats deletion elsewhere (mostly avoided
in favor of status flags); (2) a per-subject export view joining `people` against every table that
references `people_id`; (3) a `retention_policy` table + a scheduled command modeled directly on
`send_daily_digest`'s existing management-command pattern.

### 6.5 Industry-Vertical Compliance Packs

| Feature | Us | Top 10 |
|---|---|---|
| Generic ISO/FDA compliance checklist engine | ✅ Full (already scored in 1.3, P7-B) — confirmed real: `regulatory_compliance_core.py` snapshots a reusable checklist template into a per-audit instance | ✅ All |
| AS9100 (aerospace) specific content/depth | ❌ — no mention anywhere in `regulatory_compliance_core.py` or its seed data | ✅ 4/10 (Epicor, Infor, SAP have named aerospace compliance modules or partner content; most mid-market tools don't either) |
| IATF 16949 (automotive) specific content/depth | ❌ — none found | ✅ 4/10 (Plex is automotive-native and IATF-aligned out of the box; others need partner add-ons) |
| GxP / 21 CFR Part 11 electronic signatures (signed meaning, re-authentication at sign time) | ❌ — grepped `document_control_core.py` and `approval_workflow_core.py` for `signature`/`esign`: zero hits. Approvals are a role-based click (`decide_step`), not a compliant e-signature (no re-entered password, no "meaning of signature" capture) | ✅ 5/10 (SAP/Oracle/Dynamics and several mid-market vendors offer certified Part-11 e-signature modules for pharma/medical customers) |

**Assessment:** the existing compliance engine is exactly what its own docstring says — a generic,
illustrative checklist tool with two starter templates, not vertical depth. This matches the
document's own honest framing and isn't a correction, but it's worth scoring explicitly since
"generic ISO/FDA templates" and "AS9100/IATF/GxP depth" are different competitive claims that top-10
marketing decks distinguish sharply. **What it would take:** vertical template content (AS9100/
IATF 16949 are themselves just more checklist rows — cheap to seed) is low-effort; a real Part-11
e-signature (password re-entry + a captured "meaning of signature" string per `approval_step`
decision) is a moderate, contained addition to the existing `decide_step` function.

### 6.6 Integration Platform / Webhooks / API Marketplace

| Feature | Us | Top 10 |
|---|---|---|
| REST API for custom integration | ✅ Full (already scored in 1.10) — `manufacturing/api_views.py`, `/api/v1/...`, used by the mobile app | ✅ All |
| Inbound webhook receiver | ✅ Full (already scored in 1.5, P4-E) — `ecommerce_core.py`'s signature-verified Shopify/WooCommerce order webhook | ✅ All |
| **General-purpose outbound webhook system** (notify a third party on any business event — PO approved, WO completed, NCR opened, etc.) | ❌ — grepped `webhook` across the whole codebase: the only outbound HTTP calls are the e-commerce-specific `push_inventory_level`/`push_price_update` functions in `ecommerce_core.py`, scoped only to that one integration, not a general subscribable event bus | ✅ 7/10 (Dynamics/SAP/Oracle/Epicor all offer a general webhook or event-subscription mechanism) |
| Published API docs (OpenAPI/Swagger) or a self-serve API/developer portal | ❌ — grepped for `swagger`, `openapi`, `drf_yasg`, `drf-spectacular`: zero hits; no API docs page found in `manufacturing/templates/` | ✅ 6/10 |
| Per-endpoint API rate limiting | ❌ Partial — `api_auth.py`'s `is_rate_limited`/`record_login_attempt` only guard the **login** endpoint; no throttling exists on any other `/api/v1/...` endpoint | ✅ 7/10 |

**Assessment:** the REST API and inbound webhook are real and already credited elsewhere in this
document — that part of the story is accurate. What's missing and unscored is the *outbound*,
general-purpose side: nothing in this app can notify an external system ("Zapier, a customer's own
ERP, a Slack channel") when an arbitrary business event happens, and there's no public API
documentation surface a third-party integrator could self-serve from. **What it would take:** a
`webhook_subscription(event_type, target_url, secret)` table plus a small dispatch helper called
from the handful of places that already change entity status (WO/PO/SO status-change functions,
NCR creation) — the same "hang a new capability off an existing state-transition function" pattern
this codebase already uses everywhere (e.g. inventory transactions on receive/ship). Auto-generating
OpenAPI docs from `api_views.py`'s existing `@api_required`-decorated functions via
`drf-spectacular`-style introspection (or even a hand-written docs page) is comparatively cheap.

### 6.7 Low-Code / Workflow Customization

| Feature | Us | Top 10 |
|---|---|---|
| Reusable, generic approval/workflow engine (in code) | ✅ Full — `approval_workflow_core.py`'s `ENTITY_TYPES` already spans `purchase_order`, `purchase_requisition`, `gl_journal`, `cycle_count`, `document`, and more; genuinely reusable, not forked per domain | ✅ All |
| **Admin UI to create/edit workflow rules without a developer** | ❌ — confirmed by grep: `create_approval_rule`/`update_approval_rule` are called from exactly one place in the entire codebase, `manufacturing/seeds/seed_sample_operations.py:429`. No view in `manufacturing/views/*.py` ever calls either function. An org wanting a new approval rule for any entity type must have a developer insert a row directly (or extend the seed script) — there is no self-service path at all, for any of the entity types, not just the two the document already flagged this for (cycle count, document control) | ✅ 7/10 (Dynamics Power Automate, SAP Business Workflow/BTP, Oracle Process Cloud, Infor ION Workflow all ship a visual rule/workflow builder a business admin can use directly) |
| General-purpose business-rule engine (beyond approvals — e.g. configurable validation/automation rules) | ❌ — no such engine found; every business rule (MRP logic, costing, ATP, discount resolution) is hardcoded Python in its respective `*_core.py` module | ✅ 6/10 |

**Assessment:** this is a real, previously under-stated gap. The document credits the approval
engine's *code*-level genericness (correctly), but never flagged that its *configuration* path is
entirely developer/seed-script-only, with zero admin UI anywhere — this is true across the whole
app, not just the two places the document happened to mention it in passing. **What it would take:**
an `/approval-rules/` CRUD screen (list/new/edit) over the existing `approval_rule` table —
genuinely low effort since `create_approval_rule`/`update_approval_rule`/`delete_approval_rule`
already exist and work; this is a pure UI-wiring gap, not a missing-logic one. A full low-code
business-rule engine (beyond approvals) is a much larger, lower-ROI undertaking not worth pursuing
before the cheap admin-UI win above.

### 6.8 Notifications / Alerting Engine

| Feature | Us | Top 10 |
|---|---|---|
| Scheduled email digest | ✅ Partial (already scored in 1.10) — `manufacturing/management/commands/send_daily_digest.py`, confirmed real: builds `reports_core.daily_digest_text` and either emails it or prints to stdout | ✅ 7/10 |
| Transactional email on specific events (PO approval step) | ✅ Partial — `manufacturing/notify_core.py` sends email specifically for the PO approval workflow | ✅ 8/10 |
| **In-app real-time notification center** (bell icon, unread count, per-user feed) | ❌ — grepped for `Notification`/`notification_center`/a `CREATE TABLE ... notification` anywhere: zero hits beyond the two email-only mechanisms above. There is no persisted, in-app notification model at all | ✅ 8/10 |
| Push notifications to the mobile app | ❌ — no push-notification SDK (Expo Notifications, FCM/APNs) referenced in `mobile/package.json` or `mobile/app/` | ✅ 7/10 |

**Assessment:** every "notification" in this app today is either a scheduled batch email or a
single-purpose transactional email tied to one workflow (PO approval). There's no unified,
persisted, in-app notification concept a user could open and see "5 unread" for across NCRs,
approvals-pending-your-decision, low-stock alerts, etc. — despite plenty of individual signals
already existing (`approval_workflow_core.get_pending_steps`, inventory reorder alerts, NCR
creation) that a notification center would just need to fan into one feed. **What it would take:**
a `notification(people_id, type, entity_type, entity_id, message, read_at, created_at)` table, a
small `notify_core.create_notification()` helper called from the handful of places that already
know "someone needs to act on this" (approval step creation, low-stock breach, NCR assignment), and
a bell-icon partial in `base.html` polling `/api/notifications/unread-count/` every 30-60s — the
same lightweight polling this document already uses elsewhere (`sf_tv.html`), not a new
architecture pattern.

### 6.9 Mobile App Coverage

`manufacturing/` has **17 department subpackages**: `accounting`, `customer_service`, `customers`,
`engineering`, `finance`, `it`, `legal`, `maintenance`, `marketing`, `payroll`, `personnel`,
`production`, `purchasing`, `quality`, `reports`, `sales`, `time_clock`. `mobile/app/(tabs)/` has
**9 screens**: `index` (dashboard), `time-clock`, `work-orders`, `requisitions`, `approvals`,
`inventory`, `lots`, `maintenance`, `quality`, `costing` (plus `(auth)/login`).

| Department | Mobile coverage |
|---|---|
| time_clock | ✅ dedicated screen |
| production (work orders, inventory, lots, costing) | ✅ dedicated screens (4) |
| maintenance | ✅ dedicated screen |
| quality | ✅ dedicated screen |
| purchasing | ✅ Partial — requisitions + approvals screens only (no PO list/detail, no RFQ, no supplier scorecard) |
| accounting, customer_service, customers, engineering, finance, it, legal, marketing, payroll, personnel, sales | ❌ **zero mobile screens** |

**11 of 17 departments (65%) have no mobile presence at all.** This is a real, quantifiable,
previously-unscored gap — CLAUDE.md's own mobile section lists the screens accurately, but this
document has never stated the gap in terms of department coverage. Compared to top-10 vendors: most
ship either a single universal mobile app covering most modules (Dynamics 365, SAP Fiori mobile,
Oracle) or dedicated apps per persona (warehouse/plant floor apps, ESS apps) that still net out to
broader coverage than 6/17 departments — score **7/10** of the top 10 have materially broader
mobile breadth. **What it would take:** the existing REST API (`api_views.py`) already has
Financial/Production/Inventory dashboard endpoints per CLAUDE.md's own inventory of routes, so the
gap for at least a read-only Sales/Finance/HR mobile view is mobile-app screen work, not new backend
API surface — the ROI-ordered list at the end of this section reflects that. **Correction
(2026-08-28):** this held for Finance (a mobile screen shipped reusing the existing endpoint
verbatim) but not for Sales — there was no `/api/v1/...` sales route of any kind, so that one
needed genuinely new backend work too. See the dated log at the end of the document for both.

### 6.10 Offline Support

| Feature | Us | Top 10 |
|---|---|---|
| Mobile app offline data caching / sync queue | ❌ — `mobile/app/_layout.tsx` and `mobile/src/api/client.ts` only use `AsyncStorage` to persist the `api_token`/`api_user` session; grepped the whole `mobile/` tree for `NetInfo`, offline queueing, or a local SQLite/WatermelonDB store: none found. Every screen requires a live connection to `EXPO_PUBLIC_API_URL` | ✅ 5/10 (Dynamics Field Service, SAP mobile apps, and Oracle field apps support real offline-first sync; several mid-market vendors' mobile apps are online-only too) |
| Web UI offline support (service worker / PWA) | ❌ — no service worker, manifest, or PWA config found anywhere in `manufacturing/templates/` or `manufacture/settings.py` | ✅ 3/10 |

**Assessment:** a plant-floor worker or field technician with a dead connection gets a blank screen
in this app's mobile client, no cached fallback. Not universal among competitors either (many are
online-only too), but it's a real gap worth naming rather than assuming away. **What it would take:**
non-trivial — a proper offline-first mobile architecture (local SQLite cache + a sync/conflict-
resolution layer) is a substantial rewrite of the mobile data layer, not a quick add; this is
correctly a lower-priority item relative to the other gaps in this section.

### 6.11 Multi-Language / Localization

| Feature | Us | Top 10 |
|---|---|---|
| Any UI translation / i18n in active use | ❌ — grepped every template for `{% trans %}`/`{% blocktrans %}`/`{% translate %}`: **zero** matches across the entire `manufacturing/templates/` tree. Grepped all `.py` files for `gettext`/`ugettext`: zero matches. No `.po`/`.mo` files exist anywhere in the repo | ✅ 10/10 — every one of the ten named competitors ships localized UI in dozens of languages as standard |
| Django i18n scaffolding present | ✅ Partial, unused — `manufacture/settings.py` has `LANGUAGE_CODE = 'en-us'` and `USE_I18N = True`, but these are Django's stock project-template defaults, not evidence of active localization; no `LocaleMiddleware` in `MIDDLEWARE`, no `LOCALE_PATHS` | — |

**Assessment:** this app is English-only, full stop — not "partially localized," genuinely zero
translation infrastructure in active use despite Django's i18n flag technically being on. For a
buyer comparing against SAP/Oracle/Dynamics (all localized to 40+ languages) this is a hard
disqualifier for any multinational deployment, though largely irrelevant for a single-site,
English-speaking SMB buyer — which is this app's actual competitive lane against Fishbowl/JobBOSS²/
MRPeasy (also effectively English-first tools). **What it would take:** wrapping every user-facing
string in `{% trans %}` across ~150+ templates is a large, mechanical effort with real ongoing
translation-maintenance cost — reasonable to leave unscheduled unless a specific non-English-market
deal requires it.

### 6.12 Observability / Ops Maturity

| Feature | Us | Top 10 |
|---|---|---|
| Structured application logging | ✅ Full, previously uncredited — `manufacturing/log_utils.py`'s `get_logger()` plus `manufacture/settings.py`'s `LOGGING` dict (lines 228-254) give every module a consistent formatter, `LOG_LEVEL`/`LOG_FILE` env-driven configuration, and separate `django`/`manufacturing` logger namespaces | ✅ All |
| Error tracking / APM integration | ✅ Full, previously uncredited — `manufacture/settings.py` lines 274-295: real, working `sentry_sdk` integration, opt-in via a `SENTRY_DSN` env var (so CI/dev never talk to Sentry), `DjangoIntegration`, configurable `SENTRY_ENVIRONMENT` and `SENTRY_TRACES_SAMPLE_RATE` (defaults to `0`) | ✅ 8/10 |
| Health-check endpoint (`/healthz`, `/ping`, readiness/liveness) | ❌ — grepped `manufacturing/urls.py` for `health`/`ping`/`status/`/`readiness`/`liveness`: no dedicated health endpoint exists (the `status/` hits found are all entity-status-change routes like `/wo/<id>/status/`, unrelated) | ✅ 7/10 |
| Uptime/SLA tooling | ❌ — n/a for a self-hosted Django app in this dev environment; not applicable in the same way it is for a SaaS vendor | — |

**Assessment:** genuinely better than a first guess would suggest — structured logging and a real,
correctly-opt-in Sentry integration already exist and were never credited anywhere in this
document. The one real, concrete, cheap gap is a health-check endpoint, useful for any container/
load-balancer deployment (relevant given `.github/workflows/docker-build.yml` exists). **What it
would take:** a single `path('healthz/', views.healthz)` returning `200 {"status": "ok"}` after a
trivial `SELECT 1` against `get_db_connection()` — this is close to a 15-minute addition, one of the
cheapest items in this entire section.

### 6.13 Testing / QA Maturity as a Competitive Signal

| Feature | Us | Top 10 |
|---|---|---|
| Unit test coverage on business logic | ✅ Full — 89 `test_*.py` files under `./tests`, all against Qt-free `*_core.py` modules per this app's own testing convention | ✅ Table stakes, not usually vendor-marketed |
| Load/performance testing | ✅ Partial, previously uncredited — `scripts/loadtest/locustfile.py` + `scripts/loadtest/run.sh` + `locust==2.45.0` in `requirements-dev.txt`; simulates realistic concurrent browsing (dashboard/WO/PO/SO/inventory/QA) and is explicitly designed to surface whether `db_pg.get_db_connection()`'s per-call-fresh-connection pattern bottlenecks under concurrency. Real and usable, but confirmed **not** wired into any CI workflow — a manual, on-demand tool only | — (not typically a customer-visible differentiator; matters more for the vendor's own confidence at scale) |
| CI-gated performance regression testing | ❌ — the load test above is never invoked by `.github/workflows/*.yml` | — |

**Assessment:** the app is in a materially better position here than the initial framing for this
pass assumed — real load-testing tooling already exists and specifically targets this codebase's
one known architectural risk (`get_db_connection()` under concurrency). It's just not automated.
**What it would take:** the cheapest real improvement is wiring `scripts/loadtest/run.sh` into a
manually-triggered (`workflow_dispatch`) GitHub Actions job against a throwaway Postgres service
container — not a full CI gate on every PR (too slow/costly for that), but at least a repeatable,
one-click way to run it that doesn't depend on a developer's local machine.

### Prioritized Buildable-in-Software Next Steps

Unlike Section 3's four hardware-gated items, everything below is pure software effort the owner
can actually pursue. Ranked by ROI (impact × how cheap the fix is given what already exists):

1. **Admin UI for approval rules** (§6.7) — the lowest-effort item in this entire section:
   `create_approval_rule`/`update_approval_rule`/`delete_approval_rule` already exist and work;
   this is purely a missing CRUD screen over an existing, tested backend. Unblocks self-service
   workflow configuration for every entity type at once (PO, PR, GL journal, cycle count,
   document control, and any future entity type), not just one feature.
2. **Health-check endpoint** (§6.12) — a ~15-minute addition (`/healthz/` + `SELECT 1`) that
   directly benefits the existing Docker build workflow and any real deployment behind a load
   balancer or container orchestrator.
3. **In-app notification center** (§6.8) — a single new table plus a helper function called from
   signals that already exist (pending approval steps, low-stock breach, NCR assignment) turns
   several already-computed "someone should look at this" facts into one visible, persisted feed —
   high perceived-modernness payoff for a contained build.
4. **General-purpose outbound webhook system** (§6.6) — extends the existing, real inbound
   webhook/signature-verification pattern from `ecommerce_core.py` to a general
   `webhook_subscription` table and dispatch helper hung off existing status-change functions;
   turns "has a REST API" into "has an integration platform," a distinction top-10 marketing
   decks draw explicitly.
5. **SSO (SAML/OIDC) for at least one identity provider** — the highest business-impact item on
   this list (a hard blocker for many enterprise IT-security reviews) but also the most build
   effort, since it touches the session/login path directly; sequenced last of the five for that
   reason, not because it matters least.

Row-level/field-level RBAC, GDPR erasure tooling, vertical compliance packs, and full i18n are all
real, honestly-scored gaps above but are lower-ROI relative to their effort for this app's actual
buyer profile (SMB/mid-market, single-language, single-tenant) and are deliberately left off this
top-5 list rather than padded in for volume.

---

**2026-07-17:** Shipped item 1 from the list above — the **Admin UI for approval rules** (§6.7).
`/approval-rules/` (list, filterable by entity type), `/approval-rules/new/`, and
`/approval-rules/<id>/` (edit, activate/deactivate, delete) now exist under the Admin sidebar
section, gated to full-access roles the same way User Roles and Currencies already are. No new
core logic was needed — `create_approval_rule`/`update_approval_rule`/`delete_approval_rule` were
already correct, just never called from a view; the one real addition was `get_approval_rule()`
(a single-row getter the edit page needs, which the CRUD surface was missing). Deleting a rule that
already has `approval_step` rows against it now surfaces the real FK-violation error rather than a
500, with deactivation offered as the safe alternative. **Found and worked around a real routing bug
while building this:** the obvious URL prefix, `/admin/approval-rules/`, silently redirects to
Django's own admin login, because `manufacture/urls.py` mounts `admin.site.urls` at `path('admin/',
...)` ahead of `manufacturing.urls`, and that catches every path under `/admin/` first. Verified this
is pre-existing and not new: `/admin/currencies/` — the *existing* Currency Management page — has the
exact same bug and is currently unreachable in the deployed app; left that as a separate,
already-there issue rather than folding an unrelated fix into this PR. Routed the new pages at
`/approval-rules/` instead (no `/admin/` prefix), consistent with every other cross-cutting config
page in this app (`/price-lists/`, `/sampling-plans/`, `/rfq/`). Verified end-to-end against a
running dev server via the Django test client: create/edit/deactivate/reactivate/delete all confirmed
working, non-admin roles confirmed redirected away without ever seeing the page content, and the
FK-violation-on-delete path confirmed to show a real error instead of crashing. Full suite: 2647
passed (2644 + 3 new tests for `get_approval_rule`), ruff clean.

**2026-07-17, later same day:** Shipped item 2 from the list above — the **health-check endpoint**
(§6.12). `GET /healthz/` (`manufacturing/views/_health.py`) runs a trivial `SELECT 1` through
`get_db_connection()` and returns `200 {"status": "ok"}`, or `503 {"status": "error", "detail":
...}` if the database call raises — the non-2xx status matters as much as the body, since that's
what a load balancer or container orchestrator actually keys its routing/restart decision on, not
JSON content. Deliberately unauthenticated (no session/login check) since the callers here are
infrastructure, not a logged-in user, unlike every other view in this app; restricted to `GET` via
`@require_GET` (confirmed `POST` returns 405). No `*_core.py` module or unit test was added —
there's no extractable business logic here to test Qt-free, consistent with this repo's convention
that the test suite covers `*_core.py` modules, not view glue. Verified via the Django test client
against the real dev DB (200 with no session, 405 on POST) plus the full suite (2647 passed, no
new tests since there's nothing core-level to add one for) and `ruff check .` clean. Not wired into
`.github/workflows/docker-build.yml` or a Dockerfile `HEALTHCHECK` instruction — the endpoint now
exists for whoever sets up the container/load-balancer config to point at, but that wiring is a
deployment-config change outside this repo's own test/lint loop, left for a follow-up.

**2026-07-17, one more:** Shipped item 3 from the list above — the **in-app notification center**
(§6.8). A `notification(people_id, type, entity_type, entity_id, message, read_at, created_at)`
table plus `notify_core.py` helpers (`create_notification`, `create_notifications_for_role`,
`create_notifications_for_dept`, `list_notifications`, `get_unread_count`, `mark_read`,
`mark_all_read`) back a bell icon in `base.html` (unread badge, dropdown feed, mark-read/mark-all
actions) polling `/notifications/unread-count/` every 45s via vanilla `fetch()` — the same
CSRF-token pattern `prod_schedule_gantt.html`'s drag-reschedule endpoint already established, not a
new one. Hung real notification creation off two existing choke points exactly as scoped: (1)
`approval_workflow_core.submit_for_approval()` now fans a notification out to every person holding
the relevant `approver_role` — a one-query `INSERT ... SELECT`, not an N+1 per person — the instant
a step is created, so **every** entity type this engine covers (PO, requisition, GL journal, cycle
count, document) gets this for free, not just PO which already had its own separate email-only
notice; (2) `inventory_core.record_transaction()` now detects the exact transaction that crosses a
product from above its reorder point to at-or-below it (`old_qty > reorder_point >= new_qty`,
computed from `delta` with no extra query) and notifies the Purchasing department once, at the
crossing — not on every subsequent transaction while it stays low, and never on a `receive` (which
can only move stock upward, so it can never trigger this by construction). Deliberately **did not**
wire NCR assignment (the third call site named in the original scoping) — confirmed `qa_ncr.owner`
is a free-text `<input>` field, not a people_id FK, and fuzzy-matching a name string to a real
person to notify would be fragile in a way this app's own conventions elsewhere (e.g. workforce
analytics' hire-date exclusion) argue against; noted here as a real, deliberately-scoped gap rather
than silently dropped. **Found and fixed a real bug while verifying end-to-end:** the first
implementation let `submit_for_approval`/`record_transaction` write to the `notification` table
without ever ensuring it exists, which throws `UndefinedTable` on a fresh database the moment the
very first approval step or stock breach happens before anyone has ever loaded a page that
happened to ensure it — reproduced this exactly against the real dev DB, then fixed by calling
`ensure_notification_table()` at the point of writing in both integration points (guarded so it
only runs on the code path that's actually about to write, not on every call — confirmed via the
existing sequenced-mock test suite, which needed updating in four files —
`test_approval_workflow_core.py`, `test_phase4.py`, `test_cycle_count_core.py`,
`test_inventory_core.py` — for the added query, a normal consequence of a real behavior change to
an already-tested function, not a workaround). Verified end-to-end against the real dev DB via the
Django test client: an approval step for a real configured rule notified the correct Department
Manager (and only that person — a second manager's attempt to mark it read correctly returned
`false`); a real low-stock crossing on a live product notified the correct Purchasing-department
person with the right message; the bell icon renders when logged in and is absent when anonymous.
Full suite: 2669 passed (2647 + 22 new: 3 for `get_approval_rule` from the prior item plus 19 for
the new notification functions/behavior), `ruff check .` clean.

**2026-07-17, one more still:** Shipped item 4 from the list above — the **general-purpose
outbound webhook system** (§6.6). A new `webhook_core.py` adds `webhook_subscription(event_type,
target_url, secret, is_active)` + `webhook_delivery` (an audit log of every dispatch attempt,
mirroring `ecommerce_core.py`'s own `ecommerce_sync_log` for its outbound pushes) and a
`dispatch_event(conn, event_type, entity_type, entity_id, extra=None)` helper. Event types follow
a dotted `"<entity>.<status>"` convention (`po.received`, `wo.completed`, `so.confirmed`,
`ncr.opened`, etc.) — Stripe/GitHub-style — so a subscriber picks exactly the transition it cares
about rather than every status change for an entity type. Hung real dispatch off all four
call sites the doc originally named: `work_orders_core.set_wo_status`,
`purchase_orders_core.set_po_status`, and `sales_orders_core.set_so_status` each fire
`f'{entity}.{new_status}'` for whatever status was just set (one line added right after each
existing `UPDATE`, no branching needed since every status is a valid event type), and
`quality_core.create_ncr` fires a fixed `ncr.opened`. Delivery itself reuses
`ecommerce_core.py`'s own established outbound pattern exactly: stdlib `urllib` (no new
dependency), a narrow `except (URLError, OSError)` around the network call so a transport failure
degrades to a logged `'failed'` delivery rather than raising, plus `dispatch_event`'s own outer
`except Exception` around subscription lookup and each per-subscriber delivery so a broken
subscriber (or a bug in the delivery-log write itself) can never break the real WO/PO/SO/NCR
transaction it's hung off of — the same fire-and-forget guarantee `notify_core.py`'s `_send`
already makes for email. Signed payloads reuse the exact same `base64(HMAC-SHA256(secret, body))`
scheme `ecommerce_core.verify_webhook_signature` already verifies on the *inbound* side, so a
subscriber built against this app's existing inbound-webhook documentation can verify outbound
deliveries with the same code. A new Admin-sidebar page (`/webhooks/` list + filter,
`/webhooks/new/`, `/webhooks/<id>/` edit/activate-deactivate/delete, with a live "Recent
Deliveries" panel per subscription) mirrors the approval-rule admin UI's exact structure and
full-access-only gating — without it, a webhook subscription would need direct database access to
create, the same self-service gap the approval-rule admin UI closed for approval config. **Did
not** build OpenAPI/Swagger docs or per-endpoint API rate limiting (the other two ❌ rows in this
section's table) — those are real, separately-scoped gaps, not part of this item.

Adding a real DB call to four already-tested, already-shipped functions meant updating five
existing test files whose fixtures assumed exact call counts or a specific "last SQL executed"
(`test_work_orders_core.py`, `test_purchase_orders_core.py`, `test_sales_orders_core.py`,
`test_quality_core.py`) — a normal, expected consequence of a real behavior change, exactly the
same kind of update the approval-rule and notification-center PRs already needed for
`submit_for_approval`/`record_transaction`. 27 new tests for `webhook_core.py` itself. Verified
end-to-end against the real dev DB: spun up a real local HTTP listener (Python's stdlib
`http.server`, no mocking), created subscriptions for all four event types through the actual
admin UI via the Django test client, then triggered a real WO/PO/SO status change and NCR creation
— all four fired, the listener received all four POSTs with correct payloads, and every
`X-Webhook-Signature` header verified correctly against the configured secret. Also confirmed the
delivery log renders on the subscription's edit page, non-admin roles are denied, and
toggle-active/delete work. Full suite: 2696 passed (2669 + 27 new), `ruff check .` clean.

**2026-07-17, last one:** Shipped item 5 from the list above — **SSO (OpenID Connect) for at
least one identity provider** (§6.2), closing out every item on the prioritized buildable-in-
software list. Before starting, checked with the owner whether real credentials existed for any
IdP (Azure AD, Google Workspace, Okta) to wire this up against for real — none did, so this was
built and verified the same honest way Section 3's hardware-gated items already are: real client
code, verified end-to-end against a locally-run stand-in, with only the discovery URL and client
credentials changing to point at a real provider later. New `sso_core.py` implements the full
Authorization Code flow against any spec-compliant OIDC provider — discovery-document fetch,
authorize-URL construction with `state`/`nonce`, code-for-token exchange, and RS256 ID-token
verification via the IdP's published JWKS. HTTP calls use stdlib `urllib` (no new dependency,
matching `ecommerce_core.py`/`webhook_core.py`'s existing convention); the one genuinely new
dependency is `joserfc` (RFC 7515/7517/7519 JWS/JWK/JWT) for the signature verification itself —
hand-rolling RSA signature checking instead of using an audited library would mean reimplementing
security-critical crypto, the wrong call even though this codebase otherwise avoids new
dependencies aggressively. **Identity vs. authorization, a deliberate scope decision:** SSO here
only proves *who* the user is (a verified email from the signed ID token); it does not attempt to
map arbitrary IdP group/role claims onto this app's `user_dept_key`/`user_role` session keys, since
that mapping is customer-tenant-specific configuration this dev environment has no real tenant to
verify against. Instead, the verified email is looked up in this app's own existing
`people`/`user_roles`/`dept` tables via the same `accounts._get_user_profile()` the password-login
path already uses — SSO replaces *how* identity is proven, not *where* authorization data lives. A
person must already exist in the app by email for SSO login to succeed; it does not provision new
accounts. New `/sso/login/` and `/sso/callback/` routes (`views/_sso.py`) set the exact same
session keys (`user_email`/`user_role`/`user_dept_key`/`user_dept_name`/`user_full_access`/
`user_is_manager`) the password-login path sets, so `dept_required`/`role_required` and every
existing view continue working completely unchanged regardless of which path a user logged in
through. Opt-in via `OIDC_CLIENT_ID`/`OIDC_DISCOVERY_URL` env vars, same pattern as `SENTRY_DSN` —
unset by default, so local dev/CI never attempt an SSO round-trip and the login page shows
password-only; a "Sign in with SSO" button appears on `home.html` only when configured. 15 new
tests in `test_sso_core.py`, deliberately testing real cryptography rather than mocking it away: a
real locally-generated RSA keypair signs real JWTs, verified by real `joserfc` code, with dedicated
tests confirming rejection of a wrong nonce, wrong audience, wrong issuer, expired token, a token
signed by a *different* key than the one in the (mocked) JWKS, and a tampered payload with an
otherwise-valid signature — only the HTTP calls (discovery/JWKS/token-endpoint) are mocked, since
those are network I/O, not the security-critical part. **Verified end-to-end for real, not just
unit-tested:** wrote a genuine local mock OIDC provider (stdlib `http.server`, real RS256 signing)
implementing actual discovery/authorize/token/JWKS endpoints, then drove the complete flow through
the Django test client against the real dev DB — hit `/sso/login/`, followed the real redirect to
the mock IdP's `/authorize` endpoint, received a real authorization code via a real HTTP redirect,
hit `/sso/callback/` with it, and confirmed the app correctly exchanged the code, verified the RS256
signature via the mock IdP's JWKS endpoint, resolved the real `james.carter@example.com` President
account, and landed on `/dashboard/` fully authenticated with the correct session keys — plus two
negative cases: an email with no matching account is denied with a visible error and no session
created, and a tampered/mismatched `state` parameter is rejected. Full suite: 2711 passed (2696 +
15 new), `ruff check .` clean. **This closes every item on the prioritized buildable-in-software
list — the only gaps left anywhere in this document are Section 3's four hardware/external-account-
gated items, which the owner has confirmed he has no access to pursue.**

---

## Section 7: 2026-08-26 Fresh Pass — Mobile Coverage Update and New Domains Since Section 6

**Why this pass exists:** five weeks of further work landed after Section 6's five-item
buildable-in-software list closed out on 2026-07-17. None of it maps onto that list — it's either
an update to a Section 6 metric that kept moving on its own (mobile coverage), or genuinely new
domains this document has never scored. This pass does not re-verify Sections 1–6's other claims
(no reason to expect drift there); it only accounts for what's new.

### 7.1 Mobile App Coverage — updated from §6.9

`mobile/app/(tabs)/` now has **10 screens**, up from the 6 §6.9 scored: `index` (dashboard),
`time-clock`, `work-orders`, `maintenance`, `inventory`, `quality`, `approvals`, `lots`,
`requisitions`, `costing`. That's real growth (requisitions and costing are new since the last
count) but the underlying gap §6.9 named is unchanged in kind: **10 of 17 departments** now have a
mobile screen, still leaving accounting, customer_service, engineering, IT, legal, marketing,
payroll, personnel, and sales with zero mobile presence. Scored **partially closed**, not closed —
progress, not parity with the "one universal app" or "per-persona app" breadth most of the top 10
ship.

### 7.2 New domain: Credit / AR Risk Management

Section 1.6 (Finance & Accounting) already credited "Accounts Receivable with aging & DSO" as
Full, but that's collections *reporting* — nothing in this document ever scored proactive credit
*risk management*, because the app didn't have any until now. `manufacturing/credit_core.py` +
`manufacturing/views/_credit.py` (routed under `/credit/...`) now provide: credit account
open/update with automatic limit-change history logging, a credit-application intake and
approve/deny workflow (`decide_credit_application`) that opens or updates the linked account on
approval, and collections-activity tracking tied to at-risk accounts. This is the kind of module
SAP/Oracle/Dynamics ship as part of their credit-management suites and Fishbowl/JobBOSS²/MRPeasy
generally don't — a genuine mid-market-leading capability, not just a gap-fill. Not added as a new
scorecard row in Section 4 (deliberately, to avoid scorecard inflation for a single module); folded
into the existing Finance & Accounting domain's standing.

### 7.3 New domain: Payroll Processing

HR/Payroll (Section 1.7) was already scored 9/10 mid-market on the strength of ESS, benefits,
skills matrix, and workforce analytics — but the actual pay-run engine underneath it was thinner
than that score implied. `manufacturing/payroll_core.py` (609 lines) now has real pay-rate
management (hourly/salary via `upsert_pay_rate`), configurable deduction types and per-employee
deductions, a `process_payroll` engine that runs a full pay period into entries and pay stubs, and
pay-stub/YTD/department-cost reporting. This is a genuine strengthening of an already-credited
domain, not a new gap closure — the prior 9/10 score holds, but is now resting on more solid
ground underneath it.

### 7.4 Operational additions (not separately scored)

Three smaller shipped items worth naming without inflating the scorecard for them:

- **Work order assignment + notification** — `work_orders_core.py` gained an `assigned_to` column
  and `assign_wo()`, which fires a `wo_assigned` entry through the notification center §6.8 shipped
  on 2026-07-17. A small but real example of the notification infrastructure actually being reused
  by a second feature, not a one-off.
- **Work order labor time/cost reporting** — department-scoped reports layered on existing WO labor
  data; a reporting addition, not new core capability.
- **Consultant time & billing** — `consultants_core.py` adds engagement tracking, time entries,
  misc charges, rate/cost resolution, and consultant invoice generation with line items. Adjacent
  to Purchasing/Finance but its own small domain; not scored separately here.

### Net effect on standing

Sections 1–6's scores and the Section 4 scorecard (9.3/10 mid-market, 8.7/10 enterprise) are
unchanged — nothing above corrects a prior claim, and nothing above closes any of Section 6's
remaining honest gaps (modern frontend, row/field-level RBAC, GDPR tooling, vertical compliance
packs, mobile offline support, localization, CI-gated load testing all remain exactly as scored in
§6.1–§6.13). What changed is coverage of ground this document never scored at all — mobile breadth
moved from 6/17 to 10/17 departments, and two genuinely new modules (credit risk management,
payroll processing) plus three smaller operational features shipped without ever appearing in this
document until now.

---

## Section 8: 2026-08-27 Fresh Pass — Closing Section 6's Remaining Platform Gaps

**Why this pass exists:** eleven PRs (#114, #117–#124) landed after Section 7 closed, all aimed
squarely at Section 6's named platform gaps rather than at Section 1 feature rows. Re-verified
each claim below directly against the code on `main` at commit `720ccb3` rather than trusting PR
titles alone.

| §6 gap | Prior status | Now | Verified against |
|---|---|---|---|
| §6.1 Modern frontend — live-refresh without a full page reload | ❌ none | ✅ Partial (PR #114) — 4 of the highest-traffic dashboards (`sf_tv.html`, `prod_dashboard.html`, `maint_dashboard.html`, `ai_insights_dashboard.html`) use htmx for partial-page live refresh, replacing `sf_tv.html`'s old 30-second full reload | `grep -rl htmx manufacturing/templates/` — exactly these 4 files |
| §6.2 SSO — SAML 2.0 / OIDC | ❌ none (then OIDC-only after 07-17) | ✅ Full — OIDC now supports multiple concurrent providers (PR #118, `sso_core.get_providers()` returns a list, not one hardcoded provider), first-time SSO logins can self-provision a new `people` row instead of requiring one to pre-exist (PR #119), and SAML 2.0 (PR #120, `saml_core.py`, `python3-saml`) now sits alongside OIDC as a second federation protocol | `manufacturing/sso_core.py`, `manufacturing/saml_core.py`, `manufacturing/views/_saml.py` all present and routed |
| §6.2 Password policy / MFA for web login | ❌ TOTP existed only for the mobile API | ✅ Full (PR #117) — `accounts.py`'s `ensure_password_policy_columns` plus TOTP verification wired into the standard `home` login view (`mfa_pending_email`/`mfa_pending_people_id` session flow), not just `api_auth.py` | `manufacturing/views/__init__.py` lines ~1073–1091 |
| §6.3 Row-level permission control | ❌ none — ESS's ownership check was a one-off pattern | ✅ Full (PR #122/#124, merged via #123's squash) — `rbac_core.py`'s `is_privileged`/`owned_scope`/`owns_row` (+ `_strict` variants for ESS) are the reusable helper the original assessment called for | `manufacturing/rbac_core.py`, `tests/test_rbac_core.py` (23 tests) |
| §6.3 Field-level permission control | ❌ none | ✅ Full (PR #124) — `rbac_core.can_view_compensation()` masks the one concrete example named in the original gap text (mechanic hourly_rate, hidden from non-Payroll/HR/full-access viewers), enforced server-side via the existing `COALESCE(%s, hourly_rate)` update pattern, not just template hiding | `manufacturing/views/_maintenance.py`, live-verified against the running dev server this session |
| §6.5 AS9100 / IATF 16949 vertical compliance content | ❌ none — generic ISO/FDA checklist only | ✅ Full (PR #123) — `regulatory_compliance_core.py` now seeds real AS9100D and IATF 16949 checklist templates alongside the original two generic starters | `grep -c "AS9100\|IATF" manufacturing/regulatory_compliance_core.py` → 11 hits |
| §6.13 CI-gated load testing | ❌ Locust script existed but ran manually only | ✅ Partial (PR #121) — wired into `.github/workflows/loadtest.yml` as a `workflow_dispatch` manual trigger (matches the original "cheapest real improvement" recommendation exactly: repeatable one-click run, not a full per-PR gate) | `.github/workflows/loadtest.yml` |

**What's still open, unchanged from Section 6/7:**
- **§6.1 Modern frontend** — only 4 dashboards got htmx; the other ~430 templates are still
  full-page Django renders. No SPA rewrite, still correctly out of scope for this codebase's size.
- **§6.4 Data governance / GDPR tooling** — genuinely zero: still no `delete_person`/anonymize
  path, no per-subject data export, no PII tagging, no retention-policy engine anywhere in the
  codebase (confirmed by grep this session — no `data_governance_core.py` exists).
- **§6.5 GxP / 21 CFR Part 11 e-signatures** — the vertical *checklist content* gap closed (AS9100/
  IATF), but real e-signature (password re-entry + captured "meaning of signature" on
  `approval_step` decisions) was not part of PR #123's scope and remains unbuilt.
- **§6.6 OpenAPI/Swagger docs, per-endpoint API rate limiting** — both named as deliberately out of
  scope when the outbound webhook system shipped (07-17); still unbuilt.
- **§6.9 Mobile app coverage** — unchanged since Section 7 (10/17 departments).
- **§6.10 Mobile offline support** — unchanged, zero (`grep -rl "NetInfo\|offline" mobile/` — no
  hits).
- **§6.11 Localization / i18n** — unchanged, zero (`{% trans %}`/`{% blocktrans %}` — no hits across
  ~430 templates).

**Net effect on standing:** every item on Section 6's original five-item "prioritized
buildable-in-software" list was already closed by 07-17 (see that section's own dated log); this
pass closes three items Section 6 explicitly named as real gaps but deliberately left off that
top-5 list for being lower-ROI at the time — row/field-level RBAC (§6.3, both halves) and vertical
compliance pack content (§6.5, checklist rows specifically, not e-signatures). Modern frontend and
CI-gated load testing also moved from "none" to "partial," matching honestly-scoped, low-effort
slices of each rather than the full item. The five gaps left genuinely untouched — GDPR/data
governance, GxP e-signatures, API docs/rate limiting, mobile offline, and localization — are the
same ones Section 6 already flagged as lower-ROI for this app's actual buyer profile (SMB/
mid-market, single-tenant, single-language) rather than newly discovered.

---

**2026-08-27:** Shipped **§6.4 Data Governance / GDPR-Style Tooling**, the highest-remaining-value
item from this pass's own "still open" list. `data_governance_core.py` adds three pieces exactly
as scoped in §6.4's own "what it would take" note: (1) `anonymize_person()` — right-to-erasure as
anonymization, not row deletion: overwrites `people`'s PII columns (name/address/email/phone/
emergency contact) with placeholders and revokes login (deletes the `passwd` row, revokes all API
tokens, disables TOTP), while deliberately leaving every other people_id-referencing table (time
clock, payroll, reviews, notifications, etc.) untouched — deleting that history would break
financial/operational recordkeeping this app needs to keep, the same tradeoff CLAUDE.md's own note
on this gap already called for; (2) `export_person_data()` — a genuine "give me everything you have
on me" subject-access export joining `people` against 20 known people_id-referencing tables, download-
able as JSON from a new `/data-governance/` admin page; (3) a `retention_policy` engine
(months-after-termination cutoff) plus `python manage.py run_data_retention`, a new scheduled
command modeled directly on `send_daily_digest`'s own pattern, that auto-anonymizes terminated
employees once a policy's cutoff passes. `people` was already one of `audit_core.py`'s
`AUDITED_TABLES`, so every anonymization's own UPDATE is captured with full old/new values by the
existing DB-trigger audit trail for free; a lightweight `erasure_log` table sits on top of that for
fast per-subject "when/why/by whom" lookups without reconstructing it from `audit_log`'s JSONB each
time. New admin UI (`/data-governance/` search+erase+export+policy list, `/data-governance/
retention-policies/<id>/` edit) gated to full-access roles only, mirroring the Approval Rules and
Webhooks admin pages' exact structure and gating. 14 new tests in `test_data_governance_core.py`,
all against the mocked-connection convention this app's other `*_core.py` tests already use.
Verified end-to-end against the real dev DB rather than just unit-tested: created two throwaway
test people, anonymized one manually through the live web UI (confirmed `people` row scrubbed,
`passwd` row deleted, and a matching `erasure_log` entry with the acting admin's email), set the
other's termination date 400 days in the past, created a real 6-month retention policy through the
UI (dashboard correctly showed "1 candidate"), ran `run_data_retention` for real and confirmed it
anonymized exactly that person and logged the erasure as `performed_by='system:retention_policy'`
(candidate count dropped to 0 afterward), confirmed a non-admin session is redirected away from
`/data-governance/` entirely, and confirmed the JSON export endpoint returns the person's real data
plus their referencing `position` row. All test data deleted afterward. Full suite: 3396 passed
(3382 + 14 new), `ruff check .` clean, `manage.py check` clean. **This leaves four gaps genuinely
open from this section's list: GxP e-signatures, API docs/rate limiting, mobile offline support,
and localization** — none started, all still correctly scored as lower-ROI for this app's buyer
profile.

---

**2026-08-27, later same day:** Shipped **§6.5 GxP / 21 CFR Part 11 e-signatures**, exactly as
scoped in that section's own "what it would take" note: "password re-entry + a captured 'meaning
of signature' string per `approval_step` decision... a moderate, contained addition to the existing
`decide_step` function." `approval_workflow_core.decide_step()` gains a `signature_meaning`
parameter (stored in a new `approval_step.signature_meaning` column, added via `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS` since the table pre-dates this column) alongside the `decided_by`/`decided_at`
columns it already had — together the three satisfy Part 11's baseline signature-record
requirements (who, when, and what the signature meant). Password re-authentication itself isn't
stored anywhere (it's a one-time gate at decision time, not a data field) — it reuses
`accounts._verify_login()`, the exact same re-entered-password check this app already uses for
change-password and MFA-disable confirmation, so no new verification code was written. Threaded
through all three real web decision points that call the generic engine — `document_control_core
.decide_document`, `cycle_count_core.decide_cycle_count`, and `consultants_core
.decide_consultant_invoice_via_workflow` — plus their corresponding views (`_document_control.py`,
`_cycle_count.py`, `_consultants.py`), each of which now requires both a non-empty
`signature_meaning` and a correct password re-entry before calling into the wrapper; either
failure returns a clear error and records nothing (confirmed live — see below). Left the
`signature_meaning` parameter optional (default `''`) on `decide_step` itself and did **not** touch
the mobile API's decision path (`api_views.py`) or `purchase_requisitions_core
.decide_requisition_via_workflow`, since mobile capturing a re-entered password over the API is a
separate, larger design question (secure password transmission/storage on-device) not in this
item's scope — a real gap worth flagging for later, not silently dropped. Also discovered along
the way: web requisition approvals don't actually go through this generic engine at all (they use
`purchase_requisitions_core.decide_requisition`, a separate simpler status-transition function) —
`decide_requisition_via_workflow` is mobile-only. 4 new tests in `test_approval_workflow_core.py`
covering `signature_meaning` storage and its empty-by-default behavior; full suite: 3398 passed
(3396 + 4 — wrapper-function signature changes needed no fixture updates since existing tests use a
lenient sequenced-mock connection). Verified end-to-end against the real dev DB rather than just
unit-tested: created a real `document` approval rule + a real document + a real pending
`approval_step` via the actual core functions, then drove the decision through the live web UI as a
real Department Manager account — confirmed submitting with no `signature_meaning` is rejected with
a clear error and the step stays `pending`, confirmed submitting with a wrong password is rejected
the same way with nothing recorded, and confirmed a correct password + a real signature-meaning
string is accepted, immediately visible in `approval_step.signature_meaning`, and the document
correctly cascades to `approved`. All test data deleted afterward. `ruff check .` and `manage.py
check` clean. **This leaves three gaps genuinely open: API docs/rate limiting, mobile offline
support, and localization** — none started, all still correctly scored as lower-ROI for this app's
buyer profile.

---

**2026-08-28:** Shipped **§6.6 Published API docs (OpenAPI/Swagger)** and **per-endpoint API rate
limiting**, closing both remaining rows in that section's table together since one PR touches the
same choke point (`api_decorators.api_required`) either way. Docs: `api_openapi_core.py` hand-builds
a full OpenAPI 3.0 spec from a plain `ENDPOINTS` list — deliberately not introspected from Django's
URL resolver and not built on `drf-spectacular` (which would mean adopting Django REST Framework,
a framework this app has never used, just to document 48 already-working endpoints). Every entry's
method(s) were read directly off `api_views.py`'s own `@require_http_methods` decorators (or, for
the six endpoints with internal GET/POST branching, both), not guessed from naming convention.
Served as raw JSON at `/api/v1/openapi.json` and as interactive Swagger UI at `/api/docs/`
(`views/_api_docs.py`) — the UI loads `swagger-ui-dist` from a CDN, the same pattern every
dashboard's Chart.js `<script src="cdn.jsdelivr.net">` tag already uses, rather than vendoring a
JS toolchain into a repo that has none. Rate limiting: `api_auth.py` gains a second, independent
limiter alongside the existing login-attempt lockout — `is_api_rate_limited`/`record_api_request`
log every request (not just failures) per `(people_id, endpoint path)` into a new
`api_request_log` table, and `api_required` (the single decorator wrapping all 48 `@api_required`
views) now checks it on every call, returning `429` once a caller exceeds
`API_RATE_LIMIT_MAX_REQUESTS=120` requests in `API_RATE_LIMIT_WINDOW_SECONDS=60` against one
endpoint — applied automatically with no per-view opt-in, closing the gap for every endpoint at
once rather than one at a time. 16 new tests (12 for the OpenAPI spec's structure/coverage, 4
extending the existing `@api_required` test suite for the 429 path and confirming under-limit
calls still reach the view and get logged); full suite: 3412 passed (3398 + 16 — three pre-existing
`test_api_decorators.py` tests needed their `_FakeConn`/patch fixtures extended for the new
rate-limit check and `commit()` call, the same "adding a call to an already-tested function needs a
fixture update" pattern this document's own log has hit repeatedly). Verified end-to-end against
the real dev server rather than just unit-tested: fetched `/api/v1/openapi.json` and confirmed all
49 paths resolve with the live server's own host baked into `servers[0].url`; loaded `/api/docs/`
and confirmed the Swagger UI bundle renders; logged in for a real token and fired 125 real requests
at `/api/v1/auth/profile/` — the first 120 returned `200`, the remaining 5 returned `429` with a
clear error message, and the *same* token hitting a *different* endpoint (`/api/v1/dashboard/`)
immediately afterward still returned `200`, confirming the limit is genuinely per-endpoint rather
than a blanket per-user cap. All test rate-limit-log rows and tokens deleted afterward. `ruff
check .` and `manage.py check` clean. **This leaves two gaps genuinely open: mobile offline support
and localization** — both still correctly scored as lower-ROI/higher-effort for this app's buyer
profile than everything shipped in this pass.

---

**2026-08-28, later same day:** Shipped **§6.10 Mobile offline support** — deliberately partial,
matching the honest-scoping precedent this document already used for RFID (P3-M) and predictive
maintenance (P4-B) rather than claiming full offline-first coverage this pass doesn't deliver. A
reusable `mobile/src/offline/` module adds three pieces: `cache.ts`'s `fetchWithOfflineCache()`
wraps any GET call, caching the response to `AsyncStorage` on success and falling back to the last
cached value (flagged stale) when the network call fails, instead of a blank screen or a raw error
alert; `queue.ts`'s `enqueueMutation()`/`flushQueue()` persist a mutating call to replay once
connectivity returns, in the original order (stopping at the first failure rather than reordering
around it); `netStatus.ts`'s `useIsOnline()` (backed by the new `@react-native-community/netinfo`
dependency — no real alternative exists for this, the same "real, necessary new dependency" call
already made for `joserfc` in the SSO work) plus a shared `OfflineBanner` component surface
"showing cached data" / "N actions waiting to sync" instead of failing silently. A global `NetInfo`
listener in `app/_layout.tsx` flushes the queue the instant the device reconnects, regardless of
which screen is focused — a queued clock-out shouldn't wait for the user to revisit the Time Clock
tab. **Wired into exactly two of the ten screens**: Time Clock (full read-cache + write-queue —
clock in/out with no signal is the canonical plant-floor case this gap named) and Work Orders' list
view (read-cache only; status changes/assignment still require connectivity). The other 8 screens
remain unmodified — extending the same pattern to them is mechanical but is real, not-yet-done work,
stated plainly rather than implied as complete. No test framework exists for `mobile/` to add unit
tests to (CI's own three checks — `tsc --noEmit`, `expo-doctor`, `expo export --platform web` — are
this package's entire verification surface); all three ran clean against the changes. Interactive
browser verification of the offline/online transition itself (toggling connectivity and watching
the banner/queue behave) was attempted via this session's preview tooling but blocked by an
environment constraint — the preview harness's fixed project root doesn't support the mobile app's
separate `package.json` location — so this pass relies on the three static CI checks plus code
review rather than a live interactive demonstration; noted here rather than silently claimed as
verified. **This leaves one gap genuinely open: localization** — the last item on the entire
Section 6/7/8 buildable-in-software list, still correctly scored as the lowest-ROI/highest-
ongoing-cost item for this app's single-language buyer profile.

---

**2026-08-28, later still:** Shipped **§6.11 Multi-Language / Localization** — deliberately
partial, closing this document's entire buildable-in-software list the same honestly-scoped way
every other item in it closed (RFID simulated, predictive maintenance manual-entry, mobile offline
2-of-10-screens). Real, working i18n infrastructure previously entirely absent (§6.11's own finding:
"no `LocaleMiddleware`, no `LOCALE_PATHS`" despite `USE_I18N=True` already being Django's stock
default): `django.middleware.locale.LocaleMiddleware` correctly positioned in `MIDDLEWARE`,
`LANGUAGES`/`LOCALE_PATHS` in settings, and a real language switcher in `base.html`'s top bar
posting to Django's built-in `set_language` view. Translation coverage is the app's core navigation
shell — `base.html` in full (all 11 sidebar section headers, all ~37 nav links, top-bar
notifications/password/2FA/logout) and `home.html` (the login page) — roughly 60 strings wrapped in
`{% trans %}`/`{% blocktrans %}`, with real, business-appropriate Spanish translations (not
placeholder text) in `locale/es/LC_MESSAGES/django.po`, compiled to a working `.mo`. **The other
~450 department-specific content templates remain English-only** — extending this pattern to any of
them is mechanical per-template work (`{% load i18n %}`, wrap, translate, recompile) but is real,
not-yet-done work, stated plainly per this document's own convention rather than implied as
complete. No code-level tests apply (this is template/settings work, not `*_core.py` logic); full
suite re-ran clean anyway (3412 passed, unchanged) confirming nothing broke, plus `ruff check .` and
`manage.py check` clean. Verified end-to-end against the real dev server rather than just
statically: logged in as a real user, confirmed the dashboard renders correctly with all sidebar
sections/links in English by default; switched language via the real `/i18n/setlang/` endpoint and
confirmed the same dashboard re-rendered entirely in Spanish (`<html lang="es">`, "Panel de
control", "Órdenes de trabajo", "Operaciones", "Compras", "Ventas", "Recursos humanos", topbar
"Contraseña"/"Cerrar sesión", etc.) with the language-switcher `<select>` correctly showing the
active selection; separately confirmed a fresh, never-logged-in visitor sending
`Accept-Language: es` sees the login page in Spanish too, confirming `LocaleMiddleware`'s
header-based fallback works independent of the session-based switcher. **This closes the last item
on this document's entire Section 6/7/8 buildable-in-software list — every gap named across §6.1
through §6.13 that didn't require external hardware or a live third-party account (Section 3's
remaining four items) has now shipped, at the honestly-scoped depth stated in each item's own
closure note above.**

---

## Section 9: 2026-08-28 Full Re-Assessment vs. the Named Top 10

**Why this pass exists:** every item on Sections 6–8's platform-maturity list has now shipped
(§6.2 SSO/SAML/MFA, §6.3 row+field RBAC, §6.4 GDPR tooling, §6.5 vertical compliance content +
Part-11 e-signatures, §6.6 outbound webhooks + published API docs + per-endpoint rate limiting,
§6.7 self-service approval-rule admin, §6.8 notification center, §6.12 health checks, §6.13
CI-gated load testing — 11 of 13 items fully or partially closed since Section 6 first scored this
app against platform dimensions no part of Section 1–5 ever touched). This is the first pass to ask
the follow-up question directly: **given all of that, how does this app actually compare to each of
the ten named vendors today, not just against an abstract checklist?** Vendor claims below come from
each company's own public documentation/marketing and third-party review sites (Software Advice,
Capterra, Epicor's own user forums, etc.), spot-checked this session — not a live audit of their
current admin consoles, which none of the ten grant public access to. Where evidence was thin or
contradictory, that's stated rather than guessed past.

### 9.1 Top-line stats (this app, verified this session)

| Metric | Count |
|---|---|
| Qt-free business-logic modules (`*_core.py`) | 92 |
| Django web templates | 454 |
| View submodules | 67 |
| Automated test files | 104 |
| Automated tests passing | 3,412 |
| Section 1 feature domains with zero remaining ❌ | 15 / 15 |
| Section 6–8 platform-maturity items fully or partially closed | 11 / 13 |

### 9.2 Platform-maturity scorecard (Sections 6–8, current state)

| Dimension | Status | What's real |
|---|---|---|
| SSO — OIDC (multi-provider) + SAML 2.0 | ✅ Full | + self-service provisioning, password policy, TOTP MFA on web login |
| Row-level RBAC | ✅ Full | `rbac_core.py`, reusable ownership-scoping helper, adopted by Sales/CS/ESS |
| Field-level RBAC | ✅ Full | compensation-field masking, server-enforced (not just template-hidden) |
| GDPR / data governance | ✅ Full | erasure (anonymize, not delete), subject-access export, retention-policy engine |
| Vertical compliance content (AS9100D, IATF 16949) | ✅ Full | real checklist rows, not just generic ISO/FDA templates |
| 21 CFR Part 11 e-signatures | ✅ Full | password re-auth + captured meaning-of-signature on approval decisions |
| Published API docs (OpenAPI/Swagger) | ✅ Full | `/api/docs/`, hand-curated spec matching real `@require_http_methods` |
| Per-endpoint API rate limiting | ✅ Full | 120 req/60s per user per endpoint, independent of the login-lockout limiter |
| Outbound webhook system | ✅ Full | subscription + HMAC-signed delivery, 4 real event sources |
| In-app notification center | ✅ Full | bell icon, unread count, fed by approvals + low-stock crossings |
| Self-service approval-rule admin UI | ✅ Full | no-developer-needed CRUD over the existing engine |
| Health-check endpoint | ✅ Full | `/healthz/`, real `SELECT 1` |
| CI-gated load testing | 🟡 Partial | real Locust script, wired as a manual `workflow_dispatch` job, not per-PR |
| Modern reactive frontend | 🟡 Partial | htmx live-refresh on 5 of ~450 templates — see 2026-08-28 update below |
| Mobile app department coverage | 🟡 Partial | 11 of 17 departments have a mobile screen — see 2026-08-28 update below |
| Mobile offline support | 🟡 Partial | read-cache + write-queue on 2 of 10 mobile screens |
| Localization / i18n | 🟡 Partial | core nav shell + login + main dashboard, four languages (en/es/fr/de) — see 2026-08-28 update below |

### 9.3 Feature-domain scorecard (Section 4, unchanged — recapped for context)

Section 1's 15 feature domains are unaffected by this pass (nothing in Sections 6–9 touched Work
Orders, MRP, Inventory, Quality, etc.) — still averaging **9.3/10 vs. mid-market, 8.7/10 vs.
enterprise**, with 8 of 15 domains fully closed (Quality, Purchasing, HR/Payroll, Maintenance,
Reporting/Analytics, Scheduling/APS all have zero remaining ❌ rows per Section 4's own log).

### 9.4 Verdict against each of the ten named vendors

| Vendor | Where they still lead | Where this app now stands |
|---|---|---|
| **SAP S/4HANA** | Global multi-entity financial consolidation depth, Fiori UX polish, dozens of shipped languages | The SSO/RBAC/GDPR/compliance gap that used to be a hard blocker in an SAP-shop IT security review is closed; frontend modernity and localization depth are not |
| **Oracle Cloud Manufacturing (Fusion)** | Same enterprise financial/localization depth as SAP | Same story — platform-maturity parity reached, i18n breadth is the widest remaining gap |
| **Microsoft Dynamics 365 SCM** | Power Platform (Power Automate/Power BI/Power Apps) gives far deeper low-code/BI reach than this app's approval-rule admin UI + webhooks | The specific "self-service workflow config without a developer" gap Dynamics wins on is closed; Power Platform's broader no-code surface is not matched |
| **Epicor Kinetic** | Confirmed (this session) to already ship native field/row-level security, and purpose-built, certified AS9100/Part-11/aerospace compliance modules — more mature than this app's equivalents | This app now approaches parity on RBAC granularity and vertical compliance *content*; Epicor's modules are certified/purpose-built where this app's are honestly-scoped and non-certified — narrows, doesn't erase, the gap |
| **Infor CloudSuite Industrial** | ION integration platform has a more mature no-code UI than this app's webhook/approval-rule admin screens | Conceptually equivalent capability now exists (subscription-based event routing, self-service rule config); Infor's tooling is more polished |
| **Plex Manufacturing Cloud** | Native real-time shop-floor/MES depth, automotive-native heritage | The vertical-compliance and e-signature work narrows Plex's automotive/aerospace-specific edge without closing its shop-floor MES depth |
| **SYSPRO** | Comparable overall scale/target market | Likely at or near parity on RBAC/GDPR/API governance now — dimensions that used to be SYSPRO's edge over smaller point tools |
| **Fishbowl** | — | Fishbowl's own privacy page doesn't clearly state GDPR compliance and no SSO/SAML capability is publicly documented; this app is now genuinely ahead on RBAC, GDPR tooling, e-signatures, and published API docs, on top of already-comparable core feature depth |
| **JobBOSS² (ECI Solutions)** | Shop-floor/job-shop scheduling depth for its niche | No comparable RBAC/GDPR/compliance/API-governance depth found in public documentation; same verdict as Fishbowl on platform maturity |
| **MRPeasy** | **Genuinely ahead on localization** — confirmed shipping in 13+ languages (English, Spanish, French, German, Portuguese, Dutch, and more) against this app's single added language | Simple, SMB-focused by design — no RBAC/GDPR/compliance tooling to compare against; but on the one dimension this app just worked on, MRPeasy is still ahead |

**Net read:** this app has moved from "strong mid-market, several upper-mid-market capabilities"
(this document's original framing) to something closer to **upper-mid-market approaching
lower-enterprise** — comprehensive Section 1 feature depth *and* the platform-governance maturity
(SSO, granular RBAC, GDPR, vertical compliance, e-signatures, API governance) that used to be
almost exclusively SAP/Oracle/Dynamics territory. The two dimensions where the gap is still real and
wide, even against SMB-tier peers, are **localization breadth** (MRPeasy alone ships more languages
than this app's one) and **frontend modernity** (every enterprise vendor and Epicor/Infor/Plex ship
a reactive SPA; this app is 4 htmx pages into ~450 server-rendered templates). Both are already
honestly scored as such in §9.2 — this pass doesn't change either score, it just confirms the
scores hold up against the vendors' actual public positioning, not just this document's own prior
claims about them.

---

**2026-08-28, follow-up:** Extended localization directly in response to §9.4's own finding —
MRPeasy, the simplest SMB-tier named competitor, ships in 13+ languages against this app's one.
Added two more languages (French, German) alongside the existing Spanish, and extended translation
coverage from the nav shell + login page to the post-login **main dashboard** (`dashboard.html`):
all 6 executive KPI card labels, all 4 chart titles, the "Company Main Menu" heading, and the
pending-PO-approvals banner — the last one using a real `{% blocktrans count %}` plural form (not
a hardcoded English `|pluralize`), verified to resolve correctly in all three languages via
`django.utils.translation.ngettext` (Spanish/French singular-vs-plural at n=1 vs n=3, German's
`nplurals=2; plural=(n != 1)` rule). All three `.po` files hand-translated in full — 79 messages
each, zero fuzzy/untranslated per `msgfmt --statistics` — not machine-translated placeholder text.
One process finding worth keeping: re-running `makemessages` to pick up the new `dashboard.html`
strings correctly preserved the existing Spanish translations via `msgmerge` matching on source
text, but also **fuzzy-matched two new strings to the wrong existing translation** ("PO Approvals"
guessed as similar enough to already-translated "Approval Rules", "Open Work Orders"/"Maint. Work
Orders" both guessed against "Work Orders") — `#, fuzzy` markers that would have shipped silently
wrong translations if not caught and hand-corrected; now documented as a required review step in
CLAUDE.md's Localization section for the next language or template added. The one remaining
department-grid button labels on the same dashboard page are the sole exception — sourced from
`menus.py`-generated Python strings rather than template-static text, so translating them needs
`gettext_lazy` in Python, a different mechanism, not done this pass. Full suite re-ran clean (3412,
unchanged — this is template/settings/locale-file work, no `*_core.py` logic touched), `ruff
check .` and `manage.py check` clean. Verified end-to-end against the real dev server for all three
languages: logged in, switched to each via the real `/i18n/setlang/` endpoint, and confirmed the
dashboard's `<html lang>` attribute, KPI labels, and chart titles all render correctly in Spanish,
French, and German respectively. **Localization remains honestly scored as partial** — three
languages and two templates is real progress against the specific gap named in §9.4, not a claim
that the ~450 remaining templates or MRPeasy's full language count are now matched.

---

**2026-08-28, still later:** Extended **§6.1 Modern Frontend** by one more page — the **main company
dashboard** (`dashboard.html`), the single highest-traffic page in the app (every logged-in user's
landing page) — using the exact same htmx live-refresh pattern PR #114 already established for
`sf_tv.html`/`prod_dashboard.html`/`maint_dashboard.html`/`ai_insights_dashboard.html`, not a new
mechanism: a `dashboard_kpis.html` partial (the pending-PO-approvals banner + all 6 executive KPI
cards, extracted verbatim from `dashboard.html`) is both `{% include %}`d for the initial render and
served standalone by a new `dashboard_kpis_fragment` view, polled every 30s via
`hx-get`/`hx-trigger`/`hx-swap`. The KPI-computation SQL itself was factored out of the `dashboard()`
view into a shared `_dashboard_kpis(request, conn)` helper so the full-page render and the polling
fragment can never drift out of sync by construction — the fragment isn't a separate, hand-maintained
copy of the same six queries. This is now 5 of ~450 templates with live-refresh, still correctly
scored as partial; the doc's own §6.1 conclusion that a full SPA rewrite isn't proportionate to this
codebase's size is unchanged — the next htmx target (if pursued) should stay this same
highest-traffic-page-at-a-time approach, not a framework migration. Full suite re-ran clean (3412,
unchanged — the refactor is a pure extraction, no behavior change to the existing `dashboard()`
view's own output), `ruff check .` and `manage.py check` clean. Verified end-to-end against the real
dev server, not just statically: hit `/dashboard/kpis-fragment/` directly and confirmed it renders
standalone; created a real work order via `work_orders_core.create_wo` (status `'open'`), re-fetched
the fragment, and confirmed "Open Work Orders" incremented from 4 to 5 — genuine live data, not a
cached or static partial — then deleted the test work order; separately confirmed the fragment
correctly renders in the active session's language (French) when fetched with that session's
cookies, proving the i18n and htmx-fragment work compose without conflict (`LocaleMiddleware` reads
the session on every request, including polling `GET`s).

---

**2026-08-28, one more:** Closed the **Finance** row in §6.9's Mobile App Coverage table — exactly
the item that section's own "what it would take" note called cheapest: "the existing REST API
already has Financial/Production/Inventory dashboard endpoints... so the gap for at least a
read-only Sales/Finance/HR mobile view is mobile-app screen work, not new backend API surface." A
new `finance.tsx` tab reuses `/api/v1/dashboards/financial/` (`reports_core.financial_dashboard`)
completely as-is — zero new backend code — surfacing cash position, DSO, DPO, gross margin %, AP
due this week, and the AR aging bucket breakdown (current/1-30/31-60/61-90/over-90 days) via the
same `KpiCard` component and `ScrollView`/`RefreshControl` pattern the main dashboard screen already
established. §6.9's own explicit zero-coverage list drops from 11 named departments to **10**:
`accounting`, `customer_service`, `customers`, `engineering`, `it`, `legal`, `marketing`,
`payroll`, `personnel`, `sales` — one department closed this pass, matching this section's own
precedent of picking off the cheapest remaining item first (Sales and HR are the other two
"read-only, existing-API" candidates named in §6.9's own text, both still open). No backend tests
needed (no Python changed); mobile's own three-check CI surface (`tsc --noEmit`, `expo-doctor`,
`expo export --platform web`) all ran clean. Verified end-to-end rather than just statically: hit
the real `/api/v1/dashboards/financial/` endpoint directly with a real bearer token against the
live dev server and confirmed the actual JSON response shape (`cash_position`, `dso`, `dpo`,
`ar_aging` with all five bucket keys, `ap_due_week`, `gross_margin_pct`) matches the TypeScript
interface the new screen was written against exactly — not just trusting the Python source read.

---

**2026-08-28, last one for now:** Closed the **Sales** row too. Unlike Finance, this one genuinely
needed new backend API surface — §6.9's own text had claimed "the existing REST API already has
Financial/Production/Inventory dashboard endpoints... so the gap for at least a read-only
Sales/Finance/HR mobile view is mobile-app screen work, not new backend API surface," but that
claim was inaccurate for Sales specifically: grepping `urls.py`/`api_views.py` found zero
`/api/v1/...` sales routes of any kind before this pass (`sales_dashboard` at `urls.py:369` is the
*web* UI view, not part of the mobile API) — worth correcting here rather than silently building on
top of a stale claim. Added a real `reports_core.sales_dashboard(conn)` (housed alongside
`financial_dashboard`/`production_dashboard`/`inventory_dashboard`, the same domain-dashboard
convention) that reuses `sales_core.get_sales_dashboard()` and `sales_orders_core.list_sos()`
rather than a third copy of the same queries, plus a genuinely new `api_sales_dashboard` view and
`/api/v1/dashboards/sales/` route, added to `api_openapi_core.py`'s `ENDPOINTS` list so the
published API docs stay in sync. The new `sales.tsx` mobile screen surfaces open-order count, total
order value, quotes won, target attainment %, and up to 8 recent orders with customer/status/total
— also extended `StatusBadge`'s color map with the three sales-order statuses (`confirmed`,
`shipped`, `invoiced`) it didn't have colors for yet. 3 new tests for `sales_dashboard()` (including
the customer-name fallback to first/last name when no company is linked, and the 8-order cap) plus
the pre-existing OpenAPI spec-coverage tests automatically covering the new endpoint; full suite
3415 passed (3412 + 3), `ruff check .` and `manage.py check` clean; mobile's `tsc --noEmit`/
`expo-doctor` (21/21)/`expo export --platform web` all clean. Verified end-to-end against the real
dev server: hit `/api/v1/dashboards/sales/` directly with a real bearer token and confirmed live
data (10 real sales orders, real customer names, real target/actual figures) matches the TypeScript
interface exactly, including the empty-customer-name edge case for orders with no linked contact.
§6.9's explicit zero-coverage list now drops to **9** named departments: `accounting`,
`customer_service`, `customers`, `engineering`, `it`, `legal`, `marketing`, `payroll`, `personnel`.
HR/Personnel is the last "cheap, existing-API-adjacent" candidate that section named; the rest
(accounting, customer_service, engineering, IT, legal, marketing) would need real new backend work
the way Sales just did, not a free reuse the way Finance was.

---

**2026-08-28, and the last cheap one:** Closed **Personnel** — the item flagged above as the last
"cheap, existing-API-adjacent" candidate, and it held up: unlike Sales, `personnel_core
.get_personnel_dashboard()` already existed *and* was already in real use by the web personnel
dashboard (`views/__init__.py:7542`), so this needed only a new `api_personnel_dashboard` view and
`/api/v1/dashboards/personnel/` route — zero new core logic, the same reuse-only shape as Finance
rather than Sales' genuinely-new-backend shape. The new `personnel.tsx` mobile screen surfaces
total headcount, pending/approved time-off counts, a by-department headcount breakdown (bar-style,
top 6 departments), and the 8 most recently added employees with job title and department. No new
backend tests needed (no new Python logic, matching Finance's precedent, not Sales'); full suite
still 3415 passed (unchanged), `ruff check .` and `manage.py check` clean; mobile's `tsc --noEmit`/
`expo-doctor` (21/21)/`expo export --platform web` all clean. Verified end-to-end against the real
dev server: hit `/api/v1/dashboards/personnel/` directly with a real bearer token and confirmed
live data (74 real employees, a real by-department breakdown, real recent hires with job
titles) matches the TypeScript interface exactly. §6.9's explicit zero-coverage list now drops to
**8** named departments: `accounting`, `customer_service`, `customers`, `engineering`, `it`,
`legal`, `marketing`, `payroll`. **Every "cheap" candidate this section ever named (Finance, Sales,
Personnel) is now shipped** — every department left on the list would need real new backend work
the way Sales did, not a free reuse; picking further ones is a judgment call on which department's
data is most valuable on a phone, not an ROI-obvious next step the way these three were.

---

**2026-08-28, and one that turned out cheap too:** Closed **Accounting** next, despite the note
directly above saying everything left would need "real new backend work the way Sales did" — this
one turned out closer to Personnel's shape than Sales'. `accounting_core.get_ap_dashboard()` and
`get_ar_dashboard()` already existed and were already in real use by four different web views
(`views/__init__.py` lines 5141, 5293, 5411-5412, 8326-8327, including the department's own
`acct_dashboard` landing page), so the only new code is a small `reports_core
.accounting_dashboard()` combining those two existing functions with the same recent-GL-journals
query `acct_dashboard` already runs — not a third copy, and not new SQL. New `api_accounting_dashboard`
view + `/api/v1/dashboards/accounting/` route, added to `api_openapi_core.py`'s `ENDPOINTS`. The
new `accounting.tsx` mobile screen shows AP/AR outstanding balances with overdue counts, all-time
invoiced totals for both ledgers, and the 8 most recent GL journal entries with a Posted/Draft
badge. 2 new tests for `accounting_dashboard()` (combining AP+AR+journals, and the empty-journals
edge case); full suite 3417 passed (3415 + 2), `ruff check .` and `manage.py check` clean; mobile's
`tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web` all clean. Verified end-to-end
against the real dev server: hit `/api/v1/dashboards/accounting/` directly with a real bearer token
and confirmed live data (real AP/AR balances, 8 real GL journal entries including WO-close and
intercompany transactions) matches the TypeScript interface exactly. §6.9's explicit zero-coverage
list now drops to **7**: `customer_service`, `customers`, `engineering`, `it`, `legal`, `marketing`,
`payroll`. The lesson from this pass: "needs new backend work" and "is cheap to add" turned out to
be more about whether a department already had a dashboard-shaped aggregation function lying around
(Accounting did, quietly) than about which items this document happened to flag as cheap in
advance — worth spot-checking each remaining department's own `*_core.py` for an existing
`get_*_dashboard`/`*_dashboard` function before assuming new backend work is required.

---

**2026-08-28, and the pattern held again:** Closed **Customer Service** by applying that exact
lesson — checked `cs_calls_core.py` first and found `get_summary_stats()` and `list_tickets()`
already existed and were already in real use by the web `cs_dashboard_view`. Added
`reports_core.customer_service_dashboard()` combining the two (matching Accounting's and Sales'
shape: reuse the domain module's own dashboard-shaped function, add a recent-items list, no new
SQL of substance) plus a new `api_customer_service_dashboard` view and
`/api/v1/dashboards/customer-service/` route, added to `api_openapi_core.py`'s `ENDPOINTS`. The new
`customer-service.tsx` mobile screen shows open-ticket count, completion rate, average resolution
time, average age of currently-open tickets, and the 8 most recent tickets with an Open/Closed
badge. 2 new tests for `customer_service_dashboard()` (stats+recent-tickets combination, and the
8-ticket cap with a null call_date); full suite 3419 passed (3417 + 2), `ruff check .` and
`manage.py check` clean; mobile's `tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web`
all clean — including confirming a hyphenated route filename (`customer-service.tsx`, needed since
the department name has a space) works fine with Expo Router. Verified end-to-end against the real
dev server: hit `/api/v1/dashboards/customer-service/` directly with a real bearer token and
confirmed live data (26 real tickets, real completion-rate/resolution-time figures, 8 real recent
tickets with real customer names and call descriptions) matches the TypeScript interface exactly.
§6.9's explicit zero-coverage list now drops to **6**: `customers`, `engineering`, `it`, `legal`,
`marketing`, `payroll`. Three departments in a row (Personnel, Accounting, Customer Service) turned
out to already have a reusable dashboard function sitting in their own `*_core.py` — worth checking
`engineering_core.py`, `it_core.py`, `legal_core.py`, `marketing_core.py`, and `payroll_core.py` for
the same pattern before assuming any of them needs real new backend work.

---

**2026-08-28, four in a row now:** Closed **Engineering** — checked `engineering_core.py` first per
the standing lesson and found `get_eng_dashboard()` and `list_projects()` already existed, already
real, already in use by the web `eng_dashboard` view. Added `reports_core.engineering_dashboard()`
combining project/ECR/task KPIs with up to 8 recent projects (including per-project task progress:
`task_count`/`done_count`/`overdue_tasks`, already computed by `list_projects`' own `LEFT JOIN` —
no new SQL needed there either). New `api_engineering_dashboard` view + `/api/v1/dashboards
/engineering/` route, added to `api_openapi_core.py`'s `ENDPOINTS`. The new `engineering.tsx` mobile
screen shows active/planning project counts, overdue task count, pending ECR count, and a recent-
projects list with a status badge and task-progress line per project — also extended
`StatusBadge`'s color map with `planning` (engineering projects), the fourth mobile-coverage PR in a
row to need a one-line addition there. 2 new tests for `engineering_dashboard()` (KPI+recent-
projects combination, and the 8-project cap); full suite 3421 passed (3419 + 2), `ruff check .` and
`manage.py check` clean; mobile's `tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web`
all clean. Verified end-to-end against the real dev server: hit `/api/v1/dashboards/engineering/`
directly with a real bearer token and confirmed live data (8 real projects across every status, 8
real ECRs, real overdue-task counts) matches the TypeScript interface exactly, including a project
with a null `due_date`. §6.9's explicit zero-coverage list now drops to **5**: `customers`, `it`,
`legal`, `marketing`, `payroll`. Four departments running (Personnel, Accounting, Customer Service,
Engineering) have now all had a pre-existing dashboard function reused rather than needing real new
backend work — at this point the working assumption should flip: **check the department's own
`*_core.py` for a `get_*_dashboard`/`*_dashboard` function before doing anything else**, since it
has been there every single time so far.

---

**2026-08-28, five for five:** Closed **Customers** — the pattern held a fifth consecutive time.
No `customers_core.py` file exists (there never was one); the department's real logic lives in
`credit_core.py` (credit accounts, applications, collections — this is the credit/collections
risk-management domain, distinct from Sales' order pipeline and Customer Service's support
tickets) and `contacts_core.py`. `credit_core.get_credit_dashboard()` and
`list_collection_activities()` already existed and were already in real use by the web
`credit_dashboard` view. Added `reports_core.customers_dashboard()` combining the two — filtering
`list_collection_activities()`'s results down to Open/In Progress/Escalated (matching the same
filter `credit_dashboard`'s own view already applies) rather than duplicating the query. New
`api_customers_dashboard` view + `/api/v1/dashboards/customers/` route, added to
`api_openapi_core.py`'s `ENDPOINTS`. The new `customers.tsx` mobile screen shows accounts-at-risk
count, total credit exposure, pending credit applications, open collections, and a recent
collection-activity list — this one reused the shared `StatusBadge` component directly rather than
building a second local status-color map (its `escalated`/`closed` colors were added to
`StatusBadge`'s own map, the fifth mobile-coverage PR in a row to touch it). 2 new tests for
`customers_dashboard()` (KPI+recent-collections combination including the open/closed status
filter, and the contact-name fallback when no company is linked); full suite 3423 passed
(3421 + 2), `ruff check .` and `manage.py check` clean (one line-length fixup needed in the new
`ENDPOINTS` entry); mobile's `tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web` all
clean. Verified end-to-end against the real dev server: hit `/api/v1/dashboards/customers/`
directly with a real bearer token and confirmed live data (11 real credit accounts, real exposure
total, 5 real open/escalated collection activities with real customer names and promised amounts)
matches the TypeScript interface exactly. §6.9's explicit zero-coverage list now drops to **4**:
`it`, `legal`, `marketing`, `payroll`. Five for five on the "check `*_core.py` for an existing
dashboard function first" pattern — worth checking `it_core.py`, `legal_core.py`,
`marketing_core.py`, and `payroll_core.py` next before assuming any of them is the one that finally
breaks the streak.

---

**2026-08-28, six for six:** Closed **IT** — the pattern held a sixth consecutive time, and this
was the simplest case yet. `it_core.get_it_dashboard()` already existed, was already in real use by
the web `it_dashboard` view, and — unlike the four departments before it (Accounting, Customer
Service, Engineering, Customers all needed a new `reports_core.*_dashboard()` wrapper combining two
separate functions) — already bundled its `recent_tickets` list directly into its own return dict.
So this needed no `reports_core` change at all: just a new `api_it_dashboard` view calling
`it_core.get_it_dashboard()` straight through, plus `/api/v1/dashboards/it/` route, added to
`api_openapi_core.py`'s `ENDPOINTS` (with the same line-length wrap the Customers entry needed).
Zero new core logic means zero new tests — full suite held at 3423 passed, `ruff check .` and
`manage.py check` clean. The new `it.tsx` mobile screen shows open/critical/in-progress ticket
counts and assets-in-repair, plus a recent-tickets list with requester/department/issue type and a
priority tag; `resolved` was added to `StatusBadge`'s shared color map (the sixth mobile-coverage
PR in a row to touch it) for the ticket status badge, while ticket *priority* (critical/high/
medium/low) got its own small local color helper inside `it.tsx` rather than being folded into
`StatusBadge`, since priority and status are different axes on the same ticket and conflating them
into one shared map would have made both harder to read. Mobile's `tsc --noEmit`/`expo-doctor`
(21/21)/`expo export --platform web` all clean. Verified end-to-end against the real dev server:
hit `/api/v1/dashboards/it/` directly with a real bearer token and confirmed live data (13 real
tickets across every status including 2 unresolved critical, 16 real assets with 1 in repair)
matches the TypeScript interface exactly. §6.9's explicit zero-coverage list now drops to **3**:
`legal`, `marketing`, `payroll`. Six for six on the "check `*_core.py` for an existing dashboard
function first" pattern, and the first time the reused function needed no wrapper at all — worth
checking `legal_core.py`, `marketing_core.py`, and `payroll_core.py` next the same way before
assuming either the pattern or the "needs a wrapper" sub-pattern holds a seventh time.

---

**2026-08-28, seven for seven:** Closed **Legal** — same shape as IT, both the department-dashboard
pattern and the no-wrapper-needed sub-pattern held again. `legal_core.get_legal_dashboard()`
already existed, was already in real use by the web `_legal.py` dashboard view, and already bundled
`recent_contracts` directly into its own return dict — so again no `reports_core` change, just a
new `api_legal_dashboard` view calling `legal_core.get_legal_dashboard()` straight through, plus
`/api/v1/dashboards/legal/` route, added to `api_openapi_core.py`'s `ENDPOINTS` (wrapped across two
lines like the Customers/IT entries). Zero new core logic, zero new tests — full suite held at 3423
passed, `ruff check .` and `manage.py check` clean. The new `legal.tsx` mobile screen shows active-
contract count, pending-compliance count, open-litigation count, and a recent-contracts list with
counterparty/type/value/end-date and a status badge; `active`/`renewed`/`expired`/`terminated` were
added to `StatusBadge`'s shared color map (the seventh mobile-coverage PR in a row to touch it) to
cover `legal_core.CONTRACT_STATUSES` in full. Mobile's `tsc --noEmit`/`expo-doctor` (21/21)/
`expo export --platform web` all clean. Verified end-to-end against the real dev server: hit
`/api/v1/dashboards/legal/` directly with a real bearer token and confirmed live data (13 real
contracts spanning Active/Draft/Expired, 13 compliance items, 6 litigation cases) matches the
TypeScript interface exactly. §6.9's explicit zero-coverage list now drops to **2**: `marketing`,
`payroll`. Seven for seven on the "check `*_core.py` for an existing dashboard function first"
pattern, and two in a row needing no wrapper — worth checking `marketing_core.py` and
`payroll_core.py` next the same way, though at this point either remaining department breaking the
streak would be the more notable outcome.

---

**2026-08-28, eight for eight:** Closed **Marketing** — same shape again, three departments in a
row now with no wrapper needed. `marketing_core.get_marketing_dashboard()` already existed, was
already in real use by the web `_marketing.py` dashboard view, and already bundled
`recent_campaigns` directly into its own return dict — so once again no `reports_core` change, just
a new `api_marketing_dashboard` view calling `marketing_core.get_marketing_dashboard()` straight
through, plus `/api/v1/dashboards/marketing/` route, added to `api_openapi_core.py`'s `ENDPOINTS`
(wrapped across two lines like the Legal/IT/Customers entries). Zero new core logic, zero new
tests — full suite held at 3423 passed, `ruff check .` and `manage.py check` clean. The new
`marketing.tsx` mobile screen shows active/planned campaign counts, new/qualified lead counts,
published/draft content counts, and a recent-campaigns list with channel/objective/date-range/
budget and a status badge; `planned`/`paused` were added to `StatusBadge`'s shared color map (the
eighth mobile-coverage PR in a row to touch it) to cover `marketing_core.CAMPAIGN_STATUSES` in full
(`active`/`completed`/`cancelled` were already there from earlier departments). Mobile's
`tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web` all clean. Verified end-to-end
against the real dev server: hit `/api/v1/dashboards/marketing/` directly with a real bearer token
and confirmed live data (10 real campaigns spanning Planned/Active/Completed, 11 leads, 10 content
items) matches the TypeScript interface exactly. §6.9's explicit zero-coverage list now drops to
**1**: `payroll` — the last department standing. Eight for eight on the "check `*_core.py` for an
existing dashboard function first" pattern, and three in a row needing no wrapper — `payroll_core.py`
is the one to check next, and closing it would mean full 17/17 mobile department coverage.

---

**2026-08-28, nine for nine — full 17/17 mobile department coverage:** Closed **Payroll**, the last
department in §6.9's original zero-coverage list. This is the one that finally broke the
no-wrapper-needed streak (three departments running: IT, Legal, Marketing) but not the underlying
"check `*_core.py` first" pattern — `payroll_core.py` has no single `get_payroll_dashboard()`-shaped
function, only `get_dashboard_counts()` (KPI dict) and `list_payroll_runs()` (all runs) as separate
pieces, exactly the shape the web `payroll_dashboard` view itself already combines by hand
(`counts`, `list_payroll_runs()[:5]`, plus two chart-data helpers the mobile screen skips, matching
every other department's chart-free precedent). Added `reports_core.payroll_dashboard()` combining
`get_dashboard_counts()` with the same `[:5]`-sliced `list_payroll_runs()`, mirroring the
Accounting/Customer-Service/Engineering/Customers wrapper shape rather than the three-in-a-row
no-wrapper cases immediately before it. New `api_payroll_dashboard` view + `/api/v1/dashboards/
payroll/` route, added to `api_openapi_core.py`'s `ENDPOINTS`. 2 new tests for
`payroll_dashboard()` (KPI+recent-runs combination, and the 5-run cap matching the web view's own
slice); full suite 3425 passed (3423 + 2), `ruff check .` and `manage.py check` clean. The new
`payroll.tsx` mobile screen shows YTD gross payroll, employees-with-pay-rates, and active-deduction-
type counts, plus a recent-runs list with pay period/employee count/gross/net and a status badge;
`processed` was added to `StatusBadge`'s shared color map (the ninth mobile-coverage PR in a row to
touch it) — `payroll_run.status` turned out to have only one real value in practice (`'processed'`,
the column's own hardcoded default; no status-transition code exists anywhere in `payroll_core.py`).
Mobile's `tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web` all clean. Verified
end-to-end against the real dev server: hit `/api/v1/dashboards/payroll/` directly with a real
bearer token and confirmed live data (7 real payroll runs, $214,158.48 YTD gross, 12 employees with
pay rates of 74 total people) matches the TypeScript interface exactly. **§6.9's zero-coverage list
is now empty — all 17 departments have a mobile screen.** `mobile/app/(tabs)/` has grown from the
9 screens §6.9 originally scored to **19** across this nine-PR series (Finance, Sales, Personnel,
Accounting, Customer Service, Engineering, Customers, IT, Legal, Marketing, Payroll), landing on
either a pure-reuse pattern (Finance, Personnel, IT, Legal, Marketing — 5 of 9) or a small
`reports_core.*_dashboard()` KPI+recent-list wrapper (Accounting, Customer Service, Engineering,
Customers, Payroll — 5 of 9; Sales counted separately as the one genuinely-new-backend case) in
every single instance — no department needed a larger rewrite. This closes the mobile-coverage gap
named in §6.9 to full parity in *breadth* (a screen touching every department) though not
necessarily *depth* (most of these screens are KPI+recent-list dashboards, not full CRUD workflows
the way Work Orders/Requisitions/Quality are) — a fair distinction for whoever revisits this section
next.

---

**2026-08-29:** Extended §6.10's **mobile offline support** to a third screen — Maintenance's work
order list — picked as the next gap once §6.9's mobile-coverage series closed out, since it's the
cheapest remaining item still explicitly flagged as "not yet done" in both CLAUDE.md and
`mobile/README.md`. Mechanical, exactly as those docs predicted: wrapped `maintenance.tsx`'s
existing `load()` in the same `fetchWithOfflineCache()` helper Work Orders' list already uses,
added the shared `OfflineBanner`, and kept the same scope boundary (list is read-cache only;
completing a work order still requires connectivity — not queued, matching the Work Orders
precedent of leaving mutations for a later pass). No backend touched at all — this is a
mobile-only, docs-only change. Mobile's `tsc --noEmit`/`expo-doctor` (21/21)/
`expo export --platform web` all clean; full backend suite untouched (3425 passed, unchanged).
§6.10's offline-covered screen count moves from 2 of ~19 to **3 of 21** — Time Clock (full
read-cache + write-queue), Work Orders list, and now Maintenance list (both read-cache only). The
other 18 screens remain candidates for the same mechanical extension, roughly in order of which
department most plausibly has field/plant-floor connectivity gaps: Quality (NCR list, inspectors on
the shop floor) and Inventory (stock levels, warehouse staff) look like the next two cheapest,
highest-value picks.

---

**2026-08-29, one more:** Extended §6.10's mobile offline support to a fourth screen — Quality's
NCR list — per direct instruction, continuing right where the Maintenance extension left off (it
was explicitly named as the next cheapest pick). Identical mechanical pattern: wrapped
`quality.tsx`'s existing `load()` in `fetchWithOfflineCache()`, added the shared `OfflineBanner`,
kept the same scope boundary (list is read-cache only; creating an NCR still requires
connectivity — not queued, matching the Work Orders/Maintenance precedent). No backend touched —
mobile-only, docs-only change. Mobile's `tsc --noEmit`/`expo-doctor` (21/21)/
`expo export --platform web` all clean; full backend suite untouched (3425 passed, unchanged).
§6.10's offline-covered screen count moves from 3 to **4 of 21** — Time Clock (full read-cache +
write-queue), Work Orders list, Maintenance list, and now Quality's NCR list (all three list
screens read-cache only). Inventory (stock levels, warehouse staff) remains the next cheapest,
highest-value candidate named in the previous entry and still unclaimed.

---

**2026-08-29, and one more still:** Extended §6.10's mobile offline support to a fifth screen —
Inventory's product list — per direct instruction, continuing right where the Quality extension
left off (Inventory was explicitly named as the next candidate two entries running). Same
mechanical pattern with one small wrinkle: `inventory.tsx`'s `load()` returns both `products` and
the reorder `alerts` banner data from a single API response, so the fetcher passed to
`fetchWithOfflineCache()` bundles both into one cached object (`{ products, alerts }`) rather than
caching them separately — keeps the reorder-alert banner working from cache too, not just the
product list. Added the shared `OfflineBanner`; receiving stock still requires connectivity — not
queued, matching the Work Orders/Maintenance/Quality precedent. No backend touched — mobile-only,
docs-only change. Mobile's `tsc --noEmit`/`expo-doctor` (21/21)/`expo export --platform web` all
clean; full backend suite untouched (3425 passed, unchanged). §6.10's offline-covered screen count
moves from 4 to **5 of 21** — Time Clock (full read-cache + write-queue) plus four read-cache-only
list screens (Work Orders, Maintenance, Quality, Inventory). The remaining 16 screens are mostly
detail/CRUD-heavy or admin-facing (Costing, Approvals, Lots, Requisitions, and the 11 department
dashboards) where the "plant-floor worker with no signal" rationale that's driven every screen
picked so far applies less cleanly — worth a fresh look at which of them still justifies the same
mechanical extension versus leaving offline support at its current five-screen scope.
