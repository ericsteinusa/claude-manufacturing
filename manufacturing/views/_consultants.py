"""Views: Consultant Time & Charges.

Decorator split mirrors the existing requisition-vs-PO split: standing up
an engagement and logging time/charges against it is any employee's job
(like filing a requisition), while consultant master data and anything
that converts into a real payable (cutting/submitting/deciding an invoice)
is a Purchasing responsibility (like Vendor Management / deciding a PO).
"""

from django.shortcuts import render, redirect
from django.http import HttpResponse

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required, dept_manager_required, login_required
from ..accounts import READ_ONLY_ROLES
from ..csv_export import export_response
from ..personnel_core import get_person, get_person_by_email, load_depts
from ..accounting_core import load_vendors

from ..consultants_core import (
    ENGAGEMENT_STATUSES, CHARGE_CATEGORIES,
    ensure_consultant_tables,
    list_consultants, get_consultant, create_consultant, update_consultant,
    list_engagements, get_engagement, create_engagement, activate_engagement,
    close_engagement,
    list_time_entries, add_time_entry, list_charges, add_charge,
    get_invoice_lines, create_consultant_invoice, submit_consultant_invoice,
    get_consultant_invoice, list_consultant_invoices,
    decide_consultant_invoice_via_workflow,
    get_consultant_spend_report, get_engagement_spend_report,
    get_dept_consultant_spend_report,
)


def _ctx(request, **extra):
    return {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        **extra,
    }


def _actor(request, conn):
    """Resolve the caller's people_id/dept_id for engagement visibility
    scoping, mirroring views/__init__.py's _req_actor for requisitions."""
    person = get_person_by_email(conn, request.session.get('user_email', ''))
    people_id = person['id'] if person else None
    full = get_person(conn, people_id) if people_id else None
    return {
        'people_id': people_id,
        'dept_id': full['dept_id'] if full else None,
        'full_access': request.session.get('user_full_access', False),
        'is_purchasing': request.session.get('user_dept_key') == 'purchasing',
    }


# ---------------------------------------------------------------------------
# Consultant master data (Purchasing)
# ---------------------------------------------------------------------------

@dept_required('purchasing')
def consultant_list(request):
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        ensure_consultant_tables(conn)
        conn.commit()
        rows = list_consultants(conn, search=search or None)
    finally:
        conn.close()
    return render(request, 'consultant_list.html', _ctx(
        request, rows=rows, search=search,
    ))


