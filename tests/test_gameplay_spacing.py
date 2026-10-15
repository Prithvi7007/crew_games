"""Game masthead regression: all four pages share Trivia's header structure.

Root cause is fixed in the source owners, not in a late CSS override layer.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "frontend" / "src" / "player"
MAIN = (PLAYER / "main.jsx").read_text(encoding="utf-8")
SHARED = (PLAYER / "styles" / "gameplay.css").read_text(encoding="utf-8")
WORD = (PLAYER / "styles" / "word.css").read_text(encoding="utf-8")
TRIVIA = (PLAYER / "styles" / "trivia.css").read_text(encoding="utf-8")
PREVIEW = (PLAYER / "styles" / "gameplay-refinement.css").read_text(encoding="utf-8")


def test_deprecated_spacing_override_is_removed():
    assert not (PLAYER / "styles" / "gameplay-spacing.css").exists()
    assert "gameplay-spacing.css" not in MAIN
    assert "import './styles/typography.css';" in MAIN


def test_all_four_games_share_trivia_back_and_date_structure():
    # Mystery, Word and Tick use a common context row; Trivia retains its
    # working DOM structure while joining the same shared class.
    assert MAIN.count('<div className="crew-game-context">') == 3
    assert 'className="v19-trivia-context crew-game-context"' in MAIN
    assert MAIN.count('aria-label={state.archive?') == 3
    assert MAIN.count('>← Back</a>') >= 4
    assert ".crew-game-context {" in SHARED
    assert "display: flex;" in SHARED.split(".crew-game-context {", 1)[1].split("}", 1)[0]
    assert "margin-bottom: 10px" in SHARED
    # The heading is aligned on the same 1280px content rail on every page.
    assert "width: min(1280px, calc(100% - 64px))" in SHARED
    assert "width: min(1280px, calc(100% - 64px))" in WORD
    assert "width: min(1280px, calc(100% - 64px))" in TRIVIA
    assert "width: min(1160px, calc(100% - 64px))" not in SHARED


def test_original_layout_owners_use_one_top_padding_token():
    assert "--crew-game-main-top: clamp(18px, 2.4vw, 30px)" in SHARED
    for source in (SHARED, WORD, TRIVIA):
        assert "var(--crew-game-main-top)" in source
    assert "clamp(46px,6vw,78px)" not in SHARED
    assert "clamp(46px,6vw,78px)" not in WORD
    assert "clamp(42px,5vw,70px)" not in TRIVIA
    assert ".single-game-main { padding-top:52px; }" not in SHARED
    assert ".game-title-row { padding:26px 4px 28px;" not in SHARED
    assert "padding: 25px 4px 27px" not in WORD
    assert "font-size: clamp(3rem,13vw,4.4rem)" not in WORD
    assert "font-size:clamp(3rem,13vw,4.4rem)" not in SHARED
    assert "font-size: clamp(2.7rem,12vw,4rem)" not in TRIVIA


def test_trivia_reference_spacing_is_identical_at_breakpoints():
    assert "margin-bottom: 16px" in TRIVIA
    assert "margin-bottom: 16px" in WORD
    assert "margin-bottom: 16px" in SHARED
    assert "margin-bottom: 10px" in TRIVIA
    assert "margin: 14px 0 0" in WORD
    assert "margin: 14px 0 0" in SHARED
    assert "padding: 16px 0 30px" in TRIVIA
    assert "padding: 16px 0 96px" in WORD
    assert "padding: 16px 0 96px" in SHARED
    assert "margin-bottom: 14px" in TRIVIA
    assert "margin-bottom: 14px" in WORD
    assert "margin-bottom:14px" in SHARED


def test_staff_preview_keeps_a_context_line_and_results_unchanged_in_js():
    assert "body.crew-gameplay-preview .crew-game-context" in PREVIEW
    assert "display:block;" in PREVIEW
    assert "body.crew-gameplay-preview .v19-trivia-heading" in PREVIEW
    for marker in (
        "<GameResult game=\"word\"",
        "<GameResult game=\"mystery\"",
        "<GameResult game=\"tick_tock\"",
        "useCompletionViewport(state.completed)",
        "data.shell?.gameplayPreviewEnabled",
    ):
        assert marker in MAIN
