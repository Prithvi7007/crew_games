# Champion Animation Preview Implementation Plan

**Goal:** Let admins and owners preview the Season 01 champion and all four game champion animations before finalization.
**Architecture:** Add a pure demo-story builder, gated behind the existing staff-only Saga preview. Reuse the current winner and badge components, with an always-visible demo label and a title selector.
**Tech Stack:** Flask, React, Motion, existing CREW CSS and badge catalog.

## Design
- Extend /rewind?preview=1&prototype=1&story=5 with champion=all|season|trivia|word|mystery|tick_tock.
- Show only the selected champion title and official badge animation, or all five pairs in sequence.
- Reject demo requests outside the explicit admin/owner Saga preview, including requests by normal players after finalization.
- The demo replaces only the response's seasonSaga. It never changes real championship flags, scores, badge collections, snapshots, ranks, or database rows.
- Keep a visible animation-demo label, title selector, and existing playback/replay/exit controls.
- Use the same titles, badges, colors, and animation components as the real winner flow.

## Alternatives
- Reusing the existing staff Saga preview is the smallest supported route and preserves its access controls.
- A standalone demo app would duplicate animations and drift from the actual player experience.
- Finalizing championships or granting badges to preview was rejected because a visual preview requires no competition changes.

## Task 1: Read-only gated demo story
- [x] Add route tests covering five titles, the combined sequence, invalid selections, staff roles, player denial, finalized public behavior, cross-player previews, and unchanged database state.
- [x] Run tests and confirm failures are due to missing demo behavior.
- [x] Add app/rewind_champion_preview.py and the staff-only route selection.
- [x] Verify the existing full Python suite and the new tests pass.

## Task 2: Preview controls and delivery
- [x] Add a persistent demo notice and native accessible title selector to the current cinema.
- [x] Add responsive CREW-themed styles; preserve playback and replay.
- [x] Build frontend assets and sync matching verified outputs.
- [x] Review the final diff, run required checks, and open a draft PR.

## Verification record
- Baseline: 542 passed, 26 skipped.
- New route tests failed first for missing demo payload/access checks (15 failed; existing tests remained green).
- Implemented route/builder: 559 passed, 28 skipped; React production build passed.
- Standards review and spec review found no blocking issues. The demo evidence footer was clarified following review.
- Desktop/mobile Playwright smoke coverage was added for selection, title/badge rendering, replay, layout, and the demo evidence notice.
- Browser execution remains unverified in this environment: Chromium was absent, the browser download failed, and the remote browser could not reach the local fixture.
- Final matching-fingerprint pytest and React build checks are required after syncing compiled assets.
