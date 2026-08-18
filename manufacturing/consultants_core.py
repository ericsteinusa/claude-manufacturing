"""
consultants_core.py — Qt-free data layer for Consultant Time & Charges.

Tables: consultant, consultant_engagement, consultant_time_entry,
        consultant_charge, consultant_invoice.

Consultants may be external (linked to an existing `supplier` row),
internal-style contract labor (linked to an existing `people` row), both,
or neither (ad-hoc — billed under an auto-created fallback supplier, see
_resolve_vendor_id). No PyQt6; no commit inside any function except
ensure_consultant_tables — callers commit, mirroring accounting_core.py.

Money pattern: engagement/invoice totals are never stored — they are
always SUM(hours*rate) over consultant_time_entry + SUM(amount) over
consultant_charge, computed at query time, matching how
purchase_orders_core.py's PO total and accounting_core.list_ap_invoices'
paid/balance are always derived rather than stored-and-drifted.

Lifecycle: a consultant_engagement accumulates consultant_time_entry and
consultant_charge rows over time (no approval gate — an engagement can
stay 'active' for months). Periodically, create_consultant_invoice() claims
the unbilled rows in a date range into a new consultant_invoice (status
'draft'). submit_consultant_invoice() hands it to approval_workflow_core
(entity_type 'consultant_invoice'). On final approval,
decide_consultant_invoice_via_workflow() converts it into a real
accounting_core.ap_invoice, reusing all existing AP payment tracking
rather than inventing a parallel one. On rejection, claimed rows are
released (invoice_id cleared) so nothing billable is silently lost.
"""

import datetime

from .mrp_core import next_sequence_number

ENGAGEMENT_STATUSES = ('draft', 'active', 'closed', 'cancelled')
CHARGE_CATEGORIES = ('Travel', 'Materials', 'Lodging', 'Software/Tools', 'Other')
CONSULTANT_INVOICE_STATUSES = ('draft', 'submitted', 'approved', 'rejected', 'invoiced')

FALLBACK_SUPPLIER_TAG = 'CONSULTANT-FALLBACK'


