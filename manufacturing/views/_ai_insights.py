"""Views: AI Insights Hub — cross-domain feed merging predictive-maintenance
risk, APM repair-vs-replace recommendations, and demand/quality/churn
anomaly detection into one severity-ranked list (broader embedded-AI
analytics platform, Section 3 of COMPETITIVE_GAP_ANALYSIS.md)."""

from django.shortcuts import render

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required

from ..apm_core import ensure_apm_tables
from ..demand_forecast_core import ensure_demand_forecast_tables
from ..predictive_maintenance_core import ensure_predictive_maintenance_tables
from ..ai_insights_core import get_ai_insights_summary

_LINKS = {
    'maintenance': lambda ref: '/predictive-maintenance/',
    'apm': lambda ref: '/maint/apm/',
    'demand': lambda ref: f"/demand-forecast/?product_id={ref['product_id']}",
    'quality': lambda ref: '/qa/',
    'churn': lambda ref: f"/customers/{ref['customer_id']}/",
}


@dept_required('reports')
def ai_insights_dashboard(request):
    conn = get_db_connection()
    try:
        ensure_apm_tables(conn)
        ensure_demand_forecast_tables(conn)
        ensure_predictive_maintenance_tables(conn)
        insights = get_ai_insights_summary(conn)
    finally:
        conn.close()

    for row in insights:
        row['link'] = _LINKS[row['domain']](row['ref'])

    return render(request, 'ai_insights_dashboard.html', {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'insights': insights,
    })
