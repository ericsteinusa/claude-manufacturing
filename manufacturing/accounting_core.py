"""
accounting_core.py — Qt-free data layer for Accounting web views.
Tables: ap_invoice, ap_payment, ar_invoice, ar_payment,
        gl_account, gl_journal, gl_journal_line
No PyQt6, no commit inside any function.
"""

import datetime

INVOICE_STATUSES = ('open', 'partial', 'paid', 'overdue', 'cancelled')
PAYMENT_METHODS  = ('Check', 'ACH', 'Wire', 'Credit Card', 'Cash', 'Other')
ACCOUNT_TYPES    = ('Asset', 'Liability', 'Equity', 'Revenue', 'COGS', 'Expense')
DEBIT_NORMAL     = frozenset({'Asset', 'COGS', 'Expense'})


def _today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Vendor / Customer helpers
# ---------------------------------------------------------------------------

def load_vendors(conn):
    rows = conn.execute(
        "SELECT id, company_name, first_name, last_name FROM supplier"
        " ORDER BY company_name, last_name"
    ).fetchall()
    out = []
    for r in rows:
        company = r['company_name'] or ''
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
        out.append({'id': r['id'], 'label': company if company else name})
    return out


def load_customers(conn):
    rows = conn.execute(
        "SELECT id, company_name, first_name, last_name FROM customer"
        " ORDER BY company_name, last_name"
    ).fetchall()
    out = []
    for r in rows:
        company = r['company_name'] or ''
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
        out.append({'id': r['id'], 'label': company if company else name})
    return out


# ---------------------------------------------------------------------------
# Accounts Payable
# ---------------------------------------------------------------------------

