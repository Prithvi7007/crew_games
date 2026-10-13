"""The concave CREW game deck is a reversible desktop-only layout trial."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text()
CSS = (ROOT / "frontend/src/player/styles/home.css").read_text()


def test_opt_in_preview_leaves_original_home_as_default():
    assert "get('deck_preview') === '1'" in MAIN
    assert 'is-deck-preview' in MAIN
    assert "featured && !deckPreview" in MAIN
    assert "featured={deckPreview ? null : featured}" in MAIN
    assert 'href={game.url}' in MAIN
    assert "const future=state==='future'" in MAIN


def test_four_cards_have_concave_depth_without_visible_track():
    assert "@media (min-width:1121px)" in CSS
    assert ".v22-today-desktop.is-deck-preview .v22-week-progress{display:none}" in CSS
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in CSS
    for n in range(1, 5):
        assert f".v22-day-card:nth-child({n})" in CSS
    assert "rotateY(-9deg)" in CSS
    assert "rotateY(9deg)" in CSS
    assert "scale(.965)" in CSS
    assert "gap:clamp(12px,1.45vw,24px)" in CSS
    assert "filter:saturate(.72)" in CSS
    assert "prefers-reduced-motion:reduce" in CSS
