#!/bin/bash
# Provision a brand-new customer's dedicated instance of this app.
#
# Automates Customer-Instance-Setup-Checklist.md steps 1-4 and 7 (server
# provisioning, code checkout, .env, database + migrate, and
# systemd/nginx/TLS). Deliberately does NOT do:
#   - Step 5 (bootstrap the first admin) -- run `create_admin` yourself
#     once this script finishes, so you choose the customer's real name/
#     email interactively rather than baking it into a provisioning run.
#   - Step 6 (real company data), step 9 (verification walkthrough),
#     step 10 (backups) -- these need a human, not a script.
#
# Re-running against the same customer slug is mostly safe: package
# installs, the system user, the database role/db, and the systemd unit
# are all created idempotently (skipped if they already exist). The repo
# checkout does a `git pull` instead of a fresh clone if the directory is
# already there.
#
# Usage:
#   sudo ./provision-customer.sh <slug> <domain> <git-repo-url> <port> <admin-email>
#
# Example:
#   sudo ./provision-customer.sh acme acme.yourdomain.com \
#       git@github.com:you/claude-manufacturing.git 8101 you@yourdomain.com
#
# Prerequisites this script does NOT do for you:
#   - DNS for <domain> must already point at this server's public IP
#     (certbot's HTTP-01 challenge will fail otherwise).
#   - Port 80/443 must be reachable from the internet on this box.
#   - SSH access this box can use to clone <git-repo-url> (deploy key or
#     an already-configured git credential helper) must already work.

set -euo pipefail

# --- args --------------------------------------------------------------

if [ "$#" -ne 5 ]; then
    echo "Usage: sudo $0 <slug> <domain> <git-repo-url> <port> <admin-email>" >&2
    exit 1
fi

SLUG="$1"
DOMAIN="$2"
REPO_URL="$3"
PORT="$4"
ADMIN_EMAIL="$5"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root (sudo)." >&2
    exit 1
fi

if ! [[ "$SLUG" =~ ^[a-z][a-z0-9-]{1,30}$ ]]; then
    echo "ERROR: <slug> must be lowercase letters/digits/hyphens, starting with a letter (e.g. 'acme')." >&2
    exit 1
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
    echo "ERROR: <port> must be a number between 1024 and 65535." >&2
    exit 1
fi

SYS_USER="mfg-${SLUG}"
APP_DIR="/opt/customers/${SLUG}"
VENV_DIR="${APP_DIR}/venv"
DB_NAME="mfg_${SLUG}"
DB_USER="mfg_${SLUG}"
UNIT_NAME="mfg-${SLUG}.service"
ENV_FILE="${APP_DIR}/.env"

# settings.py's load_dotenv() finds .env relative to the CURRENT WORKING
# DIRECTORY, not the script's own location -- any manage.py invocation
# from this script has to `cd` into APP_DIR first or it silently picks up
# no .env at all (working, but against whatever DB the ambient
# environment happens to point at, which on this box is the dev database).
run_as_app_user() {
    sudo -u "${SYS_USER}" bash -c "cd '${APP_DIR}' && exec \"\$@\"" -- "$@"
}

echo "=== Provisioning customer '${SLUG}' ==="
echo "  domain:      ${DOMAIN}"
echo "  repo:        ${REPO_URL}"
echo "  app dir:     ${APP_DIR}"
echo "  system user: ${SYS_USER}"
echo "  database:    ${DB_NAME}"
echo "  port:        127.0.0.1:${PORT}"
echo "  systemd:     ${UNIT_NAME}"
echo

# =========================================================================
# Step 1 — provision the server
# =========================================================================
echo "==> Step 1: installing system packages"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    nginx certbot python3-certbot-nginx \
    git

mkdir -p /opt/customers
chown root:root /opt/customers

if ! id "${SYS_USER}" >/dev/null 2>&1; then
    echo "    creating non-root system user ${SYS_USER}"
    useradd --system --create-home --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${SYS_USER}"
else
    echo "    system user ${SYS_USER} already exists, skipping"
fi

# =========================================================================
# Step 2 — get the code onto the box
# =========================================================================
echo "==> Step 2: checking out the application"

if [ -d "${APP_DIR}/.git" ]; then
    echo "    ${APP_DIR} already a git checkout, pulling latest main"
    sudo -u "${SYS_USER}" git -C "${APP_DIR}" fetch origin main --quiet
    sudo -u "${SYS_USER}" git -C "${APP_DIR}" checkout main --quiet
    sudo -u "${SYS_USER}" git -C "${APP_DIR}" merge --ff-only origin/main --quiet
else
    echo "    cloning ${REPO_URL}"
    sudo -u "${SYS_USER}" git clone --quiet "${REPO_URL}" "${APP_DIR}"
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "    creating virtualenv"
    sudo -u "${SYS_USER}" python3 -m venv "${VENV_DIR}"
fi

echo "    installing Python dependencies"
sudo -u "${SYS_USER}" "${VENV_DIR}/bin/pip" install -q --upgrade pip
sudo -u "${SYS_USER}" "${VENV_DIR}/bin/pip" install -q -r "${APP_DIR}/requirements.txt"

# =========================================================================
# Step 3 — configure .env for this customer
# =========================================================================
echo "==> Step 3: writing .env"

