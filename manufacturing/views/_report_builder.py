"""Views: Custom Report Builder (P4-F) — pick table/columns, add filters,
group-by/aggregate, sort, run a live preview, save with an access level,
export CSV/PDF, and configure scheduled email delivery."""

import json

from django.http import HttpResponse
from django.shortcuts import render, redirect

from ..db_pg import get_db_connection
from ..auth_decorators import login_required
from ..log_utils import get_logger
from ..csv_export import csv_response

from ..report_builder_core import (
    REPORTABLE_TABLES, ACCESS_LEVELS, SCHEDULE_FREQUENCIES, SCHEDULE_FORMATS,
    ensure_report_builder_tables, create_saved_report, update_saved_report,
    get_saved_report, list_saved_reports, delete_saved_report,
    run_report, report_to_pdf_bytes,
)

log = get_logger(__name__)


def _rb_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'tables_json': json.dumps({
            name: {'label': t['label'],
                   'columns': {c: v for c, v in t['columns'].items()}}
            for name, t in REPORTABLE_TABLES.items()
        }),
        'access_levels': ACCESS_LEVELS,
        'schedule_frequencies': SCHEDULE_FREQUENCIES,
        'schedule_formats': SCHEDULE_FORMATS,
    }
    ctx.update(extra)
    return ctx


def _can_share(request) -> bool:
    """Only managers/full-access users may save a report at a broader
    access level than 'private' (mirrors this codebase's existing
    manager/full-access gating convention)."""
    return bool(request.session.get('user_is_manager') or request.session.get('user_full_access'))


def _definition_from_post(post) -> dict:
    columns = post.getlist('columns')
    group_by = post.getlist('group_by')

    filters = []
    for col, op, val in zip(post.getlist('filter_column'), post.getlist('filter_operator'),
                             post.getlist('filter_value')):
        if col and op:
            filters.append({'column': col, 'operator': op, 'value': val})

    aggregates = []
    for col, func in zip(post.getlist('agg_column'), post.getlist('agg_func')):
        if col and func:
            aggregates.append({'column': col, 'func': func})

    sort = []
    sort_col = post.get('sort_column', '')
    if sort_col:
        sort.append({'column': sort_col, 'direction': post.get('sort_direction', 'asc')})

    return {'columns': columns, 'filters': filters, 'group_by': group_by,
            'aggregates': aggregates, 'sort': sort}


@login_required
def report_builder_list(request):
    conn = get_db_connection()
    try:
        ensure_report_builder_tables(conn)
        conn.commit()
        reports = list_saved_reports(
            conn, request.session.get('user_email', ''),
            request.session.get('user_dept_key', ''),
            request.session.get('user_full_access', False))
    finally:
        conn.close()
    return render(request, 'report_builder_list.html', _rb_ctx(request, reports=reports))


@login_required
def report_builder_new(request):
    return _report_builder_form(request, report=None)


@login_required
def report_builder_edit(request, report_id):
    conn = get_db_connection()
    try:
        ensure_report_builder_tables(conn)
        conn.commit()
        report = get_saved_report(conn, report_id)
    finally:
        conn.close()
    if not report:
        return redirect('report_builder_list')
    return _report_builder_form(request, report=report)


