from flask import Blueprint, jsonify, render_template, request, session

from app.auth.routes import current_user_key, login_required
from app.db import finalize_game_stats, get_or_create_trivia_attempt, load_json_list, save_trivia_attempt
from app.schedule import get_game_date
from .game import get_quiz

trivia_bp = Blueprint("trivia", __name__, url_prefix="/trivia")


def serialize_state(user_key):
    game_day = get_game_date("trivia")
    game_date = game_day.isoformat()
    quiz = get_quiz(game_day)
    attempt = get_or_create_trivia_attempt(user_key, game_date)
    answers = load_json_list(attempt, "answers_json")
    index = len(answers)
    completed = bool(attempt["completed"])

    state = {
        "date": game_date,
        "theme": quiz["theme"],
        "index": index,
        "total": len(quiz["questions"]),
        "score": int(attempt["score"]),
        "correct_count": sum(1 for answer in answers if answer.get("correct")),
        "completed": completed,
        "answers": answers,
    }
    if not completed and index < len(quiz["questions"]):
        question = quiz["questions"][index]
        state["question"] = {"prompt": question["prompt"], "options": list(question["options"])}
    return state


@trivia_bp.get("")
@login_required
def play():
    user = session["user"]
    game_day = get_game_date("trivia")
    return render_template("trivia.html", user=user, game_day=game_day, state=serialize_state(current_user_key()))


@trivia_bp.post("/answer")
@login_required
def answer():
    user_key = current_user_key()
    game_day = get_game_date("trivia")
    game_date = game_day.isoformat()
    quiz = get_quiz(game_day)
    attempt = get_or_create_trivia_attempt(user_key, game_date)
    answers = load_json_list(attempt, "answers_json")

    if attempt["completed"]:
        return jsonify({"ok": False, "message": "Trivia Tuesday is already complete.", "state": serialize_state(user_key)}), 409

    index = len(answers)
    payload = request.get_json(silent=True) or {}
    try:
        selected = int(payload.get("selected"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Choose an answer first."}), 400

    if index >= len(quiz["questions"]):
        return jsonify({"ok": False, "message": "No questions remaining."}), 409
    question = quiz["questions"][index]
    if selected < 0 or selected >= len(question["options"]):
        return jsonify({"ok": False, "message": "That answer choice is invalid."}), 400

    correct = selected == question["answer"]
    answers.append({"question": index, "selected": selected, "correct": correct})
    completed = len(answers) == len(quiz["questions"])
    score = sum(10 for item in answers if item["correct"]) if completed else 0
    save_trivia_attempt(user_key, game_date, answers, completed, score)

    stats = None
    if completed:
        row = finalize_game_stats(user_key, "trivia", game_date, score, True)
        stats = {"streak": row["current_streak"], "total_points": row["total_points"]}

    return jsonify({
        "ok": True,
        "correct": correct,
        "correct_index": question["answer"],
        "correct_answer": question["options"][question["answer"]],
        "completed": completed,
        "stats": stats,
        "state": serialize_state(user_key),
    })
