"""
demand_forecast_core.py — Qt-free AI Demand Forecasting (P4-A).

Not the same feature as ``sales_core.py``'s ``sales_forecast`` table —
that's a rep/product-line/quarter **quota** a person types in
(``expected_value``, ``probability`` -> ``weighted_value``), compared
against actual revenue. This module is a genuinely computed, product x
month, unit-quantity forecast, generated from historical Sales Order lines
via a hand-rolled classical seasonal decomposition — no data-science
library (pandas/numpy/statsmodels/prophet) exists anywhere in this
codebase's ``requirements.txt``, and none is added for this feature.

The model: fit a linear trend (closed-form least squares) across the
trailing history, then compute a per-calendar-month seasonal index (the
average ratio of actual-to-trend for that month across however many years
of history exist, normalized so the 12 indices average to 1.0). A future
month's forecast is trend-at-that-point x seasonal-index-for-that-month.
With fewer than 12 months of history there's no full seasonal cycle to
measure, so the seasonal indices are all 1.0 (a flat, trend-only
projection) rather than fabricating a seasonal pattern from partial data.

``get_forecast_demand_dated`` returns exactly the ``{product_id: [(qty,
date), ...]}`` shape ``mrp_web_core.get_demand_dated`` already returns, so
feeding a forecast into MRP is an additive merge, not a rewrite (see
``mrp_web_core.run_mrp_dated``'s ``include_forecast`` parameter).

Every function taking ``conn`` takes an open connection; the caller owns
the transaction (same convention as blanket_po_core / shop_floor_core).
"""

from __future__ import annotations

from datetime import datetime, date

from .log_utils import get_logger

log = get_logger(__name__)

_HISTORY_STATUSES = ('closed', 'shipped', 'delivered', 'complete', 'completed')


def _add_months(d: date, n: int) -> date:
    month0 = d.month - 1 + n
    year = d.year + month0 // 12
    month = month0 % 12 + 1
    return date(year, month, 1)


def _month_floor(d: date) -> date:
    return date(d.year, d.month, 1)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_demand_forecast_tables(conn) -> None:
    """Create demand_forecast if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS demand_forecast (
            id             SERIAL PRIMARY KEY,
            product_id     INTEGER NOT NULL,
            forecast_month DATE NOT NULL,
            forecast_qty   REAL NOT NULL DEFAULT 0,
            method         TEXT DEFAULT 'seasonal_decomposition',
            generated_at   TEXT DEFAULT '',
            UNIQUE (product_id, forecast_month)
        )
    """)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def get_monthly_history(conn, product_id: int, months: int = 24) -> list:
    """Trailing ``months`` of realized (shipped/closed) demand for one
    product, zero-filled for months with no orders. Returns an ordered
    list of ``(month_date, qty)`` ending with last month (not the current,
    still-in-progress month)."""
    end_month = _add_months(_month_floor(date.today()), -1)
    start_month = _add_months(end_month, -(months - 1))

    placeholders = ', '.join(['%s'] * len(_HISTORY_STATUSES))
    rows = conn.execute(f"""
        SELECT DATE_TRUNC('month', so.order_date::date)::date AS mo,
               COALESCE(SUM(si.qty), 0) AS qty
        FROM sales_order so
        JOIN so_item si ON si.so_id = so.id
        WHERE si.product_id = %s
          AND so.order_date IS NOT NULL AND so.order_date != ''
          AND so.order_date::date >= %s
          AND LOWER(so.status) IN ({placeholders})
        GROUP BY 1
    """, [product_id, start_month.isoformat(), *_HISTORY_STATUSES]).fetchall()

    by_month = {r['mo']: float(r['qty']) for r in rows}
    out = []
    cursor = start_month
    while cursor <= end_month:
        out.append((cursor, by_month.get(cursor, 0.0)))
        cursor = _add_months(cursor, 1)
    return out


# ---------------------------------------------------------------------------
# Time-series model (pure functions, no DB)
# ---------------------------------------------------------------------------

