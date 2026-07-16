"""Views: Risk Management dashboard."""

import json

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..log_utils import get_logger

log = get_logger(__name__)


def risk_dashboard(request):
    if not request.session.get('user_email'):
        return redirect('home')
    conn = get_db_connection()
    try:
        kpi_row = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM risk_register) AS total_risks,
                (SELECT COUNT(*) FROM risk_register
                 WHERE status NOT IN ('Closed','Mitigated')) AS open_risks,
                (SELECT COUNT(*) FROM risk_assessment) AS total_assessments,
                (SELECT COUNT(*) FROM risk_audit
                 WHERE status NOT IN ('Completed','Closed')) AS open_audits,
                (SELECT COUNT(*) FROM risk_insurance
                 WHERE status = 'Active') AS active_policies,
                (SELECT COUNT(*) FROM risk_continuity) AS continuity_plans
        """).fetchone()
        kpis = dict(kpi_row) if kpi_row else {}

        severity_rows = conn.execute("""
            SELECT severity, COUNT(*) AS cnt
            FROM risk_register
            WHERE severity IS NOT NULL
            GROUP BY severity ORDER BY cnt DESC
        """).fetchall()
        severity_json = json.dumps([dict(r) for r in severity_rows])

        status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM risk_register
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        reg_status_json = json.dumps([dict(r) for r in status_rows])

        level_rows = conn.execute("""
            SELECT risk_level, COUNT(*) AS cnt
            FROM risk_assessment
            WHERE risk_level IS NOT NULL
            GROUP BY risk_level ORDER BY cnt DESC
        """).fetchall()
        risk_level_json = json.dumps([dict(r) for r in level_rows])

        category_rows = conn.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM risk_register
            WHERE category IS NOT NULL
            GROUP BY category ORDER BY cnt DESC
            LIMIT 8
        """).fetchall()
        category_json = json.dumps([dict(r) for r in category_rows])

        kri_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM risk_kri
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        kri_status_json = json.dumps([dict(r) for r in kri_rows])

        audit_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM risk_audit
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        audit_status_json = json.dumps([dict(r) for r in audit_rows])

        recent_risks = [dict(r) for r in conn.execute("""
            SELECT id, risk, category, severity, status, owner
            FROM risk_register
            ORDER BY id DESC LIMIT 10
        """).fetchall()]

        recent_assessments = [dict(r) for r in conn.execute("""
            SELECT id, title, category, risk_level, status, owner
            FROM risk_assessment
            ORDER BY id DESC LIMIT 8
        """).fetchall()]
    finally:
        conn.close()

    return render(request, 'risk_dashboard.html', {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'kpis': kpis,
        'severity_json': severity_json,
        'reg_status_json': reg_status_json,
        'risk_level_json': risk_level_json,
        'category_json': category_json,
        'kri_status_json': kri_status_json,
        'audit_status_json': audit_status_json,
        'recent_risks': recent_risks,
        'recent_assessments': recent_assessments,
    })
