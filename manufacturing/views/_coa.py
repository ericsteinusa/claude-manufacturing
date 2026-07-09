"""Views: Certificate of Analysis (CoA) generation, mirroring _sampling_plan.py."""

from django.http import HttpResponse
from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES

from ..coa_core import (
    ensure_coa_tables, list_coas, get_coa, get_coa_results, generate_coa,
    render_coa_pdf,
)
from ..lot_core import ensure_lot_tables, list_lots
from ..quality_core import ensure_spc_tables

log = get_logger(__name__)

_COA_DEPT_KEYS = {'quality_assurance'}


def _coa_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def _ensure_all(conn):
    ensure_lot_tables(conn)
    ensure_spc_tables(conn)
    ensure_coa_tables(conn)


@dept_required(_COA_DEPT_KEYS)
def coa_list(request):
    conn = get_db_connection()
    try:
        _ensure_all(conn)
        coas = list_coas(conn, search=request.GET.get('q') or None)
    finally:
        conn.close()
    return render(request, 'coa_list.html', _coa_ctx(
        request, coas=coas, q=request.GET.get('q', ''),
    ))


@dept_required(_COA_DEPT_KEYS, write_redirect='coa_list')
def coa_new(request):
    conn = get_db_connection()
    error = None
    try:
        _ensure_all(conn)
        lots = list_lots(conn)
        if request.method == 'POST':
            lot_raw = request.POST.get('lot_id', '')
            if not lot_raw:
                error = 'Lot is required.'
            else:
                try:
                    coa_id = generate_coa(
                        conn, int(lot_raw),
                        issued_by=request.POST.get('issued_by', '').strip(),
                        created_by=request.session.get('user_email', ''),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    return redirect('coa_detail', coa_id=coa_id)
                except ValueError as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    lot_id_param = request.GET.get('lot_id', '')
    return render(request, 'coa_new.html', _coa_ctx(
        request, lots=lots, error=error,
        preselect_lot_id=int(lot_id_param) if lot_id_param.isdigit() else None,
    ))


@dept_required(_COA_DEPT_KEYS)
def coa_detail(request, coa_id):
    conn = get_db_connection()
    try:
        _ensure_all(conn)
        coa = get_coa(conn, coa_id)
        if not coa:
            return redirect('coa_list')
        results = get_coa_results(conn, coa_id)
    finally:
        conn.close()
    return render(request, 'coa_detail.html', _coa_ctx(
        request, coa=coa, results=results,
    ))


@dept_required(_COA_DEPT_KEYS)
def coa_pdf(request, coa_id):
    conn = get_db_connection()
    try:
        _ensure_all(conn)
        coa = get_coa(conn, coa_id)
        if not coa:
            return redirect('coa_list')
        results = get_coa_results(conn, coa_id)
    finally:
        conn.close()
    pdf = render_coa_pdf(coa, results)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{coa["coa_number"]}.pdf"'
    return resp
