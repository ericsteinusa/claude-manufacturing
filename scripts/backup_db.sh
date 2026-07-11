#!/bin/sh
set -eu

# Dumps the database configured via the same DB_* env vars manufacture/
# settings.py and docker-compose.yml already use, to a timestamped,
# gzip-compressed file. Hosting-agnostic: works against the docker-compose
# `db` service (`docker compose exec web ./scripts/backup_db.sh`) or any
# future managed Postgres instance without changes.

: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=company_db}"
: "${DB_USER:=postgres}"

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT_FILE="$OUT_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "Backing up ${DB_NAME}@${DB_HOST}:${DB_PORT} to ${OUT_FILE} ..."
PGPASSWORD="${DB_PASSWORD:-}" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    | gzip > "$OUT_FILE"
echo "Done: ${OUT_FILE}"
