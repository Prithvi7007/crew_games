"""Reviewable, idempotent end-of-season championship badges.

No awards are created automatically. An authenticated admin must explicitly
review and finalize after the season ends. Tied first places share the badge.
"""
import json
from datetime import date

from app.badges import CHAMPIONSHIP_CODES
from app.db import _db_timestamp, get_db, get_season_by_id
from app.schedule import crew_today

RULE_VERSION = 1
CHAMPIONSHIP_GAME = {
    "season_champion": None,
    "season_mystery_master": "mystery",
    "season_trivia_master": "trivia",
    "season_wordle_master": "word",
    "season_tick_tock_master": "tick_tock",
}
assert set(CHAMPIONSHIP_GAME) == CHAMPIONSHIP_CODES


def _stored(season_id):
    row = get_db().execute(
        "SELECT snapshot_json FROM season_badge_finalizations WHERE season_id = ?",
        (int(season_id),),
    ).fetchone()
    if row is None:
        return None
    snapshot = json.loads(row["snapshot_json"])
    return {**snapshot, "already_finalized": True, "new_awards": 0}


def preview_season_championships(season_id, *, today=None):
    """Return immutable winners after approval, otherwise live read-only preview."""
    today = today or crew_today()
    season = get_season_by_id(int(season_id), reference_day=today)
    if not season:
        raise ValueError("Unknown season.")
    stored = _stored(season_id)
    if stored:
        return stored

    scores = {}
    rows = get_db().execute(
        """
        SELECT p.id AS profile_id, p.username, gc.game_key,
               SUM(gc.score) AS points
        FROM game_completions gc
        JOIN profiles p ON p.id = gc.profile_id
        WHERE gc.game_date BETWEEN ? AND ?
          AND gc.game_key IN ('mystery','trivia','word','tick_tock')
        GROUP BY p.id, p.username, gc.game_key
        """,
        (season["start_date"].isoformat(), season["end_date"].isoformat()),
    ).fetchall()
    for row in rows:
        pid = int(row["profile_id"])
        result = scores.setdefault(pid, {
            "profile_id": pid, "username": row["username"], "total": 0,
            "mystery": 0, "trivia": 0, "word": 0, "tick_tock": 0,
        })
        points = int(row["points"])
        result["total"] += points
        result[row["game_key"]] = points

    winners = {}
    for badge_code, game in CHAMPIONSHIP_GAME.items():
        key = game or "total"
        candidates = [p for p in scores.values() if p[key] > 0]
        high = max((p[key] for p in candidates), default=0)
        winners[badge_code] = sorted(
            [{"profile_id": p["profile_id"], "username": p["username"],
              "points": p[key]} for p in candidates if p[key] == high],
            key=lambda x: (x["username"].casefold(), x["profile_id"]),
        )
    return {
        "season_id": int(season_id),
        "season_number": season["number"],
        "season_name": season["name"],
        "season_end": season["end_date"].isoformat(),
        "eligible": today > season["end_date"],
        "rule_version": RULE_VERSION,
        "tie_rule": "All players tied for the highest positive score share first place.",
        "winners": winners,
        "already_finalized": False,
        "new_awards": 0,
    }


def finalize_season_championships(season_id, *, today=None):
    """Freeze a reviewed snapshot and award its winners once, atomically."""
    preview = preview_season_championships(season_id, today=today)
    if preview["already_finalized"]:
        return preview
    if not preview["eligible"]:
        raise ValueError("Season has not ended; championship badges cannot be finalized.")
    db = get_db()
    timestamp = _db_timestamp()
    snapshot = {**preview, "already_finalized": True}
    try:
        cursor = db.execute(
            """INSERT INTO season_badge_finalizations
               (season_id, finalized_at, rule_version, snapshot_json)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (season_id) DO NOTHING""",
            (int(season_id), timestamp, RULE_VERSION,
             json.dumps(snapshot, sort_keys=True, separators=(",", ":"))),
        )
        if cursor.rowcount == 0:
            db.rollback()
            return _stored(season_id)

        new_awards = 0
        for code, winners in snapshot["winners"].items():
            for winner in winners:
                award = db.execute(
                    """INSERT INTO badge_awards
                       (profile_id, season_id, badge_code, awarded_at, source_date, evidence_json)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT (profile_id, season_id, badge_code) DO NOTHING""",
                    (winner["profile_id"], int(season_id), code, timestamp, None,
                     json.dumps({"season_id": int(season_id), "rule_version": RULE_VERSION,
                                 "points": winner["points"], "tie_rule": "shared-first"},
                                sort_keys=True)),
                )
                new_awards += max(0, award.rowcount)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {**snapshot, "new_awards": new_awards}
