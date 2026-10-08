from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v13_shared_shell_and_mobile_navigation_are_present():
    header = (ROOT / "app" / "templates" / "_app_header.html").read_text(encoding="utf-8")
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    css = (ROOT / "app" / "static" / "css" / "main.css").read_text(encoding="utf-8")

    assert "crew-signal" not in header
    assert "mobile-bottom-nav" in header
    assert "PLAY TOGETHER" in header
    assert "GO FURTHER" in header
    assert "filename='css/main.css', v='13.10.1'" in base
    assert "CREW v13.3 — Cinematic Today" in css
    assert "CREW v13.4 — North-star composition polish" in css
    assert "CREW v13.6 — North-star fidelity lock" in css
    assert "CREW v13.7 — full-bleed fidelity lock" in css
    assert "mystery-scene-mobile.webp" in css
    assert "trivia-scene-mobile.webp" in css
    assert "word-scene-mobile.webp" in css
    assert "tick_tock-scene-mobile.webp" in css
    assert "body.daily-drop .noise" in css
    assert "prefers-reduced-motion" in css


def test_current_home_uses_the_consolidated_home_experience():
    home = (ROOT / "app" / "templates" / "home.html").read_text(encoding="utf-8-sig")
    today_partial = ROOT / "app" / "templates" / "_home_v17.html"
    today_css = ROOT / "app" / "static" / "css" / "home.css"

    assert "v17-today-page" in home
    assert "filename='css/home.css'" in home
    assert '{% include "_home_v17.html" %}' in home
    assert today_partial.exists()
    assert today_css.exists()

    partial = today_partial.read_text(encoding="utf-8")
    assert '{% include "_app_header.html" %}' in partial

    header = (ROOT / "app" / "templates" / "_app_header.html").read_text(encoding="utf-8")
    assert ">Home</a>" in header
    assert ">Rankings</a>" in header


def test_trivia_uses_shared_react_player_app_without_replacing_flask_contract():
    player_template = ROOT / "app" / "templates" / "player_app.html"
    react_source = ROOT / "frontend" / "src" / "player" / "main.jsx"
    react_css = ROOT / "frontend" / "src" / "player" / "player.css"
    package = ROOT / "frontend" / "package.json"
    routes = (ROOT / "app" / "trivia" / "routes.py").read_text(encoding="utf-8")

    assert player_template.exists()
    assert react_source.exists()
    assert react_css.exists()
    assert package.exists()
    assert 'render_player(' in routes
    assert '"trivia"' in routes
    assert "function TriviaPage" in react_source.read_text(encoding="utf-8")
