"""cash_flow_core.py — Qt-free Cash Flow Statement & 13-Week Forecast (P2-D
from COMPETITIVE_GAP_ANALYSIS.md).

Pure computed view over existing tables — no tables of its own, same
convention as atp_core.py / supplier_scorecard_core.py:
  - gl_journal / gl_journal_line (accounting_core.income_statement): net
    income, the indirect method's starting point.
  - ar_invoice / ar_payment, ap_invoice / ap_payment: period-over-period
    balance changes (operating adjustments) for the statement, and
    currently-outstanding balances bucketed by due_date for the forecast.
  - fixed_asset (fixed_asset_core): depreciation addback (reuses
    calc_annual_depreciation rather than reimplementing the formulas) and
    capex (investing activities).
  - bank_account / bank_statement (finance_core.get_cash_position): actual
    cash balance, both as the forecast's starting point and as a
    side-by-side check against the statement's computed net change.

Two things this system has no data for, called out explicitly rather than
faked:
  - Inventory value change (operating): there is no point-in-time inventory
    valuation anywhere in this schema to compute a historical balance from
    (product.amount is a current quantity, not a dated ledger).
  - Financing activities: grepping the whole codebase turns up no loan/debt
    table of any kind, so this section is always zero.

Every function takes an open connection; the caller owns the transaction
(same convention as accounting_core / finance_core).
"""

from __future__ import annotations

from datetime import date, timedelta

from .accounting_core import income_statement
from .fixed_asset_core import calc_annual_depreciation
from .finance_core import get_cash_position

FORECAST_WEEKS = 13

INVENTORY_NOTE = (
    "Change in inventory is not included: this system has no point-in-time "
    "inventory valuation to compute a historical balance from."
)
FINANCING_NOTE = (
    "No loans or other financing transactions are tracked in this system yet."
)


def _ar_balance_as_of(conn, as_of):
    """Total AR outstanding as of a specific date: invoices dated on or
    before as_of, minus payments made on or before as_of.

    Deliberately not accounting_core.get_ar_aging, which filters by an
    invoice's *current* status — a since-paid invoice would be wrongly
    excluded from a balance computed as of a date before it was paid. The
    payment subquery pre-aggregates per invoice_id before the join so an
    invoice with several partial payments can't fan out and double-count
    i.amount (the same join-fan-out trap noted in routing_core /
    supplier_scorecard_core).
    """
    row = conn.execute("""
        SELECT COALESCE(SUM(i.amount), 0) AS invoiced,
               COALESCE(SUM(paid.total), 0) AS paid
        FROM ar_invoice i
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS total
            FROM ar_payment WHERE payment_date <= %s
            GROUP BY invoice_id
        ) paid ON paid.invoice_id = i.id
        WHERE i.invoice_date <= %s AND i.status != 'cancelled'
    """, (as_of, as_of)).fetchone()
    return float(row['invoiced'] or 0) - float(row['paid'] or 0) if row else 0.0


def _ap_balance_as_of(conn, as_of):
    """AP mirror of _ar_balance_as_of — see its docstring."""
    row = conn.execute("""
        SELECT COALESCE(SUM(i.amount), 0) AS invoiced,
               COALESCE(SUM(paid.total), 0) AS paid
        FROM ap_invoice i
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS total
            FROM ap_payment WHERE payment_date <= %s
            GROUP BY invoice_id
        ) paid ON paid.invoice_id = i.id
        WHERE i.invoice_date <= %s AND i.status != 'cancelled'
    """, (as_of, as_of)).fetchone()
    return float(row['invoiced'] or 0) - float(row['paid'] or 0) if row else 0.0


def _depreciation_for_period(conn, date_from, date_to):
    """Depreciation addback for the period: each active asset's annual
    depreciation (via fixed_asset_core.calc_annual_depreciation — not
    reimplemented here) prorated by the fraction of a year the period
    covers. A simplification: uniform proration across the whole period
    regardless of exactly when within it an asset was purchased (same
    class of simplification as routing_core's Gantt window-capacity
    calculation, which also doesn't account for sub-period granularity).
    """
    rows = conn.execute("""
        SELECT purchase_price, salvage_value, useful_life_years,
               depreciation_method
        FROM fixed_asset
        WHERE status != 'Disposed' AND purchase_date IS NOT NULL
          AND purchase_date != '' AND purchase_date <= %s
    """, (date_to,)).fetchall()
    days = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days + 1
    year_fraction = max(days, 0) / 365.0
    total = sum(calc_annual_depreciation(dict(r)) for r in rows) * year_fraction
    return round(total, 2)


def _capex_for_period(conn, date_from, date_to):
    """Fixed-asset purchases within the period — the investing-activities
    outflow. No disposal/sale-proceeds data exists on fixed_asset_event to
    net against, so investing activities covers purchases only."""
    row = conn.execute("""
        SELECT COALESCE(SUM(purchase_price), 0) AS capex
        FROM fixed_asset
        WHERE purchase_date BETWEEN %s AND %s
    """, (date_from, date_to)).fetchone()
    return float(row['capex']) if row else 0.0


