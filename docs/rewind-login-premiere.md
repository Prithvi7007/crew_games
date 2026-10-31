# Season 1 Rewind on login

Players with cutoff-eligible Season 1 history enter their own finalized Rewind
automatically after their next login, or next Home visit in an existing session.
Use a separate key in the existing v16 trophy_tour_completions table to remember
finished/skipped Rewinds across sessions and devices. No schema change.

Use an authenticated session handoff for autoplay; an intro query alone cannot
activate it. Keep explicit staff/admin destinations and previews unchanged.
Preserve safe local player deep links as the return destination. No season
results, awards or other player's completion state may change.

Normal motion begins automatically using the current chapter clock. Reduced
motion opens a readable first chapter with manual Next. The final chapter gets
its full duration during a login premiere; finishing or Skip returns to CREW.
A visible Skip action and a no-JavaScript continuation keep gameplay accessible.
After finishing or skipping, later logins go directly to normal CREW pages.
Manual public Rewind remains available and can also record finished/skipped.

An in-flight session guard prevents a Home redirect loop if optional tracking
or its network request fails. Such failures must never block sign-in/gameplay.
A closed tab without finish/skip can be offered the film on a later login.

Implementation:
1. Test eligible login/Home, per-player finished/skipped persistence, deep links,
   preview isolation, CSRF and fail-open behavior.
2. Add app/rewind_login.py and small auth/main route hooks, completion endpoint,
   launch metadata and a no-JavaScript return link.
3. Add frontend completion handling, autoplay initialization, final-act timing
   and visible Skip. Preserve manual viewing and reduced motion.
4. Build, sync assets, run the complete suite/build on the final fingerprint,
   review request/security/standards, then create the draft PR.
