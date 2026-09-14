#!/usr/bin/env bash
set -euo pipefail
umask 077

BACKUP_DIR="${CREW_BACKUP_DIR:-/var/backups/crew}"
VERIFY_DB="crew_restore_verify"
LATEST=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'crew_*.dump' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)

if [[ -z "${LATEST:-}" || ! -f "$LATEST" ]]; then
  echo "No CREW backup found in $BACKUP_DIR" >&2
  exit 1
fi

pg_restore --list "$LATEST" >/dev/null
if [[ -f "$LATEST.sha256" ]]; then
  sha256sum --check "$LATEST.sha256"
fi

cleanup() {
  runuser -u postgres -- dropdb --if-exists "$VERIFY_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
runuser -u postgres -- createdb "$VERIFY_DB"
runuser -u postgres -- pg_restore --exit-on-error --no-owner --no-privileges --dbname="$VERIFY_DB" "$LATEST"

PROFILE_TABLE=$(runuser -u postgres -- psql -d "$VERIFY_DB" -Atqc "SELECT to_regclass('public.profiles') IS NOT NULL")
if [[ "$PROFILE_TABLE" != "t" ]]; then
  echo "Restore verification failed: profiles table missing" >&2
  exit 1
fi

REVISION=$(runuser -u postgres -- psql -d "$VERIFY_DB" -Atqc "SELECT COALESCE((SELECT version_num FROM alembic_version LIMIT 1), 'unversioned')" 2>/dev/null || echo unversioned)
PROFILE_COUNT=$(runuser -u postgres -- psql -d "$VERIFY_DB" -Atqc "SELECT COUNT(*) FROM profiles")

echo "CREW restore verification passed: backup=$LATEST revision=$REVISION profiles=$PROFILE_COUNT"
