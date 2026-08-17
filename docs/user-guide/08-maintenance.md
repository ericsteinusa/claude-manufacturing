# Maintenance

**Menu:** Work Orders, Maintenance Schedule, Equipment Maintenance, Parts
Inventory, Maintenance Reports, Safety Inspections, Preventive Maintenance,
Predictive Maintenance. Managers also see a **Maintenance Manager** menu with
Work Order Approvals, Budget Management, and Maintenance Reports.

**Who can access it:** Maintenance staff, plus Production and Purchasing
staff (they need visibility into equipment status and parts).

## Dashboard (`/maint/`)

Overall OEE gauge, 8-week OEE trend, downtime-by-equipment (3 months),
schedule/work-order status breakdown, downtime-by-category.

## OEE Report (`/maint/oee/`)

Per-workcenter Availability / Performance / Quality / OEE %, filterable by
week/month/quarter/year or a custom range. Exportable to CSV. The manager-menu
**Daily Report** and **Weekly Report** leaves route here (pre-filtered to
day/week).

## Labor Time & Cost Report (`/maint/reports/labor/`)

**Who can access it:** the Maintenance Department Manager, or President/VP.
The manager-menu **Cost Analysis** leaf routes here.

Filterable by period (day/week/month/quarter/year or a custom date range)
and work-order status:

- **Work Order Time Variance** — for every work order with an estimated or
  actual hours value, the estimate vs. actual hours, the variance, and the
  labor cost (actual hours × the assigned mechanic's hourly rate).
- **Labor by Mechanic** — for each mechanic matched to a work order's
  "Assigned To" field, total hours tracked vs. estimated, how many work
  orders they were assigned, their hourly rate, and cost per work order plus
  a running total.

Both tables export to CSV independently via the toolbar. The **Downtime
Report** leaf is unaffected and still routes to Downtime (`/maint/downtime/`)
below.

## Work Orders (`/maint/wo/`)

Create a maintenance work order (title, equipment, work type, priority,
assignee/mechanic, requested/due date, estimated hours, notes); mark
**Complete** (optionally recording actual hours worked at that point); filter
by status/priority/search. Estimated and actual hours feed the Labor Time &
Cost Report above.

## Equipment (`/maint/equipment/`)

Register or edit equipment: name, asset tag, location, manufacturer, install
date, last service date, status.

## PM Schedules (`/maint/schedule/`)

Create a recurring preventive-maintenance task (task, equipment, frequency,
assignee, last-done/next-due date), and mark it **Complete** when done.

## Safety Inspections (`/maint/inspections/`)

Schedule an inspection (area, type, inspector, date) and mark it **Complete**
with the result.

## Downtime (`/maint/downtime/`)

Log downtime (equipment, reason, category, date, hours, cost) and
**Resolve** it once addressed.

## Parts (`/maint/parts/`)

Maintain the spare-parts inventory: name, part number, category, location,
quantity, reorder level, unit cost, status.

## Mechanics (`/maint/mechanics/`)

Staff roster: name, trade, shift, phone, status, hourly rate (used to
compute cost on the Labor Time & Cost Report above).

## Predictive Maintenance (`/predictive-maintenance/`)

Rolling MTBF and threshold/risk alerts; manually log a sensor reading
(vibration/temperature) and set alert thresholds.

## Asset Performance Management — APM (`/maint/apm/`)

Criticality ranking and repair-vs-replace recommendations per asset.

## Technician Routing (`/maint/routes/`)

Build a technician's route/schedule for a day — the list of stops/work
orders they'll handle.
