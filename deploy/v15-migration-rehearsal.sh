#!/usr/bin/env bash
# CREW v15: migration rehearsal against the verified checkpoint; never live DB.
set -Eeuo pipefail
umask 077
[[ "$EUID" == 0 ]] || { echo "STOP: requires the host operations service." >&2; exit 1; }

PROD=/opt/crew
STAGE=/opt/crew-v15-rehearsal
SOURCE=/var/backups/crew/crew_20261010T001254Z.dump
BACKUP=/var/backups/crew/release-checkpoints/pre_v15_20261010T001254Z.dump
TEST_DB=crew_v15_migration_test

exec 9>/run/lock/crew-v15-migration-rehearsal.lock
flock -n 9 || { echo "STOP: rehearsal already running." >&2; exit 1; }

[[ "$(runuser -u crew -g www-data -- git -C "$PROD" rev-parse HEAD)" == c5a9275629ba4389c2b66a14b61a523868d40673 ]] || {
  echo "STOP: production commit changed." >&2; exit 1;
}
[[ -z "$(runuser -u crew -g www-data -- git -C "$PROD" status --porcelain)" ]] || {
  echo "STOP: production checkout dirty." >&2; exit 1;
}
[[ "$(git -C "$STAGE" rev-parse HEAD)" == f4a35026d1df0e86e987d4bca310b8d32aed4134 ]] || {
  echo "STOP: staging is not the approved release." >&2; exit 1;
}
[[ -z "$(git -C "$STAGE" status --porcelain)" ]] || {
  echo "STOP: staging checkout dirty." >&2; exit 1;
}
grep -q '^revision = "v15_badges"$' "$STAGE/alembic/versions/v15_badges.py"
grep -q '^down_revision = "v14_seasons"$' "$STAGE/alembic/versions/v15_badges.py"

[[ -f "$SOURCE" && -f "$SOURCE.sha256" && -f "$BACKUP" ]] || {
  echo "STOP: missing approved recovery checkpoint or original checksum." >&2; exit 1;
}
sha256sum --status --check "$SOURCE.sha256" || {
  echo "STOP: checksum failed." >&2; exit 1;
}
cmp -s "$SOURCE" "$BACKUP" || {
  echo "STOP: release checkpoint does not match the verified backup." >&2; exit 1;
}
pg_restore --list "$BACKUP" >/dev/null

# Root must never source code from the crew-writable application directory.
# Only the root-owned configuration file is sourced; URL decoding is performed
# with trusted system Python (never /opt/crew/.venv/bin/python as root).
ENV_FILE=/etc/crew/crew.env
[[ ! -L "$ENV_FILE" && -f "$ENV_FILE" ]] || {
  echo "STOP: unsafe environment file." >&2; exit 1;
}
[[ "$(stat -c %u "$ENV_FILE")" == 0 ]] || {
  echo "STOP: environment file is not root-owned." >&2; exit 1;
}
case "$(stat -c %a "$ENV_FILE")" in
  600|640|400|440) ;;
  *) echo "STOP: environment file permissions are unsafe." >&2; exit 1 ;;
esac
[[ ! -L /etc/crew && "$(stat -c %u /etc/crew)" == 0 ]] || {
  echo "STOP: environment directory is not root-owned." >&2; exit 1;
}
DIR_MODE=$(stat -c %a /etc/crew)
(( (8#$DIR_MODE & 8#022) == 0 )) || {
  echo "STOP: environment directory is group/world-writable." >&2; exit 1;
}
set -a
# shellcheck disable=SC1091
source "$ENV_FILE"
set +a
mapfile -d '' -t pg_parts < <(/usr/bin/python3 - <<'PY'
import os
import sys
from urllib.parse import unquote, urlsplit
raw = os.environ.get("DATABASE_URL", "")
for old in ("postgresql+psycopg://", "postgres://"):
    if raw.startswith(old):
        raw = "postgresql://" + raw[len(old):]
parsed = urlsplit(raw)
database = unquote(parsed.path.lstrip("/"))
if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.username or not database:
    raise SystemExit("STOP: invalid PostgreSQL URL")
for part in (parsed.hostname, str(parsed.port or 5432),
             unquote(parsed.username), unquote(parsed.password or ""), database):
    sys.stdout.write(part + "\0")
PY
)
[[ "${#pg_parts[@]}" == 5 ]] || {
  echo "STOP: could not load database connection." >&2; exit 1;
}
export PGHOST="${pg_parts[0]}" PGPORT="${pg_parts[1]}"
export PGUSER="${pg_parts[2]}" PGPASSWORD="${pg_parts[3]}" PGDATABASE="${pg_parts[4]}"
unset pg_parts

case "$PGHOST" in
  localhost|127.0.0.1|::1|/var/run/postgresql|/run/postgresql) ;;
  *) echo "STOP: remote PostgreSQL is not supported." >&2; exit 1 ;;
