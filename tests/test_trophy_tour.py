"""October 19 CREW trophy launch: gating, real awards, persistence and preview."""
import json
import re
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app.badge_store import award_badges
from app.db import create_profile, get_profile_by_id, get_season_for_date, profile_user_key, update_profile_role
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
    assert ordinary["shell"]["trophyTour"] is not None
    assert ordinary["shell"]["trophyTour"]["preview"] is False
    preview = _data(client.get("/trophies?trophy_tour_preview=1"))
    assert preview["shell"]["trophyTour"]["preview"] is True
    assert preview["tourReplay"]["preview"] is True
    # Preview never persists, so admin remains eligible for their real welcome.
    assert _data(client.get("/home"))["shell"]["trophyTour"]["preview"] is False


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
    assert "TrophyWelcomeTour" in shell
    assert "data.shell?.trophyTour" in shell
    assert "trophy_tour_preview=1" not in shell  # Preview remains server-driven.


def test_trophy_room_starts_at_collection_without_redundant_hero():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    component = (root / "frontend/src/player/TrophyRoom.jsx").read_text()
    styles = (root / "frontend/src/player/styles/trophies.css").read_text()
    shell = (root / "frontend/src/player/main.jsx").read_text()
    assert "trophy-simple-header" not in component
    assert "CREW ACHIEVEMENTS" not in component
    assert "Your badges" not in component
    assert "Replay welcome tour" not in component
    assert "trophy-season-row" not in component
    assert "ACHIEVEMENT COLLECTION" in component
    assert '<h1 id="trophy-collection-title">All badges' in component
    assert "trophy-filters" in component
    assert "trophy-badge-grid" in component
    assert "saveSlot" in component
    assert ".trophy-section-header h1" in styles
    assert "PlayerWithTour" in shell
    assert "TrophyWelcomeTour" in shell
    assert "data.shell?.trophyTour" in shell


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_early_admin_owner_login_auto_tour_persists_completion(app, client, monkeypatch, role):
    _clock(monkeypatch, date(2026, 10, 12))
    profile_id = _profile(app, "Early" + role.title())
    with app.app_context():
        update_profile_role(profile_id, role)
    # Real sign-in followed by the redirected landing page, not a manual preview URL.
    client.get("/login")
    with client.session_transaction() as sess:
        token = sess["csrf_token"]
    login = client.post(
        "/login",
        data={"username": "Early" + role.title(), "password": "tour-password-example",
              "csrf_token": token},
        follow_redirects=False,
    )
    assert login.status_code == 302
    home = _data(client.get(login.headers["Location"]))
    assert home["shell"]["trophyTour"]["preview"] is False
    # The real login rotates the CSRF token together with the session.
    with client.session_transaction() as sess:
        fresh_token = sess["csrf_token"]
    assert _send(client, fresh_token, "finished").status_code == 200
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None
    with app.app_context():
        from app.db import get_db
        row = get_db().execute(
            "SELECT completion_type FROM trophy_tour_completions WHERE profile_id=? AND tour_key=?",
            (profile_id, TOUR_KEY),
        ).fetchone()
        assert row["completion_type"] == "finished"
    # Ordinary players must still be blocked prior to the public reveal.
    player = _profile(app, "EarlyOther" + role.title())
    player_csrf = _signin(client, app, player)
    assert _data(client.get("/home"))["shell"]["trophyTour"] is None
    assert _send(client, player_csrf, "finished").status_code == 404


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_badge_preview_all_catalog_and_profile_without_real_awards(
    app, client, monkeypatch, role,
):
    from app.badges import BADGES
    from app.badge_store import get_badge_awards, get_showcase
    _clock(monkeypatch, date(2026, 10, 12))
    player = _profile(app, "Preview" + role.title())
    with app.app_context():
        update_profile_role(player, role)
    csrf = _signin(client, app, player, role=role)
    page = _data(client.get("/trophies"))
    assert page["trophyPreview"]["enabled"] is True
    assert page["trophyPreview"]["badgeCode"] is None
    assert page["earnedCount"] == 0
    assert len(page["badges"]) == len(BADGES) == 21
    assert all(item["earned"] is False and item["awardId"] is None for item in page["badges"])
    assert page["trophyPreview"]["url"] == "/api/trophies/preview-badge"
    for definition in BADGES:
        response = client.post("/api/trophies/preview-badge",
                               json={"badgeCode": definition.code},
                               headers={"X-CSRFToken": csrf})
        assert response.status_code == 200
        assert response.get_json()["badgeCode"] == definition.code
        profile_data = _data(client.get("/profile"))
        badge = profile_data["equippedBadge"]
        assert badge["code"] == definition.code
        assert badge["preview"] is True
        assert badge["name"] == definition.name
    selected = _data(client.get("/trophies"))
    assert selected["trophyPreview"]["badgeCode"] == BADGES[-1].code
    with app.app_context():
        assert get_badge_awards(player, page["selectedSeason"]["id"]) == []
        assert get_showcase(player) == []
    assert client.post("/api/trophies/preview-badge", json={"badgeCode": None},
                       headers={"X-CSRFToken": csrf}).status_code == 200
    assert _data(client.get("/profile"))["equippedBadge"] is None


