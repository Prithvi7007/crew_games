"""Weekly trend benchmarks use player totals, participation and the finale cutoff."""
import json
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from app.championships import finalize_season_championships
from app.db import (create_profile, finalize_game_stats, get_db, get_season_for_date,
                    profile_user_key, update_profile_role)
from app.season_rewind import build_season_rewind


def player(name, role="player"):
    profile = create_profile(name, generate_password_hash("test-password"), "⭐",
                             generate_password_hash("test-recovery"))
    pid = int(profile["id"])
    if role != "player":
        update_profile_role(pid, role)
    return pid


def score(pid, game, day, points):
    finalize_game_stats(profile_user_key(pid), game, day, points, True)


def trend(recap):
    return next(b["visual"] for b in recap["seasonSaga"]["beats"] if b["kind"] == "weekly_trend")


def test_weekly_average_uses_other_active_player_totals_and_keeps_highest_and_peak(app):
    with app.app_context():
        me, a, b = (player(name) for name in ("WeeklyMe", "WeeklyA", "WeeklyB"))
        admin, owner = player("WeeklyAdmin", "admin"), player("WeeklyOwner", "owner")
        player("WeeklyInactive")
        for pid, values in ((me, [("trivia", 100), ("word", 50)]),
                            (a, [("trivia", 100), ("word", 0)]),
                            (b, [("trivia", 30)]),
                            (admin, [("trivia", 100), ("word", 100)]),
                            (owner, [("trivia", 100)])):
            for game, points in values:
                score(pid, game, "2026-09-22" if game == "trivia" else "2026-09-23", points)
        for pid, points in ((me, 20), (a, 0), (b, 60), (admin, 100)):
            score(pid, "trivia", "2026-09-29", points)
        score(me, "trivia", "2026-10-06", 10)
        score(admin, "trivia", "2026-10-06", 100)
        score(a, "trivia", "2026-10-13", 50)
        season = get_season_for_date(date(2026, 10, 26))
        finalize_season_championships(season["id"], today=date(2026, 11, 2))

        recap = build_season_rewind(me, season)
        visual = trend(recap)
        weeks = visual["weeks"]
        assert [(w["crew"], w["peerPlayers"]) for w in weeks] == [
            (65, 2), (30, 2), (None, 0), (50, 1), (None, 0), (None, 0),
        ]
        assert [w["mine"] for w in weeks] == [150, 20, 10, 0, 0, 0]
        assert [w["highest"] for w in weeks] == [200, 100, 100, 50, 0, 0]
        assert visual["bestWeek"] == 1
        peak = next(b["visual"] for b in recap["seasonSaga"]["beats"] if b["kind"] == "peak_week")
        assert peak["score"] == 150 and peak["wasWeeklyLeader"] is False
        staff = trend(build_season_rewind(admin, season))
        assert staff["weeks"][0]["crew"] == 93.3
        assert staff["weeks"][0]["peerPlayers"] == 3


def test_weekly_average_preserves_zero_and_excludes_post_cutoff_completions(app):
    with app.app_context():
        me, peer = player("CutoffWeeklyMe"), player("CutoffWeeklyPeer")
        score(me, "word", "2026-09-23", 20)
        score(me, "word", "2026-09-30", 40)
        score(peer, "word", "2026-09-23", 0)
        score(peer, "word", "2026-09-30", 90)
        season = get_season_for_date(date(2026, 10, 26))
        finalize_season_championships(season["id"], today=date(2026, 11, 2))
        db = get_db()
        frozen = db.execute("SELECT snapshot_json FROM season_badge_finalizations WHERE season_id = ?",
                            (season["id"],)).fetchone()
        cutoff = datetime.fromisoformat(json.loads(frozen["snapshot_json"])["score_cutoff"])
        db.execute("UPDATE game_completions SET completed_at = ? WHERE profile_id = ? AND game_date = ?",
                   ((cutoff + timedelta(seconds=1)).isoformat(), peer, "2026-09-30"))
        db.commit()
        weeks = trend(build_season_rewind(me, season))["weeks"]
        assert weeks[0]["crew"] == 0 and weeks[0]["peerPlayers"] == 1
        assert weeks[1]["crew"] is None and weeks[1]["peerPlayers"] == 0
        assert weeks[1]["highest"] == 40
