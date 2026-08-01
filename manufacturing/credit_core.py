"""Qt-free Credit Department data layer — dashboard, credit accounts,
applications, limit-change history, and collections.

Tables: credit_account, credit_application, credit_limit_history,
        collection_activity (all defined in seeds/seed_sample_customers.py;
        this module is their first real read/write path — the web UI never
        had one, the menu leaf just routed to General Ledger instead).
No PyQt6, no commit inside any function.
"""

import datetime

CREDIT_STATUSES = ('good', 'hold', 'suspended', 'closed')
APPLICATION_STATUSES = ('pending', 'approved', 'denied')
COLLECTION_STATUSES = ('Open', 'In Progress', 'Escalated', 'Resolved')
ACTIVITY_TYPES = ('Call', 'Email', 'Letter', 'Visit', 'Other')


def _today() -> str:
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_credit_dashboard(conn) -> dict:
    """Return dict with keys: accounts, applications, collections.

    accounts:     {total, good, hold, suspended, total_exposure}
    applications: {total, pending}
    collections:  {total, open}
    """
    acct = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'good') AS good, "
        "COUNT(*) FILTER (WHERE status = 'hold') AS hold, "
        "COUNT(*) FILTER (WHERE status = 'suspended') AS suspended, "
        "COALESCE(SUM(credit_limit), 0) AS total_exposure "
        "FROM credit_account"
    ).fetchone()
    accounts = dict(acct) if acct else {
        'total': 0, 'good': 0, 'hold': 0, 'suspended': 0, 'total_exposure': 0.0}

    app = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'pending') AS pending "
        "FROM credit_application"
    ).fetchone()
    applications = dict(app) if app else {'total': 0, 'pending': 0}

    coll = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status IN ('Open', 'In Progress', 'Escalated')) AS open "
        "FROM collection_activity"
    ).fetchone()
    collections = dict(coll) if coll else {'total': 0, 'open': 0}

    return {
        'accounts': accounts,
        'applications': applications,
        'collections': collections,
    }


# ---------------------------------------------------------------------------
# Credit Accounts
# ---------------------------------------------------------------------------

def list_credit_accounts(conn, status=None, search=None) -> list:
    sql = (
        "SELECT ca.id, ca.customer_id, ca.credit_limit, ca.status, ca.terms, "
        "ca.opened_date, ca.notes, "
        "c.company_name, c.first_name, c.last_name "
        "FROM credit_account ca "
        "JOIN customer c ON c.id = ca.customer_id "
        "WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND ca.status = %s"
        params.append(status)
    if search:
        sql += " AND (c.company_name ILIKE %s OR c.first_name ILIKE %s OR c.last_name ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY c.company_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_credit_account(conn, account_id: int) -> dict | None:
    row = conn.execute(
        "SELECT ca.*, c.company_name, c.first_name, c.last_name, c.email, c.phone_number "
        "FROM credit_account ca "
        "JOIN customer c ON c.id = ca.customer_id "
        "WHERE ca.id = %s",
        (account_id,),
    ).fetchone()
    return dict(row) if row else None


def get_credit_account_by_customer(conn, customer_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM credit_account WHERE customer_id = %s", (customer_id,)
    ).fetchone()
    return dict(row) if row else None


def customers_without_credit_account(conn) -> list:
    """Customers that don't have a credit_account row yet (for the "open a
    new account" dropdown — credit_account.customer_id is UNIQUE)."""
    rows = conn.execute(
        "SELECT c.id, c.company_name, c.first_name, c.last_name "
        "FROM customer c "
        "LEFT JOIN credit_account ca ON ca.customer_id = c.id "
        "WHERE ca.id IS NULL "
        "ORDER BY c.company_name"
    ).fetchall()
    return [dict(r) for r in rows]


def create_credit_account(
    conn, customer_id: int, credit_limit: float, status: str,
    terms: str, opened_date: str, notes: str,
) -> int:
    if not customer_id:
        raise ValueError('Customer is required')
    if get_credit_account_by_customer(conn, customer_id):
        raise ValueError('This customer already has a credit account')
    if status not in CREDIT_STATUSES:
        status = 'good'
    row = conn.execute(
        "INSERT INTO credit_account "
        "(customer_id, credit_limit, status, terms, opened_date, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (customer_id, credit_limit or 0, status, terms or '',
         opened_date or _today(), notes or ''),
    ).fetchone()
    return row['id']


