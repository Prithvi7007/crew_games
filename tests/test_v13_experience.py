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


def test_v13_home_is_a_daily_drop_not_a_dashboard():
    home = (ROOT / "app" / "templates" / "home.html").read_text(encoding="utf-8")
    css = (ROOT / "app" / "static" / "css" / "main.css").read_text(encoding="utf-8")

    assert "daily-drop-stage" in home
    assert "drop-week-rail" in home
    assert "drop-progress-row" in home
    assert "next-drop-card" in home
    assert "The case is open." in home
    assert "Enter the case" in home
    assert "week-console" not in home
    assert "v13-leader-section" not in home
    assert "v13-leader-card" not in home
    assert "THE FOUR SIGNALS" not in home
    assert "theme_label" not in home
    assert "drop-stage-media" in home
    assert "<picture" not in home
    assert "drop-stage-media-desktop" in home
    assert "drop-stage-media-mobile" in home
    assert "-scene-master.webp" in home
    assert "filename=scene_desktop, v='13.10.1'" in home
    assert "filename=scene_mobile, v='13.10.1'" in home
    assert "earned</span>" not in home
    assert "WEEK 01" in home
    assert "100 points on the line." not in home
    assert "points on the line." in home
    assert "Your run." not in home
    assert "mystery-scene.webp" in css
    assert "trivia-scene.webp" in css
    assert "word-scene.webp" in css
    assert "tick_tock-scene.webp" in css

    header = (ROOT / "app" / "templates" / "_app_header.html").read_text(encoding="utf-8")
    assert ">Today</a>" in header
    assert ">Rankings</a>" in header


def test_v13_8_trivia_uses_react_island_without_replacing_flask_contract():
    trivia = (ROOT / "app" / "templates" / "trivia.html").read_text(encoding="utf-8")
    react_source = ROOT / "frontend" / "src" / "trivia" / "main.jsx"
    react_css = ROOT / "frontend" / "src" / "trivia" / "trivia.css"
    package = ROOT / "frontend" / "package.json"

    assert 'id="crew-trivia-root"' in trivia
    assert 'data-answer-url="{{ url_for(\'trivia.answer\', date=state.date) }}"' in trivia
    assert 'id="trivia-state"' in trivia
    assert "filename='react/trivia.js', v='13.9'" in trivia
    assert "filename='react/trivia.css', v='13.9'" in trivia
    assert "static', filename='js/trivia.js'" not in trivia
    assert react_source.exists()
    assert react_css.exists()
    assert package.exists()
    assert "react-trivia-context" in trivia
    assert "Perfect run" in react_source.read_text(encoding="utf-8")
