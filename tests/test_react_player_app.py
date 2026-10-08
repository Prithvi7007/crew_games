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
