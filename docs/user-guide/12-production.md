# Production

**Menu:** Production (Work Orders, MRP Planning, Production Schedule,
Inventory, Equipment Status, Quality Control, Production Reports, Labor
Tracking), Shipping, and Shop Floor (Production/Downtime Entry, Shift Plan,
Live OEE Dashboard, Shop Floor TV Display). Managers also see a **Production
Manager** menu with Shipping, Production Reports, Resource Management, and
Budget.

**Who can access it:** Production staff. Inventory/BOM pages are also shared
with Engineering, Maintenance, and Purchasing since they all need the same
product/material data.

## Dashboard (`/prod/`)

Daily-output trend, work-order status, top products, on-time %, scrap/rework
by operation, monthly completed-work-order trend.

## Production Reports (`/prod/reports/`)

Work-order status breakdown, completed-count today/this-week/this-month,
overdue work orders (product, due date, status), and low-stock products
nearing their reorder point. The "Production Reports" manager-menu leaves
(Daily Production, Weekly Summary, Efficiency, Scrap, KPI Dashboard) route to
this single page, as does the "Resource Management" leaf **Resource
Reports**. The other Resource Management leaves route to the Dashboard
(`/prod/`) or Capacity Planning (`/prod/schedule/capacity/`) above, and the
manager-menu **Budget** leaves route to Finance's Budget page — see the
[Accounting guide](01-accounting.md#budget-management-finbudgets).

## Labor Time & Cost Report (`/prod/reports/labor/`)

**Who can access it:** the Production Department Manager, or President/VP.
All four "Labor Tracking" menu leaves (Current Labor, Labor by Shift, Labor
by Job, Labor Reports) route here.

Filterable by period (day/week/month/quarter/year or a custom date range)
and work-order status:

- **Work Order Time Variance** — for every work order with routing
  operations, standard hours vs. actual hours, the variance, and the labor
  cost (actual hours × the operation's workcenter rate).
- **Labor by Person** — for each person whose name matches a work order's
  "Completed By" or "Assigned To", total hours tracked vs. standard, how
  many work orders they touched, and cost per work order plus a running
  total. Cost only shows for hourly-paid employees — salaried staff show
  hours and work-order count with no dollar figure, since their pay rate
  isn't an hourly rate.

Both tables export to CSV independently via the toolbar.

## Work Orders (`/wo/`)

- **New** (`/wo/new/`) — number, product, description, quantity, start/due
  date, notes.
- **Detail** (`/wo/<id>/`) — add materials; change status (draft → open →
  in_progress → completed/cancelled); forward/backward capacity-based
  scheduling buttons; view routing operations and rolled-up labor/actual
  cost.
- **Assigning a work order** — on that same detail page, a Production
  Department Manager or Supervisor (or President/VP) picks a name from the
  **Assigned To** dropdown and clicks **Assign**; only people in the
  Production department appear in the list. There's no separate reassign
  page — pick a different name (or "— Unassigned —") and click Assign
  again. The person assigned gets an in-app notification (the bell icon in
  the top bar) right away.

## MRP — Material Requirements Planning (`/mrp/`)

1. Review net demand vs. on-hand and scheduled receipts.
2. Click **Run MRP Plan** (optionally including forecast demand) to produce
   a make/buy plan.
3. Review the plan and select which lines to release, overriding quantities
   if needed.
4. Releasing a line **auto-creates** a Work Order (for a "make" item) or a
   Purchase Order (for a "buy" item).

There's also a **Safety Stock** page to bulk-edit reorder points across
products.

## Production Schedule

- **Schedule** (`/prod/schedule/`) and a drag-to-reschedule **Gantt view**
  (`/prod/schedule/gantt/`).
- **Capacity Planning** (`/prod/schedule/capacity/`) — workcenter load and
  bottleneck check.

## Inventory (`/inventory/`)

- List, filter by item type; create a new item.
- **Detail** (`/inventory/<id>/`) — record a transaction: receive, issue, or
  adjust.
- **Dashboard** (`/inventory/dashboard/`) — stock KPIs, top-value products,
  14-day receive/issue trend, top movers, value-by-supplier.
- **Cycle Counts** (`/inventory/cycle-counts/`) — schedule or perform a
  physical count.
- **Valuation** (`/inventory/valuation/`) — FIFO/LIFO/weighted-average
  costing.

## Lots & Serials (`/lots/`)

Create a lot (product, quantity, received/expiry date); track its
genealogy; add serial numbers; change lot status; expiry alerts.

## Routing & Workcenters

- **Workcenters** (`/workcenters/`) — define capacity hours/day, labor rate,
  and a working-day calendar with exceptions; per-workcenter calendar view.
- **Routing** (`/routing/<product_id>/`) — define a product's routing steps
  (operation, workcenter, standard hours).

## Costing

- **Cost roll** (`/costs/<product_id>/`) — roll a standard cost and view cost
  history.
- **WO actual cost** (`/wo/<id>/cost/`) — compute and save a work order's
  actual cost and variance.

## Shop Floor

- **Entry** (`/shop-floor/entry/`) — an operator logs production or downtime
  by shift.
- **Shift Plan** (`/shop-floor/plan/`).
- **Live OEE Dashboard** (`/shop-floor/`) and a no-interaction **TV Display**
  (`/shop-floor/tv/`) for a kiosk screen.

## Specialized manufacturing modes

- **Recipe/Formula Management** (`/recipes/`) — for process manufacturing.
- **Repetitive Manufacturing** (`/repetitive/`) — rate-based schedules.
- **Configure-to-Order** (`/cto/`) — configure a sales-order line's product
  options.
- **Scenario Planning** (`/scenarios/`) — create and "run" a what-if
  scenario.

## Shipping (also under Production's menu)

- **Shipments** (`/prod/shipping/`) — carrier, tracking number, ship date,
  status, line items.
- **Tracking Dashboard** (`/prod/tracking/`), **Delivery Status**
  (`/prod/delivery-status/`), **Daily Report** (`/prod/daily-report/`),
  **Performance** (`/prod/performance/`).

## Returns (RMA) (`/prod/returns/`)

Create an RMA (linked Sales Order, customer, reason, description) and update
its status/resolution. Reports available at `/prod/returns/reports/`.

## Warehouse Management (WMS)

Under Production → Shipping → Warehouse Management:

- **Warehouses** (`/wms/warehouses/`) and **Bins** (`/wms/bins/`).
- **Putaway Rules** (`/wms/putaway-rules/`).
- **Receive** (`/wms/receive/`) — receive against an open PO line directly
  into a bin.
- **Picks** (`/wms/picks/`) — pick detail, pack station, ship-confirm.
- **Waves** (`/wms/waves/`) — wave picking.
- **Transfers** (`/wms/transfers/`) — move stock between warehouses/bins.
- **RFID** (`/wms/rfid/readers/`, `/wms/rfid/tags/`) — reader and tag
  management.
