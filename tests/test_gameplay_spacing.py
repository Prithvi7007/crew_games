"""Game page title spacing must not inherit the old oversized hero layout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "frontend" / "src" / "player"
MAIN = (PLAYER / "main.jsx").read_text(encoding="utf-8")
SPACING = (PLAYER / "styles" / "gameplay-spacing.css").read_text(encoding="utf-8")
ORIGINAL_GAME = (PLAYER / "styles" / "gameplay.css").read_text(encoding="utf-8")
ORIGINAL_WORD = (PLAYER / "styles" / "word.css").read_text(encoding="utf-8")
ORIGINAL_TRIVIA = (PLAYER / "styles" / "trivia.css").read_text(encoding="utf-8")


def test_spacing_layer_follows_typography_and_game_preview_styles():
    imports = [
        "gameplay.css", "word.css", "trivia.css",
        "gameplay-refinement.css", "typography.css",
        "gameplay-spacing.css",
    ]
    order = [MAIN.index(f"import './styles/{name}';") for name in imports]
    assert order == sorted(order)


def test_main_padding_compacted_for_all_four_regular_game_routes():
    # Original spacing was 42–78px above a second 25–26px title pad.
    assert "clamp(46px,6vw,78px)" in ORIGINAL_GAME
    assert "clamp(46px,6vw,78px)" in ORIGINAL_WORD
    assert "clamp(42px,5vw,70px)" in ORIGINAL_TRIVIA
    assert "padding-top: clamp(18px, 2.4vw, 30px)" in SPACING
    assert ".game-page:not(.crew-gameplay-preview):not(.crew-game-complete) .single-game-main" in SPACING
    assert ".word-page:not(.crew-gameplay-preview):not(.crew-game-complete) .word-main" in SPACING
    assert ".v19-trivia-page:not(.crew-gameplay-preview) .v19-trivia-main:not(.crew-result-presentation)" in SPACING
    assert ".game-title-row" in SPACING
    assert ".word-heading" in SPACING
    assert ".v19-trivia-heading" in SPACING


def test_gameplay_preview_and_completion_view_remain_isolated():
    assert ":not(.crew-gameplay-preview)" in SPACING
    assert ":not(.crew-game-complete)" in SPACING
    assert ":not(.crew-result-presentation)" in SPACING
    for target in (
        ".game-stage", ".word-game-panel", ".timer-stage",
        ".react-trivia-stage", ".crew-result-stage",
        ".v20-profile-main", ".home-week", ".trophy-section-header",
        ".crew-page-head", ".app-nav", ".word-tile",
    ):
        assert target not in SPACING
    assert "data.shell?.gameplayPreviewEnabled" in MAIN
    assert "useCompletionViewport" in MAIN


def test_mobile_and_context_spacing_are_compact():
    assert "@media (max-width: 760px)" in SPACING
    assert "padding-top: 16px" in SPACING
    assert "margin-bottom: 14px" in SPACING
    assert "margin-bottom: 8px" in SPACING
    assert "margin-top: 10px" in SPACING
    assert "text-wrap" not in SPACING
    assert "font-size" not in SPACING
