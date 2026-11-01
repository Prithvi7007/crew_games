"""A previous-season Rewind belongs only to accounts that played that season."""
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from app.championships import finalize_season_championships
from app.db import (
    create_profile, finalize_game_stats, get_db, get_season_for_date,
    profile_user_key, update_profile_role,
)
from app.rewind_login import rewind_completed
from app.schedule import CREW_TIMEZONE


def state(response):
    match = re.search(rb'<script[^>]+id="player-state"[^>]*>(.*?)</script>', response.data, re.S)
    assert match is not None
    return json.loads(match.group(1))


def setup_player(*, joined_offset=-1, played=True, role="player"):
    season = get_season_for_date(date(2026, 10, 26))
    boundary = datetime.combine(
        season["end_date"] + timedelta(days=1), time.min, ZoneInfo(CREW_TIMEZONE),
    ).astimezone(timezone.utc)
    joined = boundary + timedelta(seconds=joined_offset)
    with patch("app.db._db_timestamp", return_value=joined.replace(tzinfo=None).isoformat()):
        row = create_profile("EligibilityPlayer", generate_password_hash("test-password"),
                             "⭐", generate_password_hash("test-key"))
    pid = int(row["id"])
    if role != "player":
        update_profile_role(pid, role)
    # An archive attempt before a delayed finalization must not make a
    # Season 2 signup eligible for a Season 1 story. Zero scores count as play.
    if played:
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-10-20", 0, True)
        get_db().execute("UPDATE game_completions SET completed_at = ? WHERE profile_id = ?",
                         ((boundary + timedelta(hours=2)).replace(tzinfo=None).isoformat(), pid))
        get_db().commit()
    frozen_at = boundary + timedelta(days=2)
    with patch("app.championships.datetime") as clock:
        clock.now.return_value = frozen_at
        finalize_season_championships(season["id"], today=season["end_date"] + timedelta(days=3))
    return pid, season


def sign_in(client):
    client.get("/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    return client.post("/login", data={
        "username": "EligibilityPlayer", "password": "test-password", "csrf_token": token,
    })


@pytest.mark.parametrize("joined_offset,eligible", [(-1, True), (0, False), (1, False)])
def test_season_membership_controls_login_navigation_and_direct_replay(app, client, joined_offset, eligible):
    with app.app_context():
        pid, season = setup_player(joined_offset=joined_offset)
        response = sign_in(client)
        assert response.location == ("/rewind?intro=1" if eligible else "/home")
        nav = state(client.get("/games"))["shell"]
        assert nav["rewindUrl"] == ("/rewind" if eligible else None)
        manual = client.get("/rewind")
        if eligible:
            assert manual.status_code == 200
            assert state(manual)["rewind"]["gamesPlayed"] == 1
            assert state(manual)["rewind"]["seasonSaga"]["beats"][0]["kind"] == "welcome"
            assert state(client.get("/rewind?intro=1"))["rewindLoginLaunch"] is not None
        else:
            assert manual.status_code == 302 and manual.location == "/home"
            assert client.get("/rewind?intro=1").location == "/home"
            # Even a leftover premiere session cannot turn this account into a participant.
            with client.session_transaction() as session:
                session["rewind_login_intro"] = {"profile_id": pid, "season_id": season["id"],
                                                "return_url": "/home"}
                token = session["csrf_token"]
            assert client.get("/rewind?intro=1").location == "/home"
            assert client.post("/api/rewind/completion", json={"action": "finished"},
                               headers={"X-CSRFToken": token}).status_code == 404
        assert not rewind_completed(pid)


def test_an_older_account_without_eligible_play_gets_no_empty_rewind(app, client):
    with app.app_context():
        setup_player(played=False)
        assert sign_in(client).location == "/home"
        assert state(client.get("/games"))["shell"]["rewindUrl"] is None
        assert client.get("/rewind").location == "/home"


def test_new_staff_account_keeps_explicit_film_previews_without_a_personal_premiere(app, client):
    with app.app_context():
        setup_player(joined_offset=1, role="owner")
        assert sign_in(client).location == "/home"
        assert state(client.get("/games"))["shell"]["rewindUrl"] is None
        response = client.get("/rewind?preview=1&prototype=1&story=5")
        assert response.status_code == 200
        assert state(response)["rewindFilmPrototype"] is True
        assert state(response)["rewindLoginLaunch"] is None
