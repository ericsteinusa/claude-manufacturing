"""Views: AI Demand Forecasting — product x month forecast dashboard with
an actual-vs-forecast overlay (P4-A)."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import FULL_ACCESS_ROLES, READ_ONLY_ROLES

from ..demand_forecast_core import (
    ensure_demand_forecast_tables, generate_all_forecasts,
    list_forecast_summary, list_demand_forecast,
)

log = get_logger(__name__)

_DEMAND_FORECAST_DEPT_KEYS = {'sales', 'production'}


def _df_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_DEMAND_FORECAST_DEPT_KEYS)
def demand_forecast_dashboard(request):
    product_id = request.GET.get('product_id')
    product_id = int(product_id) if product_id else None

    conn = get_db_connection()
    try:
        ensure_demand_forecast_tables(conn)
        conn.commit()
        summary = list_forecast_summary(conn)
        if not product_id and summary:
            product_id = summary[0]['product_id']
        series = list_demand_forecast(conn, product_id) if product_id else []
    finally:
        conn.close()

    max_qty = max(
        [row['actual_qty'] or 0 for row in series] +
        [row['forecast_qty'] or 0 for row in series] + [0]
    )

    return render(request, 'demand_forecast.html', _df_ctx(
        request, summary=summary, series=series, product_id=product_id,
        max_qty=max_qty,
    ))


@dept_required(_DEMAND_FORECAST_DEPT_KEYS, write_redirect='demand_forecast_dashboard')
def demand_forecast_generate(request):
    if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
        conn = get_db_connection()
        try:
            ensure_demand_forecast_tables(conn)
            conn.commit()
            generate_all_forecasts(conn)
            conn.commit()
        finally:
            conn.close()
    return redirect('demand_forecast_dashboard')
