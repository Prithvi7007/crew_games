# CREW Badge Awards + Showcase — PR 9

This increment builds on merged v15 badge schema (PR 7) and Trophy Room (PR 8).

## Awarding

- Every completed Mystery/Trivia/Word/Tick-Tock game calls the shared
  `safe_award_completion` hook **after** its attempt and game completion
  are saved by the server. In-progress games do not award badges.
- Evaluation reads persisted attempt rows and matching `game_completions`
  records; client-supplied scores or badge codes are never trusted.
- Eligible game mastery badges stack; four complete games scheduled in one
  season week can award High Roller (350+/400) or Unicorn (400/400).
- Collection medals count distinct eligible non-collection badge codes
  **within the same season**.
- Each badge is unique per (profile, season, code). Archive games use their
  original scheduled date, and do not repair a streak or add badge points.
- The five season championships are NOT granted here; those require the
  separate frozen end-of-season snapshot planned for a later PR.

## Trophy Room

- Shows saved unlocks and an optional result-page celebration for newly
  awarded medals only.
- Players can add, replace, or clear three showcase slots via
  POST `/api/trophies/showcase`. Requires authenticated session and CSRF.
- The server validates slot number and ownership of saved `awardId`.
  Selecting another player's award or duplicating an award across slots
  returns a validation error.
- A showcase can retain medals from previous seasons.

## Historical badge backfill — not automatic

```sh
flask --app app badges-backfill
flask --app app badges-backfill --profile-id 123
# Only after backup, rehearsal, and confirmation of dry-run results:
flask --app app badges-backfill --apply
```

Dry-run previews without writes. `--apply` uses saved completed attempts,
does not change scores, is idempotent, and never grants season championship
medals. A game with missing or contradictory attempt/completion evidence
is excluded from preview or rejected during apply; investigate those records
before operating on a live database. Backfill must be planned around
migration, backup and restore rehearsal; do NOT execute on production as
part of merging this PR.

## Verification

- Offline bridge pytest: 143 passed
- Offline bridge React/Vite: passed
- GitHub quality gate must also pass, including committed frontend assets
- No automatic deployment or production DB migration
