from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app" / "static" / "css"
PLAYER_CSS = ROOT / "frontend" / "src" / "player" / "styles"


def test_core_pages_have_single_stylesheet_owners():
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    assert 'id="crew-player-root"' in template
    assert "react/player.css" in template
    assert "react/player.js" in template

    for component in (
        "HomePage",
        "GamesPage",
        "RankingsPage",
        "ProfilePage",
        "MysteryPage",
        "TriviaPage",
        "WordPage",
        "TickTockPage",
    ):
        assert f"function {component}" in source

def test_shared_shell_is_not_redeclared_by_page_css():
    shell = (CSS / "crew-shell.css").read_text(encoding="utf-8")
    assert ".crew-app-page .app-nav" in shell
    assert ".crew-nav-account" in shell
    assert ".crew-points-chip" in shell

    for filename in ("home.css", "games.css", "rankings.css"):
        content = (PLAYER_CSS / filename).read_text(encoding="utf-8")
        assert ".app-nav" not in content
        assert ".desktop-nav" not in content
        assert ".mobile-bottom-nav" not in content


def test_obsolete_version_layers_are_removed():
    obsolete = (
        "v16-today.css",
        "v17-today.css",
        "v19-rankings.css",
        "v22-today-desktop.css",
        "v23-core-pages.css",
    )
    for filename in obsolete:
        assert not (CSS / filename).exists(), filename


def test_home_uses_mobile_weight_artwork():
    content = (PLAYER_CSS / "home.css").read_text(encoding="utf-8")
    for filename in (
        "mystery-mobile.jpg",
        "trivia-mobile.jpg",
        "word-mobile.jpg",
        "tick_tock-mobile.jpg",
    ):
        assert filename in content


def test_deployment_maintenance_tracks_current_schema_and_permissions():
    rehearsal = (ROOT / "deploy/v12-migration-rehearsal.sh").read_text(encoding="utf-8")
    rollback = (ROOT / "deploy/rollback-code.sh").read_text(encoding="utf-8")

    assert "from app.migrations import HEAD_REVISION" in rehearsal
    assert '"$REVISION" != "$HEAD_REVISION"' in rehearsal
    assert "chown -R crew:www-data /opt/crew" in rollback
