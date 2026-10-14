"""Page headings use old Games/Rankings sizing; small labels remain untouched."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src" / "player"
MAIN = FRONTEND / "main.jsx"
TYPO = FRONTEND / "styles" / "typography.css"
PAGE = FRONTEND / "styles" / "page.css"


def test_typography_loaded_last_and_original_games_rankings_preserved():
    src = MAIN.read_text(encoding="utf-8")
    css = TYPO.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")

    assert "import './styles/typography.css';" in src
    for earlier in (
        "page.css", "home.css", "games.css", "rankings.css",
        "profile.css", "trophies.css", "gameplay-refinement.css",
        "word.css", "trivia.css", "results.css",
    ):
        assert src.index(f"import './styles/{earlier}';") < src.index("import './styles/typography.css';")
    assert "clamp(1.75rem, 2.4vw, 2.35rem)" in page
    assert "--crew-type-page-title: clamp(1.75rem, 2.4vw, 2.35rem)" in css
    assert ".react-player-page .home-week h1," in css
    assert ".react-player-page .trophy-section-header h1" in css
    assert "font-size: var(--crew-type-page-title)" in css
    # Existing .crew-page-head sets both Games and Rankings. No new override.
    assert ".react-player-page .crew-page-head h1" not in css


def test_small_labels_descriptions_badge_count_and_profile_keep_old_styles():
    css = TYPO.read_text(encoding="utf-8")
    for selector in (
        ".v17-eyebrow", ".crew-page-kicker", ".home-week p",
        ".crew-page-head p", ".trophy-eyebrow", ".trophy-equip-guidance",
        ".trophy-section-header h1 small", ".trophy-group-heading h2",
        ".v20-profile-identity", ".v20-kicker",
        ".game-title-row p", ".word-heading p", ".v19-trivia-date",
        ".game-title-row .eyebrow", ".word-heading .eyebrow",
        ".game-side-panel h2", ".word-side-card h2",
    ):
        assert selector not in css
    assert "--crew-type-description" not in css
    assert "--crew-type-context" not in css
    assert "--crew-type-profile-title" not in css


def test_game_titles_stay_compact_without_resizing_game_content():
    css = TYPO.read_text(encoding="utf-8")
    for selector in (
        ".react-player-page.game-page .game-title-row h1",
        ".react-player-page.word-page .word-heading h1",
        ".react-player-page.v19-trivia-page .v19-trivia-heading h1",
        "body.react-player-page.crew-gameplay-preview.game-page .game-title-row h1",
        "body.react-player-page.crew-gameplay-preview.word-page .word-heading h1",
        "body.react-player-page.crew-gameplay-preview.v19-trivia-page .v19-trivia-heading h1",
    ):
        assert selector in css
    for element in (
        ".react-trivia-question-wrap h1", ".word-tile", ".key",
        ".timer-ring", ".target-time", ".react-result-score",
        ".crew-result-score", ".cul-message",
    ):
        assert element not in css
    assert "@media (max-width: 760px)" in css
    assert "@media (max-width: 380px)" in css


def test_home_season_date_swap_remains_dynamic():
    src = MAIN.read_text(encoding="utf-8")
    assert '<span className="v17-eyebrow">{weekLabel}</span>' in src
    assert "season.week_number" in src
    assert "CinematicReveal" in src
    assert "data.shell?.gameplayPreviewEnabled" in src
