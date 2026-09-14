#!/usr/bin/env bash
# Read-only VPS inventory. This script does not change the server.
set -u

echo '=== OS ==='
if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "${PRETTY_NAME:-unknown}"
fi

echo
echo '=== Python ==='
command -v python3 || true
python3 --version 2>/dev/null || true

echo
echo '=== Reverse proxies ==='
for svc in nginx apache2 httpd caddy; do
  if command -v "$svc" >/dev/null 2>&1; then echo "$svc: installed"; fi
  systemctl is-active "$svc" 2>/dev/null && echo "$svc: active" || true
done

echo
echo '=== Databases ==='
psql --version 2>/dev/null || true
mysql --version 2>/dev/null || true
systemctl is-active postgresql 2>/dev/null && echo 'postgresql: active' || true
systemctl is-active mysql 2>/dev/null && echo 'mysql: active' || true
systemctl is-active mariadb 2>/dev/null && echo 'mariadb: active' || true

echo
echo '=== Listening TCP sockets ==='
ss -ltn 2>/dev/null || true

echo
echo '=== Relevant running services ==='
systemctl --type=service --state=running --no-pager 2>/dev/null \
  | grep -Ei 'nginx|apache|caddy|gunicorn|uvicorn|postgres|mysql|maria|redis' || true
