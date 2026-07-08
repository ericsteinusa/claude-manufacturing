# Manufacturing Company Management System

A Django web application that provides department management screens for a manufacturing company. The system uses a PostgreSQL database (`company_db`); the department menu tree is served as web pages, with every leaf resolving to a real page (see `manufacturing/menus.py` and `manufacturing/views/__init__.py`).

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

Each department's functional areas (Budget, Credit, Payroll, Contracts, Compliance, Litigation, Campaigns, Work Orders, Non-Conformance, Sales Orders, and so on) are reachable from that department's web menu — start at `/dept/<dept>/` and drill down; `menus.py`'s `MENU_TREE` is the source of truth for what's available per department.

## Requirements

- Python 3.x
- PostgreSQL

Install dependencies from `requirements.txt` (includes Django, psycopg2,
bcrypt, python-dotenv, openpyxl, python-barcode, and reportlab — the last two
are needed for the WO/PART/PO barcode label feature):

```bash
pip install -r requirements.txt
```

## Running the Application

Run the Django development server from the project root:

```bash
python manage.py runserver
```

Then sign in at `/` (or `/register/` for a new account) and navigate the department menu tree from the dashboard.

## Project Structure

```
manufacturing/
├── views/                    # Django HTTP handlers (package split by domain)
├── templates/                # Django HTML templates
├── menus.py / urls.py        # Menu tree + routing
├── db_pg.py                  # PostgreSQL connection layer
└── *_core.py                 # Qt-free business logic shared by views/ and seeds/
```

See `CLAUDE.md` for the full directory breakdown.

## Database

The app connects to a PostgreSQL database (`company_db`) via `psycopg2`, using the connection helpers in `db_pg.py` (`get_db()` / `get_db_connection()`). Connection settings are read from a `.env` file; see `.env.example` for the required variables (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`).


 
 
