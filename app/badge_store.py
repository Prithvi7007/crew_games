"""Server-side persistence helpers for season-specific badge awards.

The route/integration layer is intentionally deferred until PR3. Never pass
browser-supplied badge codes to these helpers.
"""

import json
from datetime import date

from app.badges import BADGES_BY_CODE
from app.db import _db_timestamp, get_db, get_season_for_date


def award_badges(profile_id, season_id, badge_codes, *, source_date=None, evidence=None):
    """Idempotently persist server-validated awards; returns newly awarded codes."""
    codes = set(badge_codes)
    invalid = codes - BADGES_BY_CODE.keys()
    if invalid:
        raise ValueError(f"Unknown badge code(s): {', '.join(sorted(invalid))}")
    db = get_db()
    if not db.execute("SELECT id FROM seasons WHERE id = ?", (season_id,)).fetchone():
        raise ValueError("Unknown season")
    if source_date is not None:
        game_day = date.fromisoformat(str(source_date))
        original_season = get_season_for_date(game_day)
        if not original_season or original_season["id"] != int(season_id):
            raise ValueError("Badge source date must belong to the specified season")
    stamp = _db_timestamp()
    evidence_json = json.dumps(evidence or {}, separators=(",", ":"), sort_keys=True)
    awarded = []
    for code in sorted(codes):
        cursor = db.execute(
            """INSERT INTO badge_awards (profile_id, season_id, badge_code, awarded_at, source_date, evidence_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (profile_id, season_id, badge_code) DO NOTHING""",
            (int(profile_id), int(season_id), code, stamp,
             str(source_date) if source_date is not None else None, evidence_json),
        )
        if cursor.rowcount:
            awarded.append(code)
    db.commit()
    return tuple(awarded)


def award_badges_for_game_date(profile_id, game_date, badge_codes, *, evidence=None):
    """Catch-up games are associated with the season of the scheduled date."""
    game_day = date.fromisoformat(str(game_date))
    season = get_season_for_date(game_day)
    if not season:
        raise ValueError("No CREW season covers the game date")
    return award_badges(
        profile_id, season["id"], badge_codes,
        source_date=game_day.isoformat(), evidence=evidence,
    )


def get_badge_awards(profile_id, season_id):
    return get_db().execute(
        """SELECT id, badge_code, awarded_at, source_date, evidence_json
           FROM badge_awards WHERE profile_id = ? AND season_id = ?
           ORDER BY awarded_at ASC, id ASC""",
        (int(profile_id), int(season_id)),
    ).fetchall()


def set_showcase_slot(profile_id, slot, badge_award_id=None):
    """Only the player's own existing award can occupy a showcase slot."""
    if type(slot) is not int or slot not in (1, 2, 3):
        raise ValueError("Showcase slot must be 1, 2, or 3")
    db = get_db()
    if badge_award_id is None:
        db.execute(
            "DELETE FROM badge_showcase WHERE profile_id = ? AND slot = ?",
            (int(profile_id), slot),
        )
    else:
        owned = db.execute(
            "SELECT id FROM badge_awards WHERE id = ? AND profile_id = ?",
            (int(badge_award_id), int(profile_id)),
        ).fetchone()
        if not owned:
            raise ValueError("Showcase badge must belong to the player")
        duplicate = db.execute(
            """SELECT slot FROM badge_showcase
               WHERE profile_id = ? AND badge_award_id = ? AND slot <> ?""",
            (int(profile_id), int(badge_award_id), slot),
        ).fetchone()
        if duplicate:
            raise ValueError("Badge is already showcased in another slot")
        db.execute(
            """INSERT INTO badge_showcase (profile_id, slot, badge_award_id)
               VALUES (?, ?, ?)
               ON CONFLICT (profile_id, slot) DO UPDATE
               SET badge_award_id = excluded.badge_award_id""",
            (int(profile_id), slot, int(badge_award_id)),
        )
    db.commit()


def get_showcase(profile_id):
    return get_db().execute(
        """SELECT s.slot, a.id AS award_id, a.season_id, a.badge_code
           FROM badge_showcase s
           JOIN badge_awards a ON a.id = s.badge_award_id
           WHERE s.profile_id = ? ORDER BY s.slot""",
        (int(profile_id),),
    ).fetchall()
