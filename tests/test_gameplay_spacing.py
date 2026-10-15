"""Structural guardrails only: visual geometry is covered by Playwright.

These checks protect the shared-header architecture. We no longer assert
literal pixel margins/paddings because they don't verify browser rendering.
"""
from pathlib import Path

PLAYER = Path(__file__).resolve().parents[1] / "frontend/src/player"
MAIN = (PLAYER / "main.jsx").read_text(encoding="utf-8")
HEADER = (PLAYER / "GamePageHeader.jsx").read_text(encoding="utf-8")


def test_all_four_game_routes_render_one_shared_header_component():
    assert "import GamePageHeader from './GamePageHeader';" in MAIN
    assert MAIN.count("<GamePageHeader ") == 4
    for title in (
        "Mystery Monday", "Trivia Tuesday",
        "Wordle Wednesday", "Tick-Tock Thursday",
    ):
        assert f'title="{title}"' in MAIN
    assert '<h1>{title}</h1>' in HEADER
    assert 'href={returnUrl}' in HEADER
    assert 'aria-label={archive ?' in HEADER


def test_header_has_one_style_owner_and_no_new_spacing_override():
    css = (PLAYER / "styles/gameplay.css").read_text(encoding="utf-8")
    word = (PLAYER / "styles/word.css").read_text(encoding="utf-8")
    trivia = (PLAYER / "styles/trivia.css").read_text(encoding="utf-8")
    assert ".crew-game-heading {" in css
    assert ".crew-game-heading h1 {" in css
    assert not (PLAYER / "styles/gameplay-spacing.css").exists()
    for source in (css, word, trivia):
        assert "var(--crew-game-main-top)" in source
    assert ".game-title-row" not in css
    assert ".word-heading" not in word
    # Old detached score ribbons no longer have any corresponding React markup.
    assert "glass-stat" not in MAIN
    assert ".game-page .glass-stat" not in css
    assert ".word-page .glass-stat" not in word
