"""Qt-free IT dashboard data layer."""


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