def get_ap_dashboard(conn):
    row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE i.status='open')    AS open_count,
            COUNT(*) FILTER (WHERE i.status='overdue') AS overdue_count,
            COALESCE(SUM(i.amount) FILTER (WHERE i.status IN ('open','partial','overdue')), 0)
                AS total_outstanding,
            COALESCE(SUM(i.amount), 0) AS total_invoiced,
            COUNT(*) AS total_invoices
        FROM ap_invoice i
    """).fetchone()
    return dict(row) if row else {
        'open_count': 0, 'overdue_count': 0,
        'total_outstanding': 0.0, 'total_invoiced': 0.0, 'total_invoices': 0,
    }


def list_ap_invoices(conn, status=None, vendor_id=None,
                     date_from=None, date_to=None):
    conds = []
    params = []
    if status:
        conds.append('i.status = %s')
        params.append(status)
    if vendor_id:
        conds.append('i.vendor_id = %s')
        params.append(vendor_id)
    if date_from:
        conds.append('i.due_date >= %s')
        params.append(date_from)
    if date_to:
        conds.append('i.due_date <= %s')
        params.append(date_to)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    rows = conn.execute(f"""
        SELECT i.id, i.invoice_number, i.invoice_date, i.due_date,
               i.amount, i.description, i.status, i.created_by,
               s.company_name, s.first_name, s.last_name,
               COALESCE(SUM(p.amount), 0) AS paid
        FROM ap_invoice i
        LEFT JOIN supplier s ON s.id = i.vendor_id
        LEFT JOIN ap_payment p ON p.invoice_id = i.id
        {where}
        GROUP BY i.id, i.created_by, s.company_name, s.first_name, s.last_name
        ORDER BY i.due_date ASC NULLS LAST, i.id DESC
    """, params or None).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        company = r['company_name'] or ''
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
        d['vendor_label'] = company if company else name
        d['balance'] = r['amount'] - r['paid']
        out.append(d)
    return out


def get_ap_invoice(conn, inv_id):
    row = conn.execute("""
        SELECT i.*, s.company_name, s.first_name, s.last_name,
               COALESCE(SUM(p.amount), 0) AS paid
        FROM ap_invoice i
        LEFT JOIN supplier s ON s.id = i.vendor_id
        LEFT JOIN ap_payment p ON p.invoice_id = i.id
        WHERE i.id = %s
        GROUP BY i.id, s.company_name, s.first_name, s.last_name
    """, (inv_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    company = row['company_name'] or ''
    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    d['vendor_label'] = company if company else name
    d['balance'] = row['amount'] - row['paid']
    return d


def create_ap_invoice(conn, vendor_id, invoice_number, invoice_date,
                      due_date, amount, description, created_by):
    if not invoice_number:
        raise ValueError('Invoice number is required')
    row = conn.execute(
        "INSERT INTO ap_invoice (vendor_id, invoice_number, invoice_date,"
        " due_date, amount, description, status, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,'open',%s) RETURNING id",
        (vendor_id or None, invoice_number,
         invoice_date or _today(),
         due_date or None,
         float(amount or 0), description or '', created_by or '')
    ).fetchone()
    return row['id']


def update_ap_invoice(conn, inv_id, vendor_id, invoice_number, invoice_date,
                      due_date, amount, description, status):
    if not invoice_number:
        raise ValueError('Invoice number is required')
    if status not in INVOICE_STATUSES:
        status = 'open'
    conn.execute(
        "UPDATE ap_invoice SET vendor_id=%s, invoice_number=%s,"
        " invoice_date=%s, due_date=%s, amount=%s, description=%s,"
        " status=%s WHERE id=%s",
        (vendor_id or None, invoice_number,
         invoice_date or _today(), due_date or None,
         float(amount or 0), description or '', status, inv_id)
    )


def set_ap_status(conn, inv_id, status):
    if status not in INVOICE_STATUSES:
        status = 'open'
    conn.execute("UPDATE ap_invoice SET status=%s WHERE id=%s", (status, inv_id))


def list_ap_payments(conn, inv_id):
    return conn.execute(
        "SELECT * FROM ap_payment WHERE invoice_id=%s ORDER BY payment_date DESC",
        (inv_id,)
    ).fetchall()


def record_ap_payment(conn, inv_id, payment_date, amount, method, reference, notes):
    amount = float(amount or 0)
    if method not in PAYMENT_METHODS:
        method = 'Check'
    conn.execute(
        "INSERT INTO ap_payment (invoice_id, payment_date, amount,"
        " payment_method, reference, notes) VALUES (%s,%s,%s,%s,%s,%s)",
        (inv_id, payment_date or _today(), amount, method,
         reference or '', notes or '')
    )
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM ap_payment WHERE invoice_id=%s",
        (inv_id,)
    ).fetchone()['total']
    inv = conn.execute("SELECT amount FROM ap_invoice WHERE id=%s", (inv_id,)).fetchone()
    if inv:
        if paid <= 0:
            new_status = 'open'
        elif paid >= inv['amount']:
            new_status = 'paid'
        else:
            new_status = 'partial'
        conn.execute("UPDATE ap_invoice SET status=%s WHERE id=%s", (new_status, inv_id))


# ---------------------------------------------------------------------------
# Accounts Receivable
# ---------------------------------------------------------------------------

def get_ar_dashboard(conn):
    row = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE i.status='open')    AS open_count,
            COUNT(*) FILTER (WHERE i.status='overdue') AS overdue_count,
            COALESCE(SUM(i.amount) FILTER (WHERE i.status IN ('open','partial','overdue')), 0)
                AS total_outstanding,
            COALESCE(SUM(i.amount), 0) AS total_invoiced,
            COUNT(*) AS total_invoices
        FROM ar_invoice i
    """).fetchone()
    return dict(row) if row else {
        'open_count': 0, 'overdue_count': 0,
        'total_outstanding': 0.0, 'total_invoiced': 0.0, 'total_invoices': 0,
    }


def list_ar_invoices(conn, status=None, customer_id=None,
                     date_from=None, date_to=None):
    conds = []
    params = []
    if status:
        conds.append('i.status = %s')
        params.append(status)
    if customer_id:
        conds.append('i.customer_id = %s')
        params.append(customer_id)
    if date_from:
        conds.append('i.due_date >= %s')
        params.append(date_from)
    if date_to:
        conds.append('i.due_date <= %s')
        params.append(date_to)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    rows = conn.execute(f"""
        SELECT i.id, i.invoice_number, i.invoice_date, i.due_date,
               i.amount, i.description, i.status, i.created_by,
               c.company_name, c.first_name, c.last_name,
               COALESCE(SUM(p.amount), 0) AS received
        FROM ar_invoice i
        LEFT JOIN customer c ON c.id = i.customer_id
        LEFT JOIN ar_payment p ON p.invoice_id = i.id
        {where}
        GROUP BY i.id, i.created_by, c.company_name, c.first_name, c.last_name
        ORDER BY i.due_date ASC NULLS LAST, i.id DESC
    """, params or None).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        company = r['company_name'] or ''
        name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
        d['customer_label'] = company if company else name
        d['balance'] = r['amount'] - r['received']
        out.append(d)
    return out


