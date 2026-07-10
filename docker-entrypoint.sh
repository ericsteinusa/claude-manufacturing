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

python manage.py collectstatic --noinput

exec gunicorn manufacture.wsgi:application --bind 0.0.0.0:8000 --workers 3
