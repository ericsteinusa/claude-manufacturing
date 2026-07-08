"""supplier_scorecard_core.py — Qt-free aggregation for the Supplier
Performance Scorecard (P2-C from COMPETITIVE_GAP_ANALYSIS.md).

Pure computed view over existing tables — no tables of its own, same
convention as atp_core.py:
  - purchase_order / po_item (purchase_orders_core.py): on-time delivery %
    (expected_date vs. received_date, over fully 'received' POs only — a
    'partial' PO has no single receipt date to compare) and quantity fill
    rate % (qty_received / qty_ordered, over POs that have actually been
    placed: 'sent', 'partial', or 'received' — draft/pending_approval
    haven't gone to the supplier yet, cancelled was never meant to be
    fulfilled).
  - qa_supplier (owned by the QA module, see quality_core.py): quality
    reject rate, derived from `ppm` (parts-per-million). qa_supplier.supplier
    is a free-text name field, not a supplier_id FK, so it's matched to
    supplier.company_name by a case-insensitive/trimmed name — a supplier
    with no matching qa_supplier row(s) simply has no quality component,
    not a zero/worst score (see _composite_score's renormalisation).

Every function takes an open connection; the caller owns the transaction
(same convention as purchase_orders_core / rfq_core / atp_core).
"""

from __future__ import annotations

from datetime import date, timedelta

# Composite-score weights (sum to 1.0; renormalised over whichever metrics
# actually have data for a given supplier — see _composite_score).
ON_TIME_WEIGHT = 0.40
FILL_RATE_WEIGHT = 0.35
QUALITY_WEIGHT = 0.25

# PO statuses considered "placed" for fill-rate purposes.
_PLACED_STATUSES = ('sent', 'partial', 'received')

# Trailing window used when get_supplier_scorecard_detail isn't given an
# explicit date range.
_DEFAULT_TREND_DAYS = 180


def _supplier_display_name(row):
    """Mirror suppliers.py's display convention: company_name, else name."""
    company = (row.get('company_name') or '').strip()
    if company:
        return company
    return f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()


def _qa_supplier_table_exists(conn):
    """True if qa_supplier exists. It's owned by the QA module, not here, so
    it may not exist yet on a fresh DB — checked via to_regclass rather than
    try/except so a missing table can't abort the caller's transaction."""
    row = conn.execute(
        "SELECT to_regclass('qa_supplier') IS NOT NULL AS tbl_exists"
    ).fetchone()
    return bool(row and row['tbl_exists'])


def _composite_score(on_time_pct, fill_rate_pct, quality_score_pct):
    """Weighted average over whichever of the three metrics are not None,
    renormalised so a supplier missing one metric (most commonly: no
    matching qa_supplier row) isn't penalized for data that was never
    entered. Returns None if none of the three have data.
    """
    parts = [
        (on_time_pct, ON_TIME_WEIGHT),
        (fill_rate_pct, FILL_RATE_WEIGHT),
        (quality_score_pct, QUALITY_WEIGHT),
    ]
    available = [(v, w) for v, w in parts if v is not None]
    if not available:
        return None
    total_weight = sum(w for _, w in available)
    return round(sum(v * w for v, w in available) / total_weight, 1)


def _date_conds(alias, date_from, date_to):
    conds, params = [], []
    if date_from:
        conds.append(f"{alias}.order_date >= %s")
        params.append(date_from)
    if date_to:
        conds.append(f"{alias}.order_date <= %s")
        params.append(date_to)
    return conds, params


def _on_time_by_supplier(conn, date_from=None, date_to=None, supplier_id=None):
    conds, params = _date_conds('po', date_from, date_to)
    conds = [
        "po.status = 'received'",
        "po.expected_date IS NOT NULL",
        "po.received_date IS NOT NULL",
        "po.supplier_id IS NOT NULL",
        *conds,
    ]
    if supplier_id:
        conds.append("po.supplier_id = %s")
        params.append(supplier_id)
    rows = conn.execute(f"""
        SELECT po.supplier_id,
               COUNT(*) AS received_count,
               COUNT(*) FILTER (WHERE po.received_date <= po.expected_date)
                   AS on_time_count
        FROM purchase_order po
        WHERE {" AND ".join(conds)}
        GROUP BY po.supplier_id
    """, params).fetchall()
    return {r['supplier_id']: dict(r) for r in rows}


