#!/bin/sh
set -eu

# One-time bootstrap for a fresh Ubuntu 22.04/24.04 VPS (DigitalOcean/Hetzner/
# Linode default) — one of these per customer, per the dedicated-instance
# decision. Run once as root, right after the box is created:
#
#   ssh root@new-vps-ip 'bash -s' < scripts/provision_vps.sh
#
# Idempotent where practical (safe to re-run), except the SSH-hardening step
# is deliberately ordered last and behind a real check, since a mistake there
# can lock out the operator permanently.

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this as root (fresh VPS bootstrap only)." >&2
  exit 1
fi

DEPLOY_USER="${DEPLOY_USER:-deploy}"

echo "=== Creating ${DEPLOY_USER} user ==="
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  usermod -aG sudo "$DEPLOY_USER"
fi

echo "=== Copying root's authorized_keys to ${DEPLOY_USER} ==="
# Aborts here (before the SSH-hardening step below) if root has no key on
# file — proceeding would disable both password and root login with no way
# back in.
if [ ! -s /root/.ssh/authorized_keys ]; then
  echo "root has no authorized_keys — add your SSH public key to" >&2
  echo "/root/.ssh/authorized_keys before running this script." >&2
  exit 1
fi
mkdir -p "/home/${DEPLOY_USER}/.ssh"
cp /root/.ssh/authorized_keys "/home/${DEPLOY_USER}/.ssh/authorized_keys"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
chmod 700 "/home/${DEPLOY_USER}/.ssh"
chmod 600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"

echo "=== Installing Docker Engine + Compose plugin ==="
# The distro-packaged docker.io lags behind the Compose v2 syntax already
# used in docker-compose.yml — install from Docker's own apt repo instead.
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  . /etc/os-release
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
usermod -aG docker "$DEPLOY_USER"

echo "=== Enabling automatic OS security updates ==="
apt-get install -y -qq unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "=== Configuring firewall (ufw) ==="
apt-get install -y -qq ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "=== Hardening SSH (key-only, no root login) ==="
sed -i \
  -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
  -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
  /etc/ssh/sshd_config
# Validate before restarting — a bad config here would otherwise only be
# discovered on the next SSH attempt, with no way back in.
sshd -t
systemctl restart ssh

echo
echo "=== Done ==="
echo "Log back in as ${DEPLOY_USER} (root/password login are now disabled):"
echo "  ssh ${DEPLOY_USER}@<this-host>"
echo "Then, as ${DEPLOY_USER}:"
echo "  git clone <repo-url> && cd manufacture"
echo "  cp .env.example .env  # fill in DB_PASSWORD, DJANGO_SECRET_KEY, etc."
echo "  docker compose up -d --build"
echo "  ./scripts/setup_tls.sh <customer-domain>"
