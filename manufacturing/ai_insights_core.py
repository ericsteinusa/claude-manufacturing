"""
ai_insights_core.py — Broader Embedded-AI Analytics Platform (Section 3 of
COMPETITIVE_GAP_ANALYSIS.md, "Where We Trail Enterprise" — the one item on
that list buildable without a live external system/hardware).

This app's existing "AI" features (demand_forecast_core.py,
predictive_maintenance_core.py) are hand-rolled classical statistics, not a
data-science library (see demand_forecast_core.py's docstring) — this module
follows the same convention: no pandas/numpy/statsmodels, no new tables,
nothing persisted against real data (same "pure computed layer" choice as
cash_flow_core.py / scenario_planning_core.py).

It ties together two previously siloed risk reports (predictive maintenance,
APM) and three genuinely new hand-rolled signals (demand anomaly, quality
anomaly, customer churn risk) into a single severity-ranked feed. No `link`/
URL is built here — that's a views/ concern, keeping this module Django-free
like every other `*_core.py`.
"""

from __future__ import annotations

import math
from datetime import date

from .apm_core import get_apm_dashboard
from .contacts_core import get_customer_orders, list_customers
from .demand_forecast_core import list_demand_forecast, list_forecast_summary
from .predictive_maintenance_core import get_predictive_maintenance_report
from .quality_core import get_ncr_severity_trend

SEVERITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

MIN_TREND_POINTS = 3
DEMAND_Z_THRESHOLD = 2.0
QUALITY_Z_THRESHOLD = 2.0
MIN_CHURN_ORDERS = 3
CHURN_INTERVAL_MULTIPLIER = 1.5


def _add_months(d: date, n: int) -> date:
    month0 = d.month - 1 + n
    year = d.year + month0 // 12
    month = month0 % 12 + 1
    return date(year, month, 1)


def _fmt_z(z: float) -> str:
    return 'inf' if math.isinf(z) else f'{z:.2f}'


def _trailing_zscore(latest: float, prior: list[float]) -> float | None:
    """Z-score of ``latest`` against the population mean/stdev of ``prior``.

    None if there isn't enough prior history (MIN_TREND_POINTS) to form a
    baseline. If the prior window has zero variance (a flat run of
    identical values), a matching latest value is unremarkable (0.0); a
    deviating one is a real signal off a flat baseline, returned as a
    signed infinity rather than raising ZeroDivisionError.
    """
    if len(prior) < MIN_TREND_POINTS:
        return None
    mean = sum(prior) / len(prior)
    variance = sum((x - mean) ** 2 for x in prior) / len(prior)
    stdev = math.sqrt(variance)
    if stdev == 0:
        if latest == mean:
            return 0.0
        return math.inf if latest > mean else -math.inf
    return (latest - mean) / stdev


def _z_severity(z: float) -> str:
    return 'high' if math.isinf(z) or abs(z) >= 3 else 'medium'


def get_demand_anomalies(conn, months_history: int = 24,
                          z_threshold: float = DEMAND_Z_THRESHOLD) -> list[dict]:
    """Flag products whose latest completed month of actual demand is a
    statistical outlier against their own trailing history.

    Only scans products that already have a generated forecast (via
    list_forecast_summary) — there's no "every product with SO history"
    query in demand_forecast_core.py to reuse instead of re-deriving one;
    a product nobody has ever run "Generate Forecasts" for isn't scanned
    yet, the same honest-scoping choice this app makes elsewhere rather
    than silently duplicating that query.
    """
    out = []
    for summary in list_forecast_summary(conn):
        product_id = summary['product_id']
        series = list_demand_forecast(conn, product_id, months_history)
        actuals = [row['actual_qty'] for row in series if not row['is_forecast']]
        if len(actuals) < MIN_TREND_POINTS + 1:
            continue

        latest, prior = actuals[-1], actuals[:-1]
        z = _trailing_zscore(latest, prior)
        if z is None or (not math.isinf(z) and abs(z) < z_threshold):
            continue

        direction = 'spike' if z > 0 else 'drop'
        prior_mean = sum(prior) / len(prior)
        name = summary.get('product_name') or f'product #{product_id}'
        out.append({
            'domain': 'demand',
            'severity': _z_severity(z),
            'title': f'Demand {direction} — {name}',
            'detail': (f'Latest month qty {latest:g} vs. trailing average '
                       f'{prior_mean:.1f} (z={_fmt_z(z)})'),
            'ref': {'product_id': product_id},
        })
    return out


