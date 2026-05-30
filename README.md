# Manufacturing Company Management System

A desktop application built with Python and PyQt6 that provides department management screens for a manufacturing company. The system uses a PostgreSQL database (`company_db`) and launches department-specific sub-menus from a central company main menu.

## Departments

- Accounting
- Customer Service
- Engineering
- Information Technology
- Maintenance
- Marketing
- Personnel
- Production
- Purchasing
- Quality Assurance
- Sales

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
