# October 19, 2026 — CREW badge launch readiness

This document is an evidence-led **launch checklist**, not permission to change
live player records. Keep the CREW Games homepage and scoring logic unchanged.

## Verified in source and isolated tests

- [x] Public unlock is gated to **October 19, 2026, CREW America/New_York date**
  by `app/trophy_access.py`. Players cannot open the collection or
  change showcases before that date; admin/owner previews remain possible.
- [x] The 21-badge catalog and rarity/game identity artwork are implemented.
- [x] Game completion awards are derived from **saved server-side evidence**,
  scoped to the scheduled game's season, permanent and idempotent. Awards
  do **not** grant score points. Championships are not awarded mid-season.
- [x] React Trophy Room shows real earned/locked states; equipping requires
  the player's saved award. Admin/owner try-ons do not create awards.
- [x] An admin's own Rankings row can show their private try-on; other viewers
  see only real equipped awards. Players with no ranked score may see their
  own expressly **unranked** preview row; no scores/ranks change.
- [x] Personalized four-step welcome tour, skip/finish persistence,
  session-only Maybe Later, replay, launch-gated access, fail-open
  behavior and reduced-motion handling have regression coverage.
- [x] Production dashboard reported healthy services and migration revision
  `v16_trophy_tour` as of October 14 (prior to this PR).

## Before enabling public access — operator/manual sign-off required

- [ ] **Real award inventory:** Read production `badge_awards` counts by
  season/code and reconcile against game completions. The restricted MCP
  read-only reporting gateway does **not** expose raw badge tables, so
  actual awarded totals could not be independently confirmed here.
- [ ] **Historical awards:** With approved operational access and no writes,
  run `flask --app app badges-backfill` **without `--apply`**. Preserve
  `completions_scanned`, `new_awards`, `by_badge`, review missing/contradictory
  attempts and compare to production saved awards. Do not infer a clean
  backfill from the existence of the command.
- [ ] If historical entitlements are missing, perform a separate reviewed,
  **explicitly authorized** `--apply` only after a fresh verified backup
  and dry-run review. Never run on merge or as a side effect of this PR.
- [ ] Before Oct 19, sign in with an admin/owner: verify genuine counts in
  `/trophies?trophy_tour_preview=1`; try every badge, clear preview,
  confirm only the viewer sees the private preview on Rankings (including
  when unranked), and confirm actual showcase choices are unchanged.
- [ ] Visually test mobile portrait, narrow desktop, keyboard navigation,
  Escape/focus return, reduced motion, and 0/earned-badge states.
- [ ] On Oct 19, with a consenting normal test player, confirm the tour
  appears on their first eligible page, showcases **only earned** badges,
  finishes exactly once across login sessions, and permits equipping in
  Trophy Room. Confirm an account with zero earned badges sees no fake
  unlocks. Recheck page navigation and gameplay unaffected.
- [ ] Verify system alerts/health and record rollback decision. If the
  optional tour fails, `TROPHY_TOUR_ENABLED=false` disables the tour
  independently of badges; do not downgrade the v16 database routinely.

## Follow-on (not part of the October 19 visibility launch)

The five season championship awards have catalog definitions and a
finalization storage table, but **no proven frozen end-of-season
winner-selection/finalization implementation** in this codebase.
Do not promise them as already awarded. Schedule a separate reviewed
design, tie-rule and eligibility process ahead of season-end.

## Evidence boundaries

This readiness check inspected the current CREW source, merged history and
live production health. Production's read-only database gateway responded to
a connectivity check but did **not** permit direct `badge_awards` or
`trophy_tour_completions` count queries. Therefore, neither the current
number of live awards nor historical backfill completion is asserted.
