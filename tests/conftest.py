"""Bootstraps Django settings once for the whole session.

Only needed by tests that import manufacturing/api_views.py or other
Django-request-shaped modules (django.http.JsonResponse touches
settings.DEFAULT_CHARSET at construction time). The *_core.py modules
tested elsewhere in this suite don't need this — they're plain Python
with no Django import, so this setup is a no-op for them.

No live database is touched: every DATABASES/SECRET_KEY setting in
manufacture/settings.py has an env-var fallback, and Django doesn't
open a connection until a query actually runs (which the API tests
mock via a fake connection).
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacture.settings')
django.setup()
