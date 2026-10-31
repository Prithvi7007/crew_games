"""Account-scoped, one-time Season 1 Rewind premiere; no competition mutations."""
import json
from urllib.parse import unquote, urlsplit

from flask import current_app, request, session
from sqlalchemy.exc import SQLAlchemyError

from app.db import _db_timestamp, get_db

REWIND_TOUR_KEY = "season_1_rewind_2026"
SESSION_KEY = "rewind_login_intro"


def safe_local_target(target, default="/home"):
    if not isinstance(target, str) or not target.startswith("/"):
        return default
    decoded = unquote(target)
    if decoded.startswith("//") or "\\" in decoded or any(ord(c) < 32 for c in decoded):
        return default
    try:
        parsed = urlsplit(target)
    except ValueError:
        return default
    return default if parsed.scheme or parsed.netloc else target


def rewind_completed(profile_id):
    return bool(get_db().execute(
        "SELECT 1 FROM trophy_tour_completions WHERE profile_id = ? AND tour_key = ?",
        (int(profile_id), REWIND_TOUR_KEY),
    ).fetchone())


def _eligible_season(profile_id):
    row = get_db().execute(
        """SELECT s.id, s.start_date, s.end_date, f.snapshot_json
           FROM seasons s JOIN season_badge_finalizations f ON f.season_id = s.id
           WHERE s.season_number = 1""",
    ).fetchone()
    if row is None:
        return None
    cutoff = json.loads(row["snapshot_json"]).get("score_cutoff")
    if not cutoff:
        return None
    played = get_db().execute(
        """SELECT 1 FROM game_completions
           WHERE profile_id = ? AND game_date BETWEEN ? AND ?
             AND completed_at < ?
             AND game_key IN ('mystery','trivia','word','tick_tock') LIMIT 1""",
        (int(profile_id), row["start_date"], row["end_date"], cutoff),
    ).fetchone()
    return row if played else None


def _tracking_failed():
    try:
        get_db().rollback()
    except SQLAlchemyError:
        pass
    current_app.logger.exception("Optional Rewind tracking unavailable; continuing to CREW")


def premiere_destination(profile_id, target="/home"):
    """Only an authenticated login/Home visit can create an autoplay handoff."""
    active = session.get(SESSION_KEY)
    if isinstance(active, dict) and active.get("profile_id") == int(profile_id):
        return None  # Also prevents a loop when a skip/completion request fails.
    target = safe_local_target(target)
    path = urlsplit(target).path
    if path.split("/")[1] in {"admin", "api", "login", "logout", "create-profile",
                              "recover", "recovery-code"}:
        return None
    if urlsplit(target).query and path == "/rewind":
        return None  # Explicit Film Lab/replay links keep their requested behavior.
    try:
        season = _eligible_season(profile_id)
        if season is None or rewind_completed(profile_id):
            return None
    except (SQLAlchemyError, ValueError, TypeError, KeyError):
        _tracking_failed()
        return None
    session[SESSION_KEY] = {
        "profile_id": int(profile_id), "season_id": int(season["id"]),
        "return_url": "/home" if path == "/rewind" else target,
    }
    return "/rewind?intro=1"


def premiere_payload(profile_id, season_id):
    active = session.get(SESSION_KEY)
    if (request.args.getlist("intro") != ["1"] or not isinstance(active, dict)
            or active.get("profile_id") != int(profile_id)
            or active.get("season_id") != int(season_id)):
        return None
    try:
        if rewind_completed(profile_id):
            return None
    except SQLAlchemyError:
        _tracking_failed()
        return None
    return {"returnUrl": safe_local_target(active.get("return_url"))}


def complete_rewind(profile_id, action):
    if action not in {"finished", "skipped"} or _eligible_season(profile_id) is None:
        raise ValueError("Rewind is not available for this player.")
    db = get_db()
    db.execute(
        """INSERT INTO trophy_tour_completions
           (profile_id, tour_key, completed_at, completion_type) VALUES (?, ?, ?, ?)
           ON CONFLICT (profile_id, tour_key) DO NOTHING""",
        (int(profile_id), REWIND_TOUR_KEY, _db_timestamp(), action),
    )
    db.commit()
    session.pop(SESSION_KEY, None)