def update_credit_account(
    conn, account_id: int, credit_limit: float, status: str,
    terms: str, notes: str, changed_by: str, reason: str = '',
) -> None:
    """Update an account's limit/status/terms. If the limit or status
    actually changes, logs a credit_limit_history row automatically —
    matching the seeded data's implied workflow (every real limit/status
    change has a paired history row explaining it)."""
    if status not in CREDIT_STATUSES:
        status = 'good'
    current = conn.execute(
        "SELECT credit_limit, status FROM credit_account WHERE id = %s",
        (account_id,),
    ).fetchone()
    if not current:
        raise ValueError('Credit account not found')

    conn.execute(
        "UPDATE credit_account SET credit_limit=%s, status=%s, terms=%s, notes=%s "
        "WHERE id=%s",
        (credit_limit or 0, status, terms or '', notes or '', account_id),
    )

    limit_changed = float(current['credit_limit']) != float(credit_limit or 0)
    status_changed = current['status'] != status
    if limit_changed or status_changed:
        customer_id = conn.execute(
            "SELECT customer_id FROM credit_account WHERE id = %s", (account_id,)
        ).fetchone()['customer_id']
        conn.execute(
            "INSERT INTO credit_limit_history "
            "(customer_id, changed_date, old_limit, new_limit, old_status, "
            " new_status, changed_by, reason) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (customer_id, _today(), current['credit_limit'], credit_limit or 0,
             current['status'], status, changed_by or '',
             reason or 'Manual update via Credit Department'),
        )


# ---------------------------------------------------------------------------
# Credit Limit History
# ---------------------------------------------------------------------------

def list_limit_history(conn, customer_id: int | None = None) -> list:
    sql = (
        "SELECT h.*, c.company_name "
        "FROM credit_limit_history h "
        "JOIN customer c ON c.id = h.customer_id "
        "WHERE TRUE"
    )
    params: list = []
    if customer_id:
        sql += " AND h.customer_id = %s"
        params.append(customer_id)
    sql += " ORDER BY h.changed_date DESC, h.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------------------------------------------------------------------------
# Credit Applications
# ---------------------------------------------------------------------------

