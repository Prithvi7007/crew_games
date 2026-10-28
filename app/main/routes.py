from datetime import timedelta

from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, request, session, url_for

from app.auth.routes import current_user_key, login_required
from app.player_ui import render_player
from app.season_rewind import build_season_rewind, rewind_url
from app.badge_display import with_public_equipped_badges
from app.trophy_access import trophies_visible_to, trophy_preview_enabled
from app.trophy_tour import complete_tour, earned_tour_payload
from app.badges import BADGES, BADGES_BY_CODE
from app.badge_store import get_badge_awards, get_showcase, set_showcase_slot
from app.db import (
    get_game_attempt_summary,
    get_game_completion,
    get_profile_by_username,
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



@main_bp.get("/rewind")
@login_required
def season_one_rewind():
    user = session["user"]
    season = next((item for item in list_seasons(crew_today())
                   if item["number"] == 1), None)
    if not season:
        abort(404)
    # Restrict this experimental film to staff even after finalization.
    film_requested = request.args.get("prototype") == "1"
    film_preview = film_requested and user.get("role") in ("admin", "owner")
    if film_requested and not film_preview:
        abort(404)
    preview = (
        user.get("role") in ("admin", "owner")
        and request.args.get("preview") == "1"
    )
    # A second staff-only lens: test the evidence before designing a film.
    analysis_preview = request.args.get("analysis") == "1"
    if analysis_preview and not (film_preview and preview):
        abort(404)
    # Evidence-led V2 is a second, strictly staff-only film preview.
    story_preview = request.args.get("story") == "2"
    if story_preview and (not film_preview or not preview or analysis_preview):
        abort(404)
    # View another player's real Rewind only in the explicit staff-only Film
    # Lab preview. Never impersonate the player or change the login session.
    cross_player_preview = "player" in request.args
    requested_player = request.args.get("player")
    if cross_player_preview and (
        not film_preview or not preview
        or not requested_player or len(requested_player) > 80
    ):
        abort(404)
    profile_id = user["profile_id"]
    if cross_player_preview:
        player = get_profile_by_username(requested_player)
        if not player:
            abort(404)
        profile_id = player["id"]

    story = build_season_rewind(profile_id, season, admin_preview=preview)
    if not story:
        abort(404)
    response = make_response(render_player(
        "rewind", "Season One Rewind", "crew-rewind-page",
        {
            "rewind": story,
            "rewindFilmPrototype": film_preview,
            "rewindAnalyticsPreview": analysis_preview,
            "rewindStoryPreview": story_preview,
            "rewindPreviewPlayer": story["username"] if cross_player_preview else None,
        }, user,
    ))
    if film_preview:
        response.headers["Cache-Control"] = "private, no-store"
    return response


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
    weekly = get_weekly_points(user_key, today)
    season = get_season_summary(user_key, today)

    games = []
    for definition in GAME_DEFINITIONS:
        item = dict(definition)
        game_day = get_game_date(item["key"], today)
        summary = get_game_attempt_summary(user_key, item["key"], game_day.isoformat())
        item.update(summary)
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
    return render_player(
        "home",
        "Home",
        "v17-today-page",
        {
            "today": today,
            "games": games,
            "todaysGame": todays_game,
            "rewindUrl": rewind_url(
                next((item for item in list_seasons(today) if item["number"] == 1), None),
                role=user.get("role", "player")),
            "weekNumber": get_crew_week_number(today),
            "season": season,
        },
        user,
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
            item.update(summary)
            item["date"] = game_day
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

    return render_player(
        "games",
        "Games",
        "games-page",
        {"weeks": weeks, "season": season},
        user,
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

    return render_player(
        "leaderboard",
        "Rankings",
        "rankings-page",
        {
            "board": with_public_equipped_badges(board, user),
            "selectedSeason": selected_season,
            "selectedWeek": selected_week,
            "selectedGame": game,
            "filters": filter_data,
            "apiUrl": url_for("main.leaderboard_api"),
        },
        user,
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

        return jsonify(with_public_equipped_badges(
            get_leaderboard(
                period,
                game,
                reference_day=reference_day,
                current_profile_id=session["user"]["profile_id"],
            ), session["user"]
        ))

    return jsonify(with_public_equipped_badges(
        get_leaderboard(
            "all_time",
            game,
            current_profile_id=session["user"]["profile_id"],
        ), session["user"]
    ))


@main_bp.get("/trophies")
@login_required
def trophies():
    """Season-scoped, read-only collection; badge granting is server-owned."""
    if not trophies_visible_to(session["user"]):
        return "", 404
    today = crew_today()
    user = session["user"]
    profile_id = int(user["profile_id"])
    seasons = list_seasons(today)
    current = get_season_for_date(today)
    requested = request.args.get("season", type=int)
    selected = next((season for season in seasons if season["id"] == requested), None)
    selected = selected or current or (seasons[0] if seasons else None)

    saved = get_badge_awards(profile_id, selected["id"]) if selected else []
    awards_by_code = {row["badge_code"]: row for row in saved}
    showcase = get_showcase(profile_id)
    preview_enabled = trophy_preview_enabled(user)
    preview_code = session.get("trophy_preview_badge_code") if preview_enabled else None
    if preview_code not in BADGES_BY_CODE:
        preview_code = None
    badges = [
        {
            "code": badge.code,
            "name": badge.name,
            "vertical": badge.vertical,
            "rarity": badge.rarity,
            "gameKey": badge.game_key,
            "earned": badge.code in awards_by_code,
            "awardId": int(awards_by_code[badge.code]["id"]) if badge.code in awards_by_code else None,
            "awardedAt": awards_by_code[badge.code]["awarded_at"] if badge.code in awards_by_code else None,
            "sourceDate": awards_by_code[badge.code]["source_date"] if badge.code in awards_by_code else None,
        }
        for badge in BADGES
    ]
    return render_player(
        "trophies", "Trophy Room", "trophy-page",
        {
            "badges": badges,
            "earnedCount": sum(badge["earned"] for badge in badges),
            "trophyPreview": {
                "enabled": preview_enabled,
                "badgeCode": preview_code,
                "url": url_for("main.update_trophy_preview_badge") if preview_enabled else None,
            },
            "unlockPreviewEnabled": (
                preview_enabled and request.args.get("unlock_preview") == "1"
            ),
            "selectedSeason": selected,
            "seasons": [
                {"id": season["id"], "number": season["number"], "name": season["name"]}
                for season in seasons
            ],
            "tourReplay": ({**earned_tour_payload(profile_id, today), "preview": True}
                           if current_app.config.get("TROPHY_TOUR_ENABLED", True) else None),
            "showcaseUrl": url_for("main.update_trophy_showcase"),
            "showcase": [
                {"slot": row["slot"], "badgeCode": row["badge_code"],
                 "awardId": int(row["award_id"]),
                 "badge": {
                     "code": row["badge_code"],
                     "name": BADGES_BY_CODE[row["badge_code"]].name,
                     "vertical": BADGES_BY_CODE[row["badge_code"]].vertical,
                     "rarity": BADGES_BY_CODE[row["badge_code"]].rarity,
                     "gameKey": BADGES_BY_CODE[row["badge_code"]].game_key,
                     "seasonNumber": int(row["season_number"]),
                 }}
                for row in showcase
            ],
        },
        user,
        nav_points=get_weekly_points(current_user_key(), today)["points"],
    )


@main_bp.post("/api/trophies/tour")
@login_required
def update_trophy_tour():
    """Player-scoped one-time tour state; protected by the global CSRF guard."""
    if (not current_app.config.get("TROPHY_TOUR_ENABLED", True)
            or not trophies_visible_to(session["user"])):
        return "", 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("action") not in ("later", "skipped", "finished"):
        return jsonify({"ok": False, "message": "Invalid tour action."}), 400
    action = payload["action"]
    if action == "later":
        session["trophy_tour_snoozed"] = True
    else:
        complete_tour(session["user"]["profile_id"], action)
        session.pop("trophy_tour_snoozed", None)
    response = jsonify({"ok": True})
    response.headers["Cache-Control"] = "no-store"
    return response


@main_bp.post("/api/trophies/preview-badge")
@login_required
def update_trophy_preview_badge():
    """Temporary, private profile try-on; never creates badge awards or a showcase."""
    if not trophy_preview_enabled(session["user"]):
        return "", 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "badgeCode" not in payload:
        return jsonify({"ok": False, "message": "Invalid preview request."}), 400
    code = payload["badgeCode"]
    if code is not None and (not isinstance(code, str) or code not in BADGES_BY_CODE):
        return jsonify({"ok": False, "message": "Unknown preview badge."}), 400
    if code is None:
        session.pop("trophy_preview_badge_code", None)
    else:
        session["trophy_preview_badge_code"] = code
    response = jsonify({"ok": True, "badgeCode": code})
    response.headers["Cache-Control"] = "no-store"
    return response


@main_bp.post("/api/trophies/showcase")
@login_required
def update_trophy_showcase():
    """Change exactly one showcase slot, validating ownership on the server."""
    if not trophies_visible_to(session["user"]):
        return "", 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "message": "Invalid showcase request."}), 400
    slot = payload.get("slot")
    award_id = payload.get("awardId")
    if type(slot) is not int or slot not in (1, 2, 3):
        return jsonify({"ok": False, "message": "Invalid showcase slot."}), 400
    if award_id is not None and (type(award_id) is not int or award_id <= 0):
        return jsonify({"ok": False, "message": "Invalid badge selection."}), 400
    profile_id = int(session["user"]["profile_id"])
    try:
        set_showcase_slot(profile_id, slot, award_id)
    except ValueError:
        return jsonify({"ok": False, "message": "Choose one of your earned badges."}), 400
    saved = get_showcase(profile_id)
    response = jsonify({
        "ok": True,
        "showcase": [
            {"slot": item["slot"], "badgeCode": item["badge_code"],
             "awardId": int(item["award_id"]),
             "badge": {
                 "code": item["badge_code"],
                 "name": BADGES_BY_CODE[item["badge_code"]].name,
                 "vertical": BADGES_BY_CODE[item["badge_code"]].vertical,
                 "rarity": BADGES_BY_CODE[item["badge_code"]].rarity,
                 "gameKey": BADGES_BY_CODE[item["badge_code"]].game_key,
                 "seasonNumber": int(item["season_number"]),
             }}
            for item in saved
        ],
    })
    response.headers["Cache-Control"] = "no-store"
    return response
