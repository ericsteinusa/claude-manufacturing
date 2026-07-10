"""Tests for ai_insights_core — broader embedded-AI analytics platform."""

import math
from datetime import date, timedelta

import pytest

from manufacturing import ai_insights_core
from manufacturing.ai_insights_core import (
    _trailing_zscore, get_demand_anomalies, get_quality_anomalies,
    get_churn_risk_customers, get_ai_insights_summary,
)


# ── _trailing_zscore ────────────────────────────────────────────────────────

def test_zscore_none_below_min_points():
    assert _trailing_zscore(10.0, [1.0, 2.0]) is None


def test_zscore_flat_prior_matching_latest_is_zero():
    assert _trailing_zscore(5.0, [5.0, 5.0, 5.0, 5.0]) == 0.0


def test_zscore_flat_prior_deviating_latest_is_signed_inf():
    assert _trailing_zscore(9.0, [5.0, 5.0, 5.0, 5.0]) == math.inf
    assert _trailing_zscore(1.0, [5.0, 5.0, 5.0, 5.0]) == -math.inf


def test_zscore_normal_variance():
    # prior = [2, 4, 6, 8] -> mean 5, population stdev sqrt(5)
    z = _trailing_zscore(15.0, [2.0, 4.0, 6.0, 8.0])
    assert z == pytest.approx((15.0 - 5.0) / math.sqrt(5.0))


# ── get_demand_anomalies ────────────────────────────────────────────────────

def _forecast_series(actual_qtys):
    return [{'month': f'2026-{i+1:02d}-01', 'actual_qty': qty,
              'forecast_qty': None, 'is_forecast': False}
             for i, qty in enumerate(actual_qtys)]


def test_get_demand_anomalies_flags_spike(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_forecast_summary',
                         lambda conn: [{'product_id': 1, 'product_name': 'Widget'}])
    monkeypatch.setattr(ai_insights_core, 'list_demand_forecast',
                         lambda conn, pid, months_history=24: _forecast_series(
                             [10, 10, 10, 10, 100]))
    out = get_demand_anomalies(conn=object())
    assert len(out) == 1
    assert out[0]['domain'] == 'demand'
    assert out[0]['severity'] == 'high'
    assert out[0]['ref'] == {'product_id': 1}


def test_get_demand_anomalies_skips_insufficient_history(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_forecast_summary',
                         lambda conn: [{'product_id': 1, 'product_name': 'Widget'}])
    monkeypatch.setattr(ai_insights_core, 'list_demand_forecast',
                         lambda conn, pid, months_history=24: _forecast_series([10, 10]))
    assert get_demand_anomalies(conn=object()) == []


def test_get_demand_anomalies_no_flag_when_within_threshold(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_forecast_summary',
                         lambda conn: [{'product_id': 1, 'product_name': 'Widget'}])
    monkeypatch.setattr(ai_insights_core, 'list_demand_forecast',
                         lambda conn, pid, months_history=24: _forecast_series(
                             [10, 11, 9, 10, 11]))
    assert get_demand_anomalies(conn=object()) == []


# ── get_quality_anomalies ───────────────────────────────────────────────────

