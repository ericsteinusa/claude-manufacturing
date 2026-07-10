#!/bin/sh
set -eu

# Restores a backup produced by backup_db.sh.
#
# DESTRUCTIVE: this overwrites existing data in the target database. Never
# point this at a database you don't intend to fully overwrite — there is no
# confirmation prompt beyond the pause below, by design, so this can still be
# scripted.

: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=company_db}"
: "${DB_USER:=postgres}"

IN_FILE="${1:?usage: restore_db.sh <backup-file.sql.gz> [--yes]}"
CONFIRM="${2:-}"

echo "About to restore ${IN_FILE} into ${DB_NAME}@${DB_HOST}:${DB_PORT}."
echo "This overwrites existing data in that database."
if [ "$CONFIRM" != "--yes" ]; then
  echo "Ctrl+C now to abort, or re-run with --yes to skip this pause."
  sleep 5
fi

gunzip -c "$IN_FILE" | PGPASSWORD="${DB_PASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
echo "Restore complete."
