"""Guard against resurrecting the retired desktop card deck experiment."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/player/styles/home.css").read_text(encoding="utf-8")


def test_homepage_restores_the_original_featured_layout():
    assert "deck_preview" not in MAIN
    assert "deckPreview" not in MAIN
    assert "is-deck-preview" not in MAIN
    assert 'className="v22-today-desktop"' in MAIN
    assert "featured?' has-featured':''" in MAIN
    assert "featured={featured} today={today}" in MAIN
    assert 'href={game.url}' in MAIN
    assert "const future=state==='future'" in MAIN


def test_experimental_concave_card_css_is_removed():
    assert "is-deck-preview" not in CSS
    assert "rotateY(-9deg)" not in CSS
    assert "rotateY(9deg)" not in CSS
    assert ".v22-feature" in CSS
    assert ".v22-week-grid.has-featured" in CSS
