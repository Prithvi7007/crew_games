from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v13_shared_shell_and_mobile_navigation_are_present():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    shell = (ROOT / "app/static/css/crew-shell.css").read_text(encoding="utf-8")

    assert "function AppHeader" in source
    assert "mobile-bottom-nav" in source
    assert "PLAY TOGETHER" in source
    assert "GO FURTHER" in source
    assert "crew-nav-account" in source

    assert ".crew-app-page .app-nav" in shell
    assert ".crew-app-page .mobile-bottom-nav" in shell

def test_current_home_uses_the_consolidated_home_experience():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    css = ROOT / "frontend" / "src" / "player" / "styles" / "home.css"

    assert "function HomePage" in source
    assert "function HomeDesktop" in source
    assert "function HomeJourney" in source
    assert "v17-today-shell" in source
    assert "v22-today-desktop" in source
    assert "home-summary" in source
    assert "<AppHeader" in source
    assert css.exists()

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
