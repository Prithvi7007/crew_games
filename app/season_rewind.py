"""Read-only, season-scoped personalized CREW Rewind.

A finalized championship snapshot is the release gate and scoring cutoff.
Never make unreviewed finale ranks or awards public.
"""
import json
from collections import defaultdict
from datetime import date

from app.badges import BADGES_BY_CODE
from app.db import get_db
from app.rewind_insights import build_rewind_insights
from app.rewind_analytics import build_rewind_analytics
from app.rewind_story import build_rewind_story
from app.rewind_saga import build_season_saga
from app.schedule import get_week_start

_GAME_NAMES = {
    "mystery": "Mystery Monday",
    "trivia": "Trivia Tuesday",
    "word": "Wordle Wednesday",
    "tick_tock": "Tick-Tock Thursday",
}
_GAME_ORDER = tuple(_GAME_NAMES)
_PERSONAS = {
    "mystery": "The Mystery Solver",
    "trivia": "The Trivia Brain",
    "word": "The Word Wizard",
    "tick_tock": "The Time Bender",
}
_RARITY_ORDER = {"legendary": 4, "epic": 3, "rare": 2, "common": 1}


def _finalization(season_id):
    row = get_db().execute(
        "SELECT finalized_at, snapshot_json FROM season_badge_finalizations WHERE season_id = ?",
        (int(season_id),),
    ).fetchone()
    if not row:
        return None
    return {"finalized_at": row["finalized_at"], "snapshot": json.loads(row["snapshot_json"])}


def rewind_url(season, *, role="player"):
    """Do not advertise public Rewind before admin championship finalization."""
    if not season or int(season["number"]) != 1:
        return None
    if _finalization(season["id"]):
        return "/rewind"
    if role in ("owner", "admin"):
        return "/rewind?preview=1"
    return None