if [ -f "${ENV_FILE}" ]; then
    echo "    ${ENV_FILE} already exists, leaving it as-is (delete it first to regenerate)"
else
    DB_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/')"
    SECRET_KEY="$(sudo -u "${SYS_USER}" "${VENV_DIR}/bin/python" -c \
        "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")"

    # DJANGO_HTTPS_ENABLED is deliberately left unset here -- turning it on
    # before certbot has actually obtained a certificate (step 7) would
    # force HTTPS redirects with no TLS listener behind them yet. Step 7
    # flips it on once the certificate is confirmed.
    cat > "${ENV_FILE}" <<EOF
DB_HOST=localhost
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_PORT=5432

DJANGO_DEBUG=False
DJANGO_SECRET_KEY=${SECRET_KEY}
DJANGO_ALLOWED_HOSTS=${DOMAIN}
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN}

LOG_LEVEL=INFO
EOF
    chown "${SYS_USER}:${SYS_USER}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo "    wrote ${ENV_FILE} (DB password and secret key generated, not printed)"
fi

# =========================================================================
# Step 4 — database
# =========================================================================
echo "==> Step 4: database setup"

DB_PASSWORD_FROM_ENV="$(grep -m1 '^DB_PASSWORD=' "${ENV_FILE}" | cut -d= -f2-)"

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
    echo "    role ${DB_USER} already exists, skipping"
else
    echo "    creating role ${DB_USER}"
    sudo -u postgres psql -c \
        "CREATE ROLE \"${DB_USER}\" WITH LOGIN PASSWORD '${DB_PASSWORD_FROM_ENV}';"
fi

if sudo -u postgres psql -lqt | cut -d '|' -f 1 | grep -qw "${DB_NAME}"; then
    echo "    database ${DB_NAME} already exists, skipping"
else
    echo "    creating database ${DB_NAME}"
    sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi

echo "    running migrations"
run_as_app_user "${VENV_DIR}/bin/python" manage.py migrate --noinput

# Deliberately NOT run: any manufacturing/seeds/seed_sample_*.py script.
# Those generate fake @example.com employees and demo data for local dev
# only -- a real customer's database should start empty except for their
# own real data (see checklist step 6, done by hand after this script).
echo "    (skipping dev seed scripts -- see checklist step 6 for real data entry)"

# =========================================================================
# Step 7 — serve it for real: systemd + nginx + TLS
# =========================================================================
echo "==> Step 7: systemd service"

cat > "/etc/systemd/system/${UNIT_NAME}" <<EOF
[Unit]
Description=Manufacturing ERP web server — customer: ${SLUG}
After=network.target postgresql.service

[Service]
Type=simple
User=${SYS_USER}
Group=${SYS_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python manage.py runserver 127.0.0.1:${PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}"

echo "    waiting for the app to come up on 127.0.0.1:${PORT}"
up=0
for _ in $(seq 1 20); do
    sleep 0.5
    if curl -s -o /dev/null "http://127.0.0.1:${PORT}/healthz/"; then
        up=1
        break
    fi
done
if [ "${up}" -ne 1 ]; then
    echo "    WARNING: app did not answer on 127.0.0.1:${PORT} within 10s -- check:"
    echo "      systemctl status ${UNIT_NAME}"
    echo "      journalctl -u ${UNIT_NAME} -n 50"
fi

echo "==> Step 7: nginx reverse proxy"

cat > "/etc/nginx/sites-available/${SLUG}.conf" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sfn "/etc/nginx/sites-available/${SLUG}.conf" "/etc/nginx/sites-enabled/${SLUG}.conf"
nginx -t
systemctl reload nginx

echo "==> Step 7: TLS certificate"

if certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos \
        -m "${ADMIN_EMAIL}" --redirect; then
    echo "    certificate obtained — enabling DJANGO_HTTPS_ENABLED"
    if grep -q '^DJANGO_HTTPS_ENABLED=' "${ENV_FILE}"; then
        sed -i 's/^DJANGO_HTTPS_ENABLED=.*/DJANGO_HTTPS_ENABLED=True/' "${ENV_FILE}"
    else
        echo "DJANGO_HTTPS_ENABLED=True" >> "${ENV_FILE}"
    fi
    systemctl restart "${UNIT_NAME}"
else
    echo "    WARNING: certbot failed — check that DNS for ${DOMAIN} already"
    echo "    points at this server's public IP and that port 80 is reachable"
    echo "    from the internet, then re-run:"
    echo "      certbot --nginx -d ${DOMAIN} --agree-tos -m ${ADMIN_EMAIL} --redirect"
    echo "    The site is still reachable over plain HTTP in the meantime."
fi

echo
echo "=== Done ==="
echo "Next steps (not automated by this script):"
echo "  1. Bootstrap the first admin account (cd first -- manage.py finds .env"
echo "     relative to the current directory, not its own location):"
echo "     cd ${APP_DIR} && sudo -u ${SYS_USER} ${VENV_DIR}/bin/python manage.py create_admin \\"
echo "         --email admin@${DOMAIN} --first-name <First> --last-name <Last>"
echo "  2. Log in at https://${DOMAIN}/ and walk through checklist step 9."
echo "  3. Set up backups (checklist step 10) — this script does not do that."
echo "  4. Decide + record the update process for this instance (checklist step 8)."
