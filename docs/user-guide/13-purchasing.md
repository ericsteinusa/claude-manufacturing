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

Submit a purchase requisition; a Supervisor or Department Manager in your
department approves or rejects it (President/VP can also approve any
requisition). Pages cover new, pending-approval, approved, and history
views.

## Consultant Time & Charges (`/consultants/`)

Track billable time and itemized expenses for both external consulting
firms and internal-style contract labor, and turn a billing period into a
real payable.

- **Consultants** (`/consultants/`) — the consultant or firm record: name,
  optionally linked to an existing supplier (external) or an existing
  employee (internal-style contract labor), default hourly rate,
  specialty, contact info.
- **Engagements** (`/consultants/engagements/`) — unlike the rest of this
  page, any employee can create an engagement for their own department
  (the same way anyone can file a requisition); Purchasing staff and
  full-access roles see engagements across every department. Log **time
  entries** (date, hours, optional rate override) and **itemized
  charges** (Travel, Materials, Lodging, Software/Tools, Other) against
  an engagement as work happens.
- **Cutting an invoice** — from an engagement's page, pick a date range
  and select **Cut Invoice** to bundle its unbilled time and charges into
  a draft invoice. This is blocked if any time entry has no hourly rate
  anywhere in the fallback chain (the entry's own rate, then the
  engagement's default, then the consultant's default) — set one before
  trying again.
- **Invoices** (`/consultants/invoices/`) — submit a draft invoice for
  approval; once approved it becomes a real Accounts Payable invoice (see
  the [Accounting guide](01-accounting.md#accounts-payable-ap)), so payment
  is recorded the same way as for any other vendor. Rejecting an invoice
  releases its claimed time and charges so they can be billed on a later
  invoice instead.
- **Spend Report** (`/consultants/reports/spend/`, Purchasing managers
  and full-access roles only) — hours and cost broken down by consultant,
  by engagement, and by department, with CSV/Excel export. Cost is left
  blank rather than shown as $0 for any consultant with an unresolved
  hourly rate.

## Blanket POs & Call-Offs (`/blanket-po/`)

A standing agreement with a supplier (ceiling value/quantity, validity
window). Create individual "call-off" releases against it, or cancel it.

## RFQs — Request for Quote (`/rfq/`)

Request quotes from suppliers; create, list, and view responses.

## Consignment (Vendor-Owned) Inventory (`/consignment/`)

Set up a standing consignment agreement, then receive, use, or cancel stock
against it.
