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
        "outer-left": ("15%", "70px", "23deg"),
        "inner-left": ("38%", "-42px", "7deg"),
        "inner-right": ("62%", "-42px", "-7deg"),
        "outer-right": ("85%", "70px", "-23deg"),
    }
    for position, (x, z, yaw) in expected.items():
        anchor = ".crew-theater-arc-panel.is-" + position + "{"
        assert anchor in CSS
        block = CSS.split(anchor, 1)[1].split("}", 1)[0]
        assert "--arc-x:" + x in block
        assert "--arc-z:" + z in block
        assert "--arc-angle:" + yaw in block
    assert "scale(var(--arc-scale))" not in CSS
    assert "width:clamp(205px,22vw,324px)" in CSS
    assert "height:clamp(336px,31vw,430px)" in CSS
    assert "crew-theater-arc-ambient" in ARC
    assert ".crew-theater-arc-panel::before" in CSS
    assert ".crew-theater-arc-panel:focus-within" in CSS
    assert "a.v22-day-card:focus-visible" in CSS
    assert "@media (prefers-reduced-motion:reduce)" in CSS
