"""CREW typography is consistent across authenticated screens only.

These regression checks protect CSS targeting so we don't accidentally resize
gameplay questions, scores, badge medallions, or marketing artwork.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src" / "player"
MAIN = FRONTEND / "main.jsx"
TYPO = FRONTEND / "styles" / "typography.css"


def test_shared_typography_imports_after_all_page_styles():
    js = MAIN.read_text(encoding="utf-8")
    assert "import './styles/typography.css';" in js
    for earlier in (
        "page.css", "home.css", "games.css", "rankings.css",
        "profile.css", "trophies.css", "gameplay-refinement.css",
        "word.css", "trivia.css", "results.css",
    ):
        assert js.index(f"import './styles/{earlier}';") < js.index("import './styles/typography.css';")


def test_type_tokens_and_all_screens_covered():
    css = TYPO.read_text(encoding="utf-8")
    for token in (
        "--crew-type-page-title",
        "--crew-type-game-title",
        "--crew-type-profile-title",
        "--crew-type-section-title",
        "--crew-type-description",
        "--crew-type-context",
    ):
        assert token in css
    selectors = (
        ".react-player-page .home-week h1",
        ".react-player-page .crew-page-head h1",
        ".react-player-page .trophy-section-header h1",
        ".react-player-page .v20-profile-identity h1",
        ".react-player-page.game-page .game-title-row h1",
        ".react-player-page.word-page .word-heading h1",
        ".react-player-page.v19-trivia-page .v19-trivia-heading h1",
    )
    for selector in selectors:
        assert selector in css
    assert "font-size: var(--crew-type-game-title)" in css
    assert "body.react-player-page.crew-gameplay-preview.game-page .game-title-row h1" in css
    assert "body.react-player-page.crew-gameplay-preview.word-page .word-heading h1" in css
    assert "body.react-player-page.crew-gameplay-preview.v19-trivia-page .v19-trivia-heading h1" in css
    # Home shares exactly the same H1 scale as Games, Rankings and Badges.
    assert css.count("font-size: var(--crew-type-page-title)") >= 3
    assert "--crew-type-home-title" not in css
    assert "font-size: var(--crew-type-page-title)" in css


def test_type_rules_do_not_resize_gameplay_content_or_global_h1():
    css = TYPO.read_text(encoding="utf-8")
    assert ":root" not in css
    assert "html h1" not in css
    assert ".react-player-page h1 {" not in css
    for gameplay_target in (
        ".react-trivia-question-wrap h1",
        ".word-tile", ".key", ".timer-ring", ".target-time",
        ".react-result-score", ".crew-result-score", ".cul-message",
    ):
        assert gameplay_target not in css
    assert ".react-player-page" in css


def test_typography_responsive_and_respects_long_badge_counts():
    css = TYPO.read_text(encoding="utf-8")
    assert "@media (max-width: 760px)" in css
    assert "@media (max-width: 380px)" in css
    assert "text-wrap: balance" in css
    assert "overflow-wrap: anywhere" in css
    assert ".trophy-section-header h1 small" in css
    assert "display: block" in css


def test_dynamic_home_header_and_staff_gameplay_preview_remain_intact():
    js = MAIN.read_text(encoding="utf-8")
    assert '<span className="v17-eyebrow">{weekLabel}</span>' in js
    assert "season.week_number" in js
    assert "data.shell?.gameplayPreviewEnabled" in js
    assert "CinematicReveal" in js
