"""Views: Batch Record Generation."""

from django.shortcuts import render, redirect
from django.http import HttpResponse

from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..batch_record_core import (
    ensure_batch_record_tables, list_batch_records, get_batch_record,
    generate_batch_record, render_batch_record_pdf,
)
from ..work_orders_core import ensure_wo_tables, list_wos

log = get_logger(__name__)

_BATCH_RECORD_DEPT_KEYS = {'production', 'quality_assurance'}


def _batch_record_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_BATCH_RECORD_DEPT_KEYS)
def batch_record_list(request):
    conn = get_db_connection()
    error = None
    try:
        ensure_batch_record_tables(conn)
        ensure_wo_tables(conn)
        if request.method == 'POST':
            try:
                record_id = generate_batch_record(
                    conn, int(request.POST['wo_id']),
                    generated_by=request.session.get('user_email', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('batch_record_detail', record_id=record_id)
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
        records = list_batch_records(conn, search=request.GET.get('q') or None)
        completed_wos = list_wos(conn, status='completed')
    finally:
        conn.close()
    return render(request, 'batch_record_list.html', _batch_record_ctx(
        request, records=records, completed_wos=completed_wos,
        q=request.GET.get('q', ''), error=error,
    ))


@dept_required(_BATCH_RECORD_DEPT_KEYS)
def batch_record_detail(request, record_id):
    conn = get_db_connection()
    try:
        ensure_batch_record_tables(conn)
        record = get_batch_record(conn, record_id)
        if not record:
            return redirect('batch_record_list')
    finally:
        conn.close()
    return render(request, 'batch_record_detail.html', _batch_record_ctx(
        request, record=record,
    ))


@dept_required(_BATCH_RECORD_DEPT_KEYS)
def batch_record_pdf(request, record_id):
    conn = get_db_connection()
    try:
        ensure_batch_record_tables(conn)
        record = get_batch_record(conn, record_id)
        if not record:
            return HttpResponse('Not found', status=404)
    finally:
        conn.close()
    pdf = render_batch_record_pdf(record)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{record["batch_record_number"]}.pdf"'
    return resp
