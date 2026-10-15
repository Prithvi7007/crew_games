"""Behavioral regressions for server-private solutions and stale game writes."""
from datetime import date

import pytest

from app.db import (
    ConcurrentAttemptError,
    create_profile,
    get_db,
    get_or_create_word_attempt,
    get_or_create_trivia_attempt,
    get_or_create_mystery_attempt,
    load_guesses,
    profile_user_key,
    save_word_attempt,
    save_trivia_attempt,
    save_mystery_attempt,
)
from app.word.game import get_daily_solution


def _player():
    from werkzeug.security import generate_password_hash
    p = create_profile(
        "ReliabilityGuard", generate_password_hash("long-passphrase-for-test"),
        "⭐", generate_password_hash("long-recovery-for-test"),
    )
    return profile_user_key(int(p["id"]))


def test_wordle_selects_future_solution_with_server_randomness_once(app, monkeypatch):
    with app.app_context():
        # The fixed daily modulo algorithm can't pass this: no random choice.
        monkeypatch.setattr("app.word.game.secrets.choice", lambda items: "MAGIC")
        day = date(2027, 1, 6)
        assert get_daily_solution(day) == "MAGIC"
        monkeypatch.setattr("app.word.game.secrets.choice", lambda items: "QUEST")
        assert get_daily_solution(day) == "MAGIC"
        assert get_db().execute(
            "SELECT solution FROM word_games WHERE game_date = ?", (day.isoformat(),)
        ).fetchone()["solution"] == "MAGIC"


def test_wordle_conflicting_guess_is_rejected_without_overwriting(app):
    with app.app_context():
        user = _player()
        get_or_create_word_attempt(user, "2026-10-14")
        save_word_attempt(user, "2026-10-14", ["MAGIC"], False, False, 0,
                          expected_guesses=[])
        with pytest.raises(ConcurrentAttemptError):
            save_word_attempt(user, "2026-10-14", ["QUEST"], False, False, 0,
                              expected_guesses=[])
        row = get_or_create_word_attempt(user, "2026-10-14")
        assert load_guesses(row) == ["MAGIC"]


def test_trivia_and_mystery_stale_progress_cannot_overwrite(app):
    with app.app_context():
        user = _player()
        day = "2026-10-13"
        get_or_create_trivia_attempt(user, day)
        first = [{"question": 0, "selected": 1, "correct": True}]
        save_trivia_attempt(user, day, first, False, 0, expected_answers=[])
        with pytest.raises(ConcurrentAttemptError):
            save_trivia_attempt(user, day, [{"question": 0, "selected": 2, "correct": False}],
                                False, 0, expected_answers=[])
        assert get_db().execute(
            "SELECT answers_json FROM trivia_attempts WHERE game_date = ?",
            (day,),
        ).fetchone()["answers_json"] == __import__("json").dumps(first)

        day = "2026-10-12"
        get_or_create_mystery_attempt(user, day)
        save_mystery_attempt(user, day, 2, [], False, False, 0,
                            expected_guesses=[], expected_revealed_count=1)
        with pytest.raises(ConcurrentAttemptError):
            save_mystery_attempt(user, day, 2, [], False, False, 0,
                                expected_guesses=[], expected_revealed_count=1)
        assert get_or_create_mystery_attempt(user, day)["revealed_count"] == 2
