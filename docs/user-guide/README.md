# Manufacturing System — User Guide

A plain-language guide to using the manufacturing management web
application: how to sign in, what each department's screens let you do, and
who is allowed to do what.

This guide covers the **web application** (`python manage.py runserver`),
used by employees at their desks. If you're looking for the mobile
companion app, see [`mobile/AGENTS.md`](../../mobile/AGENTS.md) and the
"Mobile app" section of the project's [`CLAUDE.md`](../../CLAUDE.md).

## Contents

1. [Getting Started](00-getting-started.md) — signing in, navigation, roles
   & permissions, approvals, cross-cutting tools, self-service, portals
2. [Accounting](01-accounting.md)
3. [Customer Service](02-customer-service.md)
4. [Customers & Suppliers](03-customers-suppliers.md)
5. [Engineering](04-engineering.md)
6. [Finance](05-finance.md)
7. [Information Technology (IT)](06-it.md)
8. [Legal & Risk Management](07-legal-risk.md)
9. [Maintenance](08-maintenance.md)
10. [Marketing](09-marketing.md)
11. [Payroll](10-payroll.md)
12. [Personnel (HR)](11-personnel.md)
13. [Production](12-production.md)
14. [Purchasing](13-purchasing.md)
15. [Quality Assurance (QA/QC)](14-quality.md)
16. [Reports](15-reports.md)
17. [Sales](16-sales.md)
18. [Time Clock](17-time-clock.md)

A polished, printable version of this whole guide is also available as
**`Manufacturing System User Manual.docx`** in this folder.

## A note on department names

A couple of department names differ slightly between the codebase and what
you'll see on screen:

| You'll see on screen | Internal name |
|---|---|
| Quality Assurance | `quality_assurance` (matches "quality" in the codebase) |
| Information Technology | `information_tech` |

**Payroll** and **Time Clock** don't have their own tile on the company-wide
dashboard — they're reached as sub-menus of Accounting and Personnel,
respectively, even though each has a full set of pages of its own.

**Budget Management** and **Risk Management** appear as their own dashboard
tiles for full-access users, each with its own dashboard KPIs. Budget
Management's individual menu leaves still all route to the single
Finance/Accounting Budget page, but Risk Management has its own dedicated
pages (Risk Register, Risk Assessments, Insurance, Business Continuity,
Compliance & Audit) — see the [Legal & Risk guide](07-legal-risk.md).