def _months_back(n):
    """YYYY-MM strings for the n months ending last completed month, oldest first."""
    end = date.today().replace(day=1)
    month0 = end.month - 2  # last completed month, 0-indexed
    year = end.year
    out = []
    for i in range(n - 1, -1, -1):
        m0 = month0 - i
        y = year + (m0 // 12)
        m = m0 % 12 + 1
        out.append(f'{y:04d}-{m:02d}')
    return out


def test_get_quality_anomalies_empty_when_no_data(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'get_ncr_severity_trend',
                         lambda conn, months=13: {'months': [], 'series': {}})
    assert get_quality_anomalies(conn=object()) == []


def test_get_quality_anomalies_flags_real_spike(monkeypatch):
    # Build 13 months ending at the latest completed month; last month spikes.
    all_months = _months_back(13)
    counts = [2] * 12 + [40]
    monkeypatch.setattr(ai_insights_core, 'get_ncr_severity_trend',
                         lambda conn, months=13: {
                             'months': all_months,
                             'series': {'major': counts},
                         })
    out = get_quality_anomalies(conn=object())
    assert len(out) == 1
    assert out[0]['domain'] == 'quality'
    assert out[0]['severity'] == 'high'


# ── get_churn_risk_customers ────────────────────────────────────────────────

def _order(days_ago, status='confirmed'):
    d = date.today() - timedelta(days=days_ago)
    return {'id': 1, 'so_number': 'SO-1', 'status': status,
            'order_date': d.isoformat(), 'total': 100.0}


def test_get_churn_risk_customers_skips_too_few_orders(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_customers',
                         lambda conn: [{'id': 1, 'label': 'Acme'}])
    monkeypatch.setattr(ai_insights_core, 'get_customer_orders',
                         lambda conn, cid: [_order(10), _order(40)])
    assert get_churn_risk_customers(conn=object()) == []


def test_get_churn_risk_customers_skips_cancelled_only(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_customers',
                         lambda conn: [{'id': 1, 'label': 'Acme'}])
    monkeypatch.setattr(ai_insights_core, 'get_customer_orders',
                         lambda conn, cid: [
                             _order(10, 'cancelled'), _order(40, 'cancelled'),
                             _order(70, 'cancelled'),
                         ])
    assert get_churn_risk_customers(conn=object()) == []


def test_get_churn_risk_customers_flags_overdue(monkeypatch):
    # Regular ~30-day cadence, but 200 days since the last order -> overdue.
    monkeypatch.setattr(ai_insights_core, 'list_customers',
                         lambda conn: [{'id': 1, 'label': 'Acme'}])
    monkeypatch.setattr(ai_insights_core, 'get_customer_orders',
                         lambda conn, cid: [
                             _order(200), _order(230), _order(260), _order(290),
                         ])
    out = get_churn_risk_customers(conn=object())
    assert len(out) == 1
    assert out[0]['domain'] == 'churn'
    assert out[0]['ref'] == {'customer_id': 1}


def test_get_churn_risk_customers_not_flagged_when_on_cadence(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_customers',
                         lambda conn: [{'id': 1, 'label': 'Acme'}])
    monkeypatch.setattr(ai_insights_core, 'get_customer_orders',
                         lambda conn, cid: [
                             _order(5), _order(35), _order(65), _order(95),
                         ])
    assert get_churn_risk_customers(conn=object()) == []


def test_get_churn_risk_customers_ignores_unparseable_dates(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'list_customers',
                         lambda conn: [{'id': 1, 'label': 'Acme'}])
    monkeypatch.setattr(ai_insights_core, 'get_customer_orders',
                         lambda conn, cid: [
                             {'id': 1, 'status': 'confirmed', 'order_date': '', 'total': 0},
                             {'id': 2, 'status': 'confirmed', 'order_date': None, 'total': 0},
                             _order(10), _order(40),
                         ])
    # Only 2 parseable, real orders remain -> below MIN_CHURN_ORDERS, skipped.
    assert get_churn_risk_customers(conn=object()) == []


# ── get_ai_insights_summary ──────────────────────────────────────────────────

def test_get_ai_insights_summary_merges_and_ranks(monkeypatch):
    monkeypatch.setattr(ai_insights_core, 'get_predictive_maintenance_report',
                         lambda conn: [{
                             'equipment': 'CNC-01', 'equipment_id': 1,
                             'risk_level': 'low', 'approaching_threshold': False,
                             'failure_probability_30d': 0.05,
                         }])
    monkeypatch.setattr(ai_insights_core, 'get_apm_dashboard',
                         lambda conn: [
                             {'equipment': 'PRESS-02', 'health_score': 20.0,
                              'recommendation': 'consider_replacement'},
                             {'equipment': 'DRILL-03', 'health_score': 90.0,
                              'recommendation': 'monitor'},
                         ])
    monkeypatch.setattr(ai_insights_core, 'get_demand_anomalies', lambda conn: [
        {'domain': 'demand', 'severity': 'medium', 'title': 't', 'detail': 'd', 'ref': {}},
    ])
    monkeypatch.setattr(ai_insights_core, 'get_quality_anomalies', lambda conn: [])
    monkeypatch.setattr(ai_insights_core, 'get_churn_risk_customers', lambda conn: [
        {'domain': 'churn', 'severity': 'high', 'title': 't', 'detail': 'd', 'ref': {}},
    ])

    out = get_ai_insights_summary(conn=object())

    # low-risk maintenance row (not approaching threshold) excluded, 'monitor' APM excluded
    domains = [i['domain'] for i in out]
    assert 'maintenance' not in domains
    assert domains.count('apm') == 1

    # stable-sorted by severity: high first
    severities = [i['severity'] for i in out]
    assert severities == sorted(severities, key=lambda s: ai_insights_core.SEVERITY_ORDER[s])
    assert severities[0] == 'high'
