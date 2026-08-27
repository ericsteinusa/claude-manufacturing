"""Views: maintenance domain."""

import datetime
import json

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required, dept_manager_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..csv_export import export_response
from ..oee_core import get_overall_oee, get_oee_trend, list_workcenter_oee

from ..maintenance_core import (
    WO_STATUSES, WORK_TYPES, PRIORITIES,
    EQUIPMENT_STATUSES,
    SCHEDULE_STATUSES, FREQUENCIES,
    INSPECTION_STATUSES, INSPECTION_TYPES,
    DOWNTIME_STATUSES, DOWNTIME_CATEGORIES,
    PART_STATUSES, PART_CATEGORIES,
    MECHANIC_STATUSES, MECHANIC_TRADES, MECHANIC_SHIFTS,
    get_dashboard_counts as maint_get_dashboard_counts,
    load_mechanics,
    list_work_orders, get_work_order, create_work_order,
    update_work_order, complete_work_order,
    list_equipment, get_equipment, create_equipment, update_equipment,
    set_equipment_parent, get_equipment_children,
    link_part_to_equipment, get_parts_for_equipment,
    list_schedules, get_schedule, create_schedule,
    update_schedule, complete_schedule,
    list_inspections as maint_list_inspections,
    get_inspection as maint_get_inspection,
    create_inspection as maint_create_inspection,
    update_inspection as maint_update_inspection,
    complete_inspection,
    list_downtime, get_downtime, create_downtime, update_downtime,
    resolve_downtime,
    list_parts, get_part, create_part, update_part,
    list_mechanics, get_mechanic, create_mechanic, update_mechanic,
    get_equipment_reliability_report, get_schedule_status_breakdown,
    get_wo_status_breakdown, get_downtime_by_category, get_pm_alerts,
    get_maint_wo_time_variance_report, get_maint_labor_by_mechanic_report,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Maintenance (web)
# ---------------------------------------------------------------------------

_MAINT_DEPT_KEYS = {'maintenance', 'production', 'purchasing'}


def _opt_float(val):
    """Parse a form field into a float, or None when blank (so callers can
    tell "not supplied" apart from 0 and leave existing DB values alone)."""
    val = (val or '').strip()
    return float(val) if val else None


def _resolve_period(request):
    """Resolve the period-chip / custom-range GET params shared by every
    period-filtered maintenance report (OEE, labor time/cost) into
    (period, start, end, date_from, date_to)."""
    period = request.GET.get('period', 'month')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    today = datetime.date.today()

    if date_from and date_to:
        try:
            start = datetime.date.fromisoformat(date_from)
            end = datetime.date.fromisoformat(date_to)
            if end < start:
                start, end = end, start
        except ValueError:
            start, end = today.replace(day=1), today
        period = 'custom'
    elif period == 'day':
        start = end = today
    elif period == 'week':
        start = today - datetime.timedelta(days=today.weekday())
        end = today
    elif period == 'quarter':
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=q_start_month, day=1)
        end = today
    elif period == 'year':
        start = today.replace(month=1, day=1)
        end = today
    else:
        period = 'month'
        start = today.replace(day=1)
        end = today
    return period, start, end, date_from, date_to


