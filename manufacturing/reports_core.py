"""reports_core.py — Qt-free data queries for the Reports dashboard."""

from __future__ import annotations
import csv
import datetime
import io
import textwrap

from .finance_core import get_cash_position


def hours_variance(std_hours, actual_hours) -> tuple[float, float | None]:
    """Return (variance, variance_pct) for a standard-vs-actual hours pair.

    variance = actual - std (positive = over standard). variance_pct is
    None when std_hours is 0/None, since percent-of-zero is undefined.
    """
    std_hours = std_hours or 0.0
    actual_hours = actual_hours or 0.0
    variance = actual_hours - std_hours
    variance_pct = (variance / std_hours * 100) if std_hours else None
    return variance, variance_pct


def po_summary(conn) -> dict:
    """Return PO counts by status, total active spend, and overdue count."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM purchase_order GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}

    spend_row = conn.execute(
        "SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) AS total "
        "FROM po_item pi "
        "JOIN purchase_order po ON po.id = pi.po_id "
        "WHERE po.status NOT IN ('cancelled')"
    ).fetchone()
    total_spend = float(spend_row["total"] or 0) if spend_row else 0.0

    today = datetime.date.today().isoformat()
    overdue_row = conn.execute(
        "SELECT COUNT(*) AS n FROM purchase_order "
        "WHERE expected_date < %s AND status NOT IN ('received', 'cancelled')",
        (today,),
    ).fetchone()
    overdue = overdue_row["n"] if overdue_row else 0

    return {
        "by_status": by_status, "total_spend": total_spend, "overdue": overdue
    }


def wo_summary(conn) -> dict:
    """Return WO counts by status."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM work_order GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["n"] for r in rows}
    return {"by_status": by_status}


def inventory_alerts(conn) -> dict:
    """Return products at or below their reorder point (up to 20 rows)."""
    items = conn.execute(
        "SELECT id, name, COALESCE(amount, 0) AS on_hand, "
        "COALESCE(reorder_point, 0) AS reorder_point "
        "FROM product "
        "WHERE COALESCE(reorder_point, 0) > 0 "
        "  AND COALESCE(amount, 0) <= COALESCE(reorder_point, 0) "
        "ORDER BY (COALESCE(amount, 0) - COALESCE(reorder_point, 0)) ASC "
        "LIMIT 20"
    ).fetchall()

    count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM product "
        "WHERE COALESCE(reorder_point, 0) > 0 "
        "  AND COALESCE(amount, 0) <= COALESCE(reorder_point, 0)"
    ).fetchone()

    return {
        "alert_count": count_row["n"] if count_row else 0,
        "items": [dict(r) for r in items],
    }


def cs_summary(conn) -> dict:
    """Return CS call counts: total, open, closed, today."""
    total_row = conn.execute("SELECT COUNT(*) AS n FROM calls2").fetchone()
    open_row = conn.execute(
        "SELECT COUNT(*) AS n FROM calls2 WHERE completion_box = 0"
    ).fetchone()
    today = datetime.date.today().isoformat()
    today_row = conn.execute(
        "SELECT COUNT(*) AS n FROM calls2 WHERE call_date = %s", (today,)
    ).fetchone()

    total = total_row["n"] if total_row else 0
    open_count = open_row["n"] if open_row else 0
    today_count = today_row["n"] if today_row else 0
    return {
        "total": total,
        "open": open_count,
        "closed": total - open_count,
        "today": today_count,
    }


# ---------------------------------------------------------------------------
# 5A — Financial, Production, Inventory dashboards
# ---------------------------------------------------------------------------

