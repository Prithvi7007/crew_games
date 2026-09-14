import time
from flask import Blueprint, abort, jsonify, render_template, request, session, url_for

from app.auth.routes import current_user_key, login_required
from app.db import finalize_game_stats, finish_tick_tock_attempt, get_or_create_tick_tock_attempt, start_tick_tock_attempt
from app.schedule import game_is_competitive, game_is_in_archive, game_is_playable, parse_game_day
from .game import get_target, get_timer_config, score_for_difference

tick_tock_bp = Blueprint("tick_tock", __name__, url_prefix="/tick-tock")


def serialize_state(user_key, game_day):
    game_date = game_day.isoformat(); config = get_timer_config(game_day); target = config["target"]
    attempt = get_or_create_tick_tock_attempt(user_key, game_date, target)
    signed_difference = None
    if attempt["elapsed_seconds"] is not None:
        signed_difference = float(attempt["elapsed_seconds"]) - float(attempt["target_seconds"])
    return {
        "date": game_date, "target": float(attempt["target_seconds"]), "started": bool(attempt["started_at"]),
        "completed": bool(attempt["completed"]), "score": int(attempt["score"]), "elapsed": attempt["elapsed_seconds"],
        "difference": attempt["difference_seconds"], "signed_difference": signed_difference, "theme": config["theme"],
        "playable": game_is_playable(game_day), "competitive": game_is_competitive(game_day),
        "archive": game_is_playable(game_day) and not game_is_competitive(game_day),
    }


def _day():
    game_day = parse_game_day("tick_tock", request.args.get("date"))
    if request.args.get("date") and not game_is_in_archive(game_day):
        abort(404)
    return game_day


@tick_tock_bp.get("")
@login_required
def play():
    game_day = _day()
    return render_template("tick_tock.html", user=session["user"], game_day=game_day, state=serialize_state(current_user_key(), game_day),
                           return_url=url_for("main.games", week=game_day.isoformat()) if request.args.get("date") else url_for("main.home"))


@tick_tock_bp.post("/start")
@login_required
def start():
    user_key = current_user_key(); game_day = _day(); game_date = game_day.isoformat()
    if not game_is_playable(game_day): return jsonify({"ok": False, "message": "This challenge has not opened yet."}), 403
    target = get_target(game_day); attempt = get_or_create_tick_tock_attempt(user_key, game_date, target)
    if attempt["completed"]: return jsonify({"ok": False, "message": "Tick-Tock Thursday is already complete.", "state": serialize_state(user_key, game_day)}), 409
    if attempt["started_at"]: return jsonify({"ok": False, "message": "The hidden timer is already running.", "state": serialize_state(user_key, game_day)}), 409
    start_tick_tock_attempt(user_key, game_date); return jsonify({"ok": True, "state": serialize_state(user_key, game_day)})


@tick_tock_bp.post("/stop")
@login_required
def stop():
    user_key = current_user_key(); game_day = _day(); game_date = game_day.isoformat()
    if not game_is_playable(game_day): return jsonify({"ok": False, "message": "This challenge has not opened yet."}), 403
    target = get_target(game_day); attempt = get_or_create_tick_tock_attempt(user_key, game_date, target)
    if attempt["completed"]: return jsonify({"ok": False, "message": "Tick-Tock Thursday is already complete.", "state": serialize_state(user_key, game_day)}), 409
    if not attempt["started_at"]: return jsonify({"ok": False, "message": "Start the timer first."}), 400
    elapsed = max(0.0, time.time() - float(attempt["started_at"])); difference = abs(elapsed - float(attempt["target_seconds"])); score = score_for_difference(difference)
    finish_tick_tock_attempt(user_key, game_date, elapsed, difference, score)
    row = finalize_game_stats(user_key, "tick_tock", game_date, score, True, competitive=game_is_competitive(game_day))
    return jsonify({"ok": True, "stats": {"streak": row["current_streak"], "total_points": row["total_points"], "competitive": game_is_competitive(game_day)}, "state": serialize_state(user_key, game_day)})
