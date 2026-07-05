"""Views: it domain."""

from datetime import date

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..it_core import (
    get_it_dashboard,
    list_tickets as list_it_tickets,
    get_ticket as get_it_ticket,
    create_ticket as create_it_ticket,
    update_ticket as update_it_ticket,
    set_ticket_status as set_it_ticket_status,
    next_ticket_number,
    list_assets, get_asset, create_asset, update_asset,
    TICKET_STATUSES, TICKET_PRIORITIES, ISSUE_TYPES, ASSET_STATUSES, ASSET_TYPES,
    list_repairs, get_repair, create_repair, update_repair, set_repair_status,
    REPAIR_STATUSES, REPAIR_PRIORITIES,
    list_software, get_software, create_software, update_software,
    SOFTWARE_STATUSES,
    list_licenses, get_license, create_license, update_license,
    LICENSE_TYPES, LICENSE_STATUSES,
    list_network_devices, get_network_device, create_network_device, update_network_device,
    NETWORK_DEVICE_TYPES, NETWORK_DEVICE_STATUSES,
    list_tasks, get_task, create_task, update_task, set_task_status, next_task_number,
    TASK_STATUSES, TASK_PRIORITIES, TASK_TYPES,
    list_incidents, get_incident, create_incident, update_incident, set_incident_status,
    INCIDENT_SEVERITIES, INCIDENT_STATUSES,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# IT dashboard
# ---------------------------------------------------------------------------

def _it_ctx(request, **extra):
    return {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        **extra,
    }


@dept_required('information_tech')
def it_dashboard(request):
    with get_db_connection() as conn:
        data = get_it_dashboard(conn)
    ctx = _it_ctx(request, **data)
    return render(request, 'it_dashboard.html', ctx)


@dept_required('information_tech')
def it_ticket_list(request):
    status_f = request.GET.get('status', '').strip()
    priority_f = request.GET.get('priority', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        tickets = list_it_tickets(conn, status=status_f or None,
                                  priority=priority_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                num = next_ticket_number(conn)
                create_it_ticket(
                    conn,
                    ticket_number=num,
                    requester=request.POST.get('requester', ''),
                    department=request.POST.get('department', ''),
                    issue_type=request.POST.get('issue_type', ''),
                    description=request.POST.get('description', ''),
                    priority=request.POST.get('priority', 'medium'),
                    assigned_to=request.POST.get('assigned_to', ''),
                    submitted_date=request.POST.get('submitted_date', '') or date.today().isoformat(),
                    due_date=request.POST.get('due_date', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_ticket_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                tickets = list_it_tickets(conn, status=status_f or None,
                                          priority=priority_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_ticket_list.html', _it_ctx(
        request, tickets=tickets, status_filter=status_f, priority_filter=priority_f,
        search=search, ticket_statuses=TICKET_STATUSES, ticket_priorities=TICKET_PRIORITIES,
        issue_types=ISSUE_TYPES, today=date.today().isoformat(),
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_ticket_detail(request, ticket_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    ticket = None
    try:
        ticket = get_it_ticket(conn, ticket_id)
        if not ticket:
            return redirect('it_ticket_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'status':
                    set_it_ticket_status(conn, ticket_id, request.POST.get('status', ''))
                    success = 'Status updated.'
                else:
                    update_it_ticket(
                        conn, ticket_id,
                        requester=request.POST.get('requester', ''),
                        department=request.POST.get('department', ''),
                        issue_type=request.POST.get('issue_type', ''),
                        description=request.POST.get('description', ''),
                        priority=request.POST.get('priority', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        submitted_date=request.POST.get('submitted_date', ''),
                        due_date=request.POST.get('due_date', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Ticket updated.'
                conn.commit()
                ticket = get_it_ticket(conn, ticket_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_ticket_detail.html', _it_ctx(
        request, ticket=ticket, can_edit=can_edit,
        ticket_statuses=TICKET_STATUSES, ticket_priorities=TICKET_PRIORITIES,
        issue_types=ISSUE_TYPES, error=error, success=success,
    ))


@dept_required('information_tech')
def it_asset_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('asset_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        assets = list_assets(conn, status=status_f or None,
                             asset_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_asset(
                    conn,
                    asset_tag=request.POST.get('asset_tag', ''),
                    asset_type=request.POST.get('asset_type', ''),
                    make=request.POST.get('make', ''),
                    model=request.POST.get('model', ''),
                    serial_number=request.POST.get('serial_number', ''),
                    assigned_to=request.POST.get('assigned_to', ''),
                    department=request.POST.get('department', ''),
                    purchase_date=request.POST.get('purchase_date', ''),
                    warranty_exp=request.POST.get('warranty_exp', ''),
                    status=request.POST.get('status', 'active'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('it_asset_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                assets = list_assets(conn, status=status_f or None,
                                     asset_type=type_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_asset_list.html', _it_ctx(
        request, assets=assets, status_filter=status_f, type_filter=type_f,
        search=search, asset_statuses=ASSET_STATUSES, asset_types=ASSET_TYPES,
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_asset_detail(request, asset_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    asset = None
    try:
        asset = get_asset(conn, asset_id)
        if not asset:
            return redirect('it_asset_list')
        if request.method == 'POST' and can_edit:
            try:
                update_asset(
                    conn, asset_id,
                    asset_tag=request.POST.get('asset_tag', ''),
                    asset_type=request.POST.get('asset_type', ''),
                    make=request.POST.get('make', ''),
                    model=request.POST.get('model', ''),
                    serial_number=request.POST.get('serial_number', ''),
                    assigned_to=request.POST.get('assigned_to', ''),
                    department=request.POST.get('department', ''),
                    purchase_date=request.POST.get('purchase_date', ''),
                    warranty_exp=request.POST.get('warranty_exp', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Asset updated.'
                asset = get_asset(conn, asset_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_asset_detail.html', _it_ctx(
        request, asset=asset, can_edit=can_edit,
        asset_statuses=ASSET_STATUSES, asset_types=ASSET_TYPES,
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_repairs_list(request):
    status_f = request.GET.get('status', '').strip()
    priority_f = request.GET.get('priority', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        repairs = list_repairs(conn, status=status_f or None,
                               priority=priority_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_repair(
                    conn,
                    asset_tag=request.POST.get('asset_tag', ''),
                    problem_description=request.POST.get('problem_description', ''),
                    reported_by=request.POST.get('reported_by', ''),
                    reported_date=request.POST.get('reported_date', '') or date.today().isoformat(),
                    assigned_to=request.POST.get('assigned_to', ''),
                    priority=request.POST.get('priority', 'medium'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_repairs_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                repairs = list_repairs(conn, status=status_f or None,
                                       priority=priority_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_repairs_list.html', _it_ctx(
        request, repairs=repairs, status_filter=status_f, priority_filter=priority_f,
        search=search, repair_statuses=REPAIR_STATUSES, repair_priorities=REPAIR_PRIORITIES,
        today=date.today().isoformat(), error=error, success=success,
    ))


@dept_required('information_tech')
def it_repairs_detail(request, repair_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    repair = None
    try:
        repair = get_repair(conn, repair_id)
        if not repair:
            return redirect('it_repairs_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'status':
                    set_repair_status(conn, repair_id, request.POST.get('status', ''))
                    success = 'Status updated.'
                else:
                    update_repair(
                        conn, repair_id,
                        asset_tag=request.POST.get('asset_tag', ''),
                        problem_description=request.POST.get('problem_description', ''),
                        reported_by=request.POST.get('reported_by', ''),
                        reported_date=request.POST.get('reported_date', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        priority=request.POST.get('priority', ''),
                        resolution=request.POST.get('resolution', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Repair updated.'
                conn.commit()
                repair = get_repair(conn, repair_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_repairs_detail.html', _it_ctx(
        request, repair=repair, can_edit=can_edit,
        repair_statuses=REPAIR_STATUSES, repair_priorities=REPAIR_PRIORITIES,
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_software_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        installs = list_software(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_software(
                    conn,
                    asset_tag=request.POST.get('asset_tag', ''),
                    software_name=request.POST.get('software_name', ''),
                    version=request.POST.get('version', ''),
                    vendor=request.POST.get('vendor', ''),
                    install_date=request.POST.get('install_date', '') or date.today().isoformat(),
                    status=request.POST.get('status', 'installed'),
                    installed_by=request.POST.get('installed_by', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_software_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                installs = list_software(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_software_list.html', _it_ctx(
        request, installs=installs, status_filter=status_f, search=search,
        software_statuses=SOFTWARE_STATUSES, today=date.today().isoformat(),
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_software_detail(request, sw_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    install = None
    try:
        install = get_software(conn, sw_id)
        if not install:
            return redirect('it_software_list')
        if request.method == 'POST' and can_edit:
            try:
                update_software(
                    conn, sw_id,
                    asset_tag=request.POST.get('asset_tag', ''),
                    software_name=request.POST.get('software_name', ''),
                    version=request.POST.get('version', ''),
                    vendor=request.POST.get('vendor', ''),
                    install_date=request.POST.get('install_date', ''),
                    status=request.POST.get('status', ''),
                    installed_by=request.POST.get('installed_by', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Record updated.'
                install = get_software(conn, sw_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_software_detail.html', _it_ctx(
        request, install=install, can_edit=can_edit,
        software_statuses=SOFTWARE_STATUSES, error=error, success=success,
    ))


@dept_required('information_tech')
def it_license_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        licenses = list_licenses(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_license(
                    conn,
                    software_name=request.POST.get('software_name', ''),
                    vendor=request.POST.get('vendor', ''),
                    license_key=request.POST.get('license_key', ''),
                    license_type=request.POST.get('license_type', 'perpetual'),
                    seats=int(request.POST.get('seats', '1') or 1),
                    seats_used=int(request.POST.get('seats_used', '0') or 0),
                    purchase_date=request.POST.get('purchase_date', '') or None,
                    expiry_date=request.POST.get('expiry_date', '') or None,
                    cost=float(request.POST.get('cost', '0') or 0),
                    status=request.POST.get('status', 'active'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_license_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                licenses = list_licenses(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_license_list.html', _it_ctx(
        request, licenses=licenses, status_filter=status_f, search=search,
        license_types=LICENSE_TYPES, license_statuses=LICENSE_STATUSES,
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_license_detail(request, license_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    lic = None
    try:
        lic = get_license(conn, license_id)
        if not lic:
            return redirect('it_license_list')
        if request.method == 'POST' and can_edit:
            try:
                update_license(
                    conn, license_id,
                    software_name=request.POST.get('software_name', ''),
                    vendor=request.POST.get('vendor', ''),
                    license_key=request.POST.get('license_key', ''),
                    license_type=request.POST.get('license_type', ''),
                    seats=int(request.POST.get('seats', '1') or 1),
                    seats_used=int(request.POST.get('seats_used', '0') or 0),
                    purchase_date=request.POST.get('purchase_date', '') or None,
                    expiry_date=request.POST.get('expiry_date', '') or None,
                    cost=float(request.POST.get('cost', '0') or 0),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'License updated.'
                lic = get_license(conn, license_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_license_detail.html', _it_ctx(
        request, lic=lic, can_edit=can_edit,
        license_types=LICENSE_TYPES, license_statuses=LICENSE_STATUSES,
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_network_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('device_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        devices = list_network_devices(conn, status=status_f or None,
                                       device_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_network_device(
                    conn,
                    hostname=request.POST.get('hostname', ''),
                    ip_address=request.POST.get('ip_address', ''),
                    mac_address=request.POST.get('mac_address', ''),
                    device_type=request.POST.get('device_type', ''),
                    manufacturer=request.POST.get('manufacturer', ''),
                    model=request.POST.get('model', ''),
                    location=request.POST.get('location', ''),
                    status=request.POST.get('status', 'unknown'),
                    last_seen=request.POST.get('last_seen', '') or None,
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_network_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                devices = list_network_devices(conn, status=status_f or None,
                                               device_type=type_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_network_list.html', _it_ctx(
        request, devices=devices, status_filter=status_f, type_filter=type_f,
        search=search, device_types=NETWORK_DEVICE_TYPES,
        device_statuses=NETWORK_DEVICE_STATUSES, today=date.today().isoformat(),
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_task_list(request):
    status_f = request.GET.get('status', '').strip()
    priority_f = request.GET.get('priority', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        tasks = list_tasks(conn, status=status_f or None,
                           priority=priority_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                num = next_task_number(conn)
                create_task(
                    conn,
                    task_number=num,
                    task_name=request.POST.get('task_name', ''),
                    task_type=request.POST.get('task_type', ''),
                    description=request.POST.get('description', ''),
                    assigned_to=request.POST.get('assigned_to', ''),
                    department=request.POST.get('department', ''),
                    priority=request.POST.get('priority', 'medium'),
                    scheduled_date=request.POST.get('scheduled_date', ''),
                    due_date=request.POST.get('due_date', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_task_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                tasks = list_tasks(conn, status=status_f or None,
                                   priority=priority_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_task_list.html', _it_ctx(
        request, tasks=tasks, status_filter=status_f, priority_filter=priority_f,
        search=search, task_statuses=TASK_STATUSES, task_priorities=TASK_PRIORITIES,
        task_types=TASK_TYPES, today=date.today().isoformat(),
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_task_detail(request, task_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    task = None
    try:
        task = get_task(conn, task_id)
        if not task:
            return redirect('it_task_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'status':
                    set_task_status(conn, task_id, request.POST.get('status', ''))
                    success = 'Status updated.'
                else:
                    update_task(
                        conn, task_id,
                        task_name=request.POST.get('task_name', ''),
                        task_type=request.POST.get('task_type', ''),
                        description=request.POST.get('description', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        department=request.POST.get('department', ''),
                        priority=request.POST.get('priority', ''),
                        scheduled_date=request.POST.get('scheduled_date', ''),
                        due_date=request.POST.get('due_date', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Task updated.'
                conn.commit()
                task = get_task(conn, task_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_task_detail.html', _it_ctx(
        request, task=task, can_edit=can_edit,
        task_statuses=TASK_STATUSES, task_priorities=TASK_PRIORITIES,
        task_types=TASK_TYPES, error=error, success=success,
    ))


@dept_required('information_tech')
def it_incident_list(request):
    status_f = request.GET.get('status', '').strip()
    severity_f = request.GET.get('severity', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        incidents = list_incidents(conn, status=status_f or None,
                                   severity=severity_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_incident(
                    conn,
                    title=request.POST.get('title', ''),
                    severity=request.POST.get('severity', 'info'),
                    description=request.POST.get('description', ''),
                    affected_systems=request.POST.get('affected_systems', ''),
                    reported_date=request.POST.get('reported_date', '') or date.today().isoformat(),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('it_incident_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                incidents = list_incidents(conn, status=status_f or None,
                                           severity=severity_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'it_incident_list.html', _it_ctx(
        request, incidents=incidents, status_filter=status_f, severity_filter=severity_f,
        search=search, incident_statuses=INCIDENT_STATUSES, incident_severities=INCIDENT_SEVERITIES,
        today=date.today().isoformat(), error=error, success=success,
    ))


@dept_required('information_tech')
def it_incident_detail(request, incident_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    incident = None
    try:
        incident = get_incident(conn, incident_id)
        if not incident:
            return redirect('it_incident_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'status':
                    set_incident_status(conn, incident_id, request.POST.get('status', ''))
                    success = 'Status updated.'
                else:
                    update_incident(
                        conn, incident_id,
                        title=request.POST.get('title', ''),
                        severity=request.POST.get('severity', ''),
                        description=request.POST.get('description', ''),
                        affected_systems=request.POST.get('affected_systems', ''),
                        reported_date=request.POST.get('reported_date', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Incident updated.'
                conn.commit()
                incident = get_incident(conn, incident_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_incident_detail.html', _it_ctx(
        request, incident=incident, can_edit=can_edit,
        incident_statuses=INCIDENT_STATUSES, incident_severities=INCIDENT_SEVERITIES,
        error=error, success=success,
    ))


@dept_required('information_tech')
def it_network_detail(request, device_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    device = None
    try:
        device = get_network_device(conn, device_id)
        if not device:
            return redirect('it_network_list')
        if request.method == 'POST' and can_edit:
            try:
                update_network_device(
                    conn, device_id,
                    hostname=request.POST.get('hostname', ''),
                    ip_address=request.POST.get('ip_address', ''),
                    mac_address=request.POST.get('mac_address', ''),
                    device_type=request.POST.get('device_type', ''),
                    manufacturer=request.POST.get('manufacturer', ''),
                    model=request.POST.get('model', ''),
                    location=request.POST.get('location', ''),
                    status=request.POST.get('status', ''),
                    last_seen=request.POST.get('last_seen', '') or None,
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Device updated.'
                device = get_network_device(conn, device_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'it_network_detail.html', _it_ctx(
        request, device=device, can_edit=can_edit,
        device_types=NETWORK_DEVICE_TYPES, device_statuses=NETWORK_DEVICE_STATUSES,
        error=error, success=success,
    ))


