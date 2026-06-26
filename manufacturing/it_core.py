"""Qt-free IT data layer — dashboard, tickets, assets, repairs, software, licenses, network."""

from datetime import date

TICKET_STATUSES = ('open', 'in_progress', 'resolved', 'closed')
TICKET_PRIORITIES = ('low', 'medium', 'high', 'critical')
ISSUE_TYPES = (
    'Hardware', 'Software', 'Network', 'Email', 'Phone',
    'Printer', 'Access / Permissions', 'Account', 'Other',
)
ASSET_STATUSES = ('active', 'spare', 'repair', 'retired', 'lost')
ASSET_TYPES = (
    'Desktop', 'Laptop', 'Monitor', 'Server', 'Printer',
    'Phone', 'Tablet', 'Switch', 'Router', 'UPS', 'Other',
)

REPAIR_STATUSES = ('open', 'in_progress', 'completed', 'cancelled')
REPAIR_PRIORITIES = ('low', 'medium', 'high', 'critical')

SOFTWARE_STATUSES = ('pending', 'installed', 'removed')

LICENSE_TYPES = ('perpetual', 'subscription', 'volume', 'oem', 'freeware', 'open_source')
LICENSE_STATUSES = ('active', 'expired', 'cancelled')

NETWORK_DEVICE_TYPES = (
    'Router', 'Switch', 'Firewall', 'Access Point', 'Server',
    'NAS', 'Printer', 'IP Camera', 'VoIP Phone', 'Other',
)
NETWORK_DEVICE_STATUSES = ('online', 'offline', 'unknown', 'maintenance')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_it_dashboard(conn) -> dict:
    """Return dict with keys: tickets, assets, recent_tickets.

    tickets: {open_count, in_progress_count, critical_count, total_count}
    assets:  {total, active, repair}
    recent_tickets: list of last 8 rows
                    (id, ticket_number, requester, department, issue_type,
                     priority, status, submitted_date)
    """
    t = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE status = 'open') AS open_count, "
        "COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_count, "
        "COUNT(*) FILTER (WHERE priority = 'critical' AND status NOT IN ('resolved','closed')) AS critical_count, "
        "COUNT(*) AS total_count "
        "FROM it_ticket"
    ).fetchone()
    tickets = dict(t) if t else {'open_count': 0, 'in_progress_count': 0,
                                  'critical_count': 0, 'total_count': 0}

    a = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'active') AS active, "
        "COUNT(*) FILTER (WHERE status = 'repair') AS repair "
        "FROM it_asset"
    ).fetchone()
    assets = dict(a) if a else {'total': 0, 'active': 0, 'repair': 0}

    rows = conn.execute(
        "SELECT id, ticket_number, requester, department, issue_type, "
        "priority, status, submitted_date "
        "FROM it_ticket "
        "ORDER BY submitted_date DESC, id DESC LIMIT 8"
    ).fetchall()

    return {
        'tickets': tickets,
        'assets': assets,
        'recent_tickets': [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Ticket helpers
# ---------------------------------------------------------------------------

def next_ticket_number(conn) -> str:
    yr = date.today().year
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTRING(ticket_number FROM 10) AS INTEGER)) "
        "FROM it_ticket WHERE ticket_number LIKE %s",
        (f"TKT-{yr}-%",),
    ).fetchone()
    last = (row[0] or 0) if row else 0
    return f"TKT-{yr}-{last + 1:04d}"


def list_tickets(conn, status=None, priority=None, search=None) -> list:
    sql = (
        "SELECT id, ticket_number, requester, department, issue_type, "
        "priority, status, submitted_date, due_date, assigned_to "
        "FROM it_ticket WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if priority:
        sql += " AND priority = %s"
        params.append(priority)
    if search:
        sql += " AND (ticket_number ILIKE %s OR requester ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY submitted_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_ticket(conn, ticket_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM it_ticket WHERE id = %s", (ticket_id,)
    ).fetchone()
    return dict(row) if row else None


def create_ticket(
    conn, ticket_number: str, requester: str, department: str,
    issue_type: str, description: str, priority: str,
    assigned_to: str, submitted_date: str, due_date: str,
    notes: str, created_by: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO it_ticket "
        "(ticket_number, requester, department, issue_type, description, "
        "priority, assigned_to, submitted_date, due_date, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (ticket_number, requester, department, issue_type, description,
         priority, assigned_to, submitted_date, due_date, notes, created_by),
    )
    return cur.fetchone()[0]


def update_ticket(conn, ticket_id: int, **fields) -> None:
    allowed = {
        'requester', 'department', 'issue_type', 'description', 'priority',
        'assigned_to', 'submitted_date', 'due_date', 'resolved_date',
        'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_ticket SET {set_clause} WHERE id = %s",
        list(cols.values()) + [ticket_id],
    )


