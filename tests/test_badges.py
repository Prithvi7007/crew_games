"""Badge registry, evaluation, season ownership and persistence regression tests."""

from datetime import date

import pytest
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from app.badges import (
    BADGES, BADGES_BY_CODE, CHAMPIONSHIP_CODES, evaluate_collection_badges,
    evaluate_game_badges, evaluate_week_badges,
)
from app.badge_store import (
    award_badges, award_badges_for_game_date, get_badge_awards,
    get_showcase, set_showcase_slot,
)
from app.db import create_profile


def _profile():
    p = create_profile(
        "BadgeTester" + str(_profile.counter),
        generate_password_hash("test-badge-credentials"), "⭐",
        generate_password_hash("test-badge-recovery"),
    )
    _profile.counter += 1
    return int(p["id"])


_profile.counter = 1


def test_registry_contains_exact_v1_catalog():
    assert len(BADGES) == len(BADGES_BY_CODE) == 21
    assert len([b for b in BADGES if b.vertical == "game_mastery"]) == 12
    assert len([b for b in BADGES if b.vertical == "leaderboard"]) == 6
    assert len([b for b in BADGES if b.vertical == "secret"]) == 1
    assert len([b for b in BADGES if b.vertical == "collection"]) == 2
    assert len(CHAMPIONSHIP_CODES) == 5
    assert BADGES_BY_CODE["unicorn"].rarity == "legendary"


def test_mystery_cumulative_badges_and_losses():
    assert evaluate_game_badges("mystery", {"completed": True, "won": True, "revealed_count": 1}) == {
        "case_closed", "sharp_instincts", "mind_reader"
    }
    assert evaluate_game_badges("mystery", {"completed": True, "won": True, "revealed_count": 4}) == set()
    assert evaluate_game_badges("mystery", {"completed": True, "won": False, "revealed_count": 1}) == set()
    assert evaluate_game_badges("mystery", {"completed": False, "won": True, "revealed_count": 1}) == set()


def test_trivia_uses_saved_answers_not_unverified_score():
    answers = [{"correct": i < 9} for i in range(10)]
    assert evaluate_game_badges("trivia", {"completed": True, "answers": answers}) == {
        "sharp_shooter", "brainiac"
    }
    assert evaluate_game_badges("trivia", {"completed": True, "answers_json": '[{"correct":true}]', "score": 100}) == set()
    assert evaluate_game_badges("trivia", {"completed": True, "answers": [{"correct": True}] * 10}) == {
        "sharp_shooter", "brainiac", "flawless_victory"
    }


def test_wordle_guess_counts_and_unfinished():
    assert evaluate_game_badges("word", {"completed": True, "won": True, "guesses_json": '["MAGIC"]'}) == {
        "word_wizard", "word_ninja", "one_shot_wonder"
    }
    assert evaluate_game_badges("word", {"completed": True, "won": True, "guesses": ["A", "B", "C", "D"]}) == {
        "word_wizard"
    }
    assert evaluate_game_badges("word", {"completed": True, "won": False, "guesses": ["A"] * 6}) == set()


def test_tick_tock_boundaries():
    assert evaluate_game_badges("tick_tock", {"completed": True, "difference_seconds": 0.10}) == {
        "close_call", "precision_pro", "human_stopwatch"
    }
    assert evaluate_game_badges("tick_tock", {"completed": True, "difference_seconds": 0.25}) == {
        "close_call", "precision_pro"
    }
    assert evaluate_game_badges("tick_tock", {"completed": True, "difference_seconds": 1.0}) == {"close_call"}
    assert evaluate_game_badges("tick_tock", {"completed": True, "difference_seconds": -0.01}) == set()


def test_week_badges_require_all_four_completed_scores():
    assert evaluate_week_badges({"mystery": 100, "trivia": 100, "word": 100, "tick_tock": 100}) == {
        "high_roller", "unicorn"
    }
    assert evaluate_week_badges({"mystery": 75, "trivia": 90, "word": 100, "tick_tock": 90}) == {"high_roller"}
    assert evaluate_week_badges({"mystery": 100, "trivia": 100, "word": 100}) == set()
    assert evaluate_week_badges({"mystery": 100, "trivia": 100, "word": 100, "tick_tock": 120}) == set()


def test_collection_only_counts_distinct_noncollection_codes():
    catalog = [b.code for b in BADGES if b.vertical != "collection"]
    assert evaluate_collection_badges(catalog[:9] + ["badge_hunter", "unknown"]) == set()
    assert evaluate_collection_badges(catalog[:10] + ["badge_hunter"]) == {"badge_hunter"}
    assert evaluate_collection_badges(catalog[:15] + ["badge_hunter"]) == {"badge_hunter", "crew_legend"}


def test_badge_schema_and_idempotent_season_scoping(app):
    with app.app_context():
        inspector = inspect(app.extensions["crew_db_engine"])
        for name in ("badge_awards", "badge_showcase", "season_badge_finalizations"):
            assert name in inspector.get_table_names()
        player = _profile()
        assert award_badges_for_game_date(player, "2026-09-22", ["sharp_shooter"]) == ("sharp_shooter",)
        assert award_badges_for_game_date(player, "2026-09-22", ["sharp_shooter"]) == ()
        season_one = get_badge_awards(player, 1)
        assert len(season_one) == 1
        assert season_one[0]["source_date"] == "2026-09-22"
        with pytest.raises(ValueError, match="Unknown season"):
            award_badges(player, 99999, ["sharp_shooter"])
        with pytest.raises(ValueError, match="source date"):
            award_badges(player, 1, ["high_roller"], source_date=date(2026, 11, 3))
        with pytest.raises(ValueError, match="Unknown badge"):
            award_badges(player, 1, ["not-a-badge"])


def test_showcase_enforces_ownership_and_three_slots(app):
    with app.app_context():
        player = _profile()
        stranger = _profile()
        award_badges(player, 1, ["sharp_shooter"])
        award_id = int(get_badge_awards(player, 1)[0]["id"])
        set_showcase_slot(player, 1, award_id)
        assert len(get_showcase(player)) == 1
        with pytest.raises(ValueError, match="belong"):
            set_showcase_slot(stranger, 1, award_id)
        with pytest.raises(ValueError, match="already showcased"):
            set_showcase_slot(player, 2, award_id)
        with pytest.raises(ValueError, match="Showcase slot"):
            set_showcase_slot(player, 4, award_id)
        set_showcase_slot(player, 1, None)
        assert get_showcase(player) == []
