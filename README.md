# CREW v10 — History, Leaderboards & Profiles

CREW is a privacy-first Flask games portal with a Monday–Thursday weekly cadence:

- **Mystery Monday** — solve a mystery from progressively easier clues
- **Trivia Tuesday** — ten-question daily challenge
- **Wordle Wednesday** — one shared five-letter puzzle
- **Tick-Tock Thursday** — stop a hidden timer close to the target

Each live-week game is worth up to 100 points for a 400-point weekly maximum.

## New in v10

### Functional leaderboard

`/leaderboard` now supports instant filters for:

- This Week
- Last Week
- This Month
- All Time
- All Games
- Mystery Monday
- Trivia Tuesday
- Wordle Wednesday
- Tick-Tock Thursday

The leaderboard includes a top-three podium, full standings, a pinned current-player row, completion counts, and game-specific context such as Mystery clue efficiency, Trivia accuracy, Wordle win/guess averages, and Tick-Tock timing deviation.

### Game archive

`/games` is now a week-by-week game archive. Players can review completed challenges and play games they missed.

Historical fairness rule:

> A game completed after its competitive week is saved to personal history, but never changes that old week's leaderboard, competitive points, or streak.

The database migration adds a `competitive` flag to `game_completions` to preserve this distinction. CREW game-day boundaries use `America/New_York` by default so the weekly cadence follows Orlando/Eastern time rather than the VPS UTC clock.

### Profile management

Clicking the player name/avatar opens `/profile`.

Players can:

- change their preset avatar
- change their password
- regenerate their recovery code
- see live vs archive completion totals

The **CREW name remains unique and permanent** after account creation.

## Privacy-first profiles

Player accounts require only a CREW name, preset avatar, password, and registration invitation code. CREW does not ask for a real name, work email, employee ID, phone number, department, job title, or Microsoft identity.

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

Local development defaults to SQLite.

## Content Studio

Open `/admin` and use the configured `CREW_ADMIN_PASSWORD`. The editor supports Draft → Preview → Publish for all four games.

## Production

CREW is designed for the isolated VPS stack already in use:

`Nginx → /run/crew/crew.sock → Gunicorn → Flask → crew_prod PostgreSQL`

The production deployment remains isolated from other apps through its own Linux user, app directory, database/role, systemd service, socket, Nginx host, and secrets file.

For an existing v9 production install, use **`deploy/V10_UPGRADE.md`**.
