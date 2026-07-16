"""Views: Budget Management dashboard."""

import json

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..log_utils import get_logger

log = get_logger(__name__)


def budget_dashboard(request):
    if not request.session.get('user_email'):
        return redirect('home')
    conn = get_db_connection()
    try:
        kpi_row = conn.execute("""
            SELECT
                COUNT(*) AS total_budgets,
                COUNT(*) FILTER (WHERE status = 'active') AS active_budgets,
                COUNT(*) FILTER (WHERE status = 'draft') AS draft_budgets,
                COALESCE(SUM(bl.budgeted_amount), 0) AS total_budgeted
            FROM budget b
            LEFT JOIN budget_line bl ON bl.budget_id = b.id
        """).fetchone()
        kpis = dict(kpi_row) if kpi_row else {}
        kpis['total_budgeted'] = float(kpis.get('total_budgeted', 0))

        status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM budget GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        status_json = json.dumps([dict(r) for r in status_rows])

        budget_rows = conn.execute("""
            SELECT b.budget_name AS name,
                   COALESCE(SUM(bl.budgeted_amount), 0) AS budgeted
            FROM budget b
            LEFT JOIN budget_line bl ON bl.budget_id = b.id
            WHERE b.status = 'active'
            GROUP BY b.id, b.budget_name
            ORDER BY budgeted DESC
        """).fetchall()
        budgets_json = json.dumps([
            {'name': r['name'], 'budgeted': float(r['budgeted'])}
            for r in budget_rows
        ])

        cat_rows = conn.execute("""
            SELECT category,
                   COALESCE(SUM(budgeted_amount), 0) AS amt,
                   COUNT(*) AS cnt
            FROM budget_line
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY amt DESC
            LIMIT 10
        """).fetchall()
        categories_json = json.dumps([
            {'category': r['category'], 'amt': float(r['amt'])}
            for r in cat_rows
        ])

        year_rows = conn.execute("""
            SELECT b.fiscal_year AS yr,
                   COALESCE(SUM(bl.budgeted_amount), 0) AS total
            FROM budget b
            LEFT JOIN budget_line bl ON bl.budget_id = b.id
            GROUP BY b.fiscal_year
            ORDER BY b.fiscal_year
        """).fetchall()
        by_year_json = json.dumps([
            {'yr': r['yr'], 'total': float(r['total'])}
            for r in year_rows
        ])

        recent_rows = conn.execute("""
            SELECT b.id, b.budget_name, b.fiscal_year, b.status,
                   COALESCE(SUM(bl.budgeted_amount), 0) AS total_budgeted
            FROM budget b
            LEFT JOIN budget_line bl ON bl.budget_id = b.id
            GROUP BY b.id, b.budget_name, b.fiscal_year, b.status
            ORDER BY b.fiscal_year DESC, b.id DESC
            LIMIT 10
        """).fetchall()
        recent_budgets = [
            {**dict(r), 'total_budgeted': float(r['total_budgeted'])}
            for r in recent_rows
        ]
    finally:
        conn.close()

    return render(request, 'budget_dashboard.html', {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'kpis': kpis,
        'status_json': status_json,
        'budgets_json': budgets_json,
        'categories_json': categories_json,
        'by_year_json': by_year_json,
        'recent_budgets': recent_budgets,
    })
