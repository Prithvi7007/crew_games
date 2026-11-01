"""Shared eligibility for a personal previous-season Rewind."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.db import get_db
from app.schedule import CREW_TIMEZONE


def has_season_rewind(profile_id, season_start, season_end, score_cutoff):
    """Require season membership and a real completion before the frozen cutoff.

    Season dates use CREW's local calendar; profile/completion timestamps are UTC.
    Catch-up play cannot give a later-season signup a previous-season story.
    """
    if not score_cutoff:
        return False
    end = date.fromisoformat(str(season_end))
    next_day = datetime.combine(
        end + timedelta(days=1), time.min, ZoneInfo(CREW_TIMEZONE),
    ).astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    return bool(get_db().execute(
        """SELECT 1 FROM profiles p
           WHERE p.id = ? AND p.created_at < ?
             AND EXISTS (
                 SELECT 1 FROM game_completions gc
                 WHERE gc.profile_id = p.id AND gc.game_date BETWEEN ? AND ?
                   AND gc.completed_at < ?
                   AND gc.game_key IN ('mystery','trivia','word','tick_tock')
             )""",
        (int(profile_id), next_day, str(season_start), str(season_end), score_cutoff),
    ).fetchone())


def has_season_honors(snapshot):
    """An approved, nonempty championship snapshot can welcome new CREW members."""
    return bool(snapshot.get("score_cutoff")
                and snapshot.get("winners", {}).get("season_champion"))
