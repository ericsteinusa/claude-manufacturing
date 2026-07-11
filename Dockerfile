FROM python:3.12-slim

# No extra OS packages needed: psycopg2-binary ships its own libpq, and every
# other pinned dependency in requirements.txt is pure Python.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Does NOT run collectstatic or any other manage.py command at build time —
# manufacturing.apps.ManufacturingConfig.ready() opens a real Postgres
# connection the moment Django's app registry populates, and no database is
# reachable during `docker build`. That happens in docker-entrypoint.sh once
# the container is actually running and the db service is reachable.
ENTRYPOINT ["./docker-entrypoint.sh"]
