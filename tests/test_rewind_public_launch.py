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
        assert rewind_url(season, role="player") is None
        login(client, champion)
        with patch("app.main.routes.crew_today", return_value=date(2026, 10, 26)):
            assert client.get("/rewind").status_code == 404

        result = finalize_season_championships(season["id"], today=date(2026, 11, 2))
        assert result["already_finalized"] is True
        assert rewind_url(season, role="player") == "/rewind"
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
            assert kinds[:2] == ["winner", "winner_badge"]
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
            assert r["seasonSaga"]["beats"][0]["kind"] != "winner"

            login(client, newcomer)
            r = state(client.get("/rewind"))["rewind"]
            assert r["username"] == "LaunchNewcomer" and r["rank"] is None
            assert [b["kind"] for b in r["seasonSaga"]["beats"]] == [
                "season_podium", "season_game_master", "welcome", "legacy", "season_two"
            ]
            assert r["seasonSaga"]["beats"][0]["visual"]["podium"][0]["players"][0]["name"] == "LaunchChampion"
            assert state(client.get("/rewind?preview=1"))["rewindSeasonSagaPreview"] is True

            login(client, admin)
            staff = client.get("/rewind?preview=1&prototype=1&story=5&player=LaunchChampion")
            assert staff.status_code == 200
            assert state(staff)["rewindFilmPrototype"] is True
            assert state(staff)["rewindPreviewPlayer"] == "LaunchChampion"
            assert state(client.get("/rewind?preview=1"))["rewindSeasonSagaPreview"] is False


def test_public_cinema_exit_and_fingerprint_in_head():
    root = Path(__file__).resolve().parents[1]
    film = (root / "frontend/src/player/RewindPlayerCinema.jsx").read_text()
    head = (root / "app/templates/player_app.html").read_text()
    assert "data.rewindFilmPrototype===true" in film
    assert ": '/home';" in film
    assert "window.location.assign(back)" in film and "href={back}" in film
    for name in ("rewind-director.css", "rewind-cinema.css", "rewind-saga.css"):
        assert name in head
        assert f'<link rel="stylesheet" href="/static/css/{name}"/>' not in film

