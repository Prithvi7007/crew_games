# CREW v9 → v10 production upgrade

This upgrade does not require changes to the wedding application, its database, its Nginx site, or its systemd service.

## 1. Push v10 from the development machine

After testing locally:

```powershell
git add .
git commit -m "CREW v10 leaderboard archive and profile"
git push origin main
```

## 2. Pull on the VPS

```bash
cd /opt/crew
GIT_SSH_COMMAND="ssh -i /root/.ssh/crew_github -o IdentitiesOnly=yes" git pull --ff-only origin main
chown -R crew:crew /opt/crew
```

## 3. Take a quick database backup

```bash
sudo -u postgres pg_dump --format=custom crew_prod > /root/crew_prod_pre_v10.dump
```

This touches only `crew_prod`.

## 4. Install dependencies

No new v10 dependencies are currently required, but keeping this step makes upgrades repeatable:

```bash
sudo -u crew /opt/crew/.venv/bin/pip install -r /opt/crew/requirements.txt
```

## 5. Run the database migration

```bash
sudo -u crew -g www-data bash -c '
set -a
source /etc/crew/crew.env
set +a
cd /opt/crew
.venv/bin/flask --app run.py db-upgrade
'
```

The migration adds `game_completions.competitive` with a default of `1`, so existing completions remain competitive.

## 6. Restart CREW only

```bash
systemctl restart crew
systemctl status crew --no-pager
```

## 7. Verify

```bash
curl --unix-socket /run/crew/crew.sock http://localhost/health
```

Expected:

```json
{"status":"ok"}
```

Then open:

- `https://cadacrew.fun`
- `https://cadacrew.fun/games`
- `https://cadacrew.fun/leaderboard`
- `https://cadacrew.fun/profile`

Static asset URLs include a v10 cache-busting query string so the new CSS/JS is fetched immediately even if Nginx has long-lived static caching.
