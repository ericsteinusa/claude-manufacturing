"""Views: Supplier Performance Scorecard (P2-C)."""

import json
from datetime import date

from django.shortcuts import render

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..purchase_orders_core import ensure_po_tables

from ..supplier_scorecard_core import (
    get_supplier_scorecards, get_supplier_scorecard_detail,
)

log = get_logger(__name__)

_SCORECARD_DEPT_KEYS = {'purchasing', 'quality_assurance'}


def _scorecard_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def _parse_date_param(raw, default=None):
    raw = (raw or '').strip()
    if not raw:
        return default
    try:
        date.fromisoformat(raw)
    except ValueError:
        return default
    return raw


@dept_required(_SCORECARD_DEPT_KEYS)
def supplier_scorecard_list(request):
    """Supplier ranking report — one row per supplier, sorted by composite
    score. Read-only, so no write_redirect (Auditors can view it too)."""
    date_from = _parse_date_param(request.GET.get('date_from'))
    date_to = _parse_date_param(request.GET.get('date_to'))

    conn = get_db_connection()
    try:
        ensure_po_tables(conn)
        scorecards = get_supplier_scorecards(
            conn, date_from=date_from, date_to=date_to)
    finally:
        conn.close()

    return render(request, 'supplier_scorecard_list.html', _scorecard_ctx(
        request, scorecards=scorecards, date_from=date_from or '',
        date_to=date_to or ''))


@dept_required(_SCORECARD_DEPT_KEYS)
def supplier_scorecard_detail(request, supplier_id):
    """One supplier's scorecard breakdown plus a monthly on-time %/fill-rate
    % trend chart (defaults to the trailing 6 months — see
    supplier_scorecard_core._DEFAULT_TREND_DAYS)."""
    date_from = _parse_date_param(request.GET.get('date_from'))
    date_to = _parse_date_param(request.GET.get('date_to'))

    conn = get_db_connection()
    try:
        ensure_po_tables(conn)
        scorecard = get_supplier_scorecard_detail(
            conn, supplier_id, date_from=date_from, date_to=date_to)
    finally:
        conn.close()

    if not scorecard:
        return render(request, 'supplier_scorecard_detail.html', _scorecard_ctx(
            request, scorecard=None, trend_json='[]'))

    return render(request, 'supplier_scorecard_detail.html', _scorecard_ctx(
        request, scorecard=scorecard,
        trend_json=json.dumps(scorecard['trend'])))
