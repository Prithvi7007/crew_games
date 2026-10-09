"""Badge awarding integration: persisted evidence, archive, idempotence and ownership."""

from datetime import date

from werkzeug.security import generate_password_hash

from app.badge_awarding import award_saved_completion, replay_saved_badges
from app.badge_store import get_badge_awards
from app.db import (
    create_profile, finalize_game_stats, get_db, get_or_create_mystery_attempt,
    get_or_create_trivia_attempt, get_or_create_word_attempt,
    get_or_create_tick_tock_attempt, get_season_for_date,
    profile_user_key, save_mystery_attempt, save_trivia_attempt,
    save_word_attempt, finish_tick_tock_attempt,
)


def _player():
    p = create_profile(
        "AwardsTester" + str(_player.counter),
        generate_password_hash("replay-safe-password"), "⭐",
        generate_password_hash("replay-safe-recovery"),
    )
    _player.counter += 1
    return int(p["id"])


_player.counter = 1


def _seed(profile_id, key, day, *, competitive=False, strong=True):
    user_key = profile_user_key(profile_id)
    if key == "mystery":
        get_or_create_mystery_attempt(user_key, day)
        save_mystery_attempt(user_key, day, 1 if strong else 4, [], True, strong, 100 if strong else 10)
    elif key == "trivia":
        get_or_create_trivia_attempt(user_key, day)
        save_trivia_attempt(user_key, day, [{"correct": strong}] * 10, True, 100 if strong else 0)
    elif key == "word":
        get_or_create_word_attempt(user_key, day)
        save_word_attempt(user_key, day, ["MAGIC"] if strong else ["A"] * 6, True, strong, 100 if strong else 0)
    elif key == "tick_tock":
        get_or_create_tick_tock_attempt(user_key, day, 7.0)
        finish_tick_tock_attempt(user_key, day, 7.0 if strong else 12.0, 0.0 if strong else 5.0, 100 if strong else 10)
    else:
        raise AssertionError(key)
    score = 100 if strong else (10 if key in ("mystery", "tick_tock") else 0)
    finalize_game_stats(user_key, key, day, score, strong, competitive=competitive)


def test_only_saved_completed_games_can_award_badges(app):
    with app.app_context():
        profile = _player()
        assert award_saved_completion(profile, "word", "2026-09-23") == ()
        get_or_create_word_attempt(profile_user_key(profile), "2026-09-23")
        assert award_saved_completion(profile, "word", "2026-09-23") == ()
        _seed(profile, "word", "2026-09-30", strong=True)
        awards = award_saved_completion(profile, "word", "2026-09-30")
        assert awards == ("word_wizard", "word_ninja", "one_shot_wonder")
        assert award_saved_completion(profile, "word", "2026-09-30") == ()
        season = get_season_for_date(date(2026, 9, 30))
        assert len(get_badge_awards(profile, season["id"])) == 3


def test_archive_completion_awards_without_competitive_streak_or_bonus_points(app):
    with app.app_context():
        profile = _player()
        _seed(profile, "mystery", "2026-09-21", competitive=False)
        codes = award_saved_completion(profile, "mystery", "2026-09-21")
        assert codes == ("case_closed", "sharp_instincts", "mind_reader")
        stats = get_db().execute(
            "SELECT total_points, current_streak FROM user_stats WHERE profile_id = ?", (profile,)
        ).fetchone()
        assert stats["total_points"] == 100
        assert stats["current_streak"] == 0
        season = get_season_for_date(date(2026, 9, 21))
        assert all(row["source_date"] == "2026-09-21" for row in get_badge_awards(profile, season["id"]))


def test_perfect_week_awards_high_roller_unicorn_and_collection_badge(app):
    with app.app_context():
        profile = _player()
        days = [
            ("mystery", "2026-09-21"), ("trivia", "2026-09-22"),
            ("word", "2026-09-23"), ("tick_tock", "2026-09-24"),
        ]
        collected = []
        for key, day in days:
            _seed(profile, key, day)
            collected.extend(award_saved_completion(profile, key, day))
        assert "high_roller" in collected
        assert "unicorn" in collected
        assert "badge_hunter" in collected
        assert "crew_legend" not in collected
        assert "season_champion" not in collected
        assert len(set(collected)) == len(collected)
        assert award_saved_completion(profile, "tick_tock", "2026-09-24") == ()


def test_backfill_preview_is_read_only_and_apply_is_idempotent(app):
    with app.app_context():
        profile = _player()
        _seed(profile, "trivia", "2026-09-22")
        season = get_season_for_date(date(2026, 9, 22))
        preview = replay_saved_badges(dry_run=True, profile_id=profile)
        assert preview["dry_run"] is True
        assert preview["new_awards"] == 3
        assert get_badge_awards(profile, season["id"]) == []
        applied = replay_saved_badges(dry_run=False, profile_id=profile)
        assert applied["new_awards"] == 3
        again = replay_saved_badges(dry_run=False, profile_id=profile)
        assert again["new_awards"] == 0


def test_completion_score_mismatch_does_not_award(app):
    with app.app_context():
        profile = _player()
        _seed(profile, "word", "2026-09-23")
        get_db().execute(
            "UPDATE game_completions SET score = 0 WHERE profile_id = ? AND game_key = 'word'",
            (profile,),
        )
        get_db().commit()
        import pytest
        with pytest.raises(ValueError, match="scores disagree"):
            award_saved_completion(profile, "word", "2026-09-23")


def test_real_mystery_archive_completion_returns_new_unlocks(app, client, monkeypatch):
    from app.mystery import routes as mystery_routes
    from app.db import get_profile_by_id

    profile = None
    with app.app_context():
        profile = _player()
        user = get_profile_by_id(profile)
        key = profile_user_key(profile)
    monkeypatch.setattr(
        mystery_routes, "get_puzzle",
        lambda day: {"theme": "Test", "answer": "Cinema", "clues": ["a", "b", "c", "d"]},
    )
    monkeypatch.setattr(
        mystery_routes, "is_correct_answer",
        lambda response, puzzle: response.casefold() == puzzle["answer"].casefold(),
    )
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = {
            "profile_id": profile, "username": user["username"], "avatar": user["avatar"],
            "role": user["role"], "user_key": key,
            "session_version": int(user["session_version"]),
        }
        csrf = session["csrf_token"]
    url = "/mystery/guess?date=2026-09-21"
    result = client.post(url, json={"answer": "Cinema"}, headers={"X-CSRFToken": csrf})
    assert result.status_code == 200
    assert result.json["completed"] is True
    assert result.json["badge_awards"] == ["case_closed", "sharp_instincts", "mind_reader"]
    assert result.json["stats"]["competitive"] is False
    duplicate = client.post(url, json={"answer": "Cinema"}, headers={"X-CSRFToken": csrf})
    assert duplicate.status_code == 409
    with app.app_context():
        season = get_season_for_date(date(2026, 9, 21))
        assert len(get_badge_awards(profile, season["id"])) == 3