def financial_dashboard(conn, as_of: str | None = None) -> dict:
    """Return a concise financial health snapshot.

    Keys returned:
      cash_position        Total balance across active bank accounts
      dso                  Days Sales Outstanding (90-day window)
      dpo                  Days Payable Outstanding (90-day window)
      ar_aging             Aging bucket totals from get_ar_aging
      ap_due_week          AP invoice balance due in the next 7 days
      gross_margin_pct     (Revenue - COGS) / Revenue × 100, YTD
    """
    today = as_of or datetime.date.today().isoformat()
    year_start = today[:4] + '-01-01'
    week_end = (datetime.date.fromisoformat(today)
                + datetime.timedelta(days=7)).isoformat()

    # Cash across all active bank accounts (latest statement's ending
    # balance) — shared with cash_flow_core via finance_core.get_cash_position
    # rather than a second copy of the same LATERAL-join query.
    cash_position = get_cash_position(conn)

    # DSO / DPO. AR/AP invoices don't carry a received/paid column directly —
    # amounts collected/disbursed live in ar_payment/ap_payment, one row per
    # payment, so balances need a join against a per-invoice payment total.
    ar_bal_row = conn.execute("""
        SELECT COALESCE(SUM(i.amount - COALESCE(pay.received, 0)), 0) AS b
        FROM ar_invoice i
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS received
            FROM ar_payment GROUP BY invoice_id
        ) pay ON pay.invoice_id = i.id
        WHERE i.status NOT IN ('paid', 'cancelled')
          AND i.amount > COALESCE(pay.received, 0)
    """).fetchone()
    rev_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS r FROM ar_invoice "
        "WHERE invoice_date >= %s AND status != 'cancelled'", (year_start,)
    ).fetchone()
    ar_bal = float(ar_bal_row['b'] if ar_bal_row else 0)
    revenue = float(rev_row['r'] if rev_row else 0)
    dso = round(ar_bal / revenue * 365, 1) if revenue else 0.0

    ap_bal_row = conn.execute("""
        SELECT COALESCE(SUM(i.amount - COALESCE(pay.paid, 0)), 0) AS b
        FROM ap_invoice i
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS paid
            FROM ap_payment GROUP BY invoice_id
        ) pay ON pay.invoice_id = i.id
        WHERE i.status NOT IN ('paid', 'cancelled')
          AND i.amount > COALESCE(pay.paid, 0)
    """).fetchone()
    purch_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS p FROM ap_invoice "
        "WHERE invoice_date >= %s AND status != 'cancelled'", (year_start,)
    ).fetchone()
    ap_bal = float(ap_bal_row['b'] if ap_bal_row else 0)
    purchases = float(purch_row['p'] if purch_row else 0)
    dpo = round(ap_bal / purchases * 365, 1) if purchases else 0.0

    # AR aging bucket totals
    ar_aging_rows = conn.execute("""
        SELECT i.amount - COALESCE(pay.received, 0) AS balance, i.due_date
        FROM ar_invoice i
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS received
            FROM ar_payment GROUP BY invoice_id
        ) pay ON pay.invoice_id = i.id
        WHERE i.status NOT IN ('paid', 'cancelled')
          AND i.amount > COALESCE(pay.received, 0)
    """).fetchall()
    aging_totals = {b: 0.0 for b in
                    ('current', '1_30', '31_60', '61_90', 'over_90')}
    today_d = datetime.date.fromisoformat(today)
    for r in ar_aging_rows:
        if not r['due_date']:
            aging_totals['current'] += float(r['balance'])
            continue
        try:
            days = (today_d - datetime.date.fromisoformat(str(r['due_date'])[:10])).days
        except ValueError:
            days = 0
        if days <= 0:
            bucket = 'current'
        elif days <= 30:
            bucket = '1_30'
        elif days <= 60:
            bucket = '31_60'
        elif days <= 90:
            bucket = '61_90'
        else:
            bucket = 'over_90'
        aging_totals[bucket] += float(r['balance'])

    # AP due this week
    ap_week_row = conn.execute("""
        SELECT COALESCE(SUM(i.amount - COALESCE(pay.paid, 0)), 0) AS due
        FROM ap_invoice i
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS paid
            FROM ap_payment GROUP BY invoice_id
        ) pay ON pay.invoice_id = i.id
        WHERE i.status NOT IN ('paid', 'cancelled')
          AND i.due_date BETWEEN %s AND %s
    """, (today, week_end)).fetchone()
    ap_due_week = float(ap_week_row['due'] if ap_week_row else 0)

    # Gross margin YTD from GL
    gm_rows = conn.execute("""
        SELECT ga.account_type,
               COALESCE(SUM(jl.credit - jl.debit), 0) AS net
        FROM gl_journal_line jl
        JOIN gl_journal j ON j.id = jl.journal_id
        JOIN gl_account ga ON ga.id = jl.account_id
        WHERE j.posted = 1
          AND j.journal_date >= %s
          AND ga.account_type IN ('Revenue', 'COGS')
        GROUP BY ga.account_type
    """, (year_start,)).fetchall()
    rev_gl = cogs_gl = 0.0
    for r in gm_rows:
        if r['account_type'] == 'Revenue':
            rev_gl = float(r['net'])
        elif r['account_type'] == 'COGS':
            cogs_gl = -float(r['net'])   # COGS net is debit-heavy (negative credit-debit)
    gross_margin_pct = (
        round((rev_gl - cogs_gl) / rev_gl * 100, 1)
        if rev_gl else 0.0
    )

    return {
        'cash_position':    cash_position,
        'dso':              dso,
        'dpo':              dpo,
        'ar_aging':         aging_totals,
        'ap_due_week':      ap_due_week,
        'gross_margin_pct': gross_margin_pct,
    }


