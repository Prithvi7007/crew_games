# Player benchmarks and non-winner season honors

User request: exclude owner/admin accounts from CREW averages; show the season's
Top 3 and season game masters before non-winners' personal Rewinds.

- Pass current player-role profile IDs to the Rewind benchmark builders. Keep
  own scores and cutoff-scoped competition totals/ranks/weekly highs intact.
  Average each eligible peer's own per-game average with equal player weight;
  exclude viewer, owner/admin accounts and unplayed games, retain completed zeros.
  Apply the same cohort to peer averages/medians used by supporting insights.
- Players with no official championship title receive a season podium followed
  by one short announcement for each available official game master, then the
  existing welcome/personal story. Existing title winners retain their opening.
- Podium uses positive cutoff-eligible season totals. Equal scores share places
  (competition ranking, e.g. 1,1,3); include everyone tied within Top 3 places.
  Master names/scores/badges come from the approved snapshot. No invented winners.
- Only finalized seasons receive the community honors. Preview/demos stay
  read-only; demo openings omit duplicate community honors before personal acts.
- Use CREW gold/silver/bronze for podium, game colors and actual championship
  badges for masters. Use the existing Motion chapter clock for staggered
  podium entrances and master reveals. Pause, stills, reduced motion, autoplay,
  Skip, completion tracking and final chapter behavior remain intact.
- Use a neutral cover before manual honors playback. No schema, dependency,
  score, championship finalization or badge-award changes.

Implementation/checks:
1. Add pure honor-data composition plus regression cases for role cohorts,
   equal weights, zero/missing peers, frozen state, winner/non-winner flow and ties.
2. Extend benchmark builders and compose new honors into the finalized Saga.
3. Render a responsive podium and individual game-master acts with Motion.
4. Update expected non-winner sequences; add browser coverage and duration cases.
5. Build/sync assets, run final suite and build, review standards/spec and open PR.

Browser playback requires provisioned Chromium; report its status separately.
