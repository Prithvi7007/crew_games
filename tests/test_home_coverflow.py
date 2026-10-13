"""The coverflow is an independent interactive desktop preview, not a grid transform."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
COMPONENT = (ROOT / "frontend/src/player/HomeCoverflow.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/player/styles/coverflow.css").read_text(encoding="utf-8")


def test_coverflow_is_opt_in_and_original_home_stays_available():
    assert "get('coverflow_preview') === '1'" in MAIN
    assert "has-coverflow-preview" in MAIN
    assert "import HomeCoverflow from './HomeCoverflow';" in MAIN
    assert "<HomeDesktop games={games} featured={featured} today={today}/>" in MAIN
    assert "<HomeJourney games={games} featured={featured} today={today}/>" in MAIN
    assert "featured={null} today={today}" in MAIN
    assert "new URLSearchParams" not in COMPONENT


def test_coverflow_reuses_real_game_cards_and_locked_routes():
    assert "renderCard(game, index)" in COMPONENT
    assert "key={game.key}" in COMPONENT
    assert "href={game.url}" in MAIN
    assert "return future?<article" in MAIN
    assert "stateFor(game,today)" in MAIN
    assert "const POSITIONS = ['outer-left', 'inner-left', 'inner-right', 'outer-right']" in COMPONENT


def test_coverflow_is_interactive_and_keyboard_and_touch_accessible():
    for text in ("useState(0)", "onPointerDown", "onPointerUp", "onPointerCancel",
                 "suppressClick.current", "event.preventDefault()", "setOffset", "wrappedKey", "setWrappedKey",
                 "ArrowLeft", "ArrowRight", 'aria-roledescription="carousel"',
                 'aria-live="polite"', "aria-pressed={index === offset}",
                 'aria-label="Rotate game cards left"', 'aria-label="Rotate game cards right"'):
        assert text in COMPONENT
    assert "touch-action:pan-y" in CSS
    assert "@keyframes crew-coverflow-wrap-in" in CSS
    assert ".crew-coverflow-item.is-wrapping" in CSS
    assert ":focus-visible" in CSS


def test_four_slots_are_bounded_independent_card_layers():
    assert ".crew-coverflow{display:none}" in CSS
    assert "@media (min-width:1121px)" in CSS
    assert ".v17-today-shell.has-coverflow-preview .v22-today-desktop{display:none}" in CSS
    assert "position:absolute" in CSS
    assert "width:clamp(210px,23vw,315px)" in CSS
    assert "perspective:1500px" in CSS
    assert "--cover-x:15%" in CSS
    assert "--cover-x:38%" in CSS
    assert "--cover-x:62%" in CSS
    assert "--cover-x:85%" in CSS
    assert "--cover-z:-75px" in CSS
    assert "rotateY(var(--cover-rotation))" in CSS
    assert "overflow:visible" not in CSS
    assert "@media (prefers-reduced-motion:reduce)" in CSS


def test_coverflow_cards_face_inward_toward_the_center():
    # Positive CSS rotateY faces right, negative faces left.
    expected = {
        "outer-left": 15,
        "inner-left": 3,
        "inner-right": -3,
        "outer-right": -15,
    }
    for position, angle in expected.items():
        anchor = ".crew-coverflow-item.is-" + position + "{"
        assert anchor in CSS
        declaration = CSS.split(anchor, 1)[1].split("}", 1)[0]
        assert "--cover-rotation:" + str(angle) + "deg" in declaration
