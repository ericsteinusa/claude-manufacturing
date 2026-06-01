# Manufacturing Company Management System

A desktop application built with Python and PyQt6 that provides department management screens for a manufacturing company. The system uses a PostgreSQL database (`company_db`) and launches department-specific sub-menus from a central company main menu.

## Departments

- Accounting
- Budget Management
- Customer Service
- Engineering
- Finance
- Information Technology
- Legal
- Maintenance
- Marketing
- Personnel
- Production
- Purchasing
- Quality Assurance
- Risk Management
- Sales
- Warehouse

### Finance Department

The Finance department provides two menus, each launched as `python -m manufacturing.<menu>`. Both embed their feature widgets directly as tabs:

| Menu | Module | Tabs |
| --- | --- | --- |
| Finance Main menu | `Finance_Main_menu` | Budget, Credit, Payroll, Audit |
| Finance Manager menu | `Finance_mgr_menu` | Budget, General Ledger, Tax, Audit |

The Main menu surfaces day-to-day operational screens (Credit, Payroll), while the Manager menu focuses on oversight (General Ledger, Tax). The shared Budget and Audit screens appear in both. Each tab hosts the corresponding feature widget (`BudgetManagementWidget`, `CreditDeptWidget`, `PayrollDeptWidget`, `GeneralLedgerWidget`, `TaxMgmtWidget`, `AuditMgmtWidget`).

### Legal Department

The Legal department provides two menus, each launched as `python -m manufacturing.<menu>`. Both embed their feature widgets directly as tabs:

| Menu | Module | Tabs |
| --- | --- | --- |
| Legal Main menu | `Legal_Main_menu` | Contracts, Compliance, Litigation, Intellectual Property, Employment Law |
| Legal Manager menu | `Legal_mgr_menu` | Contract Management, Litigation Management, Compliance Management, Corporate Governance |

The Main menu carries the full operational set, while the Manager menu is an oversight-focused subset that adds Corporate Governance. The feature widgets (`ContractsWidget`, `ComplianceWidget`, `LitigationWidget`, `IPWidget`, `EmploymentLawWidget`, `GovernanceWidget`) live in `Legal_mgmt.py`. Each is a database-backed register (filter bar, search, table, and Add/Edit/Delete plus a status action) sharing a common base; their `legal_*` tables are created and seeded automatically on first use.

### Risk Management Department

The Risk Management department provides two menus, each launched as `python -m manufacturing.<menu>`. Both embed their feature widgets directly as tabs:

| Menu | Module | Tabs |
| --- | --- | --- |
| Risk Management Main menu | `Risk_mgmt_Main_menu` | Risk Assessment, Risk Register, Insurance Management, Business Continuity, Compliance & Audit |
| Risk Manager menu | `Risk_mgr_menu` | Risk Register, Key Risk Indicators, Business Continuity, Audit & Compliance |

The Main menu carries the full operational set, while the Manager menu is an oversight-focused subset that adds Key Risk Indicators. The feature widgets (`RiskAssessmentWidget`, `RiskRegisterWidget`, `InsuranceWidget`, `BusinessContinuityWidget`, `ComplianceAuditWidget`, `KRIWidget`) live in `Risk_mgmt.py`. Each is a database-backed register (filter bar, search, table, and Add/Edit/Delete plus a status action) sharing a common base; their `risk_*` tables are created and seeded automatically on first use.

### Marketing Department

The Marketing department's `Marketing_Main_menu` launches two sub-menus, each launched as `python -m manufacturing.<menu>`. Both embed their feature widgets directly as tabs:

| Menu | Module | Tabs |
| --- | --- | --- |
| Marketing menu | `marketing_menu` | Campaigns, Leads & Contacts, Market Research, Content & Collateral, Marketing Analytics |
| Marketing Manager menu | `marketing_mgr_menu` | Campaign Management, Budget Approvals, Performance & ROI, Market Research |

