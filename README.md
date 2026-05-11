# Manufacturing Company Management System

A desktop application built with Python and PyQt6 that provides department management screens for a manufacturing company. The system uses a SQLite database (`company.db`) and launches department-specific sub-menus from a central company main menu.

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

Install dependencies:

```bash
pip install PyQt6
```

## Running the Application

```bash
cd manufacturing
python Company_main_menu.py
```

This opens the main menu where each department button launches its respective sub-menu.

## Project Structure

```
manufacturing/
├── Company_main_menu.py      # Main entry point
├── connect_db.py             # SQLite database connection
├── company.db                # SQLite database
├── *_Main_menu.py            # Department main menus
├── *.ui                      # Qt Designer UI files
├── *.qrc                     # Qt resource files
└── *.png / *.jpg             # Department images and icons
```

## Database

The app connects to a local SQLite database (`company.db`) via PyQt6's `QSqlDatabase` with the `QSQLITE` driver.
