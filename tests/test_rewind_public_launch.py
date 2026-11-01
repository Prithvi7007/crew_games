"""Player-facing Rewind launch gate: official finals, own story, and CSS."""
import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash
from app.championships import finalize_season_championships
from app.db import (
    create_profile, finalize_game_stats, get_profile_by_id,
    get_season_for_date, profile_user_key, update_profile_role,
)
from app.season_rewind import rewind_url
from app.player_ui import static_asset_version


def player(username, role="player"):
    with patch("app.db._db_timestamp", return_value="2026-09-21T12:00:00"):
        p = create_profile(username, generate_password_hash("test-password"), "⭐",
                           generate_password_hash("test-key"))
    pid = int(p["id"])
    if role != "player":
        update_profile_role(pid, role)
    return pid


def login(client, pid):
    p = get_profile_by_id(pid)
    client.get("/login")
    with client.session_transaction() as sess:
        sess["user"] = {
            "profile_id": pid, "username": p["username"], "role": p["role"],
            "avatar": p["avatar"], "user_key": profile_user_key(pid),
            "session_version": int(p["session_version"]),
        }


def state(response):
    match = re.search(rb'<script[^>]+id="player-state"[^>]*>(.*?)</script>',
                      response.data, re.S)
    assert match is not None
    return json.loads(match.group(1))


def test_public_saga_requires_finalization_and_stays_personal(app, client):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        champion = player("LaunchChampion")
        runner = player("LaunchRunner")
        newcomer = player("LaunchNewcomer")
        admin = player("LaunchStaff", "admin")
        finalize_game_stats(profile_user_key(champion), "trivia", "2026-10-20", 95, True)
        finalize_game_stats(profile_user_key(runner), "trivia", "2026-10-21", 70, True)
        assert rewind_url(season, profile_id=champion, role="player") is None
        login(client, champion)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
            assert client.get("/rewind").status_code == 404

        result = finalize_season_championships(season["id"], today=date(2026, 11, 2))
        assert result["already_finalized"] is True
        assert rewind_url(season, profile_id=champion, role="player") == "/rewind"
        with patch("app.main.routes.crew_today", return_value=date(2026, 11, 2)):
            response = client.get("/rewind")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "private, no-store"
            data = state(response)
            assert data["rewindSeasonSagaPreview"] is True
            assert data["rewindFilmPrototype"] is False
            assert data["rewindPreviewPlayer"] is None
            assert data["rewind"]["finalized"] is True
            assert data["rewind"]["username"] == "LaunchChampion"
            kinds = [b["kind"] for b in data["rewind"]["seasonSaga"]["beats"]]
            assert kinds[0] == "welcome"
            assert not {"champion_opening", "season_podium", "season_game_master"} & set(kinds)
            vault = next(b for b in data["rewind"]["seasonSaga"]["beats"] if b["kind"] == "trophy_vault")
            assert vault["visual"]["celebrated"] == []
            assert not any(kind in {"winner", "winner_badge"} for kind in kinds)
            assert kinds[-2:] == ["legacy", "season_two"]
            for file in ("rewind-director.css", "rewind-cinema.css", "rewind-saga.css"):
                assert (f'/static/css/{file}?v={static_asset_version("css/"+file)}').encode() in response.data
            assert response.data.index(b"rewind-saga.css?v=") < response.data.index(b'id="crew-player-root"')

            for url in ("/rewind?player=LaunchRunner", "/rewind?prototype=1",
                        "/rewind?story=5", "/rewind?preview=1&prototype=1&story=5"):
                assert client.get(url).status_code == 404

            login(client, runner)
            r = state(client.get("/rewind"))["rewind"]
            assert r["username"] == "LaunchRunner" and r["points"] == 70
            assert r["seasonSaga"]["beats"][0]["kind"] == "welcome"
            assert not any(b["kind"] in {"season_podium", "season_game_master"}
                           for b in r["seasonSaga"]["beats"])
            assert any(b["kind"] == "podium" for b in r["seasonSaga"]["beats"])

            login(client, newcomer)
            honors = state(client.get("/rewind"))["rewind"]["seasonSaga"]
            assert honors["honorsOnly"] is True
            assert [b["kind"] for b in honors["beats"]] == ["season_podium", "season_game_master"]
            assert state(client.get("/games"))["shell"]["rewindUrl"] == "/rewind?honors=1"

            login(client, admin)
            staff = client.get("/rewind?preview=1&prototype=1&story=5&player=LaunchChampion")
            assert staff.status_code == 200
            assert state(staff)["rewindFilmPrototype"] is True
            assert state(staff)["rewindPreviewPlayer"] == "LaunchChampion"
            staff_kinds = [b["kind"] for b in state(staff)["rewind"]["seasonSaga"]["beats"]]
            assert staff_kinds[0] == "champion_opening" and "season_podium" in staff_kinds
            assert state(client.get("/rewind?preview=1"))["rewindSeasonSagaPreview"] is False


def test_public_cinema_exit_and_fingerprint_in_head():
    root = Path(__file__).resolve().parents[1]
    film = (root / "frontend/src/player/RewindPlayerCinema.jsx").read_text()
    head = (root / "app/templates/player_app.html").read_text()
    assert "data.rewindFilmPrototype===true" in film
    assert ": '/home';" in film
    assert "window.location.assign(destination)" in film and 'href="/home"' in film
    for name in ("rewind-director.css", "rewind-cinema.css", "rewind-saga.css"):
        assert name in head
        assert f'<link rel="stylesheet" href="/static/css/{name}"/>' not in film


def test_rewind_navigation_pill_uses_the_finalization_gate_across_player_pages(app, client):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        pid = player("PillPlayer")
        admin = player("PillAdmin", "admin")
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-10-20", 50, True)
        login(client, pid)
        assert state(client.get("/games"))["shell"]["rewindUrl"] is None
        login(client, admin)
        assert state(client.get("/games"))["shell"]["rewindUrl"] == "/rewind?preview=1"
        finalize_season_championships(season["id"], today=date(2026, 11, 2))
        login(client, pid)
        for url in ("/home?theater_preview=0", "/games", "/leaderboard", "/profile"):
            assert state(client.get(url))["shell"]["rewindUrl"] == "/rewind"


def test_game_master_manual_replay_starts_personal_and_keeps_earned_badges(app, client):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        overall = player("ReplayOverallChampion")
        master = player("ReplayGameMaster")
        finalize_game_stats(profile_user_key(overall), "word", "2026-10-21", 100, True)
        finalize_game_stats(profile_user_key(overall), "mystery", "2026-10-19", 100, True)
        finalize_game_stats(profile_user_key(master), "trivia", "2026-10-20", 80, True)
        finalize_season_championships(season["id"], today=date(2026, 11, 2))
        login(client, master)
        data = state(client.get("/rewind"))
        beats = data["rewind"]["seasonSaga"]["beats"]
        assert data["rewindLoginLaunch"] is None
        assert beats[0]["kind"] == "welcome"
        assert not any(b["kind"] in {"champion_opening", "season_podium", "season_game_master"}
                       for b in beats)
        vault = next(b for b in beats if b["kind"] == "trophy_vault")
        assert any(b["code"] == "season_trivia_master" for b in vault["visual"]["badges"])
        assert vault["visual"]["celebrated"] == []
        assert data["rewind"]["points"] == 80
