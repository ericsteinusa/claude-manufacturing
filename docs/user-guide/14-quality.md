# Quality Assurance (QA/QC)

**Menu:** Quality Assurance Menu → QA Laboratory Menu (Test Requests, Lab
Results, Inspection Reports, Non-Conformance, Calibration, Sample
Management, Lab Reports). Managers also see a **QA Manager** menu with Audit
Management, Compliance, Corrective Actions, QA Reports, Supplier Quality,
Customer Complaints, and Document Control.

**Who can access it:** Quality Assurance staff.

## Dashboard (`/qa/`)

Open NCR/CAPA/audit counts, defect pareto chart, NCR severity trend,
inspection results, NCR-by-status.

## Non-Conformance Reports — NCRs (`/qa/ncr/`)

Log an NCR: title, source, severity, product, detected date, disposition,
owner, notes. Update it or **Close** it. Exportable.

## CAPA — Corrective/Preventive Actions (`/qa/capa/`)

Create a CAPA: title, type, NCR reference, owner, due date, action plan.
Update it or **Close** it.

## Audits (`/qa/audits/`)

Schedule an audit (title, type, auditor, scheduled date, findings) and mark
it **Complete** with the result.

## Supplier Quality (`/qa/suppliers/`)

Rate a supplier or material: rating, PPM defect rate, last audit date,
status.

## Inspections (`/qa/inspections/`)

Create an inspection (product/work order link, date, inspector, result,
sampling plan, lot quantity); mark pass/fail/on-hold; log or resolve a
defect; record sample-defect counts.

## QA Reports (`/qa/reports/`)

Daily, weekly, monthly, and custom reports.

## Sampling Plans — AQL (`/sampling-plans/`)

Define acceptance-sampling plans used when creating an inspection.

## Certificate of Analysis — CoA (`/qa/coa/`)

Generate a CoA and download it as a PDF.

## Control Plans & FMEA (`/qa/control-plans/`, `/qa/fmea/risk-register/`)

Quality control plans and a Failure-Mode-and-Effects-Analysis risk register.

## Regulatory Compliance Templates (`/qa/compliance/templates/`)

FDA/ISO template and checklist management.

## Document Control (`/documents/`)

Same pages documented in the [Engineering guide](04-engineering.md) — QA is
the other department that manages controlled documents.

## Batch Records (`/batch-records/`)

Generate and download production batch records as a PDF. Shared with
Production.
