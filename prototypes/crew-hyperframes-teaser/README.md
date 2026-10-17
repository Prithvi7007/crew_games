# CREW / HyperFrames cinematic teaser (isolated prototype)

**Status:** review-only motion prototype. Nothing in this folder is imported by Flask, Vite, templates, player UI, or the production release workflow.

## Creative brief

A 12-second, 1920 × 1080 (16:9) championship-themed teaser for the planned October 19, 2026 Trophy Room reveal.

- 0.0–3.75s — **Every Game. Every Legend.** A competitive opening with restrained CREW game colors.
- 3.1–8.15s — Illuminated **concept trophy**, concentric rings, and the CREW four-color motif.
- 7.6–12.0s — **CREW GAMES / THE TROPHY ROOM OPENS / OCTOBER 19, 2026** title finale.

The trophy illustration is **concept art**, not a copy of a player award or the canonical Trophy Room medallion. No real player, score, ranking, game answer, or unreleased badge is displayed.

## Preview / render

Requires **Node.js 22+**, **FFmpeg**, and access to the pinned GSAP dependency at `cdn.jsdelivr.net`. From this folder:

```bash
npx hyperframes preview
npx hyperframes lint
npx hyperframes check
npx hyperframes render --output crew-trophy-room-teaser.mp4
```

HyperFrames controls the playhead and clip visibility; GSAP registers a *paused, seekable* timeline as `window.__timelines.crewChampionshipTeaser`. No `setInterval`, `setTimeout`, random animation states, or browser-driven playback are used.

The MP4 is intentionally *silent*: soundtrack and sound effects require separate media review and licensing. GSAP is served by a pinned CDN only for this experimental prototype; a checked-in vendored dependency or local bundle is preferable for fully offline deterministic rendering.

## Release / review gates

1. Review storyboard, typography, motion, date, and actual visual render.
2. Validate the result with HyperFrames lint/check and inspect beginning/middle/end frames.
3. Get explicit approval of the teaser copy and visual direction. The date is an announcement **concept**, not an auto-published promise.
4. **Do not merge/deploy for automatic publication.** If approved, export and optimize the MP4 for deliberate placement in a future separate PR.

This folder is inert in the CREW application by design and does **not** flip `CINEMATIC_BADGE_UNLOCKS_ENABLED` or change the existing October 19 visibility gate.
