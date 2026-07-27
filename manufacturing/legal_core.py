"""Qt-free Legal data layer — dashboard, contracts, compliance, litigation."""

CONTRACT_TYPES = (
    'NDA', 'Service Agreement', 'Lease', 'Vendor',
    'Employment', 'Licensing', 'Partnership', 'Other',
)
CONTRACT_STATUSES = ('Draft', 'Active', 'Renewed', 'Expired', 'Terminated')

COMPLIANCE_STATUSES = ('Pending', 'In Progress', 'Complete', 'Overdue')

LITIGATION_TYPES = (
    'Civil', 'Contract Dispute', 'IP', 'Employment', 'Regulatory', 'Other',
)
LITIGATION_STATUSES = ('Open', 'In Discovery', 'Settled', 'Dismissed', 'Closed')

IP_TYPES = ('Patent', 'Trademark', 'Copyright', 'Trade Secret')
IP_STATUSES = ('Pending', 'Filed', 'Registered', 'Expired', 'Abandoned')

EMPLOYMENT_MATTER_TYPES = (
    'Discrimination', 'Wage & Hour', 'Termination', 'Harassment', 'Other',
)
EMPLOYMENT_STATUSES = ('Open', 'Investigating', 'Resolved', 'Closed')

GOVERNANCE_CATEGORIES = ('Bylaw', 'Board Resolution', 'Policy', 'Charter')
GOVERNANCE_STATUSES = ('Active', 'Under Review', 'Superseded', 'Retired')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_legal_dashboard(conn) -> dict:
    """Return dict with keys: contracts, compliance, litigation, recent_contracts.

    contracts:   {total, active, draft}
    compliance:  {total, pending, completed}
    litigation:  {total, open, closed}
    recent_contracts: list of last 8 rows
                      (id, title, counterparty, contract_type, value, status, end_date)
    """
    c = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'Active') AS active, "
        "COUNT(*) FILTER (WHERE status = 'Draft') AS draft "
        "FROM legal_contract"
    ).fetchone()
    contracts = dict(c) if c else {'total': 0, 'active': 0, 'draft': 0}

    comp = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'Pending') AS pending, "
        "COUNT(*) FILTER (WHERE status = 'Completed') AS completed "
        "FROM legal_compliance"
    ).fetchone()
    compliance = dict(comp) if comp else {'total': 0, 'pending': 0, 'completed': 0}

    lit = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'Open') AS open, "
        "COUNT(*) FILTER (WHERE status = 'Closed') AS closed "
        "FROM legal_litigation"
    ).fetchone()
    litigation = dict(lit) if lit else {'total': 0, 'open': 0, 'closed': 0}

    rows = conn.execute(
        "SELECT id, title, counterparty, contract_type, value, status, end_date "
        "FROM legal_contract "
        "ORDER BY id DESC LIMIT 8"
    ).fetchall()

    return {
        'contracts': contracts,
        'compliance': compliance,
        'litigation': litigation,
        'recent_contracts': [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

def list_contracts(conn, status=None, contract_type=None, search=None) -> list:
    sql = (
        "SELECT id, title, counterparty, contract_type, value, "
        "start_date, end_date, owner, status "
        "FROM legal_contract WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if contract_type:
        sql += " AND contract_type = %s"
        params.append(contract_type)
    if search:
        sql += " AND (title ILIKE %s OR counterparty ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_contract(conn, contract_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM legal_contract WHERE id = %s", (contract_id,)
    ).fetchone()
    return dict(row) if row else None


def create_contract(
    conn, title: str, counterparty: str, contract_type: str,
    value: float, start_date: str, end_date: str,
    owner: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO legal_contract "
        "(title, counterparty, contract_type, value, start_date, end_date, owner, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (title, counterparty, contract_type, value or 0,
         start_date, end_date, owner, status or 'Draft', notes),
    )
    return cur.fetchone()[0]


def update_contract(conn, contract_id: int, **fields) -> None:
    allowed = {
        'title', 'counterparty', 'contract_type', 'value',
        'start_date', 'end_date', 'owner', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE legal_contract SET {set_clause} WHERE id = %s",
        list(cols.values()) + [contract_id],
    )


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

def list_compliance(conn, status=None, search=None) -> list:
    sql = (
        "SELECT id, requirement, regulation, owner, due_date, "
        "completed_date, status "
        "FROM legal_compliance WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (requirement ILIKE %s OR regulation ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY due_date ASC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_compliance_item(conn, item_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM legal_compliance WHERE id = %s", (item_id,)
    ).fetchone()
    return dict(row) if row else None


def create_compliance(
    conn, requirement: str, regulation: str, owner: str,
    due_date: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO legal_compliance "
        "(requirement, regulation, owner, due_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (requirement, regulation, owner, due_date or None,
         status or 'Pending', notes),
    )
    return cur.fetchone()[0]


