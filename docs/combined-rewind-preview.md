# Combined Rewind and championship preview

Build an admin/owner preview at `/rewind?preview=1&prototype=1&story=5&combined=1`.
The existing React/Motion cinema and shared playback clock remain the presentation.

- A player selector contains every profile, including players with no completions.
- Player's championships uses frozen official openings after finalization. Before finalization, the existing read-only championship preview supplies current positive-score leaders, including ties; label every such reveal provisional.
- Explicit season/game/all championship demos prepend their scenes to the player's full real Saga. Remove replaced winner/welcome scenes to avoid duplicate openings.
- Keep actual totals, ranks, awards, login identity and published results unchanged.
- Switching player or preview mode navigates to a fresh server-rendered response and restarts playback at the cover.
- Keep controls staff-only, keyboard accessible and usable on narrow screens. Public Rewind must contain no roster.

Implementation order: route regressions; read-only composition helper and strict query validation; preview controls and provisional copy; desktop/mobile browser scenarios; full Python suite and React production build; inspect diff; commit and draft PR.

Use the existing single cinema rather than a separate viewer to preserve the smooth transitions already approved. No schema or dependency changes.
