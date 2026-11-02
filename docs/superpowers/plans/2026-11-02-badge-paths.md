# Badge Achievement Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement the user's selected third design in the existing Badges page.

**Architecture:** Keep the existing catalog, badge artwork and save APIs. Replace
large direct-equip cards with inspectable medal paths and one shared action area.
Remove obsolete collection CSS while preserving shared badge/avatar/toast rules.

**Tech Stack:** React 18, existing CSS, Flask APIs, Vite; no new dependencies.

**Spec:** docs/superpowers/specs/2026-11-02-badge-paths-design.md

## Global Constraints

- Preserve existing BadgeMedallion and EquippedProfileBadge artwork.
- No badge rules, backend routes, migrations, or dependencies change.
- Actual earned award IDs own equip state; private preview never grants awards.
- Existing artifact bounds: player.js <= 450000 bytes, player.css <= 250000 bytes.

## Review Focus

- Locked medals can be inspected without enabling a mutation.
- Switching category always displays details for a visible medal.
- Cross-season badges with equal codes remain distinct by award ID.
- Save failures and pending saves preserve an intelligible, recoverable UI.
- Long names, mobile navigation, and the detail action remain reachable.

### Task 1: Collection interaction and visual layout

**Files:** TrophyRoom.jsx, styles/trophies.css, tests/test_trophy_direct_equip.py,
tests/test_trophy_collection_rows.py, tests/test_trophy_visual_polish.py,
tests/test_browser_smoke.py.

**Interfaces:** Consume existing badges, seasons, showcase, trophyPreview,
saveSlot(slot,awardId), and savePreview(code). Produce inspectable selection and
one guarded mutation action without changing persisted data contracts.

- [x] Update old card assertions and browser interactions for inspect-then-act.
- [x] Implement four mastery paths, category fallback, detail action, season and
  category persistence, and preview tools disclosure.
- [x] Replace collection CSS, preserving shared medallion/avatar/toast styling.
- [x] Run the production build and full pytest suite; fix any regressions.

### Task 2: Rendered verification and reviewable delivery

**Files:** design-qa.md; compiled player.js/player.css; temporary preview fixture
outside the repository.

**Interfaces:** Use the checked compiled bundle with synthetic payloads for
desktop/mobile visual inspection and safe fixture save/preview endpoints.

- [x] Render the actual compiled app through sites-preview and cloud browser.
- [x] Compare the approved image and rendered collection at matching content
  width; inspect all categories, locked selection, saves, seasons and preview.
- [x] Check mobile overflow, keyboard focus, long names and save failure states.
- [x] Record truthful visual QA findings and fix P0/P1/P2 issues.
- [x] Run independent spec/standards review, sync assets, and rerun required
  checks on the final fingerprint before commit/push and draft PR. The bridge
  enforces this final delivery gate; delivery metadata is recorded in the PR.
