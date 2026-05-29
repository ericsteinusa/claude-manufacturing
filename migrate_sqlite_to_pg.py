#!/usr/bin/env python3
"""
migrate_sqlite_to_pg.py

Migrates data from manufacturing/company.db (SQLite) into PostgreSQL.

What it does:
  - Clears minimal existing PG test data (preserves Django tables)
  - Creates any missing tables needed for the migrated data
  - Inserts all SQLite data in FK-safe dependency order
  - Hashes plain-text passwords with bcrypt
  - Resets all sequences so future inserts don't collide

Run from the project root:
    python3 migrate_sqlite_to_pg.py
"""

import os
import sqlite3
import bcrypt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'manufacturing', 'company.db')


def pg_connect():
    return psycopg2.connect(
        host=os.environ['DB_HOST'],
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        port=int(os.environ.get('DB_PORT', 5432)),
    )


def _insert_rows(cur, table, col_names, rows):
    """Insert rows, skipping duplicates via savepoints. Returns insert count."""
    if not rows:
        return 0
    placeholders = ', '.join(['%s'] * len(col_names))
    cols = ', '.join(col_names)
    sql = f'INSERT INTO {table} ({cols}) VALUES ({placeholders})'
    count = 0
    for row in rows:
        cur.execute('SAVEPOINT sp')
        try:
            cur.execute(sql, row)
            cur.execute('RELEASE SAVEPOINT sp')
            count += 1
        except psycopg2.errors.UniqueViolation:
            cur.execute('ROLLBACK TO SAVEPOINT sp')
            cur.execute('RELEASE SAVEPOINT sp')
        except Exception as e:
            cur.execute('ROLLBACK TO SAVEPOINT sp')
            cur.execute('RELEASE SAVEPOINT sp')
            print(f'  Warning [{table}]: {e} — row: {row}')
    return count


