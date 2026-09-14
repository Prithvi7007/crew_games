# CREW v12 — Platform Engineering

CREW is a privacy-first Flask games portal with a Monday–Thursday weekly cadence:

- **Mystery Monday** — solve a mystery from progressively easier clues
- **Trivia Tuesday** — ten-question daily challenge
- **Wordle Wednesday** — one shared five-letter puzzle
- **Tick-Tock Thursday** — stop a hidden timer close to the target

Each live game is worth up to 100 points. v12 keeps the v11 security model and v10 product experience while upgrading the engineering underneath them.

## New in v12

### Database lifecycle and integrity

- Alembic becomes the source of truth for schema migrations
- existing v11 databases are safely stamped at the v11 baseline before upgrading
- six player-owned data tables gain relational `profile_id` links to `profiles.id`
- PostgreSQL compatibility triggers keep v11 code rollback-safe while v12 is in the expand phase
- database checks enforce valid game keys, completion flags, score ranges and Content Studio states
- leaderboard/game-history indexes are added around competitive/date/game/profile access patterns
- SQLite enables foreign-key enforcement for local development
- database connection-pool sizing/timeouts are explicit in production
- UTC timestamps are now generated from timezone-aware Python datetime values without changing the rollback-compatible storage format

### Performance

- leaderboard point/completion aggregation moves into SQL rather than loading every completion into Python
- joins use indexed relational `profile_id` columns instead of string concatenation such as `profile:12`
- common game/content/security lookup indexes are included in the migration

### Observability

- application logs are single-line structured JSON
- Nginx `X-Request-ID` values are propagated through Flask responses/logs
- request status and duration are logged without adding new personal profile data
- `/health/live` provides liveness
- `/health/ready` validates database readiness
- `/health` remains compatible with existing production checks

### Reliability and operations

- daily PostgreSQL backups are written atomically and checksum-verified
- a weekly job performs a **real restore** into a disposable PostgreSQL database
- a local readiness systemd timer probes CREW every five minutes
- an hourly platform check watches service health, disk pressure, backup freshness and TLS expiry
- failed operational checks emit high-priority `crew-alert` events into journald via a systemd `OnFailure` hook
- a migration-rehearsal script restores the latest backup into a scratch DB and applies v12 before production is touched
- a code-only rollback helper can return the application to a recorded known-good commit

### CI quality gate

GitHub Actions now runs:

- pytest
- Python compilation
- critical Ruff checks
- JavaScript syntax checks
- shell syntax checks
- Alembic upgrade/downgrade/upgrade smoke testing
- `pip-audit` dependency scanning

## Preserved v11 security controls

v12 retains database-backed authentication rate limits, session revocation, CSP, Trusted Hosts, admin-session hardening, optional TOTP, security audit events, hardened systemd/Nginx configuration and security-event retention cleanup.

CREW still stores no employee email, real name, employee ID, phone number or Microsoft identity.

## Local development

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m flask --app run.py db-upgrade
pytest -q
python run.py
```

Local development uses SQLite by default. Alembic automatically creates/upgrades the local schema when `AUTO_DB_MIGRATE=true`.

## Production

CREW remains isolated as:

`cadacrew.fun → Nginx → /run/crew/crew.sock → Gunicorn → Flask → crew_prod PostgreSQL`

**Do not migrate production directly after copying v12.** Follow `deploy/V12_UPGRADE.md`. The required sequence includes a fresh backup and a migration rehearsal against a restored clone of `crew_prod` before the live database upgrade.