def _maint_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_MAINT_DEPT_KEYS)
def maint_dashboard(request):
    today = datetime.date.today()
    month_start = today.replace(day=1)
    conn = get_db_connection()
    try:
        counts = maint_get_dashboard_counts(conn)
        oee = get_overall_oee(conn, month_start.isoformat(), today.isoformat())
        oee_trend = get_oee_trend(conn, end_date=today.isoformat(), weeks=8)
        downtime_by_equipment = get_equipment_reliability_report(conn, months=3)
        schedule_breakdown = get_schedule_status_breakdown(conn)
        wo_status = get_wo_status_breakdown(conn)
        downtime_by_cat = get_downtime_by_category(conn, months=3)
        pm_alerts = get_pm_alerts(conn, days_ahead=14)
    finally:
        conn.close()
    return render(request, 'maint_dashboard.html', _maint_ctx(
        request, counts=counts, oee=oee, oee_trend=oee_trend,
        oee_trend_json=json.dumps(oee_trend),
        downtime_by_equipment_json=json.dumps(downtime_by_equipment),
        schedule_breakdown_json=json.dumps(schedule_breakdown),
        wo_status_json=json.dumps(wo_status),
        downtime_by_cat_json=json.dumps(downtime_by_cat),
        pm_alerts=pm_alerts[:8],
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_dashboard_kpis_fragment(request):
    """htmx polling target for maint_dashboard's KPI row."""
    today = datetime.date.today()
    month_start = today.replace(day=1)
    conn = get_db_connection()
    try:
        counts = maint_get_dashboard_counts(conn)
        oee = get_overall_oee(conn, month_start.isoformat(), today.isoformat())
    finally:
        conn.close()
    return render(request, 'maint_dashboard_kpis.html', {'counts': counts, 'oee': oee})


@dept_required(_MAINT_DEPT_KEYS)
def maint_oee_report(request):
    period, start, end, date_from, date_to = _resolve_period(request)

    conn = get_db_connection()
    try:
        breakdown = list_workcenter_oee(conn, start.isoformat(), end.isoformat())
        overall = get_overall_oee(conn, start.isoformat(), end.isoformat())
        trend = get_oee_trend(conn, end_date=end.isoformat(), weeks=12)
    finally:
        conn.close()

    # per-workcenter bar chart data
    wc_chart = [
        {'name': wc['workcenter_name'],
         'availability': wc['availability_pct'],
         'performance': wc['performance_pct'],
         'quality': wc['quality_pct'],
         'oee': wc['oee_pct']}
        for wc in breakdown if wc
    ]

    return render(request, 'maint_oee_report.html', _maint_ctx(
        request, breakdown=breakdown, overall=overall,
        period=period, start=start.isoformat(), end=end.isoformat(),
        trend_json=json.dumps(trend),
        wc_chart_json=json.dumps(wc_chart),
        date_from=date_from, date_to=date_to,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_oee_export(request):
    period, start, end, date_from, date_to = _resolve_period(request)

    conn = get_db_connection()
    try:
        breakdown = list_workcenter_oee(conn, start.isoformat(), end.isoformat())
    finally:
        conn.close()

    rows = [wc for wc in breakdown if wc]
    return export_response(request, f'oee_{start}_{end}', [
        ('workcenter_name', 'Workcenter'),
        ('availability_pct', 'Availability %'),
        ('performance_pct', 'Performance %'),
        ('quality_pct', 'Quality %'),
        ('oee_pct', 'OEE %'),
        ('scheduled_hours', 'Scheduled Hrs'),
        ('downtime_hours', 'Downtime Hrs'),
        ('actual_hours', 'Actual Hrs'),
        ('total_qty', 'Total Qty'),
        ('total_scrap', 'Scrap Qty'),
    ], rows)


@dept_manager_required(_MAINT_DEPT_KEYS)
def maint_labor_report(request):
    """WO estimated-vs-actual time/cost variance + by-mechanic rollup.
    Restricted to the Maintenance department manager (and President/VP)."""
    period, start, end, date_from, date_to = _resolve_period(request)
    status_filter = request.GET.get('status', '').strip()

    conn = get_db_connection()
    try:
        wo_variance = get_maint_wo_time_variance_report(
            conn, date_from=start.isoformat(), date_to=end.isoformat(),
            status=status_filter or None)
        by_mechanic = get_maint_labor_by_mechanic_report(
            conn, date_from=start.isoformat(), date_to=end.isoformat())
    finally:
        conn.close()

    kpis = {
        'wo_count': len(wo_variance),
        'estimated_hours': sum(w['estimated_hours'] or 0 for w in wo_variance),
        'actual_hours': sum(w['actual_hours'] or 0 for w in wo_variance),
        'labor_cost': sum(w['labor_cost'] or 0 for w in wo_variance),
        'mechanic_count': len(by_mechanic),
        'total_mechanic_cost': sum(m['total_cost'] or 0 for m in by_mechanic),
    }

    return render(request, 'maint_labor_report.html', _maint_ctx(
        request, wo_variance=wo_variance, by_mechanic=by_mechanic, kpis=kpis,
        period=period, start=start.isoformat(), end=end.isoformat(),
        date_from=date_from, date_to=date_to,
        status_filter=status_filter, wo_statuses=WO_STATUSES,
    ))


@dept_manager_required(_MAINT_DEPT_KEYS)
def maint_labor_report_export(request):
    period, start, end, date_from, date_to = _resolve_period(request)
    status_filter = request.GET.get('status', '').strip()
    section = request.GET.get('section', 'wo')

    conn = get_db_connection()
    try:
        if section == 'mechanic':
            rows = get_maint_labor_by_mechanic_report(
                conn, date_from=start.isoformat(), date_to=end.isoformat())
        else:
            rows = get_maint_wo_time_variance_report(
                conn, date_from=start.isoformat(), date_to=end.isoformat(),
                status=status_filter or None)
    finally:
        conn.close()

    if section == 'mechanic':
        return export_response(request, f'maint_labor_by_mechanic_{start}_{end}', [
            ('mechanic_name', 'Mechanic'), ('wo_count', 'WO Count'),
            ('estimated_hours', 'Estimated Hrs'), ('actual_hours', 'Actual Hrs'),
            ('hours_variance', 'Variance Hrs'), ('variance_pct', 'Variance %'),
            ('hourly_rate', 'Hourly Rate'), ('total_cost', 'Total Cost'),
        ], rows)
    return export_response(request, f'maint_wo_time_variance_{start}_{end}', [
        ('wo_id', 'WO #'), ('title', 'Title'), ('equipment', 'Equipment'),
        ('status', 'Status'), ('due_date', 'Due Date'),
        ('estimated_hours', 'Estimated Hrs'), ('actual_hours', 'Actual Hrs'),
        ('hours_variance', 'Variance Hrs'), ('variance_pct', 'Variance %'),
        ('labor_cost', 'Labor Cost'),
    ], rows)


# --- Work Orders ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_wo_list(request):
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    wos = []
    mechanics = []
    try:
        wos = list_work_orders(conn, status=status_filter or None,
                               priority=priority_filter or None,
                               search=search or None)
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_work_order(
                    conn,
                    title=request.POST.get('title', ''),
                    equipment=request.POST.get('equipment', ''),
                    work_type=request.POST.get('work_type', 'Repair'),
                    priority=request.POST.get('priority', 'Medium'),
                    assigned_to=request.POST.get('assigned_to', ''),
                    requested_date=request.POST.get('requested_date', ''),
                    due_date=request.POST.get('due_date', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                    estimated_hours=_opt_float(request.POST.get('estimated_hours')),
                )
                conn.commit()
                return redirect('maint_wo_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                wos = list_work_orders(conn, status=status_filter or None,
                                       priority=priority_filter or None,
                                       search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_wo_list.html', _maint_ctx(
        request, wos=wos, mechanics=mechanics,
        status_filter=status_filter, priority_filter=priority_filter,
        search=search, wo_statuses=WO_STATUSES, work_types=WORK_TYPES,
        priorities=PRIORITIES, error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_wo_export(request):
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        wos = list_work_orders(conn, status=status_filter or None,
                               priority=priority_filter or None,
                               search=search or None)
    finally:
        conn.close()

    return export_response(request, 'maintenance_work_orders', [
        ('title', 'Title'), ('equipment', 'Equipment'),
        ('work_type', 'Work Type'), ('priority', 'Priority'),
        ('assigned_to', 'Assigned To'), ('requested_date', 'Requested Date'),
        ('due_date', 'Due Date'), ('completed_date', 'Completed Date'),
        ('status', 'Status'),
    ], wos)


@dept_required(_MAINT_DEPT_KEYS)
def maint_wo_detail(request, wo_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    wo = None
    mechanics = []
    try:
        wo = get_work_order(conn, wo_id)
        if not wo:
            return redirect('maint_wo_list')
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_work_order(
                        conn, wo_id,
                        actual_hours=_opt_float(request.POST.get('actual_hours')),
                    )
                    success = 'Work order completed.'
                else:
                    update_work_order(
                        conn, wo_id,
                        title=request.POST.get('title', ''),
                        equipment=request.POST.get('equipment', ''),
                        work_type=request.POST.get('work_type', ''),
                        priority=request.POST.get('priority', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        requested_date=request.POST.get('requested_date', ''),
                        due_date=request.POST.get('due_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                        estimated_hours=_opt_float(request.POST.get('estimated_hours')),
                    )
                    success = 'Work order updated.'
                conn.commit()
                wo = get_work_order(conn, wo_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_wo_detail.html', _maint_ctx(
        request, wo=wo, mechanics=mechanics, can_edit=can_edit,
        wo_statuses=WO_STATUSES, work_types=WORK_TYPES, priorities=PRIORITIES,
        error=error, success=success,
    ))


# --- Equipment ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_equipment_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    equipment = []
    try:
        equipment = list_equipment(conn, status=status_filter or None,
                                   search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_equipment(
                    conn,
                    name=request.POST.get('name', ''),
                    asset_tag=request.POST.get('asset_tag', ''),
                    location=request.POST.get('location', ''),
                    manufacturer=request.POST.get('manufacturer', ''),
                    install_date=request.POST.get('install_date', ''),
                    last_service=request.POST.get('last_service', ''),
                    status=request.POST.get('status', 'Operational'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_equipment_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                equipment = list_equipment(conn, status=status_filter or None,
                                           search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'maint_equipment', [
            ('name', 'Equipment Name'), ('asset_tag', 'Asset Tag'), ('location', 'Location'),
            ('manufacturer', 'Manufacturer'), ('install_date', 'Install Date'),
            ('last_service', 'Last Service'), ('status', 'Status'),
        ], equipment)

    return render(request, 'maint_equipment_list.html', _maint_ctx(
        request, equipment=equipment, status_filter=status_filter,
        search=search, equipment_statuses=EQUIPMENT_STATUSES,
        error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_equipment_detail(request, eq_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    eq = None
    try:
        eq = get_equipment(conn, eq_id)
        if not eq:
            return redirect('maint_equipment_list')
        if request.method == 'POST' and can_edit:
            try:
                update_equipment(
                    conn, eq_id,
                    name=request.POST.get('name', ''),
                    asset_tag=request.POST.get('asset_tag', ''),
                    location=request.POST.get('location', ''),
                    manufacturer=request.POST.get('manufacturer', ''),
                    install_date=request.POST.get('install_date', ''),
                    last_service=request.POST.get('last_service', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                parent_raw = request.POST.get('parent_id', '').strip()
                set_equipment_parent(conn, eq_id, int(parent_raw) if parent_raw else None)
                conn.commit()
                eq = get_equipment(conn, eq_id)
                success = 'Equipment updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        all_equipment = [e for e in list_equipment(conn) if e['id'] != eq_id]
        children = get_equipment_children(conn, eq_id)
        parts = get_parts_for_equipment(conn, eq_id)
    finally:
        conn.close()
    return render(request, 'maint_equipment_detail.html', _maint_ctx(
        request, eq=eq, can_edit=can_edit,
        equipment_statuses=EQUIPMENT_STATUSES,
        all_equipment=all_equipment, children=children, parts=parts,
        error=error, success=success,
    ))


# --- PM Schedules ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_schedule_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    schedules = []
    mechanics = []
    try:
        schedules = list_schedules(conn, status=status_filter or None,
                                   search=search or None)
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_schedule(
                    conn,
                    task=request.POST.get('task', ''),
                    equipment=request.POST.get('equipment', ''),
                    frequency=request.POST.get('frequency', 'Monthly'),
                    assigned_to=request.POST.get('assigned_to', ''),
                    last_done=request.POST.get('last_done', ''),
                    next_due=request.POST.get('next_due', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_schedule_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                schedules = list_schedules(conn, status=status_filter or None,
                                           search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'maint_schedules', [
            ('task', 'Task'), ('equipment', 'Equipment'), ('frequency', 'Frequency'),
            ('assigned_to', 'Assigned To'), ('last_done', 'Last Done'),
            ('next_due', 'Next Due'), ('status', 'Status'),
        ], schedules)

    return render(request, 'maint_schedule_list.html', _maint_ctx(
        request, schedules=schedules, mechanics=mechanics,
        status_filter=status_filter, search=search,
        schedule_statuses=SCHEDULE_STATUSES, frequencies=FREQUENCIES,
        error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_schedule_detail(request, sched_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    schedule = None
    mechanics = []
    try:
        schedule = get_schedule(conn, sched_id)
        if not schedule:
            return redirect('maint_schedule_list')
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_schedule(conn, sched_id)
                    success = 'PM task marked complete.'
                else:
                    update_schedule(
                        conn, sched_id,
                        task=request.POST.get('task', ''),
                        equipment=request.POST.get('equipment', ''),
                        frequency=request.POST.get('frequency', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        last_done=request.POST.get('last_done', ''),
                        next_due=request.POST.get('next_due', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Schedule updated.'
                conn.commit()
                schedule = get_schedule(conn, sched_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_schedule_detail.html', _maint_ctx(
        request, schedule=schedule, mechanics=mechanics, can_edit=can_edit,
        schedule_statuses=SCHEDULE_STATUSES, frequencies=FREQUENCIES,
        error=error, success=success,
    ))


# --- Inspections ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_inspection_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    inspections = []
    try:
        inspections = maint_list_inspections(conn, status=status_filter or None,
                                             search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                maint_create_inspection(
                    conn,
                    area=request.POST.get('area', ''),
                    inspection_type=request.POST.get('inspection_type', 'General'),
                    inspector=request.POST.get('inspector', ''),
                    scheduled_date=request.POST.get('scheduled_date', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_inspection_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                inspections = maint_list_inspections(
                    conn, status=status_filter or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'maint_inspections', [
            ('area', 'Area'), ('inspection_type', 'Type'), ('inspector', 'Inspector'),
            ('scheduled_date', 'Scheduled Date'), ('completed_date', 'Completed Date'),
            ('result', 'Result'), ('status', 'Status'),
        ], inspections)

    return render(request, 'maint_inspection_list.html', _maint_ctx(
        request, inspections=inspections, status_filter=status_filter,
        search=search, inspection_statuses=INSPECTION_STATUSES,
        inspection_types=INSPECTION_TYPES,
        error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_inspection_detail(request, insp_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    inspection = None
    try:
        inspection = maint_get_inspection(conn, insp_id)
        if not inspection:
            return redirect('maint_inspection_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_inspection(
                        conn, insp_id,
                        result=request.POST.get('result', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Inspection completed.'
                else:
                    maint_update_inspection(
                        conn, insp_id,
                        area=request.POST.get('area', ''),
                        inspection_type=request.POST.get('inspection_type', ''),
                        inspector=request.POST.get('inspector', ''),
                        scheduled_date=request.POST.get('scheduled_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        result=request.POST.get('result', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Inspection updated.'
                conn.commit()
                inspection = maint_get_inspection(conn, insp_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_inspection_detail.html', _maint_ctx(
        request, inspection=inspection, can_edit=can_edit,
        inspection_statuses=INSPECTION_STATUSES,
        inspection_types=INSPECTION_TYPES,
        error=error, success=success,
    ))


# --- Downtime ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_downtime_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    downtime_records = []
    try:
        downtime_records = list_downtime(conn, status=status_filter or None,
                                         search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_downtime(
                    conn,
                    equipment=request.POST.get('equipment', ''),
                    reason=request.POST.get('reason', ''),
                    category=request.POST.get('category', 'Breakdown'),
                    down_date=request.POST.get('down_date', ''),
                    hours=request.POST.get('hours', ''),
                    cost=request.POST.get('cost', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_downtime_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                downtime_records = list_downtime(conn, status=status_filter or None,
                                                 search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'maint_downtime', [
            ('equipment', 'Equipment'), ('reason', 'Reason'), ('category', 'Category'),
            ('down_date', 'Date'), ('hours', 'Hours'), ('cost', 'Cost'), ('status', 'Status'),
        ], downtime_records)

    return render(request, 'maint_downtime_list.html', _maint_ctx(
        request, downtime_records=downtime_records,
        status_filter=status_filter, search=search,
        downtime_statuses=DOWNTIME_STATUSES,
        downtime_categories=DOWNTIME_CATEGORIES,
        error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_downtime_detail(request, dt_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    record = None
    try:
        record = get_downtime(conn, dt_id)
        if not record:
            return redirect('maint_downtime_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'resolve':
                    resolve_downtime(conn, dt_id)
                    success = 'Downtime marked resolved.'
                else:
                    update_downtime(
                        conn, dt_id,
                        equipment=request.POST.get('equipment', ''),
                        reason=request.POST.get('reason', ''),
                        category=request.POST.get('category', ''),
                        down_date=request.POST.get('down_date', ''),
                        hours=request.POST.get('hours', ''),
                        cost=request.POST.get('cost', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Record updated.'
                conn.commit()
                record = get_downtime(conn, dt_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_downtime_detail.html', _maint_ctx(
        request, record=record, can_edit=can_edit,
        downtime_statuses=DOWNTIME_STATUSES,
        downtime_categories=DOWNTIME_CATEGORIES,
        error=error, success=success,
    ))


# --- Parts ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_parts_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    parts = []
    try:
        parts = list_parts(conn, status=status_filter or None,
                           search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_part(
                    conn,
                    name=request.POST.get('name', ''),
                    part_number=request.POST.get('part_number', ''),
                    category=request.POST.get('category', 'Other'),
                    location=request.POST.get('location', ''),
                    quantity=request.POST.get('quantity', ''),
                    reorder_level=request.POST.get('reorder_level', ''),
                    unit_cost=request.POST.get('unit_cost', ''),
                    status=request.POST.get('status', 'In Stock'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_parts_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                parts = list_parts(conn, status=status_filter or None,
                                   search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'maint_parts', [
            ('part_number', 'Part #'), ('name', 'Description'), ('category', 'Category'),
            ('quantity', 'Quantity'), ('unit_cost', 'Unit Cost'),
            ('location', 'Location'), ('reorder_level', 'Reorder Point'), ('status', 'Status'),
        ], parts)

    return render(request, 'maint_parts_list.html', _maint_ctx(
        request, parts=parts, status_filter=status_filter, search=search,
        part_statuses=PART_STATUSES, part_categories=PART_CATEGORIES,
        error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_part_detail(request, part_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    part = None
    try:
        part = get_part(conn, part_id)
        if not part:
            return redirect('maint_parts_list')
        if request.method == 'POST' and can_edit:
            try:
                update_part(
                    conn, part_id,
                    name=request.POST.get('name', ''),
                    part_number=request.POST.get('part_number', ''),
                    category=request.POST.get('category', ''),
                    location=request.POST.get('location', ''),
                    quantity=request.POST.get('quantity', ''),
                    reorder_level=request.POST.get('reorder_level', ''),
                    unit_cost=request.POST.get('unit_cost', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                eq_raw = request.POST.get('equipment_id', '').strip()
                link_part_to_equipment(conn, part_id, int(eq_raw) if eq_raw else None)
                conn.commit()
                part = get_part(conn, part_id)
                success = 'Part updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        all_equipment = list_equipment(conn)
    finally:
        conn.close()
    return render(request, 'maint_part_detail.html', _maint_ctx(
        request, part=part, can_edit=can_edit,
        part_statuses=PART_STATUSES, part_categories=PART_CATEGORIES,
        all_equipment=all_equipment,
        error=error, success=success,
    ))


# --- Mechanics ---

@dept_required(_MAINT_DEPT_KEYS)
def maint_mechanics_list(request):
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    mechanics = []
    try:
        mechanics = list_mechanics(conn, status=status_filter or None,
                                   search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_mechanic(
                    conn,
                    name=request.POST.get('name', ''),
                    trade=request.POST.get('trade', 'General'),
                    shift=request.POST.get('shift', 'Day'),
                    phone=request.POST.get('phone', ''),
                    status=request.POST.get('status', 'Active'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                    hourly_rate=_opt_float(request.POST.get('hourly_rate')) or 0.0,
                )
                conn.commit()
                return redirect('maint_mechanics_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                mechanics = list_mechanics(conn, status=status_filter or None,
                                           search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'maint_mechanics', [
            ('name', 'Name'), ('trade', 'Trade'), ('shift', 'Shift'),
            ('phone', 'Phone'), ('status', 'Status'),
        ], mechanics)

    return render(request, 'maint_mechanics_list.html', _maint_ctx(
        request, mechanics=mechanics, status_filter=status_filter,
        search=search, mechanic_statuses=MECHANIC_STATUSES,
        mechanic_trades=MECHANIC_TRADES, mechanic_shifts=MECHANIC_SHIFTS,
        error=error, success=success,
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_mechanic_detail(request, mech_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    mechanic = None
    try:
        mechanic = get_mechanic(conn, mech_id)
        if not mechanic:
            return redirect('maint_mechanics_list')
        if request.method == 'POST' and can_edit:
            try:
                update_mechanic(
                    conn, mech_id,
                    name=request.POST.get('name', ''),
                    trade=request.POST.get('trade', ''),
                    shift=request.POST.get('shift', ''),
                    phone=request.POST.get('phone', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                    hourly_rate=_opt_float(request.POST.get('hourly_rate')),
                )
                conn.commit()
                mechanic = get_mechanic(conn, mech_id)
                success = 'Mechanic updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_mechanic_detail.html', _maint_ctx(
        request, mechanic=mechanic, can_edit=can_edit,
        mechanic_statuses=MECHANIC_STATUSES,
        mechanic_trades=MECHANIC_TRADES, mechanic_shifts=MECHANIC_SHIFTS,
        error=error, success=success,
    ))