def _report_builder_form(request, report):
    error = success = None
    result = None
    table_name = (report or {}).get('table_name', '')
    definition = (report or {}).get('definition') or {'columns': [], 'filters': [],
                                                        'group_by': [], 'aggregates': [], 'sort': []}

    if request.method == 'POST':
        action = request.POST.get('action', 'preview')
        table_name = request.POST.get('table_name', '')
        definition = _definition_from_post(request.POST)
        conn = get_db_connection()
        try:
            ensure_report_builder_tables(conn)
            conn.commit()
            if action == 'preview':
                try:
                    result = run_report(conn, table_name, definition, limit=200)
                    fields = [f for f, _h in result['output_fields']]
                    result['row_lists'] = [[row.get(f, '') for f in fields] for row in result['rows']]
                except ValueError as e:
                    error = str(e)
            elif action == 'save':
                access_level = request.POST.get('access_level', 'private')
                if access_level != 'private' and not _can_share(request):
                    error = 'Only managers can save department- or company-wide reports.'
                else:
                    try:
                        if report:
                            update_saved_report(
                                conn, report['id'],
                                name=request.POST.get('name', '').strip(),
                                table_name=table_name, definition=definition,
                                access_level=access_level)
                            report_id = report['id']
                        else:
                            report_id = create_saved_report(
                                conn, request.POST.get('name', '').strip(), table_name,
                                definition, access_level,
                                request.session.get('user_email', ''),
                                request.session.get('user_dept_key', ''),
                                request.session.get('user_email', ''))
                        conn.commit()
                        return redirect('report_builder_detail', report_id=report_id)
                    except ValueError as e:
                        conn.rollback()
                        error = str(e)
        finally:
            conn.close()

    current_columns = REPORTABLE_TABLES.get(table_name, {}).get('columns', {})
    return render(request, 'report_builder_form.html', _rb_ctx(
        request, report=report, table_name=table_name,
        tables_json_parsed=REPORTABLE_TABLES, current_columns=current_columns,
        definition_json=json.dumps(definition), definition=definition,
        result=result, error=error, success=success, can_share=_can_share(request)))


@login_required
def report_builder_detail(request, report_id):
    error = success = None
    conn = get_db_connection()
    try:
        ensure_report_builder_tables(conn)
        conn.commit()
        report = get_saved_report(conn, report_id)
        if not report:
            return redirect('report_builder_list')

        if request.method == 'POST':
            try:
                update_saved_report(
                    conn, report_id,
                    schedule_enabled=request.POST.get('schedule_enabled') == 'on',
                    schedule_frequency=request.POST.get('schedule_frequency', ''),
                    schedule_recipients=request.POST.get('schedule_recipients', '').strip(),
                    schedule_format=request.POST.get('schedule_format', 'csv'),
                )
                conn.commit()
                success = 'Schedule updated.'
                report = get_saved_report(conn, report_id)
            except ValueError as e:
                conn.rollback()
                error = str(e)

        result = run_report(conn, report['table_name'], report['definition'], limit=200)
        fields = [f for f, _h in result['output_fields']]
        result['row_lists'] = [[row.get(f, '') for f in fields] for row in result['rows']]
    finally:
        conn.close()

    return render(request, 'report_builder_detail.html', _rb_ctx(
        request, report=report, result=result, error=error, success=success))


@login_required
def report_builder_csv(request, report_id):
    conn = get_db_connection()
    try:
        ensure_report_builder_tables(conn)
        conn.commit()
        report = get_saved_report(conn, report_id)
        if not report:
            return redirect('report_builder_list')
        result = run_report(conn, report['table_name'], report['definition'], limit=5000)
    finally:
        conn.close()
    columns = result['output_fields']
    return csv_response(f"{report['name']}.csv", columns, result['rows'])


@login_required
def report_builder_pdf(request, report_id):
    conn = get_db_connection()
    try:
        ensure_report_builder_tables(conn)
        conn.commit()
        report = get_saved_report(conn, report_id)
        if not report:
            return redirect('report_builder_list')
        result = run_report(conn, report['table_name'], report['definition'], limit=1000)
    finally:
        conn.close()
    pdf_bytes = report_to_pdf_bytes(report['name'], result['output_fields'], result['rows'])
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{report["name"]}.pdf"'
    return resp


@login_required
def report_builder_delete(request, report_id):
    conn = get_db_connection()
    try:
        ensure_report_builder_tables(conn)
        conn.commit()
        report = get_saved_report(conn, report_id)
        if report and (report['owner_email'] == request.session.get('user_email', '')
                        or request.session.get('user_full_access')):
            delete_saved_report(conn, report_id)
            conn.commit()
    finally:
        conn.close()
    return redirect('report_builder_list')
