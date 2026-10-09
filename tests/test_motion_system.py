from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_motion_layer_respects_react_result_ownership_and_accessibility_order():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    player = (ROOT / "frontend" / "src" / "player" / "main.jsx").read_text(
        encoding="utf-8"
    )

    motion = "css/crew-motion.css"
    block_head = "{% block head %}"
    foundation = "css/phase1-foundation.css"

    assert "css/v19-game-results.css" not in base
    assert "import './styles/results.css';" in player
    assert motion in base
    assert foundation in base
    assert base.index(motion) < base.index(block_head) < base.index(foundation)


def test_motion_helper_loads_before_page_specific_scripts():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    helper = "js/motion.js"
    scripts_block = "{% block scripts %}"

    assert helper in base
    assert scripts_block in base
    assert base.index(helper) < base.index(scripts_block)


def test_motion_tokens_define_emphasis_timing():
    css = (ROOT / "app" / "static" / "css" / "crew-tokens.css").read_text(
        encoding="utf-8"
    )

    required = (
        "--crew-motion-emphasis",
        "--crew-motion-result",
        "--crew-ease-emphasis",
    )

    for token in required:
        assert token in css


def test_motion_styles_cover_state_changes_and_reduced_motion():
    css = (ROOT / "app" / "static" / "css" / "crew-motion.css").read_text(
        encoding="utf-8"
    )

    required = (
        "@keyframes crew-question-in",
        "@keyframes crew-answer-correct",
        "@keyframes crew-answer-wrong",
        "@keyframes crew-result-score",
        ".crew-result-stage .crew-result-score",
        ".react-trivia-result .react-result-score",
        ".v17-score-rail i",
        "prefers-reduced-motion: reduce",
        "animation: none !important",
    )

    for token in required:
        assert token in css


def test_trivia_motion_helper_reacts_to_question_changes_and_respects_preference():
    js = (ROOT / "app" / "static" / "js" / "motion.js").read_text(encoding="utf-8")

    required = (
        "prefers-reduced-motion: reduce",
        "MutationObserver",
        "react-trivia-question-wrap",
        "react-trivia-options",
        "crew-motion-enter",
    )

    for token in required:
        assert token in js
