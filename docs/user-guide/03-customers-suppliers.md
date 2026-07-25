# Customers & Suppliers

These master records are shared across several departments: Sales ("Customer
Accounts"), Customer Service ("Customer Entry Screen" / "Customer Accounts"),
and Purchasing ("Product Entry" / "Supplier Entry" / "Vendor Management").

## Customers (`/customers/`)

- **List** — search and export to CSV.
- **New** (`/customers/new/`) — first/last name, company, phone, address,
  city/state/zip, email.
- **Detail** (`/customers/<id>/`) — edit fields, view that customer's Sales
  Order history, and assign a price list to them.

## Suppliers (`/suppliers/`)

Same layout as Customers — list, new, and detail (with that supplier's
Purchase Order history instead of Sales Orders).

- **Supplier Scorecard** (`/suppliers/scorecard/`) — Purchasing and Quality
  Assurance staff can view supplier performance ratings.

## Customer Self-Service Portal (`/portal/`)

A separate login for your customers — not an employee page. Customers
register/log in at `/portal/register/` and `/portal/login/`, then can:

- View their own Sales Orders (`/portal/orders/`).
- View, pay, and download a PDF of their own invoices (`/portal/invoices/`).
- View a shipment and download its packing slip (`/portal/shipments/<id>/`).
- Submit or check the status of a return (`/portal/rma/`).

A customer can only ever see their own orders/invoices/shipments — not
another customer's, even by guessing a URL.

## Supplier Self-Service Portal (`/supplier-portal/`)

Same idea, for your suppliers. They register/log in separately and can:

- View their own Purchase Orders (`/supplier-portal/pos/`).
- View or submit an invoice against a PO (`/supplier-portal/invoices/`).
- View and respond to RFQs sent to them (`/supplier-portal/rfqs/`).
