# CREW gameplay polish — staff-only preview

This design pass covers all four **in-progress** game screens and the transition into completed results. It is intentionally preview-gated so player gameplay is unchanged until visual approval.

## What changed

- One shared compact mission-header hierarchy across Mystery Monday, Trivia Tuesday, Wordle Wednesday and Tick-Tock Thursday, replacing oversized 4–6rem titles.
- Consistent game card surfaces, visual focus, restrained scoring panels, improved spacing and clearer back navigation.
- Mystery clue cards and answer field fit naturally in the first viewport; clue copy stays readable, reveal action remains obvious.
- Trivia puts the question and answer options first, with a tighter progress line and touch-size choices. Correct/wrong feedback, keyboard shortcuts and score logic remain unchanged.
- Wordle prioritizes the 5×6 board and keyboard, preserves color-state accessibility cues and scoring, and reduces wasted height.
- Tick-Tock emphasizes the target, timer and Stop action, preserving timing semantics and keyboard support.
- Compact responsive styling for portrait phones and small screens, focus rings, and reduced-motion support.
- On transition from an active round to results, React resets inherited scroll position before paint. The legacy badge celebration sits over the artwork half of the desktop results stage instead of pushing the score card below the fold; smaller viewports use a compact inline card.

## Preview access

After a reviewed merge and deployment, an **owner or admin** can view the redesigned active game by adding `gameplay_preview=1` to any game URL. Examples:

- `/mystery?date=2026-10-12&gameplay_preview=1`
- `/trivia?date=2026-10-13&gameplay_preview=1`
- `/word?date=2026-10-14&gameplay_preview=1`
- `/tick-tock?date=2026-10-08&gameplay_preview=1`

Use an **unplayed** game for inspecting its active gameplay screen; an already completed game correctly displays results instead. Dates are examples and must be eligible/playable for that account.

Remove the query parameter to compare with the existing UI. The flag never bypasses game scheduling, locks, scoring, saved attempts or badge permissions. Normal players cannot enable the preview.

## Release/review procedure

1. PR and production deployment do not enable the new game layouts for regular players; the cosmetic preview is server-gated to owner/admin plus an explicit query parameter.
2. Check four active states plus result states on desktop (1440×900, 1280×720), tablet and mobile (390×844, 320×700), with long clue/question strings, full keyboard, narrow phones and enlarged text.
3. Verify focused keyboard navigation, onscreen word keyboard, clue reveal, answer feedback, real points, trophy-award route and results after completion.
4. Confirm returning to an already completed round shows no new badge animation. Preview the cinematic separately through the existing owner-only opt-in.
5. After design sign-off, a **separate** implementation can make the new gameplay layout the default; this PR does not remove the opt-in gate.

This PR does not modify any award computation, user accounts, scoring, persistence models, or gameplay endpoints.