def _fill_rate_by_supplier(conn, date_from=None, date_to=None, supplier_id=None):
    conds, params = _date_conds('po', date_from, date_to)
    conds = ["po.status = ANY(%s)", "po.supplier_id IS NOT NULL", *conds]
    params = [list(_PLACED_STATUSES), *params]
    if supplier_id:
        conds.append("po.supplier_id = %s")
        params.append(supplier_id)
    rows = conn.execute(f"""
        SELECT po.supplier_id,
               COALESCE(SUM(pi.qty_ordered), 0) AS qty_ordered,
               COALESCE(SUM(pi.qty_received), 0) AS qty_received
        FROM po_item pi
        JOIN purchase_order po ON po.id = pi.po_id
        WHERE {" AND ".join(conds)}
        GROUP BY po.supplier_id
    """, params).fetchall()
    return {r['supplier_id']: dict(r) for r in rows}


def _quality_by_name_key(conn):
    """{lower(trim(supplier_name)): {avg_ppm, material_count}}. Empty dict
    if qa_supplier doesn't exist yet or has no usable rows."""
    if not _qa_supplier_table_exists(conn):
        return {}
    rows = conn.execute("""
        SELECT lower(trim(supplier)) AS name_key,
               AVG(NULLIF(regexp_replace(ppm, '[^0-9.]', '', 'g'), '')::numeric)
                   AS avg_ppm,
               COUNT(*) AS material_count
        FROM qa_supplier
        WHERE supplier IS NOT NULL AND trim(supplier) != ''
        GROUP BY lower(trim(supplier))
    """).fetchall()
    return {r['name_key']: dict(r) for r in rows}


def _score_row(supplier_row, on_time_row, fill_row, quality_row):
    """Build one scorecard dict from the raw per-metric rows (any may be
    None/absent — see get_supplier_scorecards)."""
    name = _supplier_display_name(supplier_row)

    on_time_pct = (
        round(on_time_row['on_time_count'] / on_time_row['received_count'] * 100, 1)
        if on_time_row and on_time_row['received_count'] else None
    )
    fill_rate_pct = (
        round(fill_row['qty_received'] / fill_row['qty_ordered'] * 100, 1)
        if fill_row and fill_row['qty_ordered'] else None
    )
    quality_reject_pct = (
        round(float(quality_row['avg_ppm']) / 10000.0, 2)
        if quality_row and quality_row['avg_ppm'] is not None else None
    )
    quality_score_pct = (
        round(100.0 - quality_reject_pct, 1)
        if quality_reject_pct is not None else None
    )

    return {
        'supplier_id': supplier_row['id'],
        'supplier_name': name,
        'on_time_pct': on_time_pct,
        'on_time_sample': on_time_row['received_count'] if on_time_row else 0,
        'fill_rate_pct': fill_rate_pct,
        'quality_reject_pct': quality_reject_pct,
        'quality_sample': quality_row['material_count'] if quality_row else 0,
        'composite_score': _composite_score(
            on_time_pct, fill_rate_pct, quality_score_pct),
    }


def get_supplier_scorecards(conn, date_from=None, date_to=None, supplier_id=None):
    """One row per supplier: on-time %, fill-rate %, quality reject rate %,
    composite score, and the raw sample counts behind each. Sorted by
    composite score descending (suppliers with no score at all sort last).
    A supplier with no PO/QA activity in range still appears, with every
    metric None/0.

    date_from/date_to (ISO 'YYYY-MM-DD' strings) optionally bound
    purchase_order.order_date; both independent and optional.
    supplier_id optionally restricts to a single supplier (used by
    get_supplier_scorecard_detail instead of filtering this function's full
    result — avoids scanning every other supplier's POs for one row).
    """
    sql = "SELECT id, first_name, last_name, company_name FROM supplier"
    params = []
    if supplier_id:
        sql += " WHERE id = %s"
        params.append(supplier_id)
    sql += " ORDER BY company_name"
    suppliers = [dict(r) for r in conn.execute(sql, params).fetchall()]

    on_time = _on_time_by_supplier(conn, date_from, date_to, supplier_id)
    fill = _fill_rate_by_supplier(conn, date_from, date_to, supplier_id)
    quality = _quality_by_name_key(conn)

    result = []
    for s in suppliers:
        name_key = _supplier_display_name(s).lower().strip()
        result.append(_score_row(
            s, on_time.get(s['id']), fill.get(s['id']), quality.get(name_key)))

    result.sort(key=lambda r: (
        r['composite_score'] is None, -(r['composite_score'] or 0)))
    return result