@dept_required('purchasing', write_redirect='consultant_list')
def consultant_new(request):
    error = None
    conn = get_db_connection()
    try:
        vendors = load_vendors(conn)
        if request.method == 'POST':
            try:
                consultant_id = create_consultant(
                    conn,
                    display_name=request.POST.get('display_name', '').strip(),
                    supplier_id=request.POST.get('supplier_id') or None,
                    default_hourly_rate=(
                        float(request.POST.get('default_hourly_rate'))
                        if request.POST.get('default_hourly_rate') else None),
                    specialty=request.POST.get('specialty', '').strip(),
                    email=request.POST.get('email', '').strip(),
                    phone_number=request.POST.get('phone_number', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('consultant_detail', consultant_id=consultant_id)
            except ValueError as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'consultant_form.html', _ctx(
        request, vendors=vendors, error=error, consultant=None,
    ))


@dept_required('purchasing', write_redirect='consultant_list')
def consultant_detail(request, consultant_id):
    error = success = None
    conn = get_db_connection()
    try:
        consultant = get_consultant(conn, consultant_id)
        if not consultant:
            return redirect('consultant_list')
        if request.method == 'POST':
            action = request.POST.get('action', 'update')
            try:
                if action == 'toggle_active':
                    update_consultant(conn, consultant_id,
                                       is_active=not consultant['is_active'])
                    success = ('Deactivated.' if consultant['is_active']
                               else 'Activated.')
                else:
                    update_consultant(
                        conn, consultant_id,
                        display_name=request.POST.get('display_name', '').strip(),
                        default_hourly_rate=(
                            float(request.POST.get('default_hourly_rate'))
                            if request.POST.get('default_hourly_rate') else None),
                        specialty=request.POST.get('specialty', '').strip(),
                        email=request.POST.get('email', '').strip(),
                        phone_number=request.POST.get('phone_number', '').strip(),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    success = 'Saved.'
                conn.commit()
                consultant = get_consultant(conn, consultant_id)
            except ValueError as exc:
                conn.rollback()
                error = str(exc)
        engagements = list_engagements(conn, scope_all=True)
        engagements = [e for e in engagements if e['consultant_id'] == consultant_id]
        vendors = load_vendors(conn)
    finally:
        conn.close()
    return render(request, 'consultant_detail.html', _ctx(
        request, consultant=consultant, engagements=engagements,
        vendors=vendors, error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Engagements (any logged-in employee, scoped to their own dept unless
# full-access or Purchasing)
# ---------------------------------------------------------------------------

@login_required
def engagement_list(request):
    status_f = request.GET.get('status', '').strip()
    conn = get_db_connection()
    try:
        actor = _actor(request, conn)
        scope_all = actor['full_access'] or actor['is_purchasing']
        rows = list_engagements(
            conn, dept_id=actor['dept_id'], status=status_f or None,
            scope_all=scope_all,
        )
    finally:
        conn.close()
    return render(request, 'engagement_list.html', _ctx(
        request, rows=rows, status_filter=status_f,
        statuses=ENGAGEMENT_STATUSES,
    ))


@login_required
def engagement_new(request):
    error = None
    conn = get_db_connection()
    try:
        actor = _actor(request, conn)
        consultants = list_consultants(conn, active_only=True)
        depts = load_depts(conn)
        if request.method == 'POST':
            try:
                engagement_id = create_engagement(
                    conn,
                    consultant_id=request.POST.get('consultant_id'),
                    dept_id=request.POST.get('dept_id') or actor['dept_id'],
                    title=request.POST.get('title', '').strip(),
                    purpose=request.POST.get('purpose', '').strip(),
                    start_date=request.POST.get('start_date') or None,
                    end_date=request.POST.get('end_date') or None,
                    default_hourly_rate=(
                        float(request.POST.get('default_hourly_rate'))
                        if request.POST.get('default_hourly_rate') else None),
                    requested_by=request.session.get('user_email', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('engagement_detail', engagement_id=engagement_id)
            except ValueError as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'engagement_form.html', _ctx(
        request, consultants=consultants, depts=depts, error=error,
    ))


@login_required
def engagement_detail(request, engagement_id):
    error = success = None
    conn = get_db_connection()
    try:
        actor = _actor(request, conn)
        engagement = get_engagement(conn, engagement_id)
        if not engagement:
            return redirect('engagement_list')
        can_view = (actor['full_access'] or actor['is_purchasing']
                    or engagement['dept_id'] == actor['dept_id'])
        if not can_view:
            return redirect('engagement_list')
        can_edit = (request.session.get('user_role') not in READ_ONLY_ROLES
                    and engagement['status'] in ('draft', 'active'))

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action')
            try:
                if action == 'activate':
                    activate_engagement(conn, engagement_id)
                    success = 'Engagement activated.'
                elif action == 'close':
                    close_engagement(conn, engagement_id)
                    success = 'Engagement closed.'
                elif action == 'add_time':
                    add_time_entry(
                        conn, engagement_id,
                        work_date=request.POST.get('work_date'),
                        hours=request.POST.get('hours'),
                        hourly_rate=(
                            float(request.POST.get('hourly_rate'))
                            if request.POST.get('hourly_rate') else None),
                        description=request.POST.get('description', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    success = 'Time entry added.'
                elif action == 'add_charge':
                    add_charge(
                        conn, engagement_id,
                        charge_date=request.POST.get('charge_date'),
                        category=request.POST.get('category'),
                        amount=request.POST.get('amount'),
                        description=request.POST.get('description', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    success = 'Charge added.'
                conn.commit()
                engagement = get_engagement(conn, engagement_id)
            except ValueError as exc:
                conn.rollback()
                error = str(exc)

        time_entries = list_time_entries(conn, engagement_id)
        charges = list_charges(conn, engagement_id)
        invoices = [
            i for i in list_consultant_invoices(conn)
            if i['engagement_id'] == engagement_id
        ]
        unbilled_time = [t for t in time_entries if not t['invoice_id']]
        unbilled_charges = [c for c in charges if not c['invoice_id']]
    finally:
        conn.close()
    return render(request, 'engagement_detail.html', _ctx(
        request, engagement=engagement, time_entries=time_entries,
        charges=charges, invoices=invoices,
        unbilled_time=unbilled_time, unbilled_charges=unbilled_charges,
        can_edit=can_edit, error=error, success=success,
        charge_categories=CHARGE_CATEGORIES,
        can_invoice=(actor['full_access'] or actor['is_purchasing']),
    ))


# ---------------------------------------------------------------------------
# Consultant invoices (Purchasing — converts a billing period into a
# real, approval-gated payable)
# ---------------------------------------------------------------------------

@dept_required('purchasing', write_redirect='engagement_detail')
def consultant_invoice_new(request, engagement_id):
    if request.method != 'POST':
        return redirect('engagement_detail', engagement_id=engagement_id)
    conn = get_db_connection()
    try:
        try:
            cinv_id = create_consultant_invoice(
                conn, engagement_id,
                period_start=request.POST.get('period_start'),
                period_end=request.POST.get('period_end'),
                created_by=request.session.get('user_email', ''),
            )
            conn.commit()
            return redirect('consultant_invoice_detail', cinv_id=cinv_id)
        except ValueError as exc:
            conn.rollback()
            actor = _actor(request, conn)
            engagement = get_engagement(conn, engagement_id)
            time_entries = list_time_entries(conn, engagement_id)
            charges = list_charges(conn, engagement_id)
            return render(request, 'engagement_detail.html', _ctx(
                request, engagement=engagement,
                time_entries=time_entries, charges=charges,
                invoices=[i for i in list_consultant_invoices(conn)
                          if i['engagement_id'] == engagement_id],
                unbilled_time=[t for t in time_entries if not t['invoice_id']],
                unbilled_charges=[c for c in charges if not c['invoice_id']],
                can_edit=(request.session.get('user_role') not in READ_ONLY_ROLES
                          and engagement['status'] in ('draft', 'active')),
                error=str(exc), success=None,
                charge_categories=CHARGE_CATEGORIES,
                can_invoice=(actor['full_access'] or actor['is_purchasing']),
            ))
    finally:
        conn.close()


@dept_required('purchasing')
def consultant_invoice_list(request):
    status_f = request.GET.get('status', '').strip()
    conn = get_db_connection()
    try:
        rows = list_consultant_invoices(conn, status=status_f or None)
    finally:
        conn.close()
    return render(request, 'consultant_invoice_list.html', _ctx(
        request, rows=rows, status_filter=status_f,
    ))


def _invoice_detail_ctx(request, conn, cinv_id, error=None, success=None):
    from .. import approval_workflow_core

    cinv = get_consultant_invoice(conn, cinv_id)
    if not cinv:
        return None
    lines = get_invoice_lines(conn, cinv_id)
    approval = approval_workflow_core.get_entity_approval_status(
        conn, 'consultant_invoice', cinv_id)
    user_role = request.session.get('user_role', '')
    full_access = request.session.get('user_full_access', False)
    pending_step = next(
        (s for s in approval['steps']
         if s['status'] == 'pending'
         and (full_access or s['approver_role'] == user_role)),
        None,
    )
    return _ctx(
        request, cinv=cinv, lines=lines, approval=approval,
        pending_step=pending_step, error=error, success=success,
    )


@dept_required('purchasing')
def consultant_invoice_detail(request, cinv_id):
    conn = get_db_connection()
    try:
        ctx = _invoice_detail_ctx(request, conn, cinv_id)
    finally:
        conn.close()
    if ctx is None:
        return redirect('consultant_invoice_list')
    return render(request, 'consultant_invoice_detail.html', ctx)


@dept_required('purchasing', write_redirect='consultant_invoice_detail')
def consultant_invoice_submit(request, cinv_id):
    if request.method != 'POST':
        return redirect('consultant_invoice_detail', cinv_id=cinv_id)
    conn = get_db_connection()
    error = None
    try:
        try:
            submit_consultant_invoice(
                conn, cinv_id, request.session.get('user_email', ''))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            error = str(exc)
        ctx = _invoice_detail_ctx(request, conn, cinv_id, error=error)
    finally:
        conn.close()
    if error:
        return render(request, 'consultant_invoice_detail.html', ctx)
    return redirect('consultant_invoice_detail', cinv_id=cinv_id)


@dept_required('purchasing', write_redirect='consultant_invoice_detail')
def consultant_invoice_decide(request, cinv_id):
    from .. import approval_workflow_core

    if request.method != 'POST':
        return redirect('consultant_invoice_detail', cinv_id=cinv_id)
    decision = request.POST.get('decision')
    if decision not in ('approved', 'rejected'):
        return redirect('consultant_invoice_detail', cinv_id=cinv_id)
    conn = get_db_connection()
    error = None
    try:
        approval = approval_workflow_core.get_entity_approval_status(
            conn, 'consultant_invoice', cinv_id)
        pending_step = next(
            (s for s in approval['steps'] if s['status'] == 'pending'), None)
        if pending_step:
            try:
                decide_consultant_invoice_via_workflow(
                    conn, cinv_id, pending_step['id'], decision,
                    request.session.get('user_email', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                error = str(exc)
        ctx = _invoice_detail_ctx(request, conn, cinv_id, error=error)
    finally:
        conn.close()
    if error:
        return render(request, 'consultant_invoice_detail.html', ctx)
    return redirect('consultant_invoice_detail', cinv_id=cinv_id)


# ---------------------------------------------------------------------------
# Spend reports (Purchasing department manager, mirrors prod_labor_report)
# ---------------------------------------------------------------------------

@dept_manager_required('purchasing')
def consultant_spend_report(request):
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    conn = get_db_connection()
    try:
        by_consultant = get_consultant_spend_report(
            conn, date_from=date_from or None, date_to=date_to or None)
        by_engagement = get_engagement_spend_report(
            conn, date_from=date_from or None, date_to=date_to or None)
        by_dept = get_dept_consultant_spend_report(
            conn, date_from=date_from or None, date_to=date_to or None)
    finally:
        conn.close()
    kpis = {
        'consultant_count': len(by_consultant),
        'engagement_count': len(by_engagement),
        'total_hours': sum(c['hours'] for c in by_consultant),
        'total_cost': sum(c['grand_total'] or 0 for c in by_consultant),
    }
    return render(request, 'consultant_spend_report.html', _ctx(
        request, by_consultant=by_consultant, by_engagement=by_engagement,
        by_dept=by_dept, kpis=kpis, date_from=date_from, date_to=date_to,
    ))


@dept_manager_required('purchasing')
def consultant_spend_report_export(request):
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    section = request.GET.get('section', 'consultant')
    conn = get_db_connection()
    try:
        if section == 'engagement':
            rows = get_engagement_spend_report(
                conn, date_from=date_from or None, date_to=date_to or None)
        else:
            rows = get_consultant_spend_report(
                conn, date_from=date_from or None, date_to=date_to or None)
    finally:
        conn.close()
    if section == 'engagement':
        return export_response(request, f'consultant_spend_by_engagement_{date_from}_{date_to}', [
            ('engagement_number', 'Engagement #'), ('title', 'Title'),
            ('consultant_name', 'Consultant'), ('dept_name', 'Department'),
            ('status', 'Status'), ('hours', 'Hours'),
            ('time_cost', 'Time Cost'), ('charge_total', 'Charges'),
            ('grand_total', 'Total'), ('invoiced_total', 'Invoiced'),
            ('open_balance', 'Open Balance'),
        ], rows)
    return export_response(request, f'consultant_spend_{date_from}_{date_to}', [
        ('consultant_name', 'Consultant'), ('engagement_count', 'Engagements'),
        ('hours', 'Hours'), ('time_cost', 'Time Cost'),
        ('charge_total', 'Charges'), ('grand_total', 'Total'),
    ], rows)
