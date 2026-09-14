from datetime import date, timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.auth.routes import current_user_key, login_required
from app.db import (
    ensure_user_stats,
    get_game_attempt_summary,
    get_game_completion,
    get_game_content,
    get_home_leaderboard,
    get_leaderboard,
    get_weekly_points,
)
from app.schedule import ARCHIVE_START_DATE, GAME_DEFINITIONS, crew_today, get_game_date, get_week_start

main_bp = Blueprint("main", __name__)


def _week_label(monday):
    thursday = monday + timedelta(days=3)
    if monday.month == thursday.month:
        return f"{monday.strftime('%b')} {monday.day}–{thursday.day}, {monday.year}"
    return f"{monday.strftime('%b %d')}–{thursday.strftime('%b %d')}, {monday.year}"


def _requested_week():
    raw = request.args.get("week", "")
    try:
        selected = date.fromisoformat(raw) if raw else crew_today()
    except ValueError:
        selected = crew_today()
    monday = get_week_start(selected)
    current = get_week_start(crew_today())
    archive_start = get_week_start(ARCHIVE_START_DATE)
    return max(archive_start, min(monday, current))


@main_bp.get("/")
def index():
    session.clear()
    return redirect(url_for("auth.login"))


@main_bp.get("/home")
@login_required
def home():
    user = session["user"]
    user_key = current_user_key()
    today = crew_today()
    stats_row = ensure_user_stats(user_key)
    weekly = get_weekly_points(user_key, today)

    games = []
    for definition in GAME_DEFINITIONS:
        item = dict(definition)
        game_day = get_game_date(item["key"], today)
        summary = get_game_attempt_summary(user_key, item["key"], game_day.isoformat())
        item.update(summary)
        scheduled_content = get_game_content(item["key"], game_day.isoformat(), published_only=True)
        item["theme_label"] = scheduled_content["theme_label"] if scheduled_content else ""
        item["date"] = game_day
        item["url"] = url_for(item["endpoint"])

        if item["completed"]:
            item["status"] = "completed"; item["cta"] = "View result"; item["journey_label"] = f"Completed · {item['score']} pts"
        elif game_day == today:
            item["status"] = "live"; item["cta"] = "Continue" if item["started"] else "Play today"; item["journey_label"] = "Today"
        elif game_day < today:
            item["status"] = "available"; item["cta"] = "Catch up"; item["journey_label"] = "Available"
        else:
            item["status"] = "upcoming"; item["cta"] = "Preview"; item["journey_label"] = item["date"].strftime("%b %d").upper()
        games.append(item)

    todays_game = next((game for game in games if game["date"] == today), None)
    weekday = today.weekday()
    home_phase = "play" if weekday <= 3 else ("recap" if weekday == 4 else "weekend")
    next_week_start = get_week_start(today) + timedelta(days=7)

    ranked_players = get_home_leaderboard(today, current_profile_id=user["profile_id"])
    me = next((player for player in ranked_players if player["me"]), None)
    my_rank = me["rank"] if me else None
    leaderboard = [player for player in ranked_players if player["rank"] <= 3]
    if me and all(player["profile_id"] != me["profile_id"] for player in leaderboard):
        leaderboard = [*leaderboard, me]

    stats = {
        "streak": stats_row["current_streak"], "rank": my_rank, "weekly_points": weekly["points"],
        "games_completed": weekly["completed"], "progress_percent": min(100, round((weekly["points"] / 400) * 100)),
    }
    return render_template("home.html", today=today, stats=stats, games=games, todays_game=todays_game,
                           home_phase=home_phase, next_week_start=next_week_start, leaderboard=leaderboard, user=user)


@main_bp.get("/games")
@login_required
def games():
    user = session["user"]; user_key = current_user_key(); today = crew_today(); monday = _requested_week(); current_monday = get_week_start(today)
    items = []
    for definition in GAME_DEFINITIONS:
        item = dict(definition); game_day = monday + timedelta(days=item["weekday"]); game_date = game_day.isoformat()
        summary = get_game_attempt_summary(user_key, item["key"], game_date); completion = get_game_completion(user_key, item["key"], game_date)
        content = get_game_content(item["key"], game_date, published_only=True)
        item.update(summary); item["date"] = game_day; item["theme_label"] = content["theme_label"] if content else ""
        item["url"] = url_for(item["endpoint"], date=game_date)
        if completion:
            item["completed"] = True
            item["status"] = "completed-live" if int(completion["competitive"]) else "completed-archive"
            item["status_label"] = "Completed live" if int(completion["competitive"]) else "Completed later"
            item["action"] = "View result"; item["score"] = int(completion["score"])
        elif game_day > today:
            item["status"] = "upcoming"; item["status_label"] = "Upcoming"; item["action"] = "Preview"
        elif summary["started"]:
            item["status"] = "in-progress"; item["status_label"] = "In progress"; item["action"] = "Continue"
        elif monday == current_monday and today.weekday() <= 3:
            item["status"] = "available"; item["status_label"] = "Available"; item["action"] = "Play"
        else:
            item["status"] = "missed"; item["status_label"] = "Missed"; item["action"] = "Play from archive"
        items.append(item)

    previous_week = monday - timedelta(days=7); next_week = monday + timedelta(days=7)
    if previous_week < get_week_start(ARCHIVE_START_DATE):
        previous_week = None
    return render_template("games.html", user=user, games=items, week_start=monday, week_label=_week_label(monday),
                           previous_week=previous_week, next_week=next_week if next_week <= current_monday else None,
                           is_current=monday == current_monday)


@main_bp.get("/leaderboard")
@login_required
def leaderboard():
    period = request.args.get("period", "this_week"); game = request.args.get("game", "all")
    board = get_leaderboard(period, game, current_profile_id=session["user"]["profile_id"])
    return render_template("leaderboard.html", user=session["user"], board=board, selected_period=period, selected_game=game)


@main_bp.get("/api/leaderboard")
@login_required
def leaderboard_api():
    period = request.args.get("period", "this_week"); game = request.args.get("game", "all")
    return jsonify(get_leaderboard(period, game, current_profile_id=session["user"]["profile_id"]))
