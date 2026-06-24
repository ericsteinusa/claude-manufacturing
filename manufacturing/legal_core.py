"""Qt-free Legal dashboard data layer."""


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
