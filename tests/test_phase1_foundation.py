from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_phase1_foundation_stylesheet_is_loaded_last():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    foundation = "css/phase1-foundation.css"
    game_results = "css/v19-game-results.css"

    assert foundation in base
    assert game_results in base
    assert base.index(game_results) < base.index('{% block head %}') < base.index(foundation)


def test_phase1_foundation_has_accessibility_guards():
    css = (ROOT / "app" / "static" / "css" / "phase1-foundation.css").read_text(
        encoding="utf-8"
    )

    required = (
        ":focus-visible",
        "--crew-tap-target",
        "safe-area-inset-bottom",
        "prefers-reduced-motion: reduce",
        "animation-duration: .01ms",
    )

    for token in required:
        assert token in css