def get_ar_invoice(conn, inv_id):
    row = conn.execute("""
        SELECT i.*, c.company_name, c.first_name, c.last_name,
               COALESCE(SUM(p.amount), 0) AS received
        FROM ar_invoice i
        LEFT JOIN customer c ON c.id = i.customer_id
        LEFT JOIN ar_payment p ON p.invoice_id = i.id
        WHERE i.id = %s
        GROUP BY i.id, c.company_name, c.first_name, c.last_name
    """, (inv_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    company = row['company_name'] or ''
    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    d['customer_label'] = company if company else name
    d['balance'] = row['amount'] - row['received']
    return d


def create_ar_invoice(conn, customer_id, invoice_number, invoice_date,
                      due_date, amount, description, created_by):
    if not invoice_number:
        raise ValueError('Invoice number is required')
    row = conn.execute(
        "INSERT INTO ar_invoice (customer_id, invoice_number, invoice_date,"
        " due_date, amount, description, status, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,'open',%s) RETURNING id",
        (customer_id or None, invoice_number,
         invoice_date or _today(),
         due_date or None,
         float(amount or 0), description or '', created_by or '')
    ).fetchone()
    return row['id']


def update_ar_invoice(conn, inv_id, customer_id, invoice_number, invoice_date,
                      due_date, amount, description, status):
    if not invoice_number:
        raise ValueError('Invoice number is required')
    if status not in INVOICE_STATUSES:
        status = 'open'
    conn.execute(
        "UPDATE ar_invoice SET customer_id=%s, invoice_number=%s,"
        " invoice_date=%s, due_date=%s, amount=%s, description=%s,"
        " status=%s WHERE id=%s",
        (customer_id or None, invoice_number,
         invoice_date or _today(), due_date or None,
         float(amount or 0), description or '', status, inv_id)
    )


def set_ar_status(conn, inv_id, status):
    if status not in INVOICE_STATUSES:
        status = 'open'
    conn.execute("UPDATE ar_invoice SET status=%s WHERE id=%s", (status, inv_id))


def list_ar_payments(conn, inv_id):
    return conn.execute(
        "SELECT * FROM ar_payment WHERE invoice_id=%s ORDER BY payment_date DESC",
        (inv_id,)
    ).fetchall()


def record_ar_payment(conn, inv_id, payment_date, amount, method, reference, notes):
    amount = float(amount or 0)
    if method not in PAYMENT_METHODS:
        method = 'Check'
    conn.execute(
        "INSERT INTO ar_payment (invoice_id, payment_date, amount,"
        " payment_method, reference, notes) VALUES (%s,%s,%s,%s,%s,%s)",
        (inv_id, payment_date or _today(), amount, method,
         reference or '', notes or '')
    )
    received = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM ar_payment WHERE invoice_id=%s",
        (inv_id,)
    ).fetchone()['total']
    inv = conn.execute("SELECT amount FROM ar_invoice WHERE id=%s", (inv_id,)).fetchone()
    if inv:
        if received <= 0:
            new_status = 'open'
        elif received >= inv['amount']:
            new_status = 'paid'
        else:
            new_status = 'partial'
        conn.execute("UPDATE ar_invoice SET status=%s WHERE id=%s", (new_status, inv_id))


# ---------------------------------------------------------------------------
# General Ledger — Chart of Accounts
# ---------------------------------------------------------------------------

def list_accounts(conn, acct_type=None, active_only=True):
    conds = []
    params = []
    if acct_type:
        conds.append('account_type = %s')
        params.append(acct_type)
    if active_only:
        conds.append('is_active = 1')
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(
        f"SELECT * FROM gl_account {where} ORDER BY account_number",
        params or None
    ).fetchall()


def get_account(conn, acct_id):
    return conn.execute(
        "SELECT * FROM gl_account WHERE id = %s", (acct_id,)
    ).fetchone()


def create_account(conn, account_number, account_name, account_type,
                   account_sub, notes):
    if not account_number or not account_name:
        raise ValueError('Account number and name are required')
    if account_type not in ACCOUNT_TYPES:
        account_type = 'Expense'
    row = conn.execute(
        "INSERT INTO gl_account (account_number, account_name, account_type,"
        " account_sub, is_active, notes) VALUES (%s,%s,%s,%s,1,%s) RETURNING id",
        (account_number, account_name, account_type,
         account_sub or '', notes or '')
    ).fetchone()
    return row['id']


def update_account(conn, acct_id, account_number, account_name, account_type,
                   account_sub, is_active, notes):
    if not account_number or not account_name:
        raise ValueError('Account number and name are required')
    if account_type not in ACCOUNT_TYPES:
        account_type = 'Expense'
    conn.execute(
        "UPDATE gl_account SET account_number=%s, account_name=%s,"
        " account_type=%s, account_sub=%s, is_active=%s, notes=%s WHERE id=%s",
        (account_number, account_name, account_type,
         account_sub or '', 1 if is_active else 0, notes or '', acct_id)
    )


def account_balance(conn, acct_id, acct_type, as_of=None):
    q = """
        SELECT COALESCE(SUM(jl.debit),0)  AS total_debit,
               COALESCE(SUM(jl.credit),0) AS total_credit
        FROM gl_journal_line jl
        JOIN gl_journal j ON j.id = jl.journal_id
        WHERE jl.account_id = %s AND j.posted = 1
    """
    params = [acct_id]
    if as_of:
        q += " AND j.journal_date <= %s"
        params.append(as_of)
    row = conn.execute(q, params).fetchone()
    d, c = row['total_debit'], row['total_credit']
    if acct_type in DEBIT_NORMAL:
        return d - c
    return c - d


# ---------------------------------------------------------------------------
# General Ledger — Journal Entries
# ---------------------------------------------------------------------------

def list_journals(conn, posted=None, date_from=None, date_to=None):
    conds = []
    params = []
    if posted is not None:
        conds.append('j.posted = %s')
        params.append(1 if posted else 0)
    if date_from:
        conds.append('j.journal_date >= %s')
        params.append(date_from)
    if date_to:
        conds.append('j.journal_date <= %s')
        params.append(date_to)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''
    return conn.execute(f"""
        SELECT j.id, j.journal_date, j.reference, j.description, j.posted,
               j.created_by, j.created_at,
               COUNT(jl.id) AS line_count,
               COALESCE(SUM(jl.debit), 0) AS total_debit
        FROM gl_journal j
        LEFT JOIN gl_journal_line jl ON jl.journal_id = j.id
        {where}
        GROUP BY j.id, j.created_by
        ORDER BY j.journal_date DESC, j.id DESC
    """, params or None).fetchall()


def get_journal(conn, journal_id):
    return conn.execute(
        "SELECT * FROM gl_journal WHERE id = %s", (journal_id,)
    ).fetchone()


def get_journal_lines(conn, journal_id):
    return conn.execute("""
        SELECT jl.id, jl.debit, jl.credit, jl.memo,
               a.id AS account_id, a.account_number, a.account_name,
               a.account_type
        FROM gl_journal_line jl
        JOIN gl_account a ON a.id = jl.account_id
        WHERE jl.journal_id = %s
        ORDER BY jl.id
    """, (journal_id,)).fetchall()


def create_journal(conn, journal_date, reference, description, lines, created_by):
    """lines: list of (account_id, debit, credit, memo). Must balance."""
    if not lines:
        raise ValueError('At least one line is required')
    total_dr = sum(float(ln[1]) for ln in lines)
    total_cr = sum(float(ln[2]) for ln in lines)
    if abs(total_dr - total_cr) > 0.005:
        raise ValueError(
            f'Journal must balance: debits ${total_dr:.2f} ≠ credits ${total_cr:.2f}')
    row = conn.execute(
        "INSERT INTO gl_journal (journal_date, reference, description, posted,"
        " created_by, created_at) VALUES (%s,%s,%s,0,%s,%s) RETURNING id",
        (journal_date or _today(), reference or '', description or '',
         created_by or '', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    ).fetchone()
    journal_id = row['id']
    for acct_id, dr, cr, memo in lines:
        conn.execute(
            "INSERT INTO gl_journal_line (journal_id, account_id, debit, credit, memo)"
            " VALUES (%s,%s,%s,%s,%s)",
            (journal_id, acct_id, float(dr), float(cr), memo or '')
        )
    return journal_id


def post_journal(conn, journal_id):
    conn.execute("UPDATE gl_journal SET posted=1 WHERE id=%s", (journal_id,))


def void_journal(conn, journal_id):
    j = conn.execute(
        "SELECT posted FROM gl_journal WHERE id=%s", (journal_id,)
    ).fetchone()
    if not j:
        return
    if j['posted']:
        raise ValueError('Posted entries cannot be voided')
    conn.execute("DELETE FROM gl_journal_line WHERE journal_id=%s", (journal_id,))
    conn.execute("DELETE FROM gl_journal WHERE id=%s", (journal_id,))


# ---------------------------------------------------------------------------
# General Ledger — Financial Reports
# ---------------------------------------------------------------------------

def trial_balance(conn, as_of=None):
    accounts = conn.execute(
        "SELECT id, account_number, account_name, account_type"
        " FROM gl_account WHERE is_active = 1 ORDER BY account_number"
    ).fetchall()
    rows = []
    total_dr = total_cr = 0.0
    for a in accounts:
        bal = account_balance(conn, a['id'], a['account_type'], as_of)
        if abs(bal) < 0.005:
            continue
        if a['account_type'] in DEBIT_NORMAL:
            dr = max(bal, 0)
            cr = max(-bal, 0)
        else:
            cr = max(bal, 0)
            dr = max(-bal, 0)
        total_dr += dr
        total_cr += cr
        rows.append({
            'account_number': a['account_number'],
            'account_name': a['account_name'],
            'account_type': a['account_type'],
            'debit': dr,
            'credit': cr,
        })
    return {
        'rows': rows,
        'total_debit': total_dr,
        'total_credit': total_cr,
        'balanced': abs(total_dr - total_cr) < 0.005,
    }


def _period_balance(conn, acct_id, acct_type, date_from, date_to):
    row = conn.execute("""
        SELECT COALESCE(SUM(jl.debit),0)  AS d,
               COALESCE(SUM(jl.credit),0) AS c
        FROM gl_journal_line jl
        JOIN gl_journal j ON j.id = jl.journal_id
        WHERE jl.account_id = %s AND j.posted = 1
          AND j.journal_date BETWEEN %s AND %s
    """, (acct_id, date_from, date_to)).fetchone()
    d, c = row['d'], row['c']
    if acct_type in DEBIT_NORMAL:
        return d - c
    return c - d


def income_statement(conn, date_from, date_to):
    accounts = conn.execute(
        "SELECT id, account_number, account_name, account_type FROM gl_account"
        " WHERE is_active = 1 AND account_type IN ('Revenue','COGS','Expense')"
        " ORDER BY account_type, account_number"
    ).fetchall()
    sections = {'Revenue': [], 'COGS': [], 'Expense': []}
    totals   = {'Revenue': 0.0, 'COGS': 0.0, 'Expense': 0.0}
    for a in accounts:
        bal = _period_balance(conn, a['id'], a['account_type'], date_from, date_to)
        if abs(bal) < 0.005:
            continue
        totals[a['account_type']] += bal
        sections[a['account_type']].append({
            'account_number': a['account_number'],
            'account_name': a['account_name'],
            'amount': bal,
        })
    revenue     = totals['Revenue']
    cogs        = totals['COGS']
    expenses    = totals['Expense']
    gross       = revenue - cogs
    net_income  = gross - expenses
    return {
        'sections': sections, 'totals': totals,
        'revenue': revenue, 'cogs': cogs, 'expenses': expenses,
        'gross_profit': gross, 'net_income': net_income,
    }


def balance_sheet(conn, as_of=None):
    accounts = conn.execute(
        "SELECT id, account_number, account_name, account_type FROM gl_account"
        " WHERE is_active = 1 AND account_type IN ('Asset','Liability','Equity')"
        " ORDER BY account_type, account_number"
    ).fetchall()
    sections = {'Asset': [], 'Liability': [], 'Equity': []}
    totals   = {'Asset': 0.0, 'Liability': 0.0, 'Equity': 0.0}
    for a in accounts:
        bal = account_balance(conn, a['id'], a['account_type'], as_of)
        if abs(bal) < 0.005:
            continue
        totals[a['account_type']] += bal
        sections[a['account_type']].append({
            'account_number': a['account_number'],
            'account_name': a['account_name'],
            'balance': bal,
        })
    assets      = totals['Asset']
    liabilities = totals['Liability']
    equity      = totals['Equity']
    balanced    = abs(assets - (liabilities + equity)) < 0.005
    return {
        'sections': sections, 'totals': totals,
        'assets': assets, 'liabilities': liabilities, 'equity': equity,
        'balanced': balanced,
    }