def get_quality_anomalies(conn, months: int = 13,
                           z_threshold: float = QUALITY_Z_THRESHOLD) -> list[dict]:
    """Flag an anomalous total NCR count in the latest completed month.

    get_ncr_severity_trend only lists months that had >= 1 NCR of any
    severity (months with zero NCRs entirely are simply absent from its
    'months' list) — it is NOT zero-filled across the full window like
    demand_forecast_core's history is. This function reconstructs a
    zero-filled monthly total itself rather than trusting that axis, and
    (matching demand_forecast_core's convention) ends at the last fully
    completed calendar month, not the current in-progress one.
    """
    trend = get_ncr_severity_trend(conn, months=months)
    counts_by_month: dict[str, int] = {}
    for series in trend['series'].values():
        for m, cnt in zip(trend['months'], series):
            counts_by_month[m] = counts_by_month.get(m, 0) + cnt

    end_month = _add_months(date.today().replace(day=1), -1)
    start_month = _add_months(end_month, -(months - 1))
    window = []
    cursor = start_month
    while cursor <= end_month:
        window.append(counts_by_month.get(cursor.strftime('%Y-%m'), 0))
        cursor = _add_months(cursor, 1)

    if len(window) < MIN_TREND_POINTS + 1:
        return []

    latest, prior = float(window[-1]), [float(v) for v in window[:-1]]
    z = _trailing_zscore(latest, prior)
    if z is None or (not math.isinf(z) and abs(z) < z_threshold):
        return []

    direction = 'spike' if z > 0 else 'drop'
    prior_mean = sum(prior) / len(prior)
    return [{
        'domain': 'quality',
        'severity': _z_severity(z),
        'title': f'NCR count {direction} detected',
        'detail': (f'{int(latest)} NCRs last month vs. a trailing average of '
                   f'{prior_mean:.1f} (z={_fmt_z(z)})'),
        'ref': {},
    }]


def get_churn_risk_customers(conn, interval_multiplier: float = CHURN_INTERVAL_MULTIPLIER,
                              min_orders: int = MIN_CHURN_ORDERS) -> list[dict]:
    """Flag customers who are overdue for an order relative to their own
    historical ordering cadence.

    Requires >= min_orders real, non-cancelled, date-parseable orders to
    form a baseline — customers with fewer are skipped entirely (not
    treated as "safe"; there isn't enough data to say either way, the same
    silent-exclusion-over-fabrication choice workforce_analytics_core makes
    for employees with no hire date). order_date is stored as TEXT and
    get_customer_orders orders by so.id, not order_date, so dates are
    parsed defensively and re-sorted here rather than trusted as-is.
    """
    out = []
    today = date.today()
    for customer in list_customers(conn):
        customer_id = customer['id']
        orders = get_customer_orders(conn, customer_id)

        dates = []
        for o in orders:
            if (o.get('status') or '').strip().lower() == 'cancelled':
                continue
            raw = o.get('order_date')
            if not raw:
                continue
            try:
                dates.append(date.fromisoformat(str(raw)[:10]))
            except ValueError:
                continue

        if len(dates) < min_orders:
            continue

        dates.sort()
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        avg_interval = max(1.0, sum(gaps) / len(gaps))
        days_since_last = (today - dates[-1]).days
        ratio = days_since_last / avg_interval
        if ratio < interval_multiplier:
            continue

        severity = 'high' if ratio >= 3 else 'medium'
        label = customer.get('label') or f'customer #{customer_id}'
        out.append({
            'domain': 'churn',
            'severity': severity,
            'title': f'Churn risk — {label}',
            'detail': (f'{days_since_last} days since last order vs. their own '
                       f'{avg_interval:.0f}-day average interval ({ratio:.1f}x)'),
            'ref': {'customer_id': customer_id},
        })
    return out


def get_ai_insights_summary(conn) -> list[dict]:
    """Cross-domain, severity-ranked feed merging every AI-derived signal in
    the app: existing predictive-maintenance risk and APM repair-vs-replace
    reports, plus the three new detectors above. Each row is normalized to
    {domain, severity, title, detail, ref} — no link/URL (views/ concern)."""
    insights: list[dict] = []

    for row in get_predictive_maintenance_report(conn):
        if row['risk_level'] not in ('medium', 'high') and not row['approaching_threshold']:
            continue
        severity = row['risk_level'] if row['risk_level'] in ('medium', 'high') else 'medium'
        insights.append({
            'domain': 'maintenance',
            'severity': severity,
            'title': f"Failure risk — {row['equipment']}",
            'detail': (f"{row['failure_probability_30d'] * 100:.0f}% chance of failure in "
                       f"30 days" if row['failure_probability_30d'] is not None
                       else 'Approaching its failure-interval threshold'),
            'ref': {'equipment_id': row['equipment_id']},
        })

    for row in get_apm_dashboard(conn):
        if row['recommendation'] == 'monitor':
            continue
        severity = 'high' if row['recommendation'] == 'consider_replacement' else 'medium'
        insights.append({
            'domain': 'apm',
            'severity': severity,
            'title': f"Asset health — {row['equipment']}",
            'detail': (f"Health score {row['health_score']}/100, "
                       f"{row['recommendation'].replace('_', ' ')}"),
            'ref': {'equipment': row['equipment']},
        })

    insights.extend(get_demand_anomalies(conn))
    insights.extend(get_quality_anomalies(conn))
    insights.extend(get_churn_risk_customers(conn))

    insights.sort(key=lambda i: SEVERITY_ORDER[i['severity']])
    return insights
