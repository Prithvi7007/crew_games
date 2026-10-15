"""CREW game attempts and completion scoring.

Conditional SQL writes and completion transactions live together; app.db
continues to expose the original public API for compatibility.
"""
import json
import time
from datetime import date

from app import db as store
from app.schedule import CREW_WEEK_ONE_DATE


def load_json_list(row, column):
    try:
        value = json.loads(row[column] or "[]")
    except (TypeError, json.JSONDecodeError):
        value = []
    return value if isinstance(value, list) else []


# ---------- Word ----------

def get_or_create_word_attempt(user_key, game_date):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM word_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO word_attempts (user_key, profile_id, game_date) VALUES (?, ?, ?) ON CONFLICT (profile_id, game_date) DO NOTHING",
        (user_key, profile_id, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM word_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def load_guesses(attempt_row):
    return load_json_list(attempt_row, "guesses_json")


def save_word_attempt(user_key, game_date, guesses, completed, won, score, *,
                      expected_guesses=None, commit=True):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    completed_at = store._db_timestamp() if completed else None
    guard = " AND guesses_json = ?" if expected_guesses is not None else ""
    params = (json.dumps(guesses), int(completed), int(won), score, completed_at,
              profile_id, game_date)
    if expected_guesses is not None:
        params += (json.dumps(expected_guesses),)
    cursor = db.execute(
        """
        UPDATE word_attempts
        SET guesses_json = ?, completed = ?, won = ?, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ? AND completed = 0
        """ + guard,
        params,
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise store.ConcurrentAttemptError("Wordle attempt changed in another request.")
    if commit:
        db.commit()


# ---------- Mystery ----------

def get_or_create_mystery_attempt(user_key, game_date):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM mystery_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO mystery_attempts (user_key, profile_id, game_date) VALUES (?, ?, ?) ON CONFLICT (profile_id, game_date) DO NOTHING",
        (user_key, profile_id, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM mystery_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def save_mystery_attempt(user_key, game_date, revealed_count, guesses, completed, won, score, *,
                         expected_guesses=None, expected_revealed_count=None, commit=True):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    completed_at = store._db_timestamp() if completed else None
    guard = ""
    params = (revealed_count, json.dumps(guesses), int(completed), int(won), score,
              completed_at, profile_id, game_date)
    if expected_guesses is not None:
        guard += " AND guesses_json = ?"
        params += (json.dumps(expected_guesses),)
    if expected_revealed_count is not None:
        guard += " AND revealed_count = ?"
        params += (int(expected_revealed_count),)
    cursor = db.execute(
        """
        UPDATE mystery_attempts
        SET revealed_count = ?, guesses_json = ?, completed = ?, won = ?, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ? AND completed = 0
        """ + guard,
        params,
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise store.ConcurrentAttemptError("Mystery attempt changed in another request.")
    if commit:
        db.commit()


# ---------- Trivia ----------

def get_or_create_trivia_attempt(user_key, game_date):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM trivia_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO trivia_attempts (user_key, profile_id, game_date) VALUES (?, ?, ?) ON CONFLICT (profile_id, game_date) DO NOTHING",
        (user_key, profile_id, game_date),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM trivia_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def save_trivia_attempt(user_key, game_date, answers, completed, score, *,
                        expected_answers=None, commit=True):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    completed_at = store._db_timestamp() if completed else None
    guard = " AND answers_json = ?" if expected_answers is not None else ""
    params = (json.dumps(answers), int(completed), score, completed_at, profile_id, game_date)
    if expected_answers is not None:
        params += (json.dumps(expected_answers),)
    cursor = db.execute(
        """
        UPDATE trivia_attempts
        SET answers_json = ?, completed = ?, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ? AND completed = 0
        """ + guard,
        params,
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise store.ConcurrentAttemptError("Trivia attempt changed in another request.")
    if commit:
        db.commit()


# ---------- Tick-Tock ----------

def get_or_create_tick_tock_attempt(user_key, game_date, target_seconds):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    row = db.execute(
        "SELECT * FROM tick_tock_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if row:
        return row
    db.execute(
        """
        INSERT INTO tick_tock_attempts (user_key, profile_id, game_date, target_seconds)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (profile_id, game_date) DO NOTHING
        """,
        (user_key, profile_id, game_date, target_seconds),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM tick_tock_attempts WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()

def start_tick_tock_attempt(user_key, game_date):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    started_at = time.time()
    cursor = db.execute(
        """
        UPDATE tick_tock_attempts
        SET started_at = ?, stopped_at = NULL, elapsed_seconds = NULL, difference_seconds = NULL
        WHERE profile_id = ? AND game_date = ? AND completed = 0 AND started_at IS NULL
        """,
        (started_at, profile_id, game_date),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise store.ConcurrentAttemptError("The timer has already started or finished.")
    db.commit()
    return started_at


def finish_tick_tock_attempt(user_key, game_date, elapsed_seconds, difference_seconds,
                             score, *, expected_started_at=None, commit=True):
    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    stopped_at = time.time()
    completed_at = store._db_timestamp()
    guard = " AND started_at = ?" if expected_started_at is not None else ""
    params = (stopped_at, elapsed_seconds, difference_seconds, score, completed_at,
              profile_id, game_date)
    if expected_started_at is not None:
        params += (expected_started_at,)
    cursor = db.execute(
        """
        UPDATE tick_tock_attempts
        SET stopped_at = ?, elapsed_seconds = ?, difference_seconds = ?,
            completed = 1, score = ?, completed_at = ?
        WHERE profile_id = ? AND game_date = ? AND completed = 0
        """ + guard,
        params,
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise store.ConcurrentAttemptError("The timer was already stopped or restarted.")
    if commit:
        db.commit()


# ---------- Shared progress / scoring ----------

def finalize_game_stats(user_key, game_key, game_date, score, won=True, competitive=True):
    """Record a completion once. All completions score; only timely ones affect streaks."""
    try:
        completion_day = date.fromisoformat(game_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid CREW game date") from exc
    if completion_day < CREW_WEEK_ONE_DATE:
        raise ValueError(
            f"CREW production scoring begins {CREW_WEEK_ONE_DATE.isoformat()}"
        )

    db = store.get_db()
    profile_id = store._profile_id_from_user_key(user_key)
    stats = store.ensure_user_stats(user_key)
    completed_at = store._db_timestamp()
    cursor = db.execute(
        """
        INSERT INTO game_completions (
            user_key, profile_id, game_key, game_date, score, won, completed_at, competitive
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (profile_id, game_key, game_date) DO NOTHING
        """,
        (user_key, profile_id, game_key, game_date, score, int(won), completed_at, int(bool(competitive))),
    )

    if cursor.rowcount == 0:
        return store.ensure_user_stats(user_key)

    word_points = score if game_key == "word" else 0
    word_completed = 1 if game_key == "word" else 0
    word_won = 1 if game_key == "word" and won else 0

    # Points and participation totals count for every completed game, including catch-up/archive play.
    db.execute(
        """
        UPDATE user_stats
        SET total_points = total_points + ?,
            games_completed = games_completed + 1,
            total_word_points = total_word_points + ?,
            word_games_completed = word_games_completed + ?,
            word_games_won = word_games_won + ?
        WHERE profile_id = ?
        """,
        (score, word_points, word_completed, word_won, profile_id),
    )

    # Streaks only use timely/current-week completions. Archive play cannot repair a missed streak.
    if competitive:
        completion_rows = db.execute(
            "SELECT DISTINCT game_date FROM game_completions WHERE profile_id = ? AND competitive = 1 ORDER BY game_date ASC",
            (profile_id,),
        ).fetchall()
        completion_days = []
        for item in completion_rows:
            try:
                completion_days.append(date.fromisoformat(item["game_date"]))
            except (TypeError, ValueError):
                continue
        current_streak, calculated_longest, last_completed_date = store._calculate_streaks(completion_days)
        longest_streak = max(int(stats["longest_streak"]), calculated_longest)
        db.execute(
            """
            UPDATE user_stats
            SET current_streak = ?,
                longest_streak = ?,
                last_completed_date = ?
            WHERE profile_id = ?
            """,
            (current_streak, longest_streak, last_completed_date, profile_id),
        )

    db.commit()
    return store.ensure_user_stats(user_key)

def finalize_word_stats(user_key, game_date, won, score, competitive=True):
    return finalize_game_stats(user_key, "word", game_date, score, won, competitive=competitive)


def get_game_completion(user_key, game_key, game_date):
    profile_id = store._profile_id_from_user_key(user_key)
    return store.get_db().execute(
        "SELECT * FROM game_completions WHERE profile_id = ? AND game_key = ? AND game_date = ?",
        (profile_id, game_key, game_date),
    ).fetchone()

