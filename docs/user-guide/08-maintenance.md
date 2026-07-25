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
week/month/quarter/year or a custom range. Exportable to CSV.

## Work Orders (`/maint/wo/`)

Create a maintenance work order (title, equipment, work type, priority,
assignee/mechanic, requested/due date, notes); mark **Complete**; filter by
status/priority/search.

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

Staff roster: name, trade, shift, phone, status.

## Predictive Maintenance (`/predictive-maintenance/`)

Rolling MTBF and threshold/risk alerts; manually log a sensor reading
(vibration/temperature) and set alert thresholds.

## Asset Performance Management — APM (`/maint/apm/`)

Criticality ranking and repair-vs-replace recommendations per asset.

## Technician Routing (`/maint/routes/`)

Build a technician's route/schedule for a day — the list of stops/work
orders they'll handle.