def get_cash_flow_statement(conn, date_from, date_to):
    """Indirect-method cash flow statement for [date_from, date_to].

    Returns {date_from, date_to, operating: {net_income, depreciation,
    ar_change, ap_change, total}, investing: {capex, total},
    financing: {total, note}, net_change_in_cash, cash_start, cash_end,
    inventory_note}.

    ar_change/ap_change are already sign-adjusted for display: an increase
    in AR is a cash-flow *reduction* (shown negative); an increase in AP is
    a cash-flow *addition* (shown positive) — both add up correctly into
    operating.total.

    cash_start/cash_end are the actual bank balance (finance_core.
    get_cash_position) at the edges of the window — shown alongside the
    computed net_change_in_cash as a sanity check, not forced to reconcile
    with it (see INVENTORY_NOTE/FINANCING_NOTE for why they may not tie
    exactly).
    """
    income = income_statement(conn, date_from, date_to)
    net_income = income['net_income']

    depreciation = _depreciation_for_period(conn, date_from, date_to)

    ar_change = _ar_balance_as_of(conn, date_to) - _ar_balance_as_of(conn, date_from)
    ap_change = _ap_balance_as_of(conn, date_to) - _ap_balance_as_of(conn, date_from)

    operating_total = net_income + depreciation - ar_change + ap_change

    capex = _capex_for_period(conn, date_from, date_to)
    investing_total = -capex

    financing_total = 0.0

    net_change_in_cash = operating_total + investing_total + financing_total

    return {
        'date_from': date_from,
        'date_to': date_to,
        'operating': {
            'net_income': round(net_income, 2),
            'depreciation': depreciation,
            'ar_change': round(-ar_change, 2),
            'ap_change': round(ap_change, 2),
            'total': round(operating_total, 2),
        },
        'investing': {
            'capex': round(-capex, 2),
            'total': round(investing_total, 2),
        },
        'financing': {
            'total': round(financing_total, 2),
            'note': FINANCING_NOTE,
        },
        'net_change_in_cash': round(net_change_in_cash, 2),
        'cash_start': round(get_cash_position(conn, as_of=date_from), 2),
        'cash_end': round(get_cash_position(conn, as_of=date_to), 2),
        'inventory_note': INVENTORY_NOTE,
    }


def _week_index(due_date, start, total_weeks):
    """Which forecast week (0-based) a due_date falls into, or None if it's
    beyond the horizon. A due_date before `start` (already overdue) is
    folded into week 0 — expected "now", not dropped."""
    if not due_date:
        return None
    try:
        d = date.fromisoformat(str(due_date)[:10])
    except ValueError:
        return None
    if d < start:
        return 0
    idx = (d - start).days // 7
    return idx if idx < total_weeks else None


def _outstanding_by_week(conn, table, start, total_weeks):
    payment_table = f"{table[:-len('_invoice')]}_payment"
    rows = conn.execute(f"""
        SELECT i.due_date, i.amount - COALESCE(SUM(p.amount), 0) AS balance
        FROM {table} i
        LEFT JOIN {payment_table} p ON p.invoice_id = i.id
        WHERE i.status IN ('open', 'partial', 'overdue')
        GROUP BY i.id
    """).fetchall()

    by_week = [0.0] * total_weeks
    for r in rows:
        balance = float(r['balance'] or 0)
        if balance <= 0.005:
            continue
        idx = _week_index(r['due_date'], start, total_weeks)
        if idx is not None:
            by_week[idx] += balance
    return by_week


def get_cash_forecast_13wk(conn, start_date=None):
    """13 weekly buckets of expected AR collections / AP disbursements,
    from currently-outstanding invoices' due_date, walked forward into a
    running projected cash balance that starts from the current actual
    cash position (finance_core.get_cash_position).

    Each entry: {week_start, week_end, ar_collections, ap_disbursements,
    net_cash_flow, projected_balance}, oldest first.

    Uses the *current* status-based outstanding balance (open/partial/
    overdue), not the historical as-of snapshot get_cash_flow_statement
    uses — this is a forward-looking projection of what's on the books
    right now, not a historical reconstruction.
    """
    start = date.fromisoformat(start_date) if start_date else date.today()

    ar_by_week = _outstanding_by_week(conn, 'ar_invoice', start, FORECAST_WEEKS)
    ap_by_week = _outstanding_by_week(conn, 'ap_invoice', start, FORECAST_WEEKS)

    balance = get_cash_position(conn)
    weeks = []
    for w in range(FORECAST_WEEKS):
        week_start = start + timedelta(days=7 * w)
        week_end = week_start + timedelta(days=6)
        net = ar_by_week[w] - ap_by_week[w]
        balance += net
        weeks.append({
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'ar_collections': round(ar_by_week[w], 2),
            'ap_disbursements': round(ap_by_week[w], 2),
            'net_cash_flow': round(net, 2),
            'projected_balance': round(balance, 2),
        })
    return weeks
