from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_player_implementations_are_removed():
    obsolete = (
        "app/templates/home.html",
        "app/templates/games.html",
        "app/templates/leaderboard.html",
        "app/templates/profile.html",
        "app/templates/mystery.html",
        "app/templates/trivia.html",
        "app/templates/word.html",
        "app/templates/tick_tock.html",
        "app/templates/_app_header.html",
        "app/templates/_account_menu.html",
        "app/templates/_home_v17.html",
        "app/templates/_home_v22_desktop.html",
        "app/static/js/leaderboard.js",
        "app/static/js/mystery.js",
        "app/static/js/tick-tock.js",
        "app/static/js/word-game.js",
        "app/static/js/game-results.js",
        "frontend/src/trivia/main.jsx",
        "frontend/src/trivia/trivia.css",
        "app/static/react/trivia.js",
        "app/static/react/trivia.css",
    )

    for rel in obsolete:
        assert not (ROOT / rel).exists(), rel


def test_player_routes_have_single_react_renderer():
    routes = (
        "app/main/routes.py",
        "app/mystery/routes.py",
        "app/trivia/routes.py",
        "app/word/routes.py",
        "app/tick_tock/routes.py",
    )

    for rel in routes:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "render_player(" in text, rel
        assert "render_template" not in text, rel


def test_vite_has_only_shared_player_entry():
    vite = (ROOT / "frontend/vite.config.js").read_text(encoding="utf-8")

    assert "src/player/main.jsx" in vite
    assert "src/trivia/main.jsx" not in vite
    assert "player.js" in vite
    assert "player.css" in vite


def test_player_template_uses_shared_react_mount():
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")

    assert 'id="crew-player-root"' in template
    assert "react/player.js" in template
    assert "react/player.css" in template
    assert "crew-trivia-root" not in template
    assert "react/trivia.js" not in template
    assert "react/trivia.css" not in template


def test_base_does_not_load_legacy_player_behavior():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")

    assert "game-results.js" not in base
    assert "leaderboard.js" not in base
    assert "mystery.js" not in base
    assert "word-game.js" not in base
    assert "tick-tock.js" not in base


def test_player_page_styles_are_react_owned():
    template = (ROOT / "app/templates/player_app.html").read_text(encoding="utf-8")
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    expected_sources = (
        "home.css",
        "games.css",
        "rankings.css",
        "profile.css",
        "trivia.css",
    )

    for filename in expected_sources:
        assert (ROOT / "frontend/src/player/styles" / filename).exists()

    for legacy in (
        "home.css",
        "games.css",
        "rankings.css",
        "v20-profile.css",
        "v19-trivia.css",
    ):
        assert not (ROOT / "app/static/css" / legacy).exists()

    for import_path in (
        "./styles/home.css",
        "./styles/games.css",
        "./styles/rankings.css",
        "./styles/profile.css",
        "./styles/trivia.css",
    ):
        assert f"import '{import_path}';" in source

    assert template.count("react/player.css") == 1


def test_player_page_primitives_are_react_owned():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")

    assert "css/crew-pages.css" not in base
    assert not (ROOT / "app/static/css/crew-pages.css").exists()
    assert (ROOT / "frontend/src/player/styles/page.css").exists()
    assert "import './styles/page.css';" in source


def test_mystery_and_tick_tock_styles_are_react_owned():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    gameplay = (
        ROOT / "frontend/src/player/styles/gameplay.css"
    ).read_text(encoding="utf-8")
    legacy_main = (
        ROOT / "app/static/css/main.css"
    ).read_text(encoding="utf-8")
    legacy_v18 = (
        ROOT / "app/static/css/v18-pages.css"
    ).read_text(encoding="utf-8")

    assert "import './styles/gameplay.css';" in source

    for selector in (
        ".game-stage::before",
        ".game-theme {",
        ".mystery-stage",
        ".clue-list",
        ".answer-entry",
        ".timer-stage",
        ".timer-ring",
        ".timer-action",
    ):
        assert selector in gameplay

    for selector in (
        ".mystery-stage",
        ".clue-list",
        ".clue-card",
        ".answer-entry",
        ".game-stage::before",
        ".game-theme {",
        ".timer-stage",
        ".timer-ring",
        ".timer-action",
        ".timer-result",
    ):
        assert selector not in legacy_main

    for selector in (
        ".mystery-page .game-two-column",
        ".mystery-page .game-stage",
        ".timer-page .timer-stage",
        ".timer-page .timer-ring",
        ".timer-page .timer-action",
    ):
        assert selector not in legacy_v18


def test_wordle_styles_are_react_owned():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    word = (
        ROOT / "frontend/src/player/styles/word.css"
    ).read_text(encoding="utf-8")
    legacy_main = (
        ROOT / "app/static/css/main.css"
    ).read_text(encoding="utf-8")
    legacy_v18 = (
        ROOT / "app/static/css/v18-pages.css"
    ).read_text(encoding="utf-8")
    foundation = (
        ROOT / "app/static/css/phase1-foundation.css"
    ).read_text(encoding="utf-8")
    results = (
        ROOT / "frontend/src/player/styles/results.css"
    ).read_text(encoding="utf-8")

    assert "import './styles/word.css';" in source

    for token in (
        "--word-unused-bg: #263444",
        "--word-absent-bg: #111821",
        "--word-present-bg: #9a6516",
        "--word-correct-bg: #107052",
        ".word-page .word-layout",
        ".word-page .word-tile.absent",
        ".word-page .key.present",
        ".word-page .legend-swatch.unused",
    ):
        assert token in word

    for token in (
        ".word-shell {",
        ".word-main {",
        ".word-heading {",
        ".word-layout {",
        ".word-game-panel {",
        ".word-board {",
        ".word-tile {",
        ".word-keyboard {",
        ".keyboard-row {",
        ".key.correct {",
        ".score-scale {",
    ):
        assert token not in legacy_main

    assert ".word-page" not in legacy_v18

    # Cross-cutting accessibility/result layers may reference Wordle.
    assert ".word-page .back-link" in foundation
    assert ".word-page .keyboard-legend" in foundation
    assert ".crew-game-complete.word-page::before" in results
    assert ".crew-game-complete.word-page::after" in results

    assert "Unused" in source
    assert "Not in word" in source
    assert "Wrong spot" in source
    assert "Correct spot" in source
    assert ">In word<" not in source
