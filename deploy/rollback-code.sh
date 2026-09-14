#!/usr/bin/env bash
set -euo pipefail

TARGET_SHA=${1:-}
if [[ -z "$TARGET_SHA" ]]; then
  echo "Usage: $0 <known-good-git-sha>" >&2
  exit 2
fi
if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

cd /opt/crew
if [[ -n $(git status --porcelain) ]]; then
  echo "Refusing rollback: /opt/crew has local changes." >&2
  exit 1
fi
if ! git cat-file -e "$TARGET_SHA^{commit}" 2>/dev/null; then
  echo "Commit $TARGET_SHA is not available locally. Fetch it first." >&2
  exit 1
fi

CURRENT=$(git rev-parse --short HEAD)
echo "Rolling CREW code back from $CURRENT to $TARGET_SHA"
git reset --hard "$TARGET_SHA"
chown -R crew:crew /opt/crew
systemctl restart crew
sleep 2
curl --silent --show-error --fail --max-time 8 \
  --unix-socket /run/crew/crew.sock \
  -H 'Host: cadacrew.fun' \
  http://localhost/health >/dev/null

echo "Code rollback completed. Database migrations were not downgraded."
