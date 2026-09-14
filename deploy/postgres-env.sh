#!/usr/bin/env bash
# Shared PostgreSQL environment loader for CREW operational scripts.
# Reads DATABASE_URL from the environment and exports libpq variables so
# database credentials never need to appear in command-line arguments.

crew_load_pg_env() {
  local python_bin="${CREW_PYTHON_BIN:-/opt/crew/.venv/bin/python}"
  local -a parts=()

  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "DATABASE_URL is not set" >&2
    return 1
  fi
  if [[ ! -x "$python_bin" ]]; then
    echo "CREW Python runtime not found: $python_bin" >&2
    return 1
  fi

  mapfile -d '' -t parts < <(
    "$python_bin" - <<'PY'
import os
import sys
from urllib.parse import unquote, urlsplit

raw = os.environ.get("DATABASE_URL", "")
if raw.startswith("postgresql+psycopg://"):
    raw = "postgresql://" + raw[len("postgresql+psycopg://"):]
elif raw.startswith("postgres://"):
    raw = "postgresql://" + raw[len("postgres://"):]

parsed = urlsplit(raw)
if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.username:
    raise SystemExit("DATABASE_URL must be a PostgreSQL URL with host and username")

database = unquote(parsed.path.lstrip("/"))
if not database:
    raise SystemExit("DATABASE_URL must include a database name")

values = (
    parsed.hostname,
    str(parsed.port or 5432),
    unquote(parsed.username),
    unquote(parsed.password or ""),
    database,
)
for value in values:
    sys.stdout.write(value)
    sys.stdout.write("\0")
PY
  )

  if (( ${#parts[@]} != 5 )); then
    echo "Unable to parse DATABASE_URL" >&2
    return 1
  fi

  export PGHOST="${parts[0]}"
  export PGPORT="${parts[1]}"
  export PGUSER="${parts[2]}"
  export PGPASSWORD="${parts[3]}"
  export PGDATABASE="${parts[4]}"
  export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
}
