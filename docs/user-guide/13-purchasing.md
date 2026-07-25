# Purchasing

**Menu:** Product Entry, Supplier Entry, Purchase Orders, Vendor Management,
Purchase Reports, Receiving, Contract Management, Requisitions. Managers also
see a **Purchasing Manager** menu with PO Approvals, Budget Management,
Vendor Management, Purchasing Reports, and Contract Management.

**Who can access it:** Purchasing staff.

## Dashboard (`/purch/`)

PO status, spend-by-month, top suppliers, PO trend, top items, and
requisition-status charts.

## Purchase Orders (`/po/`)

- **List** — filter by status; export to CSV.
- **New** (`/po/new/`) — number, supplier, order/expected date, status
  (draft/sent), notes, currency.
- **Detail / Edit** (`/po/<id>/`) — add or remove line items (description,
  product, quantity ordered, unit price); advance status through the
  allowed transitions (draft → sent → partial → received, or cancelled);
  receive against a line item (clamped to quantity ordered — also credits
  inventory into the "unassigned" bin); attach a landed-cost allocation.
- **Approval routing:** sending a PO whose total is **over $500**
  automatically routes it to the President/VP approval queue
  (`/po/approvals/`) instead of sending it right away.

## Receiving

Depending on which menu leaf you use, receiving routes to either the
list-based receiver on the PO detail page, or the bin-based put-away flow at
`/wms/receive/` (see the [Production guide](12-production.md#warehouse-management-wms)).

## Vendor / Supplier Management

Same `/suppliers/` pages documented in the
[Customers & Suppliers guide](03-customers-suppliers.md#suppliers-suppliers),
plus the Supplier Scorecard.

## Purchase Reports (`/purch/reports/`)

Spending summary, PO reports, budget-vs-actual, category reports.

## Contract Management (`/purch/contracts/`)

Create or edit a purchasing contract: title, category, supplier, start/end
date, value, status, notes.

## Requisitions

Submit a purchase requisition; a department manager approves or rejects it.
Pages cover new, pending-approval, approved, and history views.

## Blanket POs & Call-Offs (`/blanket-po/`)

A standing agreement with a supplier (ceiling value/quantity, validity
window). Create individual "call-off" releases against it, or cancel it.

## RFQs — Request for Quote (`/rfq/`)

Request quotes from suppliers; create, list, and view responses.

## Consignment (Vendor-Owned) Inventory (`/consignment/`)

Set up a standing consignment agreement, then receive, use, or cancel stock
against it.
