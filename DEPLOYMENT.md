# Deployment

Phases 0 (settings hardening) and 1 (Docker Compose stack) are merged. Phase
2 adds VPS provisioning and TLS on top. Two decisions from the original
scoping doc are resolved: **dedicated instance per customer**, hosted on a
**self-managed VPS** (DigitalOcean/Hetzner/Linode-class, Ubuntu 22.04/24.04).

## New customer checklist

1. Provision a fresh VPS (Ubuntu 22.04/24.04), point the customer's domain's
   DNS `A` record at its IP.
2. Bootstrap the box (creates a `deploy` user, hardens SSH, installs Docker,
   configures the firewall — see the script for exactly what it does):
   ```sh
   ssh root@<new-vps-ip> 'bash -s' < scripts/provision_vps.sh
   ```
3. Log back in as `deploy` (root/password login are disabled by step 2),
   clone the repo, and configure `.env` — see
   [Required environment variables](#required-environment-variables) below.
4. Bring the stack up over plain HTTP first (TLS needs the cert, which needs
   this running for the HTTP-01 challenge):
   ```sh
   docker compose up -d --build
   ```
5. Issue the cert and switch on HTTPS:
   ```sh
   ./scripts/setup_tls.sh <customer-domain> <your-email>
   ```
6. Verify: visit `https://<customer-domain>/`, confirm the cert is valid and
   plain `http://` redirects to `https://`.

## Quick start (local dev / testing this stack itself)

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

Handled by `scripts/setup_tls.sh <domain> <email>` (see the
[New customer checklist](#new-customer-checklist) above) — run it once DNS
for the domain already points at this box and `docker compose up -d` is
running. It:

1. Requests a cert from Let's Encrypt via the `certbot` compose service
   (HTTP-01 challenge, served through nginx's existing `/.well-known/
   acme-challenge/` location — works against the plain-HTTP config that's
   already running, no chicken-and-egg problem).
2. Swaps `nginx/app.conf` for `nginx/app-ssl.conf.template` (domain
   substituted in) and restarts nginx — the previous HTTP-only config is
   saved as `nginx/app.conf.pre-tls.bak`.
3. Sets `DJANGO_HTTPS_ENABLED=True` in `.env` and restarts `web`. This turns
   on `SECURE_SSL_REDIRECT`, secure cookies, HSTS, and trusts nginx's
   `X-Forwarded-Proto` header (safe because nginx is the only service with a
   published port — a client can never reach gunicorn directly to spoof it).

The `certbot` compose service keeps running afterward (`certbot renew` every
12h) so renewal is automatic — nothing further to schedule.

Until this has been run, `DJANGO_DEBUG=False` alone does **not** force HTTPS
or mark cookies `Secure`, so login keeps working over plain HTTP in the
meantime.

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
- **S3/object storage for `MEDIA_ROOT`** — dedicated-instance-per-customer
  (§1, resolved) means this is lower priority than it looked originally: each
  customer's disk is already isolated, so there's no urgent multi-tenant
  reason to move off it. Revisit if a customer's data volume genuinely
  outgrows local disk. Uploaded files (Document Control, P2-F) still live on
  local disk / the `media_files` volume.
- **A real deploy step in CI** — `.github/workflows/docker-build.yml` only
  builds the image to catch a broken Dockerfile on every PR. Deploying is a
  per-customer VPS operation (see the checklist above), not a single CI
  target, given the dedicated-instance model.
- **fail2ban / deeper SSH hardening** — `scripts/provision_vps.sh` covers
  key-only SSH + a firewall; anything past that is real security-review
  territory (Phase 3), not provisioning.

These map to Phases 3–4 of the original deployment scoping document, not
gaps in this phase.
