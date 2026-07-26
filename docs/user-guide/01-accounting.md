# Accounting

**Menu:** Accounting Main Menu → Accounts Payable, Accounts Receivable, Credit
Dept, Payroll Dept, General Ledger, Multi-Entity, Budget Management, Financial
Reports, Tax Management, Expense Reports, Bank Reconciliation. Managers also
see an **Accounting Manager** menu bundling all of the above plus Payroll and
Financial Reports.

**Who can access it:** Accounting and Finance staff (the two departments
share these screens). An Auditor filed under Accounting or Finance can view
these screens but cannot save changes; Auditors filed under other
departments don't get special access here beyond the cash-flow report noted
in [Getting Started](00-getting-started.md).

## Dashboard (`/acct/`)

AP/AR summary tiles, recent GL journal entries, AP/AR status charts, top
vendors/customers by outstanding balance, and a journal-posting trend chart.

## Accounts Payable (`/ap/`)

- **List** — filter by status, vendor, or date; export to CSV.
- **New Invoice** (`/ap/new`) — enter vendor, invoice number, invoice date,
  due date, amount, description, and (if foreign currency) currency and
  exchange rate.
- **Invoice detail** (`/ap/<id>/`) — record a payment (date, amount, method,
  reference, notes), or change the invoice's status.

## Accounts Receivable (`/ar/`)

Same layout as Accounts Payable, but for customer invoices — create/edit an
invoice, record a customer payment against it.

## General Ledger (`/gl/`)

- **Chart of Accounts** (`/gl/accounts/`) — create or edit an account (number,
  name, type, sub-type, active flag); each account shows its live balance.
- **Journals** (`/gl/journals/`) — list, filter by posted/date; create a new
  multi-line journal entry (account, debit, credit, memo per line), **Post**
  it, or **Void** it.
- **Financial statements** (read-only, date-range filterable): Trial Balance
  (`/gl/trial-balance/`), Income Statement (`/gl/income-statement/`), Balance
  Sheet (`/gl/balance-sheet/`), Cash Flow (`/gl/cash-flow/`).
- **Activity-Based Costing** (`/gl/abc-costing/`) — define cost-pool
  activities and view the ABC allocation report / per-product cost output.

## Multi-Entity (`/companies/`)

- Company master list and detail; **President/VP only** can create companies
  and grant/revoke a user's access to one.
- **Intercompany Transactions** (`/intercompany/`) and **Consolidated
  Financials** (`/consolidated-financials/`) roll multiple companies' books
  together.

## Budget Management (`/fin/budgets/`)

Create a budget (name, fiscal year, status), add or remove budget line items
(category, description, budgeted amount), and view Budget-vs-Actual.

## Tax Management (`/fin/tax/`)

Create or edit a tax filing: type, jurisdiction, period, amount due/paid,
filed/due dates, status, reference number.

## Bank Reconciliation (`/fin/bank-rec/`)

Create bank accounts, add bank statements (beginning/ending balance), and
reconcile them against your books.

## Payroll (linked from this menu)

Accounting can also reach the Payroll department's pages directly — see the
[Payroll guide](10-payroll.md).
