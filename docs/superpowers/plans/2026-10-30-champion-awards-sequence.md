# Championship Awards Sequence Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the champion opening around the four-part sequence accepted in chat.
**Architecture:** Keep the chapter's elapsed MotionValue as the only animation clock.
Masked heading reveals, converging lights and a coordinated title/badge impact replace
the side-by-side introduction. The existing badge close-up continues the story.
**Tech Stack:** React 18.3.1, Motion 14.6.0, existing CREW CSS.
**Spec:** The user accepted anticipation, player name, title/badge impact, then hold
and transition into Rewind. The public Editorial stagger hero is visual inspiration;
no paid source or Motion+ dependency will be used.

## Global Constraints
- Winner chapter remains 9800 ms; badge close-up remains 8200 ms.
- Preserve player names, real championship badges, exact title text, provisional
  labels, all five championship types, combined previews and access/results/awards.
- Preserve pause, resume, hidden-tab suspension, still navigation and replay.
- Reduced motion presents a complete static composition with no lights or confetti.
- Reuse installed motion/react; all effects read the supplied chapter time.

## Review Focus
- Long player names must wrap within desktop/mobile stage space.
- A paused first visit must remain readable and restart its staged reveal on Play.
- Title and badge must land together without revealing them on the neutral cover.
- Rapid replay must wait for all outgoing chapters before counting new effects.
- Staff preview controls and small/short screens must remain usable.

## Task 1: Rebuild the opening
Files: frontend/src/player/ChampionReveal.jsx,
frontend/src/player/ChampionTheater.jsx (new),
frontend/src/player/ChampionCelebration.jsx,
app/static/css/rewind-saga.css.

- [ ] Add a clock-driven masked heading component and converging-light backdrop.
- [ ] Center name, title and badge in a responsive awards composition.
- [ ] Schedule name at 1100 ms, title at 2100 ms, badge at 2600 ms,
      impact/confetti at 3150 ms, readable result at 4200 ms, signoff at 5600 ms.
- [ ] Move the halo into the badge so its position follows responsive badge layout.
- [ ] Preserve close-up, exact title semantics and reduced-motion stills.
- [ ] Build and inspect the changed source.

## Task 2: Verify and deliver
Files: tests/test_browser_smoke.py, checked app/static/react/player.js.

- [ ] Extend existing browser regressions to cover masked headings and lights in
      paused snapshots, complete reduced-motion stills and a long player name.
- [ ] Run React build and sync its checked outputs.
- [ ] Run final pytest and React build on the packaged fingerprint.
- [ ] Review standards and request coverage, fix material findings, create draft PR.
- [ ] Report browser verification separately from build/test success.

## Execution decisions
- A chapter entered while already paused uses the existing complete, readable still.
  Pausing active playback freezes the exact current frame, including a partly
  revealed heading. Forcing the heading open on Pause would expose unrevealed
  content and make resume jump; the existing clock contract remains authoritative.
- Browser coverage is authored but cannot run without provisioned Chromium.
  Source review does not establish perceived timing or short-screen vertical fit.
