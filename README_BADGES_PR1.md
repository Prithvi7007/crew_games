# CREW Season Badge Foundation — PR 1

This patch adds the **foundation only** for the approved 21 season-scoped badges.
It does not create visible UI, award badges automatically, modify game scores,
or finalize season championships.

## Approved catalog

- Game Mastery: 12 (three per game)
- Leaderboard & Rivalry: 6 (five season championships and High Roller)
- Secret: 1 (Unicorn)
- Collection: 2 (Badge Hunter, CREW Legend)

## Invariants

1. All awards are scoped by `profile_id + season_id + badge_code`.
2. Catch-up games belong to the season containing their *scheduled game date*.
3. Awards are permanent and idempotent; no points are granted.
4. One player may showcase up to three of their own earned badge awards.
5. The five season championships are **not** decided during game completion.
   Their official results must later be finalized using a frozen snapshot.
6. Game Mastery thresholds follow current game code. Stack all qualifying tiers.
7. High Roller requires four scheduled weekly scores totaling >= 350;
   Unicorn requires four 100-point scores totaling 400.
8. Badge Hunter requires 10 distinct non-collection badge types in one season;
   CREW Legend requires 15.
9. Award persistence (`app/badge_store.py`) is not wired to routes until PR 3.

## Future PRs

- PR 2: SVG components and seasonal Trophy Room React UI.
- PR 3: Server-triggered awarding, safe backfill, showcase, celebrations.
- PR 4: season ranking formulas, tie handling, minimum eligibility,
  explicitly frozen season winner snapshots and season champion awards.

## Rollout note

Apply migrations after a tested backup/restore rehearsal. Do not deploy
this patch directly to production or run historical backfills yet.
