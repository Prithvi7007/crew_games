#!/usr/bin/env bash
set -euo pipefail
umask 077

set -a
# shellcheck disable=SC1091
source /etc/crew/crew.env
set +a

BACKUP_DIR=/var/backups/crew
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"
pg_dump --format=custom --no-owner --no-privileges "$DATABASE_URL" > "$BACKUP_DIR/crew_${STAMP}.dump"
find "$BACKUP_DIR" -type f -name 'crew_*.dump' -mtime +14 -delete
