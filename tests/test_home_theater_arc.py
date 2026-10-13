"""Cinema-oriented, separate game portals remain isolated to the desktop preview."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
ARC = (ROOT / "frontend/src/player/HomeTheaterArc.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/player/styles/theater-arc.css").read_text(encoding="utf-8")
COVERFLOW = (ROOT / "frontend/src/player/styles/coverflow.css").read_text(encoding="utf-8")


def test_new_preview_does_not_replace_home_or_existing_coverflow():
    assert "get('theater_preview') === '1'" in MAIN
    assert "query.get('coverflow_preview') === '1'" in MAIN
    assert "const coverflowPreview = !theaterPreview" in MAIN
    assert "has-coverflow-preview" in MAIN
    assert "has-theater-preview" in MAIN
    assert "import HomeTheaterArc from './HomeTheaterArc'" in MAIN
    assert "import './styles/theater-arc.css'" in MAIN
    assert "<HomeDesktop games={games} featured={featured} today={today}/>" in MAIN
    assert "<HomeCoverflow games={games}" in MAIN
    assert "<HomeTheaterArc games={games}" in MAIN
    assert "<HomeJourney games={games} featured={featured} today={today}/>" in MAIN
    assert ".v17-today-shell.has-theater-preview .v22-today-desktop{display:none}" in CSS
    assert ".crew-theater-arc{display:none}" in CSS
    assert "@media (min-width:1121px)" in CSS
    assert ".crew-coverflow-stage" in COVERFLOW


def test_game_portals_are_four_separate_cards_with_original_game_behavior():
    assert "games.map((game, index)" in ARC
    assert "key={game.key}" in ARC
    assert "renderCard(game, index)" in ARC
    assert "const SLOTS = ['outer-left', 'inner-left', 'inner-right', 'outer-right']" in ARC
    assert "featured={null} today={today}" in MAIN
    assert "href={game.url}" in MAIN
    assert "return future?<article" in MAIN
    assert "stateFor(game,today)" in MAIN


def test_not_a_carousel_or_single_continuous_screen():
    assert 'aria-label="This week\'s CREW games"' in ARC
    assert 'aria-roledescription="carousel"' not in ARC
    for banned in ("useState", "setOffset", "onPointer", "onWheel", "Next", "Previous",
                   "crew-coverflow-controls", "crew-coverflow-dots", "swiper", "scrollIntoView"):
        assert banned not in ARC
    assert "crew-theater-arc-controls" not in CSS
    assert "scroll-snap-type" not in CSS


def test_cinema_orientation_and_depth_do_not_exaggerate_card_scale():
    assert "perspective:1450px" in CSS
    assert "transform-style:preserve-3d" in CSS
    assert "translateZ(var(--arc-z))" in CSS
    assert "rotateY(var(--arc-angle))" in CSS
    expected = {
        "outer-left": ("calc(50% - var(--arc-outer-offset))", "70px", "32deg"),
        "inner-left": ("calc(50% - var(--arc-inner-offset))", "-42px", "11deg"),
        "inner-right": ("calc(50% + var(--arc-inner-offset))", "-42px", "-11deg"),
        "outer-right": ("calc(50% + var(--arc-outer-offset))", "70px", "-32deg"),
    }
    for position, (x, z, yaw) in expected.items():
        anchor = ".crew-theater-arc-panel.is-" + position + "{"
        assert anchor in CSS
        block = CSS.split(anchor, 1)[1].split("}", 1)[0]
        assert "--arc-x:" + x in block
        assert "--arc-z:" + z in block
        assert "--arc-angle:" + yaw in block
    assert "scale(var(--arc-scale))" in CSS
    assert "scale(calc(var(--arc-scale) + .025))" in CSS
    assert "--arc-card-width:clamp(205px,22vw,324px)" in CSS
    assert "width:var(--arc-card-width)" in CSS
    assert "height:clamp(336px,31vw,430px)" in CSS
    assert "--arc-inner-offset:calc(var(--arc-card-width) * .5)" in CSS
    assert "--arc-outer-offset:calc(var(--arc-card-width) * 1.43)" in CSS
    assert "crew-theater-arc-ambient" in ARC
    assert ".crew-theater-arc-panel::before" in CSS
    assert ".crew-theater-arc-panel:focus-within" in CSS
    assert "a.v22-day-card:focus-visible" in CSS
    assert "@media (prefers-reduced-motion:reduce)" in CSS


def test_theater_arc_adjacent_edges_share_one_symmetric_curve():
    # A shared baseline avoids the previous ~40px near-seam height mismatch.
    # Depth and mirrored yaw now make the center look recessed.
    expected_y = {
        "outer-left": "-5px",
        "inner-left": "-5px",
        "inner-right": "-5px",
        "outer-right": "-5px",
    }
    for position, y in expected_y.items():
        anchor = ".crew-theater-arc-panel.is-" + position + "{"
        block = CSS.split(anchor, 1)[1].split("}", 1)[0]
        assert "--arc-y:" + y in block

    # Consistent ~22 degree steps mean the inner facets follow the same arc.
    assert "--arc-z:70px;--arc-angle:32deg" in CSS
    assert "--arc-z:-42px;--arc-angle:11deg" in CSS
    assert "--arc-z:-42px;--arc-angle:-11deg" in CSS
    assert "--arc-z:70px;--arc-angle:-32deg" in CSS
    assert "translateY(calc(var(--arc-y) - 9px))" in CSS
    assert ".crew-theater-arc-panel:focus-within" in CSS


def test_theater_arc_matches_adjacent_projected_edge_heights():
    """Match seam silhouettes while keeping a physically recessed center."""
    expected = {
        "outer-left": ("70px", "32deg", ".94"),
        "inner-left": ("-42px", "11deg", ".96"),
        "inner-right": ("-42px", "-11deg", ".96"),
        "outer-right": ("70px", "-32deg", ".94"),
    }
    for position, (depth, yaw, scale) in expected.items():
        anchor = ".crew-theater-arc-panel.is-" + position + "{"
        declaration = CSS.split(anchor, 1)[1].split("}", 1)[0]
        assert "--arc-z:" + depth in declaration
        assert "--arc-angle:" + yaw in declaration
        assert "--arc-scale:" + scale in declaration
    assert "height:clamp(336px,31vw,430px)" in CSS
    assert "--arc-card-width:clamp(205px,22vw,324px)" in CSS
    assert "width:var(--arc-card-width)" in CSS
    assert CSS.count("--arc-y:-5px") == 4
    assert "--arc-y:14px" not in CSS
    assert "scale(var(--arc-scale))" in CSS
    assert "scale(calc(var(--arc-scale) + .025))" in CSS
    assert "crew-theater-arc-controls" not in CSS


def test_projected_card_seams_and_spacing_remain_smooth_on_desktop():
    """Projected 3D quads preserve the upper AND lower silhouette at all widths.

    Representative desktop widths include the CSS minimum breakpoint and
    widths above the 324px card cap. The stage may be narrower than the
    viewport inside CREW's content shell.
    """
    from math import cos, radians, sin

    slots = (
        (-1.43, 70, 32, .94),
        (-.5, -42, 11, .96),
        (.5, -42, -11, .96),
        (1.43, 70, -32, .94),
    )

    def clamp(minimum, value, maximum):
        return max(minimum, min(value, maximum))

    for viewport in (1121, 1200, 1366, 1600, 1918, 2100):
        stage_width = min(viewport - 90, 1500)
        stage_height = clamp(382, viewport * .36, 480)
        card_width = clamp(205, viewport * .22, 324)
        card_height = clamp(336, viewport * .31, 430)
        origin_y = .46 * stage_height
        origin_x = .5 * stage_width

        def corner(slot, at_right, at_bottom):
            offset, depth, yaw, scale = slots[slot]
            u = (.5 if at_right else -.5) * card_width
            v = (.5 if at_bottom else -.5) * card_height
            angle = radians(yaw)
            world_x = origin_x + offset * card_width + scale * cos(angle) * u
            world_y = 10 - 5 + card_height / 2 + scale * v
            world_z = depth - scale * sin(angle) * u
            perspective = 1450 / (1450 - world_z)
            return (
                origin_x + (world_x - origin_x) * perspective,
                origin_y + (world_y - origin_y) * perspective,
            )

        for left in (0, 1, 2):
            right = left + 1
            top_left = corner(left, True, False)
            top_right = corner(right, False, False)
            bottom_left = corner(left, True, True)
            bottom_right = corner(right, False, True)
            gap = top_right[0] - top_left[0]
            # Separate clickable cards without huge empty seams.
            assert 8 <= gap <= 32, (viewport, left, "gap", gap)
            # Both corners must connect, not just the upper silhouette.
            assert abs(top_right[1] - top_left[1]) <= 6, (viewport, left, "top")
            assert abs(bottom_right[1] - bottom_left[1]) <= 6, (viewport, left, "bottom")

        # Both outside portals remain within their container.
        assert corner(0, False, False)[0] > 0
        assert corner(3, True, False)[0] < stage_width


def test_preview_spotlights_are_static_clipped_and_theme_colored():
    """A low-opacity themed overhead wash, not a new layout or moving beam."""
    assert CSS.index(".crew-theater-arc{display:none}") < CSS.index("@media (min-width:1121px)")
    spot_selector = ".crew-theater-arc-panel .v22-day-card::before{"
    assert CSS.count(spot_selector) == 1
    light = CSS.split(spot_selector, 1)[1].split("\n  }", 1)[0]
    assert 'content:""' in light
    assert "position:absolute" in light
    assert "inset:0 0 auto" in light
    assert "height:34%" in light
    assert "pointer-events:none" in light
    assert "border-radius:inherit" in light
    assert "radial-gradient(" in light
    assert "var(--v22-tone)" in light
    assert "linear-gradient(" in light
    assert "opacity:.78" in light
    assert "filter:blur(7px)" in light
    assert "animation:" not in light
    assert "transition:" not in light
    # Existing artwork and tap targets are still present, with the overlay
    # beneath the copy (z-index 1) and decorative glint (z-index 3).
    assert "z-index:0" in light
    assert ".crew-theater-arc-panel .v22-day-card::after{" in CSS
    assert "z-index:3" in CSS
    assert ".crew-theater-arc-panel a.v22-day-card:focus-visible{" in CSS
    assert ".crew-theater-arc-panel .v22-day-card.future{" in CSS
