from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_design_tokens_load_before_page_specific_styles():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    main_css = "css/main.css"
    tokens = "css/crew-tokens.css"
    block_head = "{% block head %}"

    assert main_css in base
    assert tokens in base
    assert block_head in base
    assert base.index(main_css) < base.index(tokens) < base.index(block_head)


def test_design_tokens_define_core_crew_system():
    css = (ROOT / "app" / "static" / "css" / "crew-tokens.css").read_text(
        encoding="utf-8"
    )

    required = (
        "--crew-color-bg",
        "--crew-color-text",
        "--crew-game-mystery",
        "--crew-game-trivia",
        "--crew-game-word",
        "--crew-game-tick-tock",
        "--crew-control-min",
        "--crew-motion-standard",
    )

    for token in required:
        assert token in css


def test_public_page_color_aliases_use_shared_tokens():
    static_css = ROOT / "app" / "static" / "css"
    player_css = ROOT / "frontend" / "src" / "player" / "styles"

    checks = {
        player_css / "home.css": (
            "--v17-bg: var(--crew-color-bg);",
            "--v17-accent: var(--crew-game-trivia);",
        ),
        static_css / "v18-pages.css": (
            "--crew18-bg: var(--crew-color-bg);",
            "--crew18-gold: var(--crew-game-trivia);",
        ),
        player_css / "trivia.css": (
            "--tt-bg: var(--crew-color-bg);",
            "--tt-gold: var(--crew-game-trivia);",
        ),
        player_css / "profile.css": (
            "--p-bg: var(--crew-color-bg);",
            "--p-blue: var(--crew-accent-profile);",
        ),
    }

    for css_path, expected in checks.items():
        content = css_path.read_text(encoding="utf-8")
        for token in expected:
            assert token in content
