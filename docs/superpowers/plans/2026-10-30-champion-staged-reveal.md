# Champion reveal correction

## Screenshot findings
The supplied opening screenshot exposes the championship title before Begin, puts a generic sparkle ahead of player identity, and uses the same gold treatment across titles.

## Intended behavior
- Show a neutral cover before the first winner scene; do not mount the reveal until Begin.
- Reveal the actual player name, verified title, and existing championship badge in sequence.
- Use CREW gold for the season champion and the existing game color for each game champion.
- Present the badge close-up as the next act, retaining the existing story structure.
- Pause reveal animations with playback. Replay restores the cover.
- Reduced-motion mode reveals the first act immediately without skipping it or autoplaying.
- Preserve the existing demo-only access controls and all actual results and awards.

## Implementation
- Add a small pure playback reducer with native Node tests, exercised by pytest.
- Extract champion cover/reveal rendering into ChampionReveal.jsx; reuse the badge catalog and medallion.
- Replace only the winner/winner_badge rendering and related CSS.
- Update cinema startup, pause, replay and chapter timing.
- Extend opt-in browser coverage for neutral startup, player identity, correct badge/colors, replay and reduced motion.
- Run full pytest and React build, sync verified outputs, review and create a PR.

## Verification limits
The cloud browser rejected file:// navigation under its URL security policy. No workaround will be used. The existing app must be reviewed through its normal authenticated HTTP preview after deployment; do not claim local visual verification.

## Review and verification
- New playback behavior was tested first. The initial full-suite run failed only for the missing playback module.
- Ten native Node cases cover cover/start/replay, reduced motion, paused first-act navigation, explicit evidence pause, pausable final badge, completed still navigation, bounds, and champion-only elapsed timing.
- Independent Standards and Spec reviews identified three pause regressions. The fixes separate finished from paused, retain visible paused controls, and scope elapsed-time preservation to champion scenes.
- The final badge now finishes after its own playback duration; it is never forced to animate while explicitly paused.
- Paused manual navigation shows a readable still instead of an invisible animation frame.
- Existing game-comparison timing and component wiring are preserved.
- Opt-in browser tests cover the new first-act and final-badge pause paths. They remain unrun under the documented browser policy limitation.
