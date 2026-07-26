# Getting Started

This guide explains how to sign in, find your way around, and understand what
you're allowed to see and do. Department-specific guides live alongside this
file (see [README.md](README.md) for the full list).

## Signing in

Go to the site's home page (`/`). Sign in with the **email and password**
your administrator set up for you. If your company has single sign-on (SSO)
configured, you'll also see a **"Sign in with SSO"** button that sends you to
your company's identity provider (Okta, Azure AD, etc.) instead — it logs you
in the same way once you approve it there.

Other account pages you may need:

- **Register** (`/register/`) — self-service account creation, if your
  administrator allows it. You'll need your first/last name, email, a
  password, your employee ID, and your address.
- **Forgot Password** (`/forgot-password/`) — look up your account by email,
  then set a new password.
- **Change Password** (`/change-password/`) — from inside the app, enter your
  current password and a new one.
- **Log Out** (`/logout/`) — ends your session.

## Where you land after signing in

- If you're a **President** or **Vice President**, you land on the
  **company-wide Dashboard** (`/dashboard/`) — tiles linking to every
  department, plus KPI cards (open Work Orders, open POs, open NCRs, open
  Maintenance Work Orders, low/zero-stock counts, cash position, AR/AP
  outstanding) and trend charts.
- Everyone else lands directly on **their own department's menu**
  (`/dept/<your-department>/`). You won't see other departments' menus in the
  navigation — only your own — unless your role grants broader access (see
  below).

## Finding things: the department menu

Every department has its own menu tree. Start at the department's landing
page and drill down through folders until you reach the page you want — a
list, a dashboard, or a form. If your role is a manager (or above), you'll
see extra **manager-only** menu items that regular staff in your department
don't see — things like approvals, budget management, and staff reports.

## Roles: what you can see and do

| Role | Access |
|---|---|
| **President / Vice President** | Everything, everywhere — every department, every manager screen. |
| **Department Manager** | Full access to their own department, including that department's manager-only screens (approvals, budget, staff management, etc.). |
| **Supervisor** | Normal day-to-day access to their own department's screens. No manager sub-menus. |
| **Auditor** | Same department-scoped access as a regular employee — cannot create, edit, submit, or delete anything (every "Save/New/Delete" button is hidden or blocked). The exceptions are the Audit Log and a handful of cross-department read-only reports (cash flow, ATP, supplier scorecard), which Auditors can view regardless of department. |
| **HR / Personnel** | Full access to the Personnel department's screens, regardless of which department they're actually filed under. |

A few things worth knowing:

- Several departments share pages because the underlying data is shared —
  for example, Purchasing, Production, Engineering, and Maintenance can all
  see the same product/inventory records; Purchasing and Quality Assurance
  can both see supplier scorecards; Customer Service, Sales, and Customers
  staff all see the same customer tickets.
- If you try to open a page outside your access, you'll be redirected back to
  your dashboard.
- If you're an **Auditor** and you open a page in your own department that
  you'd normally be able to edit, you can still browse it — but submitting
  the form (Save/Approve/Delete) will bounce you back without making the
  change. Auditors do not get access to other departments' pages beyond the
  Audit Log and the read-only reports noted above.

## Approvals and dollar thresholds

Some transactions require sign-off before they take effect:

- **Purchase Orders over $500**: when a PO is moved to "sent," if its total
  exceeds $500 it is automatically routed to an approval queue
  (`/po/approvals/`) instead of being sent immediately. Only a **President**
  or **Vice President** can approve or reject it there.
- **Purchase Requisitions**: submitted by staff, approved or rejected by a
  Supervisor or Department Manager in the requester's department (President/VP
  can also approve any requisition).
- A **notification bell** in the top navigation shows you unread
  notifications — including when something you submitted has been approved
  or rejected, or when something is waiting on your approval.

## Cross-cutting tools (visible to certain roles everywhere)

These aren't tied to one department — they apply company-wide:

- **Audit Log** (`/audit/`) — President/VP/Auditor only. Shows every tracked
  change to key tables, with before/after values, filterable by table and by
  user.
- **Period Locking** (`/periods/`) — President/VP only. A 13-month calendar
  with Close/Reopen buttons. Once a month is closed, you can't create or edit
  Purchase Orders, Sales Orders, or Work Orders dated into that month — you'll
  get an inline error telling you the period is closed.
- **Fixed Asset Management** (`/assets/fixed/`) — company asset register with
  depreciation schedules.
- **Currency Management** (`/admin/currencies/`) — exchange rates used
  whenever a PO, SO, AP, or AR transaction is in a foreign currency.
- **Approval Rule Management** (`/approval-rules/`) — configures who approves
  what, for departments with custom approval workflows.
- **User Roles** (`/user-roles/`) — President/VP only. Assign or change any
  user's role from a grid.
- **Reports Dashboard** (`/reports/`) and **Custom Report Builder**
  (`/reports/builder/`) — build your own report by picking a table, columns,
  filters, grouping, and sorting; save it privately or share it; export to
  CSV or PDF.

## Employee Self-Service (everyone, regardless of department)

Every logged-in employee — no matter their department — can go to the
**Employee Self-Service** area (`/ess/...`) to:

- View their own pay stubs and year-to-date pay summary.
- Submit or check the status of their own time-off requests.
- View their own performance reviews and training records.
- Edit their own profile.

Everyone can also **clock in and out** (`/time-clock/`) and view their own
hours, regardless of department.

## Customer and Supplier self-service portals

Customers and suppliers do **not** use employee logins. They have separate
portals with their own registration/login:

- **Customer Portal** (`/portal/`) — view their own orders and invoices, pay
  an invoice online, download shipment packing slips, and submit a return
  (RMA).
- **Supplier Portal** (`/supplier-portal/`) — view their own POs, submit
  invoices against a PO, and respond to RFQs.

Each portal only ever shows a customer/supplier their own records — they
cannot see another company's data even by guessing a URL.
