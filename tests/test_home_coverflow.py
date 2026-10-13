"""Opt-in CREW immersive gallery retains working game cards and no carousel movement."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
COMPONENT = (ROOT / "frontend/src/player/HomeCoverflow.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/player/styles/coverflow.css").read_text(encoding="utf-8")


def test_gallery_is_desktop_only_and_original_home_is_unchanged():
    assert "get('coverflow_preview') === '1'" in MAIN
    assert "has-coverflow-preview" in MAIN
    assert "import HomeCoverflow from './HomeCoverflow';" in MAIN
    assert "<HomeDesktop games={games} featured={featured} today={today}/>" in MAIN
    assert "<HomeJourney games={games} featured={featured} today={today}/>" in MAIN
    assert "featured={null} today={today}" in MAIN
    assert "@media (min-width:1121px)" in CSS
    assert ".v17-today-shell.has-coverflow-preview .v22-today-desktop{display:none}" in CSS
    assert ".crew-coverflow{display:none}" in CSS


def test_all_four_games_keep_real_artwork_links_and_lock_behavior():
    assert "games.map((game, index)" in COMPONENT
    assert "renderCard(game, index)" in COMPONENT
    assert "key={game.key}" in COMPONENT
    assert "href={game.url}" in MAIN
    assert "return future?<article" in MAIN
    assert "stateFor(game,today)" in MAIN
    assert "const POSITIONS = ['outer-left', 'inner-left', 'inner-right', 'outer-right']" in COMPONENT


def test_gallery_is_static_without_arrows_swipe_or_carousel_controls():
    assert 'aria-label="This week\'s CREW games"' in COMPONENT
    assert 'aria-roledescription="carousel"' not in COMPONENT
    for removed in ("onPointerDown", "onPointerUp", "onKeyDown", "setOffset",
                    "useState", "useEffect", "crew-coverflow-controls",
                    "crew-coverflow-dots", "crew-coverflow-announcement",
                    "is-wrapping", "aria-live"):
        assert removed not in COMPONENT
    assert "crew-coverflow-controls" not in CSS
    assert "crew-coverflow-dots" not in CSS
    assert "@keyframes crew-coverflow-wrap-in" not in CSS


def test_gallery_has_real_depth_inward_tilt_and_immersive_lighting():
    assert "perspective:1700px" in CSS
    assert "transform-style:preserve-3d" in CSS
    assert "translateZ(var(--cover-z))" in CSS
    assert "--cover-x:18%" in CSS
    assert "--cover-x:39%" in CSS
    assert "--cover-x:61%" in CSS
    assert "--cover-x:82%" in CSS
    expected = {
        "outer-left": ("105px", "18deg", "1"),
        "inner-left": ("-100px", "4deg", ".94"),
        "inner-right": ("-100px", "-4deg", ".94"),
        "outer-right": ("105px", "-18deg", "1"),
    }
    for position, (depth, angle, scale) in expected.items():
        anchor = ".crew-coverflow-item.is-" + position + "{"
        assert anchor in CSS
        declaration = CSS.split(anchor, 1)[1].split("}", 1)[0]
        assert "--cover-z:" + depth in declaration
        assert "--cover-rotation:" + angle in declaration
        assert "--cover-scale:" + scale in declaration
    assert "crew-coverflow-atmosphere" in COMPONENT
    assert ".crew-coverflow-atmosphere" in CSS
    assert ".crew-coverflow-item::before" in CSS
    assert "translateZ(calc(var(--cover-z) + 75px))" in CSS
    assert ":focus-within" in CSS
    assert ":focus-visible" in CSS
    assert "@media (prefers-reduced-motion:reduce)" in CSS
