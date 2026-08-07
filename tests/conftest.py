"""Bootstraps Django settings once for the whole session.

Only needed by tests that import manufacturing/api_views.py or other
Django-request-shaped modules (django.http.JsonResponse touches
settings.DEFAULT_CHARSET at construction time). The *_core.py modules
tested elsewhere in this suite don't need this — they're plain Python
with no Django import, so this setup is a no-op for them.

No live database is touched: every DATABASES/SECRET_KEY setting in
manufacture/settings.py has an env-var fallback, and Django doesn't
open a connection until a query actually runs (which the API tests
mock via a fake connection) — except that ManufacturingConfig.ready()
(manufacturing/apps.py) unconditionally calls _init_schema(), which
connects to a real Postgres to create/reconcile tables. That's fine
for the dev server but breaks `django.setup()` itself in CI, which
has no DB service (see .github/workflows/tests.yml). _init_schema is
patched out here for the duration of setup() only — nothing else in
this suite depends on it having run, since every test that touches
the DB does so through its own mocked connection.
"""
import os
from unittest.mock import patch

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacture.settings')
with patch('manufacturing.views._init_schema', lambda: None):
    django.setup()
