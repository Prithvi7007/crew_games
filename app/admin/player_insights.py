"""Read-only, season-scoped badge and performance insights for Admin Studio.

Never interpret private badge try-ons as saved awards. No write paths or
player-owned badge controls are exposed here.
"""

from app.badges import BADGES_BY_CODE, GAME_KEYS
from app.db import get_db, get_season_for_date, list_seasons
from app.schedule import crew_today


GAME_LABELS = {
    "mystery": "Mystery Monday",
    "trivia": "Trivia Tuesday",
    "word": "Wordle Wednesday",
    "tick_tock": "Tick-Tock Thursday",
}


def directory_badge_insights(profile_ids):
    """Fetch counts and slot-one equipped identity for an entire directory in 2 queries."""
    ids = sorted({int(value) for value in profile_ids})
    if not ids:
        return {}
    binds = ",".join("?" for _ in ids)
    db = get_db()
    result = {profile_id: {"badge_count": 0, "equipped_badge": None} for profile_id in ids}

    counts = db.execute(
        f"""SELECT profile_id, COUNT(*) AS count
            FROM badge_awards WHERE profile_id IN ({binds})
            GROUP BY profile_id""",
        ids,
    ).fetchall()
    for row in counts:
        result[int(row["profile_id"])]["badge_count"] = int(row["count"])

    equipped = db.execute(
        f"""SELECT bs.profile_id, ba.badge_code, s.season_number
            FROM badge_showcase AS bs
            JOIN badge_awards AS ba
              ON ba.id = bs.badge_award_id AND ba.profile_id = bs.profile_id
            JOIN seasons AS s ON s.id = ba.season_id
            WHERE bs.slot = 1 AND bs.profile_id IN ({binds})""",
        ids,
    ).fetchall()
    for row in equipped:
        badge = BADGES_BY_CODE.get(row["badge_code"])
        if badge:
            result[int(row["profile_id"])]["equipped_badge"] = {
                "name": badge.name,
                "rarity": badge.rarity,
                "season_number": int(row["season_number"]),
            }
    return result


def player_season_insights(profile_id, requested_season_id=None):
    """Season scores and confirmed awards, never account secrets or preview badges."""
    seasons = list_seasons()
    if not seasons:
        return {"seasons": [], "season": None, "performance": None,
                "awards": [], "equipped_badge": None}
    season_by_id = {int(item["id"]): item for item in seasons}
    try:
        chosen = int(requested_season_id) if requested_season_id is not None else None
    except (TypeError, ValueError):
        chosen = None
    current = get_season_for_date(crew_today())
    selected = season_by_id.get(chosen)
    if selected is None:
        selected = season_by_id.get(int(current["id"])) if current else None
    if selected is None:
        selected = next((item for item in seasons if item["status"] != "upcoming"), seasons[0])

    rows = get_db().execute(
        """SELECT game_key,
                  SUM(CASE WHEN competitive = 1 THEN 1 ELSE 0 END) AS competitive_games,
                  SUM(CASE WHEN competitive = 0 THEN 1 ELSE 0 END) AS practice_games,
                  COALESCE(SUM(CASE WHEN competitive = 1 THEN score ELSE 0 END), 0) AS points
           FROM game_completions
           WHERE profile_id = ? AND game_date BETWEEN ? AND ?
           GROUP BY game_key""",
        (int(profile_id), selected["start_date"].isoformat(),
         selected["end_date"].isoformat()),
    ).fetchall()
    games = {
        key: {"key": key, "name": GAME_LABELS[key],
              "competitive_games": 0, "practice_games": 0, "points": 0}
        for key in ("mystery", "trivia", "word", "tick_tock")
    }
    for row in rows:
        if row["game_key"] not in GAME_KEYS:
            continue
        info = games[row["game_key"]]
        for field in ("competitive_games", "practice_games", "points"):
            info[field] = int(row[field] or 0)
    performance = {
        "games": list(games.values()),
        "competitive_games": sum(g["competitive_games"] for g in games.values()),
        "practice_games": sum(g["practice_games"] for g in games.values()),
        "points": sum(g["points"] for g in games.values()),
    }

    awards = get_db().execute(
        """SELECT ba.badge_code, ba.awarded_at, ba.source_date,
                  CASE WHEN bs.badge_award_id IS NOT NULL THEN 1 ELSE 0 END AS equipped
           FROM badge_awards AS ba
           LEFT JOIN badge_showcase AS bs
             ON bs.badge_award_id = ba.id
             AND bs.profile_id = ba.profile_id AND bs.slot = 1
           WHERE ba.profile_id = ? AND ba.season_id = ?
           ORDER BY ba.awarded_at DESC, ba.id DESC""",
        (int(profile_id), int(selected["id"])),
    ).fetchall()
    earned = []
    for row in awards:
        badge = BADGES_BY_CODE.get(row["badge_code"])
        if badge:
            earned.append({
                "code": badge.code,
                "name": badge.name,
                "rarity": badge.rarity,
                "vertical": badge.vertical,
                "awarded_at": row["awarded_at"],
                "equipped": bool(row["equipped"]),
            })

    equipped = directory_badge_insights([profile_id])[int(profile_id)]["equipped_badge"]
    return {
        "season": selected,
        "seasons": seasons,
        "performance": performance,
        "awards": earned,
        "equipped_badge": equipped,
    }
