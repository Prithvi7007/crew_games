# Badge achievement paths: rendered QA

final result: passed

## Visual truth and rendering

- Approved target: option 3 selected by the user, November 2, 2026.
  Source: `/workspace/scratch/fee6ebd3114b/generated_images/exec-985d58e3-7800-4cbb-9f7e-764545c45790.png`.
- Implementation: the actual checked Vite player bundle and repository CSS,
  rendered in cloud Chrome through a temporary Python fixture server.
  Data and save endpoints are synthetic; production records were not used.
- Final desktop screenshot: `/workspace/scratch/badge-paths-desktop-final.jpg`.
- Full comparison: `/workspace/scratch/fee6ebd3114b/badge-paths-comparison-final.jpg`.
- Focused comparison: `/workspace/scratch/fee6ebd3114b/badge-paths-comparison-focused.jpg`.
- Phone screenshots: `/workspace/scratch/badge-paths-mobile-final.jpg` and
  `/workspace/scratch/badge-paths-mobile-action.jpg`.

The source is 1487x1058 pixels. The final desktop content viewport and capture
are 1363x936 CSS/image pixels at 1x. For comparison, the source was uniformly
scaled to width 1363, then cropped only at its bottom margin to height 936.
No horizontal crop or nonuniform scaling was used. Both images were placed in
one side-by-side input before assessment. A second combined input compares
navigation, heading type and the first game headings at full resolution.

The compared state is dark theme, Season 2, Mastery selected, 0/21 earned,
private admin tools closed and Case Closed inspected. The generated target
omits the global header, so the matching screenshot hides only that header in
the temporary fixture. The normal header was separately checked on desktop,
tablet and phone. No production header code was changed.

Initial tuning used a 1440x1024 fixture. Full-page/clip capture subsequently
timed out in the cloud browser, so final comparison used its native 1363x936
viewport. Screenshot success and loaded DOM were verified before comparison.
Phone CSS viewport is 390x844; its screenshot is a 1x crop of that iframe from
the browser capture. Tablet viewport is 834x1194; DOM measurements confirmed
two 393px columns and no document-width overflow.

## Findings and correction history

1. **P1: shared medals were dimmed.** Initial rendered screenshot
   `/workspace/scratch/badge-paths-initial-render.jpg` exposed a partial legacy
   selector extracted as a global opacity/grayscale rule. Removed that rule.
   The contrast regression failed before the fix and passed afterward. Final
   combined and phone captures show intact rarity frames and game colors.
2. **P2: medals and typography were undersized against the chosen target.**
   First combined evidence:
   `/workspace/scratch/fee6ebd3114b/badge-paths-comparison-initial.jpg`.
   Increased desktop medal size, name/heading scale and vertical spacing;
   removed redundant visible helper copy. Final combined comparison above
   confirms the four-column proportions and single detail/action hierarchy.
3. **P2: mobile selection could describe an offscreen group after a category
   change.** Independent spec review identified Secret → Unicorn → All.
   Added selected-group refs and horizontal container-only synchronization;
   documented the deliberate phone strip in the spec. Rendered reproduction
   now places Unicorn at x20..370 inside the x16..374 strip, with document
   width and scroll width both 390. Added an opt-in browser regression.
   Independent spec re-review reports this finding resolved.

No actionable P0/P1/P2 findings remain in the inspected states.

## Required fidelity surfaces

- **Typography:** Loaded native CREW Manrope display and Inter UI text;
  browser font status was loaded. Hierarchy, weights, tracking and wrapping
  were inspected in combined full/focused comparisons. Long badge names wrap
  without truncation. Native fonts take precedence over generated letterforms.
- **Spacing/layout:** Four paths, subtle separators, restrained category
  navigation, compact tools and a single detail region follow the chosen
  composition. Tablet wraps to two columns. Phone shows one horizontally
  browsable game group so the action follows three mastery medals. The All
  view remains a full 21-medal overview; individual categories provide shorter
  browsing. The shared action remains in document flow.
- **Colors/tokens:** Near-black CREW surface, muted secondary text, cyan active
  underline and existing green/amber/blue/purple game identities are retained.
  Earned, wearing, selected and private-preview states have textual cues.
- **Assets:** Existing repository SVG BadgeMedallion and EquippedProfileBadge
  artwork is reused unchanged. Crisp vector scaling and rarity/game rings
  were inspected. Generated concept icon approximations intentionally do not
  replace the app's native award identities. No raster UI assets were added.
- **Copy:** All 21 real badge names and earned rules are preserved. Detail
  text describes the inspected award; earned dates and original worn season
  remain accurate. Admin disclosure explicitly explains private preview.

## Interactions and limits

Actual compiled frontend checks with synthetic fixtures:

- Mastery has 12 inspectable nodes; All has 21, Rivalry 6, Secret 1 and
  Collection 2. There is one shared detail/action area.
- Selecting locked/earned medals changes details only. A player's locked
  badge has a disabled Not earned action. Admin Try on/Remove preview work.
- A player's Wear badge/Remove badge work. Wearing a Season 1 award survives
  browsing Season 2, without treating the same locked code as earned there.
- Native season navigation retains the collection query. Pending saves
  disable medal/category/season changes. A simulated 503 preserves the
  equipped state, reports the error and allows a successful retry.
- Preview tools opens with Enter and retains the cinematic unlock link.
  Enter selects an offscreen phone medal through native keyboard focus;
  the matching group becomes visible. Try on is reachable above the bottom
  navigation: measured action bottom 666px, navigation top 776px.
- Phone and tablet document widths do not overflow. Normal header and fixed
  mobile navigation remain present outside the isolated comparison.
- Console errors were inspected. No application error was observed in the
  final flow; browser-extension metadata errors were excluded. Earlier save
  failure was intentional synthetic test traffic.

These are browser interaction checks, not a claim of authenticated Flask E2E
coverage. The full backend suite and production build are separate checks.
Opt-in Chromium tests require their dedicated browser CI environment; the
ordinary pytest worker skips them. No screen-reader device audit was run.

## Review and completion gates

- Independent standards review: no P0–P2 findings.
- Independent spec review: mobile finding corrected and re-reviewed.
- Shared award rules, API contracts, header and artwork remain unchanged.
- Final production build and pytest checks must pass on the exact bridge
  fingerprint before commit/push; the bridge enforces this delivery gate.
- No dependency, migration, backend route or production data mutation.

Implementation checklist: visual corrections complete; desktop/phone rendered
comparison complete; category/selection/save/season/preview checks complete;
independent review complete. Draft PR delivery follows final bridge checks.
