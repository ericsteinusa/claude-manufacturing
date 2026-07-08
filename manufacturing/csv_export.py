"""Shared CSV/Excel export helper for Django list-page "Export" buttons.

Qt-free (safe to import from views/ and tests) — see CLAUDE.md testing notes.
Builds on :func:`reports_core.to_csv_bytes` and :func:`reports_core.export_to_excel`,
the existing Qt-free serializers (the latter already had test coverage in
``test_phase5_reports.py`` but was never wired into a view), so there is one
place that turns headers/rows into CSV or XLSX bytes.
"""

from django.http import HttpResponse

from .reports_core import export_to_excel, to_csv_bytes

XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


def csv_response(filename, columns, rows):
    """Return an ``HttpResponse`` streaming ``rows`` as a CSV attachment.

    ``columns`` is a list of ``(field, header)`` pairs controlling column
    order and the header row label. Row dicts may be missing or have extra
    keys relative to ``columns`` (live schema can diverge — see CLAUDE.md);
    missing values render as an empty cell rather than raising.
    """
    fields = [field for field, _header in columns]
    headers = [header for _field, header in columns]
    body = to_csv_bytes(headers, [[row.get(f, '') for f in fields] for row in rows])
    response = HttpResponse(body, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def excel_response(filename, columns, rows, sheet_name='Sheet1'):
    """Return an ``HttpResponse`` streaming ``rows`` as an .xlsx attachment.

    Same ``columns``/``rows`` shape as :func:`csv_response`, so callers can
    reuse the exact same data assembly for both formats.
    """
    fields = [field for field, _header in columns]
    headers = [header for _field, header in columns]
    body = export_to_excel({
        sheet_name: (headers, [[row.get(f, '') for f in fields] for row in rows]),
    })
    response = HttpResponse(body, content_type=XLSX_CONTENT_TYPE)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_response(request, base_filename, columns, rows):
    """Dispatch to :func:`excel_response` or :func:`csv_response` based on
    ``?format=xlsx`` in the request, sharing one column/row assembly per
    caller. Defaults to CSV when the param is absent or anything else.
    """
    if request.GET.get('format') == 'xlsx':
        return excel_response(f'{base_filename}.xlsx', columns, rows)
    return csv_response(f'{base_filename}.csv', columns, rows)