def _today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def ensure_consultant_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consultant (
            id SERIAL PRIMARY KEY,
            display_name   TEXT NOT NULL,
            supplier_id    INTEGER REFERENCES supplier(id),
            people_id      INTEGER REFERENCES people(id),
            default_hourly_rate REAL,
            specialty      TEXT NOT NULL DEFAULT '',
            email          TEXT NOT NULL DEFAULT '',
            phone_number   TEXT NOT NULL DEFAULT '',
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_date   TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consultant_engagement (
            id SERIAL PRIMARY KEY,
            engagement_number TEXT NOT NULL UNIQUE,
            consultant_id  INTEGER NOT NULL REFERENCES consultant(id),
            dept_id        INTEGER,
            title          TEXT NOT NULL,
            purpose        TEXT NOT NULL DEFAULT '',
            start_date     TEXT,
            end_date       TEXT,
            default_hourly_rate REAL,
            status         TEXT NOT NULL DEFAULT 'draft',
            requested_by   TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_date   TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consultant_time_entry (
            id SERIAL PRIMARY KEY,
            engagement_id  INTEGER NOT NULL REFERENCES consultant_engagement(id),
            work_date      TEXT NOT NULL,
            hours          REAL NOT NULL DEFAULT 0,
            hourly_rate    REAL,
            description    TEXT NOT NULL DEFAULT '',
            invoice_id     INTEGER,
            created_by     TEXT NOT NULL DEFAULT '',
            created_date   TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consultant_charge (
            id SERIAL PRIMARY KEY,
            engagement_id  INTEGER NOT NULL REFERENCES consultant_engagement(id),
            charge_date    TEXT NOT NULL,
            category       TEXT NOT NULL DEFAULT 'Other',
            description    TEXT NOT NULL DEFAULT '',
            amount         REAL NOT NULL DEFAULT 0,
            invoice_id     INTEGER,
            created_by     TEXT NOT NULL DEFAULT '',
            created_date   TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS consultant_invoice (
            id SERIAL PRIMARY KEY,
            invoice_number TEXT NOT NULL UNIQUE,
            engagement_id  INTEGER NOT NULL REFERENCES consultant_engagement(id),
            period_start   TEXT,
            period_end     TEXT,
            status         TEXT NOT NULL DEFAULT 'draft',
            ap_invoice_id  INTEGER,
            submitted_by   TEXT NOT NULL DEFAULT '',
            submitted_date TEXT,
            decided_by     TEXT NOT NULL DEFAULT '',
            decided_date   TEXT,
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT '',
            created_date   TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS consultant_time_entry_engagement "
        "ON consultant_time_entry(engagement_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS consultant_charge_engagement "
        "ON consultant_charge(engagement_id)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Consultant CRUD
# ---------------------------------------------------------------------------

def list_consultants(conn, active_only: bool = False, search: str | None = None) -> list[dict]:
    ensure_consultant_tables(conn)
    conds, params = [], []
    if active_only:
        conds.append("c.is_active = TRUE")
    if search:
        conds.append("(c.display_name ILIKE %s OR c.specialty ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(f"""
        SELECT c.*, s.company_name AS supplier_name,
               p.first_name AS people_first_name, p.last_name AS people_last_name
        FROM consultant c
        LEFT JOIN supplier s ON s.id = c.supplier_id
        LEFT JOIN people p ON p.id = c.people_id
        {where}
        ORDER BY c.display_name
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_consultant(conn, consultant_id: int) -> dict | None:
    ensure_consultant_tables(conn)
    row = conn.execute("""
        SELECT c.*, s.company_name AS supplier_name,
               p.first_name AS people_first_name, p.last_name AS people_last_name
        FROM consultant c
        LEFT JOIN supplier s ON s.id = c.supplier_id
        LEFT JOIN people p ON p.id = c.people_id
        WHERE c.id = %s
    """, (consultant_id,)).fetchone()
    return dict(row) if row else None


def create_consultant(conn, display_name, supplier_id=None, people_id=None,
                       default_hourly_rate=None, specialty='', email='',
                       phone_number='', notes='', created_by='') -> int:
    ensure_consultant_tables(conn)
    if not display_name:
        raise ValueError('Consultant name is required')
    row = conn.execute("""
        INSERT INTO consultant
        (display_name, supplier_id, people_id, default_hourly_rate,
         specialty, email, phone_number, notes, created_by, created_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (display_name, supplier_id or None, people_id or None,
          default_hourly_rate, specialty or '', email or '',
          phone_number or '', notes or '', created_by or '', _today())
    ).fetchone()
    return row['id']


def update_consultant(conn, consultant_id: int, **fields) -> None:
    allowed = {
        'display_name', 'supplier_id', 'people_id', 'default_hourly_rate',
        'specialty', 'email', 'phone_number', 'is_active', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE consultant SET {set_clause} WHERE id = %s",
        list(cols.values()) + [consultant_id],
    )


# ---------------------------------------------------------------------------
# Engagement CRUD
# ---------------------------------------------------------------------------

def list_engagements(conn, dept_id=None, requester_id=None, status=None,
                      scope_all: bool = False) -> list[dict]:
    """Visibility: scope_all (full-access or Purchasing) sees everything;
    otherwise callers pass dept_id and/or requester_id to scope the results,
    mirroring purchase_requisitions_core.list_requisitions' visibility split."""
    ensure_consultant_tables(conn)
    conds, params = [], []
    if not scope_all:
        if dept_id is not None:
            conds.append("e.dept_id = %s")
            params.append(dept_id)
        elif requester_id is not None:
            conds.append("e.requested_by = %s")
            params.append(requester_id)
    if status:
        conds.append("e.status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(f"""
        SELECT e.*, c.display_name AS consultant_name, d.dept_name,
               COALESCE((SELECT SUM(t.hours * COALESCE(t.hourly_rate, e.default_hourly_rate, c.default_hourly_rate))
                         FROM consultant_time_entry t WHERE t.engagement_id = e.id), 0)
               + COALESCE((SELECT SUM(ch.amount)
                         FROM consultant_charge ch WHERE ch.engagement_id = e.id), 0)
               AS grand_total
        FROM consultant_engagement e
        JOIN consultant c ON c.id = e.consultant_id
        LEFT JOIN dept d ON d.dept_id = e.dept_id
        {where}
        ORDER BY e.id DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_engagement(conn, engagement_id: int) -> dict | None:
    ensure_consultant_tables(conn)
    row = conn.execute("""
        SELECT e.*, c.display_name AS consultant_name,
               c.default_hourly_rate AS consultant_default_rate, d.dept_name
        FROM consultant_engagement e
        JOIN consultant c ON c.id = e.consultant_id
        LEFT JOIN dept d ON d.dept_id = e.dept_id
        WHERE e.id = %s
    """, (engagement_id,)).fetchone()
    return dict(row) if row else None


def create_engagement(conn, consultant_id, dept_id, title, purpose='',
                       start_date=None, end_date=None,
                       default_hourly_rate=None, requested_by='',
                       created_by='') -> int:
    ensure_consultant_tables(conn)
    if not title:
        raise ValueError('Engagement title is required')
    year = datetime.date.today().year
    prefix = f'ENG-{year}-'
    existing = [
        r[0] for r in conn.execute(
            "SELECT engagement_number FROM consultant_engagement WHERE engagement_number LIKE %s",
            (prefix + '%',),
        ).fetchall()
    ]
    engagement_number = next_sequence_number(existing, prefix)
    row = conn.execute("""
        INSERT INTO consultant_engagement
        (engagement_number, consultant_id, dept_id, title, purpose,
         start_date, end_date, default_hourly_rate, status,
         requested_by, created_by, created_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s) RETURNING id
    """, (engagement_number, consultant_id, dept_id or None, title,
          purpose or '', start_date or None, end_date or None,
          default_hourly_rate, requested_by or '', created_by or '', _today())
    ).fetchone()
    return row['id']


def activate_engagement(conn, engagement_id: int) -> None:
    conn.execute(
        "UPDATE consultant_engagement SET status = 'active' WHERE id = %s AND status = 'draft'",
        (engagement_id,),
    )


def close_engagement(conn, engagement_id: int) -> None:
    conn.execute(
        "UPDATE consultant_engagement SET status = 'closed' WHERE id = %s",
        (engagement_id,),
    )


# ---------------------------------------------------------------------------
# Time entries & charges
# ---------------------------------------------------------------------------

def list_time_entries(conn, engagement_id: int) -> list[dict]:
    ensure_consultant_tables(conn)
    rows = conn.execute("""
        SELECT * FROM consultant_time_entry
        WHERE engagement_id = %s ORDER BY work_date, id
    """, (engagement_id,)).fetchall()
    return [dict(r) for r in rows]


def list_charges(conn, engagement_id: int) -> list[dict]:
    ensure_consultant_tables(conn)
    rows = conn.execute("""
        SELECT * FROM consultant_charge
        WHERE engagement_id = %s ORDER BY charge_date, id
    """, (engagement_id,)).fetchall()
    return [dict(r) for r in rows]


def add_time_entry(conn, engagement_id, work_date, hours, hourly_rate=None,
                    description='', created_by='') -> int:
    ensure_consultant_tables(conn)
    if not work_date:
        raise ValueError('Work date is required')
    row = conn.execute("""
        INSERT INTO consultant_time_entry
        (engagement_id, work_date, hours, hourly_rate, description, created_by, created_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (engagement_id, work_date, float(hours or 0), hourly_rate,
          description or '', created_by or '', _today())
    ).fetchone()
    return row['id']


def add_charge(conn, engagement_id, charge_date, category, amount,
                description='', created_by='') -> int:
    ensure_consultant_tables(conn)
    if not charge_date:
        raise ValueError('Charge date is required')
    if category not in CHARGE_CATEGORIES:
        raise ValueError(f'category must be one of {CHARGE_CATEGORIES}')
    row = conn.execute("""
        INSERT INTO consultant_charge
        (engagement_id, charge_date, category, amount, description, created_by, created_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (engagement_id, charge_date, category, float(amount or 0),
          description or '', created_by or '', _today())
    ).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Rate resolution (single source of truth, reused by reports & invoicing)
# ---------------------------------------------------------------------------

def _resolve_time_entry_rate(entry: dict, engagement: dict, consultant: dict) -> float | None:
    """Fallback chain: entry's own rate -> engagement default -> consultant
    default -> None (unresolvable). Mirrors get_labor_by_personnel_report's
    'only cost when a real rate is known, else None — never fabricate a
    number' rule."""
    for source in (entry.get('hourly_rate'), engagement.get('default_hourly_rate'),
                   consultant.get('default_hourly_rate')):
        if source is not None:
            return float(source)
    return None


def _resolve_time_entry_cost(entry: dict, engagement: dict, consultant: dict) -> float | None:
    rate = _resolve_time_entry_rate(entry, engagement, consultant)
    if rate is None:
        return None
    return float(entry.get('hours') or 0) * rate


# ---------------------------------------------------------------------------
# Invoice lifecycle
# ---------------------------------------------------------------------------

def get_consultant_invoice(conn, cinv_id: int) -> dict | None:
    ensure_consultant_tables(conn)
    row = conn.execute("""
        SELECT ci.*, e.engagement_number, e.title AS engagement_title,
               e.consultant_id, c.display_name AS consultant_name
        FROM consultant_invoice ci
        JOIN consultant_engagement e ON e.id = ci.engagement_id
        JOIN consultant c ON c.id = e.consultant_id
        WHERE ci.id = %s
    """, (cinv_id,)).fetchone()
    return dict(row) if row else None


def list_consultant_invoices(conn, status=None) -> list[dict]:
    ensure_consultant_tables(conn)
    conds, params = [], []
    if status:
        conds.append("ci.status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(f"""
        SELECT ci.*, e.engagement_number, e.title AS engagement_title,
               c.display_name AS consultant_name
        FROM consultant_invoice ci
        JOIN consultant_engagement e ON e.id = ci.engagement_id
        JOIN consultant c ON c.id = e.consultant_id
        {where}
        ORDER BY ci.id DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_invoice_lines(conn, cinv_id: int) -> dict:
    """Return {'time_entries': [...], 'charges': [...], 'total': float}
    for the rows claimed by this invoice."""
    ensure_consultant_tables(conn)
    row = conn.execute(
        "SELECT engagement_id FROM consultant_invoice WHERE id = %s", (cinv_id,)
    ).fetchone()
    if not row:
        return {'time_entries': [], 'charges': [], 'total': 0.0}
    engagement = get_engagement(conn, row['engagement_id'])
    consultant = get_consultant(conn, engagement['consultant_id'])
    time_rows = conn.execute(
        "SELECT * FROM consultant_time_entry WHERE invoice_id = %s ORDER BY work_date, id",
        (cinv_id,),
    ).fetchall()
    charge_rows = conn.execute(
        "SELECT * FROM consultant_charge WHERE invoice_id = %s ORDER BY charge_date, id",
        (cinv_id,),
    ).fetchall()
    time_entries = []
    total = 0.0
    for r in time_rows:
        d = dict(r)
        d['resolved_rate'] = _resolve_time_entry_rate(d, engagement, consultant)
        d['cost'] = _resolve_time_entry_cost(d, engagement, consultant)
        total += d['cost'] or 0.0
        time_entries.append(d)
    charges = [dict(r) for r in charge_rows]
    total += sum(c['amount'] for c in charges)
    return {'time_entries': time_entries, 'charges': charges, 'total': total}


def create_consultant_invoice(conn, engagement_id, period_start, period_end,
                               created_by='') -> int:
    """Claim all unbilled time/charge rows for this engagement whose date
    falls in [period_start, period_end] into a new draft consultant_invoice.

    Raises ValueError if nothing is claimable, or if any claimed time entry
    has no resolvable hourly rate — mirrors accounting_core.create_ap_invoice's
    raise-up-front guard pattern for due_date, applied here so an invoice
    is never generated that would silently bill $0 for real hours worked.
    """
    ensure_consultant_tables(conn)
    engagement = get_engagement(conn, engagement_id)
    if not engagement:
        raise ValueError(f'Engagement {engagement_id} not found')
    consultant = get_consultant(conn, engagement['consultant_id'])

    time_rows = [dict(r) for r in conn.execute("""
        SELECT * FROM consultant_time_entry
        WHERE engagement_id = %s AND invoice_id IS NULL
          AND work_date >= %s AND work_date <= %s
    """, (engagement_id, period_start, period_end)).fetchall()]
    charge_rows = [dict(r) for r in conn.execute("""
        SELECT * FROM consultant_charge
        WHERE engagement_id = %s AND invoice_id IS NULL
          AND charge_date >= %s AND charge_date <= %s
    """, (engagement_id, period_start, period_end)).fetchall()]

    if not time_rows and not charge_rows:
        raise ValueError('No unbilled time entries or charges in this period')

    for entry in time_rows:
        if _resolve_time_entry_rate(entry, engagement, consultant) is None:
            raise ValueError(
                f"Time entry {entry['id']} ({entry['work_date']}) has no "
                "resolvable hourly rate — set a rate on the entry, the "
                "engagement, or the consultant before invoicing"
            )

    year = datetime.date.today().year
    prefix = f'CINV-{year}-'
    existing = [
        r[0] for r in conn.execute(
            "SELECT invoice_number FROM consultant_invoice WHERE invoice_number LIKE %s",
            (prefix + '%',),
        ).fetchall()
    ]
    invoice_number = next_sequence_number(existing, prefix)

    row = conn.execute("""
        INSERT INTO consultant_invoice
        (invoice_number, engagement_id, period_start, period_end, status,
         created_by, created_date)
        VALUES (%s,%s,%s,%s,'draft',%s,%s) RETURNING id
    """, (invoice_number, engagement_id, period_start, period_end,
          created_by or '', _today())
    ).fetchone()
    cinv_id = row['id']

    if time_rows:
        conn.execute(
            "UPDATE consultant_time_entry SET invoice_id = %s WHERE id = ANY(%s)",
            (cinv_id, [r['id'] for r in time_rows]),
        )
    if charge_rows:
        conn.execute(
            "UPDATE consultant_charge SET invoice_id = %s WHERE id = ANY(%s)",
            (cinv_id, [r['id'] for r in charge_rows]),
        )
    return cinv_id


def submit_consultant_invoice(conn, cinv_id: int, submitted_by: str) -> None:
    from . import approval_workflow_core
    from .menus import DEPT_MENU_KEY

    cinv = get_consultant_invoice(conn, cinv_id)
    if not cinv:
        raise ValueError(f'Consultant invoice {cinv_id} not found')
    lines = get_invoice_lines(conn, cinv_id)
    engagement = get_engagement(conn, cinv['engagement_id'])
    dept_key = DEPT_MENU_KEY.get(engagement.get('dept_name'), '') if engagement else ''

    conn.execute(
        "UPDATE consultant_invoice SET status = 'submitted', submitted_by = %s,"
        " submitted_date = %s WHERE id = %s",
        (submitted_by, _today(), cinv_id),
    )
    approval_workflow_core.ensure_approval_tables(conn)
    approval_workflow_core.submit_for_approval(
        conn, 'consultant_invoice', cinv_id, lines['total'], dept_key,
        requested_by=submitted_by,
    )


def _resolve_vendor_id(conn, consultant: dict) -> int:
    """Return a supplier id to bill this consultant's AP invoice against.

    Reuses the consultant's linked supplier if set. Otherwise, reuses the
    fallback-supplier-creation precedent from seeds/seed_sample_pos.py's
    _first_supplier_id — but backfills consultant.supplier_id with the new
    row so a second invoice for the same consultant reuses it instead of
    creating a duplicate fallback supplier each time (the seed script can
    recreate one per run because it's throwaway sample data; a live feature
    must not).

    The live `supplier` table has first_name/last_name/phone_number/address/
    city/state/zip_code/email all NOT NULL, despite schema.py's own DDL
    declaring them nullable (the live-schema-vs-DDL drift CLAUDE.md warns
    about) — every one of those columns must get an explicit '' rather than
    being omitted, or the INSERT raises NotNullViolation."""
    if consultant.get('supplier_id'):
        return consultant['supplier_id']
    row = conn.execute(
        "INSERT INTO supplier (first_name, last_name, company_name,"
        " phone_number, address, city, state, zip_code, email, created_by)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        ('', '', consultant['display_name'],
         consultant.get('phone_number') or '', '', '', '', '',
         consultant.get('email') or '', FALLBACK_SUPPLIER_TAG),
    ).fetchone()
    supplier_id = row['id']
    conn.execute(
        "UPDATE consultant SET supplier_id = %s WHERE id = %s",
        (supplier_id, consultant['id']),
    )
    return supplier_id


def decide_consultant_invoice_via_workflow(conn, cinv_id: int, step_id: int,
                                            decision: str, decided_by: str,
                                            notes: str = '') -> str:
    """Decide one approval_workflow step for a consultant invoice, syncing
    consultant_invoice.status to match — mirrors
    purchase_requisitions_core.decide_requisition_via_workflow's sync
    pattern (without it, approval_step and consultant_invoice would drift
    out of sync since they're otherwise unlinked tables).

    On final approval: converts to a real accounting_core.ap_invoice
    (auto-creating a fallback supplier if needed) and sets ap_invoice_id.
    On rejection: releases claimed time/charge rows (invoice_id -> NULL)
    so nothing billable is silently lost.
    Returns the resulting consultant_invoice.status.
    """
    from . import approval_workflow_core
    from . import accounting_core

    overall = approval_workflow_core.decide_step(conn, step_id, decision, decided_by, notes)

    if overall == 'approved':
        cinv = get_consultant_invoice(conn, cinv_id)
        engagement = get_engagement(conn, cinv['engagement_id'])
        consultant = get_consultant(conn, engagement['consultant_id'])
        lines = get_invoice_lines(conn, cinv_id)
        vendor_id = _resolve_vendor_id(conn, consultant)
        due_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        ap_invoice_id = accounting_core.create_ap_invoice(
            conn, vendor_id, cinv['invoice_number'], _today(), due_date,
            lines['total'],
            f"Consultant engagement {engagement['engagement_number']} "
            f"({cinv['period_start']}..{cinv['period_end']})",
            decided_by,
        )
        conn.execute(
            "UPDATE consultant_invoice SET status = 'invoiced', ap_invoice_id = %s,"
            " decided_by = %s, decided_date = %s WHERE id = %s",
            (ap_invoice_id, decided_by, _today(), cinv_id),
        )
        return 'invoiced'

    if overall == 'rejected':
        conn.execute(
            "UPDATE consultant_time_entry SET invoice_id = NULL WHERE invoice_id = %s",
            (cinv_id,),
        )
        conn.execute(
            "UPDATE consultant_charge SET invoice_id = NULL WHERE invoice_id = %s",
            (cinv_id,),
        )
        conn.execute(
            "UPDATE consultant_invoice SET status = 'rejected', decided_by = %s,"
            " decided_date = %s WHERE id = %s",
            (decided_by, _today(), cinv_id),
        )
        return 'rejected'

    return 'submitted'


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _engagement_and_consultant_cache(conn):
    engagements = {r['id']: dict(r) for r in conn.execute(
        "SELECT * FROM consultant_engagement").fetchall()}
    consultants = {r['id']: dict(r) for r in conn.execute(
        "SELECT * FROM consultant").fetchall()}
    return engagements, consultants


def get_consultant_spend_report(conn, date_from=None, date_to=None, dept_id=None) -> list[dict]:
    """Per-consultant rollup: hours, time cost (None if any claimed entry
    has no resolvable rate), charge total, engagement_count. Bounded by
    time_entry.work_date / charge.charge_date, same convention as
    get_wo_time_variance_report's date filter."""
    ensure_consultant_tables(conn)
    engagements, consultants = _engagement_and_consultant_cache(conn)

    t_conds, t_params = [], []
    if date_from:
        t_conds.append("t.work_date >= %s")
        t_params.append(date_from)
    if date_to:
        t_conds.append("t.work_date <= %s")
        t_params.append(date_to)
    if dept_id:
        t_conds.append("e.dept_id = %s")
        t_params.append(dept_id)
    t_where = ("AND " + " AND ".join(t_conds)) if t_conds else ""
    time_rows = conn.execute(f"""
        SELECT t.*, e.consultant_id, e.dept_id AS engagement_dept_id
        FROM consultant_time_entry t
        JOIN consultant_engagement e ON e.id = t.engagement_id
        WHERE 1=1 {t_where}
    """, t_params).fetchall()

    c_conds, c_params = [], []
    if date_from:
        c_conds.append("ch.charge_date >= %s")
        c_params.append(date_from)
    if date_to:
        c_conds.append("ch.charge_date <= %s")
        c_params.append(date_to)
    if dept_id:
        c_conds.append("e.dept_id = %s")
        c_params.append(dept_id)
    c_where = ("AND " + " AND ".join(c_conds)) if c_conds else ""
    charge_rows = conn.execute(f"""
        SELECT ch.*, e.consultant_id
        FROM consultant_charge ch
        JOIN consultant_engagement e ON e.id = ch.engagement_id
        WHERE 1=1 {c_where}
    """, c_params).fetchall()

    acc: dict[int, dict] = {}
    for r in time_rows:
        cid = r['consultant_id']
        engagement = engagements[r['engagement_id']]
        consultant = consultants[cid]
        a = acc.setdefault(cid, {
            'consultant_id': cid, 'consultant_name': consultant['display_name'],
            'hours': 0.0, 'time_cost': 0.0, 'has_unresolved_rate': False,
            'charge_total': 0.0, 'engagement_ids': set(),
        })
        a['engagement_ids'].add(r['engagement_id'])
        a['hours'] += r['hours'] or 0.0
        cost = _resolve_time_entry_cost(dict(r), engagement, consultant)
        if cost is None:
            a['has_unresolved_rate'] = True
        else:
            a['time_cost'] += cost

    for r in charge_rows:
        cid = r['consultant_id']
        consultant = consultants[cid]
        a = acc.setdefault(cid, {
            'consultant_id': cid, 'consultant_name': consultant['display_name'],
            'hours': 0.0, 'time_cost': 0.0, 'has_unresolved_rate': False,
            'charge_total': 0.0, 'engagement_ids': set(),
        })
        a['engagement_ids'].add(r['engagement_id'])
        a['charge_total'] += r['amount'] or 0.0

    result = []
    for a in acc.values():
        result.append({
            'consultant_id': a['consultant_id'],
            'consultant_name': a['consultant_name'],
            'engagement_count': len(a['engagement_ids']),
            'hours': a['hours'],
            'time_cost': None if a['has_unresolved_rate'] else a['time_cost'],
            'charge_total': a['charge_total'],
            'grand_total': (None if a['has_unresolved_rate']
                            else a['time_cost'] + a['charge_total']),
        })
    result.sort(key=lambda d: d['consultant_name'])
    return result


def get_engagement_spend_report(conn, date_from=None, date_to=None,
                                 dept_id=None, status=None) -> list[dict]:
    """Per-engagement rollup: consultant_name, dept_name, hours, time_cost,
    charge_total, grand_total, invoiced_total (SUM of linked ap_invoice
    amounts), open_balance (amount - paid, same shape as
    accounting_core.get_dso/get_dpo)."""
    ensure_consultant_tables(conn)
    conds, params = [], []
    if dept_id:
        conds.append("e.dept_id = %s")
        params.append(dept_id)
    if status:
        conds.append("e.status = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    engagement_rows = conn.execute(f"""
        SELECT e.*, c.display_name AS consultant_name,
               c.default_hourly_rate AS consultant_default_rate, d.dept_name
        FROM consultant_engagement e
        JOIN consultant c ON c.id = e.consultant_id
        LEFT JOIN dept d ON d.dept_id = e.dept_id
        {where}
        ORDER BY e.id DESC
    """, params).fetchall()

    result = []
    for e in engagement_rows:
        engagement = dict(e)
        consultant = {'default_hourly_rate': e['consultant_default_rate']}

        t_conds, t_params = ["t.engagement_id = %s"], [e['id']]
        if date_from:
            t_conds.append("t.work_date >= %s")
            t_params.append(date_from)
        if date_to:
            t_conds.append("t.work_date <= %s")
            t_params.append(date_to)
        time_rows = conn.execute(
            f"SELECT * FROM consultant_time_entry t WHERE {' AND '.join(t_conds)}",
            t_params).fetchall()

        c_conds, c_params = ["ch.engagement_id = %s"], [e['id']]
        if date_from:
            c_conds.append("ch.charge_date >= %s")
            c_params.append(date_from)
        if date_to:
            c_conds.append("ch.charge_date <= %s")
            c_params.append(date_to)
        charge_rows = conn.execute(
            f"SELECT * FROM consultant_charge ch WHERE {' AND '.join(c_conds)}",
            c_params).fetchall()

        hours = sum(r['hours'] or 0.0 for r in time_rows)
        has_unresolved = False
        time_cost = 0.0
        for r in time_rows:
            cost = _resolve_time_entry_cost(dict(r), engagement, consultant)
            if cost is None:
                has_unresolved = True
            else:
                time_cost += cost
        charge_total = sum(r['amount'] or 0.0 for r in charge_rows)

        ap_row = conn.execute("""
            SELECT COALESCE(SUM(i.amount), 0) AS invoiced,
                   COALESCE(SUM(i.amount), 0) - COALESCE((
                       SELECT SUM(p.amount) FROM ap_payment p
                       JOIN consultant_invoice ci2 ON ci2.ap_invoice_id = p.invoice_id
                       WHERE ci2.engagement_id = %s
                   ), 0) AS open_balance
            FROM ap_invoice i
            JOIN consultant_invoice ci ON ci.ap_invoice_id = i.id
            WHERE ci.engagement_id = %s
        """, (e['id'], e['id'])).fetchone()

        result.append({
            'engagement_id': e['id'],
            'engagement_number': e['engagement_number'],
            'title': e['title'],
            'consultant_name': e['consultant_name'],
            'dept_name': e['dept_name'],
            'status': e['status'],
            'hours': hours,
            'time_cost': None if has_unresolved else time_cost,
            'charge_total': charge_total,
            'grand_total': None if has_unresolved else (time_cost + charge_total),
            'invoiced_total': float(ap_row['invoiced']) if ap_row else 0.0,
            'open_balance': float(ap_row['open_balance']) if ap_row else 0.0,
        })
    return result


def get_dept_consultant_spend_report(conn, date_from=None, date_to=None) -> list[dict]:
    """Per-department rollup for budget owners: dept_name, engagement_count,
    consultant_count, hours, total_cost (None-safe sum — an engagement with
    an unresolved rate is skipped from the total rather than fabricating 0,
    same 'skip, don't fabricate' rule as the other two reports)."""
    ensure_consultant_tables(conn)
    engagement_report = get_engagement_spend_report(conn, date_from, date_to)
    acc: dict[str, dict] = {}
    for e in engagement_report:
        dept_name = e['dept_name'] or 'Unassigned'
        a = acc.setdefault(dept_name, {
            'dept_name': dept_name, 'engagement_count': 0,
            'consultant_names': set(), 'hours': 0.0, 'total_cost': 0.0,
            'has_unresolved': False,
        })
        a['engagement_count'] += 1
        a['consultant_names'].add(e['consultant_name'])
        a['hours'] += e['hours']
        if e['grand_total'] is None:
            a['has_unresolved'] = True
        else:
            a['total_cost'] += e['grand_total']
    result = []
    for a in acc.values():
        result.append({
            'dept_name': a['dept_name'],
            'engagement_count': a['engagement_count'],
            'consultant_count': len(a['consultant_names']),
            'hours': a['hours'],
            'total_cost': None if a['has_unresolved'] else a['total_cost'],
        })
    result.sort(key=lambda d: d['dept_name'])
    return result
