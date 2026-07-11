#!/bin/sh
set -eu

# Run once per customer, from the repo root on their VPS, once DNS for their
# domain already points at this box and `docker compose up -d` is running
# with the Phase 1 HTTP-only nginx/app.conf.
#
#   ./scripts/setup_tls.sh example-customer.com ops@yourcompany.com
#
# Handles the standard certbot bootstrap order: nginx must already be serving
# plain HTTP (for the HTTP-01 challenge) before a cert can be issued, and
# nginx can't serve HTTPS until that cert exists — so this obtains the cert
# first, against the existing HTTP-only config, then swaps in the TLS config
# afterward.

DOMAIN="${1:?usage: setup_tls.sh <domain> <email>}"
EMAIL="${2:?usage: setup_tls.sh <domain> <email>}"

echo "=== Requesting a certificate for ${DOMAIN} ==="
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$EMAIL" --agree-tos --non-interactive

echo "=== Switching nginx to the TLS-enabled config ==="
cp nginx/app.conf "nginx/app.conf.pre-tls.bak"
sed "s/DOMAIN/${DOMAIN}/g" nginx/app-ssl.conf.template > nginx/app.conf
docker compose restart nginx

echo "=== Enabling Django's HTTPS enforcement ==="
if grep -q '^DJANGO_HTTPS_ENABLED=' .env; then
  sed -i 's/^DJANGO_HTTPS_ENABLED=.*/DJANGO_HTTPS_ENABLED=True/' .env
else
  echo 'DJANGO_HTTPS_ENABLED=True' >> .env
fi
docker compose restart web

echo
echo "=== Done ==="
echo "https://${DOMAIN}/ should now be serving over TLS, with automatic"
echo "renewal handled by the long-running 'certbot' compose service."
echo "Previous HTTP-only config saved as nginx/app.conf.pre-tls.bak."