def test_badge_preview_blocks_players_invalid_codes_and_csrf(app, client, monkeypatch):
    _clock(monkeypatch, date(2026, 10, 12))
    player = _profile(app, "PreviewPublic")
    csrf = _signin(client, app, player)
    assert client.post("/api/trophies/preview-badge",
                       json={"badgeCode": "unicorn"},
                       headers={"X-CSRFToken": csrf}).status_code == 404
    admin = _profile(app, "PreviewGateAdmin")
    token = _signin(client, app, admin, role="admin")
    assert client.post("/api/trophies/preview-badge",
                       json={"badgeCode": "unicorn"}).status_code == 400
    for value in ["fake_badge", 1, True, {}, []]:
        assert client.post("/api/trophies/preview-badge",
                           json={"badgeCode": value},
                           headers={"X-CSRFToken": token}).status_code == 400
    assert client.post("/api/trophies/preview-badge", json={},
                       headers={"X-CSRFToken": token}).status_code == 400
    assert _data(client.get("/trophies"))["trophyPreview"]["badgeCode"] is None


def test_preview_is_session_only_and_real_showcase_stays_owned(app, client, monkeypatch):
    from app.badge_store import award_badges, get_showcase
    _clock(monkeypatch, date(2026, 10, 19))
    admin = _profile(app, "PreviewRealAdmin")
    csrf = _signin(client, app, admin, role="admin")
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 12))
        award_badges(admin, season["id"], ["case_closed"])
    real_award = next(item for item in _data(client.get("/trophies"))["badges"]
                      if item["code"] == "case_closed")["awardId"]
    saved = client.post("/api/trophies/showcase",
                        json={"slot": 1, "awardId": real_award},
                        headers={"X-CSRFToken": csrf})
    assert saved.status_code == 200
    preview = client.post("/api/trophies/preview-badge",
                          json={"badgeCode": "unicorn"},
                          headers={"X-CSRFToken": csrf})
    assert preview.status_code == 200
    assert _data(client.get("/profile"))["equippedBadge"]["code"] == "unicorn"
    with app.app_context():
        assert get_showcase(admin)[0]["badge_code"] == "case_closed"
    client.post("/logout", headers={"X-CSRFToken": csrf})
    _signin(client, app, admin, role="admin")
    assert _data(client.get("/profile"))["equippedBadge"]["code"] == "case_closed"


def test_admin_preview_frontend_contracts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    room = (root / "frontend/src/player/TrophyRoom.jsx").read_text()
    frontend = (root / "frontend/src/player/main.jsx").read_text()
    assert "previewMode || Boolean(badge.earned && badge.awardId)" in room
    assert "savePreview" in room
    assert "PREVIEWING" in room and "TRY ON" in room
    assert "data.trophyPreview.url" in frontend
    assert "data.equippedBadge?.preview" in frontend
