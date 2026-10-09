"""Award badges from saved server-owned completion evidence.

No client-submitted badge codes, no extra scoring, and no championship
awards during ordinary play. Replay/backfill is idempotent.
"""
from datetime import date, timedelta

from app.badges import (
    BADGES, COLLECTION_CODES, CHAMPIONSHIP_CODES, evaluate_collection_badges,
    evaluate_game_badges, evaluate_week_badges,
)
from app.badge_store import award_badges, get_badge_awards
from app.db import get_db, get_season_for_date
from app.schedule import get_week_start

ATTEMPT_TABLES = {
    "mystery": "mystery_attempts",
    "trivia": "trivia_attempts",
    "word": "word_attempts",
    "tick_tock": "tick_tock_attempts",
}
BADGE_ORDER = {badge.code: i for i, badge in enumerate(BADGES)}


def _completion_and_attempt(profile_id, game_key, game_date):
    """Never infer a valid completion from an unfinished attempt alone."""
    if game_key not in ATTEMPT_TABLES:
        raise ValueError("Unknown CREW game")
    db = get_db()
    completion = db.execute(
        """SELECT score FROM game_completions
           WHERE profile_id = ? AND game_key = ? AND game_date = ?""",
        (profile_id, game_key, game_date),
    ).fetchone()
    attempt = db.execute(
        "SELECT * FROM " + ATTEMPT_TABLES[game_key]
        + " WHERE profile_id = ? AND game_date = ?",
        (profile_id, game_date),
    ).fetchone()
    if not completion or not attempt or not attempt["completed"]:
        return None
    if int(completion["score"]) != int(attempt["score"]):
        raise ValueError("Saved attempt and completion scores disagree")
    return dict(attempt)


def _week_scores(profile_id, game_date, season_id):
    """Four game dates must belong to the same season, including archive days."""
    monday = get_week_start(date.fromisoformat(game_date))
    dates = [monday + timedelta(days=index) for index in range(4)]
    if any(
        not (season := get_season_for_date(day))
        or int(season["id"]) != int(season_id)
        for day in dates
    ):
        return {}
    rows = get_db().execute(
        """SELECT game_key, game_date, score FROM game_completions
           WHERE profile_id = ? AND game_date BETWEEN ? AND ?""",
        (profile_id, dates[0].isoformat(), dates[-1].isoformat()),
    ).fetchall()
    by_day = {
        (row["game_key"], row["game_date"]): int(row["score"])
        for row in rows
    }
    return {
        game_key: by_day[(game_key, dates[index].isoformat())]
        for index, game_key in enumerate(("mystery", "trivia", "word", "tick_tock"))
        if (game_key, dates[index].isoformat()) in by_day
    }


def award_saved_completion(profile_id, game_key, game_date, *, dry_run=False):
    """Reconcile one saved completion; return badge codes not previously awarded.

    Dry-run never writes, which permits an operator-controlled preview backfill.
    """
    profile_id = int(profile_id)
    game_date = date.fromisoformat(str(game_date)).isoformat()
    season = get_season_for_date(date.fromisoformat(game_date))
    if not season:
        return ()
    attempt = _completion_and_attempt(profile_id, game_key, game_date)
    if attempt is None:
        return ()

    season_id = int(season["id"])
    current = {row["badge_code"] for row in get_badge_awards(profile_id, season_id)}
    eligible = set(evaluate_game_badges(game_key, attempt))
    eligible.update(evaluate_week_badges(_week_scores(profile_id, game_date, season_id)))
    # Championship badges are assigned only by the final, frozen season results.
    eligible.difference_update(CHAMPIONSHIP_CODES)
    planned = eligible - current
    # Evaluate the collection milestone against awards earned in this one season.
    collection = evaluate_collection_badges(current | eligible)
    planned.update(collection - current)
    planned.difference_update(COLLECTION_CODES - collection)
    planned = tuple(sorted(planned, key=BADGE_ORDER.__getitem__))
    if dry_run or not planned:
        return planned
    # Persist once per season/code. Duplicate completion callbacks are harmless.
    saved = award_badges(
        profile_id, season_id, planned, source_date=game_date,
        evidence={"game": game_key, "source": "saved_completion"},
    )
    return tuple(sorted(saved, key=BADGE_ORDER.__getitem__))


def replay_saved_badges(*, dry_run=True, profile_id=None):
    """Explicit operator backfill, returning per-code counts; no access from HTTP."""
    db = get_db()
    query = """SELECT profile_id, game_key, game_date FROM game_completions
               WHERE game_key IN ('mystery','trivia','word','tick_tock')"""
    params = ()
    if profile_id is not None:
        query += " AND profile_id = ?"
        params = (int(profile_id),)
    query += " ORDER BY game_date, profile_id, game_key"
    rows = db.execute(query, params).fetchall()
    counts = {}
    if dry_run:
        # Simulate the whole historical sequence, including collection thresholds,
        # rather than pretending each completion occurs alone against empty storage.
        simulated = {}
        for row in rows:
            pid = int(row["profile_id"])
            key = row["game_key"]
            day = row["game_date"]
            season = get_season_for_date(date.fromisoformat(day))
            if not season or _completion_and_attempt(pid, key, day) is None:
                continue
            token = (pid, int(season["id"]))
            earned = simulated.setdefault(
                token, {item["badge_code"] for item in get_badge_awards(*token)}
            )
            attempt = _completion_and_attempt(pid, key, day)
            eligible = set(evaluate_game_badges(key, attempt))
            eligible.update(evaluate_week_badges(_week_scores(pid, day, token[1])))
            eligible.difference_update(CHAMPIONSHIP_CODES)
            eligible.update(evaluate_collection_badges(earned | eligible))
            new = eligible - earned
            earned.update(new)
            for code in new:
                counts[code] = counts.get(code, 0) + 1
    else:
        for row in rows:
            for code in award_saved_completion(
                row["profile_id"], row["game_key"], row["game_date"]
            ):
                counts[code] = counts.get(code, 0) + 1
    return {"dry_run": bool(dry_run), "completions_scanned": len(rows),
            "new_awards": sum(counts.values()), "by_badge": dict(sorted(counts.items()))}

def safe_award_completion(profile_id, game_key, game_date):
    """Do not turn a successfully saved game result into an HTTP 500."""
    from flask import current_app
    try:
        return award_saved_completion(profile_id, game_key, game_date)
    except Exception:
        current_app.logger.exception(
            "Badge awarding failed for game=%s date=%s", game_key, game_date
        )
        return ()