def _monthly_trend(conn, supplier_id, date_from, date_to):
    """[{month, po_count, on_time_pct, fill_rate_pct}] for one supplier,
    oldest first, bucketed by purchase_order.order_date's calendar month.

    po_item is pre-aggregated per PO in a subquery before the join so a PO
    with several line items can't fan out and inflate the per-month PO/
    on-time counts (the same join-fan-out trap as an ungrouped LEFT JOIN —
    see routing_core.get_gantt_operations for the analogous fix).
    """
    conds, date_params = _date_conds('po', date_from, date_to)
    where = " AND ".join(["po.supplier_id = %s", "po.order_date IS NOT NULL", *conds])
    params = [list(_PLACED_STATUSES), list(_PLACED_STATUSES), supplier_id, *date_params]

    rows = conn.execute(f"""
        SELECT to_char(po.order_date::date, 'YYYY-MM') AS month,
               COUNT(*) AS po_count,
               COUNT(*) FILTER (WHERE po.status = 'received'
                   AND po.expected_date IS NOT NULL
                   AND po.received_date IS NOT NULL) AS on_time_eligible,
               COUNT(*) FILTER (WHERE po.status = 'received'
                   AND po.expected_date IS NOT NULL
                   AND po.received_date IS NOT NULL
                   AND po.received_date <= po.expected_date) AS on_time_count,
               COALESCE(SUM(item_totals.qty_ordered)
                   FILTER (WHERE po.status = ANY(%s)), 0) AS qty_ordered,
               COALESCE(SUM(item_totals.qty_received)
                   FILTER (WHERE po.status = ANY(%s)), 0) AS qty_received
        FROM purchase_order po
        LEFT JOIN (
            SELECT po_id, SUM(qty_ordered) AS qty_ordered,
                   SUM(qty_received) AS qty_received
            FROM po_item GROUP BY po_id
        ) item_totals ON item_totals.po_id = po.id
        WHERE {where}
        GROUP BY month
        ORDER BY month
    """, params).fetchall()

    trend = []
    for r in rows:
        r = dict(r)
        # Re-aggregating an already-SUM()'d subquery column (item_totals)
        # through an outer SUM()...FILTER comes back from psycopg2 as
        # Decimal even though qty_ordered/qty_received are plain INTEGER
        # columns (a single-level SUM doesn't do this — see
        # _fill_rate_by_supplier). Cast explicitly so json.dumps() (the
        # trend feeds a Chart.js <script> tag) doesn't choke on Decimal.
        on_time_pct = (
            round(r['on_time_count'] / r['on_time_eligible'] * 100, 1)
            if r['on_time_eligible'] else None
        )
        fill_rate_pct = (
            round(float(r['qty_received']) / float(r['qty_ordered']) * 100, 1)
            if r['qty_ordered'] else None
        )
        trend.append({
            'month': r['month'],
            'po_count': r['po_count'],
            'on_time_pct': on_time_pct,
            'fill_rate_pct': fill_rate_pct,
        })
    return trend


def get_supplier_scorecard_detail(conn, supplier_id, date_from=None, date_to=None):
    """Single supplier's scorecard (same shape as one row of
    get_supplier_scorecards) plus 'trend', 'date_from', 'date_to'. Returns
    None if the supplier doesn't exist.

    Defaults to the trailing _DEFAULT_TREND_DAYS days when no date range is
    given (a full-history default would make the trend chart's x-axis grow
    unbounded for a long-lived supplier) — applied before computing the
    headline metrics too, so they cover the same window as the trend chart
    rather than an all-time figure sitting next to a 6-month graph.
    """
    if not date_from and not date_to:
        date_to = date.today().isoformat()
        date_from = (date.today() - timedelta(days=_DEFAULT_TREND_DAYS)).isoformat()

    scorecards = get_supplier_scorecards(
        conn, date_from=date_from, date_to=date_to, supplier_id=supplier_id)
    if not scorecards:
        return None
    own = scorecards[0]

    own['trend'] = _monthly_trend(conn, supplier_id, date_from, date_to)
    own['date_from'] = date_from
    own['date_to'] = date_to
    return own
