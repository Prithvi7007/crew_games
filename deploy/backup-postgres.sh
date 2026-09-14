#!/usr/bin/env bash
set -euo pipefail
umask 077

set -a
# shellcheck disable=SC1091
source /etc/crew/crew.env
set +a

BACKUP_DIR="${CREW_BACKUP_DIR:-/var/backups/crew}"
RETENTION_DAYS="${CREW_BACKUP_RETENTION_DAYS:-14}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FINAL="$BACKUP_DIR/crew_${STAMP}.dump"
TEMP="$FINAL.tmp"
# shellcheck disable=SC1091
source /opt/crew/deploy/postgres-env.sh
crew_load_pg_env

install -d -m 0700 -o root -g root "$BACKUP_DIR"
trap 'rm -f "$TEMP"' EXIT

pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$TEMP" --dbname="$PGDATABASE"
pg_restore --list "$TEMP" >/dev/null
mv "$TEMP" "$FINAL"
sha256sum "$FINAL" > "$FINAL.sha256"
find "$BACKUP_DIR" -type f \( -name 'crew_*.dump' -o -name 'crew_*.dump.sha256' \) -mtime "+$RETENTION_DAYS" -delete

echo "CREW backup created: $FINAL"
