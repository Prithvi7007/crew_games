# CREW Trophy Room launch tour — October 19, 2026

## Scope
One release PR: Alembic v16 persistence, Flask eligibility/CSRF endpoint, personalized award read, React four-step accessible tour, admin preview, replay, and regression tests. No changes to scores, awards, or game completion behavior.

## Launch rules
- Public date gate: `app.trophy_access.TROPHY_PUBLIC_REVEAL_DATE` in CREW's America/New_York timezone.
- First eligible visit after login on or after Oct 19, including users who arrive later; no forced redirect or interruption during an active game.
- Tour appears on home, games list, rankings, profile, or trophies. Game routes remain uninterrupted.
- **Maybe later** snoozes only for the current signed-in session. **Skip** and **Finish** persist once per player and tour key.
- Staff preview before launch: `/trophies?trophy_tour_preview=1` as admin/owner. Preview and Replay never write completion records.
- `TROPHY_TOUR_ENABLED=false` disables only the tour, not the Trophy Room.

## Production release safety
**This PR introduces a database migration. The code-only auto-release watcher must not be assumed to apply it.** A reviewed operator release must explicitly ensure:
1. GitHub CI and offline Python/React checks are green; merge only after review.
2. Take a verified PostgreSQL backup and confirm restore readiness.
3. Rehearse the additive `v15_badges -> v16_trophy_tour` migration against a backup/staging DB.
4. Upgrade production to `v16_trophy_tour` via the existing CREW Alembic migration procedure before exposing tour-capable code. Confirm the new table and current revision.
5. Deploy the merged commit using the established release procedure; verify `/health/ready`, login, trophy hold, admin preview and existing game routes.
6. Independently preview historical award backfill with `flask --app app badges-backfill`; **do not** apply automatically. Review evidence and take a backup before any approved `--apply` run.
7. Before Oct 19, verify the staff preview shows real badge counts, no fabricated awards, mobile layout, keyboard focus, Escape, reduced motion, and first-login behavior.
8. On Oct 19, verify one real player account with consent: initial tour, finish persistence, logout/login no replay, Trophy Room equip, and a player with zero awards.

## Failure/rollback
- Tour read failures are logged and fail open to normal gameplay; no game or login route depends on tour availability.
- To disable the feature immediately, set `TROPHY_TOUR_ENABLED=false` and restart the app through the approved operator process.
- Retain the additive v16 table when rolling back code; dropping it destroys completion history. Avoid a DB downgrade as a routine rollback.
- Do not run production migrations or backfill from the restricted development bridge; it does not have those privileges.
