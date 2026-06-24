"""Qt-free Marketing data layer — dashboard, campaigns, leads, content."""

CHANNELS = (
    'Email', 'Social', 'Search', 'Display', 'Content',
    'Event', 'PR', 'Direct Mail', 'Webinar', 'Other',
)
OBJECTIVES = (
    'Awareness', 'Lead Gen', 'Conversion', 'Retention', 'Launch', 'Re-engagement',
)
CAMPAIGN_STATUSES = ('Planned', 'Active', 'Paused', 'Completed', 'Cancelled')

LEAD_SOURCES = (
    'Web', 'Referral', 'Event', 'Cold Outreach', 'Social', 'Ad', 'Partner', 'Other',
)
LEAD_STATUSES = ('New', 'Contacted', 'Qualified', 'Nurturing', 'Converted', 'Lost')

CONTENT_TYPES = (
    'Blog', 'Whitepaper', 'Video', 'Infographic', 'Social Post',
    'Email', 'Ad Copy', 'Case Study', 'Landing Page',
)
CONTENT_STATUSES = ('Draft', 'In Review', 'Approved', 'Published', 'Archived')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_marketing_dashboard(conn) -> dict:
    """Return dict with keys: campaigns, leads, content, recent_campaigns.

    campaigns: {total, active, planned}
    leads:     {total, new_count, qualified}
    content:   {total, draft, published}
    recent_campaigns: list of last 8 rows
                      (id, name, channel, objective, status, start_date, end_date, budget)
    """
    c = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'Active') AS active, "
        "COUNT(*) FILTER (WHERE status = 'Planned') AS planned "
        "FROM marketing_campaign"
    ).fetchone()
    campaigns = dict(c) if c else {'total': 0, 'active': 0, 'planned': 0}

    leads_row = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'New') AS new_count, "
        "COUNT(*) FILTER (WHERE status = 'Qualified') AS qualified "
        "FROM marketing_lead"
    ).fetchone()
    leads = dict(leads_row) if leads_row else {'total': 0, 'new_count': 0, 'qualified': 0}

    ct = conn.execute(
        "SELECT "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE status = 'Draft') AS draft, "
        "COUNT(*) FILTER (WHERE status = 'Published') AS published "
        "FROM marketing_content"
    ).fetchone()
    content = dict(ct) if ct else {'total': 0, 'draft': 0, 'published': 0}

    rows = conn.execute(
        "SELECT id, name, channel, objective, status, start_date, end_date, budget "
        "FROM marketing_campaign "
        "ORDER BY id DESC LIMIT 8"
    ).fetchall()

    return {
        'campaigns': campaigns,
        'leads': leads,
        'content': content,
        'recent_campaigns': [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

def list_campaigns(conn, status=None, channel=None, search=None) -> list:
    sql = (
        "SELECT id, name, channel, objective, owner, start_date, end_date, budget, status "
        "FROM marketing_campaign WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if channel:
        sql += " AND channel = %s"
        params.append(channel)
    if search:
        sql += " AND (name ILIKE %s OR objective ILIKE %s OR owner ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_campaign(conn, campaign_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM marketing_campaign WHERE id = %s", (campaign_id,)
    ).fetchone()
    return dict(row) if row else None


def create_campaign(
    conn, name: str, channel: str, objective: str, owner: str,
    start_date: str, end_date: str, budget: float, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO marketing_campaign "
        "(name, channel, objective, owner, start_date, end_date, budget, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name, channel, objective, owner, start_date, end_date,
         budget or 0, status or 'Planned', notes),
    )
    return cur.fetchone()[0]


def update_campaign(conn, campaign_id: int, **fields) -> None:
    allowed = {
        'name', 'channel', 'objective', 'owner',
        'start_date', 'end_date', 'budget', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE marketing_campaign SET {set_clause} WHERE id = %s",
        list(cols.values()) + [campaign_id],
    )


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def list_leads(conn, status=None, source=None, search=None) -> list:
    sql = (
        "SELECT id, name, company, email, source, owner, captured_date, status "
        "FROM marketing_lead WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if source:
        sql += " AND source = %s"
        params.append(source)
    if search:
        sql += " AND (name ILIKE %s OR company ILIKE %s OR email ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    sql += " ORDER BY captured_date DESC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_lead(conn, lead_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM marketing_lead WHERE id = %s", (lead_id,)
    ).fetchone()
    return dict(row) if row else None


def create_lead(
    conn, name: str, company: str, email: str, source: str,
    owner: str, captured_date: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO marketing_lead "
        "(name, company, email, source, owner, captured_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name, company, email, source, owner,
         captured_date or None, status or 'New', notes),
    )
    return cur.fetchone()[0]


def update_lead(conn, lead_id: int, **fields) -> None:
    allowed = {
        'name', 'company', 'email', 'source', 'owner',
        'captured_date', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE marketing_lead SET {set_clause} WHERE id = %s",
        list(cols.values()) + [lead_id],
    )


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def list_content(conn, status=None, content_type=None, search=None) -> list:
    sql = (
        "SELECT id, title, content_type, channel, author, due_date, publish_date, status "
        "FROM marketing_content WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if content_type:
        sql += " AND content_type = %s"
        params.append(content_type)
    if search:
        sql += " AND (title ILIKE %s OR author ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY due_date ASC NULLS LAST, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_content_item(conn, item_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM marketing_content WHERE id = %s", (item_id,)
    ).fetchone()
    return dict(row) if row else None


def create_content(
    conn, title: str, content_type: str, channel: str, author: str,
    due_date: str, publish_date: str, status: str, notes: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO marketing_content "
        "(title, content_type, channel, author, due_date, publish_date, status, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (title, content_type, channel, author,
         due_date or None, publish_date or None, status or 'Draft', notes),
    )
    return cur.fetchone()[0]


def update_content(conn, item_id: int, **fields) -> None:
    allowed = {
        'title', 'content_type', 'channel', 'author',
        'due_date', 'publish_date', 'status', 'notes',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE marketing_content SET {set_clause} WHERE id = %s",
        list(cols.values()) + [item_id],
    )
