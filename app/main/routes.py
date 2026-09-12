from datetime import date, timedelta

from flask import Blueprint, redirect, render_template, session, url_for

from app.auth.routes import current_user_key, login_required
from app.db import ensure_user_stats, get_game_attempt_summary, get_game_content, get_weekly_leaderboard, get_weekly_points
from app.schedule import GAME_DEFINITIONS, get_game_date, get_week_start


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    # CREW deliberately starts at the sign-in screen when opened fresh.
    session.clear()
    return redirect(url_for("auth.login"))


@main_bp.get("/home")
@login_required
def home():
    user = session["user"]
    user_key = current_user_key()
    today = date.today()
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
            item["status"] = "completed"
            item["cta"] = "View result"
            item["journey_label"] = f"Completed · {item['score']} pts"
        elif game_day == today:
            item["status"] = "live"
            item["cta"] = "Continue" if item["started"] else "Play today"
            item["journey_label"] = "Today"
        elif game_day < today:
            # Past CREW games stay open through the week so players can catch up.
            item["status"] = "available"
            item["cta"] = "Catch up"
            item["journey_label"] = "Available"
        else:
            item["status"] = "upcoming"
            item["cta"] = "Preview"
            item["journey_label"] = item["date"].strftime("%b %d").upper()
        games.append(item)

    todays_game = next((game for game in games if game["date"] == today), None)
    weekday = today.weekday()
    if weekday <= 3:
        home_phase = "play"
    elif weekday == 4:
        home_phase = "recap"
    else:
        home_phase = "weekend"

    next_week_start = get_week_start(today) + timedelta(days=7)

    ranked_players = get_weekly_leaderboard(today, limit=100000)
    scored_players = [player for player in ranked_players if int(player["points"]) > 0]
    for index, player in enumerate(scored_players, start=1):
        player["rank"] = index
        player["me"] = player["profile_id"] == user["profile_id"]

    me = next((player for player in scored_players if player["me"]), None)
    my_rank = me["rank"] if me else None

    # Keep the home preview intentionally small: the leaders plus the current player.
    leaderboard = scored_players[:3]
    if me and all(player["profile_id"] != me["profile_id"] for player in leaderboard):
        leaderboard = [*leaderboard, me]

    stats = {
        "streak": stats_row["current_streak"],
        "rank": my_rank,
        "weekly_points": weekly["points"],
        "games_completed": weekly["completed"],
        "progress_percent": min(100, round((weekly["points"] / 400) * 100)),
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
    )