The Marketing menu carries the full operational set, while the Manager menu is an oversight-focused subset that adds Budget Approvals. The feature widgets (`CampaignsWidget`, `LeadsWidget`, `MarketResearchWidget`, `ContentWidget`, `MarketingAnalyticsWidget`, `BudgetApprovalWidget`) live in `Marketing_mgmt.py`. Each is a database-backed register (filter bar, search, table, and Add/Edit/Delete plus a status action) sharing a common base; their `marketing_*` tables are created and seeded automatically on first use.

### Maintenance Department

The Maintenance department's `Maint_Main_menu` launches two sub-menus, each launched as `python -m manufacturing.<menu>`. Both embed their feature widgets directly as tabs:

| Menu | Module | Tabs |
| --- | --- | --- |
| Maintenance menu | `Maint_Maint_menu` | Work Orders, Equipment List, Parts Inventory, Maintenance Schedule, Safety Inspection |
| Maintenance Manager menu | `Maint_mgr_menu` | Work Order Management, Mechanics, Downtime & Reliability, Equipment, Safety Inspections |

The Maintenance menu carries the full operational set, while the Manager menu is an oversight-focused subset that adds Downtime & Reliability and the mechanic roster. The feature widgets (`WorkOrdersWidget`, `EquipmentWidget`, `PartsInventoryWidget`, `MaintScheduleWidget`, `SafetyInspectionWidget`, `DowntimeWidget`, `MechanicsWidget`) live in `Maint_mgmt.py`. Each is a database-backed register (filter bar, search, table, and Add/Edit/Delete plus a status action) sharing a common base; their `maint_*` tables are created and seeded automatically on first use.

On the Manager menu, the Work Order Management screen (`WorkOrderMgmtWidget`) adds an **Assign to Mechanic** action: the manager picks an active mechanic from the roster, which sets the work order's owner and moves it to *Assigned*. The mechanic roster is maintained in the Mechanics tab.

### Quality Assurance Department

The Quality Assurance department's `QA_Main_menu` launches two sub-menus. The operational `Quality_Assurance_menu` / `QA_Lab_menu` cover lab work (Inspections, Defects, Specifications); the Manager menu embeds its feature widgets directly as tabs:

| Menu | Module | Tabs |
| --- | --- | --- |
| QA Manager menu | `QA_Mgr_menu` | Non-Conformance, Corrective Actions, Quality Audits, Supplier Quality |

The Manager menu provides quality-oversight registers. The feature widgets (`NCRWidget`, `CAPAWidget`, `AuditsWidget`, `SupplierQualityWidget`) live in `QA_mgmt.py`. Each is a database-backed register (filter bar, search, table, and Add/Edit/Delete plus a status action) sharing a common base; their `qa_*` tables are created and seeded automatically on first use.

## Requirements

- Python 3.x
- PyQt6
- PostgreSQL
- psycopg2, python-dotenv

Install dependencies:

```bash
pip install PyQt6 psycopg2-binary python-dotenv
```

## Running the Application

Run from the project root as a package module:

```bash
python -m manufacturing.Company_main_menu
```

This opens the main menu where each department button launches its respective sub-menu. The department screens use package-relative imports and are spawned as `python -m manufacturing.<screen>` from the project root, so launch the app the same way rather than running a screen file directly.

## Project Structure

```
manufacturing/
├── Company_main_menu.py      # Main entry point
├── db_pg.py                  # PostgreSQL connection layer
├── *_Main_menu.py            # Department main menus
├── *.ui                      # Qt Designer UI files
├── *.qrc                     # Qt resource files
└── *.png / *.jpg             # Department images and icons
```

## Database

The app connects to a PostgreSQL database (`company_db`) via `psycopg2`, using the connection helpers in `db_pg.py` (`get_db()` / `get_db_connection()`). Connection settings are read from a `.env` file; see `.env.example` for the required variables (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`).
