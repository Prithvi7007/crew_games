from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shared_controls_stylesheet_is_loaded_after_shell():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    shell = "css/crew-shell.css"
    controls = "css/crew-controls.css"
    foundation = "css/phase1-foundation.css"

    assert shell in base
    assert controls in base
    assert foundation in base
    assert base.index(shell) < base.index(controls) < base.index(foundation)


def test_viewport_fit_cover_is_enabled_for_safe_areas():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'content="width=device-width, initial-scale=1, viewport-fit=cover"' in base


def test_shared_controls_define_behavior_contract():
    css = (ROOT / "app" / "static" / "css" / "crew-controls.css").read_text(
        encoding="utf-8"
    )

    required = (
        ".crew-button",
        ".crew-chip",
        ".crew-field",
        ".crew-select",
        ".crew-status-pill",
        ".crew-progress-track",
        "--crew-control-min",
        "--crew-safe-top",
        "prefers-reduced-motion: reduce",
    )

    for token in required:
        assert token in css


def test_key_player_controls_use_shared_behavior_hooks():
    player = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    login = (ROOT / "app/templates/login.html").read_text(encoding="utf-8")

    for hook in ("crew-field", "crew-button", "crew-chip", "crew-select"):
        assert hook in player

    assert "crew-field" in login
    assert "crew-button" in login
