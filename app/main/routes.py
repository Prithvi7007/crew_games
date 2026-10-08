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
    get_season_for_date,
    get_season_summary,
    get_weekly_points,
    list_seasons,
)
from app.schedule import (
    ARCHIVE_START_DATE,
    GAME_DEFINITIONS,
    crew_today,
    get_crew_week_number,
    get_game_date,
    get_week_start,
)

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
    season = get_season_summary(user_key, today)

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
    return render_template(
        "home.html",
        today=today,
        stats=stats,
        games=games,
        todays_game=todays_game,
        home_phase=home_phase,
        next_week_start=next_week_start,
        leaderboard=leaderboard,
        user=user,
        week_number=get_crew_week_number(today),
        season=season,
        nav_points=weekly["points"],
    )


@main_bp.get("/games")
@login_required
def games():
    user = session["user"]
    user_key = current_user_key()
    today = crew_today()
    current_monday = get_week_start(today)
    season = get_season_for_date(today)
    nav_points = get_weekly_points(user_key, today)["points"]

    if season:
        first_monday = get_week_start(season["start_date"])
        last_monday = get_week_start(season["end_date"])
    else:
        first_monday = get_week_start(ARCHIVE_START_DATE)
        last_monday = current_monday

    weeks = []
    monday = first_monday
    week_number = 1

    while monday <= last_monday:
        items = []
        for definition in GAME_DEFINITIONS:
            item = dict(definition)
            game_day = monday + timedelta(days=item["weekday"])
            game_date = game_day.isoformat()
            summary = get_game_attempt_summary(user_key, item["key"], game_date)
            completion = get_game_completion(user_key, item["key"], game_date)
            content = get_game_content(item["key"], game_date, published_only=True) if game_day <= today else None

            item.update(summary)
            item["date"] = game_day
            item["theme_label"] = content["theme_label"] if content else ""
            item["url"] = url_for(item["endpoint"], date=game_date)

            if completion:
                item["completed"] = True
                item["status"] = "completed"
                item["status_label"] = "Completed"
                item["action"] = "View result"
                item["score"] = int(completion["score"])
            elif game_day > today:
                item["status"] = "upcoming"
                item["status_label"] = "Locked"
                item["action"] = "Locked"
            elif summary["started"]:
                item["status"] = "in-progress"
                item["status_label"] = "In progress"
                item["action"] = "Continue"
            elif monday == current_monday:
                item["status"] = "available"
                item["status_label"] = "Available"
                item["action"] = "Play"
            else:
                item["status"] = "missed"
                item["status_label"] = "Available"
                item["action"] = "Play from archive"

            items.append(item)

        weeks.append({
            "number": week_number,
            "start": monday,
            "label": _week_label(monday),
            "games": items,
            "is_current": monday == current_monday,
        })
        monday += timedelta(days=7)
        week_number += 1

    return render_template(
        "games.html",
        user=user,
        weeks=weeks,
        season=season,
        nav_points=nav_points,
    )


@main_bp.get("/leaderboard")
@login_required
def leaderboard():
    today = crew_today()
    user = session["user"]
    user_key = current_user_key()
    seasons = list_seasons(today)
    current_season = get_season_for_date(today)

    selected_id = request.args.get("season", type=int)
    selected_season = next((item for item in seasons if item["id"] == selected_id), None)
    selected_season = selected_season or current_season or (seasons[0] if seasons else None)

    selected_week = request.args.get("week", "all")
    game = request.args.get("game", "all")

    if selected_season:
        if selected_week == "all":
            period = "season"
            reference_day = selected_season["start_date"]
        else:
            try:
                week_number = int(selected_week)
            except (TypeError, ValueError):
                week_number = 1
            week_number = max(1, min(selected_season["weeks_total"], week_number))
            selected_week = str(week_number)
            period = "this_week"
            reference_day = get_week_start(selected_season["start_date"]) + timedelta(days=(week_number - 1) * 7)

        board = get_leaderboard(
            period,
            game,
            reference_day=reference_day,
            current_profile_id=user["profile_id"],
        )
    else:
        selected_week = "all"
        board = get_leaderboard(
            "all_time",
            game,
            current_profile_id=user["profile_id"],
        )

    filter_data = {
        "seasons": [
            {
                "id": item["id"],
                "number": item["number"],
                "weeks_total": item["weeks_total"],
            }
            for item in seasons
        ]
    }

    nav_points = get_weekly_points(user_key, today)["points"]

    return render_template(
        "leaderboard.html",
        user=user,
        board=board,
        seasons=seasons,
        selected_season=selected_season,
        selected_week=selected_week,
        selected_game=game,
        filter_data=filter_data,
        nav_points=nav_points,
    )


@main_bp.get("/api/leaderboard")
@login_required
def leaderboard_api():
    today = crew_today()
    seasons = list_seasons(today)
    current_season = get_season_for_date(today)

    selected_id = request.args.get("season", type=int)
    selected_season = next((item for item in seasons if item["id"] == selected_id), None)
    selected_season = selected_season or current_season or (seasons[0] if seasons else None)

    week = request.args.get("week", "all")
    game = request.args.get("game", "all")

    if selected_season:
        if week == "all":
            period = "season"
            reference_day = selected_season["start_date"]
        else:
            try:
                week_number = int(week)
            except (TypeError, ValueError):
                week_number = 1
            week_number = max(1, min(selected_season["weeks_total"], week_number))
            period = "this_week"
            reference_day = get_week_start(selected_season["start_date"]) + timedelta(days=(week_number - 1) * 7)

        return jsonify(
            get_leaderboard(
                period,
                game,
                reference_day=reference_day,
                current_profile_id=session["user"]["profile_id"],
            )
        )

    return jsonify(
        get_leaderboard(
            "all_time",
            game,
            current_profile_id=session["user"]["profile_id"],
        )
    )
