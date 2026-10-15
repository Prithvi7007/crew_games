"""One shared Trivia-style React masthead is used by all four CREW games.

The actual header markup and CSS have one owner; no more duplicated
game-specific header structures or cascade patches for the same layout.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "frontend" / "src" / "player"
MAIN = (PLAYER / "main.jsx").read_text(encoding="utf-8")
HEADER = (PLAYER / "GamePageHeader.jsx").read_text(encoding="utf-8")
SHARED = (PLAYER / "styles" / "gameplay.css").read_text(encoding="utf-8")
WORD = (PLAYER / "styles" / "word.css").read_text(encoding="utf-8")
TRIVIA = (PLAYER / "styles" / "trivia.css").read_text(encoding="utf-8")
TYPOGRAPHY = (PLAYER / "styles" / "typography.css").read_text(encoding="utf-8")
PREVIEW = (PLAYER / "styles" / "gameplay-refinement.css").read_text(encoding="utf-8")


def test_one_react_header_is_used_on_all_four_game_pages():
    assert "import GamePageHeader from './GamePageHeader';" in MAIN
    assert MAIN.count("<GamePageHeader ") == 4
    for title in (
        "Mystery Monday", "Trivia Tuesday",
        "Wordle Wednesday", "Tick-Tock Thursday",
    ):
        assert f'title="{title}"' in MAIN
    assert 'className="v19-trivia-heading crew-game-heading"' in HEADER
    assert 'className="v19-trivia-context crew-game-context"' in HEADER
    assert 'className="v19-back-link"' in HEADER
    assert 'className="v19-trivia-date"' in HEADER
    assert 'className="v19-trivia-heading-mark"' in HEADER
    assert '<h1>{title}</h1>' in HEADER
    assert '<p>{description}</p>' in HEADER
    # Game layouts no longer produce their own masthead markup.
    assert '<section className="game-title-row">' not in MAIN
    assert '<section className="word-heading">' not in MAIN
    assert '<header className="v19-trivia-heading">' not in MAIN


def test_shared_header_has_one_css_owner_and_no_last_loaded_spacing_patch():
    assert not (PLAYER / "styles" / "gameplay-spacing.css").exists()
    assert "gameplay-spacing.css" not in MAIN
    assert ".crew-game-heading {" in SHARED
    assert ".crew-game-heading h1 {" in SHARED
    assert ".crew-game-heading p {" in SHARED
    assert ".crew-game-heading .crew-game-context {" in SHARED
    assert "--crew-game-main-top: clamp(18px, 2.4vw, 30px)" in SHARED
    for source in (SHARED, WORD, TRIVIA):
        assert "var(--crew-game-main-top)" in source
    for source in (SHARED, WORD):
        assert ".game-title-row" not in source
        assert ".word-heading" not in source
    assert ".v19-trivia-heading h1" not in TRIVIA
    assert ".v19-trivia-date" not in TRIVIA
    assert ".word-heading" not in TYPOGRAPHY
    assert ".game-title-row" not in TYPOGRAPHY


def test_identical_content_rail_and_mobile_header_layout():
    for source in (SHARED, WORD, TRIVIA):
        assert "width: min(1280px, calc(100% - 64px))" in source
    assert "width: min(1160px, calc(100% - 64px))" not in SHARED
    assert ".crew-game-heading .v19-trivia-heading-mark { display: none; }" in SHARED
    assert "grid-template-columns: 1fr" in SHARED
    assert "padding: 16px 0 96px" in WORD
    assert "padding: 16px 0 96px" in SHARED
    assert "padding: 16px 0 30px" in TRIVIA
    assert "@media (max-width: 760px)" in SHARED


def test_header_metadata_and_accessibility_are_game_specific():
    assert 'metricValue={state.potential_score}' in MAIN
    assert 'metricValue="10" metricLabel="QUESTIONS"' in MAIN
    assert 'metricValue="1" metricLabel="ROUND"' in MAIN
    assert 'aria-label={archive ?' in HEADER
    assert 'href={returnUrl}' in HEADER
    assert 'aria-hidden={metricDecorative' in HEADER
    assert "{state.theme||'CREW WORD'}" in MAIN


def test_staff_preview_and_completion_still_work_without_duplicate_headers():
    assert "body.crew-gameplay-preview .crew-game-heading" in PREVIEW
    assert "body.crew-gameplay-preview .crew-game-heading h1" in PREVIEW
    assert "data.shell?.gameplayPreviewEnabled" in MAIN
    assert MAIN.count("useCompletionViewport(state.completed)") == 4
    for game in ("mystery", "word", "tick_tock"):
        assert f'<GameResult game="{game}"' in MAIN
    assert "className=\"v19-trivia-main crew-result-presentation\"" in MAIN
