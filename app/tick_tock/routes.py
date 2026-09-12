import time
from flask import Blueprint, jsonify, render_template, session

from app.auth.routes import current_user_key, login_required
from app.db import finalize_game_stats, finish_tick_tock_attempt, get_or_create_tick_tock_attempt, start_tick_tock_attempt
from app.schedule import get_game_date
from .game import get_target, get_timer_config, score_for_difference


tick_tock_bp = Blueprint("tick_tock", __name__, url_prefix="/tick-tock")


def serialize_state(user_key):
    game_day = get_game_date("tick_tock")
    game_date = game_day.isoformat()
    config = get_timer_config(game_day)
    target = config["target"]
    attempt = get_or_create_tick_tock_attempt(user_key, game_date, target)
    return {
        "date": game_date,
        "target": float(attempt["target_seconds"]),
        "started": bool(attempt["started_at"]),
        "completed": bool(attempt["completed"]),
        "score": int(attempt["score"]),
        "elapsed": attempt["elapsed_seconds"],
        "difference": attempt["difference_seconds"],
        "theme": config["theme"],
    }


@tick_tock_bp.get("")
@login_required
def play():
    user = session["user"]
    game_day = get_game_date("tick_tock")
    return render_template("tick_tock.html", user=user, game_day=game_day, state=serialize_state(current_user_key()))


@tick_tock_bp.post("/start")
@login_required
def start():
    user_key = current_user_key()
    game_day = get_game_date("tick_tock")
    game_date = game_day.isoformat()
    target = get_target(game_day)
    attempt = get_or_create_tick_tock_attempt(user_key, game_date, target)
    if attempt["completed"]:
        return jsonify({"ok": False, "message": "Tick-Tock Thursday is already complete.", "state": serialize_state(user_key)}), 409
    if attempt["started_at"]:
        return jsonify({"ok": False, "message": "The hidden timer is already running.", "state": serialize_state(user_key)}), 409
    start_tick_tock_attempt(user_key, game_date)
    return jsonify({"ok": True, "state": serialize_state(user_key)})


@tick_tock_bp.post("/stop")
@login_required
def stop():
    user_key = current_user_key()
    game_day = get_game_date("tick_tock")
    game_date = game_day.isoformat()
    target = get_target(game_day)
    attempt = get_or_create_tick_tock_attempt(user_key, game_date, target)
    if attempt["completed"]:
        return jsonify({"ok": False, "message": "Tick-Tock Thursday is already complete.", "state": serialize_state(user_key)}), 409
    if not attempt["started_at"]:
        return jsonify({"ok": False, "message": "Start the timer first."}), 400

    elapsed = max(0.0, time.time() - float(attempt["started_at"]))
    difference = abs(elapsed - float(attempt["target_seconds"]))
    score = score_for_difference(difference)
    finish_tick_tock_attempt(user_key, game_date, elapsed, difference, score)
    row = finalize_game_stats(user_key, "tick_tock", game_date, score, True)
    return jsonify({
        "ok": True,
        "stats": {"streak": row["current_streak"], "total_points": row["total_points"]},
        "state": serialize_state(user_key),
    })