def production_dashboard(conn, as_of: str | None = None) -> dict:
    """Return production KPIs.

    Keys returned:
      wos_by_status         {status: count}
      overdue_count         Open WOs past their due date
      total_scrap_qty       Sum of scrap_qty across all wo_operation rows
      total_rework_qty      Sum of rework_qty across all wo_operation rows
      avg_efficiency_pct    100 × std_hours / actual_hours (completed ops)
      open_count            Convenience alias for wos_by_status['open']
    """
    today = as_of or datetime.date.today().isoformat()

    status_rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM work_order GROUP BY status"
    ).fetchall()
    wos_by_status = {r['status']: r['n'] for r in status_rows}

    overdue_row = conn.execute(
        "SELECT COUNT(*) AS n FROM work_order "
        "WHERE due_date < %s AND status NOT IN ('completed', 'cancelled')",
        (today,),
    ).fetchone()
    overdue_count = int(overdue_row['n'] if overdue_row else 0)

    scrap_row = conn.execute(
        "SELECT COALESCE(SUM(scrap_qty), 0) AS sq, "
        "       COALESCE(SUM(rework_qty), 0) AS rq, "
        "       COALESCE(SUM(std_hours), 0) AS sh, "
        "       COALESCE(SUM(actual_hours), 0) AS ah "
        "FROM wo_operation WHERE status = 'completed'"
    ).fetchone()

    total_scrap_qty = float(scrap_row['sq'] if scrap_row else 0)
    total_rework_qty = float(scrap_row['rq'] if scrap_row else 0)
    std_h = float(scrap_row['sh'] if scrap_row else 0)
    act_h = float(scrap_row['ah'] if scrap_row else 0)
    avg_efficiency_pct = round(std_h / act_h * 100, 1) if act_h else 0.0

    return {
        'wos_by_status':     wos_by_status,
        'overdue_count':     overdue_count,
        'total_scrap_qty':   total_scrap_qty,
        'total_rework_qty':  total_rework_qty,
        'avg_efficiency_pct': avg_efficiency_pct,
        'open_count':        wos_by_status.get('open', 0),
    }


def inventory_dashboard(conn) -> dict:
    """Return inventory KPIs.

    Keys returned:
      total_sku_count       Total distinct product records
      total_inventory_value Sum(on_hand_qty × purchase_price)
      alert_count           Products at or below reorder point
      zero_stock_count      Products with zero or negative on hand
      slow_mover_count      Products with on_hand > 0 but no tx in 90 days
      slow_movers           Up to 10 slow-mover product dicts
    """
    count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM product"
    ).fetchone()
    total_sku_count = int(count_row['n'] if count_row else 0)

    value_row = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(amount, 0) * "
        "                    COALESCE(purchase_price, 0)), 0) AS v "
        "FROM product"
    ).fetchone()
    total_inventory_value = float(value_row['v'] if value_row else 0)

    alert_row = conn.execute("""
        SELECT
          COUNT(*) FILTER (
            WHERE COALESCE(reorder_point, 0) > 0
              AND COALESCE(amount, 0) <= COALESCE(reorder_point, 0)
          ) AS alert_count,
          COUNT(*) FILTER (WHERE COALESCE(amount, 0) <= 0) AS zero_count
        FROM product
    """).fetchone()
    alert_count = int(alert_row['alert_count'] if alert_row else 0)
    zero_stock_count = int(alert_row['zero_count'] if alert_row else 0)

    cutoff = (datetime.date.today()
              - datetime.timedelta(days=90)).isoformat()
    slow_rows = conn.execute("""
        SELECT p.id, p.name, COALESCE(p.amount, 0) AS amount,
               COALESCE(p.purchase_price, 0) AS purchase_price
        FROM product p
        WHERE COALESCE(p.amount, 0) > 0
          AND NOT EXISTS (
              SELECT 1 FROM inventory_transaction it
              WHERE it.product_id = p.id
                AND it.trans_date >= %s
          )
        ORDER BY p.amount DESC
        LIMIT 10
    """, (cutoff,)).fetchall()

    slow_mover_count_row = conn.execute("""
        SELECT COUNT(*) AS n FROM product p
        WHERE COALESCE(p.amount, 0) > 0
          AND NOT EXISTS (
              SELECT 1 FROM inventory_transaction it
              WHERE it.product_id = p.id AND it.trans_date >= %s
          )
    """, (cutoff,)).fetchone()

    return {
        'total_sku_count':       total_sku_count,
        'total_inventory_value': total_inventory_value,
        'alert_count':           alert_count,
        'zero_stock_count':      zero_stock_count,
        'slow_mover_count':      int(slow_mover_count_row['n'] if slow_mover_count_row else 0),
        'slow_movers':           [dict(r) for r in slow_rows],
    }


