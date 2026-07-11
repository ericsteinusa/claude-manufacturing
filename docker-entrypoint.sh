#!/bin/sh
set -e

# docker-compose's `depends_on` only waits for the db *container* to start,
# not for Postgres to actually accept connections — and
# manufacturing.apps.ManufacturingConfig.ready() needs a live connection the
# moment Django's app registry populates (collectstatic below, or gunicorn's
# own worker boot). Poll with a real connection attempt, not just a TCP
# check, so a container that's listening but still running initdb doesn't
# pass prematurely.
echo "Waiting for database at ${DB_HOST:-localhost}:${DB_PORT:-5432}..."
attempt=0
max_attempts=30
until python -c "
import os, sys
import psycopg2
try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'company_db'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
        connect_timeout=3,
    )
    conn.close()
except psycopg2.OperationalError as e:
    print(e, file=sys.stderr)
    sys.exit(1)
"; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Database did not become reachable after ${max_attempts} attempts — giving up." >&2
    exit 1
  fi
  echo "Database not ready yet (attempt ${attempt}/${max_attempts}) — retrying in 2s..."
  sleep 2
done
echo "Database is reachable."

# manufacturing/*.py's own schema (init_schema(), run above via app-registry
# population) never touches Django's own built-in tables -- django_session
# (contrib.sessions), django_admin_log/auth_permission/etc. (contrib.admin/
# auth/contenttypes) only exist if `manage.py migrate` has actually run.
# This app has no real migrations of its own (manufacturing/migrations/ is
# empty besides __init__.py) so this is only ever applying Django's bundled
# migrations for those built-in apps -- but skipping it entirely, as this
# script did until now, meant every fresh deployment 500'd on the very first
# login: SessionMiddleware tries to save the session to a table that was
# never created. Caught via real load testing against a fresh container,
# not by inspection -- collectstatic's own app-registry population made the
# app *look* fully booted, but nothing had ever exercised an actual login.
python manage.py migrate --noinput

python manage.py collectstatic --noinput

# --preload loads the WSGI app (triggering Django's app registry population,
# and so manufacturing.apps.ManufacturingConfig.ready() -> init_schema()) once
# in the gunicorn master process *before* forking workers. Without it, each
# of the 3 workers independently re-imports the app and re-runs init_schema()
# concurrently — caught in practice as a real
# "psycopg2.errors.InternalError_: tuple concurrently updated" crash on first
# boot (multiple workers racing to CREATE/ALTER the same tables and audit
# trigger function at once), not just a theoretical race.
exec gunicorn manufacture.wsgi:application --bind 0.0.0.0:8000 --workers 3 --preload