def list_credit_applications(conn, status=None, search=None) -> list:
    sql = (
        "SELECT a.*, c.company_name, c.first_name, c.last_name "
        "FROM credit_application a "
        "JOIN customer c ON c.id = a.customer_id "
        "WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND a.status = %s"
        params.append(status)
    if search:
        sql += " AND (c.company_name ILIKE %s OR c.first_name ILIKE %s OR c.last_name ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY a.applied_date DESC, a.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_credit_application(conn, app_id: int) -> dict | None:
    row = conn.execute(
        "SELECT a.*, c.company_name, c.first_name, c.last_name "
        "FROM credit_application a "
        "JOIN customer c ON c.id = a.customer_id "
        "WHERE a.id = %s",
        (app_id,),
    ).fetchone()
    return dict(row) if row else None


def create_credit_application(
    conn, customer_id: int, applied_date: str, requested_limit: float,
    notes: str, created_by: str,
) -> int:
    if not customer_id:
        raise ValueError('Customer is required')
    if not requested_limit or float(requested_limit) <= 0:
        raise ValueError('Requested limit must be greater than zero')
    row = conn.execute(
        "INSERT INTO credit_application "
        "(customer_id, applied_date, requested_limit, status, notes, created_by) "
        "VALUES (%s,%s,%s,'pending',%s,%s) RETURNING id",
        (customer_id, applied_date or _today(), requested_limit, notes or '',
         created_by or ''),
    ).fetchone()
    return row['id']


def decide_credit_application(
    conn, app_id: int, decision: str, approved_limit: float | None,
    reviewed_by: str, notes: str,
) -> None:
    """Approve or deny a pending application. Approving opens a new credit
    account (or raises the existing one's limit) and logs the change to
    credit_limit_history, same as a manual account update would."""
    if decision not in ('approved', 'denied'):
        raise ValueError("decision must be 'approved' or 'denied'")
    app = conn.execute(
        "SELECT * FROM credit_application WHERE id = %s", (app_id,)
    ).fetchone()
    if not app:
        raise ValueError('Application not found')
    if app['status'] != 'pending':
        raise ValueError(f"Application is already {app['status']}")

    final_limit = approved_limit if decision == 'approved' else None
    if decision == 'approved' and (not final_limit or float(final_limit) <= 0):
        final_limit = app['requested_limit']

    conn.execute(
        "UPDATE credit_application SET status=%s, approved_limit=%s, "
        "reviewed_by=%s, review_date=%s, notes=%s WHERE id=%s",
        (decision, final_limit, reviewed_by or '', _today(),
         notes or app['notes'] or '', app_id),
    )

    if decision != 'approved':
        return

    existing = get_credit_account_by_customer(conn, app['customer_id'])
    if existing:
        update_credit_account(
            conn, existing['id'], final_limit, existing['status'],
            existing['terms'], existing['notes'], reviewed_by,
            reason=f"Credit application #{app_id} approved",
        )
    else:
        create_credit_account(
            conn, app['customer_id'], final_limit, 'good', '', _today(),
            f"Opened from credit application #{app_id}",
        )
        conn.execute(
            "INSERT INTO credit_limit_history "
            "(customer_id, changed_date, old_limit, new_limit, old_status, "
            " new_status, changed_by, reason) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (app['customer_id'], _today(), None, final_limit, None, 'good',
             reviewed_by or '', f"Credit application #{app_id} approved"),
        )


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

def list_collection_activities(conn, status=None, customer_id=None, search=None) -> list:
    sql = (
        "SELECT ca.*, c.company_name, c.first_name, c.last_name "
        "FROM collection_activity ca "
        "JOIN customer c ON c.id = ca.customer_id "
        "WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND ca.status = %s"
        params.append(status)
    if customer_id:
        sql += " AND ca.customer_id = %s"
        params.append(customer_id)
    if search:
        sql += " AND (c.company_name ILIKE %s OR ca.contact_name ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY ca.activity_date DESC, ca.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_collection_activity(conn, activity_id: int) -> dict | None:
    row = conn.execute(
        "SELECT ca.*, c.company_name, c.first_name, c.last_name "
        "FROM collection_activity ca "
        "JOIN customer c ON c.id = ca.customer_id "
        "WHERE ca.id = %s",
        (activity_id,),
    ).fetchone()
    return dict(row) if row else None


def create_collection_activity(
    conn, customer_id: int, activity_date: str, activity_type: str,
    contact_name: str, notes: str, amount_promised: float | None,
    promise_date: str | None, follow_up_date: str | None,
    status: str, created_by: str,
) -> int:
    if not customer_id:
        raise ValueError('Customer is required')
    if activity_type not in ACTIVITY_TYPES:
        activity_type = 'Other'
    if status not in COLLECTION_STATUSES:
        status = 'Open'
    row = conn.execute(
        "INSERT INTO collection_activity "
        "(customer_id, activity_date, activity_type, contact_name, notes, "
        " amount_promised, promise_date, follow_up_date, status, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (customer_id, activity_date or _today(), activity_type,
         contact_name or '', notes or '', amount_promised or None,
         promise_date or None, follow_up_date or None, status, created_by or ''),
    ).fetchone()
    return row['id']


def update_collection_activity(conn, activity_id: int, **fields) -> None:
    allowed = {
        'activity_type', 'contact_name', 'notes', 'amount_promised',
        'promise_date', 'follow_up_date', 'status',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'status' in cols and cols['status'] not in COLLECTION_STATUSES:
        cols['status'] = 'Open'
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE collection_activity SET {set_clause} WHERE id = %s",
        list(cols.values()) + [activity_id],
    )
