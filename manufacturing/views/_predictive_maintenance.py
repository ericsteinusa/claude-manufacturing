"""Views: Predictive Maintenance — rolling MTBF, threshold/risk alerts,
and manual vibration/temperature sensor readings (P4-B)."""

from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..maintenance_core import list_equipment
from ..predictive_maintenance_core import (
    SENSOR_READING_TYPES, ensure_predictive_maintenance_tables,
    get_predictive_maintenance_report, record_sensor_reading,
    set_sensor_threshold, get_sensor_alerts,
)

log = get_logger(__name__)

_PM_DEPT_KEYS = {'maintenance', 'production'}


def _pm_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_PM_DEPT_KEYS)
def predictive_maintenance_dashboard(request):
    conn = get_db_connection()
    try:
        ensure_predictive_maintenance_tables(conn)
        conn.commit()
        report = get_predictive_maintenance_report(conn)
        sensor_alerts = get_sensor_alerts(conn)
    finally:
        conn.close()

    return render(request, 'predictive_maintenance.html', _pm_ctx(
        request, report=report, sensor_alerts=sensor_alerts,
    ))


@dept_required(_PM_DEPT_KEYS, write_redirect='predictive_maintenance_dashboard')
def sensor_reading_new(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_predictive_maintenance_tables(conn)
        conn.commit()
        equipment = list_equipment(conn, status='Operational')
        if request.method == 'POST':
            try:
                record_sensor_reading(
                    conn,
                    request.POST.get('equipment', '').strip(),
                    request.POST.get('reading_type', ''),
                    request.POST.get('value') or 0,
                    request.POST.get('unit', '').strip(),
                    request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('predictive_maintenance_dashboard')
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    return render(request, 'sensor_reading_new.html', _pm_ctx(
        request, equipment=equipment, reading_types=SENSOR_READING_TYPES, error=error,
    ))


@dept_required(_PM_DEPT_KEYS, write_redirect='predictive_maintenance_dashboard')
def sensor_threshold_set(request):
    error = None
    conn = get_db_connection()
    try:
        ensure_predictive_maintenance_tables(conn)
        conn.commit()
        equipment = list_equipment(conn, status='Operational')
        if request.method == 'POST':
            try:
                set_sensor_threshold(
                    conn,
                    request.POST.get('equipment', '').strip(),
                    request.POST.get('reading_type', ''),
                    request.POST.get('warning_max') or 0,
                    request.POST.get('critical_max') or 0,
                )
                conn.commit()
                return redirect('predictive_maintenance_dashboard')
            except ValueError as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    return render(request, 'sensor_threshold_set.html', _pm_ctx(
        request, equipment=equipment, reading_types=SENSOR_READING_TYPES, error=error,
    ))
