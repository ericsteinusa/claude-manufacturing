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
