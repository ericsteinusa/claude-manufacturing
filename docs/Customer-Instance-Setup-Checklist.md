# New Customer Instance Setup Checklist

Provisioning a dedicated, self-hosted instance of the Manufacturing ERP for a
new customer. Steps 1–4 and 7 are automated by
[`scripts/linux/provision-customer.sh`](../scripts/linux/provision-customer.sh);
the rest need a human decision and are done by hand.

## Before you start

- [ ] DNS for the customer's domain already points at this server's public IP
      (certbot's HTTP-01 challenge fails otherwise).
- [ ] Port 80 and port 443 are reachable from the internet on this box.
- [ ] SSH access this box can use to clone the git repo already works
      (deploy key or a configured git credential helper).
- [ ] You have the customer's real company name, admin contact name, and
      admin email address on hand.

## Automated — run `provision-customer.sh`

Run as root, once, from the provisioning box:

```bash
sudo ./scripts/linux/provision-customer.sh <slug> <domain> <git-repo-url> <port> <admin-email>

# Example:
sudo ./scripts/linux/provision-customer.sh acme acme.yourdomain.com \
    git@github.com:you/claude-manufacturing.git 8101 you@yourdomain.com
```

Re-running against the same slug is safe — package installs, the system
user, the database role/db, and the systemd unit are all skipped if they
already exist; the repo checkout does a `git pull` instead of a fresh clone
if the directory is already there.

### Step 1 — Provision the server
- [ ] Install system packages: `python3`, `venv`, `pip`, `postgresql`, `nginx`, `certbot`, `git`.
- [ ] Create `/opt/customers` (if missing).
- [ ] Create a dedicated non-root system user `mfg-<slug>` (no login shell).

### Step 2 — Get the code onto the box
- [ ] Clone the repo into `/opt/customers/<slug>` (or `git pull` if already checked out).
- [ ] Create a Python virtualenv and install `requirements.txt`.

### Step 3 — Configure `.env` for this customer
- [ ] Generate a real random `DJANGO_SECRET_KEY` and DB password (never the dev-insecure fallback).
- [ ] Write `DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_PORT`, `DJANGO_DEBUG=False`,
      `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` for the domain.
- [ ] `DJANGO_HTTPS_ENABLED` is left unset until step 7's certificate is confirmed.

### Step 4 — Database
- [ ] Create the Postgres role and database for this customer.
- [ ] Run `manage.py migrate --noinput` (Django's own tables: sessions, auth, admin).
- [ ] No `manufacturing/seeds/seed_sample_*` script is run — a real customer's database
      starts empty except for their own data (see Step 6).

### Step 7 — Serve it for real
- [ ] Write and enable a systemd unit (`mfg-<slug>.service`) running
      `manage.py runserver` on `127.0.0.1:<port>`, `Restart=on-failure`.
- [ ] Write an nginx reverse-proxy config for the domain and reload nginx.
- [ ] Obtain a Let's Encrypt certificate via `certbot --nginx`; on success, flip
      `DJANGO_HTTPS_ENABLED=True` in `.env` and restart the service.
- [ ] If certbot fails, the site still serves over plain HTTP — check DNS and
      port 80, then re-run certbot manually.

## Manual — do these yourself, in order

### Step 5 — Bootstrap the first admin account

`cd` into the app directory first — `manage.py` finds `.env` relative to the
current working directory, not its own location:

```bash
cd /opt/customers/<slug>
sudo -u mfg-<slug> venv/bin/python manage.py create_admin \
    --email admin@<domain> --first-name <First> --last-name <Last>
```

- [ ] Grants a President-role account by default (pass `--role` to grant something else).
- [ ] If `--password` is omitted, a one-time generated password is printed to the
      terminal — hand it to the customer through a secure channel and have them
      change it on first login.

### Step 6 — Enter the customer's real company data
- [ ] Log in as the admin created in Step 5 and enter real departments,
      employees, products, customers, and suppliers — no seed/demo data is
      preloaded.

### Step 8 — Decide the update process for this instance
- [ ] Decide and record how this customer's instance will receive future code
      updates (e.g. the autopull pattern in
      [`scripts/linux/manufacture-autopull.sh`](../scripts/linux/manufacture-autopull.sh),
      or manual deploys) and document it for this customer.

### Step 9 — Verification walkthrough
- [ ] Log in at `https://<domain>/` over HTTPS and confirm the certificate is valid.
- [ ] Confirm `/healthz/` reports `status: ok`.
- [ ] Click through the main departments/dashboards the customer will actually use.
- [ ] Confirm no dev-only banners, sample data, or `@example.com` accounts are present.

### Step 10 — Set up backups
- [ ] Schedule [`scripts/backup_db.sh`](../scripts/backup_db.sh) (or equivalent)
      for this customer's database and confirm restore works with
      [`scripts/restore_db.sh`](../scripts/restore_db.sh) before considering
      the instance production-ready.
