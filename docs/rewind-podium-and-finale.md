# Rewind podium visibility and finale

The finalized season podium was nested in the non-winner branch, hiding it from champions and game masters. It now appears once after their personal championship celebration and before their personal analytics. Non-winners retain their existing podium, game-master announcements and welcome.

The personal weekly-podium chapter was restricted to the top three players by podium-frequency rank. Every viewer with an eligible completion now receives their own actual weekly Top 3 record. Zero-podium participants see zero and neutral wording; accounts without completions still receive no invented record. Competition tie-breaking and scores are unchanged.

The old finale actions were absolutely positioned over the scene. The new final scene and action group share a scrollable layout, with a smaller Season 2 lockup and space reserved for staff controls. Its wrapper remains stable when the actions appear so the final scene does not remount and replay its entrance. The actions are Watch Again and Home. Home always targets `/home`. Completing a login film records the existing completion marker and keeps the ending on screen. Replay immediately starts the first chapter (or its readable reduced-motion state), rather than returning to a login cover without a start button. The final animated chapter uses the same chapter clock before settling.

Regression coverage includes champion/master/non-winner podiums, podium-frequency rank four, legitimate zero records, replay state, completion persistence, login/preview finales, short/mobile layouts and Home navigation. Browser layout must be distinguished from source/build verification when Chromium is unavailable. No schema, score, award or login-marker reset changes.
