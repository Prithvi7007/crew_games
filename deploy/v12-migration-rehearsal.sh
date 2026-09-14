#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this rehearsal as root." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source /etc/crew/crew.env
set +a

BACKUP_DIR="${CREW_BACKUP_DIR:-/var/backups/crew}"
TEST_DB="crew_v12_migration_test"
DB_ROLE="${CREW_DB_ROLE:-crew_app}"
LATEST=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'crew_*.dump' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)

if [[ -z "${LATEST:-}" || ! -f "$LATEST" ]]; then
  echo "No CREW backup found. Run crew-backup.service first." >&2
  exit 1
fi

cleanup() {
  runuser -u postgres -- dropdb --if-exists "$TEST_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
runuser -u postgres -- createdb --owner="$DB_ROLE" "$TEST_DB"
# Load the application role connection without exposing its password in argv.
# shellcheck disable=SC1091
source /opt/crew/deploy/postgres-env.sh
crew_load_pg_env
PROD_DATABASE="$PGDATABASE"
export PGDATABASE="$TEST_DB"

# Restore through the application role so restored objects have the same owner
# and migration permissions as production.
pg_restore --exit-on-error --no-owner --no-privileges --dbname="$PGDATABASE" "$LATEST"

# Build the scratch URL from DATABASE_URL without placing credentials in a
# command argument, then preserve only the three variables the migration CLI
# needs when dropping privileges to the CREW application user.
TEST_URL=$(/opt/crew/.venv/bin/python - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

raw = os.environ["DATABASE_URL"]
parts = urlsplit(raw)
print(urlunsplit((parts.scheme, parts.netloc, "/crew_v12_migration_test", parts.query, parts.fragment)))
PY
)
export DATABASE_URL="$TEST_URL" CREW_ENV=development AUTO_DB_MIGRATE=false

cd /opt/crew

runuser -u crew -g www-data \
  --whitelist-environment=DATABASE_URL,CREW_ENV,AUTO_DB_MIGRATE \
  -- /opt/crew/.venv/bin/flask --app run.py db-integrity-check

runuser -u crew -g www-data \
  --whitelist-environment=DATABASE_URL,CREW_ENV,AUTO_DB_MIGRATE \
  -- /opt/crew/.venv/bin/flask --app run.py db-upgrade

# Restore parent libpq state for any later shell diagnostics.
export PGDATABASE="$PROD_DATABASE"

REVISION=$(runuser -u postgres -- psql -d "$TEST_DB" -Atqc "SELECT version_num FROM alembic_version")
FK_COUNT=$(runuser -u postgres -- psql -d "$TEST_DB" -Atqc "SELECT COUNT(*) FROM pg_constraint WHERE contype='f' AND conname LIKE 'fk_%_profile_id_profiles'")
NULL_LINKS=$(runuser -u postgres -- psql -d "$TEST_DB" -Atqc "SELECT COUNT(*) FROM game_completions WHERE profile_id IS NULL")

if [[ "$REVISION" != "v12_platform" || "$FK_COUNT" -lt 6 || "$NULL_LINKS" != "0" ]]; then
  echo "v12 migration rehearsal failed: revision=$REVISION profile_fks=$FK_COUNT null_completion_links=$NULL_LINKS" >&2
  exit 1
fi

echo "v12 migration rehearsal passed: revision=$REVISION profile_fks=$FK_COUNT"
