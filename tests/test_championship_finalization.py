"""Season championships are manually reviewed, frozen and idempotent."""
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app.championships import preview_season_championships, finalize_season_championships
from app.db import create_profile, finalize_game_stats, get_db, get_season_for_date, profile_user_key
from app.badge_store import get_badge_awards


def _player(name):
    row = create_profile(name, generate_password_hash("championship-long-passphrase"),
                         "⭐", generate_password_hash("championship-recovery-long"))
    return int(row["id"])


def test_championship_preview_is_read_only_and_awarding_requires_season_end(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 20))
        winner = _player("WinnerChampion")
        finalize_game_stats(profile_user_key(winner), "trivia", "2026-10-20", 100, True)
        preview = preview_season_championships(season["id"], today=date(2026, 11, 1))
        assert preview["winners"]["season_champion"][0]["profile_id"] == winner
        assert preview["winners"]["season_trivia_master"][0]["profile_id"] == winner
        assert get_badge_awards(winner, season["id"]) == []
        with pytest.raises(ValueError, match="ended"):
            finalize_season_championships(season["id"], today=date(2026, 10, 30))


def test_tied_winners_share_first_place_and_finalization_is_idempotent(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 20))
        alpha = _player("AlphaChampion")
        beta = _player("BetaChampion")
        for player_id in (alpha, beta):
            finalize_game_stats(profile_user_key(player_id), "trivia", "2026-10-20", 100, True)
        preview = preview_season_championships(season["id"], today=date(2026, 11, 1))
        assert {w["profile_id"] for w in preview["winners"]["season_champion"]} == {alpha, beta}
        first = finalize_season_championships(season["id"], today=date(2026, 11, 1))
        assert first["already_finalized"] is True
        assert first["new_awards"] == 4
        again = finalize_season_championships(season["id"], today=date(2026, 11, 2))
        assert again["new_awards"] == 0
        for player_id in (alpha, beta):
            names = {a["badge_code"] for a in get_badge_awards(player_id, season["id"])}
            assert {"season_champion", "season_trivia_master"} <= names
        saved = get_db().execute(
            "SELECT COUNT(*) AS cnt FROM season_badge_finalizations WHERE season_id = ?",
            (season["id"],)
        ).fetchone()
        assert saved["cnt"] == 1


def test_championship_snapshot_freezes_winners_after_approval(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 20))
        leader = _player("SnapshotLeader")
        other = _player("SnapshotOther")
        finalize_game_stats(profile_user_key(leader), "mystery", "2026-10-19", 100, True)
        initial = finalize_season_championships(season["id"], today=date(2026, 11, 1))
        assert initial["winners"]["season_champion"][0]["profile_id"] == leader
        finalize_game_stats(profile_user_key(other), "mystery", "2026-10-19", 100, True)
        finalize_game_stats(profile_user_key(other), "trivia", "2026-10-20", 100, True)
        frozen = preview_season_championships(season["id"], today=date(2026, 11, 2))
        assert frozen["already_finalized"] is True
        assert frozen["winners"]["season_champion"][0]["profile_id"] == leader
        assert not any(a["badge_code"] == "season_champion"
                       for a in get_badge_awards(other, season["id"]))


def test_admin_championship_review_requires_login_and_explicit_confirmation(app, client):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 20))
        season_id = season["id"]
    url = f"/admin/seasons/{season_id}/championships"
    response = client.get(url)
    assert response.status_code in (302, 401, 403)
    admin_id = None
    with app.app_context():
        admin_id = _player("ChampionshipAdmin")
        from app.db import get_profile_by_id, update_profile_role
        update_profile_role(admin_id, "admin")
        p = get_profile_by_id(admin_id)
    client.get("/login")
    with client.session_transaction() as session:
        session["user"] = {
            "profile_id": admin_id, "username": p["username"], "role": "admin",
            "avatar": p["avatar"], "user_key": profile_user_key(admin_id),
            "session_version": int(p["session_version"]),
        }
        token = session["csrf_token"]
    review = client.get(url)
    assert review.status_code == 200
    assert b"Season championships" in review.data
    response = client.post(url, data={"csrf_token": token, "confirm": "WRONG"})
    assert response.status_code == 302
    with app.app_context():
        row = get_db().execute(
            "SELECT COUNT(*) AS n FROM season_badge_finalizations WHERE season_id = ?",
            (season_id,)
        ).fetchone()
        assert row["n"] == 0
