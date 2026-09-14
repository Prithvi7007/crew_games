# CREW v12 Platform Engineering upgrade

v12 is a platform release. It does not add a new game. It replaces ad-hoc schema upgrades with Alembic, adds relational profile keys and database constraints/indexes, structured request logging, readiness/liveness probes, CI quality gates, verified backups, and a code rollback path.

## Safety model

The production migration follows an **expand-compatible** strategy:

- existing `user_key` columns remain in place;
- v12 adds `profile_id` foreign keys and writes both identifiers;
- PostgreSQL compatibility triggers populate `profile_id` if the v11 application is temporarily rolled back;
- existing timestamp columns remain in their v11 storage format so a code rollback stays safe;
- no game/content/profile data is intentionally deleted.

Do not remove the compatibility columns/triggers in the same release. That is a later contract migration after v12 has proven stable.

## Before production

1. Run the full local test suite.
2. Commit and push v12.
3. On the VPS, take a fresh CREW-only PostgreSQL backup.
4. Pull v12 code without restarting the running v11 Gunicorn process.
5. Install `requirements.txt` (adds Alembic).
6. Install/run the v12 backup service once.
7. Run `deploy/v12-migration-rehearsal.sh`. It restores the latest backup into a temporary PostgreSQL database, migrates that clone, verifies the revision/FKs, then drops the clone.
8. Only after the rehearsal passes, run the production `db-upgrade`.
9. Restart CREW and run readiness/security/regression checks.

## Local validation

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m flask --app run.py db-upgrade
python -m flask --app run.py db-revision
pytest -q
python run.py
```

Expected revision:

```text
v12_platform
```

## Production migration commands

Use the dedicated GitHub deploy key when fetching. Take a fresh backup before these steps.

```bash
cd /opt/crew
sudo -u crew /opt/crew/.venv/bin/pip install -r /opt/crew/requirements.txt
```

Run the data-integrity preflight against production **before** migration:

```bash
sudo -u crew -g www-data bash -c '
set -a
source /etc/crew/crew.env
set +a
cd /opt/crew
.venv/bin/flask --app run.py db-integrity-check
'
```

Then rehearse against a restored clone:

```bash
bash /opt/crew/deploy/v12-migration-rehearsal.sh
```

Only if that reports `v12 migration rehearsal passed`, migrate production:

```bash
sudo -u crew -g www-data bash -c '
set -a
source /etc/crew/crew.env
set +a
cd /opt/crew
.venv/bin/flask --app run.py db-upgrade
.venv/bin/flask --app run.py db-revision
'
```

Restart and verify:

```bash
systemctl restart crew
curl --unix-socket /run/crew/crew.sock -H 'Host: cadacrew.fun' http://localhost/health/ready
```

## Operations units

Copy and enable these only after validating them with `systemd-analyze verify`:

- `crew-backup.service` / `.timer` — daily atomic PostgreSQL custom-format backup
- `crew-restore-verify.service` / `.timer` — weekly real restore into a scratch database
- `crew-healthcheck.service` / `.timer` — five-minute local readiness probe
- `crew-platform-check.service` / `.timer` — hourly service/disk/backup/TLS checks
- `crew-ops-failure@.service` — high-priority journald signal for failed operational units

The four v12 operational services use the failure hook. This gives the VPS a durable local alert signal; routing those events to an external pager/email provider is intentionally a separate integration decision. The existing v11 security cleanup timer remains enabled.

## Rollback

Record the pre-v12 Git SHA before deployment. v12 keeps compatibility fields/triggers specifically so the previous v11 code can be used as an emergency application rollback without immediately downgrading the database.

```bash
bash /opt/crew/deploy/rollback-code.sh <PRE_V12_SHA>
```

That helper rolls back **code only**. It never restores/downgrades the production database automatically. Database restore is a separate deliberate incident-recovery action.
