from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_react_player_bundle_is_the_new_shared_entry():
    vite = (ROOT / "frontend/vite.config.js").read_text(encoding="utf-8")
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")
    assert "src/player/main.jsx" in vite
    assert "player.js" in vite
    assert "player.css" in vite
    assert "crew-player-root" in template
    assert "react/player.js" in template
    assert "function AppHeader" in source
    assert "function AccountMenu" in source


def test_word_and_trivia_are_rendered_by_react_player_contract():
    word = (ROOT / "app/word/routes.py").read_text(encoding="utf-8")
    trivia = (ROOT / "app/trivia/routes.py").read_text(encoding="utf-8")
    assert 'render_player(' in word and '"word"' in word
    assert 'render_player(' in trivia and '"trivia"' in trivia
    assert 'render_template("word.html"' not in word
    assert 'render_template("trivia.html"' not in trivia


def test_wordle_handles_backend_tile_state_objects():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    assert "function tileState(tile)" in source
    assert "(item.tiles||[]).map(tileState)" in source
    assert "tileState(item.tiles?.[i])" in source


def test_wordle_absent_state_is_visually_distinct():
    css = (ROOT / "frontend/src/player/player.css").read_text(encoding="utf-8")
    assert ".word-page .key.absent" in css
    assert "#465565" in css
    assert ".word-page .legend-swatch.absent" in css


def test_all_logged_in_player_pages_use_shared_react_runtime():
    sources = {
        "home": ROOT / "app/main/routes.py",
        "games": ROOT / "app/main/routes.py",
        "leaderboard": ROOT / "app/main/routes.py",
        "profile": ROOT / "app/auth/routes.py",
        "mystery": ROOT / "app/mystery/routes.py",
        "trivia": ROOT / "app/trivia/routes.py",
        "word": ROOT / "app/word/routes.py",
        "tick_tock": ROOT / "app/tick_tock/routes.py",
    }
    for page, path in sources.items():
        text = path.read_text(encoding="utf-8")
        assert f'"{page}"' in text, page
        assert "render_player(" in text, page


def test_react_player_source_contains_all_runtime_pages():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    for component in (
        "HomePage", "GamesPage", "RankingsPage", "ProfilePage",
        "MysteryPage", "TriviaPage", "WordPage", "TickTockPage",
    ):
        assert f"function {component}" in source
    assert "function GameResult" in source


def test_player_template_loads_page_owned_styles():
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")
    for stylesheet in ("home.css", "games.css", "rankings.css", "v20-profile.css", "v19-trivia.css"):
        assert stylesheet in template

def test_react_assets_use_content_fingerprinted_cache_busting():
    helper = (ROOT / "app/player_ui.py").read_text(encoding="utf-8")
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")
    assert "def react_asset_version" in helper
    assert 'react_js_version=react_asset_version("player.js")' in helper
    assert 'react_css_version=react_asset_version("player.css")' in helper
    assert "v=react_js_version" in template
    assert "v=react_css_version" in template


def test_mobile_shell_keeps_account_controls_available():
    css = (ROOT / "app/static/css/crew-shell.css").read_text(encoding="utf-8")
    assert "/* React player runtime hardening. */" in css
    assert '.account-trigger[aria-expanded="true"]' in css
    assert ".crew-runtime-notice" in css
    assert "Override the earlier mobile rule that hid the entire account menu" in css


def test_runtime_fetch_handles_session_expiry_and_rankings_races():
    source = (ROOT / "app/static/js/ui.js").read_text(encoding="utf-8")
    assert "response.redirected" in source
    assert "redirectedUrl.pathname === '/login'" in source
    assert "encodeURIComponent(next)" in source
    assert "leaderboardRequestId" in source
    assert "crewLeaderboardStale" in source
    assert "crewLeaderboard" in source


def test_trivia_motion_targets_shared_react_root():
    source = (ROOT / "app/static/js/motion.js").read_text(encoding="utf-8")
    assert "crew-player-root" in source
    assert "root.dataset.page !== 'trivia'" in source
    assert "crew-trivia-root" not in source