def set_ticket_status(conn, ticket_id: int, status: str) -> None:
    resolved = date.today().isoformat() if status in ('resolved', 'closed') else None
    if resolved:
        conn.execute(
            "UPDATE it_ticket SET status = %s, resolved_date = %s WHERE id = %s",
            (status, resolved, ticket_id),
        )
    else:
        conn.execute(
            "UPDATE it_ticket SET status = %s WHERE id = %s",
            (status, ticket_id),
        )


# ---------------------------------------------------------------------------
# Asset helpers
# ---------------------------------------------------------------------------

def list_assets(conn, status=None, asset_type=None, search=None) -> list:
    sql = (
        "SELECT id, asset_tag, asset_type, make, model, serial_number, "
        "assigned_to, department, purchase_date, warranty_exp, status "
        "FROM it_asset WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if asset_type:
        sql += " AND asset_type = %s"
        params.append(asset_type)
    if search:
        sql += " AND (asset_tag ILIKE %s OR make ILIKE %s OR model ILIKE %s OR assigned_to ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY asset_tag"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_asset(conn, asset_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM it_asset WHERE id = %s", (asset_id,)
    ).fetchone()
    return dict(row) if row else None


def create_asset(
    conn, asset_tag: str, asset_type: str, make: str, model: str,
    serial_number: str, assigned_to: str, department: str,
    purchase_date: str, warranty_exp: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO it_asset "
        "(asset_tag, asset_type, make, model, serial_number, assigned_to, "
        "department, purchase_date, warranty_exp, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (asset_tag, asset_type, make, model, serial_number, assigned_to,
         department, purchase_date, warranty_exp, status, notes),
    )
    return cur.fetchone()[0]


def update_asset(conn, asset_id: int, **fields) -> None:
    allowed = {
        'asset_tag', 'asset_type', 'make', 'model', 'serial_number',
        'assigned_to', 'department', 'purchase_date', 'warranty_exp',
        'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_asset SET {set_clause} WHERE id = %s",
        list(cols.values()) + [asset_id],
    )


# ---------------------------------------------------------------------------
# Asset History
# ---------------------------------------------------------------------------

