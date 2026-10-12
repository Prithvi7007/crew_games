"""October 19 CREW trophy launch: gating, real awards, persistence and preview."""
import json
import re
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app.badge_store import award_badges
from app.db import create_profile, get_profile_by_id, get_season_for_date, profile_user_key
from app.trophy_tour import TOUR_KEY


def _profile(app, name):
    with app.app_context():
        return int(create_profile(
            name, generate_password_hash("tour-password-example"),
            "🏆", generate_password_hash("tour-recovery-example"),
        )["id"])


def _signin(client, app, profile_id, role="player"):
    with app.app_context():
        profile = get_profile_by_id(profile_id)
    client.get("/login")
    with client.session_transaction() as sess:
        csrf = sess["csrf_token"]
        sess.clear()
        sess["csrf_token"] = csrf
        sess["user"] = {
            "profile_id": profile_id, "username": profile["username"],
            "avatar": profile["avatar"], "role": role,
            "user_key": profile_user_key(profile_id),
            "session_version": int(profile["session_version"]),
        }
        return sess["csrf_token"]


def _data(response):
    match = re.search(r'<script[^>]*id="player-state"[^>]*>(.*?)</script>',
                      response.get_data(as_text=True), flags=re.DOTALL)
    assert match
    return json.loads(match.group(1))


def _clock(monkeypatch, day):
    monkeypatch.setattr("app.trophy_tour.crew_today", lambda: day)
    monkeypatch.setattr("app.trophy_access.crew_today", lambda: day)
    monkeypatch.setattr("app.main.routes.crew_today", lambda: day)


def _send(client, csrf, action):
    return client.post("/api/trophies/tour", json={"action": action},
                       headers={"X-CSRFToken": csrf})


def test_launch_gate_and_no_early_player_tour(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 18))
    player = _profile(app, "TourEarly")
    token = _signin(client, app, player)
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None
    assert _send(client, token, "finished").status_code == 404
    _clock(monkeypatch, date(2026, 10, 19))
    assert _data(client.get("/home"))["shell"]["trophyTour"]["earnedCount"] == 0


def test_personalized_badges_and_other_players_are_private(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 19))
    player = _profile(app, "TourWinner")
    other = _profile(app, "TourOther")
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 7))
        award_badges(player, season["id"], ["brainiac", "word_wizard"], source_date="2026-10-07")
        award_badges(other, season["id"], ["unicorn"], source_date="2026-10-07")
    _signin(client, app, player)
    tour = _data(client.get("/home"))["shell"]["trophyTour"]
    assert tour["earnedCount"] == 2
    assert tour["seasonNumber"] == 1
    assert {item["code"] for item in tour["badges"]} == {"brainiac", "word_wizard"}
    assert "unicorn" not in json.dumps(tour)
    assert all("awardId" not in item for item in tour["badges"])


@pytest.mark.parametrize("action", ["finished", "skipped"])
def test_completion_is_idempotent_and_persists_across_sessions(app, client, monkeypatch, action):
    _clock(monkeypatch, date(2026, 10, 19))
    player = _profile(app, "Tour" + action.title())
    csrf = _signin(client, app, player)
    assert _data(client.get("/home"))["shell"]["trophyTour"]
    assert _send(client, csrf, action).status_code == 200
    assert _send(client, csrf, action).status_code == 200
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None
    with app.app_context():
        from app.db import get_db
        row = get_db().execute(
            "SELECT completion_type FROM trophy_tour_completions WHERE profile_id = ? AND tour_key = ?",
            (player, TOUR_KEY),
        ).fetchone()
        assert row["completion_type"] == action
    client.post("/logout", headers={"X-CSRFToken": csrf})
    _signin(client, app, player)
    assert _data(client.get("/games"))["shell"]["trophyTour"] is None


def test_maybe_later_is_session_only_and_returns_after_new_login(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 19))
    player = _profile(app, "TourLater")
    token = _signin(client, app, player)
    assert _send(client, token, "later").status_code == 200
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None
    with app.app_context():
        from app.db import get_db
        assert get_db().execute(
            "SELECT 1 FROM trophy_tour_completions WHERE profile_id = ?", (player,)
        ).fetchone() is None
    _signin(client, app, player)
    assert _data(client.get("/home"))["shell"]["trophyTour"] is not None


def test_admin_preview_before_launch_is_non_persistent(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 12))
    player = _profile(app, "TourAdmin")
    _signin(client, app, player, role="admin")
    ordinary = _data(client.get("/trophies"))
    assert ordinary["shell"]["trophyTour"] is None
    preview = _data(client.get("/trophies?trophy_tour_preview=1"))
    assert preview["shell"]["trophyTour"]["preview"] is True
    assert preview["tourReplay"]["preview"] is True
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None


def test_csrf_validation_anonymous_invalid_action_and_gameplay_safety(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 19))
    assert client.post("/api/trophies/tour", json={"action": "finished"}).status_code == 400
    player = _profile(app, "TourSafety")
    csrf = _signin(client, app, player)
    assert client.post("/api/trophies/tour", json={"action": "finished"}).status_code == 400
    assert _send(client, csrf, "invalid").status_code == 400
    assert _data(client.get("/home"))["shell"]["trophyTour"] is not None
    monkeypatch.setattr("app.trophy_tour.tour_completed", lambda _profile: (_ for _ in ()).throw(
        __import__("sqlalchemy").exc.OperationalError("SELECT", {}, Exception("unavailable"))
    ))
    response = client.get("/home")
    assert response.status_code == 200
    assert _data(response)["shell"]["trophyTour"] is None


def test_tour_can_be_disabled_without_disabling_trophies(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 19))
    player = _profile(app, "TourDisabled")
    token = _signin(client, app, player)
    app.config["TROPHY_TOUR_ENABLED"] = False
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None
    assert _data(client.get("/trophies"))["tourReplay"] is None
    assert _send(client, token, "finished").status_code == 404
    assert client.get("/trophies").status_code == 200


def test_replay_payload_available_after_completion(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 19))
    player = _profile(app, "TourReplay")
    token = _signin(client, app, player)
    assert _send(client, token, "finished").status_code == 200
    trophies = _data(client.get("/trophies"))
    assert trophies["shell"]["trophyTour"] is None
    assert trophies["tourReplay"]["preview"] is True




def test_real_login_redirect_shows_tour_on_destination(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 19))
    _profile(app, "TourLogin")
    client.get("/login")
    with client.session_transaction() as sess:
        token = sess["csrf_token"]
    response = client.post(
        "/login", data={"username": "TourLogin", "password": "tour-password-example",
                        "csrf_token": token}, follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")
    assert _data(client.get(response.headers["Location"]))["shell"]["trophyTour"] is not None


def test_late_first_login_reveals_last_started_season(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 11, 3))
    player = _profile(app, "TourLate")
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 7))
        award_badges(player, season["id"], ["word_wizard"], source_date="2026-10-07")
    _signin(client, app, player)
    tour = _data(client.get("/home"))["shell"]["trophyTour"]
    assert tour["earnedCount"] == 1
    assert tour["seasonNumber"] == 1

def test_tour_frontend_contracts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    component = (root / "frontend/src/player/TrophyWelcomeTour.jsx").read_text()
    shell = (root / "frontend/src/player/main.jsx").read_text()
    assert 'aria-modal="true"' in component
    assert "prefers-reduced-motion:reduce" in (root / "frontend/src/player/styles/trophy-tour.css").read_text()
    assert "BadgeMedallion" in component
    assert "crew-tour-badges" in component
    assert "PlayerWithTour" in shell
    assert "onReplayTour" in shell
