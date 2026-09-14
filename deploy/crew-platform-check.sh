#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${CREW_BACKUP_DIR:-/var/backups/crew}"
CERT="/etc/letsencrypt/live/cadacrew.fun/fullchain.pem"

for service in crew nginx postgresql; do
  if [[ $(systemctl is-active "$service") != "active" ]]; then
    echo "CREW platform check failed: $service is not active" >&2
    exit 1
  fi
done

curl --silent --show-error --fail --max-time 8 \
  --unix-socket /run/crew/crew.sock \
  -H 'Host: cadacrew.fun' \
  http://localhost/health/ready >/dev/null

ROOT_USE=$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
if (( ROOT_USE >= 90 )); then
  echo "CREW platform check failed: root filesystem is ${ROOT_USE}% full" >&2
  exit 1
fi

LATEST=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'crew_*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)
if [[ -z "$LATEST" ]]; then
  echo "CREW platform check failed: no database backup found" >&2
  exit 1
fi
NOW=$(date +%s)
MTIME=$(stat -c %Y "$LATEST")
if (( NOW - MTIME > 129600 )); then
  echo "CREW platform check failed: newest backup is older than 36 hours" >&2
  exit 1
fi

if [[ ! -r "$CERT" ]] || ! openssl x509 -checkend 604800 -noout -in "$CERT" >/dev/null; then
  echo "CREW platform check failed: TLS certificate missing or expires within 7 days" >&2
  exit 1
fi

echo "CREW platform check passed: disk=${ROOT_USE}% backup=$(basename "$LATEST")"
