"""Qt-free Marketing dashboard data layer."""


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
