# Badges: achievement paths

Approved visual target: the third generated image selected by the user on
November 2, 2026. Four game columns, compact medal paths, restrained text
collection navigation, season selector, discreet preview tools, and one shared
detail/action area. Preserve the global CREW header outside this page redesign.

Use the existing vector BadgeMedallion and EquippedProfileBadge components,
catalog, rarity/game palette, award IDs, private preview, and save APIs. No new
art assets, badge rules, backend routes, database migrations, or dependencies.

Mastery opens by default; All badges, Rivalry, Secret and Collection remain
available. Selecting a medal only inspects it. The detail area contains the sole
equip/unequip or private-preview action. Locked badges remain inspectable and
cannot be equipped. Selection falls back to a visible medal when categories
change. Keep the selected category when switching seasons.

Desktop uses four mastery columns; tablet wraps to two. On phones, horizontally
scrollable groups show one game at a time so the shared detail area follows
three medals rather than twelve. Changing collection or selection brings the
selected group into view without moving the page vertically. Names wrap,
controls remain keyboard accessible, and the detail area remains in normal
document flow. All badges and other categories use compact groups without
implying prerequisite unlock rules.

Worn badges retain their original season across browsing. Disable mutations
and season navigation during saves, preserve visible error feedback, and keep
admin preview tools available through a native disclosure. Keep existing toast
and sitewide avatar/badge identity behavior.

Validation: full backend suite and production build; updated interaction
regressions; source and independent review; rendered comparison and interaction
checks using the actual compiled app with explicitly synthetic preview data.
Browser/visual evidence must be reported separately from tests and build.
