# Championship celebration polish

Request: make the season champion animation more celebratory using Motion Animation.
Base: 62ba40ab2dc58fa8bf4314e02faae73fcd1dd26d (PR #130).

The existing player-name, title and real-badge staging remains the story.
A halo builds behind the badge, a short burst from both lower sides marks the
title reveal at 2850 ms, and the badge settles with a slight overshoot and a
single light sweep. The badge close-up uses a smaller burst at 1100 ms.
Season champions use CREW gold; game champions retain their game accent.

All effects derive from the chapter's elapsed MotionValue with useTransform.
There are no effect timers, autonomous CSS animations, random render values,
new dependencies, audio or changes to chapter duration, results, awards or
staff preview access. Decorative layers are hidden from assistive technology,
ignore pointer input and clip particles inside the stage. Particle count is
bounded at 36 for the winner and 18 for the badge.

Reduced motion renders a static halo, with no particles, badge bounce or sheen.
Manual paused visits and early completion use the existing readable chapter
stills. Resuming and replaying reset through the existing chapter clock.

A stronger title burst on the shared clock is the chosen approach. Independent
confetti timers would risk the pause regressions already fixed in Rewind;
replacing the real badge or changing the story would lose the player's identity.

Validation: retain the existing playback regressions and full Python suite,
build and sync the React production bundle, then rerun both checks for the final
fingerprint. Browser scenarios cover desktop/mobile confetti start, pause/resume,
replay, overflow and reduced motion. Browser rendering requires provisioned
Chromium; report whether it ran separately from Python/build results.

Motion Animation's live search was used before implementation. This host exposes
no reader for its motion:// links; the matching official public pages were read:
- https://motion.dev/docs/react-use-transform
- https://motion.dev/docs/react-accessibility
