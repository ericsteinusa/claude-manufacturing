"""Qt-free purchasing dashboard data layer."""



def get_purchasing_dashboard(conn) -> dict:
    """Return dict with keys: pos, recent_pos.

    pos: {draft, pending_approval, sent, partial, received, open, total}
    recent_pos: list of last 8 PO rows (id, po_number, order_date,
                expected_date, status, supplier_name)
    """
    po_row = conn.execute(
        "SELECT "
        "COUNT(*) FILTER (WHERE status = 'draft') AS draft, "
        "COUNT(*) FILTER (WHERE status = 'pending_approval') AS pending_approval, "
        "COUNT(*) FILTER (WHERE status = 'sent') AS sent, "
        "COUNT(*) FILTER (WHERE status = 'partial') AS partial, "
        "COUNT(*) FILTER (WHERE status = 'received') AS received, "
        "COUNT(*) FILTER (WHERE status NOT IN ('received','cancelled')) AS open, "
        "COUNT(*) AS total "
        "FROM purchase_order"
    ).fetchone()

    recent_rows = conn.execute(
        "SELECT po.id, po.po_number, po.order_date, po.expected_date, po.status, "
        "COALESCE(s.company_name, '') AS supplier_name "
        "FROM purchase_order po "
        "LEFT JOIN supplier s ON s.id = po.supplier_id "
        "ORDER BY po.id DESC LIMIT 8"
    ).fetchall()

    return {
        'pos': dict(po_row) if po_row else {},
        'recent_pos': [dict(r) for r in recent_rows],
    }
