# Engineering

**Menu:** Engineers, Project Management, Design Documents, Bill of Materials,
Change Orders, Test & Validation, Engineering Reports, Standards &
Compliance. Managers also see an **Engineering Manager** menu with Engineers,
Project Approvals, Resource Management, Budget, and Engineering Reports.

**Who can access it:** Engineering staff. BOM pages are also visible to
Production; document control pages are also visible to Quality Assurance.

## Dashboard (`/eng/`)

Project/task/ECR status charts, KPI cards, standards status.

## Projects (`/eng/projects/`)

Create a project (title, product, engineer, start/due date, status, notes),
add tasks to it (name, assignee, due date, priority, notes), and update task
status.

## Engineering Change Requests — ECRs (`/eng/ecrs/`)

Create or edit an ECR (title, product, project, requested-by, review date,
notes) and change its status.

## Tasks (`/eng/tasks/`)

A standalone task list not tied to a project — assignee, due date, priority,
status.

## Standards & Specs (`/eng/specs/`)

Create or edit a standard/spec: number, title, category, version, status,
review date, description.

## Reports (`/eng/reports/`)

Project status, resource utilization, KPI, and design-review reports.

## Bill of Materials (`/bom/`)

- Pick an item type (Buy/Make) for a product, and update item-master fields
  (item type, lead time, unit of measure).
- Add, edit, or delete a BOM component line (component, quantity required,
  unit, scrap %, notes).
- **Explode** a multi-level BOM for a given quantity to see everything needed
  to build it.

## Design Documents / Document Control (`/documents/`)

Upload a document with a revision number, set its status (draft/in-review/
obsolete), and download the file. Shared with Quality Assurance.