def _linear_trend(values: list) -> tuple:
    """Closed-form least-squares slope/intercept of ``values`` over index
    0..n-1. Returns (slope, intercept)."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, values[0]
    xs = range(n)
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _seasonal_indices(values: list, slope: float, intercept: float) -> list:
    """Classical multiplicative seasonal index per calendar-month position
    (index 0..11), normalized to mean 1.0. Falls back to flat 1.0 for every
    position when there's under 12 months of history (no full cycle to
    measure)."""
    n = len(values)
    if n < 12:
        return [1.0] * 12

    ratios_by_position: dict = {}
    for i, actual in enumerate(values):
        trend_at_i = slope * i + intercept
        if trend_at_i > 0:
            ratios_by_position.setdefault(i % 12, []).append(actual / trend_at_i)

    indices = [
        (sum(ratios_by_position[pos]) / len(ratios_by_position[pos]))
        if ratios_by_position.get(pos) else 1.0
        for pos in range(12)
    ]
    mean_index = sum(indices) / 12
    if mean_index > 0:
        indices = [idx / mean_index for idx in indices]
    return indices


def _compute_forecast(history: list, months_ahead: int = 12,
                       start_position: int = 0) -> list:
    """The time-series model: trend projection x seasonal index for each
    of the next ``months_ahead`` points past the end of ``history``.
    ``start_position`` is the calendar-month index (0=Jan) of the first
    history point, needed to align seasonal indices to real months.
    Clamped to >= 0. Pure function — no DB, directly unit-testable."""
    n = len(history)
    slope, intercept = _linear_trend(history)
    indices = _seasonal_indices(history, slope, intercept)

    forecast = []
    for step in range(1, months_ahead + 1):
        trend_value = slope * (n - 1 + step) + intercept
        position = (start_position + n - 1 + step) % 12
        forecast.append(max(0.0, trend_value * indices[position]))
    return forecast


# ---------------------------------------------------------------------------
# Generate / read forecasts
# ---------------------------------------------------------------------------

def generate_forecast_for_product(conn, product_id: int, months_history: int = 24,
                                   months_ahead: int = 12) -> list:
    """Compute and upsert a forecast for one product. Returns the list of
    ``{forecast_month, forecast_qty}`` rows written."""
    history = get_monthly_history(conn, product_id, months_history)
    qtys = [qty for _month, qty in history]
    start_position = history[0][0].month - 1 if history else 0
    forecast_qtys = _compute_forecast(qtys, months_ahead, start_position)

    last_month = history[-1][0] if history else _month_floor(date.today())
    now = datetime.now().isoformat()
    out = []
    for step, qty in enumerate(forecast_qtys, start=1):
        forecast_month = _add_months(last_month, step)
        conn.execute(
            "INSERT INTO demand_forecast "
            "(product_id, forecast_month, forecast_qty, method, generated_at) "
            "VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT (product_id, forecast_month) DO UPDATE "
            "SET forecast_qty=EXCLUDED.forecast_qty, generated_at=EXCLUDED.generated_at",
            (product_id, forecast_month.isoformat(), qty,
             'seasonal_decomposition', now),
        )
        out.append({'forecast_month': forecast_month.isoformat(), 'forecast_qty': qty})
    return out


def generate_all_forecasts(conn, months_history: int = 24, months_ahead: int = 12) -> int:
    """Generate forecasts for every product with any SO history in the
    trailing window. Returns the number of products forecasted."""
    rows = conn.execute("""
        SELECT DISTINCT si.product_id
        FROM so_item si
        JOIN sales_order so ON so.id = si.so_id
        WHERE si.product_id IS NOT NULL
          AND so.order_date::date >= %s
    """, [_add_months(_month_floor(date.today()), -(months_history - 1)).isoformat()]).fetchall()

    for r in rows:
        generate_forecast_for_product(conn, r['product_id'], months_history, months_ahead)
    return len(rows)


def list_forecast_summary(conn) -> list:
    """One row per forecasted product: total forecast qty over the stored
    horizon, for the dashboard's product picker."""
    rows = conn.execute("""
        SELECT df.product_id, p.name AS product_name,
               SUM(df.forecast_qty) AS total_forecast_qty,
               MAX(df.generated_at) AS generated_at
        FROM demand_forecast df
        LEFT JOIN product p ON p.id = df.product_id
        GROUP BY df.product_id, p.name
        ORDER BY total_forecast_qty DESC
    """).fetchall()
    return [dict(r) for r in rows]


def list_demand_forecast(conn, product_id: int, months_history: int = 24) -> list:
    """Merged chronological series of actual history + stored forecast for
    one product, for the actual-vs-forecast overlay display."""
    history = get_monthly_history(conn, product_id, months_history)
    out = [{'month': m.isoformat(), 'actual_qty': qty, 'forecast_qty': None,
            'is_forecast': False} for m, qty in history]

    forecast_rows = conn.execute(
        "SELECT forecast_month, forecast_qty FROM demand_forecast "
        "WHERE product_id = %s ORDER BY forecast_month",
        (product_id,),
    ).fetchall()
    for r in forecast_rows:
        out.append({'month': str(r['forecast_month']), 'actual_qty': None,
                    'forecast_qty': float(r['forecast_qty']), 'is_forecast': True})
    return out


def get_forecast_demand_dated(conn) -> dict:
    """Stored forecast rows as ``{product_id: [(qty, date), ...]}`` —
    exactly mrp_web_core.get_demand_dated's shape, so MRP can merge it in
    additively (see mrp_web_core.run_mrp_dated's include_forecast flag)."""
    rows = conn.execute(
        "SELECT product_id, forecast_month, forecast_qty FROM demand_forecast"
    ).fetchall()
    result: dict = {}
    for r in rows:
        month = r['forecast_month']
        if isinstance(month, str):
            month = date.fromisoformat(month)
        result.setdefault(r['product_id'], []).append((float(r['forecast_qty']), month))
    return result