esac
[[ "$PGDATABASE" == crew_prod && "$PGPORT" == 5432 ]] || {
  echo "STOP: unsafe production database name." >&2; exit 1;
}

# The postgres admin commands always use a LOCAL socket, never the app's
# inherited PGUSER/PGPASSWORD/PGDATABASE environment.
pg_admin() {
  runuser -u postgres -- env -u PGHOST -u PGPORT -u PGUSER -u PGPASSWORD -u PGDATABASE "$@"
}
scratch_sql() {
  pg_admin psql -X -v ON_ERROR_STOP=1 -d "$TEST_DB" -Atqc "$1"
}
existing=$(pg_admin psql -X -d postgres -Atqc \
  "SELECT count(*) FROM pg_database WHERE datname = '$TEST_DB'")
[[ "$existing" == 0 ]] || {
  echo "STOP: scratch DB already exists; refusing to overwrite it." >&2; exit 1;
}

created=0
cleanup() {
  result=$?
  trap - EXIT
  if [[ "$created" == 1 ]]; then
    pg_admin dropdb "$TEST_DB" >/dev/null || {
      echo "WARNING: scratch DB cleanup failed." >&2
      result=1
    }
  fi
  exit "$result"
}
trap cleanup EXIT

DB_ROLE="${CREW_DB_ROLE:-crew_app}"
[[ "$DB_ROLE" == "$PGUSER" ]] || {
  echo "STOP: app database role does not match restore role." >&2; exit 1;
}
[[ "$DB_ROLE" =~ ^[a-z_][a-z_0-9]*$ ]] || {
  echo "STOP: invalid application role." >&2; exit 1;
}
pg_admin createdb --owner="$DB_ROLE" "$TEST_DB"
created=1
export PGDATABASE="$TEST_DB"
pg_restore --exit-on-error --no-owner --no-privileges \
  --dbname="$TEST_DB" "$BACKUP"

before_revision=$(scratch_sql "SELECT version_num FROM alembic_version")
[[ "$before_revision" == v14_seasons ]] || {
  echo "STOP: source backup revision is not v14_seasons." >&2; exit 1;
}
COUNTS_SQL="SELECT (SELECT count(*) FROM profiles)::text || ':' ||
 (SELECT count(*) FROM game_completions)::text || ':' ||
 (SELECT count(*) FROM mystery_attempts)::text || ':' ||
 (SELECT count(*) FROM trivia_attempts)::text || ':' ||
 (SELECT count(*) FROM word_attempts)::text || ':' ||
 (SELECT count(*) FROM tick_tock_attempts)::text || ':' ||
 (SELECT count(*) FROM user_stats)::text || ':' ||
 (SELECT count(*) FROM seasons)::text"
before_counts=$(scratch_sql "$COUNTS_SQL")

# Construct a scratch-only SQLAlchemy URL, keeping credentials out of argv.
TEST_URL=$(/usr/bin/python3 - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit
parsed = urlsplit(os.environ["DATABASE_URL"])
if parsed.scheme not in ("postgresql", "postgresql+psycopg", "postgres"):
    raise SystemExit("STOP: invalid PostgreSQL URL")
if parsed.path.lstrip("/") in ("", "postgres", "crew_v15_migration_test"):
    raise SystemExit("STOP: invalid production database")
print(urlunsplit((parsed.scheme, parsed.netloc, "/crew_v15_migration_test",
                  parsed.query, parsed.fragment)))
PY
)
export DATABASE_URL="$TEST_URL" CREW_ENV=development AUTO_DB_MIGRATE=false

cd "$STAGE"
runuser -u crew -g www-data \
  --whitelist-environment=DATABASE_URL,CREW_ENV,AUTO_DB_MIGRATE \
  -- "$PROD/.venv/bin/flask" --app app db-integrity-check
runuser -u crew -g www-data \
  --whitelist-environment=DATABASE_URL,CREW_ENV,AUTO_DB_MIGRATE \
  -- "$PROD/.venv/bin/flask" --app app db-upgrade

after_revision=$(scratch_sql "SELECT version_num FROM alembic_version")
after_counts=$(scratch_sql "$COUNTS_SQL")
tables=$(scratch_sql "SELECT count(*) FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name IN
  ('badge_awards', 'badge_showcase', 'season_badge_finalizations')")
[[ "$after_revision" == v15_badges && "$before_counts" == "$after_counts" && "$tables" == 3 ]] || {
  echo "STOP: migration result or saved-record counts do not match." >&2; exit 1;
}
echo "CREW v15 rehearsal passed: revision=v15_badges prior_counts_unchanged=yes badge_tables=3"
echo "Scratch database will be removed. Production database was not migrated."
