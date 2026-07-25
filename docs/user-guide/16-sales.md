# Sales

**Menu:** Sales Orders, Customer Accounts, Sales Reports, Quotes, Leads &
Opportunities, Contracts, Sales Forecasting, AI Demand Forecast. Managers
also see a **Sales Manager** menu with Sales Targets, Territory Management,
Commission Tracking, and Staff Performance.

**Who can access it:** Sales staff.

## Dashboard (`/sales/`)

Revenue-by-month, top customers/products, order-status/lead-status charts,
quote funnel.

## Sales Orders (`/sales/orders/`, also `/so/`)

- **New** — number, customer, order/ship date, notes, currency; add/remove
  line items.
- **Detail** — change status (draft → confirmed → shipped → invoiced/
  cancelled). Confirming an order can trigger an **Available-to-Promise /
  Capable-to-Promise** warning if stock or capacity is short, with an
  "override and confirm anyway" option.

## Quotes (`/sales/quotes/`)

Create or update a quote: customer, description, amount, owner, quote/
valid-until date, status. Includes a convert-to-order workflow.

## Sales Targets (`/sales/targets/`)

Set a rep's target vs. actual per period/region.

## Leads & Opportunities (`/sales/leads/`)

Create or edit a lead: company, contact, source, status, priority,
estimated value, owner.

## Contracts (`/sales/contracts/`)

Create or edit a sales contract: customer, title, value, start/end/renewal
date, owner, status.

## Forecasting (`/sales/forecast/`)

Create a forecast (rep, period, fiscal year, product line, expected value,
probability, status), record actuals, and view variance/attainment %.

- **Demand pivot** (`/sales/demand/`) — product × quarter revenue/unit pivot
  with forecast comparison.
- **AI Demand Forecast** (`/demand-forecast/`) — generate an AI-driven
  forecast with an actual-vs-forecast overlay.

## Territory Management (`/sales/territories/`)

Create or edit territories (name, region, assigned rep, status) and view
performance-by-territory.

## Commission Tracking (`/sales/commissions/`)

Record a commission (rep, period, plan, sale amount, commission, status);
view paid-commission history; manage commission plan definitions (flat rate
or tiered).

## Staff Performance (`/sales/performance/`)

Rep performance dashboard; schedule/record a performance review (rating,
strengths, improvements, goals); log coaching notes.

## Price Lists & Promotions (`/price-lists/`, `/promotions/`)

Define tiered price lists and discount promotions assignable to customers.
Shared with Accounting.

## EDI Integration (`/edi/`)

- Upload an inbound 850 to auto-create a Sales Order (`/edi/850/upload/`).
- Download outbound acknowledgment/ship-notice/invoice documents (855/856/
  810).
- View the EDI transaction log (`/edi/log/`).

## e-Commerce Integration (`/ecommerce/`)

Manage store connections, receive order webhooks, push shipment
confirmations, and view the sync log.
