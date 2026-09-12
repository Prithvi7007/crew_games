# CREW v9 — Deployment Ready

CREW is a privacy-first Flask games portal with a Monday–Thursday weekly cadence:

- **Mystery Monday** — solve a mystery from progressively easier clues
- **Trivia Tuesday** — ten-question daily challenge
- **Wordle Wednesday** — one shared five-letter puzzle
- **Tick-Tock Thursday** — stop a hidden timer close to the target

Each game is worth up to 100 points for a 400-point weekly maximum. CREW includes pseudonymous player profiles, recovery codes, weekly scoring/leaderboards, and the Content Studio for drafting, previewing, and publishing weekly content.

## Privacy-first profiles

Player accounts require only a CREW name, preset avatar, password, and the registration invitation code. The app does not ask for a real name, work email, employee ID, phone number, department, job title, or Microsoft identity. Passwords and recovery codes are stored as hashes. The readable one-time recovery display is encrypted before being placed in the temporary Flask session and expires after five minutes.

## Local development

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`. Local development defaults to SQLite. Copy `.env.example` to `.env` if you want to set your own development secrets.

## Content Studio

Open `/admin` and use the configured `CREW_ADMIN_PASSWORD`. The editor supports Draft → Preview → Publish for all four games. Published content locks once the first player starts that dated challenge. Optional IP/theme labels are blank by default and should only be used when the actual content is intentionally themed.

## Production changes in v9

- PostgreSQL support through SQLAlchemy + psycopg
- production configuration validation (CREW refuses to start with placeholder secrets or SQLite)
- explicit `flask --app run.py db-upgrade` schema command
- Gunicorn production server
- secure session-cookie defaults for HTTPS
- CSRF protection for forms and game JSON requests
- reverse-proxy awareness through `ProxyFix`
- trusted-host validation
- `/health` database health endpoint
- branded 400 / 404 / 500 pages
- security response headers
- isolated VPS systemd + Nginx templates
- Nginx login/admin rate limiting
- optional isolated PostgreSQL backup timer
- `.gitignore` for local secrets, SQLite data, venvs, and bytecode

## VPS deployment

This package is designed to coexist safely with another application on the same VPS. CREW uses its own Linux user, application directory, virtual environment, PostgreSQL database/role, systemd unit, Unix socket, reverse-proxy host, secrets file, and backup directory.

**Start with `deploy/VPS_DEPLOYMENT.md`.** Run `deploy/preflight.sh` before making server changes so the existing app's reverse proxy and database setup can be confirmed. The preflight script is read-only.

Because this deployment is a fresh CREW install, there is no SQLite/profile migration step.
