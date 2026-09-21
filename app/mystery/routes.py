from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from app.auth.routes import current_user_key, login_required
from app.db import finalize_game_stats, get_or_create_mystery_attempt, load_json_list, save_mystery_attempt
from app.schedule import game_is_archive, game_is_competitive, game_is_in_archive, game_is_playable, parse_game_day
from .game import get_puzzle, is_correct_answer, score_for_clues

mystery_bp = Blueprint("mystery", __name__, url_prefix="/mystery")


def serialize_state(user_key, game_day):
    game_date = game_day.isoformat()
    puzzle = get_puzzle(game_day)
    attempt = get_or_create_mystery_attempt(user_key, game_date)
    guesses = load_json_list(attempt, "guesses_json")
    revealed_count = max(1, min(len(puzzle["clues"]), int(attempt["revealed_count"])))
    playable = game_is_playable(game_day)
    competitive = game_is_competitive(game_day)
    state = {
        "date": game_date,
        "theme": puzzle["theme"],
        "revealed_count": revealed_count,
        "total_clues": len(puzzle["clues"]),
        "clues": list(puzzle["clues"][:revealed_count]),
        "guesses": guesses,
        "completed": bool(attempt["completed"]),
        "won": bool(attempt["won"]),
        "score": int(attempt["score"]),
        "potential_score": score_for_clues(revealed_count, len(puzzle["clues"])),
        "playable": playable,
        "competitive": competitive,
        "archive": game_is_archive(game_day),
    }
    if state["completed"]:
        state["answer"] = puzzle["answer"]
    return state


def _day():
    game_day = parse_game_day("mystery", request.args.get("date"))
    if request.args.get("date") and not game_is_in_archive(game_day):
        abort(404)
    return game_day


@mystery_bp.get("")
@login_required
def play():
    user = session["user"]
    game_day = _day()
    if not game_is_playable(game_day):
        return redirect(url_for("main.games"))
    return render_template(
        "mystery.html", user=user, game_day=game_day,
        state=serialize_state(current_user_key(), game_day),
        return_url=url_for("main.games", week=game_day.isoformat()) if request.args.get("date") else url_for("main.home"),
    )


@mystery_bp.post("/reveal")
@login_required
def reveal():
    user_key = current_user_key(); game_day = _day(); game_date = game_day.isoformat()
    if not game_is_playable(game_day):
        return jsonify({"ok": False, "message": "This challenge has not opened yet."}), 403
    puzzle = get_puzzle(game_day); attempt = get_or_create_mystery_attempt(user_key, game_date)
    if attempt["completed"]:
        return jsonify({"ok": False, "message": "Mystery Monday is already complete.", "state": serialize_state(user_key, game_day)}), 409
    revealed_count = int(attempt["revealed_count"])
    if revealed_count >= len(puzzle["clues"]):
        return jsonify({"ok": False, "message": "All clues are already revealed."}), 400
    revealed_count += 1
    save_mystery_attempt(user_key, game_date, revealed_count, load_json_list(attempt, "guesses_json"), False, False, 0)
    return jsonify({"ok": True, "state": serialize_state(user_key, game_day)})


@mystery_bp.post("/guess")
@login_required
def guess():
    user_key = current_user_key(); game_day = _day(); game_date = game_day.isoformat()
    if not game_is_playable(game_day):
        return jsonify({"ok": False, "message": "This challenge has not opened yet."}), 403
    puzzle = get_puzzle(game_day); attempt = get_or_create_mystery_attempt(user_key, game_date)
    if attempt["completed"]:
        return jsonify({"ok": False, "message": "Mystery Monday is already complete.", "state": serialize_state(user_key, game_day)}), 409
    answer = (request.get_json(silent=True) or {}).get("answer", "").strip()
    if not answer or len(answer) > 80:
        return jsonify({"ok": False, "message": "Enter your mystery answer first."}), 400
    guesses = load_json_list(attempt, "guesses_json"); revealed_count = int(attempt["revealed_count"])
    won = is_correct_answer(answer, puzzle); guesses.append({"answer": answer, "correct": won, "clue": revealed_count})
    if won:
        score, completed = score_for_clues(revealed_count, len(puzzle["clues"])), True
    elif revealed_count >= len(puzzle["clues"]):
        score, completed = 10, True
    else:
        score, completed, revealed_count = 0, False, revealed_count + 1
    save_mystery_attempt(user_key, game_date, revealed_count, guesses, completed, won, score)
    stats = None
    if completed:
        row = finalize_game_stats(user_key, "mystery", game_date, score, won, competitive=game_is_competitive(game_day))
        stats = {"streak": row["current_streak"], "total_points": row["total_points"], "competitive": game_is_competitive(game_day)}
    return jsonify({
        "ok": True, "correct": won, "completed": completed,
        "message": "Mystery solved." if won else ("Mystery closed." if completed else "Not quite — another clue just unlocked."),
        "stats": stats, "state": serialize_state(user_key, game_day),
    })