# ---------------------------------------------------------------------------
# 5B — Export helpers (CSV + Excel)
# ---------------------------------------------------------------------------

def to_csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    """Return a UTF-8 CSV as bytes, suitable for a Django FileResponse."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue().encode('utf-8')


def financial_dashboard_csv(conn, as_of: str | None = None) -> bytes:
    """Export financial dashboard to CSV bytes."""
    d = financial_dashboard(conn, as_of)
    today = as_of or datetime.date.today().isoformat()
    rows = [
        ['Metric', 'Value'],
        ['As of', today],
        ['Cash Position', f"${d['cash_position']:,.2f}"],
        ['Days Sales Outstanding (DSO)', d['dso']],
        ['Days Payable Outstanding (DPO)', d['dpo']],
        ['Gross Margin %', d['gross_margin_pct']],
        ['AP Due This Week', f"${d['ap_due_week']:,.2f}"],
        [],
        ['AR Aging Bucket', 'Balance'],
    ]
    for bucket, amt in d['ar_aging'].items():
        rows.append([bucket, f"${amt:,.2f}"])
    return to_csv_bytes(rows[0], rows[1:])


def inventory_dashboard_csv(conn) -> bytes:
    """Export inventory dashboard to CSV bytes."""
    d = inventory_dashboard(conn)
    summary = [
        ['Total SKUs', d['total_sku_count']],
        ['Total Inventory Value', f"${d['total_inventory_value']:,.2f}"],
        ['Alert Count (at/below reorder)', d['alert_count']],
        ['Zero Stock Count', d['zero_stock_count']],
        ['Slow Mover Count (90 days)', d['slow_mover_count']],
    ]
    hdr = ['Metric', 'Value']
    return to_csv_bytes(hdr, summary)


def export_to_excel(sheets: dict[str, tuple[list, list]]) -> bytes:
    """Build an Excel workbook and return bytes.

    *sheets* is a dict of ``{sheet_name: (headers, rows)}``.
    Returns b'' if openpyxl is not installed.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        return b''

    wb = openpyxl.Workbook()
    if wb.worksheets:
        wb.remove(wb.worksheets[0])   # remove the default blank sheet
    for name, (headers, rows) in sheets.items():
        ws = wb.create_sheet(title=name[:31])
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def daily_digest_text(conn) -> str:
    """Return a plain-text daily digest report string."""
    today = datetime.date.today().isoformat()
    fin = financial_dashboard(conn, as_of=today)
    prod = production_dashboard(conn, as_of=today)
    inv = inventory_dashboard(conn)
    po = po_summary(conn)
    return textwrap.dedent(f"""\
        === Daily ERP Digest — {today} ===

        FINANCIAL
          Cash position:     ${fin['cash_position']:>12,.2f}
          DSO (days):        {fin['dso']:>12.1f}
          DPO (days):        {fin['dpo']:>12.1f}
          Gross margin:      {fin['gross_margin_pct']:>11.1f}%
          AP due this week:  ${fin['ap_due_week']:>12,.2f}

        PRODUCTION
          Open WOs:          {prod['open_count']:>12}
          Overdue WOs:       {prod['overdue_count']:>12}
          Avg efficiency:    {prod['avg_efficiency_pct']:>11.1f}%
          Scrap qty (YTD):   {prod['total_scrap_qty']:>12.1f}

        INVENTORY
          Total SKUs:        {inv['total_sku_count']:>12}
          Total value:       ${inv['total_inventory_value']:>12,.2f}
          Low-stock alerts:  {inv['alert_count']:>12}
          Zero-stock items:  {inv['zero_stock_count']:>12}
          Slow movers (90d): {inv['slow_mover_count']:>12}

        PURCHASING
          Open POs:          {po['by_status'].get('open', 0):>12}
          Overdue POs:       {po['overdue']:>12}
          Active spend:      ${po['total_spend']:>12,.2f}
    """)
