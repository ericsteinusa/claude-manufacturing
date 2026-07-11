# Deployment

This is Phase 1 of the production deployment plan (Phase 0 — settings
hardening — already merged). It's a portable Docker Compose stack: no
hosting target has been chosen yet, so this runs identically on a bare VPS
today and becomes the base image for a managed platform (Fly/Render/ECS)
later without redoing this work.

## Quick start

```sh
cp .env.example .env
# edit .env: set DB_PASSWORD at minimum

docker compose up --build
```

This brings up three services:

- `db` — Postgres 16, data in a named volume (`postgres_data`), **not**
  published to the host (see [Backups](#backups-and-restore) for how to
  reach it anyway)
- `web` — the Django app, built from `Dockerfile`, behind gunicorn
- `nginx` — listens on port 80, serves `/static/` directly from a shared
  volume and proxies everything else to `web`

First boot takes a few extra seconds: `docker-entrypoint.sh` waits for
Postgres to actually accept connections (not just for the container to
start), then runs `collectstatic`, then starts gunicorn.

Visit `http://localhost/`.

## Required environment variables

Copy `.env.example` to `.env` and fill in real values. At minimum:

- `DB_PASSWORD` — required; `docker compose up` refuses to start without it
- `DJANGO_SECRET_KEY` — required once you set `DJANGO_DEBUG=False` (see
  below); falls back to an insecure checked-in key otherwise, which is fine
  for local dev only

See `.env.example` for the full list, including `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS` for a real domain.

## Enabling HTTPS

`nginx/app.conf` has no TLS configured yet — this Phase 1 baseline is
intentionally hosting-agnostic, and a cert needs a real domain name, which
depends on a hosting decision not yet made. Until then, `DJANGO_DEBUG=False`
alone does **not** force HTTPS or mark cookies `Secure`, so login keeps
working over plain HTTP.

Once you have a domain and a cert:

1. Add a `listen 443 ssl` server block to `nginx/app.conf` with your
   certificate paths (or terminate TLS at a load balancer in front of nginx
   instead).
2. Set `DJANGO_HTTPS_ENABLED=True` in `.env`. This turns on
   `SECURE_SSL_REDIRECT`, secure cookies, HSTS, and trusts nginx's
   `X-Forwarded-Proto` header (safe because nginx is the only service with a
   published port — a client can never reach gunicorn directly to spoof it).

## Pointing at a managed Postgres

Nothing to build — `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` are
already just environment variables (`manufacture/settings.py`). To use a
managed instance (RDS, Cloud SQL, Neon, etc.) instead of the bundled `db`
service:

1. Remove `db` from `docker-compose.yml` (or leave it — unused services just
   sit idle).
2. Remove the `DB_HOST`/`DB_PORT` overrides from the `web` service's
   `environment:` block, and set the real values in `.env` instead.

## Backups and restore

`scripts/backup_db.sh` / `scripts/restore_db.sh` are thin `pg_dump`/`psql`
wrappers using the same `DB_*` env vars as everything else — hosting-agnostic,
and the right tool once you're pointed at a managed Postgres reachable from
wherever you run them (they need `postgresql-client` installed on that
machine).

For the bundled `db` service specifically, since its port isn't published to
the host, use its own built-in client tools instead:

```sh
# Backup
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip' \
    > "backups/company_db_$(date +%Y%m%d_%H%M%S).sql.gz"

# Restore (DESTRUCTIVE — overwrites existing data)
gunzip -c backups/company_db_TIMESTAMP.sql.gz | \
    docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

Neither path is scheduled automatically yet — wire whichever one fits into
cron / your platform's scheduled-job mechanism.

## What's deliberately not done yet (and why)

- **pgbouncer / connection pooling** — `manufacturing/db_pg.py`'s
  `get_db_connection()` opens a fresh connection per call, which won't hold
  up under real concurrent load. Not wired up here because there's no real
  traffic yet to justify it — add it once load testing (Phase 3) shows it's
  needed, not before.
- **S3/object storage for `MEDIA_ROOT`** — depends on which hosting target
  gets picked later; forcing a specific provider now would mean redoing this
  when that decision lands. Uploaded files (Document Control, P2-F) still
  live on local disk / the `media_files` volume.
- **A real deploy step in CI** — `.github/workflows/docker-build.yml` only
  builds the image to catch a broken Dockerfile on every PR. There's no
  hosting target/credentials yet to actually deploy to.
- **TLS/certbot** — needs a real domain name, which depends on the hosting
  decision. See [Enabling HTTPS](#enabling-https) for what to do once one
  exists.

These map to Phases 2–4 of the original deployment scoping document, not
gaps in this phase.