_CREATE_ASSET_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS it_asset_history (
    id          SERIAL PRIMARY KEY,
    asset_tag   TEXT DEFAULT '',
    asset_id    INTEGER,
    event_type  TEXT DEFAULT '',
    description TEXT DEFAULT '',
    changed_by  TEXT DEFAULT '',
    changed_at  TIMESTAMP DEFAULT NOW()
)
"""


def _ensure_asset_history_table(conn) -> None:
    conn.execute(_CREATE_ASSET_HISTORY_TABLE)
    conn.commit()


def log_asset_event(
    conn, asset_tag: str, asset_id: int | None,
    event_type: str, description: str, changed_by: str,
) -> None:
    _ensure_asset_history_table(conn)
    conn.execute(
        "INSERT INTO it_asset_history "
        "(asset_tag, asset_id, event_type, description, changed_by) "
        "VALUES (%s,%s,%s,%s,%s)",
        (asset_tag, asset_id, event_type, description, changed_by),
    )


def list_asset_history(
    conn, asset_tag: str | None = None,
    event_type: str | None = None, limit: int = 300,
) -> list:
    _ensure_asset_history_table(conn)
    sql = (
        "SELECT id, asset_tag, asset_id, event_type, description, "
        "changed_by, changed_at "
        "FROM it_asset_history WHERE TRUE"
    )
    params: list = []
    if asset_tag:
        sql += " AND asset_tag ILIKE %s"
        params.append(f"%{asset_tag}%")
    if event_type:
        sql += " AND event_type = %s"
        params.append(event_type)
    sql += f" ORDER BY changed_at DESC, id DESC LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------------------------------------------------------------------------
# Hardware Repairs
# ---------------------------------------------------------------------------

_CREATE_REPAIR_TABLE = """
CREATE TABLE IF NOT EXISTS it_repair (
    id               SERIAL PRIMARY KEY,
    asset_tag        TEXT DEFAULT '',
    problem_description TEXT DEFAULT '',
    reported_by      TEXT DEFAULT '',
    reported_date    DATE,
    assigned_to      TEXT DEFAULT '',
    priority         TEXT DEFAULT 'medium',
    status           TEXT DEFAULT 'open',
    resolution       TEXT DEFAULT '',
    completed_date   DATE,
    notes            TEXT DEFAULT '',
    created_by       TEXT DEFAULT ''
)
"""


def _ensure_repair_table(conn) -> None:
    conn.execute(_CREATE_REPAIR_TABLE)
    conn.commit()


def list_repairs(conn, status=None, priority=None, search=None) -> list:
    _ensure_repair_table(conn)
    sql = (
        "SELECT id, asset_tag, problem_description, reported_by, reported_date, "
        "assigned_to, priority, status, completed_date "
        "FROM it_repair WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if priority:
        sql += " AND priority = %s"
        params.append(priority)
    if search:
        sql += " AND (asset_tag ILIKE %s OR reported_by ILIKE %s OR problem_description ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY reported_date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_repair(conn, repair_id: int) -> dict | None:
    _ensure_repair_table(conn)
    row = conn.execute("SELECT * FROM it_repair WHERE id = %s", (repair_id,)).fetchone()
    return dict(row) if row else None


def create_repair(
    conn, asset_tag: str, problem_description: str, reported_by: str,
    reported_date: str, assigned_to: str, priority: str,
    notes: str, created_by: str,
) -> int:
    _ensure_repair_table(conn)
    cur = conn.execute(
        "INSERT INTO it_repair "
        "(asset_tag, problem_description, reported_by, reported_date, "
        "assigned_to, priority, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,'open',%s,%s) RETURNING id",
        (asset_tag, problem_description, reported_by,
         reported_date or date.today().isoformat(),
         assigned_to, priority, notes, created_by),
    )
    return cur.fetchone()[0]


def update_repair(conn, repair_id: int, **fields) -> None:
    allowed = {
        'asset_tag', 'problem_description', 'reported_by', 'reported_date',
        'assigned_to', 'priority', 'status', 'resolution', 'completed_date', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_repair SET {set_clause} WHERE id = %s",
        list(cols.values()) + [repair_id],
    )


def set_repair_status(conn, repair_id: int, status: str) -> None:
    completed = date.today().isoformat() if status == 'completed' else None
    if completed:
        conn.execute(
            "UPDATE it_repair SET status = %s, completed_date = %s WHERE id = %s",
            (status, completed, repair_id),
        )
    else:
        conn.execute("UPDATE it_repair SET status = %s WHERE id = %s", (status, repair_id))


# ---------------------------------------------------------------------------
# Software Installations
# ---------------------------------------------------------------------------

_CREATE_SOFTWARE_TABLE = """
CREATE TABLE IF NOT EXISTS it_software_install (
    id            SERIAL PRIMARY KEY,
    asset_tag     TEXT DEFAULT '',
    software_name TEXT DEFAULT '',
    version       TEXT DEFAULT '',
    vendor        TEXT DEFAULT '',
    install_date  DATE,
    status        TEXT DEFAULT 'installed',
    installed_by  TEXT DEFAULT '',
    notes         TEXT DEFAULT '',
    created_by    TEXT DEFAULT ''
)
"""


def _ensure_software_table(conn) -> None:
    conn.execute(_CREATE_SOFTWARE_TABLE)
    conn.commit()


def list_software(conn, status=None, search=None) -> list:
    _ensure_software_table(conn)
    sql = (
        "SELECT id, asset_tag, software_name, version, vendor, "
        "install_date, status, installed_by "
        "FROM it_software_install WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (software_name ILIKE %s OR vendor ILIKE %s OR asset_tag ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY software_name, asset_tag"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_software(conn, sw_id: int) -> dict | None:
    _ensure_software_table(conn)
    row = conn.execute(
        "SELECT * FROM it_software_install WHERE id = %s", (sw_id,)
    ).fetchone()
    return dict(row) if row else None


def create_software(
    conn, asset_tag: str, software_name: str, version: str, vendor: str,
    install_date: str, status: str, installed_by: str, notes: str, created_by: str,
) -> int:
    _ensure_software_table(conn)
    cur = conn.execute(
        "INSERT INTO it_software_install "
        "(asset_tag, software_name, version, vendor, install_date, "
        "status, installed_by, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (asset_tag, software_name, version, vendor,
         install_date or date.today().isoformat(),
         status or 'installed', installed_by, notes, created_by),
    )
    return cur.fetchone()[0]


def update_software(conn, sw_id: int, **fields) -> None:
    allowed = {
        'asset_tag', 'software_name', 'version', 'vendor',
        'install_date', 'status', 'installed_by', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_software_install SET {set_clause} WHERE id = %s",
        list(cols.values()) + [sw_id],
    )


# ---------------------------------------------------------------------------
# Software Licenses
# ---------------------------------------------------------------------------

_CREATE_LICENSE_TABLE = """
CREATE TABLE IF NOT EXISTS it_license (
    id            SERIAL PRIMARY KEY,
    software_name TEXT DEFAULT '',
    vendor        TEXT DEFAULT '',
    license_key   TEXT DEFAULT '',
    license_type  TEXT DEFAULT 'perpetual',
    seats         INTEGER DEFAULT 1,
    seats_used    INTEGER DEFAULT 0,
    purchase_date DATE,
    expiry_date   DATE,
    cost          REAL DEFAULT 0,
    status        TEXT DEFAULT 'active',
    notes         TEXT DEFAULT '',
    created_by    TEXT DEFAULT ''
)
"""


def _ensure_license_table(conn) -> None:
    conn.execute(_CREATE_LICENSE_TABLE)
    conn.commit()


def list_licenses(conn, status=None, search=None) -> list:
    _ensure_license_table(conn)
    sql = (
        "SELECT id, software_name, vendor, license_type, seats, seats_used, "
        "purchase_date, expiry_date, cost, status "
        "FROM it_license WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (software_name ILIKE %s OR vendor ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY software_name"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_license(conn, license_id: int) -> dict | None:
    _ensure_license_table(conn)
    row = conn.execute(
        "SELECT * FROM it_license WHERE id = %s", (license_id,)
    ).fetchone()
    return dict(row) if row else None


def create_license(
    conn, software_name: str, vendor: str, license_key: str, license_type: str,
    seats: int, seats_used: int, purchase_date: str, expiry_date: str,
    cost: float, status: str, notes: str, created_by: str,
) -> int:
    _ensure_license_table(conn)
    cur = conn.execute(
        "INSERT INTO it_license "
        "(software_name, vendor, license_key, license_type, seats, seats_used, "
        "purchase_date, expiry_date, cost, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (software_name, vendor, license_key, license_type,
         seats or 1, seats_used or 0, purchase_date or None, expiry_date or None,
         cost or 0, status or 'active', notes, created_by),
    )
    return cur.fetchone()[0]


def update_license(conn, license_id: int, **fields) -> None:
    allowed = {
        'software_name', 'vendor', 'license_key', 'license_type',
        'seats', 'seats_used', 'purchase_date', 'expiry_date',
        'cost', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_license SET {set_clause} WHERE id = %s",
        list(cols.values()) + [license_id],
    )


# ---------------------------------------------------------------------------
# Network Devices
# ---------------------------------------------------------------------------

_CREATE_NETWORK_TABLE = """
CREATE TABLE IF NOT EXISTS it_network_device (
    id           SERIAL PRIMARY KEY,
    hostname     TEXT DEFAULT '',
    ip_address   TEXT DEFAULT '',
    mac_address  TEXT DEFAULT '',
    device_type  TEXT DEFAULT '',
    manufacturer TEXT DEFAULT '',
    model        TEXT DEFAULT '',
    location     TEXT DEFAULT '',
    status       TEXT DEFAULT 'unknown',
    last_seen    DATE,
    notes        TEXT DEFAULT '',
    created_by   TEXT DEFAULT ''
)
"""


def _ensure_network_table(conn) -> None:
    conn.execute(_CREATE_NETWORK_TABLE)
    conn.commit()


def list_network_devices(conn, status=None, device_type=None, search=None) -> list:
    _ensure_network_table(conn)
    sql = (
        "SELECT id, hostname, ip_address, mac_address, device_type, "
        "manufacturer, model, location, status, last_seen "
        "FROM it_network_device WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if device_type:
        sql += " AND device_type = %s"
        params.append(device_type)
    if search:
        sql += " AND (hostname ILIKE %s OR ip_address ILIKE %s OR location ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY hostname"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_network_device(conn, device_id: int) -> dict | None:
    _ensure_network_table(conn)
    row = conn.execute(
        "SELECT * FROM it_network_device WHERE id = %s", (device_id,)
    ).fetchone()
    return dict(row) if row else None


def create_network_device(
    conn, hostname: str, ip_address: str, mac_address: str, device_type: str,
    manufacturer: str, model: str, location: str, status: str,
    last_seen: str, notes: str, created_by: str,
) -> int:
    _ensure_network_table(conn)
    cur = conn.execute(
        "INSERT INTO it_network_device "
        "(hostname, ip_address, mac_address, device_type, manufacturer, model, "
        "location, status, last_seen, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (hostname, ip_address, mac_address, device_type, manufacturer, model,
         location, status or 'unknown', last_seen or None, notes, created_by),
    )
    return cur.fetchone()[0]


def update_network_device(conn, device_id: int, **fields) -> None:
    allowed = {
        'hostname', 'ip_address', 'mac_address', 'device_type',
        'manufacturer', 'model', 'location', 'status', 'last_seen', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE it_network_device SET {set_clause} WHERE id = %s",
        list(cols.values()) + [device_id],
    )
