from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from app.auth.routes import current_user_key, login_required
from app.db import ensure_user_stats, finalize_word_stats, get_game_content, get_or_create_word_attempt, load_guesses, save_word_attempt
from app.schedule import game_is_archive, game_is_competitive, game_is_in_archive, game_is_playable, parse_game_day
from .game import evaluate_guess, get_daily_solution, score_for_result, validate_guess

word_bp = Blueprint("word", __name__, url_prefix="/word")


def serialize_state(user_key, game_day):
    game_date = game_day.isoformat(); solution = get_daily_solution(game_day); scheduled = get_game_content("word", game_date, published_only=True)
    attempt = get_or_create_word_attempt(user_key, game_date); guesses = load_guesses(attempt)
    evaluated = [{"guess": guess, "tiles": evaluate_guess(guess, solution)} for guess in guesses]
    state = {
        "date": game_date, "guesses": evaluated, "guess_count": len(guesses), "max_guesses": 6,
        "completed": bool(attempt["completed"]), "won": bool(attempt["won"]), "score": int(attempt["score"]),
        "potential_score": score_for_result(len(guesses) + 1, True) if not attempt["completed"] else int(attempt["score"]),
        "theme": scheduled["theme_label"] if scheduled else "", "playable": game_is_playable(game_day),
        "competitive": game_is_competitive(game_day), "archive": game_is_archive(game_day),
    }
    if state["completed"]: state["solution"] = solution
    return state


def _day():
    game_day = parse_game_day("word", request.args.get("date"))
    if request.args.get("date") and not game_is_in_archive(game_day):
        abort(404)
    return game_day


@word_bp.get("")
@login_required
def play():
    game_day = _day()
    if not game_is_playable(game_day):
        return redirect(url_for("main.games"))
    ensure_user_stats(current_user_key()); state = serialize_state(current_user_key(), game_day)
    return render_template("word.html", user=session["user"], today=game_day, state=state,
                           return_url=url_for("main.games", week=game_day.isoformat()) if request.args.get("date") else url_for("main.home"))


@word_bp.post("/guess")
@login_required
def submit_guess():
    user_key = current_user_key(); payload = request.get_json(silent=True) or {}; game_day = _day()
    if not game_is_playable(game_day): return jsonify({"ok": False, "message": "This challenge has not opened yet."}), 403
    is_valid, normalized = validate_guess(payload.get("guess"), game_day)
    if not is_valid: return jsonify({"ok": False, "message": normalized}), 400
    game_date = game_day.isoformat(); solution = get_daily_solution(game_day); attempt = get_or_create_word_attempt(user_key, game_date); guesses = load_guesses(attempt)
    if attempt["completed"]: return jsonify({"ok": False, "message": "Wordle Wednesday is already complete.", "state": serialize_state(user_key, game_day)}), 409
    if normalized in guesses: return jsonify({"ok": False, "message": "You already tried that word."}), 400
    if len(guesses) >= 6: return jsonify({"ok": False, "message": "No guesses remaining."}), 409
    guesses.append(normalized); tiles = evaluate_guess(normalized, solution); won = normalized == solution; completed = won or len(guesses) == 6
    score = score_for_result(len(guesses), won) if completed else 0
    save_word_attempt(user_key, game_date, guesses, completed, won, score)
    stats = None
    if completed:
        row = finalize_word_stats(user_key, game_date, won, score, competitive=game_is_competitive(game_day))
        stats = {"streak": row["current_streak"], "longest_streak": row["longest_streak"], "total_word_points": row["total_word_points"], "competitive": game_is_competitive(game_day)}
    response = {"ok": True, "guess": normalized, "tiles": tiles, "guess_count": len(guesses), "remaining": 6-len(guesses),
                "completed": completed, "won": won, "score": score,
                "potential_score": score_for_result(len(guesses)+1, True) if not completed else score, "stats": stats}
    if completed: response["solution"] = solution
    return jsonify(response)
