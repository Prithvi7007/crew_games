from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_phase1_foundation_stylesheet_is_loaded_last():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    player = (ROOT / "frontend" / "src" / "player" / "main.jsx").read_text(
        encoding="utf-8"
    )

    foundation = "css/phase1-foundation.css"
    block_head = "{% block head %}"

    assert foundation in base
    assert "css/v19-game-results.css" not in base
    assert "import './styles/results.css';" in player
    assert base.index(block_head) < base.index(foundation)


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
