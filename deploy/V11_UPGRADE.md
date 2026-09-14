# CREW v9/v10 → v11 production upgrade

These steps are for the isolated CREW production install at `/opt/crew` on `cadacrew.fun`. They do not modify the wedding application or `wedding_db`.

## 1. Test and push locally first

On Windows in the CREW project:

```powershell
python -m compileall app
git status
git add .
git commit -m "CREW v11 security and integrity"
git push origin main
```

For the full v11 checks locally:

```powershell
pip install -r requirements-dev.txt
pytest -q
pip-audit -r requirements.txt
```

## 2. Snapshot the CREW database before the migration

On the VPS:

```bash
sudo mkdir -p /var/backups/crew
sudo -u postgres pg_dump -Fc crew_prod > /var/backups/crew/crew_prod_pre_v11_$(date +%Y%m%d_%H%M%S).dump
ls -lh /var/backups/crew | tail
```

## 3. Pull v11

```bash
cd /opt/crew
GIT_SSH_COMMAND="ssh -i /root/.ssh/crew_github -o IdentitiesOnly=yes" git pull --ff-only origin main
chown -R crew:crew /opt/crew
sudo -u crew /opt/crew/.venv/bin/pip install -r /opt/crew/requirements.txt
```

## 4. Update required production environment values

v11 requires explicit trusted hosts and a 12-character minimum player password policy. Existing player password hashes remain valid; the longer rule applies when creating/changing/recovering an account.

```bash
grep -q '^TRUSTED_HOSTS=' /etc/crew/crew.env || echo 'TRUSTED_HOSTS=cadacrew.fun,www.cadacrew.fun' >> /etc/crew/crew.env
grep -q '^PASSWORD_MIN_LENGTH=' /etc/crew/crew.env || echo 'PASSWORD_MIN_LENGTH=12' >> /etc/crew/crew.env
grep -q '^PASSWORD_MAX_LENGTH=' /etc/crew/crew.env || echo 'PASSWORD_MAX_LENGTH=128' >> /etc/crew/crew.env
grep -q '^ADMIN_SESSION_HOURS=' /etc/crew/crew.env || echo 'ADMIN_SESSION_HOURS=4' >> /etc/crew/crew.env
chmod 640 /etc/crew/crew.env
```

Do not print `/etc/crew/crew.env` into chat or logs.

## 5. Upgrade the CREW database

```bash
sudo -u crew -g www-data bash -c '
set -a
source /etc/crew/crew.env
set +a
cd /opt/crew
.venv/bin/flask --app run.py db-upgrade
'
```

Expected: `CREW database schema is up to date.`

Verify only CREW's DB:

```bash
sudo -u postgres psql -d crew_prod -c "\d profiles"
sudo -u postgres psql -d crew_prod -c "\dt security_*"
```

`profiles` should include `session_version`, and the two security tables should exist.

## 6. Optional but strongly recommended: enable admin TOTP

Generate the secret after the v11 pull and environment update:

```bash
sudo -u crew -g www-data bash -c '
set -a
source /etc/crew/crew.env
set +a
cd /opt/crew
.venv/bin/flask --app run.py generate-admin-totp
'
```

Save the Base32 secret in an authenticator/password manager. Add it to `/etc/crew/crew.env` as:

```text
CREW_ADMIN_TOTP_SECRET=<the generated Base32 secret>
```

Then keep the env file at `root:www-data` / mode `640`.

## 7. Install the hardened CREW systemd unit and restart only CREW

Back up the current CREW unit, then install the v11 unit. This does not touch the wedding service.

```bash
cp /etc/systemd/system/crew.service /etc/systemd/system/crew.service.pre-v11
cp /opt/crew/deploy/crew.service /etc/systemd/system/crew.service
systemd-analyze verify /etc/systemd/system/crew.service
systemctl daemon-reload
systemctl restart crew
systemctl status crew --no-pager
curl --unix-socket /run/crew/crew.sock -H 'Host: cadacrew.fun' http://localhost/health
```

Expected health response:

```json
{"status":"ok"}
```

The existing wedding systemd service is not restarted.

### Enable daily security-state retention cleanup

```bash
cp /opt/crew/deploy/crew-security-cleanup.service /etc/systemd/system/crew-security-cleanup.service
cp /opt/crew/deploy/crew-security-cleanup.timer /etc/systemd/system/crew-security-cleanup.timer
systemctl daemon-reload
systemctl enable --now crew-security-cleanup.timer
systemctl list-timers crew-security-cleanup.timer --no-pager
```

This deletes expired limiter buckets and pseudonymous security events older than 90 days. It does not touch gameplay/history tables.

## 8. Install CREW-only Nginx edge throttling

Back up only the CREW site, install the v11 template, validate the complete Nginx configuration, and reload only if validation succeeds:

```bash
cp /etc/nginx/sites-available/crew /etc/nginx/sites-available/crew.pre-v11
cp /opt/crew/deploy/nginx-crew.conf /etc/nginx/sites-available/crew
nginx -t && systemctl reload nginx
```

The template adds modest IP throttles to CREW authentication endpoints as defense in depth. It does not edit `/etc/nginx/sites-available/wedding`.

## 9. Verify through HTTPS

```bash
curl -I https://cadacrew.fun/login
curl https://cadacrew.fun/health
```

Confirm the browser can:

1. sign in as an existing player
2. open Home/Games/Leaderboard/Profile
3. change an avatar
4. play one current/archive game
5. sign into `/admin` (plus TOTP if enabled)

A password change should keep that browser signed in but invalidate another browser's prior session.

## Rollback

If the app is unhealthy after restart:

```bash
cd /opt/crew
git log --oneline -5
git checkout <previous-good-commit>
systemctl restart crew
```

The v11 schema additions are additive/backward-compatible with the v9/v10 schema, so an application-code rollback does not require immediately dropping the added columns/tables.
