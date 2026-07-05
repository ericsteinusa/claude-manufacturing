"""Shared CSV export helper for Django list-page "Export CSV" buttons.

Qt-free (safe to import from views/ and tests) — see CLAUDE.md testing notes.
Builds on :func:`reports_core.to_csv_bytes`, the existing Qt-free CSV
serializer, so there is one place that turns headers/rows into CSV bytes.
"""

from django.http import HttpResponse

from .reports_core import to_csv_bytes


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
