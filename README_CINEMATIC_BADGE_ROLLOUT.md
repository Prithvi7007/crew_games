# CREW cinematic badge unlocks — guarded integration

The approved single-badge V2 and multi-badge V3 cinematic component is reused for real, **newly saved server-awarded** badge codes. This is a UI-only integration. Scores, saved completions, award rules, and season records remain unchanged.

## Safe default

- `CINEMATIC_BADGE_UNLOCKS_ENABLED=false` (the default in `config.py`) keeps the original game-result badge celebration intact for all players, even after this PR is merged.
- The existing October 19, 2026 trophy visibility gate continues to block normal players from seeing new badges or the cinematic before launch.
- Staff/admin can test **genuine** saved unlocks with `?cinematic_unlock_test=1` on the relevant game page while the global flag is disabled. This only changes their own render path; it does not award test badges or alter completed games.
- The existing `/trophies?unlock_preview=1` remains a safe, read-only animation lab.
- The live cinema uses the same real `BadgeMedallion` visual assets; it is a dismissible, keyboard-accessible modal with a Continue button, Escape support, focus restoration, and reduced-motion support.
- For 4+ simultaneous unlocks, the three highest-rarity badges occupy the stage, while **all** award names are listed in the finale. The count always reflects the complete server return.

## Verified launch procedure

1. Merge the integration PR **without** changing `CINEMATIC_BADGE_UNLOCKS_ENABLED`. Deploy with the verified CREW release agent, preserving the prior results UI.
2. Verify normal scores and badge totals remain unchanged; ensure login, result navigation, the admin animation lab, and existing Trophy Room still work.
3. On an isolated consenting staff test account, begin an unplayed qualifying game page with `?cinematic_unlock_test=1`, earn a **genuinely new** badge, and confirm one cinematic plus correct badge collection persistence.
4. Test Common, Rare/Epic, multiple badges, mobile portrait/landscape, Escape, Continue, focus restoration, and reduced-motion. Revisit the same completed game and confirm no new cinema appears.
5. After public Trophy Room reveal and a real normal-player tour smoke test on October 19, explicitly opt in to `CINEMATIC_BADGE_UNLOCKS_ENABLED=true` through the approved operator environment procedure and restart the service. Keep the flag false if any issue remains.
6. If there is trouble after enabling, revert the config to `false` and restart: the existing in-results celebration is restored; no database rollback is needed.

No production feature-flag change is part of this PR.
