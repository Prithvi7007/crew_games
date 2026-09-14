from flask import Blueprint, abort, jsonify, render_template, request, session, url_for

from app.auth.routes import current_user_key, login_required
from app.db import finalize_game_stats, get_or_create_trivia_attempt, load_json_list, save_trivia_attempt
from app.schedule import game_is_competitive, game_is_in_archive, game_is_playable, parse_game_day
from .game import get_quiz

trivia_bp = Blueprint("trivia", __name__, url_prefix="/trivia")


def serialize_state(user_key, game_day):
    game_date = game_day.isoformat(); quiz = get_quiz(game_day); attempt = get_or_create_trivia_attempt(user_key, game_date)
    answers = load_json_list(attempt, "answers_json"); index = len(answers); completed = bool(attempt["completed"])
    state = {
        "date": game_date, "theme": quiz["theme"], "index": index, "total": len(quiz["questions"]),
        "score": int(attempt["score"]), "correct_count": sum(1 for a in answers if a.get("correct")),
        "completed": completed, "answers": answers, "playable": game_is_playable(game_day),
        "competitive": game_is_competitive(game_day), "archive": game_is_playable(game_day) and not game_is_competitive(game_day),
    }
    if not completed and index < len(quiz["questions"]):
        q = quiz["questions"][index]; state["question"] = {"prompt": q["prompt"], "options": list(q["options"])}
    return state


def _day():
    game_day = parse_game_day("trivia", request.args.get("date"))
    if request.args.get("date") and not game_is_in_archive(game_day):
        abort(404)
    return game_day


@trivia_bp.get("")
@login_required
def play():
    game_day = _day()
    return render_template("trivia.html", user=session["user"], game_day=game_day, state=serialize_state(current_user_key(), game_day),
                           return_url=url_for("main.games", week=game_day.isoformat()) if request.args.get("date") else url_for("main.home"))


@trivia_bp.post("/answer")
@login_required
def answer():
    user_key = current_user_key(); game_day = _day(); game_date = game_day.isoformat()
    if not game_is_playable(game_day): return jsonify({"ok": False, "message": "This challenge has not opened yet."}), 403
    quiz = get_quiz(game_day); attempt = get_or_create_trivia_attempt(user_key, game_date); answers = load_json_list(attempt, "answers_json")
    if attempt["completed"]: return jsonify({"ok": False, "message": "Trivia Tuesday is already complete.", "state": serialize_state(user_key, game_day)}), 409
    try: selected = int((request.get_json(silent=True) or {}).get("selected"))
    except (TypeError, ValueError): return jsonify({"ok": False, "message": "Choose an answer first."}), 400
    index = len(answers)
    if index >= len(quiz["questions"]): return jsonify({"ok": False, "message": "No questions remaining."}), 409
    question = quiz["questions"][index]
    if selected < 0 or selected >= len(question["options"]): return jsonify({"ok": False, "message": "That answer choice is invalid."}), 400
    correct = selected == question["answer"]; answers.append({"question": index, "selected": selected, "correct": correct})
    completed = len(answers) == len(quiz["questions"]); score = sum(10 for item in answers if item["correct"]) if completed else 0
    save_trivia_attempt(user_key, game_date, answers, completed, score)
    stats = None
    if completed:
        row = finalize_game_stats(user_key, "trivia", game_date, score, True, competitive=game_is_competitive(game_day))
        stats = {"streak": row["current_streak"], "total_points": row["total_points"], "competitive": game_is_competitive(game_day)}
    return jsonify({"ok": True, "correct": correct, "correct_index": question["answer"], "correct_answer": question["options"][question["answer"]],
                    "completed": completed, "stats": stats, "state": serialize_state(user_key, game_day)})
