# CREW v11 — Security & Integrity

CREW is a privacy-first Flask games portal with a Monday–Thursday weekly cadence:

- **Mystery Monday** — solve a mystery from progressively easier clues
- **Trivia Tuesday** — ten-question daily challenge
- **Wordle Wednesday** — one shared five-letter puzzle
- **Tick-Tock Thursday** — stop a hidden timer close to the target

Each live-week game is worth up to 100 points for a 400-point weekly maximum. v11 keeps the v10 leaderboard, game archive and profile experience and hardens the account/content platform underneath them.

## New in v11

### Authentication and account integrity

- database-backed failure rate limiting shared across Gunicorn workers
- separate limits for player login, recovery, profile creation, profile password changes and Content Studio login
- constant-work password/recovery checks reduce account-enumeration timing differences
- password/passphrase minimum increased to 12 characters by default
- password changes and account recovery increment a server-side `session_version`, revoking older signed-in sessions
- successful password changes automatically refresh the current browser into the new session version
- security-sensitive pages send `Cache-Control: no-store`
- security audit events store keyed hashes rather than raw usernames/IP addresses

### Content Studio hardening

- admin sessions are now cryptographically tied to the current admin password; rotating the password revokes old admin sessions
- admin sessions expire independently after 4 hours by default
- database-backed admin login rate limiting
- optional RFC 6238 TOTP second factor with no additional runtime package
- stricter plain-text length validation for Mystery/Trivia editor content

Enable admin TOTP with:

```bash
flask --app run.py generate-admin-totp
```

Add the printed secret to `CREW_ADMIN_TOTP_SECRET` in the production environment, add the secret to an authenticator/password manager, then restart CREW.

### Browser security

- nonce-based Content Security Policy for scripts
- `frame-ancestors 'none'`, `object-src 'none'`, restrictive `form-action`, `connect-src` and `base-uri`
- Cross-Origin-Opener-Policy and Cross-Origin-Resource-Policy headers
- stricter Permissions-Policy
- Mystery, Trivia, Tick-Tock and Leaderboard clients no longer render dynamic content with `innerHTML`
- production requires explicit `TRUSTED_HOSTS`

### Security schema

`db-upgrade` adds:

- `profiles.session_version`
- `security_rate_limits`
- `security_events`

No player email, real name, employee ID, phone number or Microsoft identity is introduced.

## Existing v10 product features

- filtered leaderboard: week/month/all-time + per-game rankings
- game-specific leaderboard statistics
- week-by-week historical game archive
- archive plays that cannot rewrite historical competitive results
- profile management for avatar/password/recovery code
- immutable unique CREW names
- America/New_York game-day boundaries
- Content Studio Draft → Preview → Publish workflow

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

Local development defaults to SQLite and auto-upgrades the local schema.

## Security test suite

```bash
pip install -r requirements-dev.txt
pytest -q
pip-audit -r requirements.txt
```

The v11 suite includes rate-limit, CSP, session-revocation, legacy-admin-session and DOM-injection regression checks.

## Production

CREW remains designed for the isolated VPS stack:

`Nginx → /run/crew/crew.sock → Gunicorn → Flask → crew_prod PostgreSQL`

The production deployment stays isolated through its own Linux user, app directory, PostgreSQL role/database, systemd service, Unix socket, Nginx host and secrets file.

For the live v9/v10 install on `cadacrew.fun`, follow **`deploy/V11_UPGRADE.md`** before restarting the service. The database upgrade is backward-compatible with the currently deployed v9 schema.
