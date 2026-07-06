"""Views: maintenance domain."""

import datetime
import json

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..csv_export import csv_response
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
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Maintenance (web)
# ---------------------------------------------------------------------------

_MAINT_DEPT_KEYS = {'maintenance', 'production', 'purchasing'}


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
    finally:
        conn.close()
    return render(request, 'maint_dashboard.html', _maint_ctx(
        request, counts=counts, oee=oee, oee_trend=oee_trend,
        downtime_by_equipment_json=json.dumps(downtime_by_equipment),
        schedule_breakdown_json=json.dumps(schedule_breakdown),
    ))


@dept_required(_MAINT_DEPT_KEYS)
def maint_oee_report(request):
    period = request.GET.get('period', 'month')
    if period not in ('week', 'month'):
        period = 'month'

    today = datetime.date.today()
    if period == 'week':
        start = today - datetime.timedelta(days=today.weekday())
    else:
        start = today.replace(day=1)

    conn = get_db_connection()
    try:
        breakdown = list_workcenter_oee(conn, start.isoformat(), today.isoformat())
        overall = get_overall_oee(conn, start.isoformat(), today.isoformat())
    finally:
        conn.close()

    return render(request, 'maint_oee_report.html', _maint_ctx(
        request, breakdown=breakdown, overall=overall,
        period=period, start=start.isoformat(), end=today.isoformat(),
    ))


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

    return csv_response('maintenance_work_orders.csv', [
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
                    complete_work_order(conn, wo_id)
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
                conn.commit()
                eq = get_equipment(conn, eq_id)
                success = 'Equipment updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_equipment_detail.html', _maint_ctx(
        request, eq=eq, can_edit=can_edit,
        equipment_statuses=EQUIPMENT_STATUSES,
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
                conn.commit()
                part = get_part(conn, part_id)
                success = 'Part updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_part_detail.html', _maint_ctx(
        request, part=part, can_edit=can_edit,
        part_statuses=PART_STATUSES, part_categories=PART_CATEGORIES,
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