def _reset_sequence(cur, table, pk_col='id'):
    """Reset the sequence for a table's serial PK to max(id)."""
    try:
        cur.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', '{pk_col}'),
                COALESCE(MAX({pk_col}), 1)
            ) FROM {table}
        """)
    except Exception:
        pass  # table may not have a sequence (e.g. dept uses dept_id)


def _create_missing_tables(cur):
    """Create tables that exist in SQLite but haven't been initialised in PG yet."""

    cur.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id             SERIAL PRIMARY KEY,
            customer_id    INTEGER,
            call           TEXT,
            call_date      TEXT,
            call_time      TEXT,
            completion_date TEXT,
            completion_time TEXT,
            comments_box   TEXT,
            completion_box  INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS calls2 (
            id             SERIAL PRIMARY KEY,
            customer_id    INTEGER,
            call           TEXT,
            call_date      TEXT,
            call_time      TEXT,
            completion_date TEXT,
            completion_time TEXT,
            comments_box   TEXT,
            completion_box  INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gl_account (
            id             SERIAL PRIMARY KEY,
            account_number TEXT NOT NULL UNIQUE,
            account_name   TEXT NOT NULL,
            account_type   TEXT,
            account_sub    TEXT,
            is_active      INTEGER DEFAULT 1,
            notes          TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gl_journal (
            id           SERIAL PRIMARY KEY,
            journal_date TEXT,
            reference    TEXT,
            description  TEXT,
            posted       INTEGER DEFAULT 0,
            created_by   TEXT,
            created_at   TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gl_journal_line (
            id         SERIAL PRIMARY KEY,
            journal_id INTEGER NOT NULL REFERENCES gl_journal(id),
            account_id INTEGER NOT NULL REFERENCES gl_account(id),
            debit      REAL DEFAULT 0.0,
            credit     REAL DEFAULT 0.0,
            memo       TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS department (
            id          SERIAL PRIMARY KEY,
            people_id   INTEGER REFERENCES people(id),
            dept_id     INTEGER REFERENCES dept(dept_id),
            dept_sub_id INTEGER REFERENCES dept_sub(dept_sub_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier (
            id           SERIAL PRIMARY KEY,
            first_name   TEXT,
            last_name    TEXT,
            company_name TEXT,
            phone_number TEXT,
            address      TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT,
            email        TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id             SERIAL PRIMARY KEY,
            supplier_id    INTEGER REFERENCES supplier(id),
            name           TEXT NOT NULL,
            purchase_date  TEXT,
            purchase_price REAL DEFAULT 0.0,
            bin            TEXT DEFAULT '',
            amount         REAL DEFAULT 0.0,
            reorder_point  REAL DEFAULT 0.0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tax (
            id      SERIAL PRIMARY KEY,
            state   TEXT,
            percent REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tax_calendar (
            id          SERIAL PRIMARY KEY,
            tax_type    TEXT,
            description TEXT,
            due_date    TEXT,
            period      TEXT,
            status      TEXT,
            notes       TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_schedule (
            id         SERIAL PRIMARY KEY,
            audit_name TEXT,
            audit_type TEXT,
            department TEXT,
            auditor    TEXT,
            scheduled  TEXT,
            completed  TEXT,
            status     TEXT,
            notes      TEXT
        )
    """)


def migrate():
    sq = sqlite3.connect(SQLITE_PATH)
    sq.row_factory = sqlite3.Row
    pg = pg_connect()
    cur = pg.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ── 1. Clear existing PG app data (preserve Django tables) ──────────────
    print('Clearing existing PostgreSQL app data...')
    clear_order = [
        'user_roles', 'passwd', 'position', 'department',
        'people', 'roles', 'dept_sub', 'dept', 'customer',
        'gl_journal_line', 'gl_journal', 'gl_account',
        'calls', 'calls2', 'supplier', 'product',
        'tax', 'tax_calendar', 'audit_schedule',
    ]
    for table in clear_order:
        try:
            cur.execute(f'TRUNCATE TABLE {table} RESTART IDENTITY CASCADE')
        except psycopg2.errors.UndefinedTable:
            pg.rollback()
        except Exception as e:
            pg.rollback()
            print(f'  Note: could not truncate {table}: {e}')
    pg.commit()

    # ── 2. Create missing tables ─────────────────────────────────────────────
    print('Creating missing tables...')
    _create_missing_tables(cur)
    pg.commit()

    totals = {}

    # ── 3. Migrate in FK-safe order ──────────────────────────────────────────

    # roles
    rows = sq.execute('SELECT id, role_name, description FROM roles').fetchall()
    data = [(r['id'], r['role_name'], r['description'] or '') for r in rows]
    n = _insert_rows(cur, 'roles', ['id', 'role_name', 'description'], data)
    totals['roles'] = n

    # dept
    rows = sq.execute('SELECT dept_id, dept_name FROM dept').fetchall()
    data = [(r['dept_id'], r['dept_name']) for r in rows]
    n = _insert_rows(cur, 'dept', ['dept_id', 'dept_name'], data)
    totals['dept'] = n

    # dept_sub  (SQLite has no dept_id column — insert NULL)
    rows = sq.execute('SELECT dept_sub_id, dept_sub_name FROM dept_sub').fetchall()
    data = [(r['dept_sub_id'], None, r['dept_sub_name']) for r in rows]
    n = _insert_rows(cur, 'dept_sub', ['dept_sub_id', 'dept_id', 'dept_sub_name'], data)
    totals['dept_sub'] = n

    # people  (deduplicate by email — skip id=0 blank record)
    seen_emails = set()
    people_rows = []
    for r in sq.execute('SELECT * FROM people ORDER BY id').fetchall():
        email = (r['email'] or '').strip().lower()
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        people_rows.append((
            r['id'],
            r['first_name'] or '',
            r['last_name'] or '',
            r['emp_id'] or 0,
            r['address'] or '',
            r['city'] or '',
            r['state'] or '',
            r['zip_code'] or '',
            r['email'] or '',
            r['dept_id'],
            r['dept_Sub_id'],  # note capital S in SQLite
        ))
    n = _insert_rows(cur, 'people',
        ['id', 'first_name', 'last_name', 'employee_id',
         'address', 'city', 'state', 'zip_code', 'email',
         'dept_id', 'dept_sub_id'],
        people_rows)
    totals['people'] = n

    # passwd  (hash plain-text passwords with bcrypt)
    rows = sq.execute('SELECT id, people_id, password FROM passwd').fetchall()
    passwd_rows = []
    for r in rows:
        raw = r['password'] or ''
        if raw.startswith('$2b$') or raw.startswith('$2a$'):
            hashed = raw
        else:
            hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
        passwd_rows.append((r['id'], r['people_id'], hashed))
    n = _insert_rows(cur, 'passwd', ['id', 'people_id', 'password'], passwd_rows)
    totals['passwd'] = n

    # user_roles
    rows = sq.execute('SELECT id, people_id, role_id FROM user_roles').fetchall()
    data = [(r['id'], r['people_id'], r['role_id']) for r in rows]
    n = _insert_rows(cur, 'user_roles', ['id', 'people_id', 'role_id'], data)
    totals['user_roles'] = n

    # position  (map SQLite 'position' column → PG 'job_title')
    rows = sq.execute('SELECT id, people_id, position FROM position').fetchall()
    data = [(r['id'], r['people_id'], r['position'] or '') for r in rows]
    n = _insert_rows(cur, 'position', ['id', 'people_id', 'job_title'], data)
    totals['position'] = n

    # customer
    rows = sq.execute('SELECT * FROM customer').fetchall()
    data = [(r['id'], r['first_name'], r['last_name'], r['company_name'],
             r['phone_number'], r['address'], r['city'], r['state'],
             r['zip_code'], r['email']) for r in rows]
    n = _insert_rows(cur, 'customer',
        ['id', 'first_name', 'last_name', 'company_name', 'phone_number',
         'address', 'city', 'state', 'zip_code', 'email'], data)
    totals['customer'] = n

    # department (people-dept mapping)
    rows = sq.execute('SELECT id, people_id, dept_id, dept_sub_id FROM department').fetchall()
    data = [(r['id'], r['people_id'], r['dept_id'], r['dept_sub_id']) for r in rows]
    n = _insert_rows(cur, 'department', ['id', 'people_id', 'dept_id', 'dept_sub_id'], data)
    totals['department'] = n

    # gl_account
    rows = sq.execute('SELECT * FROM gl_account').fetchall()
    data = [(r['id'], r['account_number'], r['account_name'], r['account_type'],
             r['account_sub'], r['is_active'], r['notes']) for r in rows]
    n = _insert_rows(cur, 'gl_account',
        ['id', 'account_number', 'account_name', 'account_type',
         'account_sub', 'is_active', 'notes'], data)
    totals['gl_account'] = n

    # gl_journal
    rows = sq.execute('SELECT * FROM gl_journal').fetchall()
    data = [(r['id'], r['journal_date'], r['reference'], r['description'],
             r['posted'], r['created_by'], r['created_at']) for r in rows]
    n = _insert_rows(cur, 'gl_journal',
        ['id', 'journal_date', 'reference', 'description',
         'posted', 'created_by', 'created_at'], data)
    totals['gl_journal'] = n

    # gl_journal_line
    rows = sq.execute('SELECT * FROM gl_journal_line').fetchall()
    data = [(r['id'], r['journal_id'], r['account_id'],
             r['debit'], r['credit'], r['memo']) for r in rows]
    n = _insert_rows(cur, 'gl_journal_line',
        ['id', 'journal_id', 'account_id', 'debit', 'credit', 'memo'], data)
    totals['gl_journal_line'] = n

    # supplier
    rows = sq.execute('SELECT * FROM supplier').fetchall()
    data = [(r['id'], r['first_name'], r['last_name'], r['company_name'],
             r['phone_number'], r['address'], r['city'], r['state'],
             r['zip_code'], r['email']) for r in rows]
    n = _insert_rows(cur, 'supplier',
        ['id', 'first_name', 'last_name', 'company_name', 'phone_number',
         'address', 'city', 'state', 'zip_code', 'email'], data)
    totals['supplier'] = n

    # product
    rows = sq.execute('SELECT * FROM product').fetchall()
    data = [(r['id'], r['supplier_id'], r['name'], r['purchase_date'],
             r['purchase_price'], r['bin'], r['amount'], r['reorder_point']) for r in rows]
    n = _insert_rows(cur, 'product',
        ['id', 'supplier_id', 'name', 'purchase_date',
         'purchase_price', 'bin', 'amount', 'reorder_point'], data)
    totals['product'] = n

    # calls
    rows = sq.execute('SELECT * FROM calls').fetchall()
    data = [(r['id'], r['customer_id'], r['call'], r['call_date'], r['call_time'],
             r['completion_date'], r['completion_time'],
             r['comments_box'], r['completion_box']) for r in rows]
    n = _insert_rows(cur, 'calls',
        ['id', 'customer_id', 'call', 'call_date', 'call_time',
         'completion_date', 'completion_time', 'comments_box', 'completion_box'], data)
    totals['calls'] = n

    # calls2
    rows = sq.execute('SELECT * FROM calls2').fetchall()
    data = [(r['id'], r['customer_id'], r['call'], r['call_date'], r['call_time'],
             r['completion_date'], r['completion_time'],
             r['comments_box'], r['completion_box']) for r in rows]
    n = _insert_rows(cur, 'calls2',
        ['id', 'customer_id', 'call', 'call_date', 'call_time',
         'completion_date', 'completion_time', 'comments_box', 'completion_box'], data)
    totals['calls2'] = n

    # tax
    rows = sq.execute('SELECT * FROM tax').fetchall()
    data = [(r['id'], r['state'], r['percent']) for r in rows]
    n = _insert_rows(cur, 'tax', ['id', 'state', 'percent'], data)
    totals['tax'] = n

    # tax_calendar
    rows = sq.execute('SELECT * FROM tax_calendar').fetchall()
    data = [(r['id'], r['tax_type'], r['description'], r['due_date'],
             r['period'], r['status'], r['notes']) for r in rows]
    n = _insert_rows(cur, 'tax_calendar',
        ['id', 'tax_type', 'description', 'due_date', 'period', 'status', 'notes'], data)
    totals['tax_calendar'] = n

    # audit_schedule
    rows = sq.execute('SELECT * FROM audit_schedule').fetchall()
    data = [(r['id'], r['audit_name'], r['audit_type'], r['department'],
             r['auditor'], r['scheduled'], r['completed'], r['status'], r['notes']) for r in rows]
    n = _insert_rows(cur, 'audit_schedule',
        ['id', 'audit_name', 'audit_type', 'department',
         'auditor', 'scheduled', 'completed', 'status', 'notes'], data)
    totals['audit_schedule'] = n

    pg.commit()

    # ── 4. Reset sequences ───────────────────────────────────────────────────
    print('Resetting sequences...')
    seq_tables = [
        ('roles', 'id'), ('people', 'id'), ('passwd', 'id'),
        ('user_roles', 'id'), ('position', 'id'), ('customer', 'id'),
        ('department', 'id'), ('gl_account', 'id'), ('gl_journal', 'id'),
        ('gl_journal_line', 'id'), ('supplier', 'id'), ('product', 'id'),
        ('calls', 'id'), ('calls2', 'id'), ('tax', 'id'),
        ('tax_calendar', 'id'), ('audit_schedule', 'id'),
    ]
    for table, pk in seq_tables:
        _reset_sequence(cur, table, pk)
    pg.commit()

    # ── 5. Report ────────────────────────────────────────────────────────────
    print()
    print('Migration complete:')
    print(f'  {"Table":<20} {"Rows inserted":>14}')
    print(f'  {"-"*20} {"-"*14}')
    for table, count in totals.items():
        print(f'  {table:<20} {count:>14}')
    total = sum(totals.values())
    print(f'  {"-"*20} {"-"*14}')
    print(f'  {"TOTAL":<20} {total:>14}')

    sq.close()
    pg.close()


if __name__ == '__main__':
    migrate()
