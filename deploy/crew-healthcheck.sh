#!/usr/bin/env bash
set -euo pipefail

response=$(curl --silent --show-error --fail --max-time 8 \
  --unix-socket /run/crew/crew.sock \
  -H 'Host: cadacrew.fun' \
  http://localhost/health/ready)

case "$response" in
  *'"status":"ok"'*) echo "$response" ;;
  *) echo "Unexpected CREW health response: $response" >&2; exit 1 ;;
esac
