"""One-time own-player Rewind launch after season finalization."""
import json
import re
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.championships import finalize_season_championships
from app.db import (
    create_profile, finalize_game_stats, get_db, get_season_for_date,
    profile_user_key, update_profile_role,
)
from app.rewind_login import REWIND_TOUR_KEY, rewind_completed, safe_local_target


def player(name, role="player"):
    row = create_profile(name, generate_password_hash("test-password"), "⭐",
                         generate_password_hash("test-recovery"))
    if role != "player":
        update_profile_role(row["id"], role)
    return int(row["id"])


def prepare(name="LoginFilmPlayer", role="player", finalized=True, played=True):
    pid = player(name, role)
    if played:
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-10-20", 80, True)
    season = get_season_for_date(date(2026, 10, 26))
    if finalized:
        finalize_season_championships(season["id"], today=date(2026, 11, 2))
    return pid


def login(client, name="LoginFilmPlayer", target=""):
    client.get("/login")
    with client.session_transaction() as sess:
        token = sess["csrf_token"]
    return client.post("/login" + target, data={
        "username": name, "password": "test-password", "csrf_token": token,
    })


def payload(response):
    match = re.search(rb'<script[^>]+id="player-state"[^>]*>(.*?)</script>', response.data, re.S)
    assert match is not None
    return json.loads(match.group(1))


def complete(client, action):
    client.get("/rewind?intro=1")
    with client.session_transaction() as sess:
        token = sess["csrf_token"]
    return client.post("/api/rewind/completion", json={"action": action},
                       headers={"X-CSRFToken": token})


@pytest.mark.parametrize("role", ["player", "admin", "owner"])
def test_first_login_gets_own_official_film_once(app, client, role):
    with app.app_context():
        pid = prepare(role=role)
        response = login(client)
        assert response.status_code == 302
        assert response.location == "/rewind?intro=1"
        data = payload(client.get(response.location))
        assert data["rewindLoginLaunch"]["returnUrl"] == "/home"
        assert data["rewindCompletionUrl"] == "/api/rewind/completion"
        assert data["rewind"]["username"] == "LoginFilmPlayer"
        assert data["rewind"]["finalized"] is True
        assert data["rewindFilmPrototype"] is False
        assert not rewind_completed(pid)
        assert complete(client, "finished").status_code == 200
        assert rewind_completed(pid)
        # A fresh login clears the session; the database marker still suppresses it.
        assert login(client).location == "/home"


@pytest.mark.parametrize("action", ["finished", "skipped"])
def test_dismissal_is_personal_idempotent_and_preserves_competition(app, client, action):
    with app.app_context():
        pid = prepare()
        other = player("OtherLoginPlayer")
        db = get_db()
        before = {t: [dict(r) for r in db.execute("SELECT * FROM " + t).fetchall()]
                  for t in ("game_completions", "badge_awards", "season_badge_finalizations")}
        login(client)
        assert complete(client, action).status_code == 200
        assert complete(client, action).status_code == 200
        rows = db.execute("SELECT * FROM trophy_tour_completions WHERE tour_key = ?",
                          (REWIND_TOUR_KEY,)).fetchall()
        assert len(rows) == 1
        assert rows[0]["profile_id"] == pid and rows[0]["completion_type"] == action
        assert not rewind_completed(other)
        assert {t: [dict(r) for r in db.execute("SELECT * FROM " + t).fetchall()]
                for t in before} == before


@pytest.mark.parametrize("finalized,played", [(False, True), (True, False)])
def test_unfinalized_and_nonparticipant_logins_keep_normal_destination(app, client, finalized, played):
    with app.app_context():
        prepare(finalized=finalized, played=played)
        assert login(client).location == "/home"


def test_existing_session_home_visit_launches_once_without_redirect_loop(app, client):
    with app.app_context():
        pid = prepare()
        login(client)
        # Simulate a session signed in before this feature was deployed.
        with client.session_transaction() as sess:
            sess.pop("rewind_login_intro", None)
        assert client.get("/home").location == "/rewind?intro=1"
        assert client.get("/home").status_code == 200
        assert not rewind_completed(pid)
        assert complete(client, "skipped").status_code == 200
        assert client.get("/home").status_code == 200


def test_deep_links_are_preserved_and_admin_destinations_are_not_interrupted(app, client):
    with app.app_context():
        prepare(role="owner")
        response = login(client, target="?next=/games")
        assert response.location == "/rewind?intro=1"
        assert payload(client.get(response.location))["rewindLoginLaunch"]["returnUrl"] == "/games"
        assert login(client, target="?next=/admin/settings").location == "/admin/settings"


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/\\evil.example", "/home\n"])
def test_return_destination_is_local_only(target):
    assert safe_local_target(target) == "/home"


def test_preview_and_untrusted_query_cannot_enable_autoplay_or_complete_for_another_player(app, client):
    with app.app_context():
        pid = prepare(role="owner")
        other = player("OtherFilmTarget")
        login(client)
        staff = payload(client.get("/rewind?preview=1&prototype=1&story=5&player=OtherFilmTarget"))
        assert staff["rewindLoginLaunch"] is None
        assert staff["rewindCompletionUrl"] is None
        with client.session_transaction() as sess:
            token = sess["csrf_token"]
        assert client.post("/api/rewind/completion", json={"action": "finished"}).status_code == 400
        assert client.post("/api/rewind/completion", json={"action": "finished", "profile_id": other},
                           headers={"X-CSRFToken": token}).status_code == 400
        assert not rewind_completed(pid) and not rewind_completed(other)
        with client.session_transaction() as sess:
            sess.pop("rewind_login_intro", None)
        assert payload(client.get("/rewind?intro=1"))["rewindLoginLaunch"] is None


def test_optional_tracking_failure_does_not_block_login(app, client):
    with app.app_context():
        prepare()
        with patch("app.rewind_login._eligible_season", side_effect=SQLAlchemyError("offline")):
            assert login(client).location == "/home"


def test_trophy_tour_marker_does_not_suppress_rewind(app, client):
    from app.trophy_tour import complete_tour, tour_completed
    with app.app_context():
        pid = prepare()
        complete_tour(pid, "finished")
        assert tour_completed(pid)
        assert not rewind_completed(pid)
        assert login(client).location == "/rewind?intro=1"


def test_late_archive_only_player_is_not_given_a_previous_season_premiere(app, client):
    with app.app_context():
        pid = prepare(played=False)
        finalize_game_stats(profile_user_key(pid), "word", "2026-10-21", 50, True)
        db = get_db()
        db.execute("UPDATE game_completions SET completed_at = ? WHERE profile_id = ?",
                   ("2099-01-01T00:00:00", pid))
        db.commit()
        assert login(client).location == "/home"


def test_completion_storage_failure_keeps_the_route_back_to_home_open(app, client):
    with app.app_context():
        prepare()
        login(client)
        with patch("app.main.routes.complete_rewind", side_effect=SQLAlchemyError("offline")):
            assert complete(client, "skipped").status_code == 503
        assert client.get("/home").status_code == 200
