"""Views: Cash Flow Statement & 13-Week Forecast (P2-D)."""

import json
from datetime import date

from django.shortcuts import render

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..accounts import READ_ONLY_ROLES
from ..fixed_asset_core import init_fixed_asset_tables

from ..cash_flow_core import get_cash_flow_statement, get_cash_forecast_13wk
from ._common import parse_date_param as _parse_date_param

_CASH_FLOW_DEPT_KEYS = {'accounting', 'finance'}


def _cash_flow_ctx(request, **extra):
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_CASH_FLOW_DEPT_KEYS)
def gl_cash_flow_statement(request):
    """Indirect-method cash flow statement, read-only (no write_redirect —
    Auditors can view it too, same as gl_income_statement/gl_balance_sheet)."""
    today = date.today()
    date_from = _parse_date_param(
        request.GET.get('date_from'), f'{today.year}-01-01')
    date_to = _parse_date_param(request.GET.get('date_to'), today.isoformat())
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    with get_db_connection() as conn:
        init_fixed_asset_tables(conn)
        result = get_cash_flow_statement(conn, date_from, date_to)

    return render(request, 'gl_cash_flow_statement.html', _cash_flow_ctx(
        request, **result))


@dept_required(_CASH_FLOW_DEPT_KEYS)
def fin_cash_forecast(request):
    """13-week rolling cash forecast + balance projection chart."""
    start_date = _parse_date_param(request.GET.get('start_date'))

    with get_db_connection() as conn:
        weeks = get_cash_forecast_13wk(conn, start_date=start_date)

    return render(request, 'fin_cash_forecast.html', _cash_flow_ctx(
        request, weeks=weeks, weeks_json=json.dumps(weeks),
        start_date=start_date or date.today().isoformat()))
