"""Personal CREW Rewind only becomes public after approved championship finalization."""
from datetime import date
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app.championships import finalize_season_championships
from app.db import (
    create_profile, finalize_game_stats, get_profile_by_id,
    get_season_for_date, profile_user_key, update_profile_role,
)
from app.season_rewind import build_season_rewind, rewind_url
from app.badge_store import award_badges


def _player(name, role="player"):
    row = create_profile(
        name, generate_password_hash("correct horse battery staple"),
        "⭐", generate_password_hash("ORBIT-NOVA-COMET-RIVER-ABCD"),
    )
    profile_id = int(row["id"])
    if role != "player":
        update_profile_role(profile_id, role)
    return profile_id


def _login(client, app, pid):
    with app.app_context():
        profile = get_profile_by_id(pid)
        user = {
            "profile_id": pid, "username": profile["username"],
            "avatar": profile["avatar"], "role": profile["role"],
            "user_key": profile_user_key(pid),
            "session_version": int(profile["session_version"]),
        }
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = user


def test_rewind_is_locked_to_players_until_championship_approval(app, client):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        player_id = _player("RewindPlayer")
        admin_id = _player("RewindAdmin", role="admin")
        finalize_game_stats(profile_user_key(player_id), "trivia", "2026-10-20", 90, True)
        assert rewind_url(season, role="player") is None
        assert rewind_url(season, role="admin") == "/rewind?preview=1"
        assert build_season_rewind(player_id, season) is None

    _login(client, app, player_id)
    with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
        assert client.get("/rewind").status_code == 404
        assert client.get("/rewind?preview=1").status_code == 404
        assert client.get("/rewind?preview=1&prototype=1").status_code == 404

    _login(client, app, admin_id)
    with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
        preview = client.get("/rewind?preview=1")
        assert preview.status_code == 200
        assert b"CREW REWIND" not in preview.data  # React renders client-side
        assert b'"preview": true' in preview.data
        assert client.get("/rewind").status_code == 404
        film = client.get("/rewind?preview=1&prototype=1")
        assert film.status_code == 200
        assert b'"rewindFilmPrototype": true' in film.data


def test_rewind_uses_real_earned_metrics_and_exact_season_weeks(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        pid = _player("RewindScore")
        other = _player("RewindOther")
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-09-22", 80, True)
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-09-29", 100, True)
        finalize_game_stats(profile_user_key(pid), "word", "2026-09-23", 60, True)
        finalize_game_stats(profile_user_key(other), "mystery", "2026-10-05", 70, True)
        award_badges(pid, season["id"], ["brainiac"])
        data = build_season_rewind(pid, season, admin_preview=True)

    assert data["points"] == 240
    assert data["insights"]["averageScore"] == 80
    assert data["insights"]["gamesTried"] == 2
    assert data["insights"]["longestWeeklyStreak"] == 2
    assert data["insights"]["highestGame"]["score"] == 100
    assert data["insights"]["momentum"] is None
    assert data["gamesPlayed"] == 3
    assert data["gamesTotal"] == 24
    assert data["weeksActive"] == 2
    assert data["bestWeek"] == {"number": 1, "points": 140, "played": 2}
    assert len(data["weeklyScores"]) == 6
    assert data["weeklyScores"][0]["points"] == 140
    assert data["weeklyScores"][1]["points"] == 100
    assert len(data["weeklyGameScores"]) == 6
    assert data["weeklyGameScores"][0]["games"]["trivia"] == 80
    assert data["weeklyGameScores"][0]["games"]["word"] == 60
    assert data["weeklyGameScores"][1]["games"]["trivia"] == 100
    assert data["signature"]["key"] == "trivia"
    assert data["signature"]["average"] == 90
    assert data["rank"] == 1
    assert data["participants"] == 2
    assert data["badges"]["featured"]["name"] == "Brainiac"
    assert data["preview"] is True


def test_approved_rewind_stays_frozen_after_late_archive_play(app, client):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        pid = _player("FrozenRewind")
        other = _player("LateRewind")
        finalize_game_stats(profile_user_key(pid), "word", "2026-10-21", 75, True)
        finalize_game_stats(profile_user_key(other), "mystery", "2026-10-19", 65, True)
        finalized = finalize_season_championships(season["id"], today=date(2026, 11, 2))
        assert finalized["already_finalized"] is True
        before = build_season_rewind(pid, season)
        # A player can still catch up on old puzzles; championship Rewind stays
        # pinned to the reviewed score cutoff.
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-10-27", 100, False)
        from app.db import get_db
        db = get_db()
        db.execute(
            "UPDATE game_completions SET completed_at = ? WHERE profile_id = ? AND game_date = ?",
            ("2099-01-01T00:00:00", pid, "2026-10-27"),
        )
        db.commit()
        after = build_season_rewind(pid, season)
        assert rewind_url(season) == "/rewind"

    assert after["preview"] is False
    assert after["points"] == before["points"] == 75
    assert after["gamesPlayed"] == before["gamesPlayed"] == 1
    assert after["insights"] == before["insights"]
    assert after["weeklyGameScores"] == before["weeklyGameScores"]
    assert after["signature"]["key"] == "word"
    assert after["champion"] is True

    _login(client, app, pid)
    with patch("app.main.routes.crew_today", return_value=date(2026, 11, 2)):
        response = client.get("/rewind")
    assert response.status_code == 200
    assert b"FrozenRewind" in response.data
    assert b'"preview": false' in response.data


def test_rewind_zero_score_player_gets_kind_story_without_fake_rank(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        pid = _player("RewindNewcomer")
        data = build_season_rewind(pid, season, admin_preview=True)

    assert data["points"] == 0
    assert data["gamesPlayed"] == 0
    assert data["rank"] is None
    assert data["signature"] is None
    assert data["bestWeek"] is None
    assert data["insights"]["playStyle"]["title"] == "THE NEXT CHAPTER"
    assert data["insights"]["averageScore"] is None
    assert data["persona"] == "The CREW Original"
    assert data["badges"]["count"] == 0
