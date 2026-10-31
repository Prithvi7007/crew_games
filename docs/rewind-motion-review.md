# Season Rewind motion update

Request: review and update the Season Rewind with the Motion Animation plugin.
Base: 18b8fb062fcc182b56745667b4f4d2ff1682fcbc (main).

## Findings

- Weekly paths, metric entrances, trophy staggers and points-share segments run
  independently of the player's pause state.
- The game spotlight uses its own interval. Pausing restarts that interval;
  selecting a game changes the spotlight without moving the chapter deadline.
- The initially inspected version had 750 ms blurred exits and entrances. The
  refreshed main branch already uses a 580 ms directional crossfade. This update
  uses shorter overlapping exits/entrances and removes scaling to keep text clear.
- The points-share chart animates flex proportions, so intermediate geometry
  temporarily represents a different mix of scores.

## Implementation

Use the installed Motion 14.6 React APIs. Keep the CREW theme, earned badges,
player identity, exact score geometry and all existing access/award rules.

1. Give each mounted chapter one elapsed MotionValue. Derive chart/reveal styles
   from it; use an application timer with the same remaining duration to advance.
2. Stop both on pause, evidence disclosure, hidden tabs, outgoing presence and
   unmount. Resume the remaining duration. Ignore cancelled callbacks.
3. Derive the comparison spotlight from chapter time. Selecting a game seeks that
   same clock; a paused/reduced-motion selection shows its complete values.
4. Keep manual navigation while paused readable. Reduced motion is static and
   manually advanced, including the first champion and the final badge.
5. Replace full-frame blur/scale with a 180 ms exit and 320 ms opacity/translation
   entry with continuous directional crossfades. Keep the background and controls mounted.
6. Reveal fixed final points-share geometry with transforms. Drive champion
   staging, weekly paths, metrics, podiums and trophy entrances from the clock.

A CSS-only pause patch would leave timers and game selection out of sync. A new
animation library or visual redesign adds unnecessary scope. The shared Motion
clock is the implementation choice for this update.

## Verification

- Native Node regressions: elapsed pause/resume, cancelled callbacks, seeks,
  single completion, readable stills and comparison boundaries.
- Full pytest suite and React build; sync the checked generated assets, then run
  both checks again for the final repository fingerprint.
- Opt-in Chromium regressions for real rendered pause/resume, comparison seeks,
  reduced motion, navigation/replay and desktop/mobile overflow.
- Independent standards and request/spec reviews of the final diff.

Local Chromium is unavailable in this session. The deployed preview requires
an authenticated admin session; no visual verification will be claimed without
one. Browser tests remain executable in the existing browser CI job.

## Official Motion references

- https://motion.dev/docs/react-motion-value
- https://motion.dev/docs/react-use-transform
- https://motion.dev/docs/animate
- https://motion.dev/docs/react-animate-presence

The connected plugin's live documentation search was used to discover these
APIs. Public official docs were read because this host exposes no resource reader
for the plugin's motion:// documentation links.