def update_compliance(conn, item_id: int, **fields) -> None:
    allowed = {
        'requirement', 'regulation', 'owner', 'due_date',
        'completed_date', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE legal_compliance SET {set_clause} WHERE id = %s",
        list(cols.values()) + [item_id],
    )


# ---------------------------------------------------------------------------
# Litigation
# ---------------------------------------------------------------------------

def list_litigation(conn, status=None, case_type=None, search=None) -> list:
    sql = (
        "SELECT id, case_name, opposing_party, court, case_type, "
        "filed_date, status, outcome "
        "FROM legal_litigation WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if case_type:
        sql += " AND case_type = %s"
        params.append(case_type)
    if search:
        sql += " AND (case_name ILIKE %s OR opposing_party ILIKE %s OR court ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY filed_date DESC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_litigation_case(conn, case_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM legal_litigation WHERE id = %s", (case_id,)
    ).fetchone()
    return dict(row) if row else None


def create_litigation(
    conn, case_name: str, opposing_party: str, court: str,
    case_type: str, filed_date: str, status: str, outcome: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO legal_litigation "
        "(case_name, opposing_party, court, case_type, filed_date, status, outcome, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (case_name, opposing_party, court, case_type,
         filed_date or None, status or 'Open', outcome, notes),
    )
    return cur.fetchone()[0]


def update_litigation(conn, case_id: int, **fields) -> None:
    allowed = {
        'case_name', 'opposing_party', 'court', 'case_type',
        'filed_date', 'status', 'outcome', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE legal_litigation SET {set_clause} WHERE id = %s",
        list(cols.values()) + [case_id],
    )


# ---------------------------------------------------------------------------
# Intellectual Property
# ---------------------------------------------------------------------------

def list_ip(conn, status=None, search=None) -> list:
    sql = (
        "SELECT id, title, ip_type, registration_no, jurisdiction, filed_date, "
        "expiry_date, status FROM legal_ip WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (title ILIKE %s OR registration_no ILIKE %s OR jurisdiction ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_ip(conn, title, ip_type, registration_no, jurisdiction,
              filed_date, expiry_date, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO legal_ip "
        "(title, ip_type, registration_no, jurisdiction, filed_date, expiry_date, "
        "status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (title, ip_type, registration_no, jurisdiction, filed_date or None,
         expiry_date or None, status or 'Pending', notes),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Employment Law
# ---------------------------------------------------------------------------

def list_employment(conn, status=None, search=None) -> list:
    sql = (
        "SELECT id, matter, employee, matter_type, owner, opened_date, "
        "closed_date, status FROM legal_employment WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (matter ILIKE %s OR employee ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_employment(conn, matter, employee, matter_type, owner,
                       opened_date, closed_date, status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO legal_employment "
        "(matter, employee, matter_type, owner, opened_date, closed_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (matter, employee, matter_type, owner, opened_date or None,
         closed_date or None, status or 'Open', notes),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Corporate Governance
# ---------------------------------------------------------------------------

def list_governance(conn, status=None, search=None) -> list:
    sql = (
        "SELECT id, item, category, owner, ref_date, reference, status "
        "FROM legal_governance WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (item ILIKE %s OR reference ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_governance(conn, item, category, owner, ref_date, reference,
                       status, notes) -> int:
    cur = conn.execute(
        "INSERT INTO legal_governance "
        "(item, category, owner, ref_date, reference, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (item, category, owner, ref_date or None, reference,
         status or 'Active', notes),
    )
    return cur.fetchone()[0]