def build_season_rewind(profile_id, season, *, admin_preview=False):
    """Render the signed-in player's season story without changing game state.

    When finalized, every score is constrained by the immutable championship
    cutoff. Later archive plays must never rewrite the season finale.
    """
    if not season or int(season["number"]) != 1:
        return None
    frozen = _finalization(season["id"])
    if frozen is None and not admin_preview:
        return None

    cutoff = frozen["snapshot"].get("score_cutoff") if frozen else None
    # Finalizations always store a score cutoff. Do not silently use live scores
    # if a historical snapshot is malformed.
    if frozen is not None and not cutoff:
        return None

    start = season["start_date"].isoformat()
    end = season["end_date"].isoformat()
    score_limit = "AND gc.completed_at < ?" if cutoff else ""
    query_args = [start, end]
    if cutoff:
        query_args.append(cutoff)

    db = get_db()
    # All completion rows (including legitimate catch-up plays) count until
    # the owner-approved cutoff, matching championship score eligibility.
    completions = db.execute(
        f"""SELECT gc.profile_id, gc.game_key, gc.game_date, gc.score
            FROM game_completions gc
            WHERE gc.game_date BETWEEN ? AND ?
              AND gc.game_key IN ('mystery','trivia','word','tick_tock')
              {score_limit}
            ORDER BY gc.profile_id, gc.game_date, gc.game_key""",
        query_args,
    ).fetchall()

    all_profiles = db.execute("SELECT id, username, role FROM profiles").fetchall()
    profile_names = {int(p["id"]): p["username"] for p in all_profiles}
    benchmark_profile_ids = {int(p["id"]) for p in all_profiles if p["role"] == "player"}
    if int(profile_id) not in profile_names:
        return None

    totals = defaultdict(lambda: {"points": 0, "completed": 0})
    mine = []
    for row in completions:
        pid = int(row["profile_id"])
        score = int(row["score"])
        totals[pid]["points"] += score
        totals[pid]["completed"] += 1
        if pid == int(profile_id):
            mine.append(row)

    # Match the public leaderboard's points / count / name order for a
    # reproducible rank; zero-point players are welcomed without a false rank.
    leaderboard = sorted(
        [pid for pid, data in totals.items() if data["points"] > 0],
        key=lambda pid: (-totals[pid]["points"], -totals[pid]["completed"],
                         profile_names[pid].casefold(), pid),
    )
    rank = leaderboard.index(int(profile_id)) + 1 if int(profile_id) in leaderboard else None
    games = {key: {"key": key, "name": name, "points": 0, "played": 0}
             for key, name in _GAME_NAMES.items()}
    weeks = defaultdict(lambda: {"points": 0, "played": 0})
    weekly_game_points = defaultdict(lambda: defaultdict(int))
    season_week_zero = get_week_start(season["start_date"])

    for row in mine:
        game = games[row["game_key"]]
        game["points"] += int(row["score"])
        game["played"] += 1
        played_day = date.fromisoformat(row["game_date"])
        week_number = (get_week_start(played_day) - season_week_zero).days // 7 + 1
        weeks[week_number]["points"] += int(row["score"])
        weekly_game_points[week_number][row["game_key"]] += int(row["score"])
        weeks[week_number]["played"] += 1

    played_games = [game for game in games.values() if game["played"]]
    # "Strongest" means highest average scored *per completed game*, not
    # simply most weeks played. A stable order resolves exact ties.
    strongest = max(
        played_games,
        key=lambda g: (g["points"] / g["played"], g["points"],
                       -_GAME_ORDER.index(g["key"])),
        default=None,
    )
    strongest = (
        {**strongest, "average": round(strongest["points"] / strongest["played"])}
        if strongest else None
    )

    week = max(
        weeks,
        key=lambda number: (weeks[number]["points"], weeks[number]["played"], -number),
        default=None,
    )
    best_week = {"number": week, **weeks[week]} if week is not None else None

    badge_rows = db.execute(
        """SELECT badge_code, awarded_at FROM badge_awards
           WHERE profile_id = ? AND season_id = ? ORDER BY awarded_at, id""",
        (int(profile_id), int(season["id"])),
    ).fetchall()
    # Unlike late archive completions, new badges might still be awarded later.
    # The Rewind reflects only awards held when championships were finalized.
    awarded_codes = {
        row["badge_code"] for row in badge_rows
        if not frozen or row["awarded_at"] <= frozen["finalized_at"]
    }
    badges = [BADGES_BY_CODE[code] for code in awarded_codes if code in BADGES_BY_CODE]
    badges.sort(key=lambda badge: (-_RARITY_ORDER.get(badge.rarity, 0), badge.name))
    featured = badges[0] if badges else None

    winners = frozen["snapshot"].get("winners", {}) if frozen else {}
    champion = any(
        int(item["profile_id"]) == int(profile_id)
        for item in winners.get("season_champion", [])
    )

    result = {
        "seasonNumber": int(season["number"]),
        "seasonName": season["name"],
        "username": profile_names[int(profile_id)],
        "preview": frozen is None,
        "finalized": frozen is not None,
        "points": sum(int(row["score"]) for row in mine),
        "gamesPlayed": len(mine),
        "gamesTotal": int(season["games_total"]),
        "weeksActive": len(weeks),
        "rank": rank,
        "participants": len(totals),
        "signature": strongest,
        "persona": _PERSONAS[strongest["key"]] if strongest else "The CREW Original",
        "insights": build_rewind_insights(
            mine, completions, profile_id=profile_id,
            season_start=season["start_date"],
            weeks_total=season["weeks_total"], signature=strongest,
            rank=rank, participants=len(totals),
            benchmark_profile_ids=benchmark_profile_ids,
            points=totals[int(profile_id)]["points"],
        ),
        "analyticsStory": build_rewind_analytics(
            mine, completions, profile_id=profile_id,
            season_start=season["start_date"],
            weeks_total=season["weeks_total"],
            profile_names=profile_names, rank=rank,
            benchmark_profile_ids=benchmark_profile_ids,
        ),
        "bestWeek": best_week,
        "weeklyScores": [
            {"number": number, **weeks[number]}
            for number in range(1, int(season["weeks_total"]) + 1)],
        "weeklyGameScores": [
            {"number": number, "games": {
                key: weekly_game_points[number][key] for key in _GAME_ORDER}}
            for number in range(1, int(season["weeks_total"]) + 1)],
        "gameBreakdown": list(games.values()),
        "badges": {"count": len(badges), "featured": (
            {"code": featured.code, "name": featured.name,
             "rarity": featured.rarity, "gameKey": featured.game_key}
            if featured else None
        )},
        "champion": champion,
    }
    result["seasonSaga"] = build_season_saga(
        result, completions, profile_id=profile_id,
        season_start=season["start_date"],
        weeks_total=season["weeks_total"],
        names=profile_names,
        official_winners=winners,
        awarded_codes=awarded_codes,
        benchmark_profile_ids=benchmark_profile_ids,
    )
    result["cinematicStory"] = build_rewind_story(
        result, completions, profile_id=profile_id,
        season_start=season["start_date"],
        weeks_total=season["weeks_total"],
        profile_names=profile_names,
    )
    return result
