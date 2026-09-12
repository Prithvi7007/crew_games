from datetime import date

from flask import Blueprint, jsonify, render_template, request, session

from app.auth.routes import current_user_key, login_required
from app.db import (
    ensure_user_stats,
    finalize_word_stats,
    get_or_create_word_attempt,
    load_guesses,
    save_word_attempt,
)
from .game import evaluate_guess, get_daily_solution, score_for_result, validate_guess
from app.schedule import get_game_date


word_bp = Blueprint("word", __name__, url_prefix="/word")


def serialize_state(user_key):
    game_day = get_game_date("word")
    game_date = game_day.isoformat()
    solution = get_daily_solution(game_day)
    from app.db import get_game_content
    scheduled = get_game_content("word", game_date, published_only=True)
    attempt = get_or_create_word_attempt(user_key, game_date)
    guesses = load_guesses(attempt)

    evaluated = [
        {"guess": guess, "tiles": evaluate_guess(guess, solution)}
        for guess in guesses
    ]

    state = {
        "date": game_date,
        "guesses": evaluated,
        "guess_count": len(guesses),
        "max_guesses": 6,
        "completed": bool(attempt["completed"]),
        "won": bool(attempt["won"]),
        "score": attempt["score"],
        "potential_score": score_for_result(len(guesses) + 1, True) if not attempt["completed"] else attempt["score"],
        "theme": scheduled["theme_label"] if scheduled else "",
    }
    if state["completed"]:
        state["solution"] = solution
    return state


@word_bp.get("")
@login_required
def play():
    user = session["user"]
    ensure_user_stats(current_user_key())
    state = serialize_state(current_user_key())
    return render_template(
        "word.html",
        user=user,
        today=get_game_date("word"),
        state=state,
    )


@word_bp.post("/guess")
@login_required
def submit_guess():
    user_key = current_user_key()
    payload = request.get_json(silent=True) or {}
    game_day = get_game_date("word")
    is_valid, normalized = validate_guess(payload.get("guess"), game_day)
    if not is_valid:
        return jsonify({"ok": False, "message": normalized}), 400

    game_date = game_day.isoformat()
    solution = get_daily_solution(game_day)
    attempt = get_or_create_word_attempt(user_key, game_date)
    guesses = load_guesses(attempt)

    if attempt["completed"]:
        return jsonify({"ok": False, "message": "Wordle Wednesday is already complete.", "state": serialize_state(user_key)}), 409
    if normalized in guesses:
        return jsonify({"ok": False, "message": "You already tried that word."}), 400
    if len(guesses) >= 6:
        return jsonify({"ok": False, "message": "No guesses remaining."}), 409

    guesses.append(normalized)
    tiles = evaluate_guess(normalized, solution)
    won = normalized == solution
    completed = won or len(guesses) == 6
    score = score_for_result(len(guesses), won) if completed else 0

    save_word_attempt(
        user_key=user_key,
        game_date=game_date,
        guesses=guesses,
        completed=completed,
        won=won,
        score=score,
    )

    stats = None
    if completed:
        stats_row = finalize_word_stats(user_key, game_date, won, score)
        stats = {
            "streak": stats_row["current_streak"],
            "longest_streak": stats_row["longest_streak"],
            "total_word_points": stats_row["total_word_points"],
        }

    response = {
        "ok": True,
        "guess": normalized,
        "tiles": tiles,
        "guess_count": len(guesses),
        "remaining": 6 - len(guesses),
        "completed": completed,
        "won": won,
        "score": score,
        "potential_score": score_for_result(len(guesses) + 1, True) if not completed else score,
        "stats": stats,
    }
    if completed:
        response["solution"] = solution

    return jsonify(response)
