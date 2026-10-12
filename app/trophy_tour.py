"""October 19 trophy-launch welcome tour: server-owned eligibility and state."""
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app, request, session

from app.badges import BADGES
from app.badge_store import get_badge_awards
from app.db import _db_timestamp, get_db, get_season_for_date, list_seasons
from app.schedule import crew_today
from app.trophy_access import TROPHY_PUBLIC_REVEAL_DATE

TOUR_KEY = "trophy_launch_2026"
TOUR_PAGES = frozenset(("home", "games", "leaderboard", "profile", "trophies"))


def _preview_allowed(user, page):
    return (
        page == "trophies"
        and user.get("role") in ("admin", "owner")
        and request.args.get("trophy_tour_preview") == "1"
    )


def tour_completed(profile_id):
    return bool(get_db().execute(
        "SELECT 1 FROM trophy_tour_completions WHERE profile_id = ? AND tour_key = ?",
        (int(profile_id), TOUR_KEY),
    ).fetchone())


def earned_tour_payload(profile_id, today=None):
    """Only the signed-in player's actual persisted, season-specific awards."""
    today = today or crew_today()
    season = get_season_for_date(today)
    if season is None:
        season = next((item for item in list_seasons(today) if item["start_date"] <= today), None)
    if season is None:
        return {"seasonNumber": None, "earnedCount": 0, "badges": []}
    awards = {row["badge_code"] for row in get_badge_awards(profile_id, season["id"])}
    badges = [
        {"code": badge.code, "name": badge.name, "rarity": badge.rarity,
         "gameKey": badge.game_key, "vertical": badge.vertical}
        for badge in BADGES if badge.code in awards
    ]
    return {"seasonNumber": int(season["number"]), "earnedCount": len(badges), "badges": badges}


def tour_for_player(user, page):
    """Fail open for gameplay if the optional tour storage is unavailable."""
    if page not in TOUR_PAGES or not current_app.config.get("TROPHY_TOUR_ENABLED", True):
        return None
    preview = _preview_allowed(user, page)
    if not preview and crew_today() < TROPHY_PUBLIC_REVEAL_DATE:
        return None
    if not preview and session.get("trophy_tour_snoozed"):
        return None
    try:
        if not preview and tour_completed(user["profile_id"]):
            return None
        return {**earned_tour_payload(user["profile_id"]), "preview": preview}
    except SQLAlchemyError:
        current_app.logger.exception("Trophy tour unavailable; continuing normal gameplay")
        return None


def complete_tour(profile_id, action):
    """Idempotent, player-scoped persistence. No badge or score mutations."""
    if action not in ("finished", "skipped"):
        raise ValueError("Invalid trophy tour completion")
    get_db().execute(
        """INSERT INTO trophy_tour_completions (profile_id, tour_key, completed_at, completion_type)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (profile_id, tour_key) DO NOTHING""",
        (int(profile_id), TOUR_KEY, _db_timestamp(), action),
    )
    get_db().commit()
